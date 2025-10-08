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

def _preprocess_plate(img, target_width=600):
    """预处理：灰度 -> 双边滤波 -> 自适应阈值 -> 放大 -> 轻度锐化
    提高默认宽度以提升对窄纵向字符的识别率（可按需改回 400 或更高）
    """
    if img is None:
        return None
    # 若彩色，转灰度
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()

    # 去噪
    den = cv2.bilateralFilter(gray, 9, 75, 75)
    # 自适应二值化（参数可调）
    th = cv2.adaptiveThreshold(den, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, 31, 12)
    # 膨胀让字符更连贯
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    morph = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)
    # 调整大小以提高识别率
    h, w = morph.shape
    scale = target_width / float(w) if w > 0 else 1.0
    new_h = max(32, int(h * scale))
    resized = cv2.resize(morph, (target_width, new_h), interpolation=cv2.INTER_LINEAR)
    # 轻度锐化（unsharp mask）
    blurred = cv2.GaussianBlur(resized, (0, 0), sigmaX=1.0)
    sharpen = cv2.addWeighted(resized, 1.5, blurred, -0.5, 0)
    # 将黑底白字转换为白底黑字（符合 OCR 常用输入）
    inverted = cv2.bitwise_not(sharpen)
    return inverted

def _clean_plate_text(raw_text):
    """对 OCR 原始结果做清洗：
    - 保留中文、字母、数字，并大写英文字母
    - 若结果首字符是汉字，则去掉该汉字及其后紧跟的一个英文字母（表示地名的字母）
    """
    if not raw_text:
        return ""
    # 合并多行，去掉空格和常见分隔符
    s = re.sub(r'[\s\|\-_]+', '', raw_text)
    # 只保留中文、英文和数字
    s = ''.join(re.findall(r'[\u4e00-\u9fffA-Za-z0-9]+', s))
    s = s.upper()
    # 若首字符为汉字，则删除该汉字
    if s and re.match(r'^[\u4e00-\u9fff]', s):
        s = s[1:]
        # 若删除汉字后首字符为字母（表示地名），再删除该字母
        if s and re.match(r'^[A-Z]', s):
            s = s[1:]
    return s

def ocr_with_easyocr(img, gpu: bool | None = None):
    """增强版 OCR：
    - 多尺度识别并合并结果（提高对小/模糊字符的鲁棒性）
    - 候选扩展：从 raw 提取子串、用混淆表生成变体、对数字串尝试补前导 D/F
    - 规则优先：新能源(6位且首位 D/F) > 普通(5位)
    """
    if easyocr is None:
        raise RuntimeError("easyocr 未安装")

    # 自动检测 GPU（若用户未指定）
    if gpu is None:
        try:
            import torch
            gpu = bool(torch.cuda.is_available())
        except Exception:
            gpu = False

    # 建立 reader（一次）
    reader = easyocr.Reader(['ch_sim', 'en'], gpu=bool(gpu))

    # 多尺度识别（按不同宽度尝试）
    widths = [400, 600]
    all_results = []
    for w in widths:
        try:
            h0, w0 = img.shape[:2]
            if w0 > 0 and w0 != w:
                scale = w / float(w0)
                nh = max(32, int(h0 * scale))
                scaled = cv2.resize(img, (w, nh), interpolation=cv2.INTER_LINEAR)
            else:
                scaled = img
            res = reader.readtext(scaled, detail=1, paragraph=False)
            if res:
                all_results.extend(res)
        except Exception:
            continue

    if not all_results:
        return "", 0.0

    # 兼容 result 的不同结构
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

    # 去掉首位地名汉字及其后单字母；并保留字母数字
    def _strip_leading_and_keep_alnum(raw: str) -> str:
        if not raw:
            return ""
        s = re.sub(r'[\s\|\-_]+', '', raw)
        if re.match(r'^[\u4e00-\u9fff]', s):
            s = s[1:]
            if s and re.match(r'^[A-Za-z]', s):
                s = s[1:]
        s = ''.join(re.findall(r'[A-Za-z0-9]+', s)).upper()
        return s

    # 从 raw 中提取可能的车牌候选子串并扩展变体
    def _extract_and_expand(raw: str) -> list:
        if not raw:
            return []
        s = re.sub(r'[\s\|\-_]+', '', raw).upper()
        if re.match(r'^[\u4e00-\u9fff]', s):
            s = s[1:]
        subs = set()
        # 常见长度连续字母数字串
        for m in re.finditer(r'[A-Z0-9]{4,6}', s):
            subs.add(m.group(0))
        # 额外宽松匹配
        if not subs:
            for m in re.finditer(r'[A-Z0-9]{3,6}', s):
                subs.add(m.group(0))
        # 混淆替换表（常见视觉混淆）
        confuse = {
            'O': '0', '0': 'O',
            'I': '1', 'L': '1', '1': 'I',
            'Z': '2', '2': 'Z',
            'S': '5', '5': 'S',
            'B': '8', '8': 'B',
            'D': '0'  # 保留但不要滥用
        }
        expanded = set()
        for sub in list(subs):
            expanded.add(sub)
            # 单字符替换生成变体（限制生成量）
            for i, ch in enumerate(sub):
                if ch in confuse:
                    variant = sub[:i] + confuse[ch] + sub[i+1:]
                    expanded.add(variant)
            # 若为纯数字或以数字开头且长度为4或5，尝试补前导 D/F
            if re.match(r'^[0-9]+$', sub) and len(sub) in (4,5):
                for p in ('D', 'F'):
                    expanded.add(p + sub)
            # 若长度为5且以数字起始，尝试补常见首字母（谨慎）
            if len(sub) == 5 and re.match(r'^[0-9]', sub):
                for p in ('D', 'F'):
                    expanded.add(p + sub)
        return list(expanded)

    # 车牌正则（新能源优先）
    new_energy_re = re.compile(r'^[DF][A-Z0-9]{5}$')
    normal_re = re.compile(r'^[A-Z0-9]{5}$')

    # 构建候选集（带置信度）
    candidates = []
    for item in all_results:
        raw = _item_text(item)
        conf = _item_conf(item)
        cleaned = _strip_leading_and_keep_alnum(raw)
        if cleaned:
            candidates.append((cleaned, float(conf)))
        for sub in _extract_and_expand(raw):
            candidates.append((sub, float(conf)))

    if not candidates:
        return "", 0.0

    # 优先选择匹配新能源的最高置信度
    new_matches = [(c, conf) for (c, conf) in candidates if new_energy_re.match(c)]
    if new_matches:
        best_text, best_conf = max(new_matches, key=lambda x: x[1])
        return best_text, float(best_conf)

    # 再选择普通车牌
    normal_matches = [(c, conf) for (c, conf) in candidates if normal_re.match(c)]
    if normal_matches:
        best_text, best_conf = max(normal_matches, key=lambda x: x[1])
        return best_text, float(best_conf)

    # 回退按置信度最高（返回清洗后的文本）
    best_text, best_conf = max(candidates, key=lambda x: x[1])
    # 最终再做一次清洗：去掉前导汉字及地名字母
    final = _strip_leading_and_keep_alnum(best_text)
    return final, float(best_conf)

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