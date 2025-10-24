import os
import sys
import pathlib
from flask import Flask
from flask_cors import CORS
from flask_executor import Executor

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
        app.logger.warning("CORS not available, skipping")

    # Register blueprints - 浣跨敤 package 缁濆�瑰�煎叆
    from backend.api.receive import bp as receive_bp
    app.register_blueprint(receive_bp)

    from backend.api.send import bp as send_bp
    app.register_blueprint(send_bp)

    # Register health check blueprint
    try:
        from backend.api.health import bp as health_bp
        app.register_blueprint(health_bp)
    except Exception:
        app.logger.warning("Health blueprint not available, skipping")


    # Initialize Executor (thread 妯″紡)
    app.config.setdefault('EXECUTOR_TYPE', 'thread')
    executor = Executor(app)
    setattr(app, "executor", executor)

    # Debug: print all register router
    logger = app.logger
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
    # 鐩存帴杩愯�岀敤浜庡紑鍙戣皟璇�
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.logger.warning("Starting app on port %s", port)
    app.run(host="0.0.0.0", port=port, debug=True)