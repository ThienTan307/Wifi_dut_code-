#include "WifiScanner.h"

void WifiScanner::init() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    delay(100);
}

std::vector<WifiAccessPoint> WifiScanner::scan() {
    std::vector<WifiAccessPoint> apList;
    int n = WiFi.scanNetworks();
    for (int i = 0; i < n; ++i) {
        WifiAccessPoint ap;
        ap.bssid = WiFi.BSSIDstr(i);
        ap.ssid  = WiFi.SSID(i);
        ap.rssi  = WiFi.RSSI(i);
        apList.push_back(ap);
    }
    return apList;
}