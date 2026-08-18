# Map Visualization và giao diện web

## Tổng quan

Dự án này không còn dùng một file `map_visualizer.py` theo kiểu matplotlib như mô tả cũ. Hệ thống hiện tại hiển thị vị trí trên bản đồ bằng web frontend chạy trên `maps.dut.udn.vn`, và kết quả đến từ backend MQTT.

Tác vụ chính của frontend:

1. tải cấu hình phòng từ `room_config.json`
2. kết nối MQTT over WebSocket đến broker
3. subscribe topic `location/result`
4. nhận JSON `{ "predicted_room": "...", "confidence": ... }`
5. cập nhật vị trí người dùng trên bản đồ

---

## Cấu trúc frontend thực tế

Các file quan trọng:

- `maps.dut.udn.vn/index.html`
- `maps.dut.udn.vn/script.js`
- `maps.dut.udn.vn/room_config.json`

`script.js` là phần chính chứa logic giao diện và MQTT client.

---
---

## Kết nối MQTT WebSocket trên frontend

Trong `script.js`, cấu hình thực tế là:

```js
const CONFIG = {
  ROOM_CONFIG_URL: './room_config.json',
  MQTT_PRIMARY_URL: 'ws://192.168.2.115:9001',
  MQTT_FALLBACK_URL: 'ws://127.0.0.1:9001',
  MQTT_RESULT_TOPIC: 'location/result'
};
```

Frontend làm các nhiệm vụ:

- `loadRoomConfig()` đọc file JSON
- `connectMQTTWebSockets()` nối tới broker websocket
- `handleLocationResult(payload)` parse JSON
- `updateMapUI(roomKey, confidence)` cập nhật UI

---

## Dạng payload gửi về frontend

Backend Python publish JSON dạng:

```json
{"predicted_room": "PHONG_HOC_1", "confidence": 88.7}
```

Sau đó, `script.js` gọi:

```js
const roomKey = data.predicted_room || data.room || 'Chưa xác định';
const confidence = parseFloat(data.confidence) || 0.0;
```

và hiển thị trên HUD UI.

---

## Giao diện hiển thị

UI không còn là một cửa sổ matplotlib như mô tả cũ. Thay vào đó, frontend hiển thị:

- tên phòng dự đoán
- độ tin cậy (%)
- vị trí người dùng trên bản đồ bằng dot đỏ
- các thông tin phòng và router từ `room_config.json`

---

## Mô hình dữ liệu trong web UI

`roomConfigMap = jsonData.rooms ? jsonData.rooms : jsonData;`

Nghĩa là frontend hỗ trợ cả 2 dạng:

- `rooms` được lồng trong một object lớn
- hoặc json trực tiếp toàn bộ map config

Nó sau đó dùng `roomDetails.x/y` để set vị trí chấm on-map.

---

## Lưu ý về map và room name

`predicted_room` phải khớp với tên key trong `rooms` ban đầu. Ví dụ nếu backend dự đoán `PHONG_HOC_1` nhưng `rooms` trong JSON dùng `Phong_Hoc_1`, UI sẽ không tìm thấy tọa độ và dot đỏ không di chuyển.

Điều này là nguyên nhân phổ biến của lỗi giao diện: tên phòng sai định dạng hoặc không khớp chính xác.

---

## Kết luận

Web map hiện tại là một frontend MQTT-based UI, không phải `matplotlib` animation. Hệ thống hiện thực đang hoạt động theo mô hình:

```text
ESP32 -> MQTT -> Python WKNN -> MQTT location/result -> Web map
```
