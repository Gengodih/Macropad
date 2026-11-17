"""Builds the background renderer library for the app from the pad's own
animation code (native/bgfx.cpp): bgfx.dll on Windows, bgfx.so elsewhere.

    python tools/build_bgfx.py             build for this computer
    python tools/build_bgfx.py --windows   cross-build bgfx.dll on Linux (mingw-w64)
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "native", "bgfx.cpp")
OUT_DIR = os.path.join(ROOT, "app", "macropad_app", "resources")


def main():
    cross = "--windows" in sys.argv
    windows = cross or sys.platform == "win32"
    out = os.path.join(OUT_DIR, "bgfx.dll" if windows else "bgfx.so")
    if cross:
        cxx = shutil.which("x86_64-w64-mingw32-g++")
    else:
        cxx = os.environ.get("CXX") or shutil.which("g++") or shutil.which("clang++")
    if not cxx:
        sys.exit("No C++ compiler found (g++ / mingw-w64).")
    cmd = [cxx, "-O2", "-std=c++17", "-shared", "-o", out, SRC]
    if windows:
        cmd += ["-static", "-static-libgcc", "-static-libstdc++", "-s"]
    else:
        cmd += ["-fPIC", "-fvisibility=hidden"]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    print("built", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
