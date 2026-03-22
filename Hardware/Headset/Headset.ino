// ======================== CODE FOR HEADSET ========================
#include <Wire.h>
#include "Adafruit_MAX1704X.h"
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

#define DEVICE_HEADSET
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
const char* ssid = "LOW's S24+"; // My phone will always be with me. Network (should) be available.
const char* password = "uuykg2ags4uyncf";

// -------- MQTT --------
const char* mqttServer = "192.168.0.10"; // TODO: set to your laptop LAN IP
const int mqttPort = 8883;

WiFiClientSecure espClient;
PubSubClient client(espClient);

// -------- MAX17048 --------
Adafruit_MAX17048 maxlipo;
float battHist[3] = {0,0,0};
int battIndex = 0;
bool battStable = false;

// -------- Microphone --------
const int sampleWindow = 10;
const int AMP_PIN = 34;

// -------- MPU6050 --------
const int MPU_ADDR = 0x68;
int16_t AcX, AcY, AcZ, GyX, GyY, GyZ;
int16_t pAcX = 0, pAcY = 0, pAcZ = 0;
int16_t pGyX = 0, pGyY = 0, pGyZ = 0;

/* MPU1050 (IMU) Tuning Set Here*/
const int ACC_THRESH  = 7000;
const int GYRO_THRESH = 3000;

// -------- Timing --------
unsigned long lastSend = 0;
const unsigned long SEND_INTERVAL = 200;

// -------- WiFi + MQTT --------

void connectWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    breathingColor(255,255,255);
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
    breathingColor(255,255,255);
    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
    } else {
      Serial.print("failed rc=");
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

void setRGB(int r, int g, int b) {
  ledcWrite(CH_RED,   r);
  ledcWrite(CH_GREEN, g);
  ledcWrite(CH_BLUE,  b);
}

// -------- Setup --------

void setup() {
    // RGB LED init (POWER ON immediately)
  ledcSetup(CH_RED,   PWM_FREQ, PWM_RES);
  ledcSetup(CH_GREEN, PWM_FREQ, PWM_RES);
  ledcSetup(CH_BLUE,  PWM_FREQ, PWM_RES);

  ledcAttachPin(PIN_RED,   CH_RED);
  ledcAttachPin(PIN_GREEN, CH_GREEN);
  ledcAttachPin(PIN_BLUE,  CH_BLUE);

  Serial.begin(115200);

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  Wire.begin(21, 22, 100000);

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

  // ----- Microphone -----
  unsigned long startMillis = millis();
  int signalMax = 0;
  int signalMin = 4095;

  while (millis() - startMillis < sampleWindow) {
    int sample = analogRead(AMP_PIN);
    if (sample > signalMax) signalMax = sample;
    if (sample < signalMin) signalMin = sample;
  }

  int micPeakToPeak = signalMax - signalMin;

  // ----- IMU -----
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, 14, true);

  AcX = Wire.read()<<8 | Wire.read();
  AcY = Wire.read()<<8 | Wire.read();
  AcZ = Wire.read()<<8 | Wire.read();
  Wire.read(); Wire.read();
  GyX = Wire.read()<<8 | Wire.read();
  GyY = Wire.read()<<8 | Wire.read();
  GyZ = Wire.read()<<8 | Wire.read();

  bool movement =
    abs(AcX - pAcX) > ACC_THRESH ||
    abs(AcY - pAcY) > ACC_THRESH ||
    abs(AcZ - pAcZ) > ACC_THRESH ||
    abs(GyX - pGyX) > GYRO_THRESH ||
    abs(GyY - pGyY) > GYRO_THRESH ||
    abs(GyZ - pGyZ) > GYRO_THRESH;

  pAcX = AcX; pAcY = AcY; pAcZ = AcZ;
  pGyX = GyX; pGyY = GyY; pGyZ = GyZ;

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
          breathingColor(0,255,0);   // GREEN
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
    payload += "\"id\":\"" + String(DEVICE_ID) + "\",";
    payload += "\"type\":\"headset\",";

    payload += "\"voltage\":" + String(cellVoltage, 2) + ",";
    payload += "\"percent\":" + String(batteryPercent, 1) + ",";

    payload += "\"ax\":" + String(AcX) + ",";
    payload += "\"ay\":" + String(AcY) + ",";
    payload += "\"az\":" + String(AcZ) + ",";
    payload += "\"gx\":" + String(GyX) + ",";
    payload += "\"gy\":" + String(GyY) + ",";
    payload += "\"gz\":" + String(GyZ) + ",";
    payload += "\"movement\":" + String(movement ? "true" : "false")+ ",";

    payload += "\"p2p\":" + String(micPeakToPeak);

    payload += "}";

    String topic = "sensors/headset/" + String(DEVICE_ID);
    client.publish(topic.c_str(), payload.c_str());

    // ----- Serial print -----
    Serial.print("Battery: "); Serial.print(cellVoltage); Serial.print("V, ");
    Serial.print(batteryPercent); Serial.print("%, ");

    Serial.print("IMU: "); 
    Serial.print("Ax="); Serial.print(AcX); Serial.print(", ");
    Serial.print("Ay="); Serial.print(AcY); Serial.print(", ");
    Serial.print("Az="); Serial.print(AcZ); Serial.print(", ");
    Serial.print("Gx="); Serial.print(GyX); Serial.print(", ");
    Serial.print("Gy="); Serial.print(GyY); Serial.print(", ");
    Serial.print("Gz="); Serial.print(GyZ); Serial.print(", ");
    Serial.print("Movement="); Serial.println(movement ? "Yes" : "No");

    Serial.print("Mic P2P: "); Serial.println(micPeakToPeak);
    Serial.println("------------------------------------------------");
  }

}
