import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from pathlib import Path
from typing import Optional, Dict, Any, List
import json

import numpy as np
from PIL import Image

from backend.config import cfg

try:
    from ultralytics import YOLO
except Exception as e:
    raise RuntimeError("ultralytics required: pip install ultralytics") from e

_MODEL = None

def _get_model(model_path: Path):
    global _MODEL
    if _MODEL is None:
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        _MODEL = YOLO(str(model_path))
    return _MODEL

def _default_results_dir() -> Path:
    return Path(cfg.RESULTS_DETECTOR_DIR)

def _find_image_by_id(file_id: str, uploads_dir: Path, exts: Optional[set] = None) -> Optional[Path]:
    exts = exts or set(cfg.ALLOWED_EXTS)
    if not uploads_dir.exists():
        return None
    for p in uploads_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in exts:
            continue
        if file_id in p.name:
            return p
    return None

def _save_results(rendered_arr: np.ndarray, img_path: Path, results_dir: Path, detections: List[Dict[str, Any]]):
    results_dir.mkdir(parents=True, exist_ok=True)
    arr = np.asarray(rendered_arr)
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    if arr.ndim == 3 and arr.shape[2] == 1:
        arr = np.concatenate([arr] * 3, axis=2)
    if arr.dtype != np.uint8:
        if np.issubdtype(arr.dtype, np.floating):
            arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8) if arr.max() <= 1.0 else np.clip(arr, 0, 255).astype(np.uint8)
        else:
            arr = np.clip(arr, 0, 255).astype(np.uint8)

    out_img_path = results_dir / f"{img_path.stem}_pred{img_path.suffix}"
    Image.fromarray(arr).save(out_img_path)

    out_json_path = results_dir / f"{img_path.stem}.json"
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump({"image": img_path.name, "detections": detections}, f, ensure_ascii=False, indent=2)

    return out_img_path, out_json_path

def _run_detection_on_path(img_path: Path, model, conf: float, imgsz: int, results_dir: Path) -> Dict[str, Any]:
    try:
        results_dir.mkdir(parents=True, exist_ok=True)
        # Prevent ultralytics from writing its default runs/ folder; we save results ourselves.
        res_list = model.predict(source=str(img_path), conf=conf, imgsz=imgsz, verbose=False, save=False)
        res = res_list[0] if isinstance(res_list, (list, tuple)) and len(res_list) > 0 else res_list

        rendered = None
        try:
            plot_fn = getattr(res, "plot", None)
            if callable(plot_fn):
                rendered = plot_fn()
        except Exception:
            rendered = None

        if rendered is None:
            rendered = np.array(Image.open(img_path).convert("RGB"))

        detections: List[Dict[str, Any]] = []
        try:
            boxes = getattr(res, "boxes", None)
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
            pass

        if not isinstance(rendered, np.ndarray):
            rendered = np.array(rendered)
        out_img, out_json = _save_results(rendered, img_path, results_dir, detections)

        return {
            "status": "ok",
            "image": img_path.name,
            "out_image": str(out_img),
            "out_json": str(out_json),
            "detections": detections
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "image": img_path.name if 'img_path' in locals() else None}

def detect_image(file_id: str) -> Dict[str, Any]:
    """
    抽象入口：只需传入 file_id
    """
    conf = cfg.DEFAULT_CONF
    imgsz = cfg.DEFAULT_IMGSZ

    model_path = Path(cfg.PLATE_MODEL)
    uploads_dir = Path(cfg.UPLOADS_DIR)
    results_dir = _default_results_dir()

    img_path = _find_image_by_id(file_id, uploads_dir)
    if img_path is None:
        return {"status": "not_found", "error": f"no image with id {file_id} in {uploads_dir}"}

    try:
        model = _get_model(model_path)
    except Exception as e:
        return {"status": "error", "error": str(e)}

    result = _run_detection_on_path(img_path, model, conf, imgsz, results_dir)
    return result