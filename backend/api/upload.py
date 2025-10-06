from flask import Blueprint, request, jsonify, current_app, url_for
from werkzeug.utils import secure_filename
import os
import time

bp = Blueprint("upload_api", __name__, url_prefix="/api")

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}

def allowed_filename(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXT

@bp.route("/upload", methods=["POST"])
def upload():
    # Support "image", "upload", or use the first file field found
    file = None
    if "image" in request.files:
        file = request.files["image"]
    elif "upload" in request.files:
        file = request.files["upload"]
    else:
        files = list(request.files.values())
        if files:
            file = files[0]

    if not file or file.filename == "":
        # Return the received field names for debugging
        return jsonify({"error": "no file uploaded", "received_fields": list(request.files.keys())}), 400

    filename = secure_filename(file.filename or "")
    if not allowed_filename(filename):
        return jsonify({"error": "file type not allowed", "ext": os.path.splitext(filename)[1].lower()}), 400

    upload_dir = os.path.join(current_app.root_path, "static", "uploads")
    try:
        os.makedirs(upload_dir, exist_ok=True)
    except Exception as e:
        current_app.logger.exception("mkdir failed")
        return jsonify({"error": "cannot create upload dir", "detail": str(e)}), 500

    save_path = os.path.join(upload_dir, filename)
    if os.path.exists(save_path):
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{int(time.time())}{ext}"
        save_path = os.path.join(upload_dir, filename)

    try:
        file.save(save_path)
        current_app.logger.info("Saved upload to %s", save_path)
    except Exception as e:
        current_app.logger.exception("save failed")
        return jsonify({"error": "save failed", "detail": str(e)}), 500

    file_url = url_for("static", filename=f"uploads/{filename}", _external=True)

    try:
        from .processing import processing_image
        result = processing_image(save_path)
    except Exception as e:
        current_app.logger.exception("detection failed")
        return jsonify({
            "filename": filename,
            "url": file_url,
            "detection": None,
            "error": "detection failed",
            "detail": str(e)
        }), 500

    return jsonify({
        "filename": filename,
        "url": file_url,
        "detection": result
    }), 200