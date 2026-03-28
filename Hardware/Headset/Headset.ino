// ======================== CODE FOR HEADSET ========================
#include <Wire.h>
#include "Adafruit_MAX1704X.h"
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <time.h>
#include <math.h>

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

#define DEVICE_ID "3"

// -------- WiFi --------
const char* ssid = "XH001";  // My phone will always be with me. Network (should) be available.
const char* password = "zxd19901120";

// -------- MQTT --------
const char* mqttServer = "Yeos-MacBook-Pro.local";
const int mqttPort = 8883;

WiFiClientSecure espClient;
PubSubClient client(espClient);

// -------- MAX17048 --------
Adafruit_MAX17048 maxlipo;
float battHist[3] = {0,0,0};
int battIndex = 0;
bool battStable = false;

// -------- Microphone --------
const int AMP_PIN = 34;

// Live audio stream settings
const int AUDIO_SAMPLE_RATE = 8000;
const int AUDIO_CHUNK_MS = 20;
const int AUDIO_CHUNK_SAMPLES = AUDIO_SAMPLE_RATE * AUDIO_CHUNK_MS / 1000; // 160 samples
uint8_t audioChunk[AUDIO_CHUNK_SAMPLES];
int audioChunkIndex = 0;
unsigned long lastAudioMicros = 0;
int micPeakToPeak = 0;

unsigned long audioPacketsSent = 0;
unsigned long lastAudioReport = 0;

// -------- MPU6050 --------
const int MPU_ADDR = 0x68;
int16_t AcX, AcY, AcZ, GyX, GyY, GyZ;
int16_t pAcX = 0, pAcY = 0, pAcZ = 0;
int16_t pGyX = 0, pGyY = 0, pGyZ = 0;

/* MPU6050 (IMU) Tuning Set Here */
const int ACC_THRESH  = 7000;
const int GYRO_THRESH = 3000;

// -------- Timing --------
unsigned long lastSend = 0;
const unsigned long SEND_INTERVAL = 200;

// -------- Forward declarations --------
void connectWiFi();
void connectMQTT();
void configureTLS();
void setRGB(int r, int g, int b);
void breathingColor(int r, int g, int b);
void streamAudioMQTT();

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
  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());
}

void connectMQTT() {
  client.setServer(mqttServer, mqttPort);

  while (!client.connected()) {
    String clientId = "ESP32_" + String(DEVICE_ID);
    Serial.print("Connecting MQTT... ");
    breathingColor(255,255,255);

    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
      // reset timing a bit after reconnect
      lastAudioMicros = micros();
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

// -------- LED --------
void setRGB(int r, int g, int b) {
  ledcWriteChannel(CH_RED,   r);
  ledcWriteChannel(CH_GREEN, g);
  ledcWriteChannel(CH_BLUE,  b);
}

float breathePhase = 0;

void breathingColor(int r, int g, int b) {
  breathePhase += 0.06;

  if (breathePhase > TWO_PI)
    breathePhase = 0;

  float wave = (sin(breathePhase) + 1.0) / 2.0;
  wave = pow(wave, 1.8);

  int brightness = 10 + wave * 90;

  int R = r * brightness / 255;
  int G = g * brightness / 255;
  int B = b * brightness / 255;

  setRGB(R, G, B);
}

// -------- Audio Streaming --------
void streamAudioMQTT() {
  const unsigned long sampleInterval = 1000000UL / AUDIO_SAMPLE_RATE;
  unsigned long nowMicros = micros();

  static int currentMax = 0;
  static int currentMin = 255;
  static unsigned long lastP2PUpdate = 0;

  while ((unsigned long)(nowMicros - lastAudioMicros) >= sampleInterval) {
    lastAudioMicros += sampleInterval;

    // Read 12-bit ADC (0..4095), compress to 8-bit (0..255)
    int raw = analogRead(AMP_PIN);
    uint8_t sample8 = raw >> 4;

    audioChunk[audioChunkIndex++] = sample8;

    

    // Update peak-to-peak from same audio samples
    if (sample8 > currentMax) currentMax = sample8;
    if (sample8 < currentMin) currentMin = sample8;

    // Publish audio chunk once full
// Publish audio chunk once full
if (audioChunkIndex >= AUDIO_CHUNK_SAMPLES) {
  String audioTopic = "audio/headset/" + String(DEVICE_ID);
  bool ok = client.publish(audioTopic.c_str(), audioChunk, AUDIO_CHUNK_SAMPLES);

  if (ok) {
    audioPacketsSent++;
    // Serial.print("Audio sent, bytes=");
    // Serial.println(AUDIO_CHUNK_SAMPLES);
  } else {
    Serial.println("Audio MQTT publish FAILED");
  }

  audioChunkIndex = 0;
}

    unsigned long nowMs = millis();
    if (nowMs - lastP2PUpdate >= 20) {
      micPeakToPeak = currentMax - currentMin;
      currentMax = 0;
      currentMin = 255;
      lastP2PUpdate = nowMs;
    }

    nowMicros = micros();
  }
}

// -------- Setup --------
void setup() {
  // RGB LED init
  ledcAttachChannel(PIN_RED,   PWM_FREQ, PWM_RES, CH_RED);
  ledcAttachChannel(PIN_GREEN, PWM_FREQ, PWM_RES, CH_GREEN);
  ledcAttachChannel(PIN_BLUE,  PWM_FREQ, PWM_RES, CH_BLUE);

  Serial.begin(115200);

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  Wire.begin(21, 22, 100000);

  // Bigger MQTT packet buffer for audio payload
  client.setBufferSize(512);

  connectWiFi();

  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  time_t now = 0;
  while (now < 1700000000) {
    delay(500);
    time(&now);
  }

  configureTLS();
  connectMQTT();

  // MPU6050 init
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);
  Wire.write(0);
  Wire.endTransmission(true);

  // MAX17048 init
  maxlipo.begin();

  lastAudioMicros = micros();

  Serial.println("Audio streaming ready at 8000 Hz");
}

// -------- Loop --------
void loop() {
  if (!client.connected()) connectMQTT();
  client.loop();

  // keep audio streaming running continuously
  streamAudioMQTT();

  if (millis() - lastAudioReport >= 1000) {
  lastAudioReport = millis();
  Serial.print("Audio packets/sec: ");
  Serial.println(audioPacketsSent);
  audioPacketsSent = 0;
}

  unsigned long now = millis();

  // ----- IMU -----
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, 14, true);

  if (Wire.available() >= 14) {
    AcX = Wire.read() << 8 | Wire.read();
    AcY = Wire.read() << 8 | Wire.read();
    AcZ = Wire.read() << 8 | Wire.read();
    Wire.read(); Wire.read(); // temp
    GyX = Wire.read() << 8 | Wire.read();
    GyY = Wire.read() << 8 | Wire.read();
    GyZ = Wire.read() << 8 | Wire.read();
  }

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
      breathingColor(255,120,0); // ORANGE
    }
    else {
      breathingColor(255,0,0);   // RED
    }
  } else {
    breathingColor(255,255,255);
  }

  // give audio streamer another chance after sensor work
  streamAudioMQTT();

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
    payload += "\"movement\":" + String(movement ? "true" : "false") + ",";
    payload += "\"p2p\":" + String(micPeakToPeak);
    payload += "}";

    String topic = "sensors/headset/" + String(DEVICE_ID);
    bool ok = client.publish(topic.c_str(), payload.c_str());

    if (!ok) {
      Serial.println("Sensor MQTT publish failed");
    }

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
    Serial.print("Movement="); Serial.print(movement ? "Yes" : "No");
    Serial.print(", Mic P2P: "); Serial.println(micPeakToPeak);

    Serial.println("------------------------------------------------");
  }
}