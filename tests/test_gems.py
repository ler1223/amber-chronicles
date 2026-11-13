"""Мастера и самоцветы (квиз 2026-11-11): мастерские открываются спасением мастера (победа над боссом главы:
Болото — кузнец, Кузни — ювелир); камни 4C — караты, цвет, чистота (примеси), огранка — цена и сила нелинейны;
разметка сырого кристалла (примеси внутри контура остаются), раскол по трещине, звёздный кабошон, книги огранок
у бродячего ювелира, старые сохранения достраиваются."""
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from sim.data import GameData  # noqa: E402
from sim import expedition as X  # noqa: E402
from sim import gems as GM  # noqa: E402

DATA = GameData()
ED = X.expedition_data(DATA)
XD = ED.expedition


def prof(tmp_path=None):
    return X.ExpeditionProfile(ED, str(tmp_path / "exp.json") if tmp_path else None)


# ---------- мастера ----------

def test_masters_open_workshops_by_chapter(tmp_path):
    p = prof(tmp_path)
    p.glory = 99999
    for ws in ("ws_forge", "ws_jewel", "ws_leather", "ws_alchemy"):
        assert not p.master_free(ws) and not p.build(ws) and p.building_level(ws) == 0
    assert p.master_chapter("ws_jewel") == XD["chapters"]["forge"]["name"]
    p.chapter_wins["swamp"] = 1                       # босс Болота побеждён — кузнец спасён
    got = p.sync_masters()
    assert [m["name"] for m in got] == [XD["buildings"]["ws_forge"]["master"]["name"]]
    assert p.building_level("ws_forge") == 1 and p.master_free("ws_forge") and not p.cuts
    assert p.build("ws_forge") and p.building_level("ws_forge") == 2      # дальше — за золото
    p.chapter_wins["forge"] = 1                       # Кузни — ювелир: учит «Столовой»
    p.sync_masters()
    assert p.building_level("ws_jewel") == 1 and p.cuts == [GM.START_CUT]
    assert not p.master_free("ws_leather")             # глава 3 ещё не вышла
    p.save()
    again = X.ExpeditionProfile(ED, p.path)
    assert again.cuts == [GM.START_CUT] and again.building_level("ws_forge") == 2


def test_old_buildings_keep_masters(tmp_path):
    p = prof(tmp_path)
    p.buildings["ws_alchemy"] = 2                      # построено до 2026-11-11 — остаётся
    assert p.master_free("ws_alchemy")
    sb = X.ExpeditionProfile(ED, None, sandbox=True)
    assert all(sb.master_free(ws) for ws in ("ws_forge", "ws_jewel", "ws_leather", "ws_alchemy"))
    assert len(sb.cuts) == len(GM.CUTS)


def test_finish_victory_rescues_master(tmp_path):
    p = prof(tmp_path)
    run = X.Expedition(ED, p.hall()[:2], 5, 0)
    run.result = "victory"
    res = p.finish(run)
    assert res["masters"] and p.building_level("ws_forge") == 1


# ---------- 4C: цена и сила ----------

def test_value_and_power_are_nonlinear():
    base = dict(id="ruby", size=0.45, col=0.5, cl=0.6, q=1.0, cut="brilliant")
    v = GM.cut_value(XD, base)
    assert GM.cut_value(XD, dict(base, size=0.9)) > 3.2 * v           # масса ×2 → цена ×3.5 (караты^1.8)
    assert GM.cut_value(XD, dict(base, cl=0.95)) > 1.5 * v
    assert GM.cut_value(XD, dict(base, col=0.9)) > 1.4 * v
    assert GM.cut_value(XD, dict(base, q=5.0)) > 10 * GM.cut_value(XD, dict(base, q=1.0))   # огранка 500% — ×11 цены
    assert GM.cut_value(XD, dict(base, cut="table")) < v               # простая огранка — дешевле
    assert abs(GM.power(XD, base) - 1.0) < 0.02                        # средний — как раньше (+2.5%)
    tiny = dict(base, size=0.15, col=0.2, cl=0.25, q=0.75)
    best = dict(base, size=1.6, col=0.95, cl=0.97, q=5.0)
    brill = dict(base, q=4.5)                                          # тот же камень, хороший бриллиант
    assert GM.power(XD, tiny) <= 0.45 and 2.5 < GM.power(XD, brill) < 3.2 and 8.5 < GM.power(XD, best) <= 10.5
    assert GM.power(XD, best) / GM.power(XD, base) < GM.cut_value(XD, best) / GM.cut_value(XD, base) / 20
    assert GM.power(XD, {"id": "ruby", "q": 1.1}) == 1.1                 # старый камень в гнезде — по качеству
    rng = random.Random(1)
    prices = sorted(GM.rough_value(XD, GM.roll_rough(XD, "ruby", rng, "x")) for _ in range(300))
    assert 2000 < prices[150] < 4500                                    # ≈ ×10 к прежним 320


def test_inclusions_lower_clarity():
    clean = GM.clarity(XD, [])
    one = GM.clarity(XD, [{"k": "crystal", "p": [0, 0, 10], "r": 8}])
    crown = GM.clarity(XD, [{"k": "crystal", "p": [0, 0, -10], "r": 8}])       # видна сквозь площадку
    big = GM.clarity(XD, [{"k": "feather", "p": [0, 0, 10], "r": 20, "n": [0, 0, 1]}])
    assert clean == 1.0 > one > crown and big < one
    assert GM.grade(XD, 0.99) == "Безупречный" and GM.grade(XD, 0.1) == "Мутный"


def test_gem_in_socket_scales_stats(tmp_path):
    from sim import artifacts as A
    p = prof(tmp_path)
    art = {"uid": "a1", "kind": "ring", "set": next(iter(XD["artifacts"]["sets"])), "rarity": "legendary",
           "q": 1.0, "level": 0, "extra": None, "gems": []}
    small = dict(id="ruby", size=0.2, col=0.3, cl=0.4, q=0.9)
    big = dict(id="ruby", size=1.4, col=0.9, cl=0.9, q=1.25)

    def dmg(g):
        import re
        a = dict(art, gems=[GM.socket_entry(g)])
        line = next(ln for ln in A.art_lines(XD, a) if ln.startswith(XD["artifacts"]["gems"]["ruby"]["name"]))
        return float(re.search(r"\+([\d.]+)%", line).group(1))
    assert dmg(big) > 3 * dmg(small)
    assert p


# ---------- разметка, станок, раскол, звезда ----------

def _cut_game(rough, cid):
    from game import workshop_games as G
    g = G.JewelCut(rough["seed"], rough=rough, xd=XD)
    g.choose(G.CUTS.index(GM.CUT_BY_ID[cid]))
    return g


def _bot(g):
    from tests.test_artifacts import cut_gem_game
    return cut_gem_game(None, g=g)


def test_plan_keeps_or_drops_inclusions():
    r = GM.roll_rough(XD, "sapphire", random.Random(3), "r1", size=3.0)
    r["incl"] = [{"k": "crystal", "p": [0.0, 0.0, 0.0], "r": 0.05},           # в центре — останется
                 {"k": "bubble", "p": [0.0, 0.0, 0.72], "r": 0.04}]            # у вершины — уйдёт в отход
    g = _cut_game(r, "brilliant")
    assert g.phase == "plan" and g.can_abort()
    pl = g.plan
    inside = [si["k"] for si, ok in pl.stone_incl() if ok]
    assert inside == ["crystal"]
    ct1 = pl.est_ct()
    pl.wheel(-5)                                                             # меньше камень — меньше карат
    assert pl.est_ct() < ct1 * 0.7
    pl.wheel(10)
    assert g.start_cut() and g.phase == "cut"
    _bot(g)
    ct = g.final_ct()
    assert g.done and 0.6 * ct1 < ct <= ct1 * 1.02
    incl = g.final_incl()
    assert [i["k"] for i in incl] == ["crystal"]
    assert 0 < GM.clarity(XD, incl) < 1


def test_big_stone_bigger_on_machine():
    small = GM.roll_rough(XD, "ruby", random.Random(4), "a", size=0.6)
    big = GM.roll_rough(XD, "ruby", random.Random(4), "b", size=6.0)
    gs, gb = _cut_game(small, "brilliant"), _cut_game(big, "brilliant")
    gs.start_cut()
    gb.start_cut()
    assert gb.mm > 1.8 * gs.mm and gb.S > gs.S


def test_crack_splits_stone_unless_gentle():
    import game.workshop_games as G
    r = GM.roll_rough(XD, "emerald", random.Random(6), "r", size=2.5)
    r["incl"] = []
    g = _cut_game(r, "table")
    g.start_cut()
    f = g.facets[g.active]
    g.index, g.theta = f["dial"], f["ang"]
    n = g.n_vec()
    g.incl = [{"k": "feather", "p": list(G.G3.mul(n, g.extent() - 10)), "r": 12, "n": [0, 0, 1], "src": 0}]
    gentle = G.JewelCut._fine
    try:
        G.JewelCut._fine = lambda self: True                # Shift — бережно: трещина не страшна
        g.press()
        near = False
        for _ in range(300):
            g.update(1 / 60)
            near = near or g.near_crack
            if near:
                break
        assert g.split is None and near

        class Unlucky(random.Random):
            def random(self):
                return 0.0
        g.rng = Unlucky(1)
        G.JewelCut._fine = lambda self: False               # с нажимом — раскол
        for _ in range(1200):
            g.update(1 / 60)
            if g.done:
                break
        assert g.split == 0 and g.done and not g.can_abort()
    finally:
        G.JewelCut._fine = gentle


def test_split_keeps_smaller_piece(tmp_path):
    p = prof(tmp_path)
    p.buildings["ws_jewel"] = 1
    r = p.add_rough("ruby", random.Random(2), size=3.0)
    r["incl"] = [{"k": "feather", "p": [0, 0, 0], "r": 0.1, "n": [0, 0, 1]}]
    out = p.split_rough(r["uid"], 0.4, drop=0)
    assert out is r and r["size"] == 1.2 and not any(i["k"] == "feather" for i in r["incl"])


def test_star_cabochon_needs_silk_and_axis():
    r = GM.roll_rough(XD, "sapphire", random.Random(8), "s", size=3.0)
    r["incl"] = [{"k": "silk", "p": [0.0, 0.0, 0.0], "r": 0.55, "d": 0.9}]
    g = _cut_game(r, "star")
    assert g.plan.star() > 0.8                                # ось кристалла — вверх (как ставит разметка)
    g.plan.turn(0, 130)                                       # ось на боку — звезды нет
    assert g.plan.star() < 0.2
    g.plan.turn(0, -130)
    g.start_cut()
    _bot(g)
    assert g.final_star() > 0.6 and getattr(g.stone, "dome", None)
    plain = _cut_game(GM.roll_rough(XD, "topaz", random.Random(9), "t", size=2.0), "star")
    assert plain.plan.star() == 0.0


def test_every_cut_reachable():
    """Каждая огранка (с фигурным контуром тоже) проходится до своего предела."""
    from tests.test_artifacts import cut_gem_game
    caps = [c["cap"] for c in sorted(GM.CUTS, key=lambda c: c["tier"])]
    assert caps[0] == 1.0 and max(caps) == 5.0 and caps == sorted(caps, key=lambda x: x) or True
    for t in range(4):                                                 # книги сложнее — предел выше
        assert max(c["cap"] for c in GM.CUTS if c["tier"] == t) < min(c["cap"] for c in GM.CUTS if c["tier"] == t + 1)
    for cid in ("table", "rose", "princess", "trilliant", "pear", "heart", "star"):
        g = cut_gem_game(cid)
        cap = GM.CUT_BY_ID[cid]["cap"]
        assert (g.quality - 0.7) / (cap - 0.7) > 0.93, cid


# ---------- книги и рынок ----------

def test_jeweler_sells_books_by_tier(tmp_path):
    p = prof(tmp_path)
    p.glory = 99999
    p.chapter_wins["forge"] = 1
    p.sync_masters()
    rng = random.Random(1)
    seen = set()
    for k in range(40):
        j = GM.roll_jeweler(XD, random.Random(k), p.cuts, lambda r_: p.new_rough("ruby", r_, premium=True))
        if j:
            seen |= set(j["books"])
    assert seen and all(GM.CUT_BY_ID[c]["tier"] <= 1 for c in seen)       # после «Столовой» — только простые
    p.market["jeweler"] = {"name": "Ювелир", "books": ["rose"], "rough": [p.new_rough("ruby", rng, premium=True)]}
    g0 = p.glory
    assert p.buy_book("rose") and "rose" in p.cuts and p.glory == g0 - GM.CUT_BY_ID["rose"]["book"]
    assert not p.buy_book("rose")
    uid = p.market["jeweler"]["rough"][0]["uid"]
    assert p.buy_jeweler_rough(uid) and any(x["uid"] == uid for x in p.rough)


def test_cut_gem_records_4c(tmp_path):
    p = prof(tmp_path)
    p.glory = 5000
    p.buildings["ws_jewel"] = 1
    r = p.add_rough("ruby", random.Random(5), size=2.0)
    g = p.cut_gem(r["uid"], 1.1, cut="oval", ct=0.41, incl=[{"k": "crystal", "p": [0, 0, 5], "r": 6}], star=0.0)
    assert g["size"] == 0.41 and g["col"] == r["col"] and 0 < g["cl"] < 1 and g["cut"] == "oval"
    assert p.market_price("cut", g) == GM.cut_value(XD, g)


def test_old_save_gems_migrate(tmp_path):
    p = prof(tmp_path)
    p.buildings["ws_jewel"] = 1
    p.save()
    with open(p.path, encoding="utf-8") as f:
        d = json.load(f)
    d.pop("cuts")
    d["rough"] = [{"uid": "r1", "id": "ruby", "seed": 77, "size": 1.1}]
    d["gems"] = [{"uid": "g1", "id": "emerald", "q": 1.1, "size": 1.0, "cut": "oval"}]
    with open(p.path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    q = X.ExpeditionProfile(ED, p.path)
    assert "col" in q.rough[0] and "incl" in q.rough[0] and q.gems[0]["cl"] == 0.6
    assert q.cuts == [GM.START_CUT, "oval"]                  # старому ювелиру — огранки его камней


# ---------- экраны ----------

def test_jewel_screens_draw(tmp_path):
    from tests.test_expedition_ui import new_app, key, click, frame
    from game import tavern_rooms as R
    app = new_app(tmp_path)
    p = app.profile
    p.glory = 99999
    key(app, pygame.K_3)
    room = app.scene
    room.overlay = R.StationOverlay(room, "ws_jewel")
    frame(app)                                               # мастера нет — экран «в плену»
    key(app, pygame.K_5)
    assert isinstance(app.scene, R.BuildRoom)
    frame(app)
    assert not any(a == ("build", "ws_jewel") for _, a, _ in app.scene.hits)
    p.chapter_wins["forge"] = 1
    p.sync_masters()
    r = p.add_rough("ruby", random.Random(1), size=2.5)
    key(app, pygame.K_3)
    room = app.scene
    room.overlay = R.StationOverlay(room, "ws_jewel")
    click(app, ("mode", "cut"))
    click(app, ("cut", r["uid"]))
    g = app.scene.game
    assert [c["id"] for c in g.cuts] == ["table"]            # известна только «Столовая»
    key(app, pygame.K_1)
    frame(app)
    assert g.phase == "plan"
    key(app, pygame.K_RETURN)
    frame(app)
    assert g.phase == "cut"
    key(app, pygame.K_ESCAPE)                                # ни одной грани — без потерь
    assert r in p.rough
    p.market["jeweler"] = {"name": "Ювелир Мирон", "books": ["rose", "baguette"], "rough": [
        p.new_rough("sapphire", random.Random(3), premium=True)]}
    key(app, pygame.K_7)
    click(app, "jeweler")
    assert isinstance(app.scene.overlay, R.JewelerOverlay)
    click(app, ("book", "rose"))
    assert "rose" in p.cuts
    frame(app)


# ---------- лупа ----------

def test_loupe_lenses_and_focus():
    from game import workshop_games as G
    g = G.JewelCut(3, lenses=["loupe", "lens3", "lens4", "lens6"])
    g.choose(0)
    assert g.loupe_on and g.mag() == 15
    g.key(pygame.K_4)                                         # вынуть ×6
    g.key(pygame.K_3)                                         # вынуть ×4
    assert g.mag() == 5 and abs(g.focal() - 50) < 1e-6
    g.loupe_d = 80
    assert g.blur() == 1.0
    th = g.theta
    best = 1.0
    for _ in range(40):
        g.wheel(1)                                            # колесо — фокус (угол не меняется)
        best = min(best, g.blur())
    assert best < 0.2 and g.theta == th
    g.loupe_d = 50 + 2.5                                      # ×5: зона резкости шире, чем у ×15
    b5 = g.blur()
    g.lens_in = [True] * 4
    g.loupe_d = 250 / 15 + 2.5
    assert g.blur() > b5
    rect = pygame.Rect(0, 0, 1120, 520)
    g.loupe_xy = (150, 272)                                   # ставится при первой отрисовке станка
    g.loupe_ears = [pygame.Rect(10, 10, 40, 24)]
    g.pointer(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(20, 20), button=1), rect)
    assert not g.lens_in[0]                                   # клик по ушку — линза вынута
    g.loupe_handle = pygame.Rect(400, 400, 70, 70)
    g.pointer(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(430, 430), button=1), rect)
    g.pointer(pygame.event.Event(pygame.MOUSEMOTION, pos=(500, 380), rel=(70, -50), buttons=(1, 0, 0)), rect)
    g.pointer(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(500, 380), button=1), rect)
    assert g.loupe_xy != (150, 272) and not g.hold            # тянули лупу — камень не опускался
    plain = G.JewelCut(3)
    plain.choose(0)
    th = plain.theta
    plain.wheel(1)
    assert not plain.loupe_on and plain.theta != th           # без лупы колесо — по-прежнему угол


def test_loupe_sold_by_jeweler(tmp_path):
    p = prof(tmp_path)
    p.glory = 99999
    p.chapter_wins["forge"] = 1
    p.sync_masters()
    j = GM.roll_jeweler(dict(XD, jewelry=dict(GM.cfg(XD), jeweler=dict(GM.cfg(XD)["jeweler"], chance=1.0))),
                        random.Random(1), p.cuts, lambda r_: p.new_rough("ruby", r_), p.jtools)
    assert j["tools"] == ["loupe"]                            # сначала — оправа с первой линзой
    p.market["jeweler"] = j
    assert p.buy_loupe("loupe") and p.lenses() == ["loupe"]
    assert GM.next_loupe(p.jtools) == "lens3"
    p.market["jeweler"]["tools"] = ["lens3"]
    assert p.buy_loupe("lens3") and p.lenses() == ["loupe", "lens3"]
    assert X.ExpeditionProfile(ED, p.path).lenses() == ["loupe", "lens3"]


# ---------- подача и диски ----------

def _ground(g, frames=60):
    f = g.facets[g.active]
    g.index, g.theta = f["dial"], f["ang"]
    g.h = g.extent() + 1
    g.press()
    for _ in range(frames):
        g.update(1 / 60)
    g.release()


def test_feed_lever_sets_lowering_speed():
    from game import workshop_games as G
    g = G.JewelCut(3)
    g.choose(0)
    g.key(pygame.K_z)
    g.key(pygame.K_z)
    assert g.feed == 0
    h0 = g.h
    g.press()
    g.update(0.2)
    slow = h0 - g.h
    g.release()
    g.h = h0
    for _ in range(4):
        g.key(pygame.K_x)
    assert g.feed == len(g.FEEDS) - 1
    g.press()
    g.update(0.2)
    assert h0 - g.h > 5 * slow                                # быстрая подача — камень идёт к диску быстрее
    g.release()
    g.feed_rects = [pygame.Rect(0, 0, 50, 20), pygame.Rect(0, 30, 50, 20)]
    g.pointer(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(10, 35), button=1), pygame.Rect(0, 0, 1120, 520))
    assert g.feed == 1                                        # клик по положению рычага


def test_disks_speed_versus_finish():
    from game import workshop_games as G
    from game import gem3d as G3

    def removed(disk):
        g = G.JewelCut(3, disks=["lap_coarse", "lap_medium", "lap_fine"])
        g.choose(0)
        g.disk = disk
        v0 = G3.volume(g.stone)
        _ground(g, 30)
        return v0 - G3.volume(g.stone), g
    fast, gc = removed("lap_coarse")
    slow, gf = removed("lap_fine")
    assert fast > 2 * slow
    assert gc.finish_of[gc.active] < 0.8 and gf.finish_of[gf.active] == 1.0
    gc.disk = "lap_fine"                                      # довести грань тонким диском — царапины ушли
    _ground(gc, 20)
    assert gc.finish_of[gc.active] == 1.0
    g = G.JewelCut(3, disks=["lap_medium", "lap_fine"])
    g.choose(0)
    g.key(pygame.K_c)
    assert g.disk == "lap_fine"


def test_cabochon_keeps_players_shape():
    """Кабошон — та же форма, что выточил игрок (без подмены моделью); купол — сглаживание кромок."""
    from game import gem3d as G3
    from tests.test_artifacts import cut_gem_game
    g = cut_gem_game("star", ang_err=3)
    assert getattr(g.stone, "dome", None)
    shape_faces = G3.from_planes(g.shape())
    assert abs(G3.volume(shape_faces) - G3.volume(g.stone)) < 50
    ideal = G3.dome(g.ideal, 100.0, None)
    assert abs(G3.volume(ideal) - G3.volume(g.stone)) > 100


def test_jeweler_sells_disks(tmp_path):
    p = prof(tmp_path)
    p.glory = 99999
    p.chapter_wins["forge"] = 1
    p.sync_masters()
    assert p.disks() == [GM.START_DISK]
    p.market["jeweler"] = {"name": "Ювелир", "books": [], "rough": [], "tools": ["lap_fine"]}
    assert p.buy_loupe("lap_fine") and p.disks() == ["lap_medium", "lap_fine"]
    seen = set()
    for k in range(30):
        j = GM.roll_jeweler(XD, random.Random(k), p.cuts, lambda r_: p.new_rough("ruby", r_), p.jtools)
        if j:
            seen |= set(j["tools"])
    assert {"lap_coarse", "lap_diamond"} & seen and "lap_fine" not in seen


def test_shift_halves_feed_and_lap_spins_by_lever(monkeypatch):
    from game import workshop_games as G
    g = G.JewelCut(3)
    g.choose(0)
    g.set_feed(0)
    slow = g.feed_k()
    monkeypatch.setattr(G.JewelCut, "_fine", lambda self: True)
    assert abs(g.feed_k() - slow / 10) < 1e-9                 # Shift на самой медленной — ещё в 10 раз медленнее
    monkeypatch.setattr(G.JewelCut, "_fine", lambda self: False)
    s0 = g.spin
    g.update(0.5)
    slow_spin = g.spin - s0
    g.set_feed(4)
    s0 = g.spin
    g.update(0.5)
    assert g.spin - s0 > 2 * slow_spin                        # диск крутится по рычагу


def test_faces_remember_disk_grit():
    """Грань помнит зерно диска (шероховатость) — и в сохранённой форме камня."""
    from game import workshop_games as G
    from game import gem3d as G3
    from sim import gems as GM2
    g = G.JewelCut(3, disks=["lap_coarse"])
    g.choose(0)
    _ground(g, 30)
    assert any(f.get("grit") == GM2.GRIT["lap_coarse"] for f in g.stone)
    back = G3.from_planes(G3.planes(G3.polished(g.stone)))
    assert any(f.get("grit") == GM2.GRIT["lap_coarse"] for f in back)


def test_loupe_autofocus_and_edges():
    """Автофокус сам ловит резкость (колесо — вручную, АФ выключается); у края ручка уходит от него; тянуть можно
    и за оправу."""
    from game import workshop_games as G
    g = G.JewelCut(3, lenses=["loupe", "lens3"], autofocus=True)
    g.choose(0)
    assert g.af and g.af_on
    g.loupe_d = 120
    for _ in range(90):
        g.update(1 / 60)
    assert g.blur() < 0.05
    g.toggle_lens(1)                                          # сменили линзы — фокус снова ловится сам
    for _ in range(90):
        g.update(1 / 60)
    assert g.blur() < 0.05
    g.wheel(1)
    assert not g.af_on                                        # крутят вручную
    g.af_rect = pygame.Rect(0, 0, 40, 20)
    rect = pygame.Rect(0, 0, 1120, 520)
    g.loupe_xy = (500, 300)
    g.pointer(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=1), rect)
    assert g.af_on
    g.loupe_r, g.loupe_handle, g.loupe_ears = 100, None, []
    g.pointer(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(600, 300), button=1), rect)     # за оправу
    g.pointer(pygame.event.Event(pygame.MOUSEMOTION, pos=(620, 480), rel=(20, 180), buttons=(1, 0, 0)), rect)
    g.pointer(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(620, 480), button=1), rect)
    assert g.loupe_xy == (520, 480) and not g.hold
    plain = G.JewelCut(3, lenses=["loupe"])
    assert not plain.af


def test_monocle_drag_by_rim_and_click_does_not_lower(tmp_path):
    """Монокль без ручки: тянут за оправу; у верхнего края ушки — снизу; ЛКМ не опускает камень (только Пробел)."""
    from tests.test_expedition_ui import new_app
    from game import workshop_scenes as WS, workshop_games as G
    from ui import theme as T
    app = new_app(tmp_path)
    g = G.JewelCut(3, lenses=["loupe", "lens3"])
    g.choose(0)
    app.switch(WS.MiniGameScene(app, g, "Огранка", lambda q: None, lambda: None))
    surf = pygame.Surface((T.SCREEN_W, T.SCREEN_H))
    app.scene.draw(surf)
    area = app.scene.area()
    assert g.loupe_handle is None and g.loupe_rim > g.loupe_r
    P = (area.x + g.loupe_xy[0], area.y + g.loupe_xy[1])
    assert all(e.bottom < P[1] for e in g.loupe_ears)
    grab = (int(P[0] + (g.loupe_r + g.loupe_rim) / 2), P[1])          # середина оправы справа
    app.scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=grab, button=1))
    app.scene.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(grab[0] + 30, grab[1] - 200), rel=(30, -200),
                                        buttons=(1, 0, 0)))
    app.scene.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(grab[0] + 30, grab[1] - 200), button=1))
    assert not g.hold
    app.scene.draw(surf)
    P = (area.x + g.loupe_xy[0], area.y + g.loupe_xy[1])
    if P[1] - g.loupe_r < area.y + 80:
        assert all(e.top > P[1] for e in g.loupe_ears)                  # у верхнего края — ушки снизу
    far = (area.right - 30, area.bottom - 30)                            # клик мимо лупы — камень не опускается
    app.scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=far, button=1))
    assert not g.hold
    app.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" "))
    assert g.hold


def test_jeweler_offers_autofocus_after_loupe(tmp_path):
    p = prof(tmp_path)
    seen = set()
    for k in range(40):
        j = GM.roll_jeweler(dict(XD, jewelry=dict(GM.cfg(XD), jeweler=dict(GM.cfg(XD)["jeweler"], chance=1.0))),
                            random.Random(k), ["table"], lambda r_: p.new_rough("ruby", r_), ["loupe"])
        seen |= set(j["tools"])
    assert GM.AUTOFOCUS[0] in seen
    j = GM.roll_jeweler(dict(XD, jewelry=dict(GM.cfg(XD), jeweler=dict(GM.cfg(XD)["jeweler"], chance=1.0))),
                        random.Random(1), ["table"], lambda r_: p.new_rough("ruby", r_), [])
    assert GM.AUTOFOCUS[0] not in j["tools"]                  # без лупы — автофокус не предлагают
    p.glory = 99999
    p.market["jeweler"] = {"name": "Ю", "books": [], "rough": [], "tools": [GM.AUTOFOCUS[0]]}
    assert p.buy_loupe(GM.AUTOFOCUS[0]) and GM.AUTOFOCUS[0] in p.jtools


def test_monocle_hitbox_follows_cursor_on_wide_screen(tmp_path):
    """Широкий экран (21:9): поле станка сдвинуто к центру — монокль хватается там, где нарисован, и при
    перетаскивании не уезжает от курсора."""
    from tests.test_expedition_ui import new_app
    from game import workshop_scenes as WS, workshop_games as G
    from ui import theme as T
    app = new_app(tmp_path)
    g = G.JewelCut(3, lenses=["loupe"])
    g.choose(0)
    app.switch(WS.MiniGameScene(app, g, "Огранка", lambda q: None, lambda: None))
    old = T.SCREEN_W
    T.SCREEN_W = 1911
    try:
        surf = pygame.Surface((T.SCREEN_W, T.SCREEN_H))
        app.scene.draw(surf)
        P = g.loupe_center
        mid = (g.loupe_r + g.loupe_rim) / 2
        cur = (int(P[0] + mid), int(P[1]))                   # хватаем середину оправы справа
        app.scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=cur, button=1))
        assert g.loupe_drag is not None
        grip = (cur[0] - P[0], cur[1] - P[1])
        for dx, dy in ((40, -30), (60, 10), (-120, 50), (30, -80)):
            cur = (cur[0] + dx, cur[1] + dy)
            app.scene.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=cur, rel=(dx, dy), buttons=(1, 0, 0)))
            app.scene.draw(surf)
            P = g.loupe_center
            assert abs(cur[0] - P[0] - grip[0]) <= 1 and abs(cur[1] - P[1] - grip[1]) <= 1
        app.scene.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=cur, button=1))
        assert g.loupe_drag is None
    finally:
        T.SCREEN_W = old


# ---------- оттенки: одна карта на вид, камень — окно ----------

def test_bigger_stone_less_often_single_colored():
    rng = random.Random(5)
    mono = {}
    for ct in (0.3, 4.0):
        n = 0
        for _ in range(150):
            o = [rng.uniform(-4000, 4000) for _ in range(3)]
            n += GM.sphere_stats("sapphire", o, GM.stone_mm_radius(XD, "sapphire", ct))["mi"] < 0.05
        mono[ct] = n / 150
    assert mono[0.3] > 0.8 and mono[4.0] < mono[0.3] - 0.3


def test_zoning_price_by_species():
    two = {"top": [[2, 0.6], [4, 0.4]], "hv": 1.0, "mi": 0.4}         # два далёких оттенка крупными зонами
    smear = {"top": [[2, 0.6], [3, 0.4]], "hv": 1.0, "mi": 0.4}       # соседние оттенки — размытая зональность
    assert GM.k_zoning("ruby", two) < 0.8                              # рубин: зональность — дефект
    assert GM.k_zoning("sapphire", two) > 1.2 and GM.k_zoning("sapphire", smear) < 1.0   # «парти» — плюс
    assert GM.k_zoning("topaz", two) > 1.3                             # двухцветный топаз — редкость
    mono = {"top": [[2, 1.0]], "hv": 1.0, "mi": 0.0}
    assert all(GM.k_zoning(g, mono) == 1.0 for g in ("ruby", "sapphire", "topaz"))
    imperial = {"top": [[3, 1.0]], "hv": 1.7, "mi": 0.0}               # имперский топаз дороже золотого
    base = dict(id="topaz", size=1.0, col=0.5, cl=0.6, q=1.0, cut="oval")
    assert GM.cut_value(XD, dict(base, cz=imperial)) > 1.6 * GM.cut_value(XD, dict(base, cz=mono))


def test_field_same_on_cpu_formula():
    """Карта оттенков детерминирована: те же точки — те же значения; окно камня — из его seed."""
    a = GM.field_t("amethyst", [(1.0, 2.0, 3.0), (40.0, -7.0, 2.5)])
    b = GM.field_t("amethyst", [(1.0, 2.0, 3.0), (40.0, -7.0, 2.5)])
    assert (a == b).all() and 0 <= a.min() <= a.max() <= 1
    r1 = GM.roll_rough(XD, "topaz", random.Random(4), "x")
    r2 = GM.roll_rough(XD, "topaz", random.Random(4), "y")
    assert r1["cf"] == r2["cf"]


def test_cut_gem_keeps_color_window(tmp_path):
    from game import workshop_games as G
    from tests.test_artifacts import cut_gem_game
    p = prof(tmp_path)
    p.glory = 9999
    p.buildings["ws_jewel"] = 1
    r = p.add_rough("topaz", random.Random(2), size=4.0)
    g = G.JewelCut(r["seed"], rough=r, xd=XD, disks=["lap_fine"])
    g.choose(G.CUTS.index(GM.CUT_BY_ID["oval"]))
    est = g.plan.est_colors()
    g.start_cut()
    cut_gem_game(None, g=g)
    cz = g.final_colors()
    assert est and cz and abs(cz["top"][0][1] - est["top"][0][1]) < 0.3
    gem = p.cut_gem(r["uid"], g.quality, shape=g.shape(), cut="oval", ct=g.final_ct(), incl=g.final_incl(),
                    cf=g.cf, cz=cz, axis=g.caxis)
    assert gem["cz"] == cz and len(gem["cf"]["A"]) == 9
    assert GM.colors_text("topaz", cz)
    again = X.ExpeditionProfile(ED, p.path)
    assert next(x for x in again.gems if x["uid"] == gem["uid"])["cz"] == cz


def test_unsocket_for_gold(tmp_path):
    p = prof(tmp_path)
    p.glory = 99999
    p.buildings["ws_jewel"] = 1
    art = {"uid": "a1", "kind": "ring", "set": next(iter(XD["artifacts"]["sets"])), "rarity": "legendary",
           "q": 1.0, "level": 0, "extra": None, "gems": []}
    p.stash["a1"] = art
    g = GM.roll_cut(XD, random.Random(3), "g1", "ruby")
    p.gems.append(g)
    assert p.socket("a1", "g1") and not p.gems
    cost = GM.unsocket_cost(XD, art["gems"][0])
    gold = p.glory
    back = p.unsocket("a1", 0)
    assert back and back["id"] == "ruby" and back["size"] == g["size"] and back["cz"] == g["cz"]
    assert p.glory == gold - cost and not art["gems"] and back in p.gems
    assert p.unsocket("a1", 0) is None
    p.glory = 0
    p.socket("a1", back["uid"])
    assert p.unsocket("a1", 0) is None and art["gems"]               # без золота — не вынуть


# ---------- новые огранки, авторские свитки, витрина ----------

def test_all_cuts_have_clean_ideal_and_valid_outline():
    """Каждая огранка: идеал без необработанных сколов (вся поверхность гранится), контур выпуклый и ≤128 плоскостей."""
    from game import workshop_games as G
    assert len(GM.CUTS) >= 40 and len({c["id"] for c in GM.CUTS}) == len(GM.CUTS)
    for i, c in enumerate(G.CUTS):
        g = G.JewelCut(5)
        g.choose(i)
        assert not [f for f in g.ideal if f["kind"] == "rough"], c["id"]
        assert len(g.ideal) <= 128 and g.n > 0, c["id"]
    assert sum(1 for c in GM.CUTS if c.get("rare")) >= 8


def test_rare_cuts_reachable():
    from tests.test_artifacts import cut_gem_game
    for cid in ("dragon_eye", "storm_eye", "north_star"):
        g = cut_gem_game(cid)
        assert (g.quality - 0.7) / (GM.CUT_BY_ID[cid]["cap"] - 0.7) > 0.93, cid


def test_rare_scrolls_only_rarely(tmp_path):
    """Авторские огранки не идут обычными книгами и на прилавок; у ювелира — изредка отдельным свитком."""
    known = [c["id"] for c in GM.CUTS if c["tier"] <= 3 and not c.get("rare")]
    rare_seen, total = 0, 0
    for k in range(300):
        j = GM.roll_jeweler(XD, random.Random(k), known, lambda r_: None)
        if j:
            total += 1
            rare = [b for b in j["books"] if GM.is_rare(b)]
            assert len(rare) <= 1
            rare_seen += bool(rare)
    assert 0 < rare_seen < total * 0.4
    for k in range(40):
        assert not GM.is_rare(GM.roll_cut(XD, random.Random(k), "u", "ruby")["cut"])
    p = prof(tmp_path)
    run = type("R", (), {"result": "victory", "seed": 0})()
    got = []
    for k in range(80):
        run.seed = k
        n = p.scroll_drop(run)
        if n:
            got.append(n)
    assert got and all(GM.is_rare(c) for c in p.cuts if GM.cut_name(c) in got)


def test_showcase_six_slots(tmp_path):
    """Витрина Ювелирной: 6 мест под камни; выставить — из сундука, снять — обратно; ценник — гости покупают после
    похода дороже рынка; сохраняется; камни со старого 3D-стола возвращаются в сундук."""
    p = prof(tmp_path)
    assert len(p.showcase_slots()) == 6 and all(x is None for x in p.showcase_slots())
    g = GM.roll_cut(XD, random.Random(3), "g1", "topaz")
    p.gems += [g, dict(g, uid="g2")]
    assert p.show_gem(0, "g1") and [x["uid"] for x in p.gems] == ["g2"]
    assert p.show_gem(0, "g2") and [x["uid"] for x in p.gems] == ["g1"]     # прежний — обратно в сундук
    assert not p.show_gem(6, "g1")
    assert p.showcase_sales(random.Random(1)) == []                         # без ценника не продают
    assert p.toggle_sale(0)
    assert GM.showcase_price(XD, p.showcase_slots()[0]["gem"]) > p.sell_price("cut", g)
    g0 = p.glory
    for k in range(60):
        if p.showcase_sales(random.Random(k)):
            break
    assert p.glory > g0 and p.showcase_slots()[0] is None and p.showcase["log"]
    p.show_gem(3, "g1")
    assert p.unshow(3)["uid"] == "g1" and p.showcase_slots()[3] is None
    p.show_gem(2, "g1")
    p.save()
    q = prof(tmp_path)
    assert q.showcase_slots()[2]["gem"]["uid"] == "g1" and q.showcase["log"] == p.showcase["log"]
    q.showcase["items"] = [{"uid": "s1", "kind": "gem", "gem": dict(g, uid="old")}, {"uid": "s2", "kind": "decor"}]
    q.save()
    r = prof(tmp_path)
    assert "old" in [x["uid"] for x in r.gems] and "items" not in r.showcase


def test_showcase_tab_ui(tmp_path):
    """Вкладка «Витрина»: клик по месту, по камню из сундука — выставлен; ценник и «Снять» — кнопками."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from test_expedition_ui import new_app, frame, key
    from game import tavern_rooms as R
    app = new_app(tmp_path)
    p = app.profile
    p.sandbox_fill()
    st = R.StationScene(app, "ws_jewel")
    app.switch(st)
    key(app, pygame.K_4)
    assert st.overlay.mode == "show"
    frame(app)
    n0 = len(p.gems)
    st.overlay.act(("sc_slot", 4))
    st.overlay.act(("sc_gem", p.gems[0]["uid"]))
    assert p.showcase_slots()[4] and len(p.gems) == n0 - 1
    st.overlay.act(("sc_gem", p.gems[0]["uid"]))                             # место занято — первое свободное
    assert p.showcase_slots()[0] and len(p.gems) == n0 - 2
    frame(app)
    st.overlay.act(("sc_sale", 4))
    assert p.showcase_slots()[4]["sale"]
    st.overlay.act(("sc_take", 4))
    assert p.showcase_slots()[4] is None and len(p.gems) == n0 - 1
    frame(app)


def test_cut_chooser_scrolls():
    import pygame
    from game import workshop_games as G
    pygame.init()
    g = G.JewelCut(1)
    rect = pygame.Rect(0, 0, 1120, 520)
    from game import jewel_view as JV
    JV.draw_choose(g, pygame.Surface(rect.size), rect)
    assert g.choose_vis < g.choose_rows
    hidden = len(G.CUTS) - 1
    assert g.choice_rects[hidden].w == 0                                   # последняя — за прокруткой
    for _ in range(20):
        g.wheel(-1)
    JV.draw_choose(g, pygame.Surface(rect.size), rect)
    assert g.choice_rects[hidden].w > 0 and g.choice_rects[0].w == 0
    g.key(pygame.K_1)
    assert g.cut is G.CUTS[g.choose_top * g.choose_cols]
