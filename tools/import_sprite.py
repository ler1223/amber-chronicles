"""Картинка из генератора (ChatGPT/DALL·E: «пиксель-арт 32×32, увеличенный в 16 раз») → спрайт игры.

  python tools/import_sprite.py картинка.png assets/sprites/warrior.png [размер=32]

Что делает: убирает фон (цвет углов — обычно пурпурный #FF00FF), находит сетку крупных пикселей (размер клетки —
по длинам одноцветных отрезков), берёт цвет из середины каждой клетки (без размытия), урезает палитру до 16
цветов, обрезает пустые поля и ставит персонажа ногами на нижний ряд, по центру холста размер×размер.
"""
import sys
from collections import Counter

import numpy as np
import pygame


def cell_size(a):
    """Размер крупного пикселя: самая частая длина одноцветного отрезка в строках и столбцах (не меньше 2)."""
    runs = Counter()
    for arr in (a, a.transpose(1, 0, 2)):
        for row in arr[::7]:
            diff = np.any(np.abs(np.diff(row.astype(int), axis=0)) > 18, axis=1)
            edges = np.flatnonzero(diff)
            lens = np.diff(edges)
            runs.update(int(x) for x in lens if 2 <= x <= 64)
    if not runs:
        return 1
    best = max(runs.items(), key=lambda kv: kv[1] * (1 + 0.15 * kv[0]))[0]
    return max(1, best)


def convert(src, dst, size=32, colors=16):
    pygame.init()
    img = pygame.image.load(src)
    a = pygame.surfarray.array3d(img).transpose(1, 0, 2)              # [y, x, rgb]
    corners = np.array([a[0, 0], a[0, -1], a[-1, 0], a[-1, -1]], int)
    bg = np.median(corners, axis=0)
    cs = cell_size(a)
    h, w = a.shape[0] // cs, a.shape[1] // cs
    ys = (np.arange(h) * cs + cs // 2).clip(0, a.shape[0] - 1)
    xs = (np.arange(w) * cs + cs // 2).clip(0, a.shape[1] - 1)
    small = a[ys][:, xs].astype(int)
    alpha = np.abs(small - bg).sum(-1) > 60                              # фон — прозрачный
    if not alpha.any():
        raise SystemExit("не нашлось персонажа: фон и рисунок одного цвета?")
    pix = small[alpha]
    q = (pix // 12) * 12                                                 # палитра: частые цвета, остальные — к ближайшему
    common = [np.array(c) for c, _ in Counter(map(tuple, q)).most_common(colors)]
    pal = np.array(common)
    idx = np.argmin(((pix[:, None, :] - pal[None]) ** 2).sum(-1), 1)
    small[alpha] = pal[idx]
    yy, xx = np.nonzero(alpha)
    crop = small[yy.min():yy.max() + 1, xx.min():xx.max() + 1]
    cal = alpha[yy.min():yy.max() + 1, xx.min():xx.max() + 1]
    ch, cw = crop.shape[:2]
    if ch > size or cw > size:
        k = size / max(ch, cw)
        ny, nx = (np.arange(int(ch * k)) / k).astype(int), (np.arange(int(cw * k)) / k).astype(int)
        crop, cal = crop[ny][:, nx], cal[ny][:, nx]
        ch, cw = crop.shape[:2]
    out = np.zeros((size, size, 4), np.uint8)
    y0, x0 = size - ch, (size - cw) // 2                                 # ноги — на нижний ряд, по центру
    out[y0:, x0:x0 + cw, :3] = crop
    out[y0:, x0:x0 + cw, 3] = cal * 255
    surf = pygame.image.frombuffer(np.ascontiguousarray(out).tobytes(), (size, size), "RGBA")
    pygame.image.save(surf, dst)
    print(f"{dst}: клетка {cs}px, сетка {w}x{h}, рисунок {cw}x{ch}, палитра {len(pal)}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(1)
    convert(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 32)
