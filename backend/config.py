from __future__ import annotations
from pathlib import Path
from typing import FrozenSet
import os

class Config:
    """
    统一的路径配置。
    """
    def __init__(self):
        repo_root = Path(__file__).resolve().parents[1]
        backend_dir = repo_root / "backend"
        static_dir = backend_dir / "static"
        models_dir = static_dir / "models"
        results_dir = static_dir / "results"
        uploads_dir = backend_dir / "uploads"
        logs_dir = repo_root / "logs"

        self.PROJECT_ROOT = repo_root
        self.BACKEND_DIR = backend_dir
        self.STATIC_DIR = static_dir
        self.MODELS_DIR = models_dir
        self.RESULTS_DIR = results_dir
        self.UPLOADS_DIR = str(uploads_dir)
        self.LOGS_DIR = str(logs_dir)

        # default subdirs under results
        self.RESULTS_DETECTOR_DIR = str(results_dir / "detector")
        self.RESULTS_EXTRACTOR_DIR = str(results_dir / "extractor")
        self.RESULTS_READER_DIR = str(results_dir / "reader")
        self.RESULTS_NUMBER_DIR = str(results_dir / "number")

        # model defaults
        self.PLATE_MODEL = str(models_dir / "plate_best.pt")
        self.NUMBER_MODEL = str(models_dir / "number_best.pt")

        # detection defaults
        self.DEFAULT_CONF = 0.25
        self.DEFAULT_IMGSZ = 640

        # allowed extensions
        self.ALLOWED_EXTS = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".gif"})

    def ensure_dirs(self) -> None:
        # create directories if not exist
        for p in (
            Path(self.UPLOADS_DIR),
            Path(self.RESULTS_DETECTOR_DIR),
            Path(self.RESULTS_EXTRACTOR_DIR),
            Path(self.RESULTS_READER_DIR),
            Path(self.RESULTS_NUMBER_DIR),
            Path(self.MODELS_DIR),
            Path(self.STATIC_DIR),
            Path(self.LOGS_DIR),
        ):
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception:
                # best-effort, ignore errors here
                pass

# 全局实例
cfg = Config()
cfg.ensure_dirs()

# 兼容导出（保留旧接口，但指向 cfg）
UPLOADS_DIR = cfg.UPLOADS_DIR
PLATE_MODEL = cfg.PLATE_MODEL
RESULTS_DETECTOR_DIR = cfg.RESULTS_DETECTOR_DIR
RESULTS_EXTRACTOR_DIR = cfg.RESULTS_EXTRACTOR_DIR
RESULTS_READER_DIR = cfg.RESULTS_READER_DIR
NUMBER_MODEL = cfg.NUMBER_MODEL
DEFAULT_CONF = cfg.DEFAULT_CONF
DEFAULT_IMGSZ = cfg.DEFAULT_IMGSZ
ALLOWED_EXTS = cfg.ALLOWED_EXTS