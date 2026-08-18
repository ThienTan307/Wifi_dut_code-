# Work Session Notes - ESP32 Firmware Updates

**Date:** 2026-08-16  
**Focus:** ESP32 Firmware - WiFi Scanning & MQTT Integration  
**Status:** Active Development

---

## 📋 Summary of Recent Changes

### 1. **MQTT Integration Enhancement**
   - Implemented direct MQTT publishing of WiFi scan results
   - Configuration:
     - Server: `192.168.100.234:1883`
     - Client ID: `ESP32-S3-GW`
     - Topic: `wifi/scan`
   
   **Key Features:**
   ```cpp
   - Publishes gateway ID and current location
   - Includes top-K access points (TOP_K = 5)
   - Sends raw RSSI, EMA-filtered RSSI, and calculated distance
   - Automatic retry logic (10s intervals)
   ```

### 2. **Distance Calculation**
   - **Formula:** Path Loss Model
   ```
   Distance = 10^((P₀ - RSSI) / (10n))
   - P₀: Measured Power at 1m = -29.0 dBm
   - n: Path Loss Exponent = 4.0
   ```
   - Used for indoor WiFi positioning

### 3. **EMA Filtering System**
   - Exponential Moving Average smoothing applied to RSSI values
   - Filter coefficient: **0.3** (configurable)
   - Reduces noise from WiFi signal fluctuations
   - Files: `EMA_filter.h`, `EMA_filter.cpp`

### 4. **WiFi Connection Management**
   ```cpp
   - SSID: "THIEN TAN"
   - Password: "0912345678"
   - Connection timeout: 10 seconds
   - Graceful fallback to offline mode if connection fails
   ```

### 5. **Scan Interval Configuration**
   - Scan interval: **2000ms (2 seconds)**
   - Configurable via `SCAN_INTERVAL_MS` constant
   - Current location variable: `Vi_Tri_Hien_Tai` (Vietnamese: "Current Location")

---

## 🔧 Code Architecture

### File Structure:
```
ESP32_Firmware/
├── include/
│   ├── WifiScanner.h       // WiFi AP scanning interface
│   ├── EMA_filter.h        // Signal filtering
│   └── DataPackager.h      // Data serialization
├── src/
│   ├── main.cpp            // Main application logic
│   ├── WifiScanner.cpp     // WiFi scanning implementation
│   ├── EMA_filter.cpp      // EMA filter implementation
│   └── DataPackager.cpp    // Data packaging for MQTT
└── platformio.ini          // Build configuration
```

### Core Components:

#### **WifiScanner** (`WifiScanner.h`)
```cpp
struct WifiAccessPoint {
    String bssid;
    String ssid;
    int    rssi;
};

class WifiScanner {
    void init();
    std::vector<WifiAccessPoint> scan();
};
```
- Scans available WiFi networks
- Returns list of detected access points with signal strength

#### **DataPackager** (`DataPackager.cpp`)
```cpp
String package(const String& location,
               const std::vector<WifiAccessPoint>& aps,
               std::map<String, float>& filteredRssi);
```
- Formats WiFi data for transmission
- Output format: `location,BSSID|SSID:EMA_RSSI,...`

---

## 📡 MQTT Payload Format

```json
{
  "gw": "ESP32-S3-GW",
  "loc": "Vi_Tri_Hien_Tai",
  "aps": [
    {
      "mac": "AA:BB:CC:DD:EE:FF",
      "ssid": "Router-Name",
      "rssi": -45,
      "ema": -48.25,
      "dist": 2.15
    },
    ...
  ]
}
```

**Fields:**
- `gw`: Gateway identifier
- `loc`: Current location tag
- `aps`: Array of top-5 detected access points
- `mac`: Access point MAC address
- `ssid`: Network name
- `rssi`: Raw received signal strength
- `ema`: EMA-filtered signal strength
- `dist`: Calculated distance in meters (using path loss model)

---

## 🎯 Key Ideas & Next Steps

### ✅ Completed:
1. ✓ MQTT publisher with connection retry mechanism
2. ✓ EMA filtering for stable RSSI values
3. ✓ Path loss distance calculation
4. ✓ Top-K access point selection (TOP_K=5)
5. ✓ WiFi connection with 10s timeout

### 🔄 In Progress / To-Do:
1. **Performance Tuning**
   - Optimize scan interval (currently 2s)
   - Fine-tune EMA filter coefficient (currently 0.3)
   - Consider battery optimization for mobile scenarios

2. **Data Quality**
   - Add RSSI range validation (typically -100 to 0 dBm)
   - Implement outlier detection
   - Add signal stability detection

3. **Integration**
   - Connect to PC_Online_KNN for real-time positioning
   - Integrate with Map_Khu_I for visualization
   - Add location persistence/history

4. **Error Handling**
   - Add watchdog timer for crash recovery
   - Implement MQTT reconnection with exponential backoff
   - Add buffer for offline data (when MQTT unavailable)

5. **Testing**
   - Validate distance calculation accuracy
   - Test MQTT payload delivery reliability
   - Performance testing with high scan rates

---

## 🔗 Related Components

- **PC_Offline_Collector** (`collector.py`): Collects training dataset
- **PC_Online_KNN** (`knn_online.py`): KNN-based indoor positioning engine
- **Map Server** (`mqtt_server.py`): Receives MQTT data and updates position

---

## 📝 Configuration Reference

```cpp
// WiFi Setup
const char* WIFI_SSID       = "THIEN TAN";
const char* WIFI_PASS       = "0912345678";

// MQTT Configuration
const char* MQTT_SERVER     = "192.168.100.234";  
const int   MQTT_PORT       = 1883;
const char* MQTT_CLIENT_ID  = "ESP32-S3-GW";
const char* MQTT_TOPIC      = "wifi/scan";

// Algorithm Parameters
const int   TOP_K           = 5;                  // Top 5 APs
const float EMA_COEFF       = 0.3f;               // EMA filter factor
const float MEASURED_POWER  = -29.0f;             // dBm at 1m
const float PATH_LOSS_EXP   = 4.0f;               // Environmental factor

// Timing
const unsigned long SCAN_INTERVAL_MS         = 2000;
const unsigned long MQTT_RETRY_INTERVAL_MS   = 10000;
```

---

## 💡 Technical Notes

1. **ESP32-S3 Platform**
   - Uses Arduino framework with PlatformIO
   - WiFi module with WPA2 support
   - MQTT via PubSubClient library

2. **Signal Processing**
   - EMA provides smoothing without excessive latency
   - Path loss model calibrated for indoor environment
   - Exponent n=4 typical for indoor multi-path scenarios

3. **Reliability**
   - Non-blocking WiFi/MQTT connection handling
   - Graceful degradation if network unavailable
   - Constant scanning even without network

---

## 📞 Questions for Next Session

1. Should we add multi-location support (multiple gateways)?
2. Need to calibrate the path loss parameters for specific environment?
3. Should distance data be used for trilateration on server side?
4. Any power consumption constraints for battery-powered deployment?

---

**Last Updated:** 2026-08-16  
**Next Review:** After integration testing with KNN module
