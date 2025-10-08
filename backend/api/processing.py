from typing import Any, Dict, Optional
from pathlib import Path
import os
import shutil
import uuid
import time
import json

def processing_image(file_path: str, out_dir: Optional[str] = None, conf: float = 0.25, imgsz: int = 640) -> Dict[str, Any]:
    """
    主入口：负责文件路径 -> 调用 yolo_detector -> 调用 crop -> 导出标注图（如需）
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"file not found: {file_path}")

    repo_root = Path(__file__).resolve().parents[2]  # e:\Project\PlateVision
    static_dir = repo_root / "backend" / "static"
    uploads_dir = static_dir / "uploads"

    # 统一 results 根，然后分别指定 detector 输出目录 和 crop 输出目录
    results_root = static_dir / "results"
    detect_results_dir = results_root / "yolo_detect"   # detector 写入的位置
    crops_root_dir = results_root / "crops"              # crop 写入的位置

    uploads_dir.mkdir(parents=True, exist_ok=True)
    results_root.mkdir(parents=True, exist_ok=True)
    detect_results_dir.mkdir(parents=True, exist_ok=True)
    crops_root_dir.mkdir(parents=True, exist_ok=True)

    src = Path(file_path)

    # 直接使用传入的路径，不再复制到 uploads（删除复制/避免复制的逻辑）
    dst = src
    unique_name = src.name

    # 调用 yolo_detector（它会调用 services.detector 并读取结果 json）
    detector_out = yolo_detector(str(dst), conf=conf, imgsz=imgsz, detect_results_dir=detect_results_dir)
    if detector_out.get("status") != "ok":
        return {"status": "error", "message": detector_out.get("message", "detector failed"), "source": str(file_path)}

    data = detector_out["detector_result"]
    data.setdefault("internal", {})
    data["internal"]["uploaded_name"] = unique_name
    # detector 已把 result json 路径写在 internal.result_json（若成功）
    result_json_path = data["internal"].get("result_json")
    annotated_image = data["internal"].get("annotated_image")
    data["internal"]["annotated_image"] = annotated_image

    # 仅当 detector 确认生成了 result json 时才调用裁剪
    if result_json_path and Path(result_json_path).exists():
        try:
            from services import crop  # backend/services/crop.py
            crops_out_dir = crops_root_dir
            crops_out_dir.mkdir(parents=True, exist_ok=True)
            saved = crop_img(str(result_json_path),
                                               images_dir=str(uploads_dir),
                                               out_dir=str(crops_out_dir),
                                               padding=0.08,
                                               min_area=64)
            data["internal"]["crops"] = saved

            # 调用 OCR 对每个裁剪结果进行识别（使用 backend/services/ocr.py 中的 recognize_plate_from_path）
            try:
                from services import ocr as ocr_service  # backend/services/ocr.py
            except Exception:
                ocr_service = None

            if ocr_service is not None:
                ocr_results = []
                for crop_path in saved:
                    try:
                        plate_text, conf = ocr_service.recognize_plate_from_path(str(crop_path), engine='easyocr')
                        ocr_results.append({"path": str(crop_path), "text": plate_text, "conf": conf})
                        # 在控制台打印保存的结果
                        print(f"OCR: {crop_path} -> {plate_text} (conf={conf})")
                    except Exception as e:
                        ocr_results.append({"path": str(crop_path), "error": str(e)})
                        print(f"OCR error for {crop_path}: {e}")
                data["internal"]["ocr_results"] = ocr_results

                # 新增：通过 api 层保存到数据库（不在 processing 中直接操作底层 db）
                try:
                    from api import db_api  # backend/api/db_api.py
                    try:
                        resp = db_api.save_ocr_results(unique_name, ocr_results)
                        data["internal"]["db_save"] = resp
                        print(f"DB save response: {resp}")
                    except Exception as e:
                        data["internal"]["db_save_error"] = f"save_ocr_results error: {e}"
                except Exception as e:
                    data["internal"]["db_save_error"] = f"db_api import failed: {e}"
            else:
                data["internal"]["ocr_error"] = "easyocr not available or import failed"
        except Exception as e:
            data["internal"]["crops_error"] = str(e)
    else:
        data["internal"]["crops_error"] = f"detector result json not found: {result_json_path}"

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


def yolo_detector(uploaded_path: str, conf: float = 0.25, imgsz: int = 640, detect_results_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    仅负责调用 detector 并读取 detector 产生的 JSON/标注图。
    参数 uploaded_path: 已保存到 backend/static/uploads 的文件完整路径（包含唯一名）。
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
    results_root = static_dir / "results"

    # 计算要让 detector 写入的结果目录，并把它传给 detector
    results_dir = Path(detect_results_dir) if detect_results_dir else results_root / "yolo_detect"
    # 调用 detector，并传入结果目录（同步调用）
    detector.detect_all(conf=conf, imgsz=imgsz, results_dir=results_dir, input_path=Path(uploaded_path))

    up = Path(uploaded_path)
    result_json_path = results_dir / f"{up.stem}.json"
    annotated_image_path = results_dir / f"{up.stem}_pred{up.suffix}"

    # 等待短时间以确保文件写入完成（通常 detector.detect_all 是同步的，但加个重试更稳健）
    timeout = 5.0  # seconds
    poll_interval = 0.15
    waited = 0.0
    while waited < timeout and not result_json_path.exists():
        time.sleep(poll_interval)
        waited += poll_interval

    if not result_json_path.exists():
        return {"status": "error", "message": "detector did not produce result json", "expected": str(result_json_path)}

    # 读取 json
    try:
        with open(result_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"failed to read detector json: {e}", "path": str(result_json_path)}

    data.setdefault("internal", {})
    data["internal"]["uploaded_name"] = up.name
    data["internal"]["result_json"] = str(result_json_path)
    data["internal"]["annotated_image"] = str(annotated_image_path) if annotated_image_path.exists() else None

    return {"status": "ok", "detector_result": data}


def crop_img(result_json_path: str, images_dir: Optional[str] = None, out_dir: Optional[str] = None,
             padding: float = 0.08, min_area: int = 64):
    """
    封装裁剪调用：调用 backend.services.crop.crop_from_detector_result 并返回已保存裁剪图路径列表。
    延迟导入以避免循环依赖；若 result json 不存在会抛出 FileNotFoundError。
    """
    from services import crop as _crop  # backend/services/crop.py (延迟导入)

    json_p = Path(result_json_path)
    if not json_p.exists():
        raise FileNotFoundError(f"detector result json not found: {result_json_path}")

    out_dir_p = Path(out_dir) if out_dir else json_p.parent / "crops"
    out_dir_p.mkdir(parents=True, exist_ok=True)

    saved = _crop.crop_from_detector_result(str(json_p),
                                            images_dir=str(images_dir) if images_dir else None,
                                            out_dir=str(out_dir_p),
                                            padding=padding,
                                            min_area=min_area)
    return saved
