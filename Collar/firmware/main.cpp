/*
 * Whim GeoF — ESP32-S3 Collar Firmware
 * Reads GPS, checks point-in-polygon geofence, sends LoRa heartbeat packets.
 * Uses DeepSleep for power conservation.
 *
 * Hardware: ESP32-S3 + GPS module (UART) + SX1276 LoRa + IMU (accelerometer)
 *
 * LoRa Spreading Factor set to SF12 for maximum range in hilly Ozarks terrain.
 */

#include <Arduino.h>
#include <LoRa.h>
#include <TinyGPSPlus.h>
#include <SPIFFS.h>
#include <ArduinoJson.h>
#include <Wire.h>

// ==================== PIN DEFINITIONS ====================
#define GPS_RX_PIN        16
#define GPS_TX_PIN        17
#define GPS_BAUD          9600

#define LORA_SS_PIN       5
#define LORA_RST_PIN      14
#define LORA_DIO0_PIN     2
#define LORA_FREQ         915E6  // US frequency band
#define LORA_SF           12     // SF12 for hilly terrain / max range
#define LORA_TX_POWER     20     // dBm

#define IMU_ADDR          0x68   // MPU6050 default I2C address
#define IMU_SDA_PIN       21
#define IMU_SCL_PIN       22

#define BATT_ADC_PIN      34     // Battery voltage divider

// ==================== TIMING ====================
#define HEARTBEAT_INTERVAL_US  (20ULL * 60 * 1000000)  // 20 minutes
#define MOTION_INTERVAL_US     (5ULL  * 60 * 1000000)  // 5 minutes when motion detected
#define GPS_TIMEOUT_MS         30000                     // 30s to acquire fix
#define MOTION_THRESHOLD       2000                      // IMU threshold for movement

// ==================== GLOBALS ====================
static const char* COLLAR_ID   = "C001";
static const char* COLLAR_NAME = "Cow-1";
static const char* FENCE_PATH  = "/fence.json";

TinyGPSPlus gps;
HardwareSerial gpsSerial(1);

struct FenceVertex {
    float lat;
    float lon;
};

FenceVertex fenceVertices[32];
int fenceVertexCount = 0;

RTC_DATA_ATTR int bootCount = 0;
RTC_DATA_ATTR bool lastMotionDetected = false;

// ==================== FENCE LOADING ====================

bool loadFence() {
    if (!SPIFFS.begin(true)) return false;

    File f = SPIFFS.open(FENCE_PATH, "r");
    if (!f) return false;

    StaticJsonDocument<2048> doc;
    DeserializationError err = deserializeJson(doc, f);
    f.close();
    if (err) return false;

    JsonArray verts = doc["vertices"];
    fenceVertexCount = 0;
    for (JsonArray v : verts) {
        if (fenceVertexCount >= 32) break;
        fenceVertices[fenceVertexCount].lat = v[0].as<float>();
        fenceVertices[fenceVertexCount].lon = v[1].as<float>();
        fenceVertexCount++;
    }
    return true;
}

// ==================== POINT-IN-POLYGON ====================

bool pointInPolygon(float lat, float lon) {
    if (fenceVertexCount < 3) return true;  // no fence = inside

    bool inside = false;
    int j = fenceVertexCount - 1;
    for (int i = 0; i < fenceVertexCount; i++) {
        float yi = fenceVertices[i].lon;
        float xi = fenceVertices[i].lat;
        float yj = fenceVertices[j].lon;
        float xj = fenceVertices[j].lat;

        if (((yi > lon) != (yj > lon)) &&
            (lat < (xj - xi) * (lon - yi) / (yj - yi) + xi)) {
            inside = !inside;
        }
        j = i;
    }
    return inside;
}

// ==================== BATTERY ====================

int readBatteryPercent() {
    int raw = analogRead(BATT_ADC_PIN);
    // 12-bit ADC, voltage divider assumes 2:1 ratio
    float voltage = (raw / 4095.0) * 3.3 * 2.0;
    // LiPo: 4.2V = 100%, 3.0V = 0%
    int pct = (int)((voltage - 3.0) / 1.2 * 100.0);
    if (pct > 100) pct = 100;
    if (pct < 0) pct = 0;
    return pct;
}

// ==================== IMU ====================

bool checkMotion() {
    Wire.beginTransmission(IMU_ADDR);
    Wire.write(0x3B);  // ACCEL_XOUT_H
    Wire.endTransmission(false);
    Wire.requestFrom(IMU_ADDR, 6);

    if (Wire.available() < 6) return false;

    int16_t ax = (Wire.read() << 8) | Wire.read();
    int16_t ay = (Wire.read() << 8) | Wire.read();
    int16_t az = (Wire.read() << 8) | Wire.read();

    int32_t magnitude = (int32_t)ax * ax + (int32_t)ay * ay + (int32_t)az * az;
    // Subtract gravity (~16384^2) and check threshold
    int32_t gravSq = 16384L * 16384L;
    int32_t delta = abs(magnitude - gravSq);

    return delta > ((int32_t)MOTION_THRESHOLD * MOTION_THRESHOLD);
}

// ==================== GPS ====================

bool acquireGPS(float &lat, float &lon) {
    gpsSerial.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
    unsigned long start = millis();

    while (millis() - start < GPS_TIMEOUT_MS) {
        while (gpsSerial.available()) {
            gps.encode(gpsSerial.read());
        }
        if (gps.location.isUpdated() && gps.location.isValid()) {
            lat = gps.location.lat();
            lon = gps.location.lng();
            return true;
        }
        delay(10);
    }
    return false;
}

// ==================== LORA TRANSMIT ====================

bool initLoRa() {
    LoRa.setPins(LORA_SS_PIN, LORA_RST_PIN, LORA_DIO0_PIN);
    if (!LoRa.begin(LORA_FREQ)) return false;
    LoRa.setSpreadingFactor(LORA_SF);
    LoRa.setTxPower(LORA_TX_POWER);
    LoRa.enableCrc();
    return true;
}

void sendPacket(float lat, float lon, int battery, bool outsideFence) {
    // CSV format: COLLAR_ID,LAT,LON,BATTERY,NAME[,ALERT]
    String payload = String(COLLAR_ID) + "," +
                     String(lat, 6) + "," +
                     String(lon, 6) + "," +
                     String(battery) + "," +
                     String(COLLAR_NAME);
    if (outsideFence) {
        payload += ",OUTSIDE_FENCE";
    }

    LoRa.beginPacket();
    LoRa.print(payload);
    LoRa.endPacket();
}

void sendEmergencyPacket(float lat, float lon, int battery) {
    // Immediate transmission — outside fence
    for (int i = 0; i < 3; i++) {  // retry 3x for emergency
        sendPacket(lat, lon, battery, true);
        delay(500);
    }
}

// ==================== MAIN ====================

void setup() {
    Serial.begin(115200);
    bootCount++;

    Wire.begin(IMU_SDA_PIN, IMU_SCL_PIN);

    // Wake IMU from sleep
    Wire.beginTransmission(IMU_ADDR);
    Wire.write(0x6B);  // PWR_MGMT_1
    Wire.write(0x00);
    Wire.endTransmission();

    loadFence();

    if (!initLoRa()) {
        Serial.println("LoRa init failed");
        esp_deep_sleep(HEARTBEAT_INTERVAL_US);
        return;
    }

    float lat = 0, lon = 0;
    bool hasFix = acquireGPS(lat, lon);
    int battery = readBatteryPercent();
    bool motionDetected = checkMotion();

    if (hasFix) {
        bool inside = pointInPolygon(lat, lon);
        if (!inside) {
            sendEmergencyPacket(lat, lon, battery);
            Serial.println("ALERT: Outside fence!");
        } else {
            sendPacket(lat, lon, battery, false);
            Serial.println("Status OK — inside fence");
        }
    } else {
        // No GPS fix — send status with last known or zeros
        sendPacket(0, 0, battery, false);
        Serial.println("No GPS fix — heartbeat only");
    }

    lastMotionDetected = motionDetected;

    // Sleep interval: 5 min if motion, 20 min if idle
    uint64_t sleepTime = motionDetected
        ? MOTION_INTERVAL_US
        : HEARTBEAT_INTERVAL_US;

    Serial.printf("Boot #%d | Batt: %d%% | Motion: %s | Sleep: %llu min\n",
                  bootCount, battery, motionDetected ? "YES" : "NO",
                  sleepTime / 60000000ULL);

    LoRa.sleep();
    esp_deep_sleep(sleepTime);
}

void loop() {
    // Never reached — ESP32 uses deep sleep + reboot cycle
}
