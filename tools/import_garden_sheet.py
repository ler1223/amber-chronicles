"""Нарезка листа сада на 18 PNG для `assets/sprites/garden/`.

  python tools/import_garden_sheet.py assets/art_src/sheet_garden.png assets/sprites/garden

Лист: 3 колонки (стадии 0, 1, 2) × 6 рядов (sunleaf, moonroot, thornbud,
starflower, emberfern, frostbell). Спрайты ищутся как крупные связные
компоненты, поэтому мелкие искры и лепестки приклеиваются к ближайшему
растению, а не режутся по ровной сетке. Пурпурный фон вырезается flood-fill
от краёв — розовые цветы тернового бутона остаются целыми.
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

NAMES = ("sunleaf", "moonroot", "thornbud", "starflower", "emberfern", "frostbell")
COLS, ROWS = 3, 6
BG = np.array([255, 0, 255])
MAIN_AREA = 500
MIN_AREA = 20


def _components(rgb):
    near = np.abs(rgb.astype(int) - BG).sum(2) < 110
    labels, _ = ndimage.label(near)
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
    bg = np.isin(labels, list(border))
    fg = ~bg
    fl, _ = ndimage.label(fg, structure=np.ones((3, 3)))
    out = []
    for i, sl in enumerate(ndimage.find_objects(fl), 1):
        if sl is None:
            continue
        area = int((fl[sl] == i).sum())
        if area < MIN_AREA:
            continue
        y0, y1 = sl[0].start, sl[0].stop
        x0, x1 = sl[1].start, sl[1].stop
        out.append({"label": i, "area": area, "box": (x0, y0, x1, y1),
                    "cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2})
    return fl, fg, out


def cut(src, dst_dir):
    os.makedirs(dst_dir, exist_ok=True)
    rgb = np.array(Image.open(src).convert("RGB"))
    # Точный фон (включая замкнутые дырки между стеблями) убираем отдельно.
    bg_exact = np.abs(rgb.astype(int) - BG).sum(2) < 60
    fl, fg, comps = _components(rgb)
    mains = [c for c in comps if c["area"] >= MAIN_AREA]
    small = [c for c in comps if c["area"] < MAIN_AREA]
    if len(mains) != COLS * ROWS:
        raise SystemExit(f"ожидалось {COLS * ROWS} крупных растений, найдено {len(mains)}")
    by_col = [[] for _ in range(COLS)]
    for c in mains:
        col = 0 if c["cx"] < rgb.shape[1] / 3 else 1 if c["cx"] < rgb.shape[1] * 2 / 3 else 2
        by_col[col].append(c)
    for col, items in enumerate(by_col):
        items.sort(key=lambda c: c["cy"])
        if len(items) != ROWS:
            raise SystemExit(f"в колонке {col} не {ROWS} растений: {len(items)}")
    # Мелкие искры/лепестки — к ближайшему крупному растению.
    for s in small:
        owner = min(mains, key=lambda m: (m["cx"] - s["cx"]) ** 2 + (m["cy"] - s["cy"]) ** 2)
        owner.setdefault("extra", []).append(s)

    for col, items in enumerate(by_col):
        for row, main in enumerate(items):
            members = [main] + main.get("extra", [])
            x0 = min(c["box"][0] for c in members)
            y0 = min(c["box"][1] for c in members)
            x1 = max(c["box"][2] for c in members)
            y1 = max(c["box"][3] for c in members)
            keep = np.isin(fl, [c["label"] for c in members]) & ~bg_exact
            rgba = np.dstack([rgb, (keep * 255).astype(np.uint8)])
            img = Image.fromarray(rgba, "RGBA").crop((x0, y0, x1, y1))
            if max(img.size) > 128:
                img.thumbnail((128, 128), Image.Resampling.LANCZOS)
            out = os.path.join(dst_dir, f"{NAMES[row]}_{col}.png")
            img.save(out)
            print(f"{out}: {img.width}×{img.height}")


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join("assets", "art_src", "sheet_garden.png")
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join("assets", "sprites", "garden")
    cut(src, dst)
