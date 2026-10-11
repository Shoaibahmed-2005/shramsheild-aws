#!/usr/bin/env python3
"""Prepare step for ShramShield backend.

Copies core/shramshield_core/*.py into backend/src/shramshield_core/
so that the Lambda package contains the shared core logic.
"""

from pathlib import Path
import shutil
import sys


def prepare() -> int:
    backend_dir = Path(__file__).resolve().parent.parent
    repo_root = backend_dir.parent
    core_src = repo_root / "core" / "shramshield_core"
    dest_dir = backend_dir / "src" / "shramshield_core"

    if not core_src.exists() or not (core_src / "wbgt.py").exists():
        print(f"[prepare.py] WARNING: {core_src} missing or wbgt.py not found yet. P1.1 may not be pushed. Skipping copy.")
        return 0

    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    dest_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for py_file in core_src.glob("*.py"):
        shutil.copy2(py_file, dest_dir / py_file.name)
        copied += 1

    print(f"[prepare.py] Copied {copied} .py files from {core_src} to {dest_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(prepare())
