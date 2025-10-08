from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PIL import Image
import json
import math

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
    if candidates is None:
        if isinstance(data, list):
            candidates = data
    if candidates is None:
        # 试着寻找顶层包含 list 的字段
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
        # 支持多种 bbox 表示
        bbox = None
        conf = None
        cls = item.get("class") or item.get("cls") or item.get("category") or item.get("name")
        # common keys
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
        # confidence
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
        
        print("All done. Crop results saved in:", out_dir_p)

    return saved

def crop_from_detector_result(result_json_path: str, images_dir: Optional[str] = None,
                              out_dir: Optional[str] = None, padding: float = 0.1, min_area: int = 16) -> List[str]:
    """
    给定 detector 的 result.json，优先在 images_dir 查找原图（同名），找不到时用 results 中的 <stem>_pred.*。
    """
    json_p = Path(result_json_path)
    if not json_p.exists():
        raise FileNotFoundError(f"result json not found: {json_p}")

    stem = json_p.stem
    # 在 images_dir 查找原图
    img_candidates = []
    if images_dir:
        images_dir_p = Path(images_dir)
        if images_dir_p.exists():
            for ext in (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"):
                p = images_dir_p / f"{stem}{ext}"
                if p.exists():
                    img_candidates.append(p)
    # 尝试 results 目录的标注图 <stem>_pred.*
    results_dir = json_p.parent
    for ext in (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"):
        p = results_dir / f"{stem}_pred{ext}"
        if p.exists():
            img_candidates.append(p)
    if not img_candidates:
        raise FileNotFoundError(f"cannot find source image for {json_p}; tried images_dir and results_dir")

    # 取第一个可用
    src_img = img_candidates[0]
    return crop_from_paths(str(src_img), str(json_p), out_dir=out_dir, padding=padding, min_area=min_area)