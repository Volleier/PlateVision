import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PIL import Image
import math

def _clamp(v, a, b):
    return max(a, min(b, v))

def _bbox_to_xyxy(bbox: List[float], img_w: int, img_h: int) -> Tuple[int,int,int,int]:
    """
    更稳健地把 bbox 转为像素坐标 (x1,y1,x2,y2)。
    支持：
    - [xmin, ymin, xmax, ymax]（绝对或归一化）
    - [cx, cy, w, h]（中心宽高，绝对或归一化）
    规则：
    - 先尝试把值转为 float
    - 判断是否为归一化（所有值在 [0,1] 范围内）
    - 如果第三项大于第一项且第四项大于第二项，优先视为 xmin/ymin/xmax/ymax
    - 否则视为 cx,cy,w,h
    """
    if len(bbox) != 4:
        raise ValueError("bbox length must be 4")

    # 安全转换
    try:
        vals = [float(x) for x in bbox]
    except Exception:
        raise ValueError("bbox values must be numeric")

    a, b, c, d = vals

    # 判断是否为归一化坐标：所有值都在 [0,1]
    is_all_in_01 = all(0.0 <= v <= 1.0 for v in vals)

    # 如果看起来像 xmin,ymin,xmax,ymax（第三项>第一项且第四项>第二项），优先按此处理
    if (c > a) and (d > b):
        if is_all_in_01:
            x1 = int(round(a * img_w))
            y1 = int(round(b * img_h))
            x2 = int(round(c * img_w))
            y2 = int(round(d * img_h))
        else:
            x1, y1, x2, y2 = int(round(a)), int(round(b)), int(round(c)), int(round(d))
    else:
        # 按中心格式 cx,cy,w,h
        if is_all_in_01:
            cx = a * img_w
            cy = b * img_h
            w = c * img_w
            h = d * img_h
        else:
            cx, cy, w, h = a, b, c, d
        x1 = int(round(cx - w / 2.0))
        y1 = int(round(cy - h / 2.0))
        x2 = int(round(cx + w / 2.0))
        y2 = int(round(cy + h / 2.0))

    # clamp 到图片范围
    x1 = _clamp(x1, 0, img_w - 1)
    y1 = _clamp(y1, 0, img_h - 1)
    x2 = _clamp(x2, 0, img_w - 1)
    y2 = _clamp(y2, 0, img_h - 1)

    # 确保 x2>x1, y2>y1
    if x2 <= x1:
        x2 = min(x1 + 1, img_w - 1)
    if y2 <= y1:
        y2 = min(y1 + 1, img_h - 1)

    return x1, y1, x2, y2

def _extract_detections_from_json(data: Dict) -> List[Dict]:
    """
    根据常见输出格式提取 detections 列表
    每项返回标准字典：{'bbox': [..], 'class': str|int|None, 'conf': float|None}
    支持的可能 key： 'predictions','detections','objects','boxes' 或直接是 list
    每个 item 可能是 dict 包含 'bbox' 或 'box' 或 'x','y','w','h' 等
    """
    candidates = None
    for key in ("predictions", "detections", "objects", "boxes", "results"):
        if key in data and isinstance(data[key], list):
            candidates = data[key]
            break
    if candidates is None:
        # 有些 detector 直接把 list 写在根
        if isinstance(data, list):
            candidates = data
        else:
            # 尝试常见子键
            for v in data.values():
                if isinstance(v, list):
                    candidates = v
                    break
    if not candidates:
        return []

    out = []
    for item in candidates:
        if isinstance(item, (list, tuple)) and len(item) >= 4:
            bbox = list(item[:4])
            cls = None
            conf = None
        elif isinstance(item, dict):
            # 尝试多种 key 名
            if "bbox" in item:
                bbox = item["bbox"]
            elif "box" in item:
                bbox = item["box"]
            elif all(k in item for k in ("x","y","w","h")):
                bbox = [item["x"], item["y"], item["w"], item["h"]]
            elif all(k in item for k in ("xmin","ymin","xmax","ymax")):
                bbox = [item["xmin"], item["ymin"], item["xmax"], item["ymax"]]
            else:
                # 无法解析，跳过
                continue
            cls = item.get("class") or item.get("label") or item.get("name")
            conf = item.get("confidence") or item.get("conf") or item.get("score")
        else:
            continue

        try:
            bbox_list = [float(x) for x in bbox]
        except Exception:
            continue
        out.append({"bbox": bbox_list, "class": cls, "conf": float(conf) if conf is not None else None})
    return out

def crop_from_paths(image_path: str, result_json_path: str, out_dir: Optional[str] = None,
                    padding: float = 0.1, min_area: int = 16) -> List[str]:
    """
    从指定原图与 JSON 文件切割出每个目标并保存。
    padding: 相对于 bbox 宽高的扩展比例（例如 0.1 -> 在四周各扩 10%）
    min_area: 忽略面积小于该值的 bbox（像素数量）
    返回已保存文件路径列表。
    """
    img_p = Path(image_path)
    json_p = Path(result_json_path)

    if not img_p.exists():
        raise FileNotFoundError(f"image not found: {img_p}")
    if not json_p.exists():
        raise FileNotFoundError(f"result json not found: {json_p}")

    out_dir_p = Path(out_dir) if out_dir else json_p.parent / "crops"
    out_dir_p.mkdir(parents=True, exist_ok=True)

    img = Image.open(img_p).convert("RGB")
    w, h = img.size

    with json_p.open("r", encoding="utf-8") as f:
        data = json.load(f)

    detections = _extract_detections_from_json(data)
    saved = []
    for i, det in enumerate(detections):
        try:
            x1, y1, x2, y2 = _bbox_to_xyxy(det["bbox"], w, h)
        except Exception:
            continue

        # apply padding
        bw = x2 - x1
        bh = y2 - y1
        pad_x = int(bw * padding)
        pad_y = int(bh * padding)
        x1p = _clamp(x1 - pad_x, 0, w - 1)
        y1p = _clamp(y1 - pad_y, 0, h - 1)
        x2p = _clamp(x2 + pad_x, 0, w - 1)
        y2p = _clamp(y2 + pad_y, 0, h - 1)

        area = (x2p - x1p) * (y2p - y1p)
        if area < min_area:
            continue

        crop = img.crop((x1p, y1p, x2p, y2p))
        cls = str(det.get("class")) if det.get("class") is not None else "obj"
        conf = f"{det.get('conf'):.2f}" if det.get("conf") is not None else "nan"
        out_name = f"{img_p.stem}_crop{i}_{cls}_{conf}{img_p.suffix}"
        out_path = out_dir_p / out_name
        crop.save(out_path)
        saved.append(str(out_path))
    return saved

def crop_from_detector_result(result_json_path: str, images_dir: Optional[str] = None,
                              out_dir: Optional[str] = None, padding: float = 0.1, min_area: int = 16) -> List[str]:
    """
    给定 detector 的 result.json，尝试在 images_dir（通常是 backend/static/uploads）中寻找原图并切割。
    如果找不到原图，会尝试使用同名带 _pred 的标注图（results 中的预测图）作为来源。
    """
    json_p = Path(result_json_path)
    if not json_p.exists():
        raise FileNotFoundError(result_json_path)

    # 常见规则： json 名称为 <stem>.json，原图可能在 uploads/<stem>.* 或 results/<stem>_pred.*
    stem = json_p.stem
    img_candidates = []

    if images_dir:
        images_dir_p = Path(images_dir)
        if images_dir_p.exists():
            img_candidates.extend(sorted(images_dir_p.glob(f"{stem}.*")))

    # 尝试 results 目录中的标注图（同级或上级 results 文件夹）
    results_dir = json_p.parent
    img_candidates.extend(sorted(results_dir.glob(f"{stem}_pred.*")))

    if not img_candidates:
        raise FileNotFoundError("cannot locate source image for result: " + str(json_p))

    # 选择第一个存在的图片
    src_img = img_candidates[0]
    return crop_from_paths(str(src_img), str(json_p), out_dir=out_dir, padding=padding, min_area=min_area)