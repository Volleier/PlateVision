"""
数据库功能已移除。该模块保留为兼容导入的占位符，所有操作均返回带有 "disabled" 的响应。
"""

from typing import List, Dict, Optional, Any

def init_db() -> Dict[str, Any]:
    return {"status": "disabled", "message": "database functionality has been removed"}

def save_single_plate(image_path: str, crop_path: Optional[str], text: Optional[str], confidence: Optional[float]) -> Dict[str, Any]:
    return {"status": "disabled", "message": "database functionality has been removed"}

def save_ocr_results(uploaded_image_name: str, ocr_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"status": "disabled", "message": "database functionality has been removed"}

def list_plates(limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    return {"status": "disabled", "message": "database functionality has been removed"}

def get_plate(plate_id: int) -> Dict[str, Any]:
    return {"status": "disabled", "message": "database functionality has been removed"}