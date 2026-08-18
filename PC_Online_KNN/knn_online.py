import json
import argparse
import sys
import os
import paho.mqtt.client as mqtt

from knn_engine import EMAFilter, parse_packet, load_dataset, predict_wknn

# ── Cấu hình mặc định ──────────────────────────────────────────────────────────
DEFAULT_BROKER      = "172.15.144.142"
DEFAULT_PORT        = 1883
DEFAULT_SUB_TOPIC   = "wifi/scan"
DEFAULT_PUB_TOPIC   = "location/result"
DEFAULT_DATASET     = "../PC_Offline_Collector/dataset_train.txt"
DEFAULT_K           = 5
DEFAULT_EMA_ALPHA   = 0.3


def parse_args():
    parser = argparse.ArgumentParser(description="WiFi WKNN Online Positioning Engine (Headless Python Backend)")
    parser.add_argument("--broker",  default=DEFAULT_BROKER,    help=f"MQTT Broker IP (mặc định: {DEFAULT_BROKER})")
    parser.add_argument("--port",    default=DEFAULT_PORT, type=int, help=f"MQTT Broker Port (mặc định: {DEFAULT_PORT})")
    parser.add_argument("--sub-topic", default=DEFAULT_SUB_TOPIC, help=f"Topic lắng nghe dữ liệu RSSI (mặc định: {DEFAULT_SUB_TOPIC})")
    parser.add_argument("--pub-topic", default=DEFAULT_PUB_TOPIC, help=f"Topic phát kết quả JSON (mặc định: {DEFAULT_PUB_TOPIC})")
    parser.add_argument("--dataset", default=DEFAULT_DATASET,   help="Đường dẫn file dataset_train.txt")
    parser.add_argument("--k",       default=DEFAULT_K, type=int, help="Số hàng xóm K (mặc định: 5)")
    parser.add_argument("--alpha",   default=DEFAULT_EMA_ALPHA, type=float, help="Hệ số lọc EMA alpha (mặc định: 0.3)")
    return parser.parse_args()


class IndoorPositioningBackend:
    def __init__(self, broker: str, port: int, sub_topic: str, pub_topic: str, dataset_path: str, k: int, alpha: float):
        self.broker = broker
        self.port = port
        self.sub_topic = sub_topic
        self.pub_topic = pub_topic
        self.dataset_path = os.path.abspath(dataset_path)
        self.k = k
        self.ema_filter = EMAFilter(alpha=alpha)

        # 1. Load dataset Fingerprint khi khởi động
        print(f"[INFO] Đang nạp file dataset từ '{self.dataset_path}'...")
        self.dataset = load_dataset(self.dataset_path)

        # Fallback nếu dataset không tìm thấy ở đường dẫn tương đối
        if not self.dataset:
            fallback_path = os.path.abspath("../maps.dut.udn.vn/dataset_train.txt")
            if os.path.exists(fallback_path):
                print(f"[INFO] Thử nạp dataset từ đường dẫn fallback: '{fallback_path}'...")
                self.dataset = load_dataset(fallback_path)

        if not self.dataset:
            print(f"[WARN] CẢNH BÁO: Dataset rỗng hoặc không tìm thấy file dataset_train.txt!")
        else:
            print(f"[OK] Đã nạp thành công {len(self.dataset)} mẫu Fingerprint vào RAM!")

        # 2. Khởi tạo MQTT Client
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="Python_WKNN_Engine")
        except AttributeError:
            self.client = mqtt.Client(client_id="Python_WKNN_Engine")

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print(f"[MQTT OK] Đã kết nối Broker '{self.broker}:{self.port}'!")
            print(f"[MQTT OK] Đang Subscribe topic '{self.sub_topic}'...")
            client.subscribe(self.sub_topic)
        else:
            print(f"[MQTT ERROR] Kết nối thất bại. Mã lỗi rc={rc}")

    def on_disconnect(self, client, userdata, rc, properties=None):
        if rc != 0:
            print(f"[MQTT WARN] Mất kết nối bất ngờ (rc={rc}). Đang tự động kết nối lại...")

    def on_message(self, client, userdata, msg):
        """Xử lý dữ liệu nhận được từ ESP32 trên topic wifi/scan"""
        try:
            raw_payload = msg.payload.decode("utf-8", errors="ignore")
            _loc_sent, rssi_map = parse_packet(raw_payload)

            if not rssi_map:
                print("[WARN] Nhận gói tin wifi/scan rỗng hoặc sai định dạng!")
                return

            # Áp dụng bộ lọc EMA
            smoothed_rssi = {}
            for bssid, rssi_val in rssi_map.items():
                smoothed_rssi[bssid] = self.ema_filter.update(bssid, rssi_val)

            # Chạy thuật toán WKNN
            predicted_room, confidence, neighbors = predict_wknn(
                current_rssi=smoothed_rssi,
                dataset=self.dataset,
                k=self.k
            )

            # Tạo payload JSON để đẩy sang Frontend
            result_payload = {
                "predicted_room": predicted_room,
                "confidence": confidence
            }
            json_str = json.dumps(result_payload, ensure_ascii=False)

            # Publish kết quả lên MQTT topic location/result
            self.client.publish(self.pub_topic, json_str)

            print(f"[WKNN OK] Phòng dự đoán: {predicted_room:20s} | Độ tin cậy: {confidence:5.1f}% | AP Quét được: {len(smoothed_rssi)}")

        except Exception as e:
            print(f"[ERROR] Lỗi trong quá trình xử lý gói tin: {e}")

    def start(self):
        try:
            print(f"[INFO] Khởi động Python Backend Engine (Headless Mode)...")
            print(f"[INFO] Lắng nghe topic: '{self.sub_topic}' ---> Xuất kết quả topic: '{self.pub_topic}'")
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_forever()
        except KeyboardInterrupt:
            print("\n[INFO] Dừng chương trình Python Backend.")
            self.client.disconnect()
            sys.exit(0)
        except Exception as e:
            print(f"[ERROR] Không thể kết nối tới MQTT Broker: {e}")
            sys.exit(1)


def main():
    args = parse_args()
    engine = IndoorPositioningBackend(
        broker=args.broker,
        port=args.port,
        sub_topic=args.sub_topic,
        pub_topic=args.pub_topic,
        dataset_path=args.dataset,
        k=args.k,
        alpha=args.alpha
    )
    engine.start()


if __name__ == "__main__":
    main()
