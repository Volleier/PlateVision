from flask import Flask
from flask_cors import CORS
import os

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # Limit upload size to 16 MB

    # Allow frontend cross-origin access to /api/* during development
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Register upload blueprint
    from api.upload import bp as upload_bp
    app.register_blueprint(upload_bp)

    # 初始化数据库（启动时建表），通过 api 层封装
    try:
        from api import db_api
        db_api.init_db()
        print("DB initialized at startup")
    except Exception as e:
        # 不阻塞应用启动，记录到 stdout 方便调试
        print("DB init failed at startup:", e)

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)