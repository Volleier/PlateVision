import os
from typing import Any, Dict, Optional
from pathlib import Path
import shutil
import uuid
import time
import json

def processing_image(file_path: str, out_dir: Optional[str] = None, conf: float = 0.25, imgsz: int = 640):
    """
    兼容接口：委托给本模块的 yolo_detector 实现
    """
    return yolo_detector(file_path, out_dir=out_dir, conf=conf, imgsz=imgsz)

def yolo_detector(file_path: str, out_dir: Optional[str] = None, conf: float = 0.25, imgsz: int = 640) -> Dict[str, Any]:
    """
    将处理逻辑迁移到此函数：
    - 把图片复制到 backend/static/uploads
    - 调用 services.detector.detect_all 进行检测
    - 从 backend/static/results 读取对应的 JSON 和标注图并返回结果字典
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"file not found: {file_path}")

    from services import detector  # 使用 backend/services/detector.py 中的 detect_all

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

    # 调用 detector 的批处理接口（会遍历 uploads 并在 results 中生成文件）
    detector.detect_all(conf=conf, imgsz=imgsz)

    result_json_path = results_dir / f"{dst.stem}.json"
    annotated_image_path = results_dir / f"{dst.stem}_pred{dst.suffix}"

    if result_json_path.exists():
        with open(result_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("internal", {})
        data["internal"]["uploaded_name"] = unique_name
        data["internal"]["result_json"] = str(result_json_path)
        data["internal"]["annotated_image"] = str(annotated_image_path) if annotated_image_path.exists() else None

        if out_dir and annotated_image_path.exists():
            out_dir_p = Path(out_dir)
            out_dir_p.mkdir(parents=True, exist_ok=True)
            exported = out_dir_p / annotated_image_path.name
            shutil.copy2(annotated_image_path, exported)
            data["internal"]["exported_image"] = str(exported)

        return {"status": "ok", "source": str(file_path), "detector_result": data}

    return {"status": "error", "message": "detector did not produce result", "path": str(file_path)}