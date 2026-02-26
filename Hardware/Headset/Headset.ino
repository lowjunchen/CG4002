// ======================== CODE FOR HEADSET ========================
#include <Wire.h>
#include "Adafruit_MAX1704X.h"
#include <WiFi.h>
#include <PubSubClient.h>

#define DEVICE_ID "1"

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
      Serial.print("failed rc=");
      Serial.println(client.state());
      delay(2000);
    }
  }
}

// -------- Setup --------

void setup() {
  Serial.begin(115200);

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  Wire.begin(21, 22, 100000);

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
