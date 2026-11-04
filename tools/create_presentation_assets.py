"""Render a recorded demo transcript and a social preview. Requires Pillow."""
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
python = sys.argv[1] if len(sys.argv) > 1 else sys.executable
run = subprocess.run([python, str(ROOT / "examples" / "offline_demo.py")], cwd=ROOT, capture_output=True, text=True, check=True)
(ROOT / "outputs" / "demo-transcript.txt").write_text(run.stdout, encoding="utf-8")
assets = ROOT / "assets"
assets.mkdir(exist_ok=True)
font_path = "C:/Windows/Fonts/consola.ttf" if Path("C:/Windows/Fonts/consola.ttf").exists() else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
font = ImageFont.truetype(font_path, 18)
small = ImageFont.truetype(font_path, 18)
image = Image.new("RGB", (1280, 480), "#111827")
draw = ImageDraw.Draw(image)
draw.text((35, 20), "Recorded command output — rendered transcript (not a screenshot)", font=small, fill="#94a3b8")
draw.multiline_text((35, 75), "$ python examples/offline_demo.py\n" + run.stdout.strip(), font=font, fill="#e2e8f0", spacing=12)
image.save(assets / "demo-transcript.png", optimize=True)
image = Image.new("RGB", (1280, 640), "#111827")
draw = ImageDraw.Draw(image)
title = ImageFont.truetype(font_path, 60)
subtitle = ImageFont.truetype(font_path, 28)
draw.text((80, 130), "AI SKILL ROUTER", font=title, fill="#f8fafc")
draw.text((80, 250), "Evidence-aware routing for scientific tools", font=subtitle, fill="#67e8f9")
draw.text((80, 320), "Inspect eligibility. Compare evidence. Abstain.", font=subtitle, fill="#cbd5e1")
draw.text((80, 500), "Early prototype  |  Offline demo  |  Apache-2.0", font=small, fill="#94a3b8")
image.save(assets / "social-preview.png", optimize=True)
print(run.stdout, end="")
