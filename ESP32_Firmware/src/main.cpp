#include <Arduino.h>
#include "WifiScanner.h"
#include "EMA_filter.h"
#include "DataPackager.h"
#include <WiFi.h>
#include <PubSubClient.h>
#include <algorithm>
#include <cmath>

const char* WIFI_SSID       = "Tan";
const char* WIFI_PASS       = "12345678";
const char* MQTT_SERVER     = "172.20.10.5";  
const int   MQTT_PORT       = 1883;
const char* MQTT_CLIENT_ID  = "ESP32-S3-GW";
const char* MQTT_TOPIC      = "wifi/scan";
const int   TOP_K           = 5;                

WifiScanner  scanner;
EMAFilter    filter(0.3f);
DataPackager packager;

WiFiClient   wifiClient;
PubSubClient mqttClient(wifiClient);

String        currentLocation    = "Vi_Tri_Hien_Tai";
unsigned long lastScanTime       = 0;
const unsigned long SCAN_INTERVAL_MS = 2000;


float calculateDistance(float rssi, float measuredPower = -29.0f, float n = 4.0f) {
    if (rssi == 0) return -1.0f;
    return pow(10.0f, (measuredPower - rssi) / (10.0f * n));
}


void connectWiFi() {
    if (WiFi.status() == WL_CONNECTED) return;
    Serial.printf("[WiFi] Connecting to %s", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    unsigned long t0 = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t0 < 10000) {
        delay(500);
        Serial.print(".");
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[WiFi] Connected → IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
        Serial.println("\n[WiFi] FAILED – continuing offline");
    }
}

// ─── MQTT connect ─────────────────────────────
unsigned long lastMqttRetry = 0;
const unsigned long MQTT_RETRY_INTERVAL_MS = 10000;

void connectMQTT() {
    if (mqttClient.connected()) return;
    if (WiFi.status() != WL_CONNECTED) return;

    unsigned long now = millis();
    if (lastMqttRetry != 0 && (now - lastMqttRetry < MQTT_RETRY_INTERVAL_MS)) return;
    lastMqttRetry = now;

    Serial.printf("[MQTT] Connecting to %s:%d ...", MQTT_SERVER, MQTT_PORT);
    if (mqttClient.connect(MQTT_CLIENT_ID)) {
        Serial.println(" OK");
    } else {
        Serial.printf(" FAILED (state=%d)\n", mqttClient.state());
    }
}

void publishMQTT(const std::vector<WifiAccessPoint>& sortedAps,
                 std::map<String, float>& filteredValues,
                 int topN)
{
    if (!mqttClient.connected()) return;

    String payload = "{";
    payload += "\"gw\":\"" + String(MQTT_CLIENT_ID) + "\",";
    payload += "\"loc\":\"" + currentLocation + "\",";
    payload += "\"aps\":[";

    for (int i = 0; i < topN; i++) {
        float fRssi = filteredValues[sortedAps[i].bssid];
        float dist  = calculateDistance(fRssi);
        if (i > 0) payload += ",";
        payload += "{";
        payload += "\"mac\":\"" + sortedAps[i].bssid + "\",";
        payload += "\"ssid\":\"" + sortedAps[i].ssid + "\",";
        payload += "\"rssi\":" + String(sortedAps[i].rssi) + ",";
        payload += "\"ema\":" + String(fRssi, 2) + ",";
        payload += "\"dist\":" + String(dist, 2);
        payload += "}";
    }

    payload += "]}";

    bool ok = mqttClient.publish(MQTT_TOPIC, payload.c_str());
    Serial.printf("[MQTT] Publish %s → %s (%d bytes)\n",
                  MQTT_TOPIC, ok ? "OK" : "FAIL", payload.length());
}

// ─────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    scanner.init();          
    connectWiFi();
    mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
    mqttClient.setBufferSize(512);
    connectMQTT();
}

void loop() {

    while (Serial.available() > 0) {
        String input = Serial.readStringUntil('\n');
        input.trim();
        if (input.startsWith("LOC:")) {
            currentLocation = input.substring(4);
            Serial.printf("[LOC] Đã đổi location → %s\n", currentLocation.c_str());
        }
    }


    if (!mqttClient.connected()) connectMQTT();
    mqttClient.loop();

    // ── Scan mỗi SCAN_INTERVAL_MS ──
    if (millis() - lastScanTime >= SCAN_INTERVAL_MS) {
        lastScanTime = millis();

        std::vector<WifiAccessPoint> rawAps = scanner.scan();
        std::map<String, float>      filteredValues;

        for (const auto& ap : rawAps) {
            filteredValues[ap.bssid] = filter.filter(ap.bssid, ap.rssi);
        }

        // Sắp xếp AP theo RSSI giảm dần (gần nhất lên đầu)
        std::vector<WifiAccessPoint> sortedAps = rawAps;
        std::sort(sortedAps.begin(), sortedAps.end(),
                  [](const WifiAccessPoint& a, const WifiAccessPoint& b) {
                      return a.rssi > b.rssi;
                  });

        int topN = min((int)sortedAps.size(), TOP_K);

        // ── Serial debug: in TOP_K AP gần nhất ──
        Serial.println("================ Top Scanned APs ================");
        for (int i = 0; i < topN; i++) {
            float fRssi = filteredValues[sortedAps[i].bssid];
            float dist  = calculateDistance(fRssi);
            Serial.printf("mac: %s : rssi: %d (ema: %.2f dBm) : dist: %.2f m : ssid: %s\n",
                          sortedAps[i].bssid.c_str(),
                          sortedAps[i].rssi,
                          fRssi,
                          dist,
                          sortedAps[i].ssid.c_str());
        }
        Serial.println("=================================================");

        // ── MQTT: ném 1 packet JSON chứa TOP_K con lên broker ──
        publishMQTT(sortedAps, filteredValues, topN);

        // ── Serial CSV: tương thích PC_Offline_Collector ──
        String dataToSend = packager.package(currentLocation, rawAps, filteredValues);
        Serial.println(dataToSend);
    }
    
}
