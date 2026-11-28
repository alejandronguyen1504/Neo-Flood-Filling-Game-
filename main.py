"""Unified entry point for Neo Flood Fill (Desktop Pygame, CLI console, and pygbag WebAssembly)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pygame  # Top-level import required by pygbag's static WASM dependency scanner

# Support both editable/src layout (Desktop) and root-packaged layout (pygbag WASM).
try:
    _SRC_CANDIDATES = (Path.cwd() / "src", Path(__file__).resolve().parent / "src")
except NameError:
    _SRC_CANDIDATES = (Path.cwd() / "src",)

for _candidate in _SRC_CANDIDATES:
    if _candidate.is_dir() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

from neo_flood_fill.visualizer import run_studio  # noqa: E402


async def main() -> None:
    """Run the interactive Pygame studio asynchronously (Desktop & pygbag WASM)."""
    await run_studio()


if "--console" in sys.argv:
    from neo_flood_fill.console_demo import main as _console_main

    _console_main([arg for arg in sys.argv[1:] if arg != "--console"])
    raise SystemExit(0)

asyncio.run(main())
