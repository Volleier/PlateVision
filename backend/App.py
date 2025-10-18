from flask import Flask
from flask_cors import CORS
from flask_executor import Executor
import os
import logging
import sys
import pathlib

_project_root = pathlib.Path(__file__).resolve().parents[1]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # Limit upload size to 16 MB

    # Initialize logging
    from logger import setup_logging
    setup_logging(app)

    # Initialize error handlers
    from error_handlers import register_error_handlers
    register_error_handlers(app)

    # Allow frontend cross-origin access to /api/* during development
    try:
        CORS(app, resources={r"/api/*": {"origins": "*"}})
    except Exception:
        logging.getLogger("App").warning("CORS not available, skipping")

    # Register blueprints - 使用 package 绝对导入
    from backend.api.receive import bp as receive_bp
    app.register_blueprint(receive_bp)

    from backend.api.send import bp as send_bp
    app.register_blueprint(send_bp)


    # Initialize Executor (thread 模式)
    app.config.setdefault('EXECUTOR_TYPE', 'thread')
    executor = Executor(app)
    setattr(app, "executor", executor)

    # Debug: 打印所有注册的路由
    logger = logging.getLogger("App")
    logger.warning("=== Registered Routes ===")
    for rule in sorted(app.url_map.iter_rules(), key=lambda x: x.rule):
        # rule.methods may be None in some environments, guard against that
        methods = set(rule.methods) if rule.methods is not None else set()
        methods = methods - {'HEAD', 'OPTIONS'}
        methods_str = ','.join(sorted(methods))
        logger.warning("  %s -> %s [%s]", rule.rule, rule.endpoint, methods_str)
    logger.warning("=========================")

    return app

if __name__ == "__main__":
    # 直接运行用于开发调试
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    logging.getLogger("App").warning("Starting app on port %s", port)
    app.run(host="0.0.0.0", port=port, debug=True)