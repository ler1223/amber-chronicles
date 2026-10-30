"""Лист-образец арт-стиля эффектов (art_style.md): «физика → пиксель».

Каждое явление грубо симулируется физически (тепло поднимается и остывает, облако расплывается, кристалл растёт
по осям, разряд ищет путь к земле, капли летят по баллистике), затем запекается в пиксельную сетку: палитра стихии
из 6 цветов, упорядоченный дизеринг вместо плавной прозрачности, 8 кадров (в игре — 12 кадров/с).
Симуляторы для игры — ui/pixfx_sim.py (этот лист берёт оттуда палитры и запекание), сам лист только рисует: python tools/style_sheet.py → assets/style/style_sheet.png
"""
import os
import sys

import numpy as np

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ui.pixfx_sim import PAL, bake, blur  # noqa: E402
OUT = os.path.join(ROOT, "assets", "style", "style_sheet.png")
N = 40          # сторона кадра эффекта в пикселях эффекта
SCALE = 4       # в листе: 1 пиксель эффекта = 4 пикселя (в игре — 2 экранных, как у фигурок)
FRAMES = 8

# палитры, дизеринг и запекание — общие с игрой (ui/pixfx_sim.py)


# ---------- явления ----------

def sim_fire(rng):
    """Тепло поднимается, сносится вбок и остывает (огонь «из физики»): языки рвутся сами."""
    H = np.zeros((N, N))
    out = []
    for t in range(FRAMES * 3):
        src = np.exp(-((np.arange(N) - N / 2) / 5.5) ** 2) * (0.8 + 0.4 * rng.random(N))
        H[-2:] = src * (1.0 if t < FRAMES * 2 else 0.25)
        shift = rng.integers(-1, 2, size=N)
        up = np.zeros_like(H)
        for x in range(N):
            up[:-1, x] = H[1:, (x + shift[x]) % N]
        H = np.clip(blur(up) * 1.02 - rng.random((N, N)) * 0.035 - 0.01, 0, 1)
        if t % 3 == 2:
            out.append(bake(H ** 0.8, PAL["fire"]))
    return out


def sim_cloud(rng, pal):
    """Облако: несколько клубов расходятся и всплывают, плотность размывается и тает."""
    D = np.zeros((N, N))
    Y, X = np.mgrid[0:N, 0:N]
    puffs = [(N / 2 + rng.normal(0, 3), N * 0.62 + rng.normal(0, 2), rng.normal(0, 0.6), -0.3 - rng.random() * 0.4,
              3 + rng.random() * 2) for _ in range(7)]
    noise = rng.random((N, N))
    for _ in range(4):
        noise = blur(noise)
    out = []
    for t in range(FRAMES):
        D *= 0.82
        for i, (x, y, vx, vy, r) in enumerate(puffs):
            x, y, r = x + vx * t, y + vy * t, r + 1.3 * t
            D += np.exp(-((X - x) ** 2 + (Y - y) ** 2) / (2 * r * r)) * max(0.0, 1.0 - t / (FRAMES + 2))
        f = blur(D)
        f = f / (f.max() + 1e-6) * max(0.2, 1 - t / (FRAMES + 3))
        lump = (np.roll(noise, t, 0) - noise.mean()) / (noise.std() + 1e-6)
        f = f * (0.72 + 0.22 * lump)
        out.append(bake(np.clip(f, 0, 1), pal, np.clip(f * 1.9, 0, 1)))
    return out


def sim_ice(rng):
    """Кристалл: дендритный рост, как у инея — шесть главных лучей растут вдоль осей кристалла, от них под углом
    отходят боковые ветви (короче к кончику). Кончики свежие — светлее."""
    F = np.zeros((N, N))
    c = N / 2
    arms = []
    for k in range(6):
        a = k * np.pi / 3 + 0.15
        arms.append({"a": a, "len": 0.0, "max": N * 0.46 * rng.uniform(0.85, 1.0), "main": True})
    branches = []
    out = []
    for t in range(FRAMES * 3):
        for arm in arms + branches:
            if arm["len"] < arm["max"]:
                arm["len"] += 1.3
                ox, oy = arm.get("o", (c, c))
                x = ox + np.cos(arm["a"]) * arm["len"]
                y = oy + np.sin(arm["a"]) * arm["len"] * 0.85
                if 0 <= x < N and 0 <= y < N:
                    F[int(y), int(x)] = t + 1
                arm["steps"] = arm.get("steps", 0) + 1
                if arm.get("main") and arm["steps"] % 3 == 0 and rng.random() < 0.85:
                    for side in (-1, 1):            # боковые ветви под 60°, короче к кончику
                        branches.append({"a": arm["a"] + side * np.pi / 3, "len": 0.0, "o": (x, y),
                                         "max": (arm["max"] - arm["len"]) * 0.45})
        if t % 3 == 2:
            frozen = F > 0
            fresh = frozen & (F > t - 2)
            v = np.where(frozen, 0.55, 0) + fresh * 0.4
            glow = blur(frozen.astype(float)) * 0.35 * (~frozen)
            out.append(bake(np.clip(v + glow, 0, 1), PAL["ice"], np.clip(frozen + glow * 2, 0, 1)))
    return out


def sim_lightning(rng):
    """Разряд: ветвящийся рост к земле (модель пробоя: соседи ближе к цели вероятнее), затем послесвечение."""
    pts = [(N // 2, 0)]
    grid = np.zeros((N, N))
    grid[0, N // 2] = 1
    while max(p[1] for p in pts) < N - 2:
        x, y = pts[rng.integers(len(pts))] if rng.random() < 0.3 else max(pts, key=lambda p: p[1])
        cand = [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (0, 1) if (dx, dy) != (0, 0)
                and 0 <= x + dx < N and 0 <= y + dy < N and grid[y + dy, x + dx] == 0]
        if not cand:
            continue
        w = np.array([(1 + dy * 3) * (1.5 if dx == 0 else 1) for (cx, cy) in cand
                      for dx, dy in [(cx - x, cy - y)]], float)
        nx, ny = cand[rng.choice(len(cand), p=w / w.sum())]
        grid[ny, nx] = 1
        pts.append((nx, ny))
    out = []
    glow = blur(blur(grid))
    for t in range(FRAMES):
        k = [1.0, 1.0, 0.25, 0.9, 0.55, 0.35, 0.2, 0.1][t]   # вспышка, мигание, послесвечение
        v = grid * k + glow * k * 1.6
        out.append(bake(np.clip(v, 0, 1), PAL["storm"]))
    return out


def sim_splash(rng, pal):
    """Всплеск: капли летят по баллистике с сопротивлением воздуха, на земле — расходящийся круг."""
    n = 40
    ang = rng.uniform(-2.6, -0.5, n)
    sp = rng.uniform(1.5, 3.4, n)
    vx, vy = np.cos(ang) * sp, np.sin(ang) * sp
    x, y = np.full(n, N / 2), np.full(n, N * 0.72)
    out = []
    Y, X = np.mgrid[0:N, 0:N]
    for t in range(FRAMES):
        f = np.zeros((N, N))
        r = 2 + t * 2.3
        ring = np.exp(-((np.sqrt((X - N / 2) ** 2 + ((Y - N * 0.75) * 2.6) ** 2) - r) / 1.2) ** 2)
        f += ring * max(0.0, 1 - t / FRAMES) * 0.9
        for _ in range(3):
            vy += 0.17
            vx *= 0.97
            vy *= 0.97
            x += vx
            y += vy
            ok = (x >= 0) & (x < N) & (y >= 0) & (y < N * 0.76)
            v = np.where(rng.random(ok.sum()) < 0.2, 0.95, 0.62)
            f[y[ok].astype(int), x[ok].astype(int)] = np.maximum(f[y[ok].astype(int), x[ok].astype(int)], v)
        out.append(bake(np.clip(f, 0, 1), pal))
    return out


def sim_blast(rng):
    """Взрыв: ударная волна по кругу, обломки по дугам, дым остаётся и оседает."""
    n = 40
    ang = rng.uniform(0, np.pi * 2, n)
    sp = rng.uniform(1.2, 2.8, n)
    x, y = np.full(n, N / 2), np.full(n, N / 2)
    vx, vy = np.cos(ang) * sp, np.sin(ang) * sp * 0.7 - 1.0
    smoke = np.zeros((N, N))
    Y, X = np.mgrid[0:N, 0:N]
    out = []
    for t in range(FRAMES):
        f = np.zeros((N, N))
        r = 2 + t * 3.0
        d = np.sqrt((X - N / 2) ** 2 + ((Y - N / 2) * 1.3) ** 2)
        f += np.exp(-((d - r) / 1.6) ** 2) * max(0.0, 1 - t / 6) * 1.1
        f += np.exp(-(d / 4) ** 2) * max(0.0, 1 - t / 2.5)
        smoke = blur(smoke) * 0.9 + np.exp(-(d / (3 + t)) ** 2) * 0.25 * (t < 4)
        for _ in range(2):
            vy += 0.12
            x += vx
            y += vy
            ok = (x >= 0) & (x < N) & (y >= 0) & (y < N)
            f[y[ok].astype(int), x[ok].astype(int)] = 0.8
        fire = bake(np.clip(f, 0, 1), PAL["fire"])
        sm = bake(np.clip(smoke * 1.8, 0, 1) * 0.6, PAL["dust"])
        out.append(np.where(fire[..., 3:4] > 0, fire, sm))
    return out


def sim_vortex(rng):
    """Гравитация: частицы по спирали затягиваются в центр (сохранение момента — быстрее у центра)."""
    n = 160
    r = rng.uniform(8, N * 0.48, n)
    a = rng.uniform(0, np.pi * 2, n)
    out = []
    for t in range(FRAMES):
        f = np.zeros((N, N))
        for _ in range(3):
            a += 0.9 / np.maximum(r, 2) * 2
            r *= 0.94
        x = (N / 2 + np.cos(a) * r).astype(int)
        y = (N / 2 + np.sin(a) * r * 0.7).astype(int)
        ok = (x >= 0) & (x < N) & (y >= 0) & (y < N)
        f[y[ok], x[ok]] = 0.5 + 0.5 * (1 - r[ok] / (N * 0.5))
        Y, X = np.mgrid[0:N, 0:N]
        f += np.exp(-(((X - N / 2) ** 2 + ((Y - N / 2) / 0.7) ** 2) / (2 + t))) * 0.9
        out.append(bake(np.clip(blur(f) * 1.6, 0, 1), PAL["gravity"]))
    return out


ROWS = [
    ("Огонь — тепло поднимается и остывает", lambda r: sim_fire(r)),
    ("Лёд — кристалл растёт по шести осям", lambda r: sim_ice(r)),
    ("Гроза — пробой к земле и послесвечение", lambda r: sim_lightning(r)),
    ("Вода — капли по баллистике, круг на земле", lambda r: sim_splash(r, PAL["water"])),
    ("Яд — облако расходится и тает", lambda r: sim_cloud(r, PAL["poison"])),
    ("Взрыв — волна, обломки, дым", lambda r: sim_blast(r)),
    ("Гравитация — спираль к центру", lambda r: sim_vortex(r)),
    ("Свет — тот же облачный решатель, палитра света", lambda r: sim_cloud(r, PAL["light"])),
]


def main():
    pygame.init()
    pygame.display.set_mode((10, 10))
    cell = N * SCALE
    pad, label_w = 10, 250
    W = label_w + FRAMES * (cell + pad) + pad
    H = 120 + len(ROWS) * (cell + pad) + 40
    sheet = pygame.Surface((W, H))
    sheet.fill((24, 26, 32))
    font = pygame.font.SysFont("segoeui,arial", 18, bold=True)
    small = pygame.font.SysFont("segoeui,arial", 14)
    sheet.blit(font.render("Палитры стихий (6 цветов: тёмный край → белое ядро)", True, (230, 230, 240)), (pad, 8))
    x = pad
    for name, pal in PAL.items():
        sheet.blit(small.render(name, True, (190, 195, 210)), (x, 36))
        for i, c in enumerate(pal):
            pygame.draw.rect(sheet, c, (x + i * 14, 58, 14, 34))
        x += 6 * 14 + 22
    y = 120
    for i, (title, fn) in enumerate(ROWS):
        rng = np.random.default_rng(7 + i)
        frames = fn(rng)
        for j, line in enumerate(_wrap(title, small, label_w - 20)):
            sheet.blit(small.render(line, True, (220, 222, 230)), (pad, y + 10 + j * 18))
        for k, fr in enumerate(frames[:FRAMES]):
            bg = pygame.Rect(label_w + k * (cell + pad), y, cell, cell)
            pygame.draw.rect(sheet, (46, 62, 44), bg)                    # «трава» под эффектом
            surf = pygame.image.frombuffer(np.ascontiguousarray(fr).tobytes(), (N, N), "RGBA")
            sheet.blit(pygame.transform.scale(surf, (cell, cell)), bg)
        y += cell + pad
    sheet.blit(small.render("Каждый кадр — 40×40 пикселей эффекта, без сглаживания; в игре 1 пиксель эффекта = "
                            "2 экранных (как у фигурок), смена кадров 12 раз в секунду.", True, (160, 166, 180)),
               (pad, y + 6))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pygame.image.save(sheet, OUT)
    print(OUT)


def _wrap(s, font, w):
    out, cur = [], ""
    for word in s.split():
        t = (cur + " " + word).strip()
        if font.size(t)[0] > w and cur:
            out.append(cur)
            cur = word
        else:
            cur = t
    return out + [cur]


if __name__ == "__main__":
    sys.exit(main())
