#!/usr/bin/env python3
"""Convenience script to regenerate ascii.svg from assets/profile.jpg.

Usage:
    python generate_ascii.py
    python generate_ascii.py path/to/new_photo.jpg
"""
import os
import sys
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "assets", "profile.jpg")
OUT = os.path.join(HERE, "ascii.svg")
SCRIPT = os.path.join(HERE, "scripts", "make_portrait.py")

cmd = [sys.executable, SCRIPT, PHOTO, OUT, "--crop", "20,140,588,860", "--cols", "92"]
print(f"Running: {' '.join(cmd)}")
res = subprocess.run(cmd)
sys.exit(res.returncode)
