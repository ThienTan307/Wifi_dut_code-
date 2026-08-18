#ifndef EMA_FILTER_H
#define EMA_FILTER_H
#include <Arduino.h>
#include <map>

class EMAFilter {
private:
    float alpha;
    std::map<String, float> filteredData;
public:
    EMAFilter(float alphaValue);
    float filter(String bssid, int rssi);
    void reset();
};
#endif