import math
import json
import os
from collections import defaultdict, Counter

def normalize_bssid(raw_bssid: str | None) -> str:
    """Chuẩn hóa BSSID về định dạng MAC chuẩn lowercase, bỏ dấu : full-width."""
    if raw_bssid is None:
        return ""
    value = str(raw_bssid).strip().lower()
    value = value.replace("：", ":").replace(";", ":")
    value = value.replace(" ", "").replace("\t", "")
    value = value.replace("\u200b", "")
    if value.count(":") >= 5:
        parts = [p for p in value.split(":") if p]
        # Chống trường hợp "aa:bb:cc:dd:ee:ff" hoặc "aa:bb:..." bị kèm ký tự khác
        if all(len(p) in (2, 1) for p in parts):
            value = ":".join(parts)
    return value.strip()


class EMAFilter:
    """Bộ lọc Trung bình Động Lũy thừa (Exponential Moving Average) cho RSSI."""
    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self._state: dict[str, float] = {}

    def update(self, bssid: str, rssi: float) -> float:
        bssid_lower = bssid.strip().lower()
        if bssid_lower not in self._state:
            self._state[bssid_lower] = rssi
        else:
            self._state[bssid_lower] = self.alpha * rssi + (1.0 - self.alpha) * self._state[bssid_lower]
        return self._state[bssid_lower]

    def reset(self):
        self._state.clear()


def parse_packet(raw_line: str) -> tuple[str, dict[str, float]]:
   
    if not raw_line or not isinstance(raw_line, str):
        return "", {}

    raw_line = raw_line.strip()
    if not raw_line:
        return "", {}

    # Trường hợp 1: JSON payload
    if raw_line.startswith("{") and raw_line.endswith("}"):
        try:
            data = json.loads(raw_line)
            if not isinstance(data, dict):
                return "", {}

            location = (
                data.get("loc", "")
                or data.get("location", "")
                or data.get("room", "")
            )
            rssi_map = {}
            aps = data.get("aps", [])

            if isinstance(aps, dict):
                for bssid, rssi in aps.items():
                    bssid_norm = normalize_bssid(bssid)
                    if bssid_norm and rssi is not None:
                        rssi_map[bssid_norm] = float(rssi)
            else:
                for ap in aps:
                    if not isinstance(ap, dict):
                        continue
                    # Hỗ trợ cả 2 key "mac" (ESP32) và "bssid" (Standard)
                    bssid = normalize_bssid(ap.get("bssid") or ap.get("mac") or "")
                    rssi = float(ap.get("ema", ap.get("rssi", -100.0)))
                    if bssid:
                        rssi_map[bssid] = rssi
            return location, rssi_map
        except Exception:
            pass

    # Trường hợp 2: "TenPhong,BSSID1:RSSI1|..." hoặc "SSID:RSSI,BSSID|..."
    location = ""
    tokens_part = raw_line

    if "," in raw_line and not raw_line.startswith("SSID") and ":" not in raw_line.split(",")[0]:
        # Định dạng Dataset: "Phong_D101,54:04:63:01:b0:51:-28.5|..."
        parts = raw_line.split(",", 1)
        location = parts[0].strip()
        tokens_part = parts[1]

    rssi_map = {}
    tokens = tokens_part.split("|")

    for token in tokens:
        token = token.strip()
        if not token:
            continue

        # Định dạng ESP32 MQTT: "SSID:RSSI,BSSID"
        if "," in token:
            comma_parts = token.rsplit(",", 1)
            ssid_rssi_part = comma_parts[0].strip()
            bssid_part = comma_parts[1].strip().lower()

            if ":" in ssid_rssi_part:
                rssi_str = ssid_rssi_part.rsplit(":", 1)[1].strip()
                try:
                    rssi_val = float(rssi_str)
                    bssid_norm = normalize_bssid(bssid_part)
                    if bssid_norm:
                        rssi_map[bssid_norm] = rssi_val
                except ValueError:
                    pass
        # Định dạng Dataset: "BSSID:RSSI" hoặc "BSSID|SSID:RSSI"
        elif ":" in token:
            colon_parts = token.rsplit(":", 1)
            bssid_ssid = colon_parts[0].strip()
            rssi_str = colon_parts[1].strip()

            bssid = bssid_ssid.split("|")[0].strip() if "|" in bssid_ssid else bssid_ssid.strip()
            bssid_norm = normalize_bssid(bssid)
            try:
                rssi_val = float(rssi_str)
                if bssid_norm:
                    rssi_map[bssid_norm] = rssi_val
            except ValueError:
                pass

    return location, rssi_map


def load_dataset(filepath: str) -> list[dict]:
    """Load dữ liệu mẫu Fingerprint từ dataset_train.txt vào RAM.

    Hỗ trợ cả 2 định dạng hiện có trong project:
    - TXT legacy: "PHONG_HOC_I101,AA:BB:CC:DD:EE:FF:-53|..."
    - TXT đang lưu thực tế: JSON object trên mỗi dòng chứa x, y, floor, aps

    Mỗi phần tử trong list trả về có dạng:
    {
        "location": "PHONG_HOC_I303",
        "rssi_map": {"bssid_lower": rssi_float, ...},
        "x": 2.5,
        "y": 3.1,
        "floor": 3,
    }
    """
    dataset = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Hỗ trợ dạng JSON hiện có trong file txt (vì người ta đã lưu x/y ngay trong file)
                if line.startswith("{") and line.endswith("}"):
                    try:
                        obj = json.loads(line)
                        room = str(obj.get("room", "") or obj.get("location", "")).strip()
                        aps = obj.get("aps", {})
                        if not room or not aps:
                            continue

                        rssi_map = {normalize_bssid(bssid): float(rssi)
                                    for bssid, rssi in aps.items()
                                    if normalize_bssid(bssid) and rssi is not None}

                        x_val = obj.get("x")
                        y_val = obj.get("y")
                        floor_val = obj.get("floor")

                        dataset.append({
                            "location": room,
                            "rssi_map": rssi_map,
                            "x": float(x_val) if x_val is not None else None,
                            "y": float(y_val) if y_val is not None else None,
                            "floor": int(floor_val) if floor_val is not None else None,
                        })
                        continue
                    except (json.JSONDecodeError, ValueError, TypeError):
                        pass

                location, rssi_map = parse_packet(line)
                if location and rssi_map:
                    dataset.append({
                        "location": location,
                        "rssi_map": rssi_map,
                        "x": None,
                        "y": None,
                        "floor": None
                    })
    except Exception as e:
        print(f"[ERROR] Không thể mở dataset_train.txt tại '{filepath}': {e}")
    return dataset


def load_dataset_v2(filepath: str) -> list[dict]:
    """Load dataset format v2 (JSONL) có hỗ trợ tọa độ X/Y.
    
    Mỗi dòng là một JSON object:
    {
        "room": "PHONG_HOC_I303",
        "x": 2.5,         # meter, null nếu chưa có
        "y": 1.8,         # meter, null nếu chưa có
        "floor": 3,       # tầng, null nếu chưa có
        "aps": {
            "fc:7c:02:9f:d0:0b": -50.62,
            ...
        }
    }
    
    Mỗi phần tử trả về có dạng tương thích với load_dataset():
    {
        "location": "PHONG_HOC_I303",
        "rssi_map": {"bssid_lower": rssi_float, ...},
        "x": 2.5,
        "y": 1.8,
        "floor": 3
    }
    """
    dataset = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    obj = json.loads(line)
                    room = str(obj.get("room", "") or obj.get("location", "")).strip()
                    aps = obj.get("aps", {})
                    if not room or not aps:
                        continue

                    # Normalize BSSID keys to lowercase and standard MAC format
                    rssi_map = {normalize_bssid(bssid): float(rssi)
                                for bssid, rssi in aps.items()
                                if normalize_bssid(bssid) and rssi is not None}

                    x_val = obj.get("x")
                    y_val = obj.get("y")
                    floor_val = obj.get("floor")

                    dataset.append({
                        "location": room,
                        "rssi_map": rssi_map,
                        "x": float(x_val) if x_val is not None else None,
                        "y": float(y_val) if y_val is not None else None,
                        "floor": int(floor_val) if floor_val is not None else None
                    })
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    print(f"[WARN] Dòng {line_num} trong '{filepath}' không hợp lệ: {e}")
                    continue
    except Exception as e:
        print(f"[ERROR] Không thể mở dataset v2 tại '{filepath}': {e}")
    return dataset


def load_dataset_auto(filepath: str) -> list[dict]:
    """Tự động phát hiện format dataset và load phù hợp.
    
    - Nếu filepath kết thúc bằng .jsonl → dùng load_dataset_v2()
    - Nếu kết thúc bằng .txt → dùng load_dataset()
    - Nếu không có extension → thử txt trước, rồi jsonl
    
    Ưu tiên dataset v2 (JSONL) nếu tồn tại song song với txt.
    """
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".jsonl":
        print(f"[INFO] Phát hiện dataset format v2 (JSONL): '{filepath}'")
        return load_dataset_v2(filepath)

    if ext == ".txt":
        # TXT hiện tại ở project có thể chứa JSON object mỗi dòng với x/y, nên ưu tiên load_dataset()
        txt_data = load_dataset(filepath)
        if txt_data:
            return txt_data

        base = os.path.splitext(filepath)[0]
        v2_path = base + ".jsonl"
        if os.path.exists(v2_path):
            print(f"[INFO] Phát hiện dataset JSONL song song: '{v2_path}'. Fallback sang JSONL...")
            v2_data = load_dataset_v2(v2_path)
            if v2_data:
                return v2_data
        return []

    # Không xác định extension → thử cả hai
    if os.path.exists(filepath):
        # Thử parse như JSONL trước
        try:
            result = load_dataset_v2(filepath)
            if result:
                return result
        except Exception:
            pass
        # Fallback về txt format
        return load_dataset(filepath)

    return []


def euclidean_distance(current_rssi: dict[str, float], train_point: dict, default_penalty: float = -100.0) -> float:
    """Tính khoảng cách Euclidean RSSI giữa tín hiệu quét được và mẫu train."""
    dist_sq = 0.0
    for bssid, current_val in current_rssi.items():
        train_val = train_point["rssi_map"].get(bssid, default_penalty)
        diff = current_val - train_val
        dist_sq += diff * diff
    return math.sqrt(dist_sq)


def interpolate_coordinates(
    k_neighbors: list[dict],
    sigma: float = 15.0
) -> tuple[float | None, float | None]:
    """Nội suy tọa độ X/Y từ k fingerprint gần nhất có tọa độ.

    Công thức:
        w_i = exp(-(d_i^2) / (sigma^2))
        x_pred = Σ(w_i * x_i) / Σ(w_i)
        y_pred = Σ(w_i * y_i) / Σ(w_i)

    Args:
        k_neighbors: List các neighbor từ predict_wknn(), mỗi item là dict với keys:
                     "distance", "location", "x" (optional), "y" (optional)
        sigma: Tham số điều chỉnh độ suy giảm trọng số (phải khớp với sigma dùng trong WKNN)

    Returns:
        (x_pred, y_pred) theo đơn vị meter.
        Nếu không có neighbor nào có tọa độ X/Y hợp lệ → trả về (None, None).
    """
    weighted_sum_x = 0.0
    weighted_sum_y = 0.0
    total_weight = 0.0

    for item in k_neighbors:
        x = item.get("x")
        y = item.get("y")

        # Chỉ dùng fingerprint có đủ cả x và y
        if x is None or y is None:
            continue

        d = item["distance"]
        w = math.exp(-(d ** 2) / (sigma ** 2))

        weighted_sum_x += w * x
        weighted_sum_y += w * y
        total_weight += w

    if total_weight <= 0:
        return None, None

    x_pred = weighted_sum_x / total_weight
    y_pred = weighted_sum_y / total_weight
    return round(x_pred, 4), round(y_pred, 4)


def predict_wknn(current_rssi: dict[str, float],
                 dataset: list[dict],
                 k: int = 5,
                 sigma: float = 15.0) -> tuple[str, float, list[dict], float | None, float | None]:
    """
    Thuật toán Weighted K-Nearest Neighbors (WKNN).

    Trọng số: w_i = exp(-(d_i^2) / (sigma^2))
    Cộng dồn trọng số theo từng phòng.
    Độ tin cậy: confidence = (W_phong_cao_nhat / Tổng_W_K_mau) * 100%

    Bổ sung: Nội suy tọa độ X/Y từ các fingerprint gần nhất có X/Y.

    Args:
        current_rssi: Dict BSSID → RSSI hiện tại (đã qua EMA)
        dataset: Dataset fingerprint đã load (từ load_dataset/load_dataset_v2)
        k: Số hàng xóm gần nhất
        sigma: Tham số sigma cho hàm trọng số Gaussian

    Returns:
        (predicted_room, confidence_percentage, top_k_neighbors, x_pred, y_pred)
        - x_pred, y_pred: tọa độ theo meter (None nếu fingerprint không có tọa độ)
    """
    if not dataset or not current_rssi:
        return "Chưa xác định", 0.0, [], None, None

    distances = []
    for point in dataset:
        d = euclidean_distance(current_rssi, point)
        distances.append({
            "distance": d,
            "location": point["location"],
            "x": point.get("x"),      # None nếu dataset cũ không có tọa độ
            "y": point.get("y"),      # None nếu dataset cũ không có tọa độ
            "floor": point.get("floor")
        })

    # Sắp xếp khoảng cách tăng dần
    distances.sort(key=lambda x: x["distance"])
    k_neighbors = distances[:min(k, len(distances))]

    # Tính trọng số w_i và cộng dồn theo phòng (Room Prediction)
    room_weights = defaultdict(float)
    total_weight = 0.0

    for item in k_neighbors:
        w = math.exp(- (item["distance"] ** 2) / (sigma ** 2))
        room_weights[item["location"]] += w
        total_weight += w

    if total_weight <= 0:
        return "Chưa xác định", 0.0, k_neighbors, None, None

    # Tìm phòng có tổng trọng số W cao nhất
    best_room = max(room_weights.items(), key=lambda x: x[1])[0]
    confidence = (room_weights[best_room] / total_weight) * 100.0

    # Coordinate Interpolation (dùng cùng k_neighbors và sigma)
    x_pred, y_pred = interpolate_coordinates(k_neighbors, sigma=sigma)

    return best_room, round(confidence, 1), k_neighbors, x_pred, y_pred


def print_prediction(predicted_room: str, confidence: float,
                     neighbors: list[dict] | None = None,
                     x_pred: float | None = None,
                     y_pred: float | None = None) -> None:
    """In ra terminal kết quả dự đoán theo dạng dễ đọc.

    Args:
        predicted_room: tên phòng dự đoán
        confidence: phần trăm độ tin cậy (đã được làm tròn)
        neighbors: (tuỳ chọn) danh sách các hàng xóm K
        x_pred: tọa độ X dự đoán (meter), None nếu chưa có
        y_pred: tọa độ Y dự đoán (meter), None nếu chưa có
    """
    try:
        nb_count = len(neighbors) if neighbors else 0
        print(f"[PREDICTION] Room: {predicted_room} | Confidence: {confidence:5.1f}% | Neighbors: {nb_count}")
        if x_pred is not None and y_pred is not None:
            print(f"[POSITION]   X: {x_pred:.4f} m | Y: {y_pred:.4f} m")
        else:
            print(f"[POSITION]   Không có tọa độ (fingerprint chưa có X/Y)")
        if neighbors:
            for n in neighbors:
                loc = n.get("location", "?")
                dist = n.get("distance", float("nan"))
                x = n.get("x")
                y = n.get("y")
                coord_str = f"  x={x:.2f} y={y:.2f}" if x is not None and y is not None else "  no coord"
                print(f"  - {loc:25s}  dist={dist:.3f}{coord_str}")
    except Exception as e:
        print(f"[PREDICTION ERROR] Không thể in kết quả: {e}")
