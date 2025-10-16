from typing import Any, Dict, Optional
from pathlib import Path
import os
import shutil
import time
import json

from backend.config import cfg

def _fs_path_to_static_url(server_path: Optional[str]) -> Optional[str]:
    """
    把后端文件系统路径转换为前端可访问的 /static/... 相对 URL。
    """
    if not server_path:
        return None
    p = Path(server_path)
    try:
        p = p.resolve()
    except Exception:
        p = Path(server_path)
    repo_root = Path(__file__).resolve().parents[2]  # e:\Project\PlateVision
    static_root = (repo_root / "backend" / "static").resolve()
    try:
        rel = p.relative_to(static_root)
        return "/static/" + str(rel).replace("\\", "/")
    except Exception:
        s = str(server_path).replace("\\", "/")
        if s.startswith("/static/"):
            return s
        return None

def plate_detector(file_id: str, conf: float = 0.25, imgsz: int = 640, results_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    本地封装：调用 backend.services.plate_detector.detect_image(file_id)
    - 确保常用目录存在
    - 使用 cfg.RESULTS_DETECTOR_DIR 或传入的 results_dir
    - 返回与服务模块相同的 detector_out（{"status":.., "image":.., "out_image":.., "out_json":.., "detections":[..]}）
    """
    # 延迟导入服务模块（避免循环依赖）
    from backend.services import plate_detector as detector_service

    # 准备路径
    repo_root = Path(__file__).resolve().parents[2]
    static_dir = repo_root / "backend" / "static"
    uploads_dir = Path(cfg.UPLOADS_DIR)
    results_root = static_dir / "results"
    detect_results_dir = Path(results_dir) if results_dir else Path(cfg.RESULTS_DETECTOR_DIR)

    # 确保目录存在
    uploads_dir.mkdir(parents=True, exist_ok=True)
    results_root.mkdir(parents=True, exist_ok=True)
    detect_results_dir.mkdir(parents=True, exist_ok=True)

    # 调用服务（当前服务接口只需 file_id）
    detector_out = detector_service.detect_image(file_id)

    # 如果需要，可以在这里扩展对 detector_out 的统一后处理（目前保持原样）
    return detector_out

def processing_image(file_id: str, out_dir: Optional[str] = None, conf: float = 0.25, imgsz: int = 640) -> Dict[str, Any]:
    """
    主入口：通过上传时的 file_id 调用本地 plate_detector 封装。
    """
    # 准备常用路径
    repo_root = Path(__file__).resolve().parents[2]
    static_dir = repo_root / "backend" / "static"
    uploads_dir = Path(cfg.UPLOADS_DIR)
    results_root = static_dir / "results"

    detect_results_dir = Path(cfg.RESULTS_DETECTOR_DIR)
    crops_root_dir = results_root / "crops"

    uploads_dir.mkdir(parents=True, exist_ok=True)
    results_root.mkdir(parents=True, exist_ok=True)
    detect_results_dir.mkdir(parents=True, exist_ok=True)
    crops_root_dir.mkdir(parents=True, exist_ok=True)

    # 使用封装函数，仅传 file_id
    detector_out = plate_detector(file_id, conf=conf, imgsz=imgsz, results_dir=detect_results_dir)
    if detector_out.get("status") != "ok":
        return {"status": "error", "message": detector_out.get("error", "detector failed"), "file_id": file_id}

    # detector 返回结构： {"status":"ok", "image": "<name>", "out_image": "<path>", "out_json": "<path>", "detections": [...]}
    data: Dict[str, Any] = {}
    data["detections"] = detector_out.get("detections", [])
    data.setdefault("internal", {})
    data["internal"]["uploaded_name"] = detector_out.get("image")
    result_json_path = detector_out.get("out_json")
    annotated_image = detector_out.get("out_image")
    data["internal"]["result_json"] = str(result_json_path) if result_json_path else None
    data["internal"]["annotated_image"] = str(annotated_image) if annotated_image else None

    # 转为前端可访问 URL（如果存在）
    annotated_url = _fs_path_to_static_url(data["internal"]["annotated_image"]) if data["internal"]["annotated_image"] else None
    if annotated_url:
        data["internal"]["annotated_url"] = annotated_url

    # 当存在 detector json 时执行裁剪与后续步骤
    if data["internal"]["result_json"] and Path(data["internal"]["result_json"]).exists():
        try:
            saved = crop_img(str(data["internal"]["result_json"]),
                                            images_dir=str(uploads_dir),
                                            out_dir=str(crops_root_dir),
                                            padding=0.08,
                                            min_area=64)
            data["internal"]["crops"] = saved

            # 调用 number_detector
            try:
                from backend.services import plate_reader as number_detector_service
            except Exception:
                number_detector_service = None

            if number_detector_service is not None:
                number_results_dir = results_root / "number"
                number_results_dir.mkdir(parents=True, exist_ok=True)
                try:
                    number_detector_service.detect_all(conf=conf, imgsz=imgsz, results_dir=number_results_dir, input_path=None)
                    imgs = sorted([p for p in number_results_dir.iterdir() if p.is_file() and p.suffix.lower() in {'.jpg','.jpeg','.png','.bmp','.tif','.tiff'}])
                    jsons = sorted([p for p in number_results_dir.iterdir() if p.is_file() and p.suffix.lower() == '.json'])
                    number_images = [ _fs_path_to_static_url(str(p)) or str(p) for p in imgs ]
                    number_jsons = [ _fs_path_to_static_url(str(p)) or str(p) for p in jsons ]
                    data["internal"]["number_results"] = {"images": number_images, "jsons": number_jsons, "dir": str(number_results_dir)}
                except Exception as e:
                    data["internal"]["number_error"] = str(e)
            else:
                data["internal"]["number_error"] = "number_detector not available or import failed"
        except Exception as e:
            data["internal"]["crops_error"] = str(e)
    else:
        data["internal"]["crops_error"] = f"detector result json not found: {result_json_path}"

    # 可选：把 annotated_image 复制到外部 out_dir 并返回 URL
    if out_dir and data["internal"].get("annotated_image"):
        annotated_image_path = Path(data["internal"]["annotated_image"])
        if annotated_image_path.exists():
            out_dir_p = Path(out_dir)
            out_dir_p.mkdir(parents=True, exist_ok=True)
            exported = out_dir_p / annotated_image_path.name
            shutil.copy2(annotated_image_path, exported)
            data["internal"]["exported_image"] = str(exported)
            exported_url = _fs_path_to_static_url(str(exported))
            if exported_url:
                data["internal"]["exported_url"] = exported_url

    # 返回结构
    return {"status": "ok", "file_id": file_id, "detector_result": data}


def crop_img(result_json_path: str, images_dir: Optional[str] = None, out_dir: Optional[str] = None,
             padding: float = 0.08, min_area: int = 64):
    """
    封装裁剪调用：调用 backend.services.plate_extractor.crop_from_detector_result 并返回已保存裁剪图路径列表。
    """
    from backend.services import plate_extractor as _crop  # 延迟导入以避免循环依赖

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
