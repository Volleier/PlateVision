from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from PIL import Image
import json
import math
import logging

from backend.config import cfg

_logger = logging.getLogger("App")

def _clamp(v, a, b):
    return max(a, min(b, v))

def _bbox_to_xyxy(bbox: List[float], img_w: int, img_h: int) -> Tuple[int,int,int,int]:
    """
    把 bbox 转为像素坐标 (x1,y1,x2,y2)。
    支持：
      - [xmin, ymin, xmax, ymax]（绝对或归一化）
      - [cx, cy, w, h]（中心宽高，绝对或归一化）
    """
    if len(bbox) != 4:
        raise ValueError("bbox must have 4 elements")

    # 尝试转为 float
    vals = []
    for v in bbox:
        try:
            vals.append(float(v))
        except Exception:
            vals.append(0.0)
    a, b, c, d = vals

    is_norm = all(0.0 <= v <= 1.0 for v in vals)

    # 如果第三项>第一项且第四项>第二项，按 xmin,ymin,xmax,ymax
    if (c > a) and (d > b):
        if is_norm:
            x1 = a * img_w
            y1 = b * img_h
            x2 = c * img_w
            y2 = d * img_h
        else:
            x1, y1, x2, y2 = a, b, c, d
    else:
        # 按 cx,cy,w,h
        if is_norm:
            cx = a * img_w
            cy = b * img_h
            w = c * img_w
            h = d * img_h
        else:
            cx, cy, w, h = a, b, c, d
        x1 = cx - w / 2.0
        y1 = cy - h / 2.0
        x2 = cx + w / 2.0
        y2 = cy + h / 2.0

    # clamp
    x1 = int(_clamp(math.floor(x1), 0, img_w - 1))
    y1 = int(_clamp(math.floor(y1), 0, img_h - 1))
    x2 = int(_clamp(math.ceil(x2), 0, img_w - 1))
    y2 = int(_clamp(math.ceil(y2), 0, img_h - 1))

    if x2 <= x1:
        x2 = min(img_w - 1, x1 + 1)
    if y2 <= y1:
        y2 = min(img_h - 1, y1 + 1)

    return x1, y1, x2, y2

def _extract_detections_from_json(data: Dict) -> List[Dict]:
    """
    返回列表，每项 dict 包含至少: {'bbox': [..], 'conf': float|None, 'class': int|str|None}
    支持常见结构：{"detections":[{xmin,ymin,xmax,ymax,...}], "predictions":..., 直接 list 等}
    """
    candidates = None
    for key in ("predictions", "detections", "objects", "boxes", "results"):
        if key in data and isinstance(data[key], list):
            candidates = data[key]
            break
    if candidates is None and isinstance(data, list):
        candidates = data
    if candidates is None:
        for v in data.values() if isinstance(data, dict) else []:
            if isinstance(v, list):
                candidates = v
                break
    if not candidates:
        return []
    out = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        bbox = None
        conf = None
        cls = item.get("class") or item.get("cls") or item.get("category") or item.get("name")
        if "bbox" in item:
            bbox = item["bbox"]
        elif "box" in item:
            bbox = item["box"]
        elif all(k in item for k in ("xmin","ymin","xmax","ymax")):
            bbox = [item["xmin"], item["ymin"], item["xmax"], item["ymax"]]
        elif all(k in item for k in ("x","y","w","h")):
            bbox = [item["x"], item["y"], item["x"] + item["w"], item["y"] + item["h"]]
        elif all(k in item for k in ("cx","cy","w","h")):
            bbox = [item["cx"], item["cy"], item["w"], item["h"]]
        for key in ("confidence","conf","score"):
            if key in item:
                try:
                    conf = float(item[key])
                except Exception:
                    conf = None
                break
        if bbox is None:
            continue
        out.append({"bbox": bbox, "conf": conf, "class": cls})
    return out

def crop_from_paths(image_path: str, result_json_path: str, out_dir: Optional[str] = None,
                    padding: float = 0.1, min_area: int = 16) -> List[str]:
    """
    对指定原图与 JSON 切割并保存。
    """
    img_p = Path(image_path)
    json_p = Path(result_json_path)

    if not img_p.exists():
        raise FileNotFoundError(f"image not found: {img_p}")
    if not json_p.exists():
        raise FileNotFoundError(f"json not found: {json_p}")

    out_dir_p = Path(out_dir) if out_dir else json_p.parent / "crops"
    out_dir_p.mkdir(parents=True, exist_ok=True)

    img = Image.open(img_p).convert("RGB")
    w, h = img.size

    try:
        with json_p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise RuntimeError(f"failed to read json: {e}")

    detections = _extract_detections_from_json(data)
    saved = []
    for i, det in enumerate(detections):
        bbox = det["bbox"]
        conf = det.get("conf")
        x1,y1,x2,y2 = _bbox_to_xyxy(bbox, w, h)
        bw = x2 - x1
        bh = y2 - y1
        if bw * bh < min_area:
            continue
        # padding
        pad_w = int(bw * padding)
        pad_h = int(bh * padding)
        x1p = _clamp(x1 - pad_w, 0, w - 1)
        y1p = _clamp(y1 - pad_h, 0, h - 1)
        x2p = _clamp(x2 + pad_w, 0, w - 1)
        y2p = _clamp(y2 + pad_h, 0, h - 1)
        crop_img = img.crop((x1p, y1p, x2p, y2p))
        conf_s = f"{conf:.2f}" if conf is not None else "na"
        out_name = f"{json_p.stem}_crop_{i}_{conf_s}.jpg"
        out_path = out_dir_p / out_name
        crop_img.save(out_path, quality=95)
        saved.append(str(out_path))
        
        # 使用 logger 替代 print
        _logger.debug("Saved crop %s for detection %d (conf=%s)", out_path, i, conf_s)

    _logger.info("crop_from_paths: saved %d crops to %s for json=%s", len(saved), out_dir_p, json_p)
    return saved

def crop_from_detector_result(result_json_path: str, images_dir: Optional[str] = None,
                              out_dir: Optional[str] = None, padding: float = 0.1, min_area: int = 16) -> List[str]:
    """
    给定 detector 的 result.json，优先在 images_dir 查找原图（同名），找不到时用 results 中的 <stem>_pred.*。
    返回裁剪后保存的文件路径列表（字符串）。
    """
    json_p = Path(result_json_path)
    if not json_p.exists():
        raise FileNotFoundError(f"result json not found: {json_p}")

    stem = json_p.stem
    img_candidates: List[Path] = []

    # 优先在上传目录或指定 images_dir 查找同名原图
    if images_dir:
        images_dir_p = Path(images_dir)
        if images_dir_p.exists():
            for ext in (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"):
                p = images_dir_p / f"{stem}{ext}"
                if p.exists():
                    img_candidates.append(p)

    # 再在 detector 的 results 目录查找带 _pred 后缀的标注图
    results_dir = json_p.parent
    for ext in (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"):
        p = results_dir / f"{stem}_pred{ext}"
        if p.exists():
            img_candidates.append(p)

    if not img_candidates:
        raise FileNotFoundError(f"cannot find source image for {json_p}; tried images_dir and results_dir")

    src_img = img_candidates[0]
    _logger.debug("crop_from_detector_result: source image for %s -> %s", json_p, src_img)
    return crop_from_paths(str(src_img), str(json_p), out_dir=out_dir, padding=padding, min_area=min_area)

# 抽象层入口
def _default_results_dir() -> Path:
    """
    返回 extractor 的默认结果目录，优先使用 cfg.RESULTS_EXTRACTOR_DIR，否则 fallback 到 backend/static/results/extractor
    """
    try:
        base = Path(cfg.RESULTS_EXTRACTOR_DIR)
        return base
    except Exception:
        repo_root = Path(__file__).resolve().parents[2]
        return (repo_root / "backend" / "static" / "results" / "extractor")

def _find_detector_json_by_file_id(file_id: str) -> Optional[Path]:
    detector_dir = Path(cfg.RESULTS_DETECTOR_DIR)
    if not detector_dir.exists():
        _logger.warning("Detector results directory does not exist: %s", detector_dir)
        return None
    for p in detector_dir.iterdir():
        if p.is_file() and p.suffix.lower() == ".json" and file_id in p.stem:
            _logger.info("Found detector json for file_id=%s -> %s", file_id, p)
            return p
    _logger.warning("No detector json found for file_id=%s in %s", file_id, detector_dir)
    return None

# ---------- Abstraction layer API ----------
def extract_image(file_id: str, padding: float = 0.08, min_area: int = 16) -> Dict[str, Any]:
    """
    抽象层入口：给定 file_id，查找 detector 的 json 并执行裁剪。
    - 只接受 file_id（不会接收 out_dir），裁剪结果总是保存到默认 extractor 结果目录（由 cfg.RESULTS_EXTRACTOR_DIR 或 fallback 决定）
    - 返回结构：
      {"status":"ok","file_id":..,"out_dir":..,"crops":[..],"detector_json": "<path>"} 或错误信息
    逻辑说明：
    - 只依赖 detector 结果 json（不会触发 detector 运行）
    - 不接受外部 out_dir 参数
    """
    _logger.info("plate_extractor.extract_image called for file_id=%s", file_id)
    try:
        json_p = _find_detector_json_by_file_id(file_id)
        if json_p is None:
            _logger.warning("extract_image: detector json not found for file_id=%s", file_id)
            return {"status": "not_found", "error": "detector json not found", "file_id": file_id}

        # 使用默认的 extractor 结果目录
        target_dir = _default_results_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        _logger.info("extract_image: extracting crops for file_id=%s -> out_dir=%s", file_id, target_dir)

        images_dir = cfg.UPLOADS_DIR
        saved = crop_from_detector_result(str(json_p), images_dir=images_dir, out_dir=str(target_dir), padding=padding, min_area=min_area)

        # 写入索引 json（包含 detector json 路径与 crops 列表）
        index = {
            "file_id": file_id,
            "detector_json": str(json_p),
            "out_dir": str(target_dir),
            "crops": saved
        }
        index_path = target_dir / f"{file_id}_extract_index.json"
        try:
            with index_path.open("w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
            _logger.info("extract_image: wrote index %s", index_path)
        except Exception:
            _logger.exception("extract_image: failed to write index json for file_id=%s", file_id)

        _logger.info("extract_image: finished for file_id=%s saved=%d", file_id, len(saved))
        return {"status": "ok", "file_id": file_id, "out_dir": str(target_dir), "crops": saved, "detector_json": str(json_p)}
    except FileNotFoundError as e:
        _logger.exception("extract_image: file not found for file_id=%s", file_id)
        return {"status": "error", "error": str(e), "file_id": file_id}
    except Exception as e:
        _logger.exception("extract_image: unexpected error for file_id=%s", file_id)
        return {"status": "error", "error": str(e), "file_id": file_id}