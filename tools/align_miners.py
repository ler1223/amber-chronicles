"""После импорта листа MH (--set mine_hd): перерезать кадры горняка с общим масштабом, общей линией земли и
выравниванием по пятке задней ноги — иначе фигура прыгает между кадрами. Запуск: python tools/align_miners.py"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "tools")
import numpy as np
import pygame
import import_sheet as IS

pygame.init()
pygame.display.set_mode((8, 8))
img = pygame.image.load("assets/art_src/sheet_mine_hd.png")
rgb = pygame.surfarray.array3d(img).transpose(1, 0, 2).astype(float)
fg = np.abs(rgb - IS.MAGENTA).sum(-1) > 120
H_, W = fg.shape
surf = pygame.Surface((W, H_), pygame.SRCALPHA)
al = np.zeros((H_, W, 4), np.uint8)
al[..., 3] = fg * 255
surf = pygame.image.frombuffer(al.tobytes(), (W, H_), "RGBA").copy()
comps = pygame.mask.from_surface(surf).connected_components(30)
big = sorted([c for c in comps if c.count() > 5000], key=lambda c: c.get_bounding_rects()[0].x)
print("big", [c.get_bounding_rects()[0] for c in big])
owner = np.zeros((H_, W), int) - 1                 # чей пиксель: мелкие куски (щебень) — ближайшей фигуре
cent = [c.get_bounding_rects()[0].centerx for c in big]
for c in comps:
    r = c.get_bounding_rects()[0]
    k = min(range(len(big)), key=lambda j: abs(cent[j] - r.centerx)) if c.count() <= 5000 else \
        next(j for j, b in enumerate(big) if b is c)
    arr = pygame.surfarray.array2d(c.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))).T != 0
    owner[arr] = k
frames, ys, heels = [], [], []
for j in range(3):
    m = owner == j
    xs_ = np.where(m.any(0))[0]
    y = np.where(m.any(1))[0]
    frames.append((int(xs_.min()), int(xs_.max()) + 1))
    ys.append(y)
top, bot = min(y.min() for y in ys), max(y.max() for y in ys) + 1
for j, ((a, b), y) in enumerate(zip(frames, ys)):
    band = (owner == j)[y.max() - int((bot - top) * 0.06):y.max() + 1]
    heels.append(int(np.where(band.any(0))[0].min()))          # пятка задней ноги
left = max(h - a for (a, b), h in zip(frames, heels))
right = max(b - h for (a, b), h in zip(frames, heels))
cw, ch = left + right, bot - top
K = 320 / ch
for i, ((a, b), h) in enumerate(zip(frames, heels), 1):
    x0 = h - left
    region = np.zeros((ch, cw))
    sub = rgb[top:bot, max(0, x0):x0 + cw]
    m = np.zeros((ch, cw), bool)
    xs = max(0, x0)
    m[:, xs - x0:xs - x0 + sub.shape[1]] = fg[top:bot, xs:xs + sub.shape[1]]
    full = np.full((ch, cw, 3), IS.MAGENTA, float)
    full[:, xs - x0:xs - x0 + sub.shape[1]] = sub
    keep = np.zeros((ch, cw))                                  # только свой кадр (+ мягкий край), без соседей
    own = (owner == i - 1)
    grow = own.copy()
    for _ in range(3):
        grow[1:] |= grow[:-1]; grow[:-1] |= grow[1:]; grow[:, 1:] |= grow[:, :-1]; grow[:, :-1] |= grow[:, 1:]
    keep[:, xs - x0:xs - x0 + sub.shape[1]] = grow[top:bot, xs:xs + sub.shape[1]]
    out = IS.hd_sprite(full, keep, (int(cw * K), 320))
    pygame.image.save(out, f"assets/sprites/mine_miner_{i}.png")
    print(i, out.get_size(), out.get_bounding_rect())
