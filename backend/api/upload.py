from flask import Blueprint, request, jsonify, current_app, url_for
from werkzeug.utils import secure_filename
from pathlib import Path
import os
import tempfile
import time
from uuid import uuid4
from PIL import Image, UnidentifiedImageError
try:
    import ulid
except Exception:
    ulid = None

from backend.config import cfg

bp = Blueprint("upload_api", __name__, url_prefix="/api")

# Default allowed file extensions for image uploads
DEFAULT_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
ALLOWED_EXT = None  

def _get_allowed_ext():
    """
    Retrieve allowed file extensions from Flask config, or use default.
    Caches the result for subsequent calls.
    """
    global ALLOWED_EXT
    if ALLOWED_EXT is None:
        ALLOWED_EXT = set(ext.lower() for ext in current_app.config.get("ALLOWED_EXT", DEFAULT_ALLOWED_EXT))
    return ALLOWED_EXT

def allowed_filename(filename: str) -> bool:
    """
    Check if the file extension of the given filename is allowed.
    """
    ext = os.path.splitext(filename)[1].lower()
    return ext in _get_allowed_ext()

@bp.route("/upload", methods=["POST"])
def upload():
    """
    Upload endpoint:
    - 保存到 cfg.UPLOADS_DIR
    - 使用 file_id (uuid4.hex) 作为文件名（保留扩展名）
    - 返回 JSON 包含 file_id, filename, path
    """
    max_len = current_app.config.get("MAX_CONTENT_LENGTH")
    upload_dir = Path(cfg.UPLOADS_DIR)
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        current_app.logger.exception("create upload dir failed")
        return jsonify({"error": "cannot create upload dir", "detail": str(e)}), 500

    # 取上传文件（支持多个常见字段）
    file = request.files.get("image") or request.files.get("upload") or (next(iter(request.files.values()), None))
    if not file or not getattr(file, "filename", ""):
        return jsonify({"error": "no file uploaded", "received_fields": list(request.files.keys())}), 400

    orig_name = secure_filename(file.filename or "")
    ext = os.path.splitext(orig_name)[1].lower()
    if ext == "":
        return jsonify({"error": "file has no extension"}), 400
    if not allowed_filename(orig_name):
        return jsonify({"error": "file type not allowed", "ext": ext}), 400

    # 生成 id 与最终文件名（只用 id 作为文件名）
    # 优先使用 ULID（可排序、26 字符），若不可用回退到 UUID4 hex
    if ulid is not None:
        file_id = ulid.new().str  # 26-char ULID
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

    # 返回 file_id 供上层 processing 使用
    return jsonify({
        "file_id": file_id,
        "filename": final_name,
        "path": str(final_path)
    }), 200