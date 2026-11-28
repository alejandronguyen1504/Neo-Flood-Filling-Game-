"""Stage only runtime files and build a lightweight pygbag WebAssembly bundle."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
STAGE_DIR = BUILD_DIR / "neo_flood_fill"
WEB_OUT = BUILD_DIR / "web"


def build_web_bundle() -> Path:
    """Copy minimal pure-Python runtime files and invoke ``pygbag --build``."""
    if STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)
    if WEB_OUT.exists():
        shutil.rmtree(WEB_OUT)

    # Place package directly next to main.py so Emscripten WASM imports work
    # without depending on Path(__file__) or src/ path manipulation.
    stage_pkg = STAGE_DIR / "neo_flood_fill"
    stage_pkg.mkdir(parents=True, exist_ok=True)

    shutil.copy2(ROOT / "main.py", STAGE_DIR / "main.py")
    for py_file in (ROOT / "src" / "neo_flood_fill").glob("*.py"):
        shutil.copy2(py_file, stage_pkg / py_file.name)

    cmd = [
        sys.executable,
        "-m",
        "pygbag",
        "--build",
        "--ume_block",
        "0",
        "--app_name",
        "neo-flood-fill",
        "--title",
        "Neo Flood Fill — Interactive Algorithm Studio",
        str(STAGE_DIR),
    ]
    subprocess.run(cmd, check=True)

    generated_web = STAGE_DIR / "build" / "web"
    if not generated_web.is_dir():
        raise RuntimeError(f"Expected pygbag output directory not found: {generated_web}")

    shutil.copytree(generated_web, WEB_OUT)
    shutil.rmtree(STAGE_DIR)
    return WEB_OUT


if __name__ == "__main__":
    out_path = build_web_bundle()
    print(f"WebAssembly bundle ready at: {out_path}")
