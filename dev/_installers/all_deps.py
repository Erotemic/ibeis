import os
import sys
import pefile
from pathlib import Path

VISITED = set()

def read_imports(pe_path: Path):
    pe = pefile.PE(str(pe_path))
    if not hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
        return []
    names = []
    for entry in pe.DIRECTORY_ENTRY_IMPORT:
        names.append(entry.dll.decode("utf-8", "ignore"))
    return sorted(set(names))

def default_search_dirs(target: Path, extra_dirs):
    dirs = []
    dirs.append(target.parent)
    dirs.extend(extra_dirs)
    # Windows system dirs
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    dirs.append(windir / "System32")
    dirs.append(windir)
    # PATH
    for p in os.environ.get("PATH", "").split(os.pathsep):
        if p:
            dirs.append(Path(p))
    # de-dupe while preserving order
    out = []
    seen = set()
    for d in dirs:
        d = d.resolve()
        if d not in seen and d.exists():
            seen.add(d)
            out.append(d)
    return out

def resolve_dll(name: str, search_dirs):
    # If it’s already an absolute path
    p = Path(name)
    if p.is_file():
        return p.resolve()

    # Try search dirs
    for d in search_dirs:
        cand = d / name
        if cand.is_file():
            return cand.resolve()
    return None

def walk(pe_path: Path, search_dirs, indent=0):
    pe_path = pe_path.resolve()
    key = str(pe_path).lower()
    if key in VISITED:
        return
    VISITED.add(key)

    imports = read_imports(pe_path)
    pad = "  " * indent
    print(f"{pad}{pe_path.name}")
    missing = 0

    for dll in imports:
        hit = resolve_dll(dll, search_dirs)
        if hit is None:
            missing += 1
            print(f"{pad}  MISSING: {dll}")
        else:
            print(f"{pad}  OK: {dll} -> {hit}")
            # Recurse only into non-system DLLs (heuristic)
            if "windows\\system32" not in str(hit).lower():
                try:
                    walk(hit, search_dirs, indent + 1)
                except pefile.PEFormatError:
                    pass

    if missing:
        print(f"{pad}!! {missing} missing dependency(ies) for {pe_path.name}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python dll_deps.py <path-to-dll-or-exe> [extra_search_dir ...]")
        raise SystemExit(2)

    target = Path(sys.argv[1])
    extra = [Path(p) for p in sys.argv[2:]]

    search_dirs = default_search_dirs(target, extra)
    walk(target, search_dirs)
