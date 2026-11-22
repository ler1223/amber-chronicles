"""Импорт интерфейса боя «Спуска» (prompts_expedition.md, раздел DC4).

assets/art_src/ui/ui_<герой>.png — набор интерфейса героя, сетка 4×3 → assets/ui/<герой>/<деталь>.png
assets/art_src/ui/ui_icons.png    — значки, сетка 8×4 → assets/ui/icons/i_<намерение>.png, s_<состояние>.png

Фон — прозрачный или сплошной пурпурный #FF00FF (тогда край отделяется мягко: пурпур вычитается из
полупрозрачных пикселей). Картинки высокого разрешения, не пиксель-арт: сохраняются как есть, обрезанные по
содержимому.

Запуск: python tools/import_ui_art.py [--preview p.png]
"""
import os
import sys

import numpy as np
import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "art_src", "ui")
OUT = os.path.join(ROOT, "assets", "ui")
HEROES = ("merc", "hunter", "pyro")
KIT = ["corner", "edge", "fill", "portrait", "orb", "button", "ribbon", "divider", "medallion", "badge",
       "pip_on", "pip_off"]
INTENTS = ["melee", "shot", "zone", "block", "aim", "heal", "roar", "charge",
           "pull", "guard", "rally", "veil", "curse", "hex", "drown", "summon"]
STATES = ["burn", "poison", "weak", "vulnerable", "wet", "stun", "strength", "thorns",
          "momentum", "rage", "heat", "frost", "mark", "veil", "focus", "shield"]
ICONS = [f"i_{n}" for n in INTENTS] + [f"s_{n}" for n in STATES]


def load(path):
    """RGBA-массив (h, w, 4); пурпурный фон → прозрачность с мягким краем."""
    img = pygame.image.load(path)
    img = img.convert_alpha() if pygame.display.get_surface() else img
    rgb = pygame.surfarray.array3d(img).swapaxes(0, 1).astype(np.float32)
    try:
        a = pygame.surfarray.array_alpha(img).swapaxes(0, 1).astype(np.float32)
    except ValueError:
        a = np.full(rgb.shape[:2], 255.0, np.float32)
    if (a < 250).mean() < 0.05:                       # прозрачности нет — фон пурпурный
        m = np.array((255.0, 0.0, 255.0))
        d = np.sqrt(((rgb - m) ** 2).sum(-1))
        a = np.clip((d - 60) / 110, 0, 1) * 255     # близко к пурпуру — прозрачно, плавный переход
        k = (a / 255)[..., None]
        rgb = np.where(k > 0.02, (rgb - (1 - k) * m) / np.maximum(k, 0.02), 0)   # вычесть подмешанный фон
    return np.dstack([np.clip(rgb, 0, 255), np.clip(a, 0, 255)]).astype(np.uint8)


def to_surface(arr):
    h, w = arr.shape[:2]
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.surfarray.blit_array(s, arr[..., :3].swapaxes(0, 1))
    al = pygame.surfarray.pixels_alpha(s)
    al[:] = arr[..., 3].swapaxes(0, 1)
    del al
    return s


def cells(arr, cols, rows, min_area=400):
    """Детали листа: связные фигуры (альфа > 40, с небольшим расширением — тонкие части не отрываются)
    распределяются по клеткам сетки по центру масс; фигуры одной клетки — одна деталь. Детали на листах
    ChatGPT стоят не строго по клеткам — по центру надёжнее, чем резать по границам."""
    from scipy import ndimage
    h, w = arr.shape[:2]
    m = arr[..., 3] > 40
    lab, n = ndimage.label(ndimage.binary_dilation(m, iterations=1))
    ch = h / rows
    for i, sl in enumerate(ndimage.find_objects(lab)):       # слиплись соседи по высоте (шип касается
        if sl[0].stop - sl[0].start > ch * 1.25:              # детали ниже) — разрезать по границе ряда
            for r in range(1, rows):
                y = int(ch * r)
                if sl[0].start < y < sl[0].stop:
                    band = lab[y - 1:y + 1, sl[1]]
                    band[band == i + 1] = 0
    lab, n = ndimage.label(lab > 0)
    groups = {}
    for i, sl in enumerate(ndimage.find_objects(lab)):
        part = (lab[sl] == i + 1) & m[sl]
        area = int(part.sum())
        if area < min_area:
            continue
        ys, xs = np.nonzero(part)
        cy, cx = ys.mean() + sl[0].start, xs.mean() + sl[1].start
        cell = (min(rows - 1, int(cy / h * rows)), min(cols - 1, int(cx / w * cols)))
        groups.setdefault(cell, []).append((i + 1, sl, area))
    out = []
    for r in range(rows):
        for c in range(cols):
            g = groups.get((r, c))
            if not g:
                out.append(None)
                continue
            big = max(a for _, _, a in g)
            g = [x for x in g if x[2] >= big * 0.02]          # пылинки рядом с деталью — прочь
            y0 = min(sl[0].start for _, sl, _ in g)
            y1 = max(sl[0].stop for _, sl, _ in g)
            x0 = min(sl[1].start for _, sl, _ in g)
            x1 = max(sl[1].stop for _, sl, _ in g)
            piece = arr[y0:y1, x0:x1].copy()
            keep = np.isin(lab[y0:y1, x0:x1], [i for i, _, _ in g])
            piece[..., 3] = np.where(keep, piece[..., 3], 0)
            ys, xs = np.nonzero(piece[..., 3] > 8)
            out.append(piece[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    return out


def save(surf, *path):
    p = os.path.join(OUT, *path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    pygame.image.save(surf, p)


def main(preview=None):
    pygame.init()
    made = []
    for hero in HEROES:
        p = os.path.join(SRC, f"ui_{hero}.png")
        if not os.path.exists(p):
            continue
        for name, piece in zip(KIT, cells(load(p), 4, 3)):
            if piece is not None:
                s = to_surface(piece)
                save(s, hero, f"{name}.png")
                made.append(s)
        print(hero, "готово")
    p = os.path.join(SRC, "ui_icons.png")
    if os.path.exists(p):
        n = 0
        for name, piece in zip(ICONS, cells(load(p), 8, 4)):
            if piece is not None:
                s = to_surface(piece)
                save(s, "icons", f"{name}.png")
                made.append(s)
                n += 1
        print("значков:", n)
    if preview and made:
        sheet = pygame.Surface((1600, 1200))
        sheet.fill((40, 36, 32))
        x = y = rowh = 0
        for s in made:
            k = min(1.0, 180 / max(s.get_size()))
            im = pygame.transform.smoothscale(s, (max(1, int(s.get_width() * k)), max(1, int(s.get_height() * k))))
            if x + im.get_width() > 1600:
                x, y, rowh = 0, y + rowh + 8, 0
            sheet.blit(im, (x, y))
            x += im.get_width() + 8
            rowh = max(rowh, im.get_height())
        pygame.image.save(sheet, preview)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--preview") + 1] if "--preview" in sys.argv else None)
