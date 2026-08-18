# EMA và WKNN trong hệ thống định vị WiFi

## Tổng quan

Thuật toán chính thực sự dùng trong code là **Weighted K-Nearest Neighbor (WKNN)**, không phải KNN thuần túy. Hệ thống áp dụng hai lớp lọc / làm mượt:

1. **EMA tại firmware ESP32**: làm mượt tín hiệu ngay trên thiết bị
2. **EMA tại Python**: làm mượt lại dữ liệu nhận được trước khi tính toán

Mục tiêu là giảm nhiễu RSSI và cải thiện độ ổn định khi so sánh với dataset.

---

## 1. EMA – Exponential Moving Average

### Cách tính

```text
EMA_new = alpha * RSSI_raw + (1 - alpha) * EMA_prev
```

Trong code được dùng với:

```python
self.alpha = 0.3
```

### Lý do dùng EMA

RSSI trên WiFi rất dễ bị dao động vì:

- phản xạ từ tường
- các thiết bị khác phát sóng cùng lúc
- nhiễu môi trường
- thay đổi vị trí người dùng rất nhỏ

EMA làm dữ liệu có tính ổn định hơn, giúp điểm đo hiện tại gần với fingerprint trong dataset.

### Ở đâu áp dụng

- ESP32: file `src/main.cpp`, `EMAFilter filter(0.3f);`
- Python: `PC_Online_KNN/knn_engine.py`, class `EMAFilter`

---

## 2. WKNN – Weighted K-Nearest Neighbor

### Ý tưởng

Tại mỗi lần quét, hệ thống lấy bản đồ RSSI hiện tại và so sánh với từng mẫu trong `dataset_train.txt`. Sau đó:

- tính khoảng cách Euclidean giữa tín hiệu hiện tại và từng mẫu training
- chọn `k` mẫu gần nhất
- gán trọng số bằng nghịch đảo khoảng cách
- cộng trọng số theo từng phòng
- phòng có tổng trọng số lớn nhất là kết quả dự đoán

### Công thức trọng số

```text
w_i = 1 / (d_i + epsilon)
```

với `epsilon` rất nhỏ để tránh chia cho 0.

### Công thức độ tin cậy

```text
confidence = (W_best / total_weight) * 100%
```

Trong code, hàm thực hiện là `predict_wknn()`.

---

## 3. Hàm parse_packet

Trong `knn_engine.py`, hàm `parse_packet(raw_line)` giúp xử lý nhiều định dạng dữ liệu khác nhau:

- JSON payload từ MQTT
- chuỗi CSV dạng `PHONG,MAC:RSSI|...`
- chuỗi MQTT dạng `SSID:RSSI,BSSID`

Ví dụ:

```python
location, rssi_map = parse_packet(raw_line)
```

Nó trả về:

- `location`: tên phòng
- `rssi_map`: dictionary dạng `{bssid_lowercase: rssi}`

Điều này rất quan trọng vì firmware phần lớn emit cả dạng CSV và JSON, và Python cần xử lý được cả hai.

---

## 4. Đo khoảng cách

Hàm `euclidean_distance(current_rssi, train_point)` tính khoảng cách giữa vector RSSI hiện tại và vector fingerprint mẫu.

```python
dist_sq = sum((current_val - train_val)^2)
```

Nếu BSSID không có trong training sample, code dùng default penalty `-100.0`.

---

## 5. Hàm chính trong engine

| Hàm / Class | Chức năng |
|---|---|
| `EMAFilter` | lọc RSSI bằng EMA ở Python |
| `parse_packet()` | tách dữ liệu đầu vào thành `location` và `rssi_map` |
| `load_dataset()` | đọc `dataset_train.txt` vào RAM |
| `euclidean_distance()` | tính khoảng cách Euclidean |
| `predict_wknn()` | chạy weighted KNN và trả về phòng dự đoán |
| `print_prediction()` | in log ra terminal cho debug |

---

## 6. Script backend đang chạy trong hệ thống

Có 2 script chính dùng cùng logic:

- `PC_Online_KNN/knn_online.py`
- `PC_Online_KNN/mqtt_server.py`

Cả hai đều import `knn_engine.py` và thực hiện các công việc tương tự:

- nhận dữ liệu RSSI đầu vào
- làm mượt EMA
- gọi `predict_wknn()`
- kết luận phòng dự đoán
- publish JSON `location/result`

---

## 7. Kỳ vọng về độ tin cậy

Khi dataset chất lượng tốt và không gian có nhiều AP rõ, hệ thống hoạt động ổn định. Tuy nhiên:

- nếu trong phòng có ít AP thì xác suất sai tăng
- nếu phân bố dữ liệu training quá ít hoặc không đồng đều thì confidence dễ thấp
- `k` quá lớn hoặc quá nhỏ cũng làm dự đoán không ổn

Mặc định hệ thống đang dùng `k = 5` và `alpha = 0.3`.
