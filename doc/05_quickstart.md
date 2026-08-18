# Quickstart – Hướng dẫn chạy hệ thống theo đúng setup hiện tại

## Yêu cầu

- Python 3.10+
- PlatformIO CLI hoặc VS Code + PlatformIO extension
- ESP32-S3 kết nối qua USB
- MQTT broker đang chạy trong LAN
- `paho-mqtt` đã được cài trong môi trường Python

---

## Bước 1 – Cài đặt dependency Python

```bash
cd d:\wifi_dut\PC_Online_KNN
pip install -r requirements.txt
```

Nếu `requirements.txt` chưa có `paho-mqtt`, cần cài thêm:

```bash
pip install paho-mqtt
```

---

## Bước 2 – Flash firmware lên ESP32

```bash
cd d:\wifi_dut\ESP32_Firmware
pio run --target upload
```

Kiểm tra serial monitor:

```bash
pio device monitor
```

Bạn nên thấy log tương tự:

```text
[WiFi] Connected → IP: ...
================ Top Scanned APs ================
mac: ... : rssi: ... : dist: ... m : ssid: ...
=================================================
PHONG_HOC_1,...
```

---

## Bước 3 – Thu thập dataset offline

```bash
cd d:\wifi_dut\PC_Offline_Collector
python collector.py --port COM19 --samples 200
```

Cách dùng:

- nhập tên phòng, ví dụ: `PHONG_HOC_1`
- script sẽ gửi `LOC:PHONG_HOC_1`
- thu thập 200 mẫu
- lưu vào `dataset_train.txt`

Lưu ý: cổng thực tế trên máy của bạn có thể không phải `COM19`, nên cần thay bằng `COMx` đúng.

---

## Bước 4 – Kiểm tra `room_config.json`

Chỉnh sửa các file config nếu cần:

- `d:\wifi_dut\PC_Online_KNN\room_config.json`
- `d:\wifi_dut\maps.dut.udn.vn\room_config.json`

Phải đảm bảo:

- tên phòng trong JSON khớp với tên phòng thu thập
- BSSID của router đúng với thực tế
- `x`, `y` được định nghĩa đúng cho bản đồ

---

## Bước 5 – Chạy backend dự đoán vị trí

### Phương án A: chạy script online dự đoán qua MQTT

```bash
cd d:\wifi_dut\PC_Online_KNN
python mqtt_server.py --broker 192.168.2.115 --k 5 --alpha 0.3
```

### Phương án B: chạy script trực tiếp hơn

```bash
cd d:\wifi_dut\PC_Online_KNN
python knn_online.py --broker 192.168.2.115 --k 5 --alpha 0.3
```

Cả 2 script dùng cùng engine `knn_engine.py` và subscribe topic `wifi/scan`.

---

## Bước 6 – Mở frontend bản đồ

Mở trên browser:

- `http://maps.dut.udn.vn`
- hoặc local file nếu đang phát triển ở máy cục bộ

Frontend sẽ subscribe `location/result` và hiển thị vị trí dự đoán trên map.

---

## Gỡ lỗi thường gặp

### 1. Không mở được cổng Serial

```text
[ERROR] Khong mo duoc port COM19
```

Giải pháp:

- kiểm tra Device Manager
- đổi `--port` thành COM đúng
- đảm bảo ESP32 đang ở trạng thái online

### 2. Dataset rỗng hoặc không có phòng

```text
[WARN] CẢNH BÁO: Dataset rỗng hoặc không tìm thấy file dataset_train.txt!
```

Giải pháp:

- chạy lại `collector.py`
- kiểm tra file `dataset_train.txt` có nội dung không
- đảm bảo `LOC:<room_name>` được gửi thành công

### 3. Frontend không hiện vị trí

Nguyên nhân thường gặp:

- `predicted_room` không khớp với key trong `room_config.json`
- MQTT broker không chạy hoặc WebSocket không kết nối được
- `location/result` không nhận được message

### 4. MQTT không kết nối

- kiểm tra IP broker `192.168.2.115`
- đảm bảo port `1883` mở
- nếu cần, kiểm tra `mqtt_server.py` log để biết connection status

---

## Lưu ý thực tế

- `DEFAULT_BROKER` trong `mqtt_server.py` là `192.168.2.115` và `DEFAULT_PORT` là `1883`
- `collector.py` mặc định là `COM19`, `samples = 200`
- `k` mặc định đang là `5`
- hệ thống đang hoạt động theo mô hình `ESP32 -> MQTT -> Python -> MQTT result -> Web UI`, chứ không phải `Serial trực tiếp -> matplotlib desktop app` như mô tả cũ
