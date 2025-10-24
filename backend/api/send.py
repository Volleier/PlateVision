from flask import Blueprint, jsonify, send_file, make_response
from pathlib import Path
import mimetypes
import logging

# 访问 receive 模块中的 _jobs 判断任务状态
from backend.api import receive as receive_mod

bp = Blueprint("send_api", __name__, url_prefix="/api")
_logger = logging.getLogger("App")

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
        for jid, info in receive_mod._jobs.items():
            if isinstance(info, dict) and info.get("file_id") == file_id:
                job_info = info
                job_id = jid
                break
    except Exception:
        _logger.exception("send_api: failed to check jobs for file_id=%s", file_id)
    
    if not job_info:
        _logger.warning("send_api: no job found for file_id=%s", file_id)
        return jsonify({"status":"error","message":"no job found","file_id":file_id}), 404

    fut = job_info.get("future")
    if fut is None:
        _logger.error("send_api: job has no future for file_id=%s", file_id)
        return jsonify({"status":"error","message":"internal_error"}), 500

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
        return jsonify({"status":"error","message":"no result image"}), 404

    image_path = Path(result_image)
    if not image_path.exists() or not image_path.is_file():
        return jsonify({"status":"error","message":"result not found on disk"}), 404

    mime, _ = mimetypes.guess_type(str(image_path))
    return send_file(str(image_path), mimetype=mime, as_attachment=False)