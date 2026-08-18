# Offline Collector

## Mục đích

`PC_Offline_Collector/collector.py` dùng để thu thập fingerprint offline cho từng phòng. Người dùng đứng ở một phòng, script sẽ gửi lệnh `LOC:<phòng>` tới ESP32 qua Serial, rồi lưu các mẫu WiFi về file `dataset_train.txt`.

File này là dữ liệu tham chiếu cho thuật toán WKNN sau này.

---

## Cách script hoạt động

`collector.py` làm đúng các bước sau:

1. Nhận cổng Serial của ESP32 (`--port`)
2. Yêu cầu người dùng nhập tên phòng
3. Gửi lệnh `LOC:<ten_phong>` liên tục trong 10 giây để xác nhận vị trí
4. Mở file output (`dataset_train.txt`) và append từng mẫu hợp lệ
5. Ngừng khi thu đủ số mẫu theo `--samples`
6. Có cơ chế tự kiểm tra nếu máy nhận đang nhận dữ liệu sai phòng thì resend `LOC`

---

## Cấu hình mặc định hiện tại

Trong file `collector.py`, các giá trị mặc định là:

```python
DEFAULT_PORT    = "COM19"
DEFAULT_BAUD    = 115200
DEFAULT_OUTPUT  = "dataset_train.txt"
DEFAULT_SAMPLES = 200
```

Điều này khác với nhiều tài liệu cũ dùng `COM3` và `50 mẫu`. Đây là cấu hình hiện hành trong code.

---

## Cách chạy

### Chạy cơ bản

```bash
cd d:\wifi_dut\PC_Offline_Collector
python collector.py
```

### Chạy với cổng và mẫu tùy chỉnh

```bash
python collector.py --port COM19 --baud 115200 --samples 200 --output dataset_train.txt
```

### Xem danh sách cổng Serial có sẵn

Script có hàm `list_available_ports()` tự in các port hiện có nếu không khởi động được.

---

## Định dạng file dataset

Mỗi dòng trong `dataset_train.txt` tương ứng với một mẫu quét WiFi từ một phòng.

Ví dụ:

```text
PHONG_HOC_1,54:04:63:01:b0:51|DUT_WIFI:-28.5|54:04:63:01:b1:22|TP-Link:-32.1
PHONG_HOC_1,54:04:63:01:b0:51|DUT_WIFI:-29.1|54:04:63:01:b1:22|TP-Link:-31.7
PHONG_HOC_2,54:04:63:01:c0:11|CafeWiFi:-62.4|54:04:63:01:d0:22|OfficeWiFi:-59.8
```

Các quy tắc:

- một dòng = một mẫu dạng fingerprint
- nhiều dòng cùng tên phòng = dữ liệu training cho phòng đó
- file được ghi tiếp nối (`append`) theo thời gian
- nếu cần training lại, nên xóa file và thu từ đầu

---

## Quy trình thu thập chuẩn

1. Nạp firmware lên ESP32
2. Kết nối ESP32 qua USB
3. Chạy:

```bash
python collector.py --port COM19 --samples 200
```

4. Nhập tên phòng, ví dụ: `PHONG_HOC_1`
5. Đứng yên và chờ script ghi đủ 200 mẫu
6. Lặp lại cho các phòng còn lại

---

## Khuyến nghị thực tế

- Thu tối thiểu 100–200 mẫu/phòng để tăng độ ổn định
- Đứng ở nhiều vị trí trong cùng một phòng nếu có thể
- Tránh di chuyển trong lúc thu mẫu
- Luôn kiểm tra tên phòng trùng khớp với `room_config.json` và tên phòng trong web map
- Trước khi chạy backend, hãy chắc dataset không rỗng

---

## Các lỗi thường gặp

### Port không mở

```text
[ERROR] Khong mo duoc port COM19: ...
```

Giải pháp:

- kiểm tra cổng COM trên Device Manager
- đổi `--port` sang cổng thực tế
- đảm bảo ESP32 được cấp nguồn và kết nối đúng USB

### Dữ liệu nhận được không đúng phòng

Script có cơ chế phát hiện và tự `RETRY` gửi lại `LOC:<room_name>`.

### File dataset rỗng

Nếu script không ghi được dữ liệu, cần kiểm tra:

- firmware đang chạy đúng
- Serial port đúng
- `LOC:<room_name>` có được ESP32 phản hồi hay không
- `Serial.println()` của ESP32 đang phát dữ liệu như kỳ vọng
