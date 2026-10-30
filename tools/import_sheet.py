"""Лист спрайтов из генератора (ChatGPT, все персонажи на одной картинке, пурпурный фон) → спрайты игры.

  python tools/import_sheet.py assets/art_src/sheet_ch12.png [папка=assets/sprites] [--preview out.png]

Картинка генератора — не настоящий пиксель-арт (нет ровной сетки, есть шум), поэтому каждый персонаж:
  1. вырезается по своей связной области (соседи с перекрытым оружием не попадают), мелкие оторванные кусочки
     (огоньки, кристаллы, искры) приклеиваются к ближайшему персонажу;
  2. край отступает на 2 пикселя (пурпурная кайма фона не попадает в цвет);
  3. уменьшается усреднением в общем масштабе (персонажи сохраняют рост относительно друг друга), элита и
     боссы — в свой холст;
  4. палитра урезается (k-средних), снаружи добавляется тёмный контур в 1 пиксель;
  5. ставится ногами на нижний ряд, по центру холста.
Порядок на листе — как в запросе (art_prompts.md): ряды сверху вниз, в ряду слева направо.
"""
import os
import sys

import numpy as np
import pygame

ORDER = ["warrior", "mage", "priest", "archer", "guardian", "cryo", "assassin", "druid", "druid_bear",
         "slime", "bog_archer", "beetle", "frog_shaman", "slime_king", "ice_witch",
         "fire_imp", "salamander", "hammer_thrower", "flame_priest", "magma_golem", "forge_overseer", "forge_lord"]
CANVAS = {"slime_king": 40, "forge_overseer": 40, "ice_witch": 48, "forge_lord": 48}   # элита ×2 = 80, боссы = 96
FIT = {"druid_bear"}            # растянуть до холста (облик медведя — крупный зверь)
HERO_H = 230                    # рост обычного персонажа на листе → 29 пикселей спрайта
MAGENTA = np.array([245, 5, 245])


def components(fg):
    h, w = fg.shape
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    al = pygame.surfarray.pixels_alpha(surf)
    al[:] = fg.T * 255
    del al
    comps = pygame.mask.from_surface(surf).connected_components(20)
    out = []
    for c in comps:
        m = pygame.surfarray.array_alpha(c.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))) > 0
        out.append((c.get_bounding_rects()[0], m.T, c.count()))
    return out


def erode(m, n):
    for _ in range(n):
        m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    return m


def kmeans(px, k, iters=12, seed=0):
    rng = np.random.default_rng(seed)
    k = min(k, len(px))
    cent = px[rng.choice(len(px), k, replace=False)].astype(float)
    for _ in range(iters):
        lab = np.argmin(((px[:, None, :] - cent[None]) ** 2).sum(-1), 1)
        for j in range(k):
            sel = px[lab == j]
            if len(sel):
                cent[j] = sel.mean(0)
    return cent, lab


def shrink(rgb, mask, scale):
    """Усреднение с учётом прозрачности: цвет считается только по закрашенным пикселям."""
    h, w = mask.shape
    nh, nw = max(1, round(h * scale)), max(1, round(w * scale))
    ys = (np.arange(nh + 1) * h / nh).astype(int)
    xs = (np.arange(nw + 1) * w / nw).astype(int)
    out = np.zeros((nh, nw, 3))
    cov = np.zeros((nh, nw))
    cs = np.cumsum(np.cumsum(np.pad(rgb * mask[..., None], ((1, 0), (1, 0), (0, 0))), 0), 1)
    ms = np.cumsum(np.cumsum(np.pad(mask.astype(float), ((1, 0), (1, 0))), 0), 1)
    for i in range(nh):
        for j in range(nw):
            y0, y1, x0, x1 = ys[i], ys[i + 1], xs[j], xs[j + 1]
            n = ms[y1, x1] - ms[y0, x1] - ms[y1, x0] + ms[y0, x0]
            area = max(1, (y1 - y0) * (x1 - x0))
            cov[i, j] = n / area
            if n:
                out[i, j] = (cs[y1, x1] - cs[y0, x1] - cs[y1, x0] + cs[y0, x0]) / n
    return out, cov


def make_sprite(rgb, mask, size, scale, colors=22):
    small, cov = shrink(rgb, mask, scale)
    alpha = cov > 0.42
    if not alpha.any():
        return None
    px = small[alpha]
    cent, lab = kmeans(px, colors)
    small[alpha] = cent[lab]
    # контур снаружи: прозрачный сосед закрашенного — тёмный цвет соседа
    h, w = alpha.shape
    pad_a = np.pad(alpha, 1)
    pad_c = np.pad(small, ((1, 1), (1, 1), (0, 0)))
    out_a = pad_a.copy()
    out_c = pad_c.copy()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = np.roll(np.roll(pad_a, dy, 0), dx, 1)
        nc = np.roll(np.roll(pad_c, dy, 0), dx, 1)
        edge = nb & ~out_a
        out_c[edge] = nc[edge] * 0.28 + np.array([12, 8, 16]) * 0.72
        out_a |= edge
    ys, xs = np.nonzero(out_a)
    out_a = out_a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    out_c = out_c[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    ch, cw = out_a.shape
    if ch > size or cw > size:                       # не влезло — ещё раз чуть мельче
        return make_sprite(rgb, mask, size, scale * size / max(ch, cw) * 0.97, colors)
    canvas = np.zeros((size, size, 4), np.uint8)
    y0, x0 = size - ch, (size - cw) // 2
    canvas[y0:, x0:x0 + cw, :3] = np.clip(out_c, 0, 255)
    canvas[y0:, x0:x0 + cw, 3] = out_a * 255
    return canvas


def run(src, folder, preview=None):
    pygame.init()
    img = pygame.image.load(src)
    a = pygame.surfarray.array3d(img).transpose(1, 0, 2).astype(float)
    fg = np.abs(a - MAGENTA).sum(-1) > 120
    comps = components(fg)
    big = sorted([c for c in comps if c[2] > 8000], key=lambda c: c[2], reverse=True)[:len(ORDER)]
    if len(big) != len(ORDER):
        raise SystemExit(f"на листе {len(big)} персонажей, ожидалось {len(ORDER)}")
    small = [c for c in comps if c[2] <= 8000]
    masks = [c[1].copy() for c in big]
    pts = []                                           # пиксели каждой фигуры (через 3) — для поиска ближайшей
    for b in big:
        ys, xs = np.nonzero(b[1][::3, ::3])
        pts.append(np.stack([xs * 3, ys * 3], 1))
    for r, m, _ in small:                              # огоньки и кристаллы — к ближайшей фигуре по её пикселям
        c = np.array([r.centerx, r.centery])
        d = [np.min(np.abs(p - c).sum(1)) for p in pts]
        i = int(np.argmin(d))
        if d[i] < 70:
            masks[i] |= m
    # порядок: ряды (по нижнему краю фигур), в ряду — слева направо
    order = sorted(range(len(big)), key=lambda i: (round(big[i][0].bottom / 300), big[i][0].left))
    out = {}
    for name, i in zip(ORDER, order):
        r = big[i][0]
        mask = erode(masks[i], 2)[r.top:r.bottom, r.left:r.right]
        rgb = a[r.top:r.bottom, r.left:r.right]
        size = CANVAS.get(name, 32)
        if name in CANVAS or name in FIT:
            scale = (size - 2) / max(r.w, r.h)
        else:
            scale = 29 / HERO_H
        spr = make_sprite(rgb, mask, size, scale)
        surf = pygame.image.frombuffer(np.ascontiguousarray(spr).tobytes(), (size, size), "RGBA").copy()
        pygame.image.save(surf, os.path.join(folder, f"{name}.png"))
        out[name] = surf
        print(f"{name}: {size}x{size}")
    if preview:
        sheet = pygame.Surface((len(ORDER) * 100, 220))
        sheet.fill((46, 70, 48))
        for k, name in enumerate(ORDER):
            s = out[name]
            kk = 96 // s.get_height() if s.get_height() > 32 else 2
            big2 = pygame.transform.scale(s, (s.get_width() * kk, s.get_height() * kk))
            sheet.blit(big2, (k * 100 + 50 - big2.get_width() // 2, 200 - big2.get_height()))
        pygame.image.save(sheet, preview)


if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    prev = sys.argv[sys.argv.index("--preview") + 1] if "--preview" in sys.argv else None
    if prev in args:
        args.remove(prev)
    if not args:
        print(__doc__)
        raise SystemExit(1)
    run(args[0], args[1] if len(args) > 1 else "assets/sprites", prev)
