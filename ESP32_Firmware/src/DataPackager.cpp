#include "DataPackager.h"

String DataPackager::package(const String& location,
                             const std::vector<WifiAccessPoint>& aps,
                             std::map<String, float>& filteredRssi) {
    String payload = location;
    for (size_t i = 0; i < aps.size(); i++) {
        payload += ",";
        payload += aps[i].bssid + "|" + aps[i].ssid + ":" + String(filteredRssi[aps[i].bssid], 2);
    }
    return payload;
}