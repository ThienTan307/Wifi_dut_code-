#ifndef WIFI_SCANNER_H
#define WIFI_SCANNER_H

#include <Arduino.h>
#include <WiFi.h>
#include <vector>
#include <map>

struct WifiAccessPoint {
    String bssid;
    String ssid;
    int    rssi;
};

class WifiScanner {
public:
    void init();
    std::vector<WifiAccessPoint> scan();
};

#endif