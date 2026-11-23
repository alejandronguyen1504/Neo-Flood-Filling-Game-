"""Unified entry point for Neo Flood Fill (Desktop Pygame, CLI console, and pygbag WebAssembly)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure ``src/`` is importable both on Desktop and inside pygbag WebAssembly bundles.
_SRC_DIR = Path(__file__).resolve().parent / "src"
if _SRC_DIR.is_dir() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


async def main() -> None:
    """Run the interactive Pygame studio asynchronously (pygbag-compatible)."""
    from neo_flood_fill.visualizer import run_studio

    await run_studio()


def _cli() -> None:
    """Dispatch CLI flags on desktop, or launch the async Pygame studio by default."""
    if "--console" in sys.argv:
        from neo_flood_fill.console_demo import main as console_main

        remaining = [arg for arg in sys.argv[1:] if arg != "--console"]
        console_main(remaining)
        return

    asyncio.run(main())


if __name__ == "__main__":
    _cli()
