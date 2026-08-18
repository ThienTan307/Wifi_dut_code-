# Tổng quan hệ thống định vị trong nhà theo dấu vân tay WiFi

## Mục tiêu dự án

Dự án này xây dựng một hệ thống định vị trong nhà theo kiểu WiFi fingerprinting, dùng tín hiệu RSSI từ các AP WiFi tại từng phòng để ước lượng vị trí người dùng. Hệ thống gồm 4 thành phần chính:

1. ESP32-S3 quét WiFi và gửi dữ liệu lên máy tính
2. PC_Offline_Collector thu dữ liệu học offline để tạo dataset
3. PC_Online_KNN tính toán vị trí bằng thuật toán WKNN (Weighted K-Nearest Neighbor)
4. Website trong maps.dut.udn.vn hiển thị vị trí dự đoán lên bản đồ

Thay vì dùng GPS, toàn bộ logic dựa trên "dấu vân tay WiFi" của từng không gian. Khi người dùng ở trong một vị trí, hệ thống so sánh tín hiệu hiện tại với dataset đã học rồi chọn phòng có độ tương đồng cao nhất.

---

## Kiến trúc hệ thống hiện tại

```text
ESP32 Firmware (ESP32_Firmware)
  ├─ quét WiFi
  ├─ lọc EMA
  ├─ sắp xếp AP theo RSSI
  ├─ gửi CSV qua Serial
  └─ publish JSON MQTT topic: wifi/scan

        │                                     │
        ├─ Serial (115200) ──────> collector.py
        │
        └─ MQTT Broker (192.168.2.115:1883) ──> knn_online.py / mqtt_server.py
                                                    │
                                                    │  parse_packet
                                                    │  EMAFilter
                                                    │  predict_wknn
                                                    ▼
                                            publish topic: location/result
                                                    │
                                                    ▼
                                               frontend web

PC_Offline_Collector/
  └─ collector.py
      └─ ghi dataset_train.txt

PC_Online_KNN/
  ├─ knn_engine.py
  ├─ knn_online.py
  ├─ mqtt_server.py
  ├─ room_config.json
  └─ requirements.txt

maps.dut.udn.vn/
  ├─ index.html
  ├─ script.js
  ├─ room_config.json
  └─ website hiển thị vị trí trong map
```

---

## Luồng hoạt động thực tế

| Giai đoạn | Mô tả | File chính |
|---|---|---|
| 1. Thu thập dữ liệu offline | Người dùng đứng tại từng phòng, thu nhiều mẫu WiFi và lưu vào dataset_train.txt | `PC_Offline_Collector/collector.py` |
| 2. Huấn luyện / reference data | Dataset chứa các mẫu RSSI theo từng phòng | `dataset_train.txt` |
| 3. Dự đoán vị trí | Python backend đọc dữ liệu từ ESP32 qua MQTT hoặc Serial, tính WKNN | `PC_Online_KNN/knn_engine.py` |
| 4. Hiển thị kết quả | Web frontend nhận MQTT `location/result` và cập nhật vị trí trên bản đồ | `maps.dut.udn.vn/script.js` |

---

## Dạng dữ liệu trong hệ thống

### 1. Dòng CSV từ ESP32 qua Serial

```text
PHONG_HOC_1,54:04:63:01:b0:51:-28.5|54:04:63:01:b1:22:-32.1|...
```

Cấu trúc:

- Phần đầu: tên phòng
- Sau dấu phẩy: danh sách AP dạng `BSSID:RSSI`
- Các phần tử được tách bằng `|`

### 2. JSON MQTT từ ESP32

```json
{
  "gw": "ESP32-S3-GW",
  "loc": "PHONG_HOC_1",
  "aps": [
    {"mac": "54:04:63:01:b0:51", "ssid": "DUT_WIFI", "rssi": -58, "ema": -57.4, "dist": 4.17},
    {"mac": "54:04:63:01:b1:22", "ssid": "TP-Link", "rssi": -65, "ema": -64.1, "dist": 9.02}
  ]
}
```

### 3. Kết quả dự đoán MQTT xuất ra frontend

```json
{
  "predicted_room": "PHONG_HOC_1",
  "confidence": 88.7
}
```

---

## Cấu trúc thư mục chính

```text
d:
└─ wifi_dut/
   ├─ ESP32_Firmware/
   │  ├─ include/
   │  ├─ src/
   │  ├─ platformio.ini
   │  └─ compile_commands.json
   ├─ PC_Offline_Collector/
   │  ├─ collector.py
   │  └─ dataset_train.txt
   ├─ PC_Online_KNN/
   │  ├─ knn_engine.py
   │  ├─ knn_online.py
   │  ├─ mqtt_server.py
   │  ├─ room_config.json
   │  └─ requirements.txt
   ├─ maps.dut.udn.vn/
   │  ├─ index.html
   │  ├─ script.js
   │  └─ room_config.json
   └─ doc/
      └─ các file markdown mô tả hệ thống
```

---

## Yếu tố quan trọng cần nhớ

- `collector.py` không dùng dữ liệu được phát trực tiếp từ front-end; nó thu dữ liệu từ ESP32 qua Serial.
- `knn_engine.py` thực chất là module thuật toán, không phải frontend hiển thị.
- `knn_online.py` và `mqtt_server.py` đều dùng cùng logic `parse_packet` + `predict_wknn` nhưng có mục đích khác nhau: một script chạy trực tiếp, một script làm MQTT backend.
- Website `maps.dut.udn.vn` không đọc dataset trực tiếp; nó chỉ nhận `location/result` qua MQTT WebSocket và render bản đồ.

---

## Tài liệu chi tiết

- [01_esp32_firmware.md](./01_esp32_firmware.md): mô tả firmware và cấu trúc quét WiFi
- [02_offline_collector.md](./02_offline_collector.md): quy trình thu thập fingerprint
- [03_knn_algorithm.md](./03_knn_algorithm.md): mô tả EMA và WKNN
- [04_map_visualization.md](./04_map_visualization.md): mô tả website UI và map
- [05_quickstart.md](./05_quickstart.md): hướng dẫn chạy nhanh và khắc phục lỗi
