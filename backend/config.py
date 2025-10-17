from __future__ import annotations
from pathlib import Path
import os

class Config:
    def __init__(self):
        repo_root = Path(__file__).resolve().parents[1]  # e:\Project\PlateVision
        backend_dir = repo_root / "backend"
        static_dir = backend_dir / "static"
        models_dir = static_dir / "models"
        results_dir = static_dir / "results"
        uploads_dir = static_dir / "uploads"
        logs_dir = repo_root / "logs"

        self.PROJECT_ROOT = str(repo_root)
        self.BACKEND_DIR = str(backend_dir)
        self.STATIC_DIR = str(static_dir)
        self.MODELS_DIR = str(models_dir)
        self.RESULTS_DIR = str(results_dir)
        self.UPLOADS_DIR = str(uploads_dir)
        self.LOGS_DIR = str(logs_dir)

        # 结果子目录
        self.RESULTS_DETECTOR_DIR = str(results_dir / "detector")
        self.RESULTS_EXTRACTOR_DIR = str(results_dir / "extractor")
        self.RESULTS_READER_DIR = str(results_dir / "reader")

        # 模型默认路径
        self.PLATE_MODEL = str(models_dir / "plate_best.pt")
        self.NUMBER_MODEL = str(models_dir / "number_best.pt")

        # 检测默认参数
        self.DEFAULT_CONF = 0.25
        self.DEFAULT_IMGSZ = 640

        # 允许的扩展名
        self.ALLOWED_EXTS = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".gif"})

    def ensure_dirs(self):
        # 确保关键目录存在
        paths = [
            Path(self.UPLOADS_DIR),
            Path(self.RESULTS_DETECTOR_DIR),
            Path(self.RESULTS_EXTRACTOR_DIR),
            Path(self.RESULTS_READER_DIR),
            Path(self.MODELS_DIR),
            Path(self.STATIC_DIR),
            Path(self.LOGS_DIR),
        ]
        for p in paths:
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception:
                # 忽略创建失败（启动时会记录）
                pass

# 全局实例
cfg = Config()
cfg.ensure_dirs()

# 兼容导出（已移除 RESULTS_CROPS_DIR / RESULTS_NUMBER_DIR 导出）
UPLOADS_DIR = cfg.UPLOADS_DIR
PLATE_MODEL = cfg.PLATE_MODEL
RESULTS_DETECTOR_DIR = cfg.RESULTS_DETECTOR_DIR
RESULTS_EXTRACTOR_DIR = cfg.RESULTS_EXTRACTOR_DIR
RESULTS_READER_DIR = cfg.RESULTS_READER_DIR
NUMBER_MODEL = cfg.NUMBER_MODEL
DEFAULT_CONF = cfg.DEFAULT_CONF
DEFAULT_IMGSZ = cfg.DEFAULT_IMGSZ
ALLOWED_EXTS = cfg.ALLOWED_EXTS