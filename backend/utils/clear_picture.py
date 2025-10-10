from pathlib import Path
import sys

EXTS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.json'}

def delete_path(p: Path):
    if not p.exists():
        print("Not found:", p)
        return
    if p.is_file():
        if p.suffix.lower() in EXTS:
            try:
                p.unlink()
                print("\nDeleted:", p)
            except Exception as e:
                print("Failed to delete:", p, e)
        else:
            print("Skipped (not target ext):", p)
    elif p.is_dir():
        count = 0
        for f in p.rglob('*'):
            if f.is_file() and f.suffix.lower() in EXTS:
                try:
                    f.unlink()
                    count += 1
                    print("Deleted:", f)
                except Exception as e:
                    print("Failed to delete:", f, e)
        print(f"Finished deleting in directory: {p} (deleted {count} files)")
    else:
        print("Skipped (unknown type):", p)

def main():
    repo_root = Path(__file__).resolve().parents[2]
    default_dirs = [
        (repo_root / "backend" / "static" / "results").resolve(),
        (repo_root / "backend" / "static" / "uploads").resolve(),
    ]

    if len(sys.argv) < 2:
        # 无参数时删除默认目录下的目标文件
        for d in default_dirs:
            delete_path(d)
        return

    # 有参数时按路径处理（文件或目录）
    for raw in sys.argv[1:]:
        p = Path(raw)
        try:
            rp = p.resolve()
        except Exception:
            print("Invalid path:", raw)
            continue
        delete_path(rp)

if __name__ == "__main__":
    main()