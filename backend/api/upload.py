from flask import Blueprint, request, jsonify, current_app, url_for
from werkzeug.utils import secure_filename
from pathlib import Path
import os
import tempfile
from uuid import uuid4
from PIL import Image, UnidentifiedImageError
import logging
from typing import Any

try:
    import ulid
except Exception:
    ulid = None

from backend.config import cfg
from backend.api.processing import processing_image

bp = Blueprint("upload_api", __name__, url_prefix="/api")

# Default allowed file extensions for image uploads
DEFAULT_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
ALLOWED_EXT = None

# 简单内存 registry（注意：重启会丢失）
_jobs = {}

# 使用与 app 同名的 logger 以便写入同一日志文件（setup_logging 中通常配置了 "App"）
_logger = logging.getLogger("App")

def _get_allowed_ext():
    global ALLOWED_EXT
    if ALLOWED_EXT is None:
        ALLOWED_EXT = set(ext.lower() for ext in current_app.config.get("ALLOWED_EXT", DEFAULT_ALLOWED_EXT))
    return ALLOWED_EXT

def allowed_filename(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in _get_allowed_ext()

def _task_wrapper(file_id: str, job_id: str):
    _logger.info("worker: start processing file_id=%s job_id=%s", file_id, job_id)
    try:
        result = processing_image(file_id)
        _logger.info("worker: finished processing file_id=%s job_id=%s status=%s", file_id, job_id, result.get("status") if isinstance(result, dict) else None)
        return result
    except Exception:
        _logger.exception("worker: exception processing file_id=%s job_id=%s", file_id, job_id)
        raise

def _task_done_callback(fut, job_id: str):
    try:
        res = fut.result()
        _logger.info("main: task done callback job_id=%s status=%s", job_id, res.get("status") if isinstance(res, dict) else None)
    except Exception as e:
        _logger.exception("main: task done callback raised for job_id=%s", job_id)

@bp.route("/upload", methods=["POST"])
def upload():
    max_len = current_app.config.get("MAX_CONTENT_LENGTH")
    upload_dir = Path(cfg.UPLOADS_DIR)
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        current_app.logger.exception("create upload dir failed")
        return jsonify({"error": "cannot create upload dir", "detail": str(e)}), 500

    file = request.files.get("image") or request.files.get("upload") or (next(iter(request.files.values()), None))
    if not file or not getattr(file, "filename", ""):
        return jsonify({"error": "no file uploaded", "received_fields": list(request.files.keys())}), 400

    orig_name = secure_filename(file.filename or "")
    ext = os.path.splitext(orig_name)[1].lower()
    if ext == "":
        return jsonify({"error": "file has no extension"}), 400
    if not allowed_filename(orig_name):
        return jsonify({"error": "file type not allowed", "ext": ext}), 400

    if ulid is not None:
        file_id = ulid.new().str
    else:
        file_id = uuid4().hex
    final_name = f"{file_id}{ext}"
    final_path = upload_dir / final_name

    current_app.logger.info("Upload received, id=%s, original_filename=%s", file_id, orig_name)

    tmp_path = None
    try:
        # 先写入临时文件（优先写到 upload_dir，失败则回退系统临时目录）
        try:
            with tempfile.NamedTemporaryFile(delete=False, dir=str(upload_dir)) as tmp:
                tmp_path = tmp.name
                file.save(tmp_path)
        except Exception:
            current_app.logger.warning("temp file in upload_dir failed, falling back to system temp dir, id=%s", file_id)
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name
                file.save(tmp_path)

        # 再次检查大小
        if max_len is not None and os.path.getsize(tmp_path) > max_len:
            os.remove(tmp_path)
            current_app.logger.warning("Upload too large after save, id=%s", file_id)
            return jsonify({"error": "file too large after upload", "max": max_len}), 413

        # 验证图片合法性
        try:
            with Image.open(tmp_path) as img:
                img.verify()
        except (UnidentifiedImageError, Exception) as e:
            os.remove(tmp_path)
            current_app.logger.warning("Uploaded file is not a valid image, id=%s, err=%s", file_id, e)
            return jsonify({"error": "invalid image file", "detail": str(e)}), 400

        # 原子移动到最终位置
        os.replace(tmp_path, str(final_path))
        current_app.logger.info("Saved upload, id=%s, path=%s", file_id, final_path)
    except Exception as e:
        current_app.logger.exception("save failed for id=%s", file_id)
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return jsonify({"error": "save failed", "detail": str(e)}), 500
    # ---------- 提交后台任务 ----------
    job_id = uuid4().hex
    task_url = url_for("upload_api.task_status", job_id=job_id, _external=False)
    try:
        executor: Any = getattr(current_app, "executor", None)
        if executor is not None:
            future = executor.submit_stored(job_id, _task_wrapper, file_id, job_id)
            # 在主进程注册 done callback（某些 backend 可能不支持 add_done_callback）
            try:
                future.add_done_callback(lambda fut, jid=job_id: _task_done_callback(fut, jid))
            except Exception:
                _logger.warning("add_done_callback failed for job_id=%s", job_id)
            _jobs[job_id] = future
            _logger.info("Submitted processing task, file_id=%s, job_id=%s", file_id, job_id)
            return jsonify({
                "file_id": file_id,
                "filename": final_name,
                "path": str(final_path),
                "job_id": job_id,
                "task_url": task_url
            }), 202
        else:
            current_app.logger.warning("App.executor not found, running processing synchronously for id=%s", file_id)
            result = processing_image(file_id)
            return jsonify({
                "file_id": file_id,
                "filename": final_name,
                "path": str(final_path),
                "job_id": None,
                "result": result
            }), 200
    except Exception as e:
        current_app.logger.exception("submit task failed for file_id=%s", file_id)
        # 回退同步执行以避免丢失任务
        try:
            result = processing_image(file_id)
            return jsonify({
                "file_id": file_id,
                "filename": final_name,
                "path": str(final_path),
                "job_id": None,
                "result": result
            }), 200
        except Exception as e2:
            current_app.logger.exception("sync processing also failed for file_id=%s", file_id)
            return jsonify({"error": "task submit and sync processing failed", "detail": str(e2)}), 500

@bp.route('/tasks/<job_id>', methods=['GET'])
def task_status(job_id):
    _logger.info("task status requested: job_id=%s remote=%s", job_id, request.remote_addr)
    fut = _jobs.get(job_id)
    if fut is None:
        _logger.warning("unknown job queried: job_id=%s", job_id)
        return jsonify({"error": "unknown job"}), 404
    if fut.done():
        try:
            result = fut.result()
        except Exception as e:
            _logger.exception("task finished with exception: job_id=%s err=%s", job_id, e)
            return jsonify({"status": "error", "error": str(e)}), 200
        _logger.info("task status done: job_id=%s", job_id)
        return jsonify({"status": "done", "result": result}), 200
    else:
        _logger.info("task status pending: job_id=%s", job_id)
        return jsonify({"status": "pending"}), 200