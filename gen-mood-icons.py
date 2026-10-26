#!/usr/bin/env python3
"""Génère les icônes PWA du Mood Tracker (smiley sur fond arrondi)."""
import os
from PIL import Image, ImageDraw

OUT = os.path.expanduser(os.environ.get("MOOD_STATIC_DIR", "~/.hermes/mood-static"))
os.makedirs(OUT, exist_ok=True)

BG = (10, 132, 255)      # bleu iOS (dark accent)
FACE = (255, 212, 59)    # jaune
INK = (60, 45, 0)


def make(size, padding_ratio=0.0, filename=None):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # fond arrondi
    radius = int(size * 0.22)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BG)
    # visage
    p = int(size * (0.14 + padding_ratio))
    face_box = [p, p, size - p, size - p]
    d.ellipse(face_box, fill=FACE)
    # yeux
    eye_r = int(size * 0.055)
    eye_y = int(size * 0.42)
    for ex in (int(size * 0.36), int(size * 0.64)):
        d.ellipse([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r], fill=INK)
    # sourire (arc épais)
    w = int(size * 0.055)
    d.arc([int(size * 0.30), int(size * 0.40), int(size * 0.70), int(size * 0.74)],
          start=20, end=160, fill=INK, width=w)
    path = os.path.join(OUT, filename or f"icon-{size}.png")
    img.save(path, "PNG")
    return path


for s in (192, 512):
    print("✅", make(s))
# version « maskable » : visage plus petit pour la zone de sécurité
print("✅", make(512, padding_ratio=0.10, filename="icon-maskable-512.png"))
print("✅", make(180, filename="apple-touch-icon.png"))
