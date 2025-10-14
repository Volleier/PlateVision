import os
import time
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(app, logs_dir=None):
    """
    将日志文件放在项目根目录的 logs 文件夹，每次运行生成新文件：
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    logs_dir = logs_dir or os.path.join(project_root, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(logs_dir, f"app_{timestamp}_{os.getpid()}.log")

    fmt = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    formatter = logging.Formatter(fmt)

    file_handler = RotatingFileHandler(filename, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG if getattr(app, "debug", False) else logging.INFO)

    # 清理默认 handlers（避免重复记录）
    for h in list(app.logger.handlers):
        app.logger.removeHandler(h)

    app.logger.setLevel(logging.DEBUG if getattr(app, "debug", False) else logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)

    # 让 werkzeug 使用相同的 handler 与级别
    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.handlers = app.logger.handlers
    werkzeug_logger.setLevel(app.logger.level)

    app.logger.info("Logging configured. Log file: %s", filename)
    return filename