from typing import Any, Dict, Optional
from pathlib import Path
import os
import shutil
import time
import json
import logging

from backend.config import cfg

# 使用与 app 相同的 logger 名称，确保日志写入同一位置
_logger = logging.getLogger("App")

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
    repo_root = Path(__file__).resolve().parents[2]
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
    直接在当前进程/线程同步调用后端 detector 服务。
    设计原则：upload 已把 processing_image 提交到 executor，processing 在 worker 内执行时
    不应再尝试使用 Flask app 的 executor（避免递归提交或跨进程访问 current_app）。
    """
    # 延迟导入服务模块（避免循环依赖）
    from backend.services import plate_detector as detector_service

    repo_root = Path(__file__).resolve().parents[2]
    static_dir = repo_root / "backend" / "static"
    uploads_dir = Path(cfg.UPLOADS_DIR)
    results_root = static_dir / "results"
    detect_results_dir = Path(results_dir) if results_dir else Path(cfg.RESULTS_DETECTOR_DIR)

    uploads_dir.mkdir(parents=True, exist_ok=True)
    results_root.mkdir(parents=True, exist_ok=True)
    detect_results_dir.mkdir(parents=True, exist_ok=True)

    _logger.info("plate_detector: start file_id=%s conf=%s imgsz=%s", file_id, conf, imgsz)
    try:
        # 直接同步调用 detector 服务
        # 所以这里只传入 file_id，其他参数由服务内部使用 cfg 配置
        detector_out = detector_service.detect_image(file_id)
        _logger.info("plate_detector: finished file_id=%s status=%s", file_id, detector_out.get("status") if isinstance(detector_out, dict) else None)
        return detector_out
    except Exception as e:
        _logger.exception("plate_detector: exception for file_id=%s", file_id)
        return {"status": "error", "error": str(e)}

def processing_image(file_id: str, out_dir: Optional[str] = None, conf: float = 0.25, imgsz: int = 640) -> Dict[str, Any]:
    """
    主入口：在 worker 中执行整个检测->裁剪->识别流程，使用本地 logger 记录关键步骤。
    """
    _logger.info("processing_image: start file_id=%s", file_id)
    # 准备路径
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

    #  ---------- 使用 detector 接口 ----------
    try:
        detector_out = plate_detector(file_id, conf=conf, imgsz=imgsz, results_dir=detect_results_dir)
        if detector_out.get("status") != "ok":
            _logger.warning("processing_image: detector failed for file_id=%s detail=%s", file_id, detector_out.get("error"))
            return {"status": "error", "message": detector_out.get("error", "detector failed"), "file_id": file_id}

        data: Dict[str, Any] = {}
        data["detections"] = detector_out.get("detections", [])
        data.setdefault("internal", {})
        data["internal"]["uploaded_name"] = detector_out.get("image")
        result_json_path = detector_out.get("out_json")
        annotated_image = detector_out.get("out_image")
        data["internal"]["result_json"] = str(result_json_path) if result_json_path else None
        data["internal"]["annotated_image"] = str(annotated_image) if annotated_image else None

        annotated_url = _fs_path_to_static_url(data["internal"]["annotated_image"]) if data["internal"]["annotated_image"] else None
        if annotated_url:
            data["internal"]["annotated_url"] = annotated_url

        # ---------- 使用 extractor 接口 ----------
        try:
            # 延迟导入 extractor（避免循环依赖）
            from backend.services import plate_extractor as extractor
            ext_res = extractor.extract_image(file_id, padding=0.08, min_area=64)
            if isinstance(ext_res, dict) and ext_res.get("status") == "ok":
                # extractor 返回的 crops 通常为文件路径列表
                saved = ext_res.get("crops", [])
                data["internal"]["crops"] = saved
                data["internal"]["extractor_out_dir"] = ext_res.get("out_dir")
                data["internal"]["detector_json"] = ext_res.get("detector_json")
            else:
                # 记录 extractor 的错误或未找到情况
                msg = ext_res.get("error") if isinstance(ext_res, dict) else str(ext_res)
                _logger.warning("extractor failed or not found for file_id=%s detail=%s", file_id, msg)
                data["internal"]["crops_error"] = msg or "extractor failed or not found"
                saved = []

            # 如果需要对每个 crop 做 number detection，逐张传入 detect_all 的 input_path
            try:
                from backend.services import plate_reader as number_detector_service
            except Exception:
                number_detector_service = None

            if number_detector_service is not None and saved:
                number_results_dir = results_root / "number"
                number_results_dir.mkdir(parents=True, exist_ok=True)
                try:
                    # 为避免重复加载模型多次，这里尽量调用 detect_all per-image with input_path
                    for crop_path in saved:
                        try:
                            number_detector_service.detect_all(conf=conf, imgsz=imgsz, results_dir=number_results_dir, input_path=Path(crop_path))
                        except Exception:
                            _logger.exception("number detection failed for crop=%s file_id=%s", crop_path, file_id)
                    imgs = sorted([p for p in number_results_dir.iterdir() if p.is_file() and p.suffix.lower() in {'.jpg','.jpeg','.png','.bmp','.tif','.tiff'}])
                    jsons = sorted([p for p in number_results_dir.iterdir() if p.is_file() and p.suffix.lower() == '.json'])
                    number_images = [_fs_path_to_static_url(str(p)) or str(p) for p in imgs]
                    number_jsons = [_fs_path_to_static_url(str(p)) or str(p) for p in jsons]
                    data["internal"]["number_results"] = {"images": number_images, "jsons": number_jsons, "dir": str(number_results_dir)}
                except Exception as e:
                    _logger.exception("number detection aggregation failed for file_id=%s", file_id)
                    data["internal"]["number_error"] = str(e)
            else:
                if number_detector_service is None:
                    data["internal"]["number_error"] = "number_detector not available or import failed"
        except Exception as e:
            _logger.exception("extract_image failed for file_id=%s", file_id)
            data["internal"]["crops_error"] = str(e)

        # 可选导出 annotated image
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

        _logger.info("processing_image: finished file_id=%s", file_id)
        return {"status": "ok", "file_id": file_id, "detector_result": data}
    except Exception as e:
        _logger.exception("processing_image: unexpected exception for file_id=%s", file_id)
        return {"status": "error", "error": str(e), "file_id": file_id}


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
