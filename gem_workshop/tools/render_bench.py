"""Стенд рендера: одни и те же камни в разных режимах света → сетка снимков.

Рисует настоящий экран осмотра (InspectScene) без окна игры и вырезает
поле камня. Нужен, чтобы сравнивать «до/после» правок шейдера.

    python tools/render_bench.py out.png [--zoom 1.6]
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))

from sim import gems as GM  # noqa: E402
from workshop.model import Workshop  # noqa: E402
from workshop import app as A  # noqa: E402


def inc(k, p, r, **kw):
    d = {"k": k, "p": list(p), "r": r}
    d.update(kw)
    return d


# Набор включений, чтобы каждый тип был виден (координаты — доли кристалла).
SET_A = [
    inc("feather", (0.30, -0.15, 0.20), 0.16, n=[0.55, 0.35, 0.76]),
    inc("cloud", (-0.35, 0.10, -0.25), 0.10, axis=[0, 0, 1], aspect=1.3),
    inc("crystal", (0.05, 0.30, -0.05), 0.05, axis=[0.3, 0.2, 0.93], aspect=1.4),
    inc("bubble", (-0.10, -0.35, 0.35), 0.035, axis=[0, 0, 1], aspect=1.0),
    inc("fingerprint", (-0.25, -0.05, 0.40), 0.20, n=[0.1, 0.8, 0.59]),
    inc("two_phase", (0.30, 0.25, -0.40), 0.07, axis=[0, 0, 1], aspect=1.6),
]

SET_B = [
    inc("silk", (0, 0, 0), 0.55, d=0.8),
    inc("crystal", (0.15, -0.10, 0.10), 0.06, axis=[0.1, 0.9, 0.4], aspect=1.2, halo=1.0),
    inc("fingerprint", (-0.20, 0.25, -0.15), 0.22, n=[0.7, 0.1, 0.7]),
    inc("feather", (-0.30, -0.30, 0.30), 0.12, n=[0.2, 0.6, 0.77], surf=1.0),
]

# (подпись, вид, форма[@ракурс], караты, насыщенность, включения, зерно камня)
# Зерно 205 — типичный фиолетовый аметист; 101 — бледный лавандово-цитриновый.
STONES = [
    ("Аметист · кристалл", "amethyst", "prism", 2.6, 0.6, SET_A, 205),
    ("Кристалл в профиль", "amethyst", "prism@side", 2.6, 0.6, SET_A, 205),
    ("Аметист · обломок", "amethyst", "massive", 2.2, 0.6, SET_A, 205),
    ("Бледный аметист", "amethyst", "prism@side", 2.6, 0.6, SET_A, 101),
    ("Сапфир · галька", "sapphire", "massive", 2.4, 0.62, SET_B, 101),
    ("Аметист · огранка", "amethyst", "cut", 1.4, 0.65, SET_A, 101),
]

MODES = [("без света", None), ("1 сзади", "back"), ("3 сбоку", "grazing"), ("2 прямой", "front")]


class _App:
    def __init__(self, w):
        self.workshop = w
        self.clock = 1.7


def make_stone(w, gid, form, size, col, incl, seed):
    import random
    r = GM.roll_rough(w.xd, gid, random.Random(seed), f"bench{seed}", size)
    if incl is None:                        # включения по рецепту минерала: камень, где их хотя бы 3
        from game import jewel_view as JV
        rng = random.Random(seed)
        for _ in range(200):
            g = GM.roll_rough(w.xd, gid, random.Random(rng.randrange(10 ** 6)), "probe", size)
            g["form"] = "massive" if form == "cut" else form
            if len([i for i in JV.rough_incl(g) if i["k"] != "silk"]) >= 3:
                break
        incl = [i for i in g["incl"] if form != "cut" or i["k"] != "silk"]
        print(gid, form, [i["k"] for i in incl])
    if form == "cut":                       # огранённый камень: включения в единицах камня (R = 100)
        return {"uid": f"benchg{seed}", "id": gid, "size": size, "col": col, "cl": 0.7, "q": 1.6,
                "cut": "brilliant", "star": 0.0,
                "incl": [dict(i, p=[v * 70 for v in i["p"]], r=i["r"] * 70) for i in incl]}
    r["form"] = form
    r["col"] = col
    r["incl"] = [dict(i) for i in incl]
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--zoom", type=float, default=1.6)
    ap.add_argument("--scale", type=float, default=0.5)
    ap.add_argument("--gen", action="store_true",
                    help="включения из генерации (рецепт минерала), а не тестовый набор")
    ap.add_argument("--zoo", type=int, default=0,
                    help="сетка из N случайных кусков сырья (как в партиях), без фонарика")
    ap.add_argument("--light", default=None, help="режим света для --zoo: back / grazing / front")
    args = ap.parse_args()
    if args.zoo:
        return zoo(args)
    if args.gen:
        global STONES
        STONES = [s[:5] + (None,) + s[6:] for s in STONES]

    w = Workshop(seed=7)
    app = _App(w)
    screen = pygame.Surface((A.W, A.H))
    font = pygame.font.SysFont("arial", 16, bold=True)
    cell = None
    rows = []
    for si, (label, gid, form, size, col, incl, seed) in enumerate(STONES):
        form, _, angle = form.partition("@")
        stone = make_stone(w, gid, form, size, col, incl, seed)
        row = []
        for mlabel, mode in MODES:
            sc = A.InspectScene(app, [stone], 0, "view", -1)
            if angle == "side":                     # ось кристалла поперёк взгляда: видны грани призмы
                sc.insp.turn(0, -130)
                sc.insp.turn(35, 0)
            sc.insp.zoom = args.zoom
            sc.flash_on = mode is not None
            sc.flash_mode = mode or "back"
            sc.flash_xy = (0.5, 0.5)
            screen.fill((0, 0, 0))
            sc.draw(screen)
            view = sc.view_rect()
            crop = screen.subsurface(view).copy()
            crop = pygame.transform.smoothscale(
                crop, (int(view.w * args.scale), int(view.h * args.scale)))
            crop.blit(font.render(f"{label} · {mlabel}", True, (240, 220, 170)), (8, 6))
            row.append(crop)
            cell = crop.get_size()
        rows.append(row)
    cw, ch = cell
    sheet = pygame.Surface((cw * len(MODES), ch * len(rows)))
    for y, row in enumerate(rows):
        for x, img in enumerate(row):
            sheet.blit(img, (x * cw, y * ch))
    pygame.image.save(sheet, args.out)
    print("saved", args.out, sheet.get_size())


def zoo(args):
    """Много случайных кусков — проверить, что сырьё разное и невзрачное."""
    import random
    w = Workshop(seed=7)
    app = _App(w)
    screen = pygame.Surface((A.W, A.H))
    font = pygame.font.SysFont("arial", 14, bold=True)
    gids = ("amethyst", "sapphire", "ruby", "emerald", "topaz")
    rng = random.Random(77)
    cells = []
    for k in range(args.zoo):
        gid = gids[k % len(gids)]
        stone = GM.roll_rough(w.xd, gid, random.Random(rng.randrange(10 ** 6)), f"zoo{k}")
        sc = A.InspectScene(app, [stone], 0, "view", -1)
        sc.insp.zoom = args.zoom
        sc.flash_on = bool(args.light)
        sc.flash_mode = args.light or "back"
        screen.fill((0, 0, 0))
        sc.draw(screen)
        view = sc.view_rect()
        crop = screen.subsurface(view).copy()
        crop = pygame.transform.smoothscale(crop, (int(view.w * args.scale), int(view.h * args.scale)))
        label = f"{w.gem_name(gid)} · {GM.shape_name(stone)} · {stone['size']:.1f} ct"
        crop.blit(font.render(label, True, (240, 220, 170)), (6, 4))
        cells.append(crop)
    cols = 5
    cw, ch = cells[0].get_size()
    rows = (len(cells) + cols - 1) // cols
    sheet = pygame.Surface((cw * cols, ch * rows))
    for i, img in enumerate(cells):
        sheet.blit(img, ((i % cols) * cw, (i // cols) * ch))
    pygame.image.save(sheet, args.out)
    print("saved", args.out, sheet.get_size())


if __name__ == "__main__":
    main()
