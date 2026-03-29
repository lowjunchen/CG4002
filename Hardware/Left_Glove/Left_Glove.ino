// ======================== CODE FOR LEFT GLOVE ========================
#include <Wire.h>
#include "Adafruit_MAX1704X.h"
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

#define DEVICE_LEFT_GLOVE
#include "certs.h"
// -------- RGB LED --------
#define PIN_RED    25
#define PIN_GREEN  26
#define PIN_BLUE   27

#define CH_RED   0
#define CH_GREEN 1
#define CH_BLUE  2

#define PWM_FREQ 5000
#define PWM_RES  8   // 0–255 brightness

float breatheValue = 0;
bool breatheUp = true;
bool whiteBlinkState = false;
unsigned long lastBlink = 0;
const unsigned long BLINK_INTERVAL = 500; // ms

#define DEVICE_ID "1"

// -------- WiFi --------
const char* ssid = "XH001";  // My phone will always be with me. Network (should) be available.
const char* password = "12345678";

// -------- MQTT --------
const char* mqttServer = "18.140.9.0"; // EC2 Elastic IP; must be present in broker server SAN
const int mqttPort = 8883;

WiFiClientSecure espClient;
PubSubClient client(espClient);

// -------- MAX17048 --------
Adafruit_MAX17048 maxlipo;
float battHist[3] = {0,0,0};
int battIndex = 0;
bool battStable = false;

// -------- MPU6050 --------
const int MPU_ADDR = 0x68;

float AcXf = 0, AcYf = 0, AcZf = 0;
float GyXf = 0, GyYf = 0, GyZf = 0;

float pAcX = 0, pAcY = 0, pAcZ = 0;
float pGyX = 0, pGyY = 0, pGyZ = 0;

// For past 10 tiers
const int TIER_HISTORY = 100;
int tierHistory[TIER_HISTORY] = {0};
int tierIndex = 0;

// For Serial Monitor smoothed Tier
const int SERIAL_HISTORY = 10;
int serialTierHistory[SERIAL_HISTORY] = {0};
int serialIndex = 0;


// Low-pass filter factor (0 < alpha < 1)
const float alpha = 0.9;


/* MPU6050 (IMU) Tuning Set Here 
This does not need to be changed */
const int ACC_NONE_THRESH  = 100;  
const int GYRO_NONE_THRESH = 100;  

// Tier thresholds
const int TIER_ACC_THRESH  = 200; // if accelerometer delta < this → frail
const int TIER_GYRO_THRESH = 200; // if gyroscope delta < this → frail


// -------- Pulse Sensor --------
#define PulseWire 39
#define LED_PIN   LED_BUILTIN

int Threshold = 2000;
unsigned long lastBeatTime = 0;
bool beatDetected = false;
int BPM = 60;
const unsigned long MIN_BEAT_INTERVAL = 300;
int BPMAlert = 0;  // 0 = no alert, 1 = alert


// -------- BPM Alert --------
const int BPM_HISTORY = 10;
int bpmHistory[BPM_HISTORY] = {60};   // start with normal BPM
int bpmIndex = 0;
int LastBPM = 60;                      // last processed BPM for alert


// -------- Timing --------
#define MAX_SPEED_DEMO 1
#if MAX_SPEED_DEMO
const unsigned long SEND_INTERVAL = 20;   // 50 Hz publish for speed demo
const unsigned long LOG_INTERVAL = 1000;  // 1 Hz logging
#else
const unsigned long SEND_INTERVAL = 500;
const unsigned long LOG_INTERVAL = 500;
#endif

unsigned long lastSend = 0;
unsigned long lastLog = 0;

// -------- Functions --------

void connectWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    breathingColor(255,255,255);
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  WiFi.setSleep(false);
}

void connectMQTT() {
  client.setServer(mqttServer, mqttPort);

  while (!client.connected()) {
    String clientId = "ESP32_" + String(DEVICE_ID);
    Serial.print("Connecting MQTT... ");
    breathingColor(255,255,255);

    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.println(client.state());
      delay(2000);
    }
  }
}

void configureTLS() {
  espClient.setCACert(CA_CERT);
  espClient.setCertificate(CLIENT_CERT);
  espClient.setPrivateKey(CLIENT_KEY);
}

// void setRGB(int r, int g, int b) {
//   ledcWrite(CH_RED,   r);
//   ledcWrite(CH_GREEN, g);
//   ledcWrite(CH_BLUE,  b);
// }
void setRGB(int r, int g, int b) {
  ledcWriteChannel(CH_RED,   r);
  ledcWriteChannel(CH_GREEN, g);
  ledcWriteChannel(CH_BLUE,  b);
}

// -------- Setup --------

void setup() {
  // RGB LED init (POWER ON immediately)
// ledcSetup(CH_RED,   PWM_FREQ, PWM_RES);
// ledcSetup(CH_GREEN, PWM_FREQ, PWM_RES);
// ledcSetup(CH_BLUE,  PWM_FREQ, PWM_RES);
ledcAttachChannel(PIN_RED,   PWM_FREQ, PWM_RES, CH_RED);
ledcAttachChannel(PIN_GREEN, PWM_FREQ, PWM_RES, CH_GREEN);
ledcAttachChannel(PIN_BLUE,  PWM_FREQ, PWM_RES, CH_BLUE);

// ledcAttachPin(PIN_RED,   CH_RED);
// ledcAttachPin(PIN_GREEN, CH_GREEN);
// ledcAttachPin(PIN_BLUE,  CH_BLUE);

  Serial.begin(115200);
  Wire.begin(21, 22);

  pinMode(LED_PIN, OUTPUT);
  analogReadResolution(12);

  connectWiFi();
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  time_t now = 0;
  while (now < 1700000000) { delay(500); time(&now); }
  configureTLS();
  connectMQTT();

  // MPU6050 init
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);
  Wire.write(0);
  Wire.endTransmission(true);

  // MAX17048 init
  maxlipo.begin();
}

// -------- Loop --------
float breathePhase = 0;

void breathingColor(int r, int g, int b) {
// breathing speed
  breathePhase += 0.06;

  if (breathePhase > TWO_PI)
      breathePhase = 0;

  // smooth inhale/exhale
  float wave = (sin(breathePhase) + 1.0) / 2.0;

  // human eye correction
  wave = pow(wave, 1.8);

  // softer wearable brightness
  int brightness = 10 + wave * 90;

  int R = r * brightness / 255;
  int G = g * brightness / 255;
  int B = b * brightness / 255;

  setRGB(R, G, B);
}

void loop() {
  if (!client.connected()) connectMQTT();
  client.loop();

  unsigned long now = millis();

// ----- Pulse -----
static int prevBPM = 0; // store last valid BPM
int signal = analogRead(PulseWire);

if (signal > Threshold && !beatDetected && (now - lastBeatTime) > MIN_BEAT_INTERVAL) {
    beatDetected = true;
    digitalWrite(LED_PIN, HIGH);

    if (lastBeatTime > 0) {
        int rawBPM = 60000 / (now - lastBeatTime);

        // Reject unrealistic BPM changes
        if (rawBPM >= 50 && rawBPM <= 150) {
            // add to history
            bpmHistory[bpmIndex] = rawBPM;
            bpmIndex = (bpmIndex + 1) % BPM_HISTORY;

            // compute average BPM
            int sum = 0, count = 0;
            for (int i = 0; i < BPM_HISTORY; i++) {
                if (bpmHistory[i] > 0) {
                    sum += bpmHistory[i];
                    count++;
                }
            }
            BPM = (count > 0) ? sum / count : rawBPM;
        } else {
            BPM = LastBPM; // discard spike
        }
    }

    lastBeatTime = now;
}

if (signal < Threshold - 150) {
    beatDetected = false;
    digitalWrite(LED_PIN, LOW);
}


// ----- BPM Alert check -----
bpmHistory[bpmIndex] = BPM;
bpmIndex = (bpmIndex + 1) % BPM_HISTORY;

// Check BPMAlert
BPMAlert = true; // assume alert
for (int i = 0; i < BPM_HISTORY; i++) {
    if (bpmHistory[i] >= 60 && bpmHistory[i] <= 120) {
        BPMAlert = false; // at least one normal → no alert
        break;
    }
}

LastBPM = BPM;

  // ----- IMU -----
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  Wire.endTransmission(false);
  Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)14, true);

// Read raw MPU values
  int16_t rawAcX = Wire.read()<<8 | Wire.read();
  int16_t rawAcY = Wire.read()<<8 | Wire.read();
  int16_t rawAcZ = Wire.read()<<8 | Wire.read();
  Wire.read(); Wire.read();
  int16_t rawGyX = Wire.read()<<8 | Wire.read();
  int16_t rawGyY = Wire.read()<<8 | Wire.read();
  int16_t rawGyZ = Wire.read()<<8 | Wire.read();

  // Apply low-pass filter
  AcXf = alpha * AcXf + (1 - alpha) * rawAcX;
  AcYf = alpha * AcYf + (1 - alpha) * rawAcY;
  AcZf = alpha * AcZf + (1 - alpha) * rawAcZ;

  GyXf = alpha * GyXf + (1 - alpha) * rawGyX;
  GyYf = alpha * GyYf + (1 - alpha) * rawGyY;
  GyZf = alpha * GyZf + (1 - alpha) * rawGyZ;


  int Tier = 0; // 0 = frail/slow, 1 = normal

  int accDelta  = max(abs(AcXf - pAcX), max(abs(AcYf - pAcY), abs(AcZf - pAcZ)));
  int gyroDelta = max(abs(GyXf - pGyX), max(abs(GyYf - pGyY), abs(GyZf - pGyZ)));


  int TierStr = 0;  // default if hand not moving

  if (accDelta > TIER_ACC_THRESH || gyroDelta > TIER_GYRO_THRESH) {
      TierStr = 1; // normal movement
  } 
  else if (accDelta > ACC_NONE_THRESH || gyroDelta > GYRO_NONE_THRESH) {
      TierStr = 0; // slow/frail
  }

  // --- Serial smoothed Tier (last 10 readings) ---
serialTierHistory[serialIndex] = TierStr;
serialIndex = (serialIndex + 1) % SERIAL_HISTORY;

int serialCountOnes = 0;
for (int i = 0; i < SERIAL_HISTORY; i++) {
    if (serialTierHistory[i] == 1) serialCountOnes++;
}

int smoothedTier = (serialCountOnes > SERIAL_HISTORY / 2) ? 1 : 0;

  // ---------------------------
// Moving average over last 10 tiers
tierHistory[tierIndex] = TierStr;          // store current TierStr
tierIndex = (tierIndex + 1) % TIER_HISTORY;

// Count how many '1's in history
int tierCountOnes = 0;
for (int i = 0; i < TIER_HISTORY; i++) {
    if (tierHistory[i] == 1) tierCountOnes++;
}

// Only flip TierOutput if the majority of history says so
// 0 -> 1 requires > 50% ones
// 1 -> 0 requires <= 50% ones
static int TierOutput = 0;  // make it static so it keeps previous state
if (TierOutput == 0 && tierCountOnes > TIER_HISTORY / 2) {
    TierOutput = 1;
} 
else if (TierOutput == 1 && tierCountOnes <= TIER_HISTORY / 2) {
    TierOutput = 0;
}

// ---------------------------
  pAcX = AcXf; pAcY = AcYf; pAcZ = AcZf;
  pGyX = GyXf; pGyY = GyYf; pGyZ = GyZf;


  // ----- Battery -----
  float cellVoltage = maxlipo.cellVoltage();
  float v2dp = round(cellVoltage * 100.0) / 100.0;

  battHist[battIndex] = v2dp;
  battIndex = (battIndex + 1) % 3;
  battStable = (battHist[0] == battHist[1]);

  bool connected = false;
  float batteryPercent = 0;

  if (!isnan(cellVoltage) && battStable) {
    connected = true;
    batteryPercent = constrain((cellVoltage / 3.97) * 100.0, 0, 100);
  }

// -------- RGB Battery Indicator --------
if (batteryPercent > 0) {
    if (batteryPercent >= 60) {
        breathingColor(52,168,83);   // GREEN
    }
    else if (batteryPercent >= 30) {
        breathingColor(255,120,0);   // ORANGE
    }
    else {
        breathingColor(255,0,0);     // RED
    }

} else {
    breathingColor(255,255,255);
}
  // ----- MQTT JSON -----
  if (now - lastSend > SEND_INTERVAL) {
    lastSend = now;

    String payload = "{";
    //payload += "\"id\":\"" + String(DEVICE_ID) + "\",";
    payload += "\"type\":\"left glove\",";

    //payload += "\"voltage\":" + String(cellVoltage, 2) + ",";
    payload += "\"percent\":" + String(batteryPercent, 1) + ",";

    //payload += "\"acc\":" + String(accDelta) + ",";
    //payload += "\"gyro\":" + String(gyroDelta) + ",";
    payload += "\"Tier\":" + String(smoothedTier) + ",";


    payload += "\"bpm\":" + String(BPM) + ",";
    payload += "\"BPMAlert\":" + String(BPMAlert ? 1 : 0);

    payload += "}";

    String topic = "sensors/device/" + String(DEVICE_ID);
    client.publish(topic.c_str(), payload.c_str());

    if (now - lastLog > LOG_INTERVAL) {
      lastLog = now;
      Serial.print("Battery: "); Serial.print(cellVoltage); Serial.print("V, ");
      Serial.print(batteryPercent); Serial.print("%, ");

      Serial.print("ACC Delta: "); Serial.print(accDelta);
      Serial.print(", GYRO Delta: "); Serial.print(gyroDelta);
      Serial.print(", Smoothed Tier: ");
      Serial.println(smoothedTier);

      Serial.print("BPM: "); Serial.print(BPM);
      Serial.print(", BPMAlert: "); Serial.println(BPMAlert ? "ALERT" : "OK");
    }
  }
}
