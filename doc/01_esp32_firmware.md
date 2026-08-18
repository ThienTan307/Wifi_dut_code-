# ESP32 Firmware

## Tổng quan

Firmware nằm trong thư mục `ESP32_Firmware/` được xây dựng bằng **PlatformIO + Arduino framework**. Nó thực hiện quét WiFi, làm mượt RSSI bằng EMA, đưa dữ liệu lên MQTT và đồng thời phát ra chuỗi CSV qua cổng Serial để phục vụ `collector.py`.

Dòng chính của hệ thống:

1. ESP32 nhận lệnh `LOC:<room_name>` từ máy tính qua Serial
2. Mỗi 2 giây, thực hiện quét mạng WiFi xung quanh
3. Lọc RSSI bằng EMA để giảm nhiễu
4. Sắp xếp danh sách AP theo mức độ mạnh yếu của tín hiệu
5. In log debug và gửi dữ liệu tới:
   - Serial: để thu mẫu offline
   - MQTT: để backend Python xử lý trực tiếp

---

## Cấu trúc thư mục

```text
ESP32_Firmware/
├── include/
│   ├── DataPackager.h
│   ├── EMA_filter.h
│   └── WifiScanner.h
├── src/
│   ├── DataPackager.cpp
│   ├── EMA_filter.cpp
│   ├── main.cpp
│   ├── WifiScanner.cpp
│   └── ...
├── platformio.ini
├── compile_commands.json
└── test/
```

---

## Biến cấu hình chính

Trong `src/main.cpp` có các hằng số thực tế sau:

```cpp
const char* WIFI_SSID      = "@PHICOMM_09";
const char* WIFI_PASS      = "12345678";
const char* MQTT_SERVER    = "192.168.2.115";
const int   MQTT_PORT      = 1883;
const char* MQTT_CLIENT_ID = "ESP32-S3-GW";
const char* MQTT_TOPIC     = "wifi/scan";
const int   TOP_K          = 5;
const unsigned long SCAN_INTERVAL_MS = 2000;
```

Điều này cho thấy firmware hiện tại đang cố định:

- kết nối tới AP WiFi `@PHICOMM_09`
- publish lên broker MQTT `192.168.2.115`
- topic `wifi/scan`
- chỉ gửi top 5 AP mạnh nhất

---

## Module `WifiScanner`

File:

- `include/WifiScanner.h`
- `src/WifiScanner.cpp`

`WifiScanner` thực hiện:

- chuyển WiFi sang mode Station (`WiFi.mode(WIFI_STA)`)
- gọi `WiFi.scanNetworks()`
- trả về một vector chứa các Access Point với dạng:

```cpp
struct WifiAccessPoint {
    String bssid;
    String ssid;
    int    rssi;
};
```

Hàm chính:

- `init()`: khởi tạo radio WiFi
- `scan()`: quét, lọc và trả về danh sách AP

---

## Module `EMAFilter`

File:

- `include/EMA_filter.h`
- `src/EMA_filter.cpp`

Bộ lọc EMA dùng công thức:

```text
EMA_new = alpha * RSSI_raw + (1 - alpha) * EMA_prev
```

Trong code thiết lập `alpha = 0.3f`.

Mục tiêu:

- giảm nhiễu từ RSSI liên tục thay đổi
- giữ được xu hướng tín hiệu ổn định hơn
- cho KNN có tín hiệu khoảng cách ổn định hơn

Hàm chính:

- `EMAFilter(float alphaValue)`
- `float filter(String bssid, int rssi)`
- `void reset()`

---

## Module `DataPackager`

File:

- `include/DataPackager.h`
- `src/DataPackager.cpp`

DataPackager chuyển dữ liệu AP thành chuỗi CSV để gửi qua Serial. Dạng thực tế:

```text
PHONG_HOC_1,54:04:63:01:b0:51|DUT_WIFI:-28.5,54:04:63:01:b1:22|TP-Link:-32.1
```

Cấu trúc:

- Phần đầu: tên phòng
- Mỗi phần tử AP: `BSSID|SSID:RSSI`
- Các phần tử được ngăn cách bằng dấu phẩy và `|`

---

## Vòng lặp `main.cpp`

Logic chính trong `loop()` như sau:

1. Đọc lệnh Serial nếu có `LOC:<room_name>`
2. Nếu MQTT chưa kết nối thì thử kết nối lại
3. Mỗi `SCAN_INTERVAL_MS = 2000ms`, thực hiện:
   - `scanner.scan()`
   - áp dụng EMA filter
   - sắp xếp AP theo RSSI giảm dần
   - in TOP_K AP mạnh nhất ra Serial
   - publish JSON lên MQTT topic `wifi/scan`
   - gửi chuỗi CSV qua Serial cho `collector.py`

Hàm `publishMQTT(...)` tạo payload JSON với các field:

- `gw`
- `loc`
- `aps[]`
- từng AP có `mac`, `ssid`, `rssi`, `ema`, `dist`

---

## Lệnh build và flash

```bash
cd d:\wifi_dut\ESP32_Firmware
pio run
pio run --target upload
pio device monitor
```

Nếu muốn kiểm tra Serial ở máy tính:

```bash
pio device monitor -b 115200
```

---

## Lưu ý quan trọng

- Firmware hiện tại không chỉ gửi dữ liệu qua Serial, mà còn publish lên MQTT.
- Chế độ `LOC:<room_name>` là cách giao tiếp chính để gán phòng khi thu dataset.
- Khi `collector.py` đang chạy, nó gửi lại lệnh `LOC:<room_name>` nếu ESP32 phát hiện dữ liệu không đúng phòng hoặc socket bị mất đồng bộ.
