# Thuật toán dự đoán học máy WKNN trong hệ thống định vị WiFi

## 1. Mục tiêu của thuật toán

Hệ thống định vị trong nhà dựa trên dấu vân tay WiFi (WiFi fingerprinting). Mỗi phòng được đại diện bởi một tập mẫu RSSI từ các Access Point (AP) khác nhau. Khi hệ thống thu thập tín hiệu hiện tại từ một vị trí mới, nó so sánh với các mẫu đã học trong dataset và tìm ra phòng có độ tương đồng cao nhất.

Thuật toán chính được dùng trong code hiện tại là:

- WKNN = Weighted K-Nearest Neighbor
- Đây là biến thể của KNN với trọng số theo khoảng cách

Mục đích là dự đoán phòng từ tín hiệu hiện tại dựa trên các mẫu training gần nhất.

---

## 2. Vị trí của WKNN trong hệ thống

Trong dự án này, WKNN được triển khai ở module:

- `PC_Online_KNN/knn_engine.py`
- `PC_Online_KNN/knn_online.py`
- `PC_Online_KNN/mqtt_server.py`

Công việc chính:

1. nhận dữ liệu RSSI từ ESP32 qua Serial hoặc MQTT
2. làm mượt tín hiệu bằng EMA
3. phân tích các BSSID và giá trị RSSI
4. so sánh với dataset train
5. chọn `k` mẫu gần nhất
6. tính trọng số và xác định phòng dự đoán

---

## 3. Dữ liệu đầu vào và đầu ra

### 3.1 Dữ liệu đầu vào

Mỗi mẫu trong dataset có dạng:

```text
PHONG_HOC_1,54:04:63:01:b0:51|DUT_WIFI:-28.5|54:04:63:01:b1:22|TP-Link:-32.1
```

Từ đây, Python sẽ parse thành dạng:

```python
{
  "location": "PHONG_HOC_1",
  "rssi_map": {
    "54:04:63:01:b0:51": -28.5,
    "54:04:63:01:b1:22": -32.1
  }
}
```

### 3.2 Dữ liệu hiện tại (điểm đo)

Một lần quét WiFi mới sẽ trở thành một vector RSSI dạng:

```python
{
  "54:04:63:01:b0:51": -30.2,
  "54:04:63:01:b1:22": -33.0,
  "54:04:63:01:c9:88": -67.4
}
```

### 3.3 Dữ liệu đầu ra

Hàm dự đoán trả về:

```python
(predicted_room, confidence, neighbors)
```

Ví dụ:

```text
(PHONG_HOC_1, 88.7, [...])
```

Trong đó:

- `predicted_room`: phòng dự đoán
- `confidence`: độ tin cậy (%)
- `neighbors`: danh sách k mẫu gần nhất

---

## 4. Ý tưởng của KNN và WKNN

### 4.1 KNN chuẩn

KNN hoạt động theo nguyên tắc:

- lấy điểm mới cần dự đoán
- tính khoảng cách tới từng điểm training
- chọn `k` điểm gần nhất
- xem trong `k` điểm này, phòng nào xuất hiện nhiều nhất
- chọn phòng có tần suất nhiều nhất

### 4.2 WKNN

WKNN cải tiến thêm bước trọng số:

- không chỉ chọn `k` gần nhất
- mà còn gán trọng số theo khoảng cách
- khoảng cách gần hơn thì trọng số lớn hơn
- kết quả cuối cùng là tổng trọng số của từng phòng

Điều này giúp giảm lỗi khi có những neighbor quá xa nhưng vẫn có thể ảnh hưởng đến bỏ phiếu bình thường.

---

## 5. Khoảng cách Euclidean

Để so sánh tín hiệu hiện tại với từng fingerprint training, code dùng khoảng cách Euclidean trên vector RSSI:

$$
D_i = \sqrt{\sum_{j=1}^{n} (RSSI^{current}_j - RSSI^{train}_{i,j})^2}
$$

Trong đó:

- $D_i$ là khoảng cách giữa tín hiệu hiện tại và mẫu training thứ $i$
- $n$ là số AP được xét chung giữa hai vector
- $RSSI^{current}_j$ là cường độ tín hiệu hiện tại của AP $j$
- $RSSI^{train}_{i,j}$ là cường độ tín hiệu đã lưu trong mẫu training thứ $i$

Đây là công thức chuẩn của khoảng cách Euclidean trong không gian nhiều chiều. Khi khoảng cách này càng nhỏ, hai tín hiệu càng gần nhau, nghĩa là vị trí đang đo càng giống mẫu training.

Trong code thực tế, hàm `euclidean_distance()` làm như sau:

```python
dist_sq = 0.0
for bssid, current_val in current_rssi.items():
    train_val = train_point["rssi_map"].get(bssid, default_penalty)
    diff = current_val - train_val
    dist_sq += diff * diff
return math.sqrt(dist_sq)
```
![alt text](image.png)
Nếu một BSSID hiện tại không xuất hiện trong mẫu train, code dùng giá trị mặc định:

```python
default_penalty = -100.0
```

---

## 6. Trọng số trong WKNN

Sau khi có khoảng cách `d_i` cho từng neighbor, code tính trọng số bằng phương pháp nghịch đảo khoảng cách:

$$
w_i = \frac{1}{d_i + \epsilon}
$$

với:

- $d_i$ là khoảng cách Euclidean của neighbor thứ $i$
- $\epsilon$ là số rất nhỏ, ví dụ $10^{-5}$, để tránh chia cho 0

Ý nghĩa của công thức này:

- neighbor càng gần thì $d_i$ càng nhỏ
- do đó $w_i$ càng lớn
- neighbor càng xa thì $w_i$ càng nhỏ
- vì vậy, đóng góp của các mẫu gần hơn bị ưu tiên hơn nhiều so với mẫu xa

Đây chính là "weighted" trong WKNN.

Trong code:

```python
w = 1.0 / (item["distance"] + epsilon)
```

Sau đó:

- cộng trọng số cho từng phòng
- phòng nào có tổng trọng số lớn nhất thì là dự đoán

### 6.1 Công thức tổng trọng số theo phòng

Sau khi xác định các weight của từng neighbor, hệ thống cộng dồn theo phòng:

$$
W_{room} = \sum_{i \in room} w_i
$$

Và phòng dự đoán là phòng có:

$$
room^* = \arg\max_{room} W_{room}
$$

Đây là phần quan trọng nhất của WKNN: ưu tiên các mẫu càng gần, không chỉ bỏ phiếu đơn giản như KNN thuần.

---

## 7. Độ tin cậy của dự đoán

Sau khi tìm được `best_room`, độ tin cậy được tính theo công thức:

$$
confidence = \frac{W_{best}}{\sum W} \times 100\%
$$

Nói cách khác:

- nếu tổng trọng số của phòng dự đoán chiếm phần lớn trong `k` mẫu gần nhất
- thì confidence cao
- nếu nhiều phòng cùng đóng góp trọng số gần nhau thì confidence thấp

Trong code:

```python
confidence = (room_weights[best_room] / total_weight) * 100.0
```

---

## 8. Quy trình hoạt động của WKNN trong dự án

### Bước 1: parse dữ liệu

`parse_packet(raw_line)` nhận chuỗi RSSI từ ESP32 hoặc dữ liệu train. Nó tách ra:

- `location`
- `rssi_map`

### Bước 2: load dataset

`load_dataset(filepath)` đọc file `dataset_train.txt` và nạp toàn bộ vào RAM.

### Bước 3: tính khoảng cách tới từng mẫu

Với tín hiệu hiện tại, mỗi mẫu training sẽ được tính một khoảng cách Euclidean.

### Bước 4: chọn k nearest neighbors

```python
k_neighbors = distances[:min(k, len(distances))]
```

### Bước 5: cộng trọng số theo phòng

```python
room_weights[item["location"]] += w
```

### Bước 6: xác định phòng dự đoán

```python
best_room = max(room_weights.items(), key=lambda x: x[1])[0]
```

### Bước 7: trả về kết quả

```python
return best_room, round(confidence, 1), k_neighbors
```

---

## 9. Ví dụ minh họa

Giả sử:

- `k = 5`
- 5 neighbor gần nhất có phòng tương ứng:
  - PHONG_HOC_1
  - PHONG_HOC_1
  - PHONG_HOC_1
  - PHONG_HOC_2
  - PHONG_HOC_1

Khi đó:

- PHONG_HOC_1 có 4 vote
- PHONG_HOC_2 có 1 vote
- nếu tính theo trọng số, phòng có tổng trọng lượng lớn hơn sẽ thắng

Nếu PHONG_HOC_1 chiếm 80–90% trọng số tổng, thì hệ thống sẽ dự đoán đó là vị trí hiện tại.

---

## 10. Hyperparameter trong dự án

### `k`

Trong project hiện tại, mặc định là:

```python
DEFAULT_K = 5
```

- `k` nhỏ: nhạy hơn, nhưng dễ bị ảnh hưởng bởi nhiễu
- `k` lớn: ổn định hơn, nhưng đôi khi mờ đi sự khác biệt giữa các phòng

### `alpha`

Alpha là hệ số và được dùng trong EMA:

```python
DEFAULT_EMA_ALPHA = 0.3
```

- alpha thấp: làm mượt hơn nhưng phản ứng chậm
- alpha cao: phản ứng nhanh hơn nhưng dễ nhiễu

---

## 11. Vì sao WKNN phù hợp với bài toán WiFi fingerprinting

WKNN phù hợp vì:

- RSSI có tính biến thiên mạnh theo môi trường
- các phòng trong cùng tòa nhà có thể có nhiều AP tương tự
- tín hiệu chỉ gần đúng không phải tuyệt đối
- WKNN mang lại khả năng xử lý "sự tương đồng" chứ không chỉ khớp tuyệt đối

Nó là một phương pháp học máy đơn giản nhưng hiệu quả cho bài toán định vị trong nhà bằng WiFi.

---

## 12. Điểm yếu và giới hạn

Mặc dù WKNN hiệu quả, nhưng vẫn có giới hạn:

- dữ liệu training cần được thu đủ và chính xác
- nếu môi trường thay đổi (thêm tường, đổi thiết bị AP, thay đổi vị trí router), độ chính xác sẽ giảm
- nếu AP quá ít hoặc lập bản đồ không đều, hệ thống dễ dự đoán sai
- tên phòng trong dataset phải khớp đúng với `room_config.json` để frontend hiển thị đúng

---

## 13. Kết luận

WKNN là thuật toán dự đoán học máy cốt lõi của hệ thống định vị này. Nó kết hợp:

- dữ liệu fingerprint từ dataset
- khoảng cách Euclidean giữa tín hiệu hiện tại và mẫu cũ
- `k` hàng xóm gần nhất
- trọng số nghịch đảo khoảng cách
- độ tin cậy dựa trên tổng trọng số

Kết quả là hệ thống có thể đưa ra phòng dự đoán gần đúng cho vị trí người dùng trong nhà dựa trên tín hiệu WiFi.

---

## 14. Tài liệu liên quan

- [03_knn_algorithm.md](./03_knn_algorithm.md)
- [05_quickstart.md](./05_quickstart.md)
- [00_project_overview.md](./00_project_overview.md)
