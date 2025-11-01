import os
# 在任何可能导入 torch/ultralytics 之前设置，避免 OpenMP 初始化错误（临时）
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import sys
from pathlib import Path
from PIL import Image
from tqdm import tqdm

def main():
    project_root = Path(__file__).resolve().parents[2] 
    model_path = project_root / "backend" / "static" / "models" / "plate" / "yolo11m.pt"
    src_images_dir = project_root / "data" / "Plate" / "training" / "images"
    dst_base_dir = project_root / "data" / "Number" / "training" / "images"

    if not model_path.exists():
        print(f"模型文件不存在: {model_path}")
        sys.exit(1)
    if not src_images_dir.exists():
        print(f"来源图片目录不存在: {src_images_dir}")
        sys.exit(1)

    try:
        from ultralytics import YOLO
    except Exception as e:
        print("需要安装 ultralytics: pip install ultralytics Pillow")
        raise

    # 加载模型
    model = YOLO(str(model_path))

    exts = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    image_paths = [p for p in src_images_dir.rglob("*") if p.suffix.lower() in exts]

    if not image_paths:
        print("未找到任何图片。")
        return

    total_crops = 0
    for img_path in tqdm(image_paths, desc="Processing images"):
        rel = img_path.relative_to(src_images_dir)
        out_dir = dst_base_dir / rel.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        img = Image.open(img_path).convert("RGB")
        w, h = img.size

        # 运行检测（可按需调整 imgsz/conf）
        results = model(str(img_path), imgsz=1280, conf=0.25, verbose=False)

        # results 可能为列表，取第一个结果
        if not results:
            continue
        res = results[0]
        boxes = getattr(res, "boxes", None)
        if boxes is None or len(boxes) == 0:
            continue

        # boxes.xyxy -> tensor of [N,4]
        xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes, "xyxy") else []
        for i, box in enumerate(xyxy, start=1):
            xmin, ymin, xmax, ymax = box[:4]
            # clamp
            xmin = max(0, int(round(xmin)))
            ymin = max(0, int(round(ymin)))
            xmax = min(w, int(round(xmax)))
            ymax = min(h, int(round(ymax)))
            if xmax <= xmin or ymax <= ymin:
                continue

            crop = img.crop((xmin, ymin, xmax, ymax))
            out_name = f"{img_path.stem}__crop{i}{img_path.suffix.lower()}"
            out_path = out_dir / out_name
            crop.save(out_path)
            total_crops += 1

    print(f"处理完成，生成裁剪图片数量: {total_crops}")

if __name__ == "__main__":
    main()