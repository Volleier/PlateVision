from typing import Callable, Any, Dict, Optional
from pathlib import Path
import logging
import shutil

from backend.config import cfg

# 使用与 app 相同的 logger 名称，确保日志写入同一位置
_logger = logging.getLogger("App")

def processing_image(file_id: str, out_dir: Optional[str] = None, progress_callback: Optional[Callable[[str, str, Any], None]] = None) -> Dict[str, Any]:
    """
    主处理流程：按顺序执行 detector -> extractor -> reader。
    
    Args:
        file_id: 上传文件的唯一标识
        out_dir: 可选的导出目录路径（用于导出标注图）
    
    Returns:
        包含处理状态和各步骤结果的字典
    """
    _logger.info("processing_image: start file_id=%s", file_id)
    data: Dict[str, Any] = {"internal": {}}

    # ---------- Detector ----------
    det_out = detector_step(file_id)
    if progress_callback:
        progress_callback("detector", "ok" if det_out.get("status") == "ok" else "error", det_out)
    if det_out.get("status") != "ok":
        _logger.warning("processing_image: detector failed for file_id=%s detail=%s", 
                       file_id, det_out.get("error"))
        return {
            "status": "error", 
            "message": det_out.get("error", "detector failed"), 
            "file_id": file_id
        }
    
    data["detections"] = det_out.get("detections", [])
    data["internal"]["uploaded_name"] = det_out.get("image")
    data["internal"]["result_json"] = det_out.get("out_json")
    data["internal"]["annotated_image"] = det_out.get("out_image")

    # ---------- Extractor ----------
    ext_out = extractor_step(file_id)
    if progress_callback:
        progress_callback("extractor", "ok" if ext_out.get("status") == "ok" else "error", ext_out)
    if ext_out.get("status") == "ok":
        data["internal"]["crops"] = ext_out.get("crops", [])
        data["internal"]["extractor_out_dir"] = ext_out.get("out_dir")
        data["internal"]["detector_json"] = ext_out.get("detector_json")
    else:
        _logger.warning("processing_image: extractor failed for file_id=%s detail=%s", 
                       file_id, ext_out.get("error"))
        data["internal"]["crops_error"] = ext_out.get("error")
        data["internal"]["crops"] = []

    # ---------- Reader ----------
    rd_out = reader_step(file_id)
    if progress_callback:
        progress_callback("reader", "ok" if rd_out.get("status") == "ok" else "error", rd_out)
    if rd_out.get("status") == "ok":
        data["internal"]["reader_results"] = {
            "images": rd_out.get("images", []),
            "jsons": rd_out.get("jsons", []),
            "dir": rd_out.get("out_dir")
        }
    else:
        _logger.warning("processing_image: reader failed for file_id=%s detail=%s", 
                       file_id, rd_out.get("error"))
        data["internal"]["reader_error"] = rd_out.get("error")

    _logger.info("processing_image: finished file_id=%s", file_id)
    return {"status": "ok", "file_id": file_id, "detector_result": data}


def detector_step(file_id: str) -> Dict[str, Any]:
    """
    检测步骤：调用 services/plate_detector，返回检测结果。
    服务层负责根据 file_id 和 cfg 定位文件并写入结果。
    """
    try:
        from backend.services import plate_detector as detector_service
        _logger.info("detector_step: start file_id=%s", file_id)
        result = detector_service.detect_image(file_id)
        _logger.info("detector_step: finished file_id=%s status=%s", 
                    file_id, result.get("status") if isinstance(result, dict) else None)
        return result if isinstance(result, dict) else {"status": "error", "error": "invalid detector output"}
    except Exception as e:
        _logger.exception("detector_step: exception file_id=%s", file_id)
        return {"status": "error", "error": str(e)}


def extractor_step(file_id: str, padding: float = 0.08, min_area: int = 64) -> Dict[str, Any]:
    """
    裁剪步骤：调用 services/plate_extractor，基于检测结果裁剪车牌区域。
    服务层根据 file_id 查找 detector JSON 并生成裁剪图。
    """
    try:
        from backend.services import plate_extractor as extractor
        _logger.info("extractor_step: start file_id=%s", file_id)
        result = extractor.extract_image(file_id, padding=padding, min_area=min_area)
        _logger.info("extractor_step: finished file_id=%s status=%s", 
                    file_id, result.get("status") if isinstance(result, dict) else None)
        return result if isinstance(result, dict) else {"status": "error", "error": "invalid extractor output"}
    except Exception as e:
        _logger.exception("extractor_step: exception file_id=%s", file_id)
        return {"status": "error", "error": str(e)}


def reader_step(file_id: str) -> Dict[str, Any]:
    """
    识别步骤：调用 services/plate_reader，对裁剪后的车牌图进行 OCR 识别。
    服务层根据 file_id 查找裁剪图并生成识别结果。
    """
    try:
        from backend.services import plate_reader as reader_service
        _logger.info("reader_step: start file_id=%s", file_id)
        result = reader_service.read_image(file_id)
        _logger.info("reader_step: finished file_id=%s status=%s", 
                    file_id, result.get("status") if isinstance(result, dict) else None)
        return result if isinstance(result, dict) else {"status": "error", "error": "invalid reader output"}
    except Exception as e:
        _logger.exception("reader_step: exception file_id=%s", file_id)
        return {"status": "error", "error": str(e)}



