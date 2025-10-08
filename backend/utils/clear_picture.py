from pathlib import Path
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python delete_file.py <file1> [file2 ...]")
        return

    repo_root = Path(__file__).resolve().parents[2]
    allowed = {
        (repo_root / "backend" / "static" / "results").resolve(),
        (repo_root / "backend" / "static" / "uploads").resolve(),
    }

    for raw in sys.argv[1:]:
        p = Path(raw)
        try:
            rp = p.resolve()
        except Exception:
            print("Invalid path:", raw)
            continue

        # ensure file is under one of allowed dirs
        allowed_ok = any((rp == base or rp.is_relative_to(base)) if hasattr(rp, "is_relative_to") else (str(rp).startswith(str(base) + "\\" ) or str(rp) == str(base)) for base in allowed)
        if not allowed_ok:
            print("Skipped (not in allowed dirs):", rp)
            continue

        if not rp.exists():
            print("Not found:", rp)
            continue
        if not rp.is_file():
            print("Skipped (not a file):", rp)
            continue
        try:
            rp.unlink()
            print("Deleted:", rp)
        except Exception as e:
            print("Failed to delete:", rp, e)

if __name__ == "__main__":
    main()