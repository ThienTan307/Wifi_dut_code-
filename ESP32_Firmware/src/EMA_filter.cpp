#include "EMA_filter.h"

EMAFilter::EMAFilter(float alphaValue) {
    alpha = alphaValue;
}

float EMAFilter::filter(String bssid, int rssi) {
    if (filteredData.find(bssid) == filteredData.end()) {
        filteredData[bssid] = rssi;
    } else {
        filteredData[bssid] = (alpha * rssi) + ((1.0 - alpha) * filteredData[bssid]);
    }
    return filteredData[bssid];
}

void EMAFilter::reset() {
    filteredData.clear();
}