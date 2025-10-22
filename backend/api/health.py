from flask import Blueprint, jsonify, current_app
import pathlib

bp = Blueprint("health", __name__)

@bp.route("/health", methods=["GET"])
def health():
    """
    返回 JSON:
      - status: "ok" 或 "error"
      - model_loaded: bool（若 static/models 下存在文件则为 True）
      - detail: 错误信息（仅在出错时返回）
    """
    try:
        models_dir = pathlib.Path(current_app.root_path) / "static" / "models"
        model_loaded = False
        if models_dir.exists():
            # 若 models 目录下存在任意文件（递归），认为模型已准备
            model_loaded = any(models_dir.rglob("*.*"))
        return jsonify({"status": "ok", "model_loaded": model_loaded}), 200
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500