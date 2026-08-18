import json
import os
import serial
import serial.tools.list_ports
import time
import argparse
import sys

PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KNN_DIR = os.path.join(PARENT_DIR, "PC_Online_KNN")
if KNN_DIR not in sys.path:
    sys.path.insert(0, KNN_DIR)

try:
    from knn_engine import parse_packet
except ImportError:
    parse_packet = None

DEFAULT_PORT    = "COM19"
DEFAULT_BAUD    = 115200
DEFAULT_OUTPUT  = "dataset_train.txt"
DEFAULT_SAMPLES = 30


def parse_args():
    parser = argparse.ArgumentParser(description="WiFi Fingerprint Data Collector")
    parser.add_argument("--port",    default=DEFAULT_PORT,    help="Serial port (default: COM19)")
    parser.add_argument("--baud",    default=DEFAULT_BAUD,    type=int, help="Baud rate (default: 115200)")
    parser.add_argument("--output",  default=DEFAULT_OUTPUT,  help="Output file (default: dataset_train.txt)")
    parser.add_argument("--samples", default=DEFAULT_SAMPLES, type=int, help="Samples to collect per room (default: 500)")
    return parser.parse_args()

def list_available_ports():
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("[INFO] Khong tim thay cong Serial/COM nao tren may tinh.")
        return
    print("[INFO] Danh sach cac cong Serial hien co:")
    for p in ports:
        print(f"   - {p.device}: {p.description}")


def is_valid_csv_line(line: str, room_name: str) -> bool:

    if not line.startswith(room_name):
        return False
    if "," not in line:
        return False
    if "|" not in line:
        return False
    return True
def collect_data(port, baud, output_file, num_samples, room_name: str, x: float, y: float, floor: int):
    if not room_name:
        print("[ERROR] Ten phong khong duoc de trong.")
        sys.exit(1)

    try:
        x_val = float(x)
        y_val = float(y)
        floor_val = int(floor)
    except (TypeError, ValueError):
        print("[ERROR] X, Y va floor phai la so hop le.")
        sys.exit(1)

    print(f"\n[INFO] Bat dau thu thap {num_samples} mau cho phong: {room_name}")
    print(f"[INFO] Vi tri: x={x_val}, y={y_val}, floor={floor_val}")
    print(f"[INFO] Port: {port} | Baud: {baud} | File: {output_file}")
    print("[INFO] Nhan Ctrl+C de dung som.\n")

    count = 0
    try:
        ser = serial.Serial(port, baud, timeout=0.01)

        print(f"[INFO] Dang gui lenh cap nhat location '{room_name}' den ESP32...")
        ack_received = False
        start_wait = time.time()

        while time.time() - start_wait < 10:
            ser.write(f"LOC:{room_name}\n".encode())
            time.sleep(0.01)

            while ser.in_waiting > 0:
                raw = ser.readline()
                line = raw.decode("utf-8", errors="ignore").strip()
                if "[LOC]" in line or line.startswith(room_name):
                    ack_received = True
                    print(f"[OK] ESP32 da xac nhan location: {room_name}")
                    break
            if ack_received:
                break

        if not ack_received:
            print(f"[WARN] ESP32 chua phan hoi ACK trong 10s. Vẫn tiep tuc lang nghe & gui lai LOC...")

        ser.reset_input_buffer()
        print(f"[INFO] Bat dau ghi du lieu JSONL vao dataset...\n")

        dropped_count = 0
        buffer = []
        buffer_size = 10
        idle_wait_seconds = 0.0
        last_valid_rx = time.monotonic()

        with open(output_file, "a", encoding="utf-8") as f:
            while count < num_samples:
                raw = ser.readline()
                if not raw:
                    idle_wait_seconds += 0.01
                    if idle_wait_seconds >= 2.0:
                        print(f"[WARN] Chua nhan duoc data tu ESP32 trong 2s. Dang gui lai LOC:{room_name}...")
                        ser.write(f"LOC:{room_name}\n".encode())
                        idle_wait_seconds = 0.0
                        dropped_count += 1
                    if dropped_count >= 5:
                        print("[WARN] ESP32 khong phan hoi sau 5 lan retry. Kiem tra port/baud/firmware.")
                        break
                    continue

                idle_wait_seconds = 0.0
                last_valid_rx = time.monotonic()
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                print(f"[RX] {line[:120]}")

                if "," in line and "|" in line and not line.startswith(room_name):
                    dropped_count += 1
                    if dropped_count >= 2:
                        print(f"\n[RETRY] ESP32 dang dung location cu, dang gui lai LOC:{room_name}...")
                        ser.write(f"LOC:{room_name}\n".encode())
                        dropped_count = 0
                    continue

                if not is_valid_csv_line(line, room_name):
                    continue

                try:
                    if parse_packet is None:
                        raise RuntimeError("parse_packet not available")
                    _, rssi_map = parse_packet(line)
                except Exception as e:
                    print(f"[WARN] parse_packet loi: {e}")
                    continue

                if not rssi_map:
                    print("[WARN] RSSI map rong sau khi parse.")
                    continue

                record = {
                    "room": room_name,
                    "x": x_val,
                    "y": y_val,
                    "floor": floor_val,
                    "aps": rssi_map,
                }
                buffer.append(json.dumps(record, ensure_ascii=False))
                count += 1

                if len(buffer) >= buffer_size:
                    f.write("\n".join(buffer) + "\n")
                    buffer = []

                preview = line[:80] + ("..." if len(line) > 80 else "")
                print(f"[SAVE] {count}/{num_samples} | room={room_name} | x={x_val} y={y_val} | raw={preview}")

            if buffer:
                f.write("\n".join(buffer) + "\n")

        print(f"\n\n[DONE] Da thu {count} mau cho phong '{room_name}' tai x={x_val}, y={y_val}, floor={floor_val} → {output_file}")

    except KeyboardInterrupt:
        print(f"\n[STOP] Dung thu thap. Da luu {count} mau.")
    except serial.SerialException as e:
        print(f"[ERROR] Khong mo duoc port {port}: {e}")
        list_available_ports()
    finally:
        if "ser" in locals() and ser.is_open:
            ser.close()


if __name__ == "__main__":
    args = parse_args()

    room_name = input("Nhap ten phong (VD: PHONG_HOC_I303): ").strip()
    if not room_name:
        print("[ERROR] Ten phong khong duoc de trong.")
        sys.exit(1)

    while True:
        try:
            x_value = float(input("Nhap toa do X (m): ").strip())
            y_value = float(input("Nhap toa do Y (m): ").strip())
            break
        except ValueError:
            print("[ERROR] X va Y phai la so thuc. Vd: 5.5")

    while True:
        try:
            floor_value = int(input("Nhap tang (VD: 1): ").strip())
            break
        except ValueError:
            print("[ERROR] Tang phai la so nguyen. Vd: 1")

    collect_data(args.port, args.baud, args.output, args.samples, room_name, x_value, y_value, floor_value)