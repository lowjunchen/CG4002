// ======================== CODE FOR RIGHT GLOVE ========================
#include <Wire.h>
#include "Adafruit_MAX1704X.h"
#include <WiFi.h>
#include <PubSubClient.h>

#define DEVICE_ID "2"

// -------- WiFi --------
const char* ssid = "LOW's S24+"; // My phone will always be with me. Network (should) be available.
const char* password = "uuykg2ags4uyncf";

// -------- MQTT --------
const char* mqttServer = "broker.hivemq.com"; // No longer need to set IP Address
const int mqttPort = 1883;

WiFiClient espClient;
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
unsigned long lastSend = 0;
const unsigned long SEND_INTERVAL = 500;

// -------- Functions --------

void connectWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
}

void connectMQTT() {
  client.setServer(mqttServer, mqttPort);

  while (!client.connected()) {
    String clientId = "ESP32_" + String(DEVICE_ID);
    Serial.print("Connecting MQTT... ");

    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.println(client.state());
      delay(2000);
    }
  }
}

// -------- Setup --------

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);

  pinMode(LED_PIN, OUTPUT);
  analogReadResolution(12);

  connectWiFi();
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

  // ----- MQTT JSON -----
  if (now - lastSend > SEND_INTERVAL) {
    lastSend = now;

    String payload = "{";
    //payload += "\"id\":\"" + String(DEVICE_ID) + "\",";
    payload += "\"type\":\"right glove\",";

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

    // ----- Serial print -----
    Serial.print("Battery: "); Serial.print(cellVoltage); Serial.print("V, ");
    Serial.print(batteryPercent); Serial.print("%, ");

    Serial.print("ACC Delta: "); Serial.print(accDelta);
    Serial.print(", GYRO Delta: "); Serial.print(gyroDelta);
    // Serial.print(", Tier: "); Serial.println(TierOutput);
    Serial.print(", Smoothed Tier (last 10): ");
    Serial.println(smoothedTier);  // 0: Frail 1: Normal 2: NIL

    Serial.print("BPM: "); Serial.print(BPM);
    Serial.print(", BPMAlert: "); Serial.println(BPMAlert ? "ALERT" : "OK");
    Serial.println("------------------------------------------------");
  }
}
