// ======================== CODE FOR HEADSET ========================
#include <Wire.h>
#include "Adafruit_MAX1704X.h"
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <time.h>
#include <math.h>
#include "driver/i2s.h"
#include "esp_task_wdt.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

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
#define PWM_RES  8

#define I2S_WS   14   // LRCL
#define I2S_SCK  13   // BCLK
#define I2S_SD   34   // DOUT

#define I2S_PORT I2S_NUM_0

// -------- Audio tuning --------
const int NOISE_GATE = 6;

const int AUDIO_SAMPLE_RATE = 8000;
const int AUDIO_CHUNK_MS = 20;
const int AUDIO_CHUNK_SAMPLES = AUDIO_SAMPLE_RATE * AUDIO_CHUNK_MS / 1000; // 160
const int AUDIO_QUEUE_LEN = 8; // 160 ms of buffering

struct AudioChunk {
  int16_t samples[AUDIO_CHUNK_SAMPLES];
};

QueueHandle_t audioQueue = nullptr;
TaskHandle_t audioTaskHandle = nullptr;

volatile int micPeakToPeak = 0;
volatile uint32_t audioDroppedChunks = 0;

unsigned long audioPacketsSent = 0;
unsigned long lastAudioReport = 0;

// -------- Device ID --------
#define DEVICE_ID "3"

// -------- WiFi --------
const char* ssid = "jytest02";
const char* password = "12345678";

// -------- MQTT --------
const char* mqttServer = "18.140.9.0";
const int mqttPort = 8883;

WiFiClientSecure espClient;
PubSubClient client(espClient);

const char* AUDIO_TOPIC  = "audio/headset/3";
const char* SENSOR_TOPIC = "sensors/headset/3";

// -------- MAX17048 --------
Adafruit_MAX17048 maxlipo;
float battHist[3] = {0, 0, 0};
int battIndex = 0;
bool battStable = false;

// -------- MPU6050 --------
const int MPU_ADDR = 0x68;
int16_t AcX, AcY, AcZ, GyX, GyY, GyZ;
int16_t pAcX = 0, pAcY = 0, pAcZ = 0;
int16_t pGyX = 0, pGyY = 0, pGyZ = 0;

const int ACC_THRESH  = 7000;
const int GYRO_THRESH = 3000;

// -------- Timing --------
unsigned long lastSend = 0;
const unsigned long SEND_INTERVAL = 200;

unsigned long lastIMURead = 0;
unsigned long lastBatteryRead = 0;
unsigned long lastLedUpdate = 0;
unsigned long lastMQTTAttempt = 0;

const unsigned long IMU_INTERVAL_MS = 20;
const unsigned long BATTERY_INTERVAL_MS = 500;
const unsigned long LED_INTERVAL_MS = 20;
const unsigned long MQTT_RETRY_MS = 2000;

// -------- Cached sensor values --------
float cellVoltage = NAN;
float batteryPercent = 0;
bool connectedBattery = false;
bool movement = false;

// -------- LED state --------
float breathePhase = 0.0f;

// -------- Forward declarations --------
void connectWiFi();
void connectMQTTNonBlocking();
void configureTLS();
void setRGB(int r, int g, int b);
void breathingColor(int r, int g, int b);
void audioCaptureTask(void* parameter);
void publishAudioFromQueue(uint8_t maxChunks);
void serviceIMU(unsigned long now);
void serviceBattery(unsigned long now);
void serviceLED(unsigned long now);
void serviceSensorPublish(unsigned long now);
void printStatus(unsigned long now);

// -------- WiFi + MQTT --------
void connectWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    breathingColor(255, 255, 255);
    delay(200);
    Serial.print(".");
  }

  Serial.println("\nWiFi connected");
  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());
}

void connectMQTTNonBlocking() {
  if (client.connected()) return;
  if (WiFi.status() != WL_CONNECTED) return;

  unsigned long now = millis();
  if (now - lastMQTTAttempt < MQTT_RETRY_MS) return;
  lastMQTTAttempt = now;

  Serial.print("Connecting MQTT... ");
  if (client.connect("ESP32_3")) {
    Serial.println("connected");
  } else {
    int s = client.state();
    Serial.print("failed rc=");
    Serial.print(s);
    Serial.print(" | WiFi=");
    Serial.print(WiFi.status());

    time_t nowT;
    time(&nowT);
    Serial.print(" | epoch=");
    Serial.println((long)nowT);
  }
}

void configureTLS() {
  espClient.setCACert(CA_CERT);
  espClient.setCertificate(CLIENT_CERT);
  espClient.setPrivateKey(CLIENT_KEY);
}

// ------ INMP441 ---------
void setupI2S() {
  const i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = AUDIO_SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 256,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  const i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD
  };

  i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_PORT, &pin_config);
  i2s_zero_dma_buffer(I2S_PORT);
}

// -------- LED --------
void setRGB(int r, int g, int b) {
  ledcWriteChannel(CH_RED,   r);
  ledcWriteChannel(CH_GREEN, g);
  ledcWriteChannel(CH_BLUE,  b);
}

void breathingColor(int r, int g, int b) {
  breathePhase += 0.06f;
  if (breathePhase > TWO_PI) breathePhase = 0;

  float wave = (sin(breathePhase) + 1.0f) * 0.5f;
  wave = powf(wave, 1.8f);

  int brightness = 10 + (int)(wave * 90.0f);
  setRGB((r * brightness) / 255, (g * brightness) / 255, (b * brightness) / 255);
}

void audioCaptureTask(void* parameter) {
  int32_t i2sBuffer[AUDIO_CHUNK_SAMPLES];
  AudioChunk chunk;
  size_t bytesRead;

  for (;;) {
    i2s_read(
      I2S_PORT,
      (void*)i2sBuffer,
      sizeof(i2sBuffer),
      &bytesRead,
      portMAX_DELAY
    );

    int samplesRead = bytesRead / sizeof(int32_t);
    if (samplesRead > AUDIO_CHUNK_SAMPLES) samplesRead = AUDIO_CHUNK_SAMPLES;

    int16_t currentMax = -32768;
    int16_t currentMin = 32767;

    for (int i = 0; i < samplesRead; i++) {
      int32_t sample = i2sBuffer[i] >> 14;

      if (abs(sample) < (NOISE_GATE << 4)) sample = 0;

      if (sample > 32767) sample = 32767;
      if (sample < -32768) sample = -32768;

      int16_t s16 = (int16_t)sample;
      chunk.samples[i] = s16;

      if (s16 > currentMax) currentMax = s16;
      if (s16 < currentMin) currentMin = s16;
    }

    for (int i = samplesRead; i < AUDIO_CHUNK_SAMPLES; i++) {
      chunk.samples[i] = 0;
    }

    micPeakToPeak = currentMax - currentMin;

    if (xQueueSend(audioQueue, &chunk, 0) != pdTRUE) {
      audioDroppedChunks++;
    }
  }
}

void publishAudioFromQueue(uint8_t maxChunks) {
  if (!client.connected()) return;

  AudioChunk chunk;
  uint8_t sentThisCall = 0;

  while (sentThisCall < maxChunks) {
    if (xQueueReceive(audioQueue, &chunk, 0) != pdTRUE) break;

    bool ok = client.publish(
      AUDIO_TOPIC,
      (const uint8_t*)chunk.samples,
      sizeof(chunk.samples)
    );

    if (!ok) {
      Serial.println("Audio MQTT publish FAILED");
      break;
    }

    audioPacketsSent++;
    sentThisCall++;
  }
}

// -------- Services --------
void serviceIMU(unsigned long now) {
  if (now - lastIMURead < IMU_INTERVAL_MS) return;
  lastIMURead = now;

  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, 14, true);

  if (Wire.available() >= 14) {
    AcX = Wire.read() << 8 | Wire.read();
    AcY = Wire.read() << 8 | Wire.read();
    AcZ = Wire.read() << 8 | Wire.read();
    Wire.read(); Wire.read();
    GyX = Wire.read() << 8 | Wire.read();
    GyY = Wire.read() << 8 | Wire.read();
    GyZ = Wire.read() << 8 | Wire.read();
  }

  movement =
    abs(AcX - pAcX) > ACC_THRESH ||
    abs(AcY - pAcY) > ACC_THRESH ||
    abs(AcZ - pAcZ) > ACC_THRESH ||
    abs(GyX - pGyX) > GYRO_THRESH ||
    abs(GyY - pGyY) > GYRO_THRESH ||
    abs(GyZ - pGyZ) > GYRO_THRESH;

  pAcX = AcX; pAcY = AcY; pAcZ = AcZ;
  pGyX = GyX; pGyY = GyY; pGyZ = GyZ;
}

void serviceBattery(unsigned long now) {
  if (now - lastBatteryRead < BATTERY_INTERVAL_MS) return;
  lastBatteryRead = now;

  float v = maxlipo.cellVoltage();
  float v2dp = roundf(v * 100.0f) / 100.0f;

  battHist[battIndex] = v2dp;
  battIndex = (battIndex + 1) % 3;

  battStable = (battHist[0] == battHist[1]);

  connectedBattery = false;
  batteryPercent = 0.0f;
  cellVoltage = v;

  if (!isnan(cellVoltage) && battStable) {
    connectedBattery = true;
    batteryPercent = constrain((cellVoltage / 3.97f) * 100.0f, 0.0f, 100.0f);
  }
}

void serviceLED(unsigned long now) {
  if (now - lastLedUpdate < LED_INTERVAL_MS) return;
  lastLedUpdate = now;

  if (batteryPercent > 0) {
    if (batteryPercent >= 60) {
      breathingColor(0, 255, 0);
    } else if (batteryPercent >= 30) {
      breathingColor(255, 120, 0);
    } else {
      breathingColor(255, 0, 0);
    }
  } else {
    breathingColor(255, 255, 255);
  }
}

void serviceSensorPublish(unsigned long now) {
  if (!client.connected()) return;
  if (now - lastSend < SEND_INTERVAL) return;
  lastSend = now;

  char payload[256];
  snprintf(
    payload,
    sizeof(payload),
    "{\"id\":\"%s\",\"type\":\"headset\",\"voltage\":%.2f,\"percent\":%.1f,\"ax\":%d,\"ay\":%d,\"az\":%d,\"gx\":%d,\"gy\":%d,\"gz\":%d,\"movement\":%s,\"p2p\":%d}",
    DEVICE_ID,
    cellVoltage,
    batteryPercent,
    AcX, AcY, AcZ,
    GyX, GyY, GyZ,
    movement ? "true" : "false",
    micPeakToPeak
  );

  if (!client.publish(SENSOR_TOPIC, payload)) {
    Serial.println("Sensor MQTT publish failed");
  }
}

void printStatus(unsigned long now) {
  static unsigned long lastStatusPrint = 0;
  if (now - lastStatusPrint < 1000) return;
  lastStatusPrint = now;

  Serial.print("Audio packets/sec: ");
  Serial.print(audioPacketsSent);
  Serial.print(" | dropped chunks: ");
  Serial.print(audioDroppedChunks);
  Serial.print(" | queue depth: ");
  Serial.println(uxQueueMessagesWaiting(audioQueue));
  audioPacketsSent = 0;

  Serial.print("Battery: ");
  Serial.print(cellVoltage);
  Serial.print("V, ");
  Serial.print(batteryPercent);
  Serial.print("%, ");
  Serial.print("Movement=");
  Serial.print(movement ? "Yes" : "No");
  Serial.print(", Mic P2P: ");
  Serial.println(micPeakToPeak);
  Serial.println("------------------------------------------------");
}

// -------- Setup --------
void setup() {
  esp_task_wdt_config_t wdt_config = {
    .timeout_ms = 5000,
    .idle_core_mask = 0,
    .trigger_panic = true
  };
  esp_task_wdt_init(&wdt_config);
  esp_task_wdt_add(NULL);

  ledcAttachChannel(PIN_RED,   PWM_FREQ, PWM_RES, CH_RED);
  ledcAttachChannel(PIN_GREEN, PWM_FREQ, PWM_RES, CH_GREEN);
  ledcAttachChannel(PIN_BLUE,  PWM_FREQ, PWM_RES, CH_BLUE);

  Serial.begin(115200);

  Wire.begin(21, 22, 400000);

  client.setBufferSize(1024);
  client.setServer(mqttServer, mqttPort);
  configureTLS();

  audioQueue = xQueueCreate(AUDIO_QUEUE_LEN, sizeof(AudioChunk));
  if (audioQueue == nullptr) {
    Serial.println("Failed to create audio queue");
    while (1) delay(1000);
  }

  connectWiFi();
  setupI2S();

  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  time_t nowTime = 0;
  while (nowTime < 1700000000) {
    delay(100);
    time(&nowTime);
  }

  while (!client.connected()) {
    connectMQTTNonBlocking();
    client.loop();
    delay(50);
  }

  Serial.println("MQTT connected, continuing setup...");

  Serial.println("Init MPU start");
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);
  Wire.write(0);
  byte mpuErr = Wire.endTransmission(true);
  Serial.print("Init MPU done, err=");
  Serial.println(mpuErr);

  Serial.println("Init MAX17048 start");
  bool maxOk = maxlipo.begin();
  Serial.print("Init MAX17048 done, ok=");
  Serial.println(maxOk ? "true" : "false");

  BaseType_t taskOk = xTaskCreatePinnedToCore(
    audioCaptureTask,
    "AudioCapture",
    4096,
    nullptr,
    2,
    &audioTaskHandle,
    1
  );
  if (taskOk == pdPASS) {
    Serial.println("Audio task started");
  } else {
    Serial.println("Audio task FAILED to start");
  }

  Serial.println("Audio streaming ready at 8000 Hz");
}

// -------- Loop --------
void loop() {
  esp_task_wdt_reset();

  unsigned long now = millis();

  connectMQTTNonBlocking();
  client.loop();

  publishAudioFromQueue(2);

  serviceIMU(now);
  serviceBattery(now);
  serviceLED(now);

  publishAudioFromQueue(2);
  serviceSensorPublish(now);
  publishAudioFromQueue(2);

  printStatus(now);

  delay(1);
}