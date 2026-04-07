from flask import Blueprint, jsonify, send_file, make_response
from pathlib import Path
import mimetypes
import logging
from typing import Optional

# 访问 receive 模块中的 _jobs 判断任务状态
from backend.api import receive as receive_mod
from backend.config import cfg

bp = Blueprint("send_api", __name__, url_prefix="/api")
_logger = logging.getLogger("App")

def _find_result_image_from_disk(file_id: str) -> Optional[Path]:
    exts = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")
    candidates = []

    # Prefer reader outputs first
    reader_dir = Path(getattr(cfg, "RESULTS_READER_DIR", ""))
    if reader_dir.exists():
        for ext in exts:
            candidates.extend(reader_dir.glob(f"*{file_id}*_pred{ext}"))

    # Fallback to detector annotated outputs
    detector_dir = Path(getattr(cfg, "RESULTS_DETECTOR_DIR", ""))
    if detector_dir.exists():
        for ext in exts:
            candidates.extend(detector_dir.glob(f"*{file_id}*_pred{ext}"))

    candidates = [p for p in candidates if p.exists() and p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)

@bp.route("/send/<file_id>", methods=["GET"])
def send_result_image(file_id: str):
    """
    根据 file_id 返回处理结果图片。
    
    优先使用 worker 完成后存储的结果路径，避免文件系统查找。
    
    Args:
        file_id: 文件唯一标识
        
    Returns:
        - 202: 任务处理中 (JSON)
        - 200: 图片文件
        - 404: 未找到图片 (JSON)
        - 500: 任务执行失败 (JSON)
    """
    _logger.info("send_api: request for file_id=%s", file_id)
    
    # 查找对应的 job
    job_info = None
    job_id = None

    try:
        finder = getattr(receive_mod, "_find_job_by_file_id", None)
        if callable(finder):
            job_id, job_info = finder(file_id)
        else:
            # Backward compatibility if helper is unavailable
            for jid, info in list(getattr(receive_mod, "_jobs", {}).items()):
                if isinstance(info, dict) and info.get("file_id") == file_id:
                    job_info = info
                    job_id = jid
                    break
    except Exception:
        _logger.exception("send_api: failed to check jobs for file_id=%s", file_id)
    
    if not job_info:
        fallback_img = _find_result_image_from_disk(file_id)
        if fallback_img is not None:
            _logger.info("send_api: no in-memory job, serving disk fallback for file_id=%s path=%s", file_id, fallback_img)
            mime, _ = mimetypes.guess_type(str(fallback_img))
            return send_file(str(fallback_img), mimetype=mime, as_attachment=False)
        _logger.warning("send_api: no job found for file_id=%s", file_id)
        return jsonify({"status":"error","message":"no job found","file_id":file_id}), 404

    fut = job_info.get("future")
    if fut is None:
        # Placeholder state before executor submission; keep polling instead of failing fast.
        steps = job_info.get("steps", {})
        return make_response(jsonify({"status": "pending", "file_id": file_id, "steps": steps}), 202)

    # 任务未完成，返回 pending + steps 状态
    if not fut.done():
        steps = job_info.get("steps", {})
        return make_response(jsonify({"status": "pending", "file_id": file_id, "steps": steps}), 202)

    # 任务完成后，继续原有检查并返回图片
    try:
        result = fut.result()
        if isinstance(result, dict) and result.get("status") != "ok":
            return jsonify({"status":"error","message":result.get("message","failed")}), 500
    except Exception as e:
        _logger.exception("send_api: job raised exception for file_id=%s", file_id)
        return jsonify({"status":"error","message":"job exception"}), 500

    result_image = job_info.get("result_image")
    if not result_image:
        fallback_img = _find_result_image_from_disk(file_id)
        if fallback_img is not None:
            _logger.info("send_api: result_image missing in job_info, serving disk fallback for file_id=%s path=%s", file_id, fallback_img)
            mime, _ = mimetypes.guess_type(str(fallback_img))
            return send_file(str(fallback_img), mimetype=mime, as_attachment=False)
        return jsonify({"status":"error","message":"no result image"}), 404

    image_path = Path(result_image)
    if not image_path.exists() or not image_path.is_file():
        return jsonify({"status":"error","message":"result not found on disk"}), 404

    mime, _ = mimetypes.guess_type(str(image_path))
    return send_file(str(image_path), mimetype=mime, as_attachment=False)