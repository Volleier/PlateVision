import os
# Temporary workaround: set before importing libraries that may trigger OpenMP (not recommended long-term)
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from pathlib import Path
import json
from PIL import Image
import numpy as np
import sys
from typing import Optional

try:
    from ultralytics import YOLO
except Exception as e:
    print("Please install ultralytics: pip install ultralytics. Error:", e)
    raise

def detect_all(conf: float = 0.25, imgsz: int = 640, results_dir: Optional[Path] = None, input_path: Optional[Path] = None):
    repo_root = Path(__file__).resolve().parents[2]  # e:\Project\PlateVision
    static_dir = repo_root / "backend" / "static"
    model_path = static_dir / "models" / "plate_best.pt"
    uploads_dir = static_dir / "uploads"
    # 如果外部传入 results_dir，则使用之；否则回退到默认 yolo_detect
    results_dir = Path(results_dir) if results_dir else static_dir / "results" / "yolo_detect"

    if not model_path.exists():
        print("Model file not found:", model_path)
        return

    uploads_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    # Load local YOLOv11 model (ultralytics)
    try:
        model = YOLO(str(model_path))
    except Exception as e:
        print("Failed to load model:", e)
        raise

    exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
    if input_path:
        # 处理单张传入图片（无需复制到 uploads）
        if not Path(input_path).exists() or Path(input_path).suffix.lower() not in exts:
            print("Input image not found or unsupported:", input_path)
            return
        imgs = [Path(input_path)]
    else:
        imgs = sorted([p for p in uploads_dir.iterdir() if p.suffix.lower() in exts and p.is_file()])
        if not imgs:
            print("No images found in:", uploads_dir)
            return

    for img_path in imgs:
        try:
            print("Processing:", img_path.name)
            # Use the predict interface (recommended by ultralytics)
            res_list = model.predict(source=str(img_path), conf=conf, imgsz=imgsz, verbose=False)
            # Handle returned single Results or a list
            res = res_list[0] if isinstance(res_list, (list, tuple)) and len(res_list) > 0 else res_list

            # Try to render annotated image
            rendered = None
            try:
                plot_fn = getattr(res, "plot", None)
                if callable(plot_fn):
                    rendered = plot_fn()  # numpy array (RGB)
            except Exception:
                rendered = None

            # If no rendered image, load original as fallback
            if rendered is None:
                rendered = np.array(Image.open(img_path).convert("RGB"))

            # Extract boxes (safe)
            detections = []
            try:
                boxes = getattr(res, "boxes", None)
                # names may be on res or on model
                names = getattr(res, "names", None) or getattr(model, "names", {}) or {}
                if boxes is not None and hasattr(boxes, "xyxy"):
                    xyxy = boxes.xyxy.cpu().numpy()
                    confs = getattr(boxes, "conf", None)
                    clss = getattr(boxes, "cls", None)
                    confs_arr = confs.cpu().numpy() if confs is not None else [0.0] * len(xyxy)
                    clss_arr = clss.cpu().numpy() if clss is not None else [0] * len(xyxy)
                    for i, b in enumerate(xyxy):
                        xmin, ymin, xmax, ymax = b.tolist()
                        cls_id = int(clss_arr[i])
                        detections.append({
                            "xmin": float(xmin), "ymin": float(ymin),
                            "xmax": float(xmax), "ymax": float(ymax),
                            "confidence": float(confs_arr[i]),
                            "class": cls_id,
                            "name": str(names.get(cls_id, cls_id))
                        })
            except Exception:
                # Ignore parsing errors and continue with current detections (may be empty)
                pass

            # Save annotated image (ensure uint8 RGB)
            try:
                arr = np.asarray(rendered)
                if arr.ndim == 2:
                    arr = np.stack([arr] * 3, axis=-1)
                if arr.ndim == 3 and arr.shape[2] == 1:
                    arr = np.concatenate([arr] * 3, axis=2)
                if arr.dtype != np.uint8:
                    if np.issubdtype(arr.dtype, np.floating):
                        arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8) if arr.max() <= 1.0 else np.clip(arr, 0, 255).astype(np.uint8)
                    else:
                        arr = np.clip(arr, 0, 255).astype(np.uint8)
            except Exception:
                arr = np.array(Image.open(img_path).convert("RGB"))

            out_img_path = results_dir / f"{img_path.stem}_pred{img_path.suffix}"
            Image.fromarray(arr).save(out_img_path)

            out_json_path = results_dir / f"{img_path.stem}.json"
            with open(out_json_path, "w", encoding="utf-8") as f:
                json.dump({"image": img_path.name, "detections": detections}, f, ensure_ascii=False, indent=2)

            print("Saved:", out_img_path.name, out_json_path.name)

        except Exception as e:
            print(f"Error processing image {img_path.name}:", e)

    print("All done. Detector results saved in:", results_dir)