"""Импорт листов живого поля «Спуска» (prompts_expedition.md, раздел DC3).

Из assets/art_src/field/ (картинки ChatGPT на пурпурном #FF00FF, 1 пиксель арта = 4×4 пикселя картинки)
делает assets/field/: детали в масштабе 1 пиксель арта = 1 пиксель (плоская карта земли — 64 на клетку):
  ground/<имя>.png   — сор на земле (вид сверху): камни, ветки, кости, мох, листья, лужи…
  plants/<имя>.png   — трава, цветы, камыши (стоят на земле; основание — нижний край)
  water/<имя>.png    — кувшинки, ряска, коряги, кромки берега (вид сверху)
  critters/<анимация>_<кадр>.png — ворона (полёт, взлёт), птичка, стрекоза, мотылёк, лягушка, рыба

Запуск: python tools/import_field_art.py [--preview p.png]
"""
import os
import sys

import numpy as np
import pygame
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from import_card_art import blob_list, load_rgba, pieces, to_surface  # noqa: E402

SRC = os.path.join(ROOT, "assets", "art_src", "field")
OUT = os.path.join(ROOT, "assets", "field")
K = 0.25                                     # 4×4 пикселя картинки → 1 пиксель арта

GROUND = ["pebbles", "gravel", "mossy_stone", "two_stones", "slab", "tiny_pebbles",
          "branch", "twigs", "log_chunk", "chips", "skull", "bones",
          "moss", "clover", "leaves_rust", "leaves_green", "roots", "mushroom_ring",
          "mud", "footprints", "puddle", "peat", "dry_sedge", "feathers"]
PLANTS = ["grass_s", "grass_m", "grass_tall", "grass_dry", "grass_wide", "blades",
          "sedge", "fern_young", "fern", "horsetail", "thistle", "weed",
          "flowers_white", "marigold", "loosestrife", "bell", "forgetmenot", "berries",
          "reeds", "cattails", "reeds_bent", "bush_round", "bush_dead", "reeds_tall"]
WATER = ["lily", "lily_two", "lily_white", "lily_pink",
         "duckweed", "duckweed_trail", "leaves_float", "log_float",
         "shore_mud", "shore_roots", "stone_sunk", "stone_moss",
         "drowned_branch", "bubbles", "algae", "reed_stubs"]
CRITTERS = [("crow_fly", 6), ("crow_takeoff", 4), ("bird", 4), ("dragonfly", 2), ("moth", 3), ("frog", 2),
            ("fish", 4)]


def small(arr):
    """Кусок листа → пиксель-арт 1:1 (усреднение блока 4×4, края альфы — чётко)."""
    h, w = arr.shape[:2]
    oh, ow = max(1, round(h * K)), max(1, round(w * K))
    f = arr.astype(np.float32)
    al = f[..., 3:4] / 255.0
    f[..., :3] *= al                                        # усреднение с учётом прозрачности — фон не подмешивается
    ys = np.linspace(0, h, oh + 1).astype(int)
    xs = np.linspace(0, w, ow + 1).astype(int)
    sums = np.add.reduceat(np.add.reduceat(f, ys[:-1], axis=0), xs[:-1], axis=1)
    cnt = np.diff(ys)[:, None, None] * np.diff(xs)[None, :, None]
    m = sums / cnt
    a = m[..., 3:4]
    rgb = np.where(a > 1, m[..., :3] / np.maximum(a / 255.0, 1e-3), 0)
    alpha = np.where(m[..., 3] > 110, 255, 0)              # пиксель-арт: без полупрозрачной каймы
    out = np.dstack([np.clip(rgb, 0, 255), alpha]).astype(np.uint8)
    return to_surface(out)


def trim(s):
    r = s.get_bounding_rect()
    return s.subsurface(r).copy() if r.w and r.h else s


def save(surf, *path):
    p = os.path.join(OUT, *path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    pygame.image.save(surf, p)


def critter_rows(arr):
    """Лист живности: кадры по рядам (по высоте), в ряду — слева направо. Куски одного кадра (брызги под
    рыбой, комья под вороной) склеиваются: в ряду они перекрываются по горизонтали."""
    m = arr[..., 3] > 40
    lab, n = ndimage.label(ndimage.binary_dilation(m, iterations=4))
    boxes = []
    for i, sl in enumerate(ndimage.find_objects(lab)):
        if ((lab[sl] == i + 1) & m[sl]).sum() < 120:
            continue
        boxes.append([sl[1].start, sl[0].start, sl[1].stop, sl[0].stop, i + 1])
    boxes.sort(key=lambda b: (b[1] + b[3]) / 2)
    rows, cur = [], []
    for b in boxes:                                           # ряды: по центру по высоте
        if cur and (b[1] + b[3]) / 2 - (cur[-1][1] + cur[-1][3]) / 2 > 70:
            rows.append(cur)
            cur = []
        cur.append(b)
    if cur:
        rows.append(cur)
    out = []
    for r in rows:
        r.sort(key=lambda b: b[0])
        merged = []
        for b in r:                                            # перекрываются по x — один кадр
            if merged and b[0] <= merged[-1][2] + 6:
                a = merged[-1]
                merged[-1] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]), a[4] + [b[4]]]
            else:
                merged.append(b[:4] + [[b[4]]])
        for x0, y0, x1, y1, ids in merged:
            piece = arr[y0:y1, x0:x1].copy()
            keep = np.isin(lab[y0:y1, x0:x1], ids) & m[y0:y1, x0:x1]
            piece[..., 3] = np.where(keep, piece[..., 3], 0)
            out.append(piece)
    return out


def unpink(img):
    """Пурпур фона, подмешанный в размытые крылья, — в светло-голубой (только живность)."""
    px = pygame.surfarray.pixels3d(img)
    r, g, b = px[..., 0].astype(int), px[..., 1].astype(int), px[..., 2].astype(int)
    pink = ((r + b) // 2 - g > 45) & (abs(r - b) < 90)
    px[pink] = (190, 214, 226)
    del px
    return img


def main(preview=None):
    pygame.init()
    made = {}
    for name, names, grid in (("ground", GROUND, (4, 6)), ("plants", PLANTS, (4, 6)), ("water", WATER, (4, 4))):
        p = os.path.join(SRC, f"field_{name}.png")
        if not os.path.exists(p):
            continue
        ps = pieces(load_rgba(p), *grid, min_area=150)
        for n, piece in zip(names, ps):
            if piece is not None:
                img = trim(small(piece))
                save(img, name, f"{n}.png")
                made.setdefault(name, []).append(img)
    p = os.path.join(SRC, "field_critters.png")
    if os.path.exists(p):
        frames = critter_rows(load_rgba(p))
        i = 0
        for anim, n in CRITTERS:
            for k in range(n):
                if i < len(frames):
                    img = unpink(trim(small(frames[i])))
                    save(img, "critters", f"{anim}_{k}.png")
                    made.setdefault("critters", []).append(img)
                i += 1
        print("кадров живности:", len(frames), "ожидалось:", sum(n for _, n in CRITTERS))
    for k, v in made.items():
        print(k, len(v))
    if preview:
        sheet = pygame.Surface((1000, 1000))
        sheet.fill((70, 80, 60))
        y = 10
        for k, imgs in made.items():
            x, rowh = 10, 0
            for img in imgs:
                im = pygame.transform.scale(img, (img.get_width() * 3, img.get_height() * 3))
                if x + im.get_width() > 990:
                    x, y = 10, y + rowh + 6
                    rowh = 0
                sheet.blit(im, (x, y))
                x += im.get_width() + 6
                rowh = max(rowh, im.get_height())
            y += rowh + 14
        pygame.image.save(sheet, preview)


if __name__ == "__main__":
    pv = sys.argv[sys.argv.index("--preview") + 1] if "--preview" in sys.argv else None
    main(pv)
