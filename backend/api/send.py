from flask import Blueprint, jsonify, send_file
from pathlib import Path
import logging
import mimetypes

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
        return jsonify({
            "status": "error",
            "error": "no job found",
            "file_id": file_id,
            "message": "未找到对应的处理任务"
        }), 404
    
    fut = job_info.get("future")
    if fut is None:
        _logger.error("send_api: job has no future for file_id=%s", file_id)
        return jsonify({
            "status": "error",
            "error": "invalid job state",
            "file_id": file_id
        }), 500
    
    # 任务未完成，返回 pending
    if not fut.done():
        _logger.info("send_api: file_id=%s job_id=%s -> pending", file_id, job_id)
        return jsonify({
            "status": "pending",
            "job_id": job_id,
            "file_id": file_id,
            "message": "图片处理中，请稍候..."
        }), 202
    
    # 检查任务是否执行失败
    try:
        result = fut.result()
        if isinstance(result, dict) and result.get("status") != "ok":
            _logger.warning("send_api: job finished with error for file_id=%s: %s",
                          file_id, result.get("message"))
            return jsonify({
                "status": "error",
                "file_id": file_id,
                "message": result.get("message", "处理失败")
            }), 500
    except Exception as e:
        _logger.exception("send_api: job raised exception for file_id=%s", file_id)
        return jsonify({
            "status": "error",
            "file_id": file_id,
            "message": f"处理失败: {str(e)}"
        }), 500
    
    # 获取存储的结果图片路径
    result_image = job_info.get("result_image")
    
    if not result_image:
        _logger.warning("send_api: no result_image stored for file_id=%s", file_id)
        return jsonify({
            "status": "error",
            "error": "no result image",
            "file_id": file_id,
            "message": "未找到处理结果图片"
        }), 404
    
    # 验证文件存在
    image_path = Path(result_image)
    if not image_path.exists() or not image_path.is_file():
        _logger.error("send_api: result_image not found on disk: %s", result_image)
        return jsonify({
            "status": "error",
            "error": "image file missing",
            "file_id": file_id,
            "message": "结果图片文件不存在"
        }), 404
    
    # 返回图片
    _logger.info("send_api: returning image %s for file_id=%s", image_path.name, file_id)
    mime, _ = mimetypes.guess_type(str(image_path))
    return send_file(str(image_path), mimetype=mime, as_attachment=False)