"""Stage runtime files, build pygbag WebAssembly bundle, and apply Prior Labs web shell."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
STAGE_DIR = BUILD_DIR / "neo_flood_fill"
WEB_OUT = BUILD_DIR / "web"

PRIOR_LABS_STYLE = """
<!-- Prior Labs Minimalist Monochrome Web Shell -->
<style>
  html, body {
    background-color: #f7f8fa !important;
    background-image: radial-gradient(#d5dbe7 1px, transparent 1px) !important;
    background-size: 18px 18px !important;
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    color: #0b0e17 !important;
    margin: 0;
    padding: 0;
    overflow: hidden;
  }
  canvas.emscripten {
    border: 0 !important;
    border-radius: 14px !important;
    box-shadow:
      0 26px 70px rgba(11, 14, 23, 0.16),
      0 4px 16px rgba(11, 14, 23, 0.06),
      0 0 0 1px rgba(11, 14, 23, 0.09) !important;
  }
  #crt, #system, #box, #pyconsole {
    display: none !important;
  }
  #transfer {
    position: fixed !important;
    top: 50% !important;
    left: 50% !important;
    transform: translate(-50%, -50%) !important;
    background: #ffffff !important;
    border: 1px solid #e2e5ec !important;
    border-radius: 16px !important;
    padding: 24px 32px !important;
    box-shadow: 0 20px 50px rgba(11, 14, 23, 0.08) !important;
    z-index: 999 !important;
    min-width: 280px;
    text-align: center !important;
  }
  #status {
    font-size: 13px !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    color: #0b0e17 !important;
    margin-bottom: 12px !important;
  }
  progress {
    width: 240px !important;
    height: 6px !important;
    border: none !important;
    border-radius: 999px !important;
    background: #eef1f7 !important;
    accent-color: #11153a !important;
    overflow: hidden;
  }
  progress::-webkit-progress-bar {
    background-color: #eef1f7;
    border-radius: 999px;
  }
  progress::-webkit-progress-value {
    background-color: #11153a;
    border-radius: 999px;
  }
  .nff-floating-badge {
    position: fixed;
    bottom: 14px;
    right: 18px;
    z-index: 50;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(8px);
    border: 1px solid #dce1ec;
    box-shadow: 0 4px 14px rgba(11, 14, 23, 0.06);
    color: #0b0e17;
    font-size: 12px;
    font-weight: 600;
    text-decoration: none;
    transition: transform 0.18s ease, background 0.18s ease, border-color 0.18s ease;
  }
  .nff-floating-badge:hover {
    background: #11153a;
    border-color: #11153a;
    color: #ffffff;
    transform: translateY(-1px);
  }
  @media (max-height: 760px) {
    .nff-floating-badge { display: none; }
  }
</style>
"""

PRIOR_LABS_BADGE = """
<a class="nff-floating-badge" href="https://github.com/alejandronguyen1504/Neo-Flood-Filling-Game-" target="_blank" rel="noopener">
  <span>Neo Flood Fill · GitHub</span>
  <span>&rarr;</span>
</a>
"""


def _inject_prior_labs_shell(index_path: Path) -> None:
    """Enhance pygbag's generated index.html with a clean monochrome shell."""
    if not index_path.is_file():
        return
    html = index_path.read_text(encoding="utf-8")
    if "Prior Labs Minimalist Monochrome Web Shell" in html:
        return
    if "</head>" in html:
        html = html.replace("</head>", f"{PRIOR_LABS_STYLE}\n</head>", 1)
    if "</body>" in html:
        html = html.replace("</body>", f"{PRIOR_LABS_BADGE}\n</body>", 1)
    index_path.write_text(html, encoding="utf-8")


def build_web_bundle() -> Path:
    """Copy minimal pure-Python runtime files and invoke ``pygbag --build``."""
    if STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)
    if WEB_OUT.exists():
        shutil.rmtree(WEB_OUT)

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
        "Neo Flood Fill — Minimalist Algorithm Studio",
        str(STAGE_DIR),
    ]
    subprocess.run(cmd, check=True)

    generated_web = STAGE_DIR / "build" / "web"
    if not generated_web.is_dir():
        raise RuntimeError(f"Expected pygbag output directory not found: {generated_web}")

    shutil.copytree(generated_web, WEB_OUT)
    shutil.rmtree(STAGE_DIR)
    _inject_prior_labs_shell(WEB_OUT / "index.html")
    return WEB_OUT


if __name__ == "__main__":
    out_path = build_web_bundle()
    print(f"WebAssembly bundle ready at: {out_path}")
