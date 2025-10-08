import os
from typing import List, Optional, Dict, Any

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.sql import func

# 配置（可通过环境变量覆盖）
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./backend/static/data/platevision.db")

# 确保 sqlite 文件目录存在（Windows 兼容）
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

# create_engine 参数
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

# 简单 ORM 模型：plates 表
class PlateRecord(Base):
    __tablename__ = "plates"
    id = Column(Integer, primary_key=True, index=True)
    image_path = Column(String, nullable=False)   # 原图路径或名称
    crop_path = Column(String, nullable=True)     # 裁剪图路径
    text = Column(String, nullable=True)          # OCR 结果
    confidence = Column(Float, nullable=True)     # 置信度
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 初始化（建表）
def init_db() -> None:
    """创建表（若不存在）。应用启动时或首次使用时调用。"""
    Base.metadata.create_all(bind=engine)

# 上下文管理的会话获取器（方便在函数里使用）
def _get_session() -> Session:
    return SessionLocal()

# 插入一条记录
def add_plate(image_path: str, crop_path: Optional[str] = None,
              text: Optional[str] = None, confidence: Optional[float] = None) -> int:
    """
    保存一条车牌识别记录，返回新记录的 id。
    """
    init_db()
    session = _get_session()
    try:
        rec = PlateRecord(
            image_path=str(image_path),
            crop_path=str(crop_path) if crop_path else None,
            text=str(text) if text else None,
            confidence=float(confidence) if confidence is not None else None
        )
        session.add(rec)
        session.commit()
        session.refresh(rec)
        return int(rec.id)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# 批量插入（接收 list of dict）
def add_plates_bulk(records: List[Dict[str, Any]]) -> List[int]:
    """
    批量插入，records 是包含 image_path/crop_path/text/confidence 的字典列表，返回 id 列表。
    """
    init_db()
    session = _get_session()
    ids: List[int] = []
    try:
        objs = []
        for r in records:
            objs.append(PlateRecord(
                image_path=str(r.get("image_path", "")),
                crop_path=str(r.get("crop_path")) if r.get("crop_path") else None,
                text=str(r.get("text")) if r.get("text") else None,
                confidence=float(r.get("confidence")) if r.get("confidence") is not None else None
            ))
        session.add_all(objs)
        session.commit()
        for o in objs:
            session.refresh(o)
            ids.append(int(o.id))
        return ids
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# 查询列表
def list_plates(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    返回最近的记录（按 id 降序），以 dict 列表形式返回。
    """
    init_db()
    session = _get_session()
    try:
        q = session.query(PlateRecord).order_by(PlateRecord.id.desc()).limit(limit).offset(offset)
        out = []
        for r in q.all():
            out.append({
                "id": int(r.id),
                "image_path": r.image_path,
                "crop_path": r.crop_path,
                "text": r.text,
                "confidence": float(r.confidence) if r.confidence is not None else None,
                "created_at": r.created_at.isoformat() if r.created_at is not None else None
            })
        return out
    finally:
        session.close()

# 根据 id 查询
def get_plate(plate_id: int) -> Optional[Dict[str, Any]]:
    init_db()
    session = _get_session()
    try:
        r = session.get(PlateRecord, int(plate_id))
        if not r:
            return None
        return {
            "id": int(r.id),
            "image_path": r.image_path,
            "crop_path": r.crop_path,
            "text": r.text,
            "confidence": float(r.confidence) if r.confidence is not None else None,
            "created_at": r.created_at.isoformat() if r.created_at is not None else None
        }
    finally:
        session.close()