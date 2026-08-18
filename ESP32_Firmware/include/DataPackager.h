#ifndef DATA_PACKAGER_H
#define DATA_PACKAGER_H

#include <Arduino.h>
#include <map>
#include <vector>
#include "WifiScanner.h"

class DataPackager {
public:
    String package(const String& location,
                   const std::vector<WifiAccessPoint>& aps,
                   std::map<String, float>& filteredRssi);
};

#endif