import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from typing import Optional, List, Dict, Any
import logging

from backend.config import cfg

_logger = logging.getLogger("App")

try:
    from ultralytics import YOLO
except Exception as e:
    _logger.error("Please install ultralytics: pip install ultralytics. Error: %s", e)
    raise

def detect_all(conf: float = 0.25, imgsz: int = 640, results_dir: Optional[Path] = None, input_path: Optional[Path] = None):
    """
    执行 number 模型检测并在 results_dir 下保存 <stem>_pred.* 与 <stem>.json。
    默认 results_dir 使用 cfg.RESULTS_READER_DIR（reader 输出目录）。
    """
    try:
        repo_root = Path(__file__).resolve().parents[2]
        static_dir = repo_root / "backend" / "static"
        model_path = Path(cfg.NUMBER_MODEL) if getattr(cfg, "NUMBER_MODEL", None) else static_dir / "models" / "number_best.pt"
        crops_dir = Path(cfg.RESULTS_EXTRACTOR_DIR)

        # 改为 reader 结果目录默认
        results_dir = Path(results_dir) if results_dir else Path(cfg.RESULTS_READER_DIR)

        if not model_path.exists():
            _logger.error("Number model not found: %s", model_path)
            return

        results_dir.mkdir(parents=True, exist_ok=True)
        if input_path:
            input_path = Path(input_path)

        try:
            model = YOLO(str(model_path))
        except Exception:
            _logger.exception("Failed to load number model: %s", model_path)
            return

        exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
        if input_path:
            if not input_path.exists() or input_path.suffix.lower() not in exts:
                _logger.warning("input_path invalid for number detection: %s", input_path)
                return
            imgs = [input_path]
        else:
            if not crops_dir.exists():
                _logger.warning("Crops dir does not exist: %s", crops_dir)
                return
            imgs = sorted([p for p in crops_dir.iterdir() if p.suffix.lower() in exts and p.is_file()])
            if not imgs:
                _logger.warning("No crop images found in %s", crops_dir)
                return

        for img_path in imgs:
            try:
                res_list = model.predict(source=str(img_path), conf=conf, imgsz=imgsz, verbose=False)
                res = res_list[0] if isinstance(res_list, (list, tuple)) and len(res_list) > 0 else res_list

                detections = []
                try:
                    boxes = getattr(res, "boxes", None)
                    names = getattr(res, "names", None) or getattr(model, "names", {}) or {}
                    if boxes is not None and hasattr(boxes, "xyxy"):
                        xyxy = boxes.xyxy.cpu().numpy()
                        confs = getattr(boxes, "conf", None)
                        clss = getattr(boxes, "cls", None)
                        confs_arr = confs.cpu().numpy() if confs is not None else [0.0] * len(xyxy)
                        clss_arr = clss.cpu().numpy() if clss is not None else [0] * len(xyxy)
                        MIN_KEEP_CONF = 0.33
                        for i, b in enumerate(xyxy):
                            conf_val = float(confs_arr[i]) if i < len(confs_arr) else 0.0
                            if conf_val < MIN_KEEP_CONF:
                                continue
                            xmin, ymin, xmax, ymax = b.tolist()
                            cls_id = int(clss_arr[i]) if i < len(clss_arr) else 0
                            detections.append({
                                "xmin": float(xmin), "ymin": float(ymin),
                                "xmax": float(xmax), "ymax": float(ymax),
                                "confidence": conf_val,
                                "class": cls_id,
                                "name": str(names.get(cls_id, cls_id))
                            })
                except Exception:
                    _logger.exception("Failed to parse number detection boxes for %s", img_path)

                # 绘制检测结果并保存
                try:
                    pil_img = Image.open(img_path).convert("RGB")
                    draw = ImageDraw.Draw(pil_img)
                    try:
                        font = ImageFont.load_default()
                    except Exception:
                        font = None

                    for det in detections:
                        xmin, ymin, xmax, ymax = det["xmin"], det["ymin"], det["xmax"], det["ymax"]
                        conf_val = det.get("confidence", 0.0)
                        name = det.get("name", "")
                        draw.rectangle([xmin, ymin, xmax, ymax], outline="red", width=2)
                        text = f"{name} {conf_val:.2f}"
                        if font is not None:
                            try:
                                bbox = draw.textbbox((0, 0), text, font=font)
                                text_size = (bbox[2] - bbox[0], bbox[3] - bbox[1])
                            except Exception:
                                bbox = font.getbbox(text)
                                text_size = (bbox[2] - bbox[0], bbox[3] - bbox[1])
                        else:
                            text_size = (len(text) * 6, 10)
                        text_x0 = xmin
                        text_y0 = max(0, ymin - text_size[1] - 2)
                        text_bg = [text_x0, text_y0, text_x0 + text_size[0] + 4, text_y0 + text_size[1] + 2]
                        draw.rectangle(text_bg, fill="black")
                        draw.text((text_x0 + 2, text_y0 + 1), text, fill="white", font=font)

                    arr = np.asarray(pil_img)
                except Exception:
                    try:
                        plot_fn = getattr(res, "plot", None)
                        rendered = plot_fn() if callable(plot_fn) else None
                    except Exception:
                        rendered = None
                    if rendered is None:
                        arr = np.array(Image.open(img_path).convert("RGB"))
                    else:
                        arr = np.asarray(rendered)

                out_img_path = results_dir / f"{img_path.stem}_pred{img_path.suffix}"
                Image.fromarray(arr).save(out_img_path)

                out_json_path = results_dir / f"{img_path.stem}.json"
                with open(out_json_path, "w", encoding="utf-8") as f:
                    json.dump({"image": img_path.name, "detections": detections}, f, ensure_ascii=False, indent=2)

                _logger.info("Saved number reader outputs: %s %s", out_img_path, out_json_path)

            except Exception:
                _logger.exception("Number detect failed for %s", img_path)

        _logger.info("Number detection done. Results saved in: %s", results_dir)
    except Exception:
        _logger.exception("detect_all unexpected error")

def _default_results_dir() -> Path:
    try:
        base = Path(cfg.RESULTS_READER_DIR)
        return base
    except Exception:
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "backend" / "static" / "results" / "reader"

def _find_extractor_crops_by_file_id(file_id: str) -> List[Path]:
    """
    在 extractor 结果目录中查找与 file_id 关联的裁剪图列表（优先读取 index json，
    若无 index 则按文件名匹配）。
    返回 Path 列表（可以为空）。
    """
    extractor_dir = Path(getattr(cfg, "RESULTS_EXTRACTOR_DIR", "")) or (Path(__file__).resolve().parents[2] / "backend" / "static" / "results" / "extractor")
    if not extractor_dir.exists():
        _logger.warning("Extractor results directory does not exist: %s", extractor_dir)
        return []

    # 尝试 index 文件 first
    index_path = extractor_dir / f"{file_id}_extract_index.json"
    crops: List[Path] = []
    if index_path.exists():
        try:
            with index_path.open("r", encoding="utf-8") as f:
                idx = json.load(f)
            for p in idx.get("crops", []):
                pp = Path(p)
                if not pp.is_absolute():
                    pp = extractor_dir / p
                if pp.exists():
                    crops.append(pp)
            if crops:
                _logger.info("Found %d crops via index for file_id=%s", len(crops), file_id)
                return crops
        except Exception:
            _logger.exception("Failed to read extractor index %s", index_path)

    # 回退：按文件名包含 file_id 的图片文件
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    for p in extractor_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() in exts and file_id in p.stem:
            crops.append(p)
    if crops:
        _logger.info("Found %d crops by filename match for file_id=%s", len(crops), file_id)
        return sorted(crops)

    # 还可以尝试子目录查找（若 extractor 将每个 file_id 放入子目录）
    for sub in extractor_dir.iterdir():
        if not sub.is_dir():
            continue
        for p in sub.iterdir():
            if p.is_file() and p.suffix.lower() in exts and file_id in p.stem:
                crops.append(p)
    if crops:
        _logger.info("Found %d crops in subdirs for file_id=%s", len(crops), file_id)
        return sorted(crops)

    _logger.warning("No extractor crops found for file_id=%s in %s", file_id, extractor_dir)
    return []


# ---------- Abstraction layer API ----------
def read_image(file_id: str) -> Dict[str, Any]:
    """
    抽象层入口：只用 file_id。
    - 从 extractor 结果中找到裁剪图并对每张裁剪图运行 number detector（detect_all）。
    - 使用本地 cfg.DEFAULT_CONF / cfg.DEFAULT_IMGSZ 作为检测参数。
    - 结果统一保存在 reader 的默认目录下的子目录 <file_id>/
    - 返回结构：
      {"status":"ok","file_id":..,"out_dir":..,"images":[..],"jsons":[..]} 或错误信息
    """
    _logger.info("plate_reader.read_image called for file_id=%s", file_id)
    try:
        crops = _find_extractor_crops_by_file_id(file_id)
        if not crops:
            _logger.warning("plate_reader.read_image: no crops found for file_id=%s", file_id)
            return {"status": "not_found", "error": "no crops found in extractor results", "file_id": file_id}

        out_root = _default_results_dir()
        out_dir = out_root
        out_dir.mkdir(parents=True, exist_ok=True)
        _logger.info("plate_reader: processing %d crops for file_id=%s -> out_dir=%s", len(crops), file_id, out_dir)

        conf = getattr(cfg, "DEFAULT_CONF", 0.25)
        imgsz = getattr(cfg, "DEFAULT_IMGSZ", 640)

        # 对每个 crop 调用本模块的 detect_all，传入本地的 conf/imgsz
        for crop_path in crops:
            try:
                _logger.debug("plate_reader: running detect_all for crop=%s with conf=%s imgsz=%s", crop_path, conf, imgsz)
                detect_all(conf=conf, imgsz=imgsz, results_dir=out_dir, input_path=Path(crop_path))
            except Exception:
                _logger.exception("plate_reader: detect_all failed for crop=%s", crop_path)

        # 汇总输出文件列表
        exts_img = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
        images = sorted([
            str(p) for p in out_dir.iterdir() 
            if p.is_file() 
            and p.suffix.lower() in exts_img 
            and p.stem.endswith("_pred")
            and file_id in p.name  
        ])
        jsons = sorted([
            str(p) for p in out_dir.iterdir() 
            if p.is_file() 
            and p.suffix.lower() == ".json"
            and file_id in p.name 
        ])

        _logger.info("plate_reader: finished for file_id=%s images=%d jsons=%d", file_id, len(images), len(jsons))
        return {"status": "ok", "file_id": file_id, "out_dir": str(out_root), "images": images, "jsons": jsons}
    except Exception as e:
        _logger.exception("plate_reader.read_image: unexpected exception for file_id=%s", file_id)
        return {"status": "error", "error": str(e), "file_id": file_id}