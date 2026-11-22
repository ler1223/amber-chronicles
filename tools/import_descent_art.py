"""Импорт листов «Спуска» из prompts_expedition.md: иллюстрации новых карт (DC6) и значки предметов (DC7).

  python tools/import_descent_art.py лист.png --set dc6_m1 [--preview p.png]
  python tools/import_descent_art.py лист.png --set dc7_items1 [--preview p.png]

Иллюстрации карт (dc6_*): лист — равная сетка, ячейки разделены тонкими чёрными линиями; каждая ячейка
обрезается по краю, сохраняется в assets/illustrations/hd/card_<id>.png. Игра (deck/model.load) сама берёт
её вместо фрагмента иллюстрации события.

Значки предметов (dc7_*): лист на пурпуре #FF00FF, сетка 8×4; в каждой ячейке значок вырезается по своему
краю, вписывается в 128×128 и сохраняется в assets/ui/items/<id>.png — сумка и полоска предметов берут его
вместо общего значка.
"""
import argparse
import os
import sys

import numpy as np
import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from import_card_art import load_rgba, to_surface  # noqa: E402

ILL = os.path.join(ROOT, "assets", "illustrations", "hd")
ITEMS = os.path.join(ROOT, "assets", "ui", "items")

# сетка (колонки, ряды) и id по порядку: слева направо, сверху вниз
SETS = {
    "dc6_m1": (4, 3, ["m_rend", "m_open", "m_blade_storm", "m_duelist", "m_riposte", "m_meet", "m_rising",
                      "m_crush", "m_leader_cry", "m_limit", "m_knives", "m_blood_trail"]),
    "dc6_m2": (3, 2, ["m_frenzy", "m_runner", "m_last_word", "m_unbreak", "m_butcher", "t_knife"]),
    "dc6_h1": (4, 3, ["h_jagged", "h_tendon", "h_pierce", "h_barrage", "h_full_quiver", "h_rain", "h_spikes",
                      "h_pit", "h_net", "h_finish", "h_patience", "h_master_quiver"]),
    "dc6_h2": (3, 2, ["h_toxic", "h_deadeye", "h_knife", "h_ambush2", "h_lure", "arrow"]),
    "dc6_p1": (4, 3, ["p_chain", "p_grenade", "p_oil", "p_sparks", "p_eternal", "p_ash_eater", "p_spark_forge",
                      "p_heart", "p_sacrifice", "p_whip", "p_keg", "p_fire_rain"]),
    "dc6_p2": (4, 2, ["p_melt", "p_smoke", "p_sun", "p_geyser", "p_flame_armor", "p_burnout", "t_spark",
                      "slime_rot"]),
    "dc7_items1": (8, 4, ["pen_nib", "horn_cleat", "wheel", "bog_flower", "puzzle", "inkwell", "spin_top",
                          "war_treatise", "pocketwatch", "fan", "letter_knife", "shuriken", "kunai", "sundial",
                          "red_skull", "gremlin_horn", "charon_ash", "dry_branch", "herb_pills", "last_stand",
                          "bandage", "boots", "still_pool", "fort_stone", "blood_vial", "fate_thread",
                          "lizard_tail", "censer", "nunchaku", "two_faced", "bells", "snake_skull"]),
    "dc7_items2": (8, 4, ["calendar", "black_crown", "velvet_collar", "kettle", "cursed_key", "rune_pyramid",
                          "phylactery", "greed_eye", "m_whet", "m_gutter", "m_mirror", "m_heavy_shield", "m_trophy",
                          "m_spurs", "h_raven", "h_horn", "h_owl", "h_hide", "h_fang", "h_quiver", "p_crucible",
                          "p_flint", "p_urn", "p_salamander", "p_melt", "p_cold_heart", "i_beads", "i_bear",
                          "i_candle"]),
}


def cut_cards(path, cols, rows, ids):
    """Равная сетка с чёрными линиями: каждая ячейка — без линий и тёмных полей по краю."""
    im = pygame.image.load(path)
    W, H = im.get_size()
    out = []
    for k, cid in enumerate(ids):
        c, r = k % cols, k // cols
        x0, x1 = round(c * W / cols), round((c + 1) * W / cols)
        y0, y1 = round(r * H / rows), round((r + 1) * H / rows)
        cell = pygame.surfarray.array3d(im.subsurface((x0, y0, x1 - x0, y1 - y0))).transpose(1, 0, 2)
        lum = cell.astype(np.float32).mean(axis=2)
        rows_ok = np.where(lum.mean(axis=1) > 18)[0]                 # срезать тёмные полосы разделителей
        cols_ok = np.where(lum.mean(axis=0) > 18)[0]
        if len(rows_ok) and len(cols_ok):
            t, b = rows_ok[0], rows_ok[-1] + 1
            lft, rgt = cols_ok[0], cols_ok[-1] + 1
            cell = cell[t:b, lft:rgt]
        pad = max(2, round(min(cell.shape[:2]) * 0.01))
        cell = cell[pad:-pad, pad:-pad]
        s = pygame.surfarray.make_surface(np.ascontiguousarray(cell.transpose(1, 0, 2)))
        dst = os.path.join(ILL, f"card_{cid}.png")
        pygame.image.save(s, dst)
        out.append((cid, s))
    return out


def cut_items(path, cols, rows, ids, size=128):
    """Пурпурный лист значков: каждый — по своему краю, вписан в size×size."""
    arr = load_rgba(path)
    H, W = arr.shape[:2]
    os.makedirs(ITEMS, exist_ok=True)
    out = []
    for k, iid in enumerate(ids):
        c, r = k % cols, k // cols
        x0, x1 = round(c * W / cols), round((c + 1) * W / cols)
        y0, y1 = round(r * H / rows), round((r + 1) * H / rows)
        cell = arr[y0:y1, x0:x1]
        ys, xs = np.where(cell[..., 3] > 40)
        if not len(ys):
            print("пусто:", iid)
            continue
        cell = cell[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        s = to_surface(np.ascontiguousarray(cell))
        k2 = (size * 0.9) / max(s.get_size())
        s = pygame.transform.smoothscale(s, (max(1, round(s.get_width() * k2)), max(1, round(s.get_height() * k2))))
        icon = pygame.Surface((size, size), pygame.SRCALPHA)
        icon.blit(s, ((size - s.get_width()) // 2, (size - s.get_height()) // 2))
        pygame.image.save(icon, os.path.join(ITEMS, f"{iid}.png"))
        out.append((iid, icon))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("--set", required=True, choices=sorted(SETS))
    ap.add_argument("--preview")
    a = ap.parse_args()
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((1, 1))
    cols, rows, ids = SETS[a.set]
    done = cut_items(a.sheet, cols, rows, ids) if a.set.startswith("dc7") else cut_cards(a.sheet, cols, rows, ids)
    print(f"{a.set}: {len(done)} из {len(ids)}")
    if a.preview and done:
        tw = 160
        th = max(round(s.get_height() * tw / s.get_width()) for _, s in done)
        pv = pygame.Surface((tw * cols + 8 * (cols + 1), (th + 8) * rows + 8))
        pv.fill((40, 34, 30))
        for k, (_, s) in enumerate(done):
            img = pygame.transform.smoothscale(s, (tw, round(s.get_height() * tw / s.get_width())))
            pv.blit(img, (8 + (k % cols) * (tw + 8), 8 + (k // cols) * (th + 8)))
        pygame.image.save(pv, a.preview)


if __name__ == "__main__":
    main()
