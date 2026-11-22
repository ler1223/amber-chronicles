"""Импорт пиксельного оформления карт «Спуска» (prompts_expedition.md, раздел DC2).

Из assets/art_src/cards/ (картинки ChatGPT на пурпурном #FF00FF) делает assets/cards/:
  frame_<тип>.png   — основы рамок 512×768 (окна вырезаны), тип: attack / skill / power / reaction;
  frames.json       — разметка каждой рамки в координатах 512×768: окно картинки, лента имени, плашка текста,
                      полоса простого, бороздка прозрения, гнездо цены (центр и радиус);
  parts/<тип>_<деталь>.png — накладки рамки (уголок, навершие, кольцо цены, конец ленты, заклёпки, планка);
  ui/<плашка>.png   — плашка текста, полоса простого, бороздка, золотая полоска;
  icons/<значок>.png — цена, теги, флажки богов;
  back_<герой>.png  — рубашки 512×768.

Пурпур вырезается с мягким краем и без розовой каймы. Масштаб ×0.5: в исходниках пиксель арта ≈ 4×4, в игре —
2×2 на лице карты 512×768.

Запуск: python tools/import_card_art.py [--preview p.png]
"""
import json
import os
import sys

import numpy as np
import pygame
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "art_src", "cards")
OUT = os.path.join(ROOT, "assets", "cards")
TYPES = ("attack", "skill", "power", "reaction")
PARTS = ("corner", "crest", "ring", "cap", "studs", "bar")
ICONS = ["energy", "heat", "react", "socket", "insight", "seal",
         "Удар", "Шаг", "Толчок", "Защита", "Шипы", "Кровь",
         "Клич", "Огонь", "Выстрел", "Метка", "Яд", "Ловушка",
         "god_gorn", "god_ash", "god_path", "god_twin", "god_shade", "god_none"]
PLATES = ("banner", "text", "alt", "groove", "fill")
GODS = ("perun", "svarog", "stribog", "yarilo", "veles", "mokosh", "morana", "chernobog")
K = 0.5                                     # 1024 → 512


def load_rgba(path):
    """Картинка → массив (h, w, 4) с вырезанным пурпуром."""
    im = pygame.image.load(path)
    a = pygame.surfarray.array3d(im).transpose(1, 0, 2).astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    key = ((r + b) / 2 - g)                 # «пурпурность»
    even = np.abs(r - b) < 80
    alpha = np.clip((150 - key) / 60, 0, 1)  # 210+ — пусто, 90− — непрозрачно, между — край
    alpha = np.where(even, alpha, 1.0)
    edge = (alpha < 1) & (alpha > 0)        # кайма: убрать пурпур из цвета
    m = np.minimum(r, b)
    spill = np.clip(m - g, 0, None) * 0.8
    a[..., 0] = np.where(edge, r - spill, r)
    a[..., 2] = np.where(edge, b - spill, b)
    out = np.dstack([np.clip(a, 0, 255), alpha * 255]).astype(np.uint8)
    return out


def to_surface(arr):
    h, w = arr.shape[:2]
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.surfarray.pixels3d(s)[:] = arr[..., :3].transpose(1, 0, 2)
    pygame.surfarray.pixels_alpha(s)[:] = arr[..., 3].T
    return s


def scaled(surf, k=K):
    w, h = surf.get_size()
    return pygame.transform.smoothscale(surf, (max(1, round(w * k)), max(1, round(h * k))))


def holes(alpha):
    """Окна рамки: прозрачные области внутри карты (без внешней), сверху вниз."""
    lab, n = ndimage.label(alpha < 128)
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab)):
        ys, xs = sl
        if xs.start == 0 and ys.start == 0:          # снаружи карты
            continue
        if (lab[sl] == i + 1).sum() < 4000:
            continue
        out.append([xs.start, ys.start, xs.stop - xs.start, ys.stop - ys.start])
    return sorted(out, key=lambda r: r[1])


def socket(rgb):
    """Гнездо цены: самый большой вписанный тёмный круг в верхнем левом углу."""
    sub = rgb[0:320, 0:320].astype(int)
    br = sub.sum(axis=2)
    sat = sub.max(axis=2) - sub.min(axis=2)
    dt = ndimage.distance_transform_edt((br < 170) & (sat < 50))
    y, x = np.unravel_index(np.argmax(dt), dt.shape)
    return int(x), int(y), float(dt.max())


def banner(rgb, top, bottom):
    """Лента имени: светлый пергамент между окном и плашкой текста."""
    sub = rgb[top:bottom].astype(int)
    r, g, b = sub[..., 0], sub[..., 1], sub[..., 2]
    m = (r > 150) & (g > 120) & (b > 70) & (r > b + 30)
    cnt = m.sum(axis=1)
    rows = np.nonzero(cnt > 0.6 * cnt.max())[0]                   # широкая часть ленты, без хвостов
    if not len(rows):
        return None
    segs = np.split(rows, np.nonzero(np.diff(rows) > 3)[0] + 1)  # самый длинный сплошной кусок — лента;
    rows = max(segs, key=len)                                     # планка и кромки ниже не в счёт
    band = m[rows.min():rows.max() + 1]
    cols = np.nonzero(band.sum(axis=0) > max(1, len(rows) * 0.3))[0]
    return [int(cols.min()), int(top + rows.min()), int(cols.max() - cols.min()), int(rows.max() - rows.min())]


def groove(rgb, y0, y1, x0, x1):
    """Бороздка прозрения: самая тёмная строка между плашкой текста и полосой простого."""
    band = rgb[y0:y1, x0 + (x1 - x0) // 4:x1 - (x1 - x0) // 4].astype(int).sum(axis=2).mean(axis=1)
    return y0 + int(np.argmin(band))


def pieces(arr, rows, cols, min_area=300):
    """Лист деталей сеткой rows×cols: в каждой ячейке — самая большая деталь (с мелкими рядом)."""
    h, w = arr.shape[:2]
    out = []
    for i in range(rows):
        for j in range(cols):
            cell = arr[i * h // rows:(i + 1) * h // rows, j * w // cols:(j + 1) * w // cols]
            m = cell[..., 3] > 40
            lab, n = ndimage.label(ndimage.binary_dilation(m, iterations=6))
            if not n:
                out.append(None)
                continue
            sizes = ndimage.sum(m, lab, range(1, n + 1))
            keep = [k + 1 for k, s in enumerate(sizes) if s >= min_area]
            mm = np.isin(lab, keep) & m
            ys, xs = np.nonzero(mm)
            piece = cell[ys.min():ys.max() + 1, xs.min():xs.max() + 1].copy()
            piece[..., 3] = np.where(mm[ys.min():ys.max() + 1, xs.min():xs.max() + 1], piece[..., 3], 0)
            out.append(piece)
    return out


def blob_list(arr, min_area=300, merge=3):
    """Детали листа: [(центр y, левый x, картинка)]; merge — на сколько склеивать близкие кусочки."""
    m = arr[..., 3] > 40
    lab, n = ndimage.label(ndimage.binary_dilation(m, iterations=merge))
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab)):
        mm = (lab[sl] == i + 1) & m[sl]
        if mm.sum() < min_area:
            continue
        p = arr[sl].copy()
        p[..., 3] = np.where(mm, p[..., 3], 0)
        out.append(((sl[0].start + sl[0].stop) / 2, sl[1].start, p))
    return out


def blobs(arr, min_area=300):
    """Отдельные детали листа (плашки), сверху вниз, слева направо."""
    m = arr[..., 3] > 40
    lab, n = ndimage.label(ndimage.binary_dilation(m, iterations=3))
    found = []
    for i, sl in enumerate(ndimage.find_objects(lab)):
        mm = (lab[sl] == i + 1) & m[sl]
        if mm.sum() < min_area:
            continue
        p = arr[sl].copy()
        p[..., 3] = np.where(mm, p[..., 3], 0)
        found.append((sl[0].start, sl[1].start, p))
    found.sort(key=lambda t: (round(t[0] / 60), t[1]))
    return [p for _, _, p in found]


def save(surf, *path):
    p = os.path.join(OUT, *path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    pygame.image.save(surf, p)
    return p


def main(preview=None):
    pygame.init()
    os.makedirs(OUT, exist_ok=True)
    meta = {"_doc": "Разметка рамок карт в координатах лица 512×768 (tools/import_card_art.py).", "frames": {}}
    for t in TYPES:
        path = os.path.join(SRC, f"frame_{t}.png")
        if not os.path.exists(path):
            continue
        arr = load_rgba(path)
        rgb = arr[..., :3]
        hs = holes(arr[..., 3])
        assert len(hs) >= 3, (t, hs)
        win, text, alt = hs[0], hs[1], hs[-1]
        sx, sy, sr = socket(rgb)
        ban = banner(rgb, win[1] + win[3] - 120, text[1])
        groove_y = groove(rgb, text[1] + text[3] + 4, alt[1] - 4, text[0], text[0] + text[2])
        save(scaled(to_surface(arr)), f"frame_{t}.png")
        h = lambda r: [round(v * K) for v in r]                          # noqa: E731
        meta["frames"][t] = {"window": h(win), "text": h(text), "alt": h(alt), "banner": h(ban) if ban else None,
                             "groove_y": round(groove_y * K), "socket": [round(sx * K), round(sy * K),
                                                                          round(sr * K)],
                             "tags_y": round(((ban[1] + ban[3]) if ban else win[1] + win[3]) * K / 2 +
                                             text[1] * K / 2)}
    p = os.path.join(SRC, "frame_parts.png")
    if os.path.exists(p):                              # детали стоят не по ровной сетке: ряды по высоте, в ряду по x
        found = blob_list(load_rgba(p), merge=12)
        found.sort(key=lambda t: t[0])
        rows = [found[k:k + len(PARTS)] for k in range(0, len(found), len(PARTS))]
        assert len(found) == len(TYPES) * len(PARTS), len(found)
        for t, row in zip(TYPES, rows):
            for name, (_, _, piece) in zip(PARTS, sorted(row, key=lambda q: q[1])):
                save(scaled(to_surface(piece)), "parts", f"{t}_{name}.png")
    p = os.path.join(SRC, "ui_icons.png")
    if os.path.exists(p):
        for name, piece in zip(ICONS, pieces(load_rgba(p), 4, 6)):
            if piece is not None:
                save(scaled(to_surface(piece)), "icons", f"{name}.png")
    p = os.path.join(SRC, "gods_slavic.png")         # славянский пантеон (DC5): 8 вымпелов, сетка 4×2
    if os.path.exists(p):
        for name, piece in zip(GODS, pieces(load_rgba(p), 2, 4)):
            if piece is not None:
                save(scaled(to_surface(piece)), "icons", f"god_{name}.png")
    p = os.path.join(SRC, "ui_plates.png")
    if os.path.exists(p):
        for name, piece in zip(PLATES, blobs(load_rgba(p))):
            save(scaled(to_surface(piece)), "ui", f"{name}.png")
    for hero in ("merc", "hunter", "pyro"):
        p = os.path.join(SRC, f"back_{hero}.png")
        if os.path.exists(p):
            save(scaled(to_surface(load_rgba(p))), f"back_{hero}.png")
    with open(os.path.join(OUT, "frames.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(json.dumps(meta["frames"], ensure_ascii=False, indent=1))
    if preview:
        sheet = pygame.Surface((512 * 4 + 50, 768 + 20))
        sheet.fill((40, 40, 40))
        for i, t in enumerate(TYPES):
            fp = os.path.join(OUT, f"frame_{t}.png")
            if not os.path.exists(fp):
                continue
            img = pygame.image.load(fp)
            x0 = 10 + i * 522
            sheet.blit(img, (x0, 10))
            m = meta["frames"][t]
            for key, col in (("window", (0, 255, 0)), ("text", (0, 200, 255)), ("alt", (255, 255, 0)),
                             ("banner", (255, 0, 0))):
                if m.get(key):
                    x, y, w, hh = m[key]
                    pygame.draw.rect(sheet, col, (x0 + x, 10 + y, w, hh), 2)
            cx, cy, r = m["socket"]
            pygame.draw.circle(sheet, (255, 0, 255), (x0 + cx, 10 + cy), r, 2)
            pygame.draw.line(sheet, (255, 128, 0), (x0, 10 + m["groove_y"]), (x0 + 512, 10 + m["groove_y"]), 1)
        pygame.image.save(sheet, preview)


if __name__ == "__main__":
    pv = sys.argv[sys.argv.index("--preview") + 1] if "--preview" in sys.argv else None
    main(pv)
