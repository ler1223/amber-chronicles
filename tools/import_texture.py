"""Текстура высокого разрешения (не пиксель-арт) → бесшовная по горизонтали полоса в assets/sprites.

Поверхности шлифовальных дисков для лупы (лист JD промптов):
    python tools/import_texture.py assets/art_src/lap_coarse.png --name lap_tex_coarse
    python tools/import_texture.py assets/art_src/lap_medium.png --name lap_tex_medium
    python tools/import_texture.py assets/art_src/lap_fine.png --name lap_tex_fine
    python tools/import_texture.py assets/art_src/lap_diamond.png --name lap_tex_diamond

Края сшиваются плавным переходом (8% ширины), высота — не больше --height (по умолчанию 512)."""
import argparse
import os
import sys

import numpy as np
import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def seamless(arr, frac=0.08):
    """Полоса без шва: правый край плавно переходит в левый (кусок справа уходит в начало)."""
    h, w, _ = arr.shape
    n = max(2, int(w * frac))
    a = arr[:, :n].astype(float)
    b = arr[:, w - n:].astype(float)
    t = np.linspace(0, 1, n)[None, :, None]
    out = arr[:, :w - n].copy()
    out[:, :n] = (b * (1 - t) + a * t).astype(arr.dtype)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--name", required=True)
    ap.add_argument("--height", type=int, default=512)
    args = ap.parse_args(argv)
    pygame.init()
    img = pygame.image.load(args.src)
    if img.get_height() > args.height:
        img = pygame.transform.smoothscale(img, (img.get_width() * args.height // img.get_height(), args.height))
    arr = pygame.surfarray.array3d(img).swapaxes(0, 1)
    arr = seamless(arr)
    out = pygame.surfarray.make_surface(arr.swapaxes(0, 1))
    path = os.path.join(ROOT, "assets", "sprites", args.name + ".png")
    pygame.image.save(out, path)
    print(f"{path}: {out.get_width()}x{out.get_height()}")


if __name__ == "__main__":
    sys.exit(main())
