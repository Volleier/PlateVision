from ultralytics import YOLO
import sys
from pathlib import Path

img = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("E:/Project/PlateVision/data/Number/test_images/plate.jpg")
weights = Path("E:/Project/PlateVision/data/Number/models/best.pt")
out_project = Path("E:/Project/PlateVision/runs/detect")
out_name = "best_plate"

if not img.exists():
    print("image not found:", img); raise SystemExit(1)
if not weights.exists():
    print("weights not found:", weights); raise SystemExit(1)

# 加载模型
model = YOLO(str(weights))

# 预测并保存带标注图片到 runs/detect/best_plate
results = model.predict(source=str(img), device=0, conf=0.25, save=True, project=str(out_project), name=out_name)

# 以下为替换/新增的输出逻辑：按框中心 x 排序并拼接类别名/索引，打印置信度
def load_names():
    # 优先尝试 dataset.yaml 中 names，其次 training/classes.txt，其次返回数字索引
    ds_yaml = Path("E:/Project/PlateVision/data/Number/training/dataset.yaml")
    if ds_yaml.exists():
        try:
            import re
            txt = ds_yaml.read_text(encoding="utf-8")
            m = re.search(r'^\s*names:\s*(\[[^\]]*\])', txt, re.MULTILINE)
            if m:
                names_list = eval(m.group(1))
                return [str(x) for x in names_list]
        except Exception:
            pass
    classes_txt = Path("E:/Project/PlateVision/data/Number/training/classes.txt")
    if classes_txt.exists():
        try:
            lines = [l.strip() for l in classes_txt.read_text(encoding="utf-8").splitlines() if l.strip()]
            return lines
        except Exception:
            pass
    return None

names = load_names()

all_seq = []
for i, r in enumerate(results):
    boxes = getattr(r, "boxes", None)
    if boxes is None or len(boxes) == 0:
        print(f"result {i}: no detections")
        continue
    dets = []
    # boxes 数据结构兼容不同版本：尝试按通用接口读取
    for b in boxes:
        try:
            xyxy = b.xyxy.cpu().numpy().tolist() if hasattr(b, "xyxy") else None
        except:
            try:
                xyxy = list(getattr(b, "xyxy", []))
            except:
                xyxy = None
        try:
            conf = float(getattr(b, "conf", 0.0))
        except:
            conf = 0.0
        try:
            cls = int(getattr(b, "cls", 0))
        except:
            # 有时类别存在 b.class 或 b.label，兼容读取
            try:
                cls = int(getattr(b, "class", 0))
            except:
                cls = 0
        if xyxy and len(xyxy) >= 4:
            x1, y1, x2, y2 = xyxy[:4]
            cx = (x1 + x2) / 2.0
        else:
            cx = 0.0
        label = str(cls) if names is None or cls >= len(names) else names[cls]
        dets.append((cx, label, conf, cls, xyxy))
    # 按中心 x 排序，拼接字符（从左到右）
    dets_sorted = sorted(dets, key=lambda x: x[0])
    seq = "".join([d[1] for d in dets_sorted])
    confs = [f"{d[2]:.3f}" for d in dets_sorted]
    print(f"Image {i}: recognized sequence: {seq}")
    print(f"  classes (idx): {[d[3] for d in dets_sorted]}")
    print(f"  confidences: {confs}")
    all_seq.append(seq)

print("annotated results saved to:", out_project / out_name)