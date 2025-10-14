from __future__ import annotations

from pathlib import Path
from typing import FrozenSet

class Config:
    """
    简洁统一的路径配置（基于当前项目结构）。
    直接在项目中通过 `from backend.config import cfg` 使用。
    """

    def __init__(self):
        # 基础路径
        self.REPO_ROOT: Path = Path(__file__).resolve().parents[1]  # e:\Project\PlateVision
        self.BACKEND_DIR: Path = Path(__file__).resolve().parent   # e:\Project\PlateVision\backend
        self.STATIC_DIR: Path = self.BACKEND_DIR / "static"

        # 固定子目录（与当前 repo 结构保持一致）
        self.MODELS_SUB = "models"
        self.RESULTS_SUB = "results"
        self.RESULTS_DETECTOR_SUB = "detector"   
        self.RESULTS_EXTRACTOR_SUB = "extractor"
        self.RESULTS_READER_SUB = "reader"
        self.UPLOADS_SUB = "uploads"
        self.SERVICES_SUB = "services"
        self.UTILS_SUB = "utils"

        # 常用路径（集中在此）
        self.MODELS_DIR: Path = self.STATIC_DIR / self.MODELS_SUB
        self.RESULTS_DIR: Path = self.STATIC_DIR / self.RESULTS_SUB
        self.RESULTS_DETECTOR_DIR: Path = self.RESULTS_DIR / self.RESULTS_DETECTOR_SUB
        self.RESULTS_EXTRACTOR_DIR: Path = self.RESULTS_DIR / self.RESULTS_EXTRACTOR_SUB
        self.RESULTS_READER_DIR: Path = self.RESULTS_DIR / self.RESULTS_READER_SUB
        self.UPLOADS_DIR: Path = self.BACKEND_DIR / self.UPLOADS_SUB  # matches backend/uploads
        self.SERVICES_DIR: Path = self.BACKEND_DIR / self.SERVICES_SUB
        self.UTILS_DIR: Path = self.BACKEND_DIR / self.UTILS_SUB

        # 常用模型文件（存在于 static/models）
        self.PLATE_MODEL: Path = self.MODELS_DIR / "plate_best.pt"
        self.NUMBER_MODEL: Path = self.MODELS_DIR / "number_best.pt"

        # 其它默认配置
        self.DEFAULT_CONF: float = 0.25
        self.DEFAULT_IMGSZ: int = 640
        self.ALLOWED_EXTS: FrozenSet[str] = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"})

    def ensure_dirs(self) -> None:
        """
        创建项目中常用的目录（安全无异常抛出）。
        """
        for p in (
            self.STATIC_DIR,
            self.MODELS_DIR,
            self.RESULTS_DIR,
            self.RESULTS_DETECTOR_DIR,
            self.RESULTS_EXTRACTOR_DIR,
            self.RESULTS_READER_DIR,
            self.UPLOADS_DIR,
        ):
            try:
                Path(p).mkdir(parents=True, exist_ok=True)
            except Exception:
                # 忽略创建失败（调用方可自行检查路径）
                pass

# 全局实例，项目中直接导入使用
cfg = Config()
cfg.ensure_dirs()