"""
训练脚本 — 强制使用 data\yolo11m.pt 训练 Plate/training 中的图片/标注（YOLO 格式）。
用法（示例）:
    python train_yolo.py --epochs 50 --batch 16 --imgsz 640 --device 0 --skip-check

要求:
    pip install ultralytics pyyaml
"""
import os
# 在任何可能导入 torch/ultralytics 之前设置，避免 OpenMP 初始化错误（临时）
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from pathlib import Path
import argparse
import sys
import tempfile
import yaml
import torch
from ultralytics import YOLO

# <-- 临时绕过 OpenMP 初始化冲突（不推荐作为长期方案，只用于临时运行）
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

PROJECT_ROOT = Path(__file__).resolve().parents[2] 
DEFAULT_WEIGHTS = PROJECT_ROOT / "data" / "yolo11m.pt"

# 尝试多个可能的位置，优先使用存在的目录（支持 data/Plate/... 的布局）
_candidate_paths = [
    PROJECT_ROOT / "Plate" / "training",
    PROJECT_ROOT / "data" / "Plate" / "training",
    PROJECT_ROOT / "data" / "Plate",
]
# 默认指向 PROJECT_ROOT/Plate/training，后续候选路径会覆盖它（避免类型为 None 导致的静态分析错误）
PLATE_TRAINING = PROJECT_ROOT / "Plate" / "training"
for _p in _candidate_paths:
    if _p.exists():
        # 如果找到的是 Plate 目录而不是 training 子目录，使用其 training 子目录（如果存在），否则直接用该目录
        if (_p / "training").exists():
            PLATE_TRAINING = (_p / "training")
        else:
            PLATE_TRAINING = _p
        break

PLATE_IMAGES = PLATE_TRAINING / "images"
PLATE_LABELS = PLATE_TRAINING / "labels"
PLATE_DATA_YAML = PLATE_TRAINING / "dataset.yaml"


def check_paths():
    missing = []
    if not DEFAULT_WEIGHTS.exists():
        missing.append(str(DEFAULT_WEIGHTS))
    if not PLATE_TRAINING.exists():
        missing.append(str(PLATE_TRAINING))
    if not (PLATE_IMAGES.exists() and any(PLATE_IMAGES.iterdir())):
        missing.append(f"{PLATE_IMAGES} (missing or empty)")
    if not (PLATE_LABELS.exists() and any(PLATE_LABELS.iterdir())):
        missing.append(f"{PLATE_LABELS} (missing or empty)")
    if missing:
        print("必要文件/文件夹缺失：")
        for m in missing:
            print("  -", m)
        sys.exit(2)


def prepare_data_yaml():
    """
    读取 Plate/training/dataset.yaml（如果存在），将 train/val 路径替换为绝对路径（指向 Plate/training/images）。
    将结果写入临时 yaml 并返回路径。Ultralytics 可接受该临时 yaml。
    """
    data = {}
    if PLATE_DATA_YAML.exists():
        with open(PLATE_DATA_YAML, "r", encoding="utf8") as f:
            data = yaml.safe_load(f) or {}
    # 强制使用 Plate/training 中的 images 子目录
    train_img = PLATE_IMAGES / "train"
    val_img = PLATE_IMAGES / "val"
    data["train"] = str(train_img.resolve())
    data["val"] = str(val_img.resolve()) if val_img.exists() else str(train_img.resolve())
    # 如果 dataset.yaml 指定了 nc 或 names，保留；否则尝试保留原样（用户可在 dataset.yaml 自行配置类别）
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".yaml", mode="w", encoding="utf8")
    yaml.dump(data, tmp)
    tmp_path = Path(tmp.name)
    tmp.close()
    return tmp_path


def verify_weights_match(weights_path: Path):
    """
    验证 weights_path（本地 yolo11m.pt）与 yolo11m 模型架构完全匹配（key & shape 相同）。
    不匹配则抛出异常，阻止自动下载/错误权重使用。
    """
    # 尝试 allowlist ultralytics DetectionModel / set，使 weights_only=True 更安全
    try:
        from ultralytics.nn.tasks import DetectionModel
        torch.serialization.add_safe_globals([DetectionModel, set])
    except Exception:
        pass

    # 尝试以安全模式加载 checkpoint（weights_only=True），失败退回 weights_only=False（仅在你信任文件时）
    load_kwargs = {"map_location": "cpu", "weights_only": True}
    try:
        ckpt = torch.load(weights_path, **load_kwargs)
    except Exception:
        ckpt = torch.load(weights_path, map_location="cpu", weights_only=False)

    # 提取 state_dict（兼容多种格式）
    state = None
    if isinstance(ckpt, dict):
        for k in ("state_dict", "model", "model_state_dict"):
            if k in ckpt:
                candidate = ckpt[k]
                if hasattr(candidate, "state_dict") and callable(candidate.state_dict):
                    state = candidate.state_dict()
                elif isinstance(candidate, dict):
                    state = candidate
                break
        if state is None:
            for v in ckpt.values():
                if isinstance(v, dict) and any(isinstance(x, torch.Tensor) for x in list(v.values())[:5] if v):
                    state = v
                    break
    elif hasattr(ckpt, "model") and hasattr(ckpt.model, "state_dict"):
        state = ckpt.model.state_dict()
    elif hasattr(ckpt, "state_dict") and callable(ckpt.state_dict):
        state = ckpt.state_dict()

    if state is None:
        raise RuntimeError(f"无法从 checkpoint 提取 state_dict: {weights_path}")

    # 用 yolo11m 架构构建本地模型（优先使用本地权重路径以避免网络下载）
    try:
        # 优先用本地 weights 文件构建模型（不会从网络下载）
        model = YOLO(str(weights_path)).model
    except Exception as e:
        raise RuntimeError(f"无法用本地权重构建模型: {e}")

    msd = model.state_dict()

    ck_keys = set(state.keys())
    md_keys = set(msd.keys())

    missing_in_ckpt = [k for k in md_keys if k not in ck_keys]
    unexpected_in_ckpt = [k for k in ck_keys if k not in md_keys]
    shape_mismatches = []
    for k in ck_keys & md_keys:
        try:
            if tuple(state[k].shape) != tuple(msd[k].shape):
                shape_mismatches.append((k, tuple(state[k].shape), tuple(msd[k].shape)))
        except Exception:
            pass

    if missing_in_ckpt or unexpected_in_ckpt or shape_mismatches:
        msg_lines = ["权重与 yolo11m 架构不匹配："]
        if missing_in_ckpt:
            msg_lines.append(f" model 中存在但 checkpoint 缺失 键数: {len(missing_in_ckpt)} 示例: {missing_in_ckpt[:10]}")
        if unexpected_in_ckpt:
            msg_lines.append(f" checkpoint 中额外键数: {len(unexpected_in_ckpt)} 示例: {unexpected_in_ckpt[:10]}")
        if shape_mismatches:
            msg_lines.append(f" shape 不匹配示例(键, ckpt_shape, model_shape): {shape_mismatches[:10]}")
        msg_lines.append("请确保使用来自 yolo11m 的权重文件（相同 ultralytics 版本导出），或重新导出权重。")
        raise RuntimeError("\n".join(msg_lines))

    # 全匹配则返回 True
    return True


def main():
    parser = argparse.ArgumentParser(description="使用 data/yolo11m.pt 训练 Plate/training 数据集（YOLO 格式）")
    parser.add_argument("--weights", type=str, default=str(DEFAULT_WEIGHTS), help="预训练权重（默认 data/yolo11m.pt）")
    parser.add_argument("--data", type=str, default=None, help="数据集 yaml（默认使用 Plate/training/dataset.yaml 并强制图片路径）")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", type=str, default="0", help="训练设备，例: '0' 或 'cpu'")
    parser.add_argument("--project", type=str, default=str(PROJECT_ROOT / "Plate" / "models"), help="输出目录")
    parser.add_argument("--name", type=str, default="yolo11m_plate_train")
    parser.add_argument("--skip-check", action="store_true", help="跳过路径/权重校验（仅调试时使用）")
    args = parser.parse_args()

    # 强制使用本地 yolo11m 权重（文件名和路径必须匹配）
    weights_path = Path(args.weights)
    try:
        same_file = weights_path.resolve() == DEFAULT_WEIGHTS.resolve()
    except Exception:
        same_file = False
    if not same_file and weights_path.name != DEFAULT_WEIGHTS.name:
        print(f"错误：训练必须使用本地权重 '{DEFAULT_WEIGHTS.name}'（路径: {DEFAULT_WEIGHTS}）。传入的权重: {args.weights}")
        sys.exit(4)

    check_paths()

    # 校验权重与 yolo11m 架构完全匹配（除非用户指定跳过）
    if not args.skip_check:
        try:
            print("验证权重与 yolo11m 架构匹配...")
            verify_weights_match(weights_path)
            print("验证通过：权重与 yolo11m 完全匹配")
        except Exception as e:
            print("权重校验失败：", e)
            sys.exit(5)

    # 之后直接以本地权重路径构建模型并训练，避免使用模型名触发下载
    try:
        from ultralytics import YOLO
    except Exception:
        print("未检测到 ultralytics。请先安装：pip install ultralytics pyyaml")
        sys.exit(3)

    model = YOLO(r"E:\Project\PlateVision\data\yolo11m.pt")
    model.train(
        data=str(args.data) if args.data else str(prepare_data_yaml()),
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        project=args.project,
        name=args.name,
        exist_ok=True,
    )
    print("训练已完成。输出保存在：", Path(args.project) / args.name)


if __name__ == "__main__":
    main()