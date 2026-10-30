"""Симуляторы явлений для пиксельных эффектов (art_style.md, «физика → пиксель»).

Каждое явление грубо симулируется физически, затем запекается в пиксели: палитра стихии из 6 цветов, упорядоченный
дизеринг вместо плавной прозрачности. Результат — список кадров RGBA (numpy uint8, [высота, ширина, 4]).
Без pygame: используется игрой (ui/pixfx.py) и листом-образцом (tools/style_sheet.py).
"""
import numpy as np

PAL = {
    "fire": [(52, 12, 24), (128, 24, 22), (206, 66, 24), (244, 136, 36), (255, 206, 92), (255, 250, 214)],
    "ice": [(22, 32, 74), (42, 84, 156), (82, 152, 222), (152, 212, 250), (214, 242, 255), (255, 255, 255)],
    "storm": [(30, 20, 74), (72, 52, 176), (124, 114, 255), (182, 192, 255), (232, 236, 255), (255, 255, 255)],
    "water": [(12, 32, 64), (22, 72, 134), (42, 124, 204), (94, 184, 242), (174, 228, 255), (242, 250, 255)],
    "poison": [(22, 32, 12), (52, 84, 22), (92, 144, 32), (142, 204, 52), (202, 242, 112), (242, 255, 204)],
    "oil": [(22, 16, 10), (52, 36, 20), (92, 66, 36), (142, 106, 56), (192, 162, 102), (236, 216, 162)],
    "light": [(62, 42, 12), (152, 112, 32), (232, 182, 62), (255, 226, 122), (255, 246, 204), (255, 255, 255)],
    "shadow": [(12, 6, 22), (42, 22, 62), (82, 42, 112), (132, 72, 172), (182, 122, 222), (232, 202, 255)],
    "nature": [(16, 32, 12), (32, 72, 26), (62, 122, 42), (112, 172, 62), (172, 216, 102), (232, 250, 182)],
    "dust": [(42, 32, 26), (82, 66, 52), (132, 112, 86), (182, 162, 132), (222, 206, 182), (250, 246, 236)],
    "gravity": [(6, 2, 16), (36, 12, 62), (82, 32, 132), (142, 82, 202), (202, 152, 255), (246, 232, 255)],
    "time": [(40, 30, 10), (110, 84, 28), (196, 156, 56), (240, 210, 110), (190, 240, 250), (255, 255, 255)],
    "steam": [(70, 78, 92), (112, 122, 138), (156, 166, 180), (196, 204, 216), (228, 234, 242), (252, 252, 255)],
    "scorch": [(18, 12, 10), (34, 24, 18), (56, 38, 26), (120, 40, 18), (220, 90, 30), (255, 190, 80)],
}
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16.0


def bake(field, pal, alpha=None, opacity=1.0):
    """Поле 0..1 → пиксели палитры с дизерингом; ниже порога — прозрачно (дизеринг и по краю)."""
    if isinstance(pal, str):
        pal = PAL[pal]
    h, w = field.shape
    th = np.tile(BAYER, (h // 4 + 1, w // 4 + 1))[:h, :w]
    v = np.clip(field, 0, 1)
    a = v if alpha is None else np.clip(alpha, 0, 1)
    idx = np.clip((v * len(pal) + th - 0.5).astype(int), 0, len(pal) - 1)
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = np.array(pal, np.uint8)[idx]
    rgba[..., 3] = np.where(a * 1.6 * opacity > th + 0.08, 255, 0)
    return rgba


def blur(f):
    return (f + np.roll(f, 1, 0) + np.roll(f, -1, 0) + np.roll(f, 1, 1) + np.roll(f, -1, 1)) / 5.0


def _dots(f, x, y, v):
    h, w = f.shape
    ok = (x >= 0) & (x < w) & (y >= 0) & (y < h)
    xi, yi = x[ok].astype(int), y[ok].astype(int)
    vv = v[ok] if np.ndim(v) else v
    f[yi, xi] = np.maximum(f[yi, xi], vv)


def overlay(top, bottom):
    return np.where(top[..., 3:4] > 0, top, bottom)


# ---------- огонь ----------

def flame(w, h, frames, seed=0, strength=1.0, width=0.35, pal="fire", warm=24, step=2):
    """Пламя: тепло поднимается, сносится вбок и остывает. Петля для горящих клеток и статуса."""
    rng = np.random.default_rng(seed)
    H = np.zeros((h, w))
    cols = np.arange(w)
    out = []
    for t in range(warm + frames * step):
        src = np.exp(-((cols - w / 2) / (w * width)) ** 2) * (0.75 + 0.45 * rng.random(w)) * strength
        H[-2:] = src
        shift = rng.integers(-1, 2, size=w)
        up = np.zeros_like(H)
        up[:-1] = H[1:, (cols + shift) % w]
        H = np.clip(blur(up) * 1.03 - rng.random((h, w)) * 0.04 * (24 / h) - 0.012 * (32 / h), 0, 1)
        if t >= warm and (t - warm) % step == 0:
            out.append(bake(H ** 0.8, pal, np.clip((H - 0.1) * 2.4, 0, 1)))   # холодный край не пылит точками
    return out


def orb(n, frames, seed=0):
    """Огненный шар-снаряд: горячее ядро, жар отрывается назад-вверх."""
    rng = np.random.default_rng(seed)
    Y, X = np.mgrid[0:n, 0:n]
    core = np.exp(-((X - n * 0.58) ** 2 + (Y - n * 0.5) ** 2) / (2 * (n * 0.18) ** 2))
    H = np.zeros((n, n))
    out = []
    for t in range(frames * 2 + 6):
        H = np.maximum(H, core * (0.85 + 0.25 * rng.random((n, n))))
        H = np.roll(H, -1, 1) * 0.86            # хвост уносится назад
        H = np.clip(blur(H) - rng.random((n, n)) * 0.05, 0, 1)
        if t >= 6 and t % 2 == 0:
            out.append(bake(np.clip(H * 1.25 + core * 0.4, 0, 1), "fire"))
    return out


def core(n, frames, seed=0, pal="fire"):
    """Голова снаряда: круглое горячее ядро, край рвётся и мерцает. Хвост дают живые частицы (ui/pixsim.py)."""
    rng = np.random.default_rng(seed)
    Y, X = np.mgrid[0:n, 0:n]
    d = np.sqrt((X - (n - 1) / 2) ** 2 + (Y - (n - 1) / 2) ** 2) / (n / 2)
    out = []
    for _ in range(frames):
        edge = blur(rng.random((n, n))) * 0.35
        f = np.clip(1.15 - d * 1.05 + edge - 0.17, 0, 1)
        out.append(bake(f ** 0.7, pal, np.clip((1 - d) * 2.2 + edge - 0.2, 0, 1)))
    return out


def blast(n, frames, seed=0, pal="fire", smoke=True):
    """Взрыв: вспышка, ударная волна по кругу, обломки по дугам, дым остаётся и оседает."""
    rng = np.random.default_rng(seed)
    k = max(1, int(n * 0.9))
    ang = rng.uniform(0, np.pi * 2, k)
    sp = rng.uniform(0.04, 0.075, k) * n
    x, y = np.full(k, n / 2), np.full(k, n / 2)
    vx, vy = np.cos(ang) * sp, np.sin(ang) * sp * 0.7 - 0.025 * n
    sm = np.zeros((n, n))
    Y, X = np.mgrid[0:n, 0:n]
    d = np.sqrt((X - n / 2) ** 2 + ((Y - n / 2) * 1.3) ** 2)
    noise = blur(blur(rng.random((n, n))))
    out = []
    for t in range(frames):
        f = np.zeros((n, n))
        r = n * (0.05 + 0.075 * t)
        f += np.exp(-((d - r) / (n * 0.04)) ** 2) * max(0.0, 1 - t / (frames * 0.7)) * 1.1
        f += np.exp(-(d / (n * (0.18 + 0.025 * t))) ** 2) * max(0.0, 1.2 - t / (frames * 0.45))
        f *= 0.8 + 0.4 * noise
        if smoke:
            sm = blur(sm) * 0.9 + np.exp(-(d / (n * (0.08 + 0.03 * t))) ** 2) * 0.3 * (t < frames * 0.5)
        for _ in range(2):
            vy += 0.0035 * n
            x += vx
            y += vy
        _dots(f, x, y, 0.75 if t < frames - 2 else 0.5)
        fire = bake(np.clip(f, 0, 1), pal)
        out.append(overlay(fire, bake(np.clip(sm * 1.7, 0, 1) * 0.6, "dust")) if smoke else fire)
    return out


def scorch(n, seed=0):
    """Подпалина на земле: обугленное пятно с тлеющими угольками (один кадр)."""
    rng = np.random.default_rng(seed)
    Y, X = np.mgrid[0:n, 0:n]
    d = np.sqrt((X - n / 2) ** 2 + (Y - n / 2) ** 2) / (n / 2)
    noise = blur(blur(rng.random((n, n))))
    f = np.clip((1 - d) * 1.4 + (noise - 0.5) * 0.9, 0, 1)
    v = f * 0.45 + (rng.random((n, n)) < 0.03) * (f > 0.5) * 0.9
    return bake(np.clip(v, 0, 1), "scorch", np.clip(f * 0.9, 0, 1))


# ---------- лёд ----------

def _dendrite(n, rng, steps, arms=6, reach=0.46):
    """Дендрит: главные лучи по осям кристалла, боковые ветви под 60°. Возвращает [шаг роста] для каждой клетки."""
    F = np.full((n, n), -1)
    c = n / 2
    tips = []
    for k in range(arms):
        a = k * 2 * np.pi / arms + rng.uniform(-0.1, 0.1)
        tips.append({"a": a, "len": 0.0, "max": n * reach * rng.uniform(0.8, 1.0), "o": (c, c), "main": True,
                     "steps": 0})
    for t in range(steps):
        for tip in list(tips):
            if tip["len"] >= tip["max"]:
                continue
            ox, oy = tip["o"]
            step = max(1.0, n / 32)
            for sub in np.arange(0.5, step + 0.01, 0.5):     # весь отрезок шага — без разрывов
                ln = tip["len"] + sub
                x = ox + np.cos(tip["a"]) * ln
                y = oy + np.sin(tip["a"]) * ln * 0.85
                if 0 <= x < n and 0 <= y < n and F[int(y), int(x)] < 0:
                    F[int(y), int(x)] = t
            tip["len"] += step
            tip["steps"] += 1
            if tip["main"] and tip["steps"] % 3 == 0 and rng.random() < 0.85:
                for side in (-1, 1):
                    tips.append({"a": tip["a"] + side * np.pi / 3, "len": 0.0, "o": (ox + np.cos(tip["a"]) * tip["len"],
                                 oy + np.sin(tip["a"]) * tip["len"] * 0.85), "main": False,
                                 "max": (tip["max"] - tip["len"]) * 0.45, "steps": 0})
    if n >= 48:                                       # на крупных — лучи в 2 пикселя
        G = F.copy()
        for dx, dy in ((1, 0), (0, 1)):
            sh = np.roll(np.roll(F, dy, 0), dx, 1)
            G = np.where((G < 0) & (sh >= 0), sh, G)
        F = G
    return F


def ice_bloom(n, frames, seed=0):
    """Ледяной удар: кристалл вырастает за пару кадров, держится, затем раскалывается — осколки летят по дугам."""
    rng = np.random.default_rng(seed)
    grow = max(2, frames // 2)
    F = _dendrite(n, rng, grow * 4)
    frozen = F >= 0
    ys, xs = np.nonzero(frozen)
    cx = cy = n / 2
    vx = (xs - cx) * 0.18 + rng.normal(0, 0.4, len(xs))
    vy = (ys - cy) * 0.12 - rng.uniform(0.3, 1.2, len(xs))
    px, py = xs.astype(float), ys.astype(float)
    out = []
    for t in range(frames):
        if t < grow:
            live = frozen & (F <= (t + 1) * 4)
            fresh = live & (F > t * 4 - 2)
            v = np.where(live, 0.55, 0) + fresh * 0.4
            g = blur(live.astype(float)) * 0.3 * ~live
            out.append(bake(np.clip(v + g, 0, 1), "ice", np.clip(live + g * 2, 0, 1)))
        else:
            f = np.zeros((n, n))
            px, py = px + vx, py + vy
            vy += 0.25
            keep = rng.random(len(px)) < max(0.15, 1 - (t - grow) / (frames - grow + 1))
            _dots(f, px[keep], py[keep], 0.7)
            out.append(bake(f, "ice"))
    return out


def spikes(w, h, frames, seed=0, count=5):
    """Ледяные шипы из земли: растут, держатся, крошатся сверху вниз."""
    rng = np.random.default_rng(seed)
    xs = np.sort(rng.uniform(w * 0.12, w * 0.88, count))
    hs = rng.uniform(h * 0.45, h * 0.95, count)
    ws = rng.uniform(w * 0.06, w * 0.12, count)
    Y, X = np.mgrid[0:h, 0:w]
    out = []
    for t in range(frames):
        grow = min(1.0, (t + 1) / (frames * 0.35))
        crumble = max(0.0, (t - frames * 0.6) / (frames * 0.4))
        f = np.zeros((h, w))
        a = np.zeros((h, w))
        for x0, hh, ww in zip(xs, hs, ws):
            top = h - hh * grow
            inside = (Y >= top) & (np.abs(X - x0) <= ww * (Y - top) / max(1, hh))
            inside &= Y >= top + hh * crumble * 0.8 + rng.random((h, w)) * crumble * 8
            edge = inside & (np.abs(X - x0) > ww * (Y - top) / max(1, hh) - 1.2)
            f = np.where(inside, 0.45 + 0.2 * (X < x0) + edge * 0.35, f)
            a = np.maximum(a, inside)
        out.append(bake(np.clip(f, 0, 1), "ice", a))
    return out


def shard(n, frames):
    """Ледяной осколок-снаряд (смотрит вправо): ромб с бегущим бликом."""
    Y, X = np.mgrid[0:n, 0:n]
    body = (np.abs(X - n / 2) / (n * 0.48) + np.abs(Y - n / 2) / (n * 0.16)) <= 1
    out = []
    for t in range(frames):
        glint = np.abs(X - (n * 0.2 + n * 0.6 * t / max(1, frames - 1))) < 1.5
        v = np.where(body, 0.45 + 0.25 * (Y < n / 2), 0) + (body & glint) * 0.5
        out.append(bake(np.clip(v, 0, 1), "ice", body.astype(float)))
    return out


def shatter(n, frames, seed=0, pal="ice"):
    """Раскол: осколки разлетаются по баллистике, мельчают и тают."""
    rng = np.random.default_rng(seed)
    k = max(8, n)
    ang = rng.uniform(0, np.pi * 2, k)
    sp = rng.uniform(0.03, 0.08, k) * n
    x, y = np.full(k, n / 2), np.full(k, n / 2)
    vx, vy = np.cos(ang) * sp, np.sin(ang) * sp * 0.7 - 0.03 * n
    out = []
    for t in range(frames):
        f = np.zeros((n, n))
        x, y = x + vx, y + vy
        vy += 0.006 * n
        keep = rng.random(k) < max(0.2, 1 - t / frames)
        _dots(f, x[keep], y[keep], np.where(rng.random(keep.sum()) < 0.3, 0.95, 0.6))
        _dots(f, x[keep] + 1, y[keep], 0.5)
        if t == 0:
            Y, X = np.mgrid[0:n, 0:n]
            f = np.maximum(f, np.exp(-((X - n / 2) ** 2 + (Y - n / 2) ** 2) / (n * 0.8)) * 1.0)
        out.append(bake(f, pal))
    return out


def frost(n, seed=0):
    """Иней на земле (один кадр): ветвистые кристаллы, полупрозрачный дизеринг."""
    rng = np.random.default_rng(seed)
    F = _dendrite(n, rng, 40, arms=6, reach=0.5) >= 0
    halo = blur(blur(F.astype(float)))
    v = np.where(F, 0.7, halo * 0.6)
    return bake(np.clip(v, 0, 1), "ice", np.clip(F * 0.9 + halo * 0.9, 0, 1))


def crust(w, h, frames, seed=0):
    """Ледяная глыба на замёрзшем: грани (ячейки вокруг случайных центров), светлые рёбра, бегущий блик."""
    rng = np.random.default_rng(seed)
    Y, X = np.mgrid[0:h, 0:w]
    pts = rng.uniform(0, 1, (9, 2)) * (w, h)
    d = np.stack([(X - px) ** 2 + (Y - py) ** 2 for px, py in pts])
    near = d.argmin(0)
    shade = (near % 3) * 0.12
    edge = (near != np.roll(near, 1, 0)) | (near != np.roll(near, 1, 1))
    inside = (np.abs(X - w / 2) / (w * 0.5) + np.maximum(0, (h * 0.15 - Y)) / (h * 0.2)) <= 1
    out = []
    for t in range(frames):
        glint = np.abs((X + Y) - (t * (w + h) / max(1, frames))) < 2
        v = np.where(inside, 0.42 + shade, 0) + (inside & edge) * 0.3 + (inside & glint) * 0.35
        out.append(bake(np.clip(v, 0, 1), "ice", inside * (0.55 + 0.4 * edge)))
    return out


# ---------- облака ----------

def cloud(n, frames, seed=0, pal="steam", rise=0.4):
    """Облако (пар, яд, свет): клубы расходятся и всплывают, плотность размывается и тает."""
    rng = np.random.default_rng(seed)
    D = np.zeros((n, n))
    Y, X = np.mgrid[0:n, 0:n]
    s = n / 40
    puffs = [(n / 2 + rng.normal(0, 3 * s), n * 0.62 + rng.normal(0, 2 * s), rng.normal(0, 0.6 * s),
              -(0.3 + rng.random() * 0.4) * s * rise * 2.5, (3 + rng.random() * 2) * s) for _ in range(7)]
    noise = blur(blur(blur(blur(rng.random((n, n))))))
    out = []
    for t in range(frames):
        D *= 0.82
        for (x, y, vx, vy, r) in puffs:
            x, y, r = x + vx * t, y + vy * t, r + 1.3 * s * t
            D += np.exp(-((X - x) ** 2 + (Y - y) ** 2) / (2 * r * r)) * max(0.0, 1.0 - t / (frames + 2))
        f = blur(D)
        f = f / (f.max() + 1e-6) * max(0.2, 1 - t / (frames + 3))
        lump = (np.roll(noise, t, 0) - noise.mean()) / (noise.std() + 1e-6)
        f = f * (0.72 + 0.22 * lump)
        out.append(bake(np.clip(f, 0, 1), pal, np.clip(f * 1.9, 0, 1)))
    return out
