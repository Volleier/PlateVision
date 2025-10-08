import cv2
import numpy as np
import re
import importlib
from typing import TYPE_CHECKING

# 兼容 Pillow 10: 若没有 ANTIALIAS/NEAREST 等旧常量，则从 Resampling 映射
try:
    from PIL import Image as _PILImage
    if not hasattr(_PILImage, "ANTIALIAS") and hasattr(_PILImage, "Resampling"):
        # 使用动态属性设置以避免静态类型检查器将旧常量视为未知属性
        try:
            resampling = getattr(_PILImage, "Resampling")
            setattr(_PILImage, "ANTIALIAS", resampling.LANCZOS)
            setattr(_PILImage, "NEAREST", resampling.NEAREST)
            setattr(_PILImage, "BILINEAR", resampling.BILINEAR)
            setattr(_PILImage, "BICUBIC", resampling.BICUBIC)
        except Exception:
            # 若任何一步失败则安全忽略（仍可在代码其它处处理兼容性）
            pass
except Exception:
    pass

# 仅延迟导入 easyocr
try:
    if TYPE_CHECKING:
        import easyocr  # type: ignore
    easyocr = importlib.import_module('easyocr')
except Exception:
    easyocr = None

def _preprocess_plate(img, target_width=400):
    """预处理：灰度 -> 双边滤波 -> 自适应阈值 -> 放大"""
    if img is None:
        return None
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()
    # 去噪
    den = cv2.bilateralFilter(gray, 9, 75, 75)
    # 自适应二值化
    th = cv2.adaptiveThreshold(den, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, 31, 15)
    # 膨胀让字符更连贯
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    morph = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)
    # 调整大小以提高识别率
    h, w = morph.shape
    scale = target_width / float(w) if w > 0 else 1.0
    new_h = max(32, int(h * scale))
    resized = cv2.resize(morph, (target_width, new_h), interpolation=cv2.INTER_LINEAR)
    # 将黑底白字转换为白底黑字（符合 OCR 常用输入）
    inverted = cv2.bitwise_not(resized)
    return inverted

def _clean_plate_text(raw_text):
    """对 OCR 原始结果做清洗，保留中文、字母、数字，并大写英文字母"""
    if not raw_text:
        return ""
    # 合并多行，去掉空格和常见分隔符
    s = re.sub(r'[\s\|\-_]+', '', raw_text)
    # 只保留中文、英文和数字
    s = ''.join(re.findall(r'[\u4e00-\u9fffA-Za-z0-9]+', s))
    s = s.upper()
    return s

def ocr_with_easyocr(img):
    """使用 EasyOCR 识别。返回 (text, confidence)"""
    if easyocr is None:
        raise RuntimeError("easyocr 未安装。请运行: pip install easyocr")
    reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)  # 根据需要启用 gpu=True
    result = reader.readtext(img, detail=1, paragraph=False)
    if not result:
        return "", 0.0
    # result 可能是序列 (bbox, text, confidence) 或 dict，做兼容提取以避免类型检查错误
    def _item_conf(item):
        try:
            if isinstance(item, (list, tuple)):
                return float(item[2]) if len(item) > 2 else 0.0
            if isinstance(item, dict):
                for k in ('confidence', 'conf'):
                    if k in item:
                        return float(item[k])
        except Exception:
            pass
        return 0.0

    def _item_text(item):
        try:
            if isinstance(item, (list, tuple)) and len(item) > 1:
                return item[1]
            if isinstance(item, dict):
                for k in ('text', 'label'):
                    if k in item:
                        return item[k]
        except Exception:
            pass
        return ""

    best = max(result, key=_item_conf)
    text = _clean_plate_text(_item_text(best))
    conf = _item_conf(best)
    return text, conf

def recognize_plate_from_path(image_path, engine='easyocr'):
    """主函数：给定裁剪好的车牌图片路径，返回识别结果与置信度
    """
    img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"无法读取图片: {image_path}")
    pre = _preprocess_plate(img)
    if engine != 'easyocr':
        raise ValueError("当前只支持 engine='easyocr'。若需其它方案请告诉我。")
    text, conf = ocr_with_easyocr(pre)
    return text, conf