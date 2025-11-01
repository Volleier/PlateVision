from flask import Blueprint, request, jsonify, current_app, url_for
from werkzeug.utils import secure_filename
from pathlib import Path
import os
import tempfile
from uuid import uuid4
from PIL import Image, UnidentifiedImageError
import logging
from typing import Any, Optional
import time
import json

try:
    import ulid
except Exception:
    ulid = None

from backend.config import cfg
from backend.api.processing import processing_image

bp = Blueprint("receive_api", __name__, url_prefix="/api")  # 改为 receive_api

# Default allowed file extensions for image uploads
DEFAULT_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
ALLOWED_EXT = None

# 简单内存 registry（注意：重启会丢失）
# 结构：_jobs[job_id] = {"future": Future, "file_id": file_id}
_jobs = {}

_logger = logging.getLogger("App")

def _get_allowed_ext():
    global ALLOWED_EXT
    if ALLOWED_EXT is None:
        ALLOWED_EXT = set(ext.lower() for ext in current_app.config.get("ALLOWED_EXT", DEFAULT_ALLOWED_EXT))
    return ALLOWED_EXT

def allowed_filename(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in _get_allowed_ext()

def _task_wrapper(file_id: str, job_id: str, config: Optional[dict] = None):
    _logger.info("worker: start processing file_id=%s job_id=%s config=%s", file_id, job_id, str(config))
    def cb(step: str, status: str, info: Any = None):
        try:
            entry = _jobs.get(job_id)
            if entry is None:
                return
            steps = entry.setdefault("steps", {})
            steps[step] = {"status": status, "info": (info if isinstance(info, dict) else None), "updated_at": time.time()}
            entry["last_update"] = time.time()
        except Exception:
            _logger.exception("worker: progress callback failed for job_id=%s step=%s", job_id, step)

    try:
        # 调用 processing_image 并传入回调与 config
        result = processing_image(file_id, progress_callback=cb, config=config)
        _logger.info("worker: finished processing file_id=%s job_id=%s status=%s", file_id, job_id, result.get("status") if isinstance(result, dict) else None)
        return result
    except Exception:
        _logger.exception("worker: exception processing file_id=%s job_id=%s", file_id, job_id)
        raise

def _task_done_callback(fut, job_id: str):
    """任务完成回调：提取并存储结果图片路径"""
    try:
        res = fut.result()
        _logger.info("main: task done callback job_id=%s status=%s", job_id, res.get("status") if isinstance(res, dict) else None)
        
        # 提取结果图片路径并存储到 _jobs
        if isinstance(res, dict) and res.get("status") == "ok":
            file_id = res.get("file_id")  # 从结果中获取 file_id
            internal = res.get("detector_result", {}).get("internal", {})
            reader_results = internal.get("reader_results", {})
            
            # 优先使用 reader 的图片（过滤出当前 file_id 的图片）
            reader_images = reader_results.get("images", [])
            result_image = None
            
            if reader_images and file_id:
                # 查找包含当前 file_id 的图片
                for img_path in reader_images:
                    if file_id in str(img_path):
                        result_image = img_path
                        break
                # 如果没找到匹配的，取最后一张（最新的）
                if not result_image and reader_images:
                    result_image = reader_images[-1]
            
            # 如果 reader 没有图片，使用 detector 的标注图
            if not result_image:
                result_image = internal.get("annotated_image") or internal.get("exported_image")
            
            # 存储结果图片路径到 _jobs
            if job_id in _jobs and isinstance(_jobs[job_id], dict):
                _jobs[job_id]["result_image"] = result_image
                _logger.info("main: stored result_image for job_id=%s file_id=%s: %s", 
                           job_id, file_id, result_image)
    except Exception:
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

    # 解析前端可选传入的 config 字段（JSON）
    config = None
    raw_config = request.form.get("config") or request.form.get("config_json")
    if raw_config:
        try:
            config = json.loads(raw_config)
            # 记录原始 JSON 字符串与美化后的解析结果，确保完整可见（注意隐私/敏感信息）
            current_app.logger.info("Upload raw config: %s", raw_config)
            current_app.logger.info("Upload parsed config: %s", json.dumps(config, ensure_ascii=False, indent=2))
        except Exception as e:
            current_app.logger.warning("Failed to parse config JSON from upload: %s err=%s", raw_config, e)
            config = None

    # 优先读取 "file" 字段（前端发送的键名）
    file = (
        request.files.get("file")
        or request.files.get("image")
        or request.files.get("upload")
        or (next(iter(request.files.values()), None))
    )
    if not file or not getattr(file, "filename", ""):
        return jsonify({"error": "no file uploaded", "received_fields": list(request.files.keys())}), 400

    orig_name = secure_filename(file.filename or "")
    ext = os.path.splitext(orig_name)[1].lower()
    if ext == "":
        return jsonify({"error": "file has no extension"}), 400
    if not allowed_filename(orig_name):
        return jsonify({"error": "file type not allowed", "ext": ext}), 400

    # 兼容不同 ulid 库实现：尝试多种常见接口，失败则回退到 uuid4
    file_id = None
    if ulid is not None:
        try:
            if hasattr(ulid, "new"):
                # ulid-py 等：ulid.new() -> ULID obj，str(...) 可获取文本表示
                file_id = str(ulid.new())
            elif hasattr(ulid, "ULID"):
                # 某些实现提供 ULID 类构造
                try:
                    file_id = str(ulid.ULID())
                except Exception:
                    file_id = None
            elif hasattr(ulid, "generate"):
                # 其他实现可能有 generate()
                file_id = str(ulid.generate())
            else:
                file_id = None
        except Exception:
            _logger.exception("ulid generation failed, fallback to uuid4")
            file_id = None
    if not file_id:
        file_id = uuid4().hex
    final_name = f"{file_id}{ext}"
    final_path = upload_dir / final_name

    current_app.logger.info("Upload received, id=%s, original_filename=%s", file_id, orig_name)

    tmp_path = None
    try:
        try:
            with tempfile.NamedTemporaryFile(delete=False, dir=str(upload_dir)) as tmp:
                tmp_path = tmp.name
                file.save(tmp_path)
        except Exception:
            current_app.logger.warning("temp file in upload_dir failed, falling back to system temp dir, id=%s", file_id)
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name
                file.save(tmp_path)

        if max_len is not None and os.path.getsize(tmp_path) > max_len:
            os.remove(tmp_path)
            current_app.logger.warning("Upload too large after save, id=%s", file_id)
            return jsonify({"error": "file too large after upload", "max": max_len}), 413

        try:
            with Image.open(tmp_path) as img:
                img.verify()
        except (UnidentifiedImageError, Exception) as e:
            os.remove(tmp_path)
            current_app.logger.warning("Uploaded file is not a valid image, id=%s, err=%s", file_id, e)
            return jsonify({"error": "invalid image file", "detail": str(e)}), 400

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
    task_url = url_for("receive_api.task_status", job_id=job_id, _external=False)
    
    executor: Any = getattr(current_app, "executor", None)
    if executor is None:
        # 无 executor，同步处理
        current_app.logger.warning("App.executor not found, running processing synchronously for id=%s", file_id)
        try:
            # 将解析到的 config 传递给 processing_image
            result = processing_image(file_id, config=config)
            return jsonify({
                "file_id": file_id,
                "filename": final_name,
                "path": str(final_path),
                "job_id": None,
                "result": result
            }), 200
        except Exception as e2:
            current_app.logger.exception("sync processing failed for file_id=%s", file_id)
            return jsonify({"error": "processing failed", "detail": str(e2)}), 500
    
    # 有 executor，异步提交
    try:
        # 优先使用 submit_stored，否则用 submit；传入 config 到 worker
        if hasattr(executor, "submit_stored"):
            future = executor.submit_stored(job_id, _task_wrapper, file_id, job_id, config)
        else:
            future = executor.submit(_task_wrapper, file_id, job_id, config)
        
        try:
            future.add_done_callback(lambda fut, jid=job_id: _task_done_callback(fut, jid))
        except Exception:
            _logger.warning("add_done_callback failed for job_id=%s", job_id)
        
        # 存储为字典结构，包含 future、file_id 与接收到的 config
        _jobs[job_id] = {"future": future, "file_id": file_id, "config": config}
        _logger.info("Submitted processing task, file_id=%s, job_id=%s config=%s", file_id, job_id, str(config))
        
        return jsonify({
            "file_id": file_id,
            "filename": final_name,
            "path": str(final_path),
            "job_id": job_id,
            "task_url": task_url
        }), 202
    except Exception as e:
        current_app.logger.exception("submit task failed for file_id=%s", file_id)
        # 回退同步执行
        try:
            result = processing_image(file_id, config=config)
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
    info = _jobs.get(job_id)
    if info is None:
        _logger.warning("unknown job queried: job_id=%s", job_id)
        return jsonify({"error": "unknown job"}), 404
    
    # 兼容旧格式（直接存 Future）和新格式（字典）
    if isinstance(info, dict):
        fut = info.get("future")
        file_id = info.get("file_id")
    else:
        fut = info
        file_id = None
    
    # 检查 fut 是否为 None（防止类型错误）
    if fut is None:
        _logger.error("future is None for job_id=%s", job_id)
        return jsonify({"error": "invalid job state", "file_id": file_id}), 500
    
    if fut.done():
        try:
            result = fut.result()
        except Exception as e:
            _logger.exception("task finished with exception: job_id=%s err=%s", job_id, e)
            return jsonify({"status": "error", "error": str(e), "file_id": file_id}), 200
        _logger.info("task status done: job_id=%s", job_id)
        return jsonify({"status": "done", "result": result, "file_id": file_id}), 200
    else:
        _logger.info("task status pending: job_id=%s", job_id)
        return jsonify({"status": "pending", "file_id": file_id}), 200