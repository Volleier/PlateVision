import os
from typing import Any, Dict, Optional
from pathlib import Path
import shutil
import uuid
import time
import json

def processing_image(file_path: str, out_dir: Optional[str] = None, conf: float = 0.25, imgsz: int = 640) -> Dict[str, Any]:
    """
    主入口：负责文件复制 -> 调用 yolo_detector -> 调用 crop -> 导出标注图（如需）
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"file not found: {file_path}")

    repo_root = Path(__file__).resolve().parents[2]  # e:\Project\PlateVision
    static_dir = repo_root / "backend" / "static"
    uploads_dir = static_dir / "uploads"
    results_dir = static_dir / "results"

    uploads_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    src = Path(file_path)
    unique_name = f"{src.stem}_{int(time.time())}_{uuid.uuid4().hex[:8]}{src.suffix}"
    dst = uploads_dir / unique_name
    shutil.copy2(src, dst)

    # 调用 yolo_detector（它会调用 services.detector 并读取结果 json）
    detector_out = yolo_detector(str(dst), conf=conf, imgsz=imgsz)
    if detector_out.get("status") != "ok":
        return {"status": "error", "message": detector_out.get("message", "detector failed"), "source": str(file_path)}

    data = detector_out["detector_result"]
    data.setdefault("internal", {})
    data["internal"]["uploaded_name"] = unique_name
    data["internal"]["result_json"] = data["internal"].get("result_json")
    annotated_image = data["internal"].get("annotated_image")
    data["internal"]["annotated_image"] = annotated_image

    # 调用裁剪模块（如果存在），保存到 results/crops 并把路径写入 internal.crops
    try:
        from services import crop  # backend/services/crop.py
        crops_out_dir = results_dir / "crops"
        crops_out_dir.mkdir(parents=True, exist_ok=True)
        saved = crop_img(str(data["internal"]["result_json"]),
                                               images_dir=str(uploads_dir),
                                               out_dir=str(crops_out_dir),
                                               padding=0.08,
                                               min_area=64)
        data["internal"]["crops"] = saved
    except Exception as e:
        data["internal"]["crops_error"] = str(e)

    # 如果请求导出标注图到外部 out_dir，则复制一份
    if out_dir and annotated_image:
        annotated_image_path = Path(annotated_image)
        if annotated_image_path.exists():
            out_dir_p = Path(out_dir)
            out_dir_p.mkdir(parents=True, exist_ok=True)
            exported = out_dir_p / annotated_image_path.name
            shutil.copy2(annotated_image_path, exported)
            data["internal"]["exported_image"] = str(exported)

    return {"status": "ok", "source": str(file_path), "detector_result": data}


def yolo_detector(uploaded_path: str, conf: float = 0.25, imgsz: int = 640) -> Dict[str, Any]:
    """
    仅负责调用 detector 并读取 detector 产生的 JSON/标注图。
    参数 uploaded_path: 已复制到 backend/static/uploads 的文件完整路径（包含唯一名）。
    返回 detector 生成的 JSON 内容（dict），并在 internal 中写入 result_json / annotated_image / uploaded_name。
    若 detector 未生成结果，返回 {"status":"error", "message":...}
    """
    if not os.path.exists(uploaded_path):
        return {"status": "error", "message": f"uploaded file not found: {uploaded_path}"}

    # 延迟导入 detector
    from services import detector  # backend/services/detector.py

    repo_root = Path(__file__).resolve().parents[2]  # e:\Project\PlateVision
    static_dir = repo_root / "backend" / "static"
    uploads_dir = static_dir / "uploads"
    results_dir = static_dir / "results"

    # 调用 detector（批处理模式，遍历 uploads 并在 results 生成文件）
    detector.detect_all(conf=conf, imgsz=imgsz)

    up = Path(uploaded_path)
    result_json_path = results_dir / f"{up.stem}.json"
    annotated_image_path = results_dir / f"{up.stem}_pred{up.suffix}"

    if not result_json_path.exists():
        return {"status": "error", "message": "detector did not produce result", "uploaded": str(up)}

    with open(result_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data.setdefault("internal", {})
    data["internal"]["uploaded_name"] = up.name
    data["internal"]["result_json"] = str(result_json_path)
    data["internal"]["annotated_image"] = str(annotated_image_path) if annotated_image_path.exists() else None

    return {"status": "ok", "detector_result": data}

def crop_img(result_json_path: str, images_dir: Optional[str] = None, out_dir: Optional[str] = None,
             padding: float = 0.08, min_area: int = 64):
    """
    封装裁剪逻辑，调用 backend/services/crop.py 中的 crop_from_detector_result。
    返回已保存裁剪图路径列表；遇到异常向上抛出以便上层记录错误。
    """
    # 延迟导入以避免循环依赖
    from services import crop as _crop  # backend/services/crop.py
    # 如果 caller 没有提供 out_dir，默认使用 results/crops
    out_dir_p = Path(out_dir) if out_dir else Path(result_json_path).parent / "crops"
    out_dir_p.mkdir(parents=True, exist_ok=True)

    # 调用 crop 模块的高阶接口
    saved = _crop.crop_from_detector_result(str(result_json_path),
                                            images_dir=str(images_dir) if images_dir else None,
                                            out_dir=str(out_dir_p),
                                            padding=padding,
                                            min_area=min_area)
    return saved
