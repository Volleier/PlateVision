import os
# Temporary workaround: set before importing libraries that may trigger OpenMP (not recommended long-term)
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from typing import Optional
import traceback

try:
    from ultralytics import YOLO
except Exception as e:
    print("Please install ultralytics: pip install ultralytics. Error:", e)
    raise

def detect_all(conf: float = 0.25, imgsz: int = 640, results_dir: Optional[Path] = None, input_path: Optional[Path] = None):
    try:
        repo_root = Path(__file__).resolve().parents[2]  # e:\Project\PlateVision
        static_dir = repo_root / "backend" / "static"
        model_path = static_dir / "models" / "number_best.pt"
        crops_dir = static_dir / "results" / "crops"

        # 默认输出目录
        results_dir = Path(results_dir) if results_dir else static_dir / "results" / "number_detect"


        if not model_path.exists():
            return

        results_dir.mkdir(parents=True, exist_ok=True)
        if input_path:
            input_path = Path(input_path)

        # Load model
        try:
            model = YOLO(str(model_path))
        except Exception as e:
            traceback.print_exc()
            return

        exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
        if input_path:
            if not input_path.exists() or input_path.suffix.lower() not in exts:
                return
            imgs = [input_path]
        else:
            if not crops_dir.exists():
                return
            imgs = sorted([p for p in crops_dir.iterdir() if p.suffix.lower() in exts and p.is_file()])
            if not imgs:
                return

        for img_path in imgs:
            try:
                res_list = model.predict(source=str(img_path), conf=conf, imgsz=imgsz, verbose=False)
                res = res_list[0] if isinstance(res_list, (list, tuple)) and len(res_list) > 0 else res_list

                # 默认由 PIL 绘制经过阈值过滤后的检测，避免 res.plot() 显示低置信度框
                detections = []
                try:
                    boxes = getattr(res, "boxes", None)
                    names = getattr(res, "names", None) or getattr(model, "names", {}) or {}
                    if boxes is not None and hasattr(boxes, "xyxy"):
                        xyxy = boxes.xyxy.cpu().numpy()
                        confs = getattr(boxes, "conf", None)
                        clss = getattr(boxes, "cls", None)
                        confs_arr = confs.cpu().numpy() if confs is not None else [0.0] * len(xyxy)
                        clss_arr = clss.cpu().numpy() if clss is not None else [0] * len(xyxy)

                        # 强制阈值：去除所有置信度低于 0.33 的检测（即 <33% 的一律忽略）
                        MIN_KEEP_CONF = 0.33

                        for i, b in enumerate(xyxy):
                            conf_val = float(confs_arr[i]) if i < len(confs_arr) else 0.0
                            if conf_val < MIN_KEEP_CONF:
                                # 跳过置信度过低的检测
                                continue
                            xmin, ymin, xmax, ymax = b.tolist()
                            cls_id = int(clss_arr[i]) if i < len(clss_arr) else 0
                            detections.append({
                                "xmin": float(xmin), "ymin": float(ymin),
                                "xmax": float(xmax), "ymax": float(ymax),
                                "confidence": conf_val,
                                "class": cls_id,
                                "name": str(names.get(cls_id, cls_id))
                            })
                except Exception:
                    pass

                # 使用 PIL 在原图上只绘制经过 MIN_KEEP_CONF 过滤后的框
                try:
                    pil_img = Image.open(img_path).convert("RGB")
                    draw = ImageDraw.Draw(pil_img)
                    try:
                        font = ImageFont.load_default()
                    except Exception:
                        font = None

                    for det in detections:
                        xmin, ymin, xmax, ymax = det["xmin"], det["ymin"], det["xmax"], det["ymax"]
                        conf_val = det.get("confidence", 0.0)
                        name = det.get("name", "")
                        # 绘制矩形和文本背景
                        draw.rectangle([xmin, ymin, xmax, ymax], outline="red", width=2)
                        text = f"{name} {conf_val:.2f}"
                        if font is not None:
                            try:
                                # PIL >= 8.0.0
                                bbox = draw.textbbox((0, 0), text, font=font)
                                text_size = (bbox[2] - bbox[0], bbox[3] - bbox[1])
                            except AttributeError:
                                # Fallback for older PIL
                                bbox = font.getbbox(text)
                                text_size = (bbox[2] - bbox[0], bbox[3] - bbox[1])
                        else:
                            text_size = (len(text) * 6, 10)
                        text_x0 = xmin
                        text_y0 = max(0, ymin - text_size[1] - 2)
                        text_bg = [text_x0, text_y0, text_x0 + text_size[0] + 4, text_y0 + text_size[1] + 2]
                        draw.rectangle(text_bg, fill="black")
                        draw.text((text_x0 + 2, text_y0 + 1), text, fill="white", font=font)

                    arr = np.asarray(pil_img)
                except Exception:
                    # 回退：尝试使用 res.plot() （可能包含低置信度框），若不可用则使用原图
                    try:
                        plot_fn = getattr(res, "plot", None)
                        rendered = plot_fn() if callable(plot_fn) else None
                    except Exception:
                        rendered = None
                    if rendered is None:
                        arr = np.array(Image.open(img_path).convert("RGB"))
                    else:
                        arr = np.asarray(rendered)

                out_img_path = results_dir / f"{img_path.stem}_pred{img_path.suffix}"
                Image.fromarray(arr).save(out_img_path)

                out_json_path = results_dir / f"{img_path.stem}.json"
                with open(out_json_path, "w", encoding="utf-8") as f:
                    json.dump({"image": img_path.name, "detections": detections}, f, ensure_ascii=False, indent=2)

                print("Saved:", out_img_path.name, out_json_path.name)

            except Exception as e:
                traceback.print_exc()

        print("All done. Number detector results saved in:", results_dir)
    except Exception as e:
        traceback.print_exc()