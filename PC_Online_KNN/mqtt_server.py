import json
import argparse
import sys
import os
import paho.mqtt.client as mqtt

from knn_engine import EMAFilter, parse_packet, load_dataset, predict_wknn, print_prediction

# ── Cấu hình mặc định ──────────────────────────────────────────────────────────
# Giữ cùng IP broker cho cả backend Python và Web Frontend; nếu đổi IP, phải đổi đồng bộ 3 nơi:
# - mqtt_server.py
# - knn_online.py
# - web/config/mqttConfig.js
DEFAULT_BROKER      = "172.15.144.142"
DEFAULT_PORT        = 1883
DEFAULT_SUB_TOPIC   = "wifi/scan"
DEFAULT_PUB_TOPIC   = "location/result"
DEFAULT_DATASET     = "../PC_Offline_Collector/dataset_train.txt"
DEFAULT_K           = 5
DEFAULT_EMA_ALPHA   = 0.3


def parse_args():
    parser = argparse.ArgumentParser(description="WiFi MQTT WKNN Indoor Positioning Backend (Headless Server)")
    parser.add_argument("--broker",    default=DEFAULT_BROKER,    help=f"Địa chỉ IP MQTT Broker (mặc định: {DEFAULT_BROKER})")
    parser.add_argument("--port",      default=DEFAULT_PORT, type=int, help=f"Cổng MQTT Broker (mặc định: {DEFAULT_PORT})")
    parser.add_argument("--sub-topic", default=DEFAULT_SUB_TOPIC, help=f"Topic lắng nghe dữ liệu sóng thô (mặc định: {DEFAULT_SUB_TOPIC})")
    parser.add_argument("--pub-topic", default=DEFAULT_PUB_TOPIC, help=f"Topic phát kết quả JSON (mặc định: {DEFAULT_PUB_TOPIC})")
    parser.add_argument("--dataset",   default=DEFAULT_DATASET,   help="Đường dẫn file dataset_train.txt")
    parser.add_argument("--k",         default=DEFAULT_K, type=int, help="Số hàng xóm K (mặc định: 5)")
    parser.add_argument("--alpha",     default=DEFAULT_EMA_ALPHA, type=float, help="Hệ số lọc EMA alpha (mặc định: 0.3)")
    return parser.parse_args()


class HeadlessMQTTServer:
    def __init__(self, broker: str, port: int, sub_topic: str, pub_topic: str, dataset_path: str, k: int, alpha: float):
        self.broker = broker
        self.port = port
        self.sub_topic = sub_topic
        self.pub_topic = pub_topic
        self.k = k
        self.ema_filter = EMAFilter(alpha=alpha)

        # 1. Tìm kiếm và nạp dataset_train.txt vào RAM
        candidate_paths = [
            os.path.abspath(dataset_path),
            os.path.abspath("../PC_Offline_Collector/dataset_train.txt"),
            os.path.abspath("../maps.dut.udn.vn/dataset_train.txt"),
            os.path.abspath("dataset_train.txt")
        ]

        self.dataset = []
        for path in candidate_paths:
            if os.path.exists(path):
                print(f"[INFO] Nạp dữ liệu Fingerprint từ: '{path}'...")
                self.dataset = load_dataset(path)
                if self.dataset:
                    print(f"[OK] Nạp thành công {len(self.dataset)} mẫu Fingerprint vào RAM!")
                    break

        if not self.dataset:
            print(f"[WARN] CẢNH BÁO: Không tìm thấy hoặc dataset_train.txt rỗng! WKNN sẽ không thể dự đoán.")

        # 2. Khởi tạo MQTT Client
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="Python_Headless_MQTT_Server", userdata={
                "sub_topic": self.sub_topic,
                "pub_topic": self.pub_topic
            })
        except AttributeError:
            self.client = mqtt.Client(client_id="Python_Headless_MQTT_Server", userdata={
                "sub_topic": self.sub_topic,
                "pub_topic": self.pub_topic
            })

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc, properties=None):
        codes = {
            0: "Kết nối thành công (OK)",
            1: "Sai phiên bản giao thức (Bad protocol)",
            2: "Client ID bị từ chối",
            3: "Broker không khả dụng",
            4: "Sai tài khoản/mật khẩu",
            5: "Không có quyền truy cập"
        }
        if rc == 0:
            print(f"[MQTT OK] Đã kết nối Broker '{self.broker}:{self.port}'")
            print(f"[MQTT OK] Subscribe topic lắng nghe: '{self.sub_topic}'")
            client.subscribe(self.sub_topic)
        else:
            print(f"[MQTT ERROR] Kết nối thất bại: {codes.get(rc, f'Mã lỗi rc={rc}')}")

    def on_disconnect(self, client, userdata, rc, properties=None):
        if rc != 0:
            print(f"[MQTT WARN] Mất kết nối tới Broker (rc={rc}). Đang tự động thử kết nối lại...")

    def on_message(self, client, userdata, msg):
        """Callback xử lý gói tin MQTT nhận từ ESP32"""
        try:
            # Decode gói tin thô
            raw_payload = msg.payload.decode("utf-8", errors="ignore")
            
            # Parse gói tin lấy danh sách (BSSID -> RSSI)
            _location_sent, rssi_map = parse_packet(raw_payload)

            if not rssi_map:
                print(f"[WARN] Gói tin từ topic '{msg.topic}' rỗng hoặc sai định dạng: {raw_payload[:60]}")
                return

            # Áp dụng bộ lọc EMA làm mượt tín hiệu RSSI
            smoothed_map = {}
            for bssid, rssi_val in rssi_map.items():
                smoothed_map[bssid] = self.ema_filter.update(bssid, rssi_val)

            # Chạy thuật toán WKNN (Machine Learning)
            predicted_room, confidence, k_neighbors = predict_wknn(
                current_rssi=smoothed_map,
                dataset=self.dataset,
                k=self.k
            )

            # In kết quả dự đoán lên terminal (dễ debug)
            print_prediction(predicted_room, confidence, k_neighbors)

            # Đóng gói kết quả thành JSON định dạng: {"predicted_room": "Tên_Phòng", "confidence": Độ_tin_cậy}
            result_data = {
                "predicted_room": predicted_room,
                "confidence": confidence
            }
            json_str = json.dumps(result_data, ensure_ascii=False)

            # Publish cục JSON sang topic location/result cho Web Frontend vẽ UI
            client.publish(self.pub_topic, json_str)

            print(f"[WKNN RESULT] Topic: '{msg.topic}' -> Room: {predicted_room:20s} | Confidence: {confidence:5.1f}% | APs: {len(smoothed_map)}")

        except Exception as e:
            print(f"[ERROR] Lỗi trong hàm on_message: {e}")

    def run(self):
        """Chạy server liên tục trên Terminal (Headless Mode)"""
        try:
            print(f"============================================================")
            print(f"  KHỞI ĐỘNG PYTHON MQTT WKNN SERVER (HEADLESS MODE)")
            print(f"  Broker: {self.broker}:{self.port}")
            print(f"  Sub Topic: '{self.sub_topic}' ---> Pub Topic: '{self.pub_topic}'")
            print(f"============================================================")

            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_forever()

        except KeyboardInterrupt:
            print("\n[INFO] Nhận tín hiệu ngắt từ người dùng (Ctrl+C). Đang dừng MQTT Server...")
            self.client.disconnect()
            sys.exit(0)
        except Exception as e:
            print(f"[ERROR] Lỗi không thể duy trì MQTT Server: {e}")
            sys.exit(1)


def main():
    args = parse_args()
    server = HeadlessMQTTServer(
        broker=args.broker,
        port=args.port,
        sub_topic=args.sub_topic,
        pub_topic=args.pub_topic,
        dataset_path=args.dataset,
        k=args.k,
        alpha=args.alpha
    )
    server.run()


if __name__ == "__main__":
    main()
