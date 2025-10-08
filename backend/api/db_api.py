import traceback
from typing import List, Dict, Optional, Any

# 更稳健的导入：优先尝试相对导入（当作为包运行时），再尝试绝对导入；失败时保留 None
db_service = None
_import_err = None
try:
    # 相对导入（backend/api 在包内部）
    from ..services import db as db_service  # type: ignore
except Exception as e1:
    _import_err = e1
    try:
        # 绝对导入（在某些运行上下文中可用）
        from services import db as db_service  # type: ignore
    except Exception as e2:
        _import_err = (e1, e2)
        db_service = None

def init_db() -> Dict[str, Any]:
    """初始化数据库（建表），返回状态字典。"""
    if db_service is None:
        return {"status": "error", "message": "db service not available", "import_error": repr(_import_err)}
    try:
        db_service.init_db()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()}

def save_single_plate(image_path: str, crop_path: Optional[str], text: Optional[str], confidence: Optional[float]) -> Dict[str, Any]:
    """
    保存单条识别记录，返回 {"status":"ok","id":...} 或错误信息。
    image_path: 原图路径或名称（可传 uploaded_name）
    crop_path: 裁剪图路径（可为 None）
    """
    if db_service is None:
        return {"status": "error", "message": "db service not available", "import_error": repr(_import_err)}
    try:
        rec_id = db_service.add_plate(image_path=image_path, crop_path=crop_path, text=text, confidence=confidence)
        return {"status": "ok", "id": rec_id}
    except Exception as e:
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()}

def save_ocr_results(uploaded_image_name: str, ocr_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    批量保存 OCR 结果。
    ocr_results: 列表，每项类似 {"path": "...", "text": "...", "conf": 0.9} 或包含 "error" 字段（会被跳过）
    返回 {"status":"ok","ids":[...]} 或错误信息。
    """
    if db_service is None:
        return {"status": "error", "message": "db service not available", "import_error": repr(_import_err)}

    records = []
    for r in ocr_results:
        if not r or "error" in r:
            continue
        records.append({
            "image_path": uploaded_image_name,
            "crop_path": r.get("path"),
            "text": r.get("text"),
            "confidence": r.get("conf")
        })

    if not records:
        return {"status": "ok", "ids": []}

    try:
        ids = db_service.add_plates_bulk(records)
        return {"status": "ok", "ids": ids}
    except Exception as e:
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()}

def list_plates(limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    """查询记录列表，返回 {'status':'ok','items':[...]}"""
    if db_service is None:
        return {"status": "error", "message": "db service not available", "import_error": repr(_import_err)}
    try:
        items = db_service.list_plates(limit=limit, offset=offset)
        return {"status": "ok", "items": items}
    except Exception as e:
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()}

def get_plate(plate_id: int) -> Dict[str, Any]:
    """按 id 查询单条记录。"""
    if db_service is None:
        return {"status": "error", "message": "db service not available", "import_error": repr(_import_err)}
    try:
        item = db_service.get_plate(int(plate_id))
        if item is None:
            return {"status": "error", "message": "not found", "id": plate_id}
        return {"status": "ok", "item": item}
    except Exception as e:
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()}