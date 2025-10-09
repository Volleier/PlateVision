"""
静态检查 backend 下 .py 文件的 import 语句，并尝试解析每个导入的模块是否在当前 Python 环境可用。
不直接 import 后端模块（避免执行顶级代码），对外部包使用 importlib.util.find_spec() 检查可用性。
对相对导入会标注为“相对导入 - 请手动确认”。
"""
import ast
import os
import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # backend 的上一级（项目根）
BACKEND = ROOT / "backend"

def collect_py_files(root: Path):
    for p in root.rglob("*.py"):
        if p.name == "__init__.py":
            continue
        yield p

def parse_imports(file_path: Path):
    with file_path.open("r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=str(file_path))
        except SyntaxError as e:
            return {"__syntax_error__": str(e)}
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(("import", alias.name))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module  # 可能为 None（如 from . import x）
            level = node.level  # 相对导入等级，0 表示非相对
            imports.append(("from", (mod, level)))
    return imports

def check_spec(name: str):
    try:
        spec = importlib.util.find_spec(name)
        return spec is not None
    except Exception:
        return False

def main():
    print(f"Project root: {ROOT}")
    # 确保项目根在 sys.path，用于解析包内绝对导入（若有）
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    problems = []
    for py in collect_py_files(BACKEND):
        imports = parse_imports(py)
        print("="*80)
        print(f"File: {py.relative_to(ROOT)}")
        if isinstance(imports, dict) and "__syntax_error__" in imports:
            print("  SYNTAX ERROR:", imports["__syntax_error__"])
            problems.append((py, "syntax", imports["__syntax_error__"]))
            continue
        if not imports:
            print("  no imports found")
            continue
        for itype, val in imports:
            if itype == "import":
                name = val.split(".")[0]  # 仅检测顶级包是否存在
                ok = check_spec(name)
                status = "OK" if ok else "MISSING"
                print(f"  import {val:<40} -> {status}")
                if not ok:
                    problems.append((py, "missing", val))
            else:  # from
                mod, level = val
                # level 应为 int，但为了安全起见在比较前进行类型检查，避免与 str 或 Unknown 比较
                if isinstance(level, int) and level > 0:
                    # 相对导入：无法静态解析成全局模块名，提醒手动确认
                    rel = '.' * level + (mod or '')
                    print(f"  from {rel:<38} -> RELATIVE IMPORT (manual check)")
                    continue
                if not mod:
                    print(f"  from {mod:<40} -> UNKNOWN (manual check)")
                    continue
                name = mod.split(".")[0]
                ok = check_spec(name)
                status = "OK" if ok else "MISSING"
                print(f"  from {mod:<40} -> {status}")
                if not ok:
                    problems.append((py, "missing", mod))
    print("="*80)
    if not problems:
        print("No missing external modules detected by static check.")
    else:
        print("Problems found (files + missing imports):")
        for item in problems:
            print(" ", item[0].relative_to(ROOT), item[1], item[2])
    print("Note: relative imports are listed as RELATIVE IMPORT and need manual verification.")
    print("Tip: run 'python -m pip install -r requirements.txt' before re-checking to ensure external deps installed.")

if __name__ == "__main__":
    main()