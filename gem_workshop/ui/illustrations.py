"""Иллюстрации экспедиции: события, акты, таверна, лагерь, торговец, итоги.

Картинка — assets/illustrations/<id>.png (пиксель-арт 192×128, в игре ×2.5 = 480×320; нарезка листов —
tools/import_illustrations.py, промпты — art_prompts.md). Пока картинки нет — рисуем заглушку: пиксельную
виньетку болота (небо, луна, деревья, вода, камыши), у каждого id свой вариант.
"""
import math
import os
import random

import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "assets", "illustrations")
W, H = 192, 128
_cache = {}

MOODS = {"short": ((22, 40, 44), (60, 90, 80)), "scene": ((18, 24, 44), (70, 70, 110)),
         "thread": ((40, 26, 18), (150, 100, 50)), "companion": ((20, 36, 30), (80, 130, 90)),
         "act": ((16, 22, 20), (80, 110, 70)), "tavern": ((40, 24, 14), (170, 110, 50))}


def get(iid, mood="short", size=(480, 320), hd=False):
    """hd — полноэкранная сцена: исходный кадр без сжатия (assets/illustrations/hd), сглаженное растяжение."""
    key = (iid, mood, size, hd)
    if key not in _cache:
        hd_path = os.path.join(DIR, "hd", f"{iid}.png")
        if hd and os.path.exists(hd_path):
            try:
                big = pygame.image.load(hd_path)
                try:
                    big = big.convert()
                except pygame.error:
                    pass
                _cache[key] = pygame.transform.smoothscale(big, size)
                return _cache[key]
            except pygame.error:
                pass
        path = os.path.join(DIR, f"{iid}.png")
        img = None
        if os.path.exists(path):
            try:
                img = pygame.image.load(path)
                try:
                    img = img.convert()
                except pygame.error:
                    pass
            except pygame.error:
                img = None
        if img is None:
            img = placeholder(iid, mood)
        _cache[key] = pygame.transform.scale(img, size)
    return _cache[key]


def has(iid):
    return os.path.exists(os.path.join(DIR, f"{iid}.png"))


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def placeholder(iid, mood="short"):
    """Пиксельная виньетка 192×128: вариант по хэшу id, настроение — по виду события."""
    rng = random.Random(iid)
    top, glow = MOODS.get(mood, MOODS["short"])
    s = pygame.Surface((W, H))
    horizon = rng.randint(66, 80)
    for y in range(H):
        t = y / horizon if y < horizon else 1.0
        s.fill(_mix(_mix(top, (8, 10, 14), 0.6), _mix(glow, top, 0.4), t ** 1.6), (0, y, W, 1))
    mx, my = rng.randint(30, 160), rng.randint(14, 34)
    for r, a in ((14, 0.15), (10, 0.3), (6, 1.0)):
        pygame.draw.circle(s, _mix(top, (240, 236, 200), a), (mx, my), r)
    for _ in range(26):
        s.set_at((rng.randrange(W), rng.randrange(horizon - 10)), _mix(top, (230, 230, 210), rng.uniform(0.3, 0.8)))
    far = _mix(top, (6, 8, 10), 0.5)
    for x in range(0, W, 3):
        h = int(10 + 8 * math.sin(x * 0.07 + rng.random()) + rng.randint(0, 6))
        pygame.draw.rect(s, far, (x, horizon - h, 3, h))
    water = _mix(top, (30, 60, 70), 0.5)
    pygame.draw.rect(s, water, (0, horizon, W, H - horizon))
    for y in range(horizon + 2, H, 3):
        for _ in range(3):
            x = rng.randrange(W)
            pygame.draw.line(s, _mix(water, (180, 200, 190), 0.25), (x, y), (x + rng.randint(4, 14), y))
    pygame.draw.line(s, _mix(water, (240, 236, 200), 0.5), (mx - 8, horizon + 6), (mx + 8, horizon + 6))
    dark = (8, 10, 10)
    for _ in range(rng.randint(2, 4)):          # деревья-силуэты
        x = rng.choice([rng.randint(0, 50), rng.randint(140, 192)])
        h = rng.randint(50, 80)
        pygame.draw.rect(s, dark, (x, horizon - h + 20, 4, h))
        for k in range(5):
            pygame.draw.circle(s, dark, (x + rng.randint(-12, 14), horizon - h + 20 + rng.randint(-6, 10)),
                               rng.randint(6, 12))
    for x in range(0, W, 2):                    # камыши впереди
        if rng.random() < 0.45:
            h = rng.randint(8, 26)
            pygame.draw.line(s, (14, 22, 14), (x, H), (x + rng.randint(-2, 2), H - h))
            if rng.random() < 0.3:
                pygame.draw.rect(s, (40, 30, 18), (x - 1, H - h, 2, 4))
    if mood in ("thread", "tavern"):            # тёплый огонёк — сюжет / таверна
        fx, fy = rng.randint(70, 120), horizon - 4
        for r, a in ((9, 0.2), (5, 0.6), (2, 1.0)):
            pygame.draw.circle(s, _mix(top, (255, 190, 90), a), (fx, fy), r)
    return s
