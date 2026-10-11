#!/usr/bin/env python3
"""Builds the Lambda dependencies layer for thermofeel 2.3.0.

Uses manylinux2014_x86_64 binary wheels for Python 3.12 so that the layer
works correctly in AWS Lambda regardless of whether it was built on Windows,
macOS, or Linux.
"""

from pathlib import Path
import shutil
import subprocess
import sys


def build_layer() -> int:
    backend_dir = Path(__file__).resolve().parent.parent
    layer_dir = backend_dir / "build" / "layer"
    target_dir = layer_dir / "python"

    print(f"[build_layer.py] Cleaning layer directory: {layer_dir}")
    if layer_dir.exists():
        shutil.rmtree(layer_dir)

    target_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--platform",
        "manylinux2014_x86_64",
        "--python-version",
        "3.12",
        "--implementation",
        "cp",
        "--only-binary=:all:",
        "--target",
        str(target_dir),
        "thermofeel==2.3.0",
    ]

    print(f"[build_layer.py] Running pip install into {target_dir}...")
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        print("[build_layer.py] ERROR during pip install:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        print(result.stdout)
        return result.returncode

    # Clean up __pycache__ and tests folders
    cleaned_caches = 0
    for path in list(target_dir.rglob("__pycache__")):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            cleaned_caches += 1

    for path in list(target_dir.rglob("tests")):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            cleaned_caches += 1

    # Calculate unzipped size
    total_bytes = sum(f.stat().st_size for f in layer_dir.rglob("*") if f.is_file())
    total_mb = total_bytes / (1024 * 1024)

    print(f"[build_layer.py] Cleaned {cleaned_caches} cache/test directories.")
    print(f"[build_layer.py] Unzipped layer size: {total_mb:.2f} MB")

    if total_mb > 200.0:
        print(f"[build_layer.py] ERROR: Layer size ({total_mb:.2f} MB) exceeds 200 MB limit!", file=sys.stderr)
        return 1

    print("[build_layer.py] Layer build completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(build_layer())
