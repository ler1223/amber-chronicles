"""Ковка (квиз 2026-11-11): плавка → пакет (тетрис) → сварка и складывание (дамаск) → разделка клином → ковка
частей по контуру и закалка; свойства металла переходят в вещь; заказы и бродячие кузнецы."""
import os
import random
import sys

import pygame

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.data import GameData  # noqa: E402
from sim import expedition as X, smithing as SM, artifacts as A  # noqa: E402
from game import smith_games as SG  # noqa: E402

DATA = GameData()
ED = X.expedition_data(DATA)
XD = ED.expedition
RECT = pygame.Rect(0, 0, 1120, 520)


def prof():
    p = X.ExpeditionProfile(ED)
    p.glory, p.mats = 99999, {m: 99 for m in XD["materials"]}
    p.buildings["ws_forge"] = 4
    return p


def smelt(p, carbon):
    g = SG.SmeltGame(1, XD)
    g.carbon = carbon
    for _ in range(int(g.dur * 30) + 2):
        g.temp = 1500                                  # держит жар в окне
        g.update(1 / 30)
    r = g.result
    return p.smelt(r["carbon"], r["heat_ok"], r["slag"])


def layered_grid(p):
    """Стол: чередовать сталь и железо по строкам (дамаск) — I-куски по 4 клетки на строку."""
    w, h = SM.frame_size(XD, "bracers")
    grid = [[None] * w for _ in range(h)]
    used = []
    for y in range(h):
        metal = "steel" if y % 2 == 0 else "iron"
        piece = SM.new_piece(XD, p.suid("p"), metal, random.Random(y), 0.85, "I")
        piece["cells"] = [[x, 0] for x in range(4)]
        p.smith["pieces"].append(piece)
        for x in range(w):
            grid[y][x] = metal
        used.append(piece["uid"])
    return grid, used


def weld_full(g):
    while g.b["weld"] < 1.0:
        g.temp = 1250
        g.strike()


def test_smelt_carbon_decides_metal():
    p = prof()
    soft = smelt(p, 0.2)
    hard = smelt(p, 0.6)
    assert soft and all(x["metal"] == "iron" for x in soft) and all(x["metal"] == "steel" for x in hard)
    assert soft[0]["purity"] > 0.7 and len(p.smith["pieces"]) == len(soft) + len(hard)


def test_stack_game_places_and_rotates():
    pygame.init()
    pcs = []
    for i, m in enumerate(("steel", "iron", "steel")):
        pc = SM.new_piece(XD, f"p{i}", m, random.Random(i), 0.8, "I")
        pc["cells"] = [[0, k] for k in range(4)]       # вертикально — придётся повернуть
        pcs.append(pc)
    g = SG.StackGame(1, XD, (), pcs, (4, 3))
    ox, oy = g.origin(RECT)
    surf = pygame.Surface((1280, 800))
    for row in range(3):
        g.draw(surf, RECT)
        r_, piece = g.inv_rects[0]
        g.pointer(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=r_.center, button=1), RECT)
        assert g.held is piece
        g.key(pygame.K_r)                              # повернуть горизонтально
        g.pointer(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(ox + 5, oy + row * g.CELL + 5), button=1), RECT)
        assert g.held is None
    g.key(pygame.K_RETURN)
    assert g.done and len(g.result["used"]) == 3
    b = SM.billet_from(XD, "b", g.result["grid"], pcs)
    assert b["voids"] == 0 and SM.pattern_score(XD, b["grid"]) == 1.0


def test_fold_multiplies_layers_and_damascus_is_tough():
    p = prof()
    grid, used = layered_grid(p)
    b = p.stack(grid, used)
    plain = SM.billet_props(XD, b)
    g = SG.WeldGame(1, XD, ("twist",), b, p.fold_max())
    for _ in range(3):                                 # сварить → сложить (без длинных клещей — до 2 раз)
        weld_full(g)
        g.key(pygame.K_f)
    weld_full(g)
    g.key(pygame.K_RETURN)
    pr = SM.billet_props(XD, g.result)
    assert g.result["folds"] == 2 and pr["layers"] == plain["layers"] * 4
    assert pr["tough"] > plain["tough"] and g.result["mass"] < b["mass"]
    cold = SG.WeldGame(1, XD, (), b, 2)
    cold.temp = 700
    cold.strike()
    assert cold.cracks == 1


def test_full_chain_makes_item_with_metal():
    p = prof()
    grid, used = layered_grid(p)
    b = p.stack(grid, used)
    g = SG.WeldGame(1, XD, (), b, p.fold_max())
    weld_full(g)
    g.key(pygame.K_f)
    weld_full(g)
    g.key(pygame.K_RETURN)
    p.store_billet(g.result)
    c = SG.CutGame(1, XD, (), g.result)
    c.cut(100)
    c.cut(100)
    c.key(pygame.K_RETURN)                             # остаток — последней частью
    parts = p.cut_parts(b["uid"], c.result["cuts"], c.result["cold"], c.result["wide"])
    assert len(parts) == 3 and abs(sum(x["mass"] for x in parts) - g.result["mass"]) <= 2
    parts = SM.match_parts(XD, "bracers", parts)
    assert SM.match_parts(XD, "bracers", p.smith["parts"]) is not None
    s = SG.ShapeGame(1, XD, (), parts, "bracers")
    s.key(pygame.K_RETURN)
    s.key(pygame.K_RETURN)
    s.temp = 820
    s.do_quench()
    sid = next(k for k, v in XD["artifacts"]["sets"].items() if v["rarity"] == "common")
    art = p.forge_item("bracers", sid, [x["uid"] for x in parts], s.result["scores"], s.result["quench"])
    assert art and art["metal"]["layers"] >= 6 and len(p.smith["parts"]) == 1      # остаток бруска — остался
    mods, extra, _ = A.effects(XD, [art])
    assert any(m.get("stat") == "hp" for m in mods)
    assert any("Металл" in ln for ln in A.art_lines(XD, art))


def test_shaping_rewards_spreading_to_contour():
    g = SG.ShapeGame(1, XD, (), [{"mass": 100}], "belt")
    start = g.part_score()
    vol0 = sum(map(sum, g.th))
    for _ in range(1500):
        best = None
        for y in range(g.GH):
            for x in range(g.GW):
                v = g.th[y][x]
                if g.mask[y][x]:
                    if v < 1.08:
                        continue
                    sc = v - 1
                else:
                    if v < 0.3:
                        continue
                    sc = v * 3
                if best is None or sc > best[0]:
                    best = (sc, x, y)
        if best is None:
            break
        g.temp = 1100
        g.strike(best[1] + 0.5, best[2] + 0.5)
    assert g.part_score() > start + 0.3
    assert abs(sum(map(sum, g.th)) - vol0) < 1.0       # металл не берётся из ниоткуда


def test_orders_and_wanderer(tmp_path):
    p = X.ExpeditionProfile(ED, str(tmp_path / "e.json"))
    p.glory = 9999
    assert p.smith["orders"]
    o = p.smith["orders"][0]
    sid = next(k for k, v in XD["artifacts"]["sets"].items() if v["rarity"] == "common")
    p.buildings["ws_forge"] = 1
    p.mats = {m: 99 for m in XD["materials"]}
    art = p.craft("ws_forge", o["kind"], sid, 1.3)
    art["metal"] = {"hard": 0.9, "tough": 0.9, "layers": 64, "pattern": 1.0}
    gold = p.glory
    assert p.fulfil(o["id"], art["uid"]) and p.glory == gold + o["gold"] and art["uid"] not in p.stash
    w = SM.roll_wanderer(dict(XD, smithing=dict(SM.cfg(XD), wanderer=dict(SM.cfg(XD)["wanderer"], chance=1.0))),
                         random.Random(2), [], lambda: p.suid("p"))
    p.market["smith"] = w
    tid = w["tools"][0]
    assert p.buy_tool(tid) and p.has_tool(tid)
    pc = w["pieces"][0]
    assert p.buy_piece(pc["uid"]) and any(x["metal"] == pc["metal"] for x in p.smith["pieces"])


def test_forge_station_tabs_draw(tmp_path):
    from tests.test_expedition_ui import new_app, frame, key
    from game import tavern_rooms as R
    app = new_app(tmp_path)
    p = app.profile
    p.sandbox_fill()
    key(app, pygame.K_3)
    room = app.scene
    room.act(("station", "ws_forge"))
    assert isinstance(room.overlay, R.SmithOverlay)
    for m, _ in R.SMITH_MODES:
        room.act(("mode", m))
        frame(app)
    room.act(("mode", "smelt"))
    key(app, pygame.K_RETURN)
    assert type(app.scene.game).__name__ == "SmeltGame"


def test_free_cut_any_number_of_pieces():
    """Разделка свободная: брусок 500 г — на сколько угодно кусков любой массы, ничего не пропадает."""
    p = prof()
    grid = [["steel"] * 5, ["iron"] * 5, ["steel"] * 5, ["iron"] * 5]
    b = SM.billet_from(XD, "bb", grid, [{"purity": 0.9, "cells": [[0, 0]] * 20}])
    b["welded"], b["weld"] = True, 1.0
    p.smith["billets"].append(b)
    c = SG.CutGame(1, XD, (), b)
    for m in (50, 50, 50, 50, 100, 100):
        c.cut(m)
    c.key(pygame.K_RETURN)
    parts = p.cut_parts("bb", c.result["cuts"], c.result["cold"])
    assert len(parts) == 7 and abs(sum(x["mass"] for x in parts) - 500) <= 2
    assert SM.match_parts(XD, "belt", parts) and SM.match_parts(XD, "bracers", parts)


def test_gaps_in_frame_are_not_pores():
    """Пустые клетки рамки — не поры: слиток цельный, просто легче."""
    full = SM.billet_from(XD, "a", [["steel"] * 4, ["iron"] * 4, ["steel"] * 4], [{"purity": 0.8, "cells": [[0, 0]] * 12}])
    holes = SM.billet_from(XD, "b", [["steel", None, "steel", None], ["iron"] * 4, [None] * 4],
                           [{"purity": 0.8, "cells": [[0, 0]] * 6}])
    assert holes["voids"] == 0 and holes["mass"] < full["mass"] and holes["layers"] == 2
    assert all(m for r in holes["grid"] for m in r)
    assert SM.prep_quality(XD, dict(holes, weld=1.0)) == SM.prep_quality(XD, dict(full, weld=1.0))


def test_heavier_parts_are_fine_and_show_in_forging():
    """Части тяжелее нужного годятся: при ковке металла больше, вещь массивнее (немного здоровья), без штрафа."""
    look = {"rows": [["steel"] * 4], "folds": 0, "twist": 0}
    props = {"hard": 0.6, "tough": 0.6, "layers": 3, "pattern": 0.0}
    light = [{"uid": "a", "mass": 100, "q0": 0.9, "props": props, "look": look},
             {"uid": "b", "mass": 100, "q0": 0.9, "props": props, "look": look}]
    heavy = [dict(x, uid=x["uid"] + "h", mass=140) for x in light]
    assert SM.match_parts(XD, "bracers", heavy) is not None
    assert SM.match_parts(XD, "bracers", [dict(x, mass=70) for x in light]) is None      # сильно легче — нет
    g1 = SG.ShapeGame(1, XD, (), light, "bracers")
    g2 = SG.ShapeGame(1, XD, (), heavy, "bracers")
    assert sum(map(sum, g2.th)) > sum(map(sum, g1.th)) * 1.3
    assert SM.final_quality(XD, heavy, [0.8, 0.8], "bracers") >= SM.final_quality(XD, light, [0.8, 0.8], "bracers")
    assert SM.mass_bonus(heavy, [100, 100]) > 0 == SM.mass_bonus(light, [100, 100])
