"""Кузня v2 и шахта (квиз 2026-11-12): тигель (сплав по весам и жару) → слиток → примитивы (ковка профиля или
литьё в форму) → вещь с закалкой и отпуском; потолки качества — горн, наковальня, приборы, жидкости, книги;
оправы ювелира — из кузни; шахта-тайкун добывает, пока игра открыта."""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from sim.data import GameData  # noqa: E402
from sim import expedition as X  # noqa: E402
from sim import forge as FG  # noqa: E402

ED = X.expedition_data(GameData())
XD = ED.expedition


def prof(tmp_path=None, level=2):
    p = X.ExpeditionProfile(ED, str(tmp_path / "exp.json") if tmp_path else None)
    p.glory = 99999
    p.mats = {m: 999 for m in XD["materials"]}
    p.buildings["ws_forge"] = level
    p.buildings["ws_jewel"] = 2
    return p


def test_crucible_mix_and_books():
    need = FG.charge_need("bronze", 300)
    assert FG.mix_accuracy("bronze", need) > 0.95
    assert FG.mix_accuracy("bronze", {"copper": 30}) < 0.85                 # без олова — не бронза
    assert "bronze" not in FG.known_alloys([]) and "bronze" in FG.known_alloys(["b_bronze"])
    assert "iron" in FG.known_alloys([]) and "damascus" not in FG.known_alloys(["b_damascus"])
    assert not FG.can_melt("steel", 1) and FG.can_melt("steel", 2) and not FG.can_melt("starsteel", 2)


def test_crucible_ingot_and_cast(tmp_path):
    p = prof(tmp_path)
    p.forge["tools"] += ["b_steel", "mold_strip"]
    ore0 = p.mats["ore"]
    ing = p.crucible("steel", FG.charge_need("steel", 400), 0.95, 0.9)
    assert ing["mass"] == 400 and ing["q"] > 0.9 and p.mats["ore"] == ore0 - 40
    cast = p.crucible("steel", FG.charge_need("steel", 300), 0.95, 0.9, mold="strip", pour=1.0)
    assert len(cast) == 3 and all(c["cast"] and c["kind"] == "strip" for c in cast)
    assert max(c["q"] for c in cast) <= 0.85                               # литьё уступает ковке
    assert p.crucible("bronze", FG.charge_need("bronze", 300), 1, 1) is None   # нет книги


def test_forged_quality_capped_by_anvil(tmp_path):
    p = prof(tmp_path)
    ing = p.crucible("iron", FG.charge_need("iron", 400), 1, 1)
    a = p.forge_prim(ing["uid"], "rod", 1.0)
    p.forge["tools"].append("anvil_master")
    b = p.forge_prim(ing["uid"], "rod", 1.0)
    assert a["q"] <= 0.86 and b["q"] > a["q"]


def test_quench_and_temper_rules():
    hard, crack = FG.quench_result("steel", 800, "water")
    assert hard > 0.95 and not crack
    soft, _ = FG.quench_result("steel", 800, "oil")
    cold, _ = FG.quench_result("steel", 650, "water")
    assert soft < hard and cold < hard
    cracks = sum(FG.quench_result("spring", 820, "brine", random.Random(k))[1] for k in range(40))
    assert cracks > 5                                      # рессорную сталь в рассол — трещины
    assert FG.temper_result("spring", 300) > 0.95 > FG.temper_result("spring", 220)
    assert FG.gauge_cap([]) == 0.75 and abs(FG.gauge_cap(["pyrometer", "magnet", "hourglass", "hardness"]) - 1) < 1e-9


def test_temper_game_flow():
    from game import forge_games as FGM
    prims = [{"uid": "a", "kind": "sheet", "alloy": "steel", "mass": 150, "q": 0.9},
             {"uid": "b", "kind": "sheet", "alloy": "steel", "mass": 150, "q": 0.9},
             {"uid": "c", "kind": "strip", "alloy": "steel", "mass": 100, "q": 0.9}]
    g = FGM.TemperGame("bracers", prims, ["water", "pyrometer", "b_quench"], 2, seed=1)
    g.rect = pygame.Rect(0, 0, 1120, 600)
    g.key(pygame.K_RETURN)
    assert g.phase == "heat"                              # Enter не закаливает — только клещами в бочку
    quench(g, 805)
    assert g.phase == "temper" and g.quench_hard > 0.9 and not g.crack
    g.temp = 222
    g.key(pygame.K_RETURN)
    assert g.done and g.result["heat"] > 0.9
    bronze = FGM.TemperGame("belt", [dict(p, alloy="bronze") for p in prims], ["water"], 2)
    assert bronze.phase == "anneal"


def test_make_item_from_prims(tmp_path):
    p = prof(tmp_path)
    p.forge["tools"] += ["b_steel"]
    ing = p.crucible("steel", FG.charge_need("steel", 600), 1, 1)
    for k in ("sheet", "sheet", "strip"):
        p.forge_prim(ing["uid"], k, 0.95)
    sid = next(s for s, v in XD["artifacts"]["sets"].items() if v["rarity"] == "rare")     # сталь — с редких
    prims = p.pick_prims("bracers", set_id=sid)
    assert prims and p.pick_prims("belt") is None
    art = p.make_item("bracers", sid, [x["uid"] for x in prims], heat=0.95, quench_hard=1.0, temper_acc=1.0)
    assert art and 0.7 <= art["q"] <= 1.3 and art["metal"]["hard"] > 0.6 and not p.forge["prims"]
    weak = p.crucible("steel", FG.charge_need("steel", 600), 1, 1)
    for k in ("sheet", "sheet", "strip"):
        p.forge_prim(weak["uid"], k, 0.95)
    art2 = p.make_item("bracers", sid, [x["uid"] for x in p.pick_prims("bracers", set_id=sid)], heat=0.0,
                       quench_hard=0.3)
    assert art2["q"] < art["q"] and art2["metal"]["hard"] < art["metal"]["hard"]


def test_gold_frame_gives_socket(tmp_path):
    from sim import artifacts as A
    p = prof(tmp_path)
    sid = next(s for s, v in XD["artifacts"]["sets"].items() if v["rarity"] == "rare")
    p.forge["prims"] = [{"uid": "g1", "kind": "wire", "alloy": "gold18", "mass": 40, "q": 0.9}]
    gold = p.make_item("ring", sid, ["g1"], heat=0.3)        # ниже потолка сборки — видно разницу
    p.forge["prims"] = [{"uid": "s1", "kind": "wire", "alloy": "bronze", "mass": 40, "q": 0.9}]
    cheap = p.make_item("ring", sid, ["s1"], heat=0.3)
    assert A.sockets(XD, gold) == A.sockets(XD, cheap) + 1 and gold["q"] > cheap["q"]


def test_mine_tycoon(tmp_path):
    p = prof(tmp_path)
    m = p.mine
    assert m["workers"] == 1 and FG.mine_rate(m) == 1.2
    p.mine_tick(6000)                                     # 100 минут — склад полон
    full = sum(m["stock"].values())
    assert FG.mine_cap(m) - 2 <= full <= FG.mine_cap(m)
    p.mine_tick(3000)
    assert sum(m["stock"].values()) <= FG.mine_cap(m)     # полон — стоят
    ore0 = p.mats["ore"]
    got, stones = p.mine_collect()
    assert p.mats["ore"] == ore0 + got["ore"] and not m["stock"]
    assert set(got) <= {"ore", "coal", "copper"}          # штольня: только железо, уголь, медь
    for what in ("workers", "pick", "store", "cart", "depth", "depth"):
        assert p.mine_upgrade(what)
    assert FG.mine_rate(m) > 1.2 and m["depth"] == 2
    p.mine_tick(3600 * 5)
    assert "gold" in m["stock"] or "silver" in m["stock"]
    p.glory = 0
    assert not p.mine_upgrade("workers")
    p.save()
    again = X.ExpeditionProfile(ED, p.path)
    assert again.mine["depth"] == 2


def test_smith_offers_and_drops(tmp_path):
    p = prof(tmp_path)
    offer = p.roll_smith_offer(random.Random(1))
    assert 2 <= len(offer) <= 4 and all(t in FG.TOOLS or t in FG.BOOKS for t in offer)
    p.market["smith"] = {"name": "Кузнец", "pieces": [], "tools": [], "forge": list(offer)}
    t = offer[0]
    assert p.buy_smith(t) and p.f_has(t) and not p.buy_smith(t)
    hits = 0
    for k in range(60):
        run = X.Expedition(ED, p.hall()[:2], k, 0)
        run.result = "victory"
        hits += bool(p.forge_drop(run))
    assert hits >= 3


def test_forge_ui_and_mine_room(tmp_path):
    from tests.test_expedition_ui import new_app, frame, key, click
    from game import tavern_rooms as R
    app = new_app(tmp_path)
    p = app.profile
    p.glory = 99999
    p.buildings["ws_forge"] = 2
    p.chapter_wins["swamp"] = 1
    key(app, pygame.K_3)
    room = app.scene
    room.act(("station", "ws_forge"))
    st = app.scene
    for m in ("crucible", "hammer", "item", "store", "orders"):
        st.act(("mode", m))
        frame(app)
    assert set(st.mat_keys()) >= {"ore", "coal", "copper"} and "leather" not in st.mat_keys()
    key(app, pygame.K_ESCAPE)
    key(app, pygame.K_8)
    assert isinstance(app.scene, R.MineRoom)
    p.mine_tick(120)
    frame(app)
    click(app, "collect")
    assert not p.mine["stock"]
    click(app, ("up", "workers"))
    assert p.mine["workers"] == 2




def quench(g, t_in=None, t_out=None, bath=None):
    """Бот закалки: деталь в клещах — в бочку (ванна по книге), держать до t_out, вынуть."""
    g.place()
    g.temp = t_in or g.a["quench"]
    g.bath_t = FG.BATH[g.liquid] if bath is None else bath
    x0, x1, sy, by = g.bath()
    g.where, g.grab, g.tong_v = "tongs", False, [0.0, 0.0]
    g.tong = [(x0 + x1) / 2, sy + 60]
    target = t_out or FG.quench_out(g.aid)
    for _ in range(4000):
        g.update(1 / 120)
        if g.temp <= target:
            break
    g.tong = [(x0 + x1) / 2, sy - 90]                      # вынуть
    g.update(1 / 120)
    return g


def rivet_all(g):
    """Бот клёпки: в каждый стык — сколько он держит, по оси перекрытия."""
    for jt in g.joints():
        b, n = jt["box"], jt["need"]
        for k in range(n):
            if b.w >= b.h:
                g.rivets.append((b.x + b.w * (k + 0.5) / n, b.y + b.h / 2))
            else:
                g.rivets.append((b.x + b.w / 2, b.y + b.h * (k + 0.5) / n))


def assemble(app, g):
    """Бот сборки: детали точно по контуру, заклёпки в стыки, испытание, закалка клещами и отпуск."""
    from tests.test_expedition_ui import frame
    frame(app)
    g.update(0.01)
    cx, cy = g.table()
    used = []
    for s_ in g.slots:
        pc = next(p_ for p_ in g.pieces if all(p_ is not u for u in used) and p_["prim"]["kind"] == s_["kind"])
        used.append(pc)
        pc["x"], pc["y"], pc["ang"] = cx + s_["dx"], cy + s_["dy"], s_["ang"]
    g.key(pygame.K_RETURN)
    assert g.phase == "join"
    rivet_all(g)
    g.key(pygame.K_RETURN)
    g.update(2.0)
    g.key(pygame.K_RETURN)
    if g.phase == "heat":
        quench(g)
        g.temp = FG.TEMPER[g.a["temper"]][1]
    g.key(pygame.K_RETURN)
    return g


def test_item_assembly_game():
    from game import forge_games as FGM
    prims = [{"uid": "a", "kind": "sheet", "alloy": "steel", "mass": 150, "q": 0.9},
             {"uid": "b", "kind": "sheet", "alloy": "steel", "mass": 150, "q": 0.9},
             {"uid": "c", "kind": "strip", "alloy": "steel", "mass": 100, "q": 0.9}]
    g = FGM.ItemGame("bracers", prims, ["water", "pyrometer", "b_quench"], 2, seed=1)
    g.rect = pygame.Rect(0, 0, 1120, 600)
    g.update(0.01)
    assert g.phase == "assemble" and g.can_abort()
    g.key(pygame.K_RETURN)
    assert g.phase == "assemble"                          # детали ещё на подносе
    cx, cy = g.table()
    for pc, s_ in zip(g.pieces, g.slots):
        pc["x"], pc["y"], pc["ang"] = cx + s_["dx"], cy + s_["dy"], s_["ang"]
    assert g.fit() > 0.97                                 # точно по контуру — почти 100%
    pc = g.pieces[0]                                      # тащим лист мышью — не прилипает, лежит где отпустили
    gx, gy = int(pc["x"]) - 40, int(pc["y"]) + 34          # за край листа, мимо полосы поверх
    g.pointer(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(gx, gy), button=1), g.rect)
    g.pointer(pygame.event.Event(pygame.MOUSEMOTION, pos=(gx - 25, gy + 9), rel=(0, 0), buttons=(1, 0, 0)), g.rect)
    g.pointer(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(gx - 25, gy + 9), button=1), g.rect)
    assert abs(pc["x"] - (cx + g.slots[0]["dx"] - 25)) < 1.5 and 0.6 < g.fit() < 0.95
    pc["x"], pc["y"] = cx + g.slots[0]["dx"], cy + g.slots[0]["dy"]
    g.key(pygame.K_RETURN)
    assert g.phase == "join" and g.rivet_max >= 5
    g.key(pygame.K_RETURN)                                # без заклёпок — разваливается
    g.update(2.0)
    assert g.phase == "test" and g.strength == 0 and g.loose
    g.phase, g.rivets = "join", []
    for p_ in g.pieces:
        p_["ox"] = p_["oy"] = 0.0                         # после испытания — детали обратно на стол
    rivet_all(g)
    assert len(g.rivets) <= g.rivet_max
    g.key(pygame.K_RETURN)
    assert g.strength > 0.95 and not g.loose
    jt = next(j for j in g.joints() if j["a"] != j["b"])  # заклёпка у самого края перекрытия — слабая
    b = jt["box"]
    edge = (b.x + 1, b.y + b.h / 2) if b.w < b.h else (b.x + b.w / 2, b.y + 1)
    assert g.rivet_s(edge, jt) < 0.5 and g.rivet_s((b.centerx, b.centery), jt) > 0.9
    g.update(2.0)
    g.key(pygame.K_RETURN)
    assert g.phase == "heat"


def test_ring_joint_is_wire_ends():
    from game import forge_games as FGM
    g = FGM.ItemGame("ring", [{"uid": "w", "kind": "wire", "alloy": "silver925", "mass": 40, "q": 0.9}], [], 2)
    g.rect = pygame.Rect(0, 0, 1120, 600)
    g.update(0.01)
    cx, cy = g.table()
    g.pieces[0].update(x=cx, y=cy, ang=0)
    g.key(pygame.K_RETURN)
    rivet_all(g)
    g.key(pygame.K_RETURN)
    assert g.strength > 0.9 and g.fit() > 0.95


def test_forged_length_goes_to_assembly(tmp_path):
    from game import forge_games as FGM
    p = prof(tmp_path)
    ing = p.crucible("iron", FG.charge_need("iron", 400), 1, 1)
    long_ = p.forge_prim(ing["uid"], "strip", 0.9, length=330)
    assert long_["len"] == 330
    g = FGM.ItemGame("ring", [{"uid": "w", "kind": "wire", "alloy": "iron", "mass": 40, "q": 0.9, "len": 420}], [], 2)
    g.rect = pygame.Rect(0, 0, 1120, 600)
    g.update(0.01)
    cx, cy = g.table()
    g.pieces[0].update(x=cx, y=cy, ang=0)
    assert g.fit() < 0.85                                 # длиннее контура — торчит


def test_quench_with_tongs_in_and_out():
    from game import forge_games as FGM
    prims = [{"uid": "a", "kind": "sheet", "alloy": "steel", "mass": 150, "q": 0.9}]

    def run(**kw):
        g = FGM.TemperGame("amulet", prims, ["water", "b_quench"], 2, seed=4)
        g.rect = pygame.Rect(0, 0, 1120, 600)
        return quench(g, **kw)
    good = run()
    hot = run(t_out=420)                                  # вынули рано — не прокалилась
    cold_in = run(t_in=640)                               # остыла по дороге
    assert good.quench_hard > 0.9 > hot.quench_hard + 0.3 and cold_in.quench_hard < 0.5
    hard, crack, rep = FG.quench_eval("steel", 800, "water", 15, 25, random.Random(1))
    assert rep["risk"] > 0.3 and rep["bath"] < 1             # холодная ванна и передержка — риск трещины
    g = FGM.TemperGame("amulet", prims, ["water"], 2, seed=4)
    g.rect = pygame.Rect(0, 0, 1120, 600)
    g.place()
    b0 = g.bath_t
    for _ in range(120):                                  # без огня под бочкой — не греется
        g.update(1 / 60)
    assert abs(g.bath_t - b0) < 0.5
    g.temp, g.where = 800, "tongs"                       # деталь в клещах остывает на воздухе
    g.tong = [g.rect.x + 400, g.rect.y + 150]
    for _ in range(60):
        g.update(1 / 60)
    assert g.temp < 760 and g.phase == "heat"


def test_cast_by_tilting_into_molds(tmp_path):
    from game import forge_games as FGM
    g = FGM.CrucibleGame("iron", {"ore": 99, "coal": 99}, ["mold_strip"], 2, seed=3)
    g.rect = pygame.Rect(0, 0, 1240, 700)
    g.charge = FG.charge_need("iron", 300)
    g.phase = "pour"
    g.key(pygame.K_1)
    g.key(pygame.K_1)
    assert g.queue == ["strip", "strip"]
    g.temp = g.a["melt"] + 70
    g.key(pygame.K_RETURN)
    assert g.phase == "cast" and g.metal == 300
    (px, py), belt = g.cast_geom()
    aim = 0.0
    for _ in range(60 * 60):                              # бот: держит тигель у кромки, льёт, пока форма под струёй
        fut = px + 50 - g.CONV_V * 0.9                    # куда упадёт металл, налитый сейчас
        under = [i for i, (a, b) in enumerate(g.mold_rects()) if a + 8 < fut < b - 8]
        fly = sum(s_[4] for s_ in g.stream)
        want = under and g.cast[under[0]]["mass"] + fly < FG.PRIMS[g.cast[under[0]]["kind"]]["mass"] * 0.92
        if want:
            aim += 0.02 if g.flow < 40 else -0.01 if g.flow > 90 else 0.0
        elif g.flow > 0:
            aim -= 0.03
        g.tilt_anchor = 500
        g.mpos = (0, 500 - 240 * aim / 1.75)
        g.update(1 / 60)
        if g.done:
            break
    assert g.done and len(g.result["casts"]) == 2
    fills = [c["fill"] for c in g.result["casts"]]
    assert min(fills) > 0.7, fills
    p = prof(tmp_path)
    p.forge["tools"].append("mold_strip")
    out = p.crucible("iron", g.result["charge"], 1, 1, casts=g.result["casts"], spilt=g.result["spilt"])
    assert len(out["casts"]) == 2 and all(c["len"] <= 260 for c in out["casts"])
    assert out["ingot"] is None or out["ingot"]["mass"] < 300


def test_spatula_gone_after_slag():
    from game import forge_games as FGM
    g = FGM.CrucibleGame("iron", {"ore": 99, "coal": 99}, [], 2, seed=3)
    g.rect = pygame.Rect(0, 0, 1120, 600)
    g.charge = FG.charge_need("iron", 300)
    g.phase = "melt"
    assert g.spat_on()
    g.slag_left, g.slag = 0, []
    assert not g.spat_on()
    x0, x1, rim, floor = g.bowl()
    assert not g.pointer(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(int(x0 + 100), int(rim + 20)), button=1),
                         g.rect)


def test_crucible_liquid_and_spatula():
    from game import forge_games as FGM
    g = FGM.CrucibleGame("iron", {"ore": 99, "coal": 99}, ["water"], 2, seed=3)
    g.rect = pygame.Rect(0, 0, 1120, 600)
    g.charge = FG.charge_need("iron", 300)
    g.phase = "melt"
    x0, x1, rim, floor = g.bowl()
    g.slag = [[x0 + 120, g.level(), 0.0, 0.0, 14]]
    g.slag_left = 0
    g.spat = [x0 + 140, g.level() + 20]                  # лопатка под шлаком, в расплаве
    g.grab = True
    g.mpos = (x0 + 140, rim - 120)                        # поднять — шлак едет на лопатке и снимается
    for _ in range(90):
        g.update(1 / 60)
    assert g.removed == 1 and not g.slag
    p0 = g.purity
    cx = (x0 + x1) / 2
    for k in range(240):                                  # аккуратно — не проливается
        g.mpos = (cx - 30 if (k // 30) % 2 else cx + 30, g.level() + 50)
        g.update(1 / 60)
    assert g.purity == p0
    g.slag_left, g.slag_t, g.grab = 3, 999.0, True        # лопатка ещё нужна (шлак не весь)
    for k in range(400):                                  # размашисто, в такт волне — через край
        g.mpos = (cx - 150 if (k // 40) % 2 else cx + 150, g.level() + 50)
        g.update(1 / 60)
    assert g.purity < p0


def test_set_metals_and_metal_affixes(tmp_path):
    from sim import artifacts as A
    p = prof(tmp_path)
    sets = XD["artifacts"]["sets"]
    common = next(s for s, v in sets.items() if v["rarity"] == "common")
    rare = next(s for s, v in sets.items() if v["rarity"] == "rare")
    assert p.set_alloys("bracers", common) == ["iron", "bronze", "copper"]
    assert "iron" in p.set_alloys("bracers", rare) and "steel" in p.set_alloys("bracers", rare)   # тиры пересекаются
    assert "silver925" in p.set_alloys("ring", common) and "iron" not in p.set_alloys("ring", common)

    def prims(alloy, tag):
        return [{"uid": f"{tag}{i}", "kind": k, "alloy": alloy, "mass": FG.PRIMS[k]["mass"], "q": 0.9}
                for i, k in enumerate(("sheet", "sheet", "strip"))]
    p.forge["prims"] = prims("steel", "s") + prims("bronze", "b")
    assert all(x["alloy"] == "bronze" for x in p.pick_prims("bracers", set_id=common))   # сталь не годна обычным
    assert p.make_item("bracers", common, ["s0", "s1", "s2"]) is None
    art = p.make_item("bracers", common, ["b0", "b1", "b2"], heat=1.0)
    assert art["metal_affix"] and art["metal_affix"][0]["id"] == "swift"
    assert any(ln.startswith("Бронза: +") and "скорости атак" in ln for ln in A.art_lines(XD, art))
    mods, extra, _ = A.effects(XD, [art])
    plain = dict(art, metal_affix=[])
    mods0, _, _ = A.effects(XD, [plain])
    speed = [m for m in mods if m.get("stat") == "atk_cooldown"]
    assert speed and not [m for m in mods0 if m.get("stat") == "atk_cooldown"]   # бронза ускоряет атаки
    mixed = FG.metal_affixes([{"alloy": "iron", "mass": 300}, {"alloy": "bronze", "mass": 100}], 1.0)
    assert [m["alloy"] for m in mixed] == ["iron", "bronze"] and mixed[0]["k"] > mixed[1]["k"]
    for a_ in FG.ALLOY_AFFIX:                           # у каждого металла — свой эффект с понятным текстом
        assert A.metal_affix_text(XD, {"alloy": a_, "id": FG.ALLOY_AFFIX[a_][0], "k": 1.0}, False)


def test_higher_tier_metal_never_weaker_in_same_stat():
    """Один и тот же стат (перезарядка у серебра и звёздной стали): металл старшего тира — не слабее."""
    from sim import artifacts as A
    order = list(A.RARITY_ORDER)

    def tier(aid):                                      # самый младший тир, где металл встречается
        return min(order.index(r) for ws in FG.SET_ALLOYS.values() for r, al in ws.items() if aid in al)

    def key(entry):                                     # что именно усиливает: стат, добавка или вид бонуса
        if "vs" in entry:
            return "vs:" + entry["vs"]
        return entry.get("stat") or entry.get("extra") or next(
            f for f in ("skill_cd", "speed", "ap_regen", "reaction") if f in entry)

    def val(entry, k):
        return k * next(entry[f] for f in ("pct", "add", "speed", "skill_cd", "ap_regen", "reaction") if f in entry)
    sa = XD["items"]["stat_affixes"]
    rows = [(tier(a_), a_, key(sa[i]), val(sa[i], k)) for a_, (i, k) in FG.ALLOY_AFFIX.items() if a_ != "damascus"]
    for t1, a1, k1, v1 in rows:
        for t2, a2, k2, v2 in rows:
            if k1 == k2 and t2 > t1:
                assert v2 >= v1, (a1, v1, a2, v2)


class _Rng:
    """Бросок торга: всегда value (0 — согласен, 0.999 — отказ)."""
    def __init__(self, value):
        self.v = value

    def random(self):
        return self.v


def test_wandering_smith_sells_ingots_and_buys_metals(tmp_path):
    p = prof(tmp_path)
    p.market = {"smith": {"name": "Кузнец", "forge": []}, "jeweler": {"name": "Ювелир", "books": [], "rough": []}}
    p.stock_wanderers(random.Random(3))
    sm = p.market["smith"]
    assert not sm["pieces"] and 3 <= len(sm["ingots"]) <= 5 and sm["wants"] and sm["patience"] == 1.0
    ing = sm["ingots"][0]
    g0 = p.glory
    assert p.buy_ingot(ing["uid"]) and p.glory == g0 - ing["price"]
    assert any(x["uid"] == ing["uid"] for x in p.forge["ingots"]) and ing not in sm["ingots"]
    # продажа: слиток за половину цены, хотелка — дороже, торг — ещё дороже
    sm["wants"] = [{"id": ing["alloy"], "k": 1.5}]
    base = int(FG.ingot_value(ing) * 0.5 * 1.5)
    assert p.trade_price("smith", "ingot", ing["uid"]) == base
    assert p.trade_price("smith", "ingot", ing["uid"], 1.3) > base
    g1 = p.glory
    assert p.trade_sell("smith", "ingot", ing["uid"], 1.3, _Rng(0.0)) == ("sold", int(FG.ingot_value(ing) * 0.5 * 1.5 * 1.3))
    assert p.glory > g1 and not any(x["uid"] == ing["uid"] for x in p.forge["ingots"]) and sm["patience"] < 1
    ore0 = p.mats["ore"]
    assert p.trade_sell("smith", "mat", "ore", 1.0)[0] == "sold" and p.mats["ore"] == ore0 - FG.MAT_LOT
    # отказы: терпение кончилось — обиделся до следующего визита
    p.forge["ingots"].append({"uid": "zz", "alloy": "iron", "mass": 300, "q": 0.9})
    res = [p.trade_sell("smith", "ingot", "zz", 1.5, _Rng(0.999))[0] for _ in range(4)]
    assert res[0] == "refused" and "angry" in res and sm["angry"]
    assert p.trade_sell("smith", "ingot", "zz", 1.0)[0] == "angry"           # даже без торга — не берёт
    p.stock_wanderers(random.Random(4))                                    # новый визит — новое настроение
    assert not p.market["smith"]["angry"] and p.trade_sell("smith", "ingot", "zz", 1.0)[0] == "sold"


def test_wandering_jeweler_buys_stones():
    assert FG.haggle_chance(1.0, 0.0) == 1.0 and FG.haggle_chance(1.5, 1.0) < FG.haggle_chance(1.15, 1.0)
    assert FG.haggle_chance(1.3, 0.2) < FG.haggle_chance(1.3, 1.0)
    p = prof()
    p.market = {"jeweler": {"name": "Ювелир", "books": [], "rough": []}}
    p.stock_wanderers(random.Random(1))
    r = p.add_rough("ruby", random.Random(5))
    p.market["jeweler"]["wants"] = [{"id": "ruby", "k": 1.6}]
    goods = p.trade_goods("jeweler")
    row = next(g for g in goods if g[1] == r["uid"])
    assert row[0] == "rough" and row[3] == 1.6
    assert p.trade_price("jeweler", "rough", r["uid"]) == int(p.market_price("rough", r) * 0.5 * 1.6)
    assert p.trade_sell("jeweler", "rough", r["uid"], 1.0)[0] == "sold" and r not in p.rough


def test_trade_windows_draw(tmp_path):
    from tests.test_expedition_ui import new_app, frame
    from game import tavern_rooms as R
    app = new_app(tmp_path)
    p = app.profile
    p.sandbox_fill()
    sc = app.scene
    for cls in (R.WandererOverlay, R.JewelerOverlay):
        sc.overlay = cls(sc)
        frame(app)
        sc.overlay.act(("tmode", "sell"))
        sc.overlay.act(("ask", 2))
        frame(app)
        assert sc.overlay.tmode == "sell"
    goods = p.trade_goods("jeweler")
    kind, key = goods[0][0], goods[0][1]
    sc.overlay.act(("ask", 0))
    sc.overlay.act(("tsell", kind, key))
    assert not any(x[1] == key for x in p.trade_goods("jeweler"))


def test_assembly_capped_whole_forging_reaches_130(tmp_path):
    p = prof(tmp_path)
    p.forge["tools"] += ["b_steel", "anvil_master", "pyrometer", "magnet", "hourglass", "hardness"]
    sid = next(s for s, v in XD["artifacts"]["sets"].items() if v["rarity"] == "rare")
    p.forge["prims"] = [{"uid": f"p{i}", "kind": k, "alloy": "steel", "mass": FG.PRIMS[k]["mass"], "q": 1.0}
                        for i, k in enumerate(("sheet", "sheet", "strip"))]
    built = p.make_item("bracers", sid, ["p0", "p1", "p2"], heat=1.0)
    assert built["q"] <= FG.ASSEMBLY_CAP                                  # сборка — не выше 100%
    p.forge["ingots"] = [{"uid": "i1", "alloy": "steel", "mass": 600, "q": 1.0, "purity": 1.0},
                         {"uid": "i2", "alloy": "starsteel", "mass": 600, "q": 1.0, "purity": 1.0}]
    assert p.whole_ingot("bracers", sid)["uid"] == "i1"                   # звёздная сталь не годна редкому сету
    assert p.make_item_whole("bracers", sid, "i2", 1.0) is None
    art = p.make_item_whole("bracers", sid, "i1", 1.0, heat=1.0)
    assert art and art["whole"] and art["q"] > 1.15 and art["metal_affix"][0]["alloy"] == "steel"
    assert next(i for i in p.forge["ingots"] if i["uid"] == "i1")["mass"] == 600 - FG.item_mass("bracers")
    assert p.whole_ingot("bracers", sid) is None                          # остаток мал для вторых наручей


def test_whole_forging_ui_chain(tmp_path):
    """Вещь по техкарте из окна кузни: ковка по этапам → закалка → вещь в сундуке (потолок техкарты)."""
    from tests.test_expedition_ui import new_app, frame, key
    from game import tavern_rooms as R, workshop_scenes as WS, forge_games as FGM
    app = new_app(tmp_path)
    p = app.profile
    p.sandbox_fill()
    st = R.StationScene(app, "ws_forge")
    app.switch(st)
    key(app, pygame.K_3)
    frame(app)
    st.overlay.set_sel = next(s for s, v in XD["artifacts"]["sets"].items() if v["rarity"] == "common")
    n0 = len(p.stash)
    st.overlay.act(("craft_whole",))
    g = app.scene.game
    from game.forge_card_game import CardGame
    assert isinstance(app.scene, WS.MiniGameScene) and isinstance(g, CardGame) and g.card_key.startswith("bracers")
    frame(app)
    for _ in g.stages:                                                    # Enter — этап за этапом
        g.key(pygame.K_RETURN)
    assert g.done and len(g.result["stages"]) == len(g.stages)
    frame(app)
    key(app, pygame.K_RETURN)                                             # экран итога — дальше
    frame(app)
    t = app.scene.game
    assert isinstance(t, FGM.TemperGame)                                  # следом — закалка
    if t.phase == "heat":
        quench(t)
    t.key(pygame.K_RETURN)
    frame(app)
    key(app, pygame.K_RETURN)
    frame(app)
    assert isinstance(app.scene, R.StationScene)
    from sim import forge_card as FC
    art = next(a for a in p.stash.values() if a.get("card"))
    assert len(p.stash) == n0 + 1 and art["card"] == g.card_key
    assert art["q"] <= FC.CARDS[g.card_key]["cap"] + 1e-9                # потолок — у техкарты


def test_bar_forging_rules():
    """Ковка «в двух видах»: плашмя — тоньше и длиннее, на ребро — уже, на угол — круглее; клин тянет, кувалда
    раздаёт вширь; обжимка круглит; гладилка ровняет; объём сохраняется всегда."""
    import numpy as np
    from sim import forge_bar as FB
    b = FB.Bar(100)
    v0, l0, w0, t0 = b.volume(), b.length(), b.w.mean(), b.t.mean()
    b.strike(l0 / 2, 1.0, "hand")
    assert b.t.min() < t0 and b.w.max() > w0 and b.length() > l0          # плашмя
    assert abs(b.volume() - v0) / v0 < 1e-9
    b.turn(90)
    w1 = b.w.min()
    b.strike(b.length() / 2, 1.0, "hand")
    assert b.w.min() < w1 and FB.orient_name(b.orient) == "на ребро"
    peen, sledge = FB.Bar(100), FB.Bar(100)
    spread = {}
    for name, bar in (("peen", peen), ("sledge", sledge)):                   # какая доля сжатия ушла вширь
        w_, t_ = bar.w[0], bar.t[0]
        bar.strike(bar.length() / 2, 1.0, name)
        i = int(np.argmin(bar.t))
        spread[name] = np.log(bar.w[i] / w_) / np.log(t_ / bar.t[i])
    assert spread["peen"] < spread["sledge"]                               # клин тянет, кувалда — вширь
    c = FB.Bar(100)
    c.turn(45)
    for k in range(10):
        c.strike(c.length() * (k + 0.5) / 10, 0.7, "hand")
    assert c.r.mean() > 0.5 and FB.orient_name(c.orient) == "на угол"     # на угол — круглее
    sw = FB.Bar(100)
    sw.w[:] *= 1.6
    sw.t[:] /= 1.6
    for k in range(20):
        sw.swage(sw.length() * (k % 10 + 0.5) / 10, 1.0)
    assert np.abs(sw.w / sw.t - 1).max() < 0.15 and sw.r.min() > 0.8     # обжимка — круг
    sm = FB.Bar(100)
    sm.strike(sm.length() * 0.3, 1.0, "peen")
    var0 = sm.t.std()
    for k in range(8):
        sm.strike(sm.length() * (k + 0.5) / 8, 1.0, "flatter")
    assert sm.t.std() < var0                                               # гладилка ровняет
    for bar in (peen, sledge, c, sw, sm):
        assert abs(bar.volume() - bar.vol0) / bar.vol0 < 1e-6


def test_bar_score_and_targets():
    import numpy as np
    from sim import forge_bar as FB
    for kind, mass, item in (("rod", 100, False), ("sheet", 150, False), ("ring", 40, True), ("amulet", 190, True)):
        t = FB.Target(kind, mass, item)
        xs, prof = t.profile(120)
        v = (prof[:, 0] * prof[:, 1] * FB.shape_k(prof[:, 2])).sum() * t.length / 120
        assert abs(v - mass * FB.MM3_PER_G) / v < 0.02                     # объём цели — по массе
        b = FB.Bar(mass)                                                   # брусок точно по цели
        b.w, b.t, b.r = prof[:, 0].copy(), prof[:, 1].copy(), prof[:, 2].copy()
        b.dx = np.full(120, t.length / 120)
        assert b.score(t) > 0.95
        b.w, b.t = b.t.copy(), b.w.copy()                                  # повёрнут на ребро — та же деталь
        assert b.score(t) > 0.95
    short = FB.Bar(100)
    assert short.score(FB.Target("rod", 100)) < 0.3                       # сырой слиток — мимо цели
    assert FB.forged_score(0.9) == 1.0 and FB.forged_score(0.3) == 0.0


def test_tech_cards_operations():
    """Операции техкарты: разгонка — вширь (длина почти та же), протяжка — в длину, осадка — конец короче и
    толще, гибка — угол на участке, пробивка — сквозное отверстие едет вместе с металлом; объём — всегда тот же."""
    import numpy as np
    from sim import forge_card as FC
    b = FC.CardBar(150)
    v0, l0, w0 = b.volume(), b.length(), b.w.mean()
    b.spread(l0 / 2, 1.0, "sledge")
    assert b.w.max() > w0 * 1.15 and b.length() < l0 * 1.08                # вширь, а не в длину
    b2 = FC.CardBar(150)
    b2.orient = 0
    b2.strike(l0 / 2, 1.0, "hand")
    assert b2.length() > l0 * 1.04                                        # протяжка — длиннее
    u = FC.CardBar(150)
    t_end = u.t[-1]
    u.upset(1, 1.0)
    assert u.length() < l0 and u.t[-1] > t_end * 1.05                    # осадка правого торца
    c = FC.CardBar(60)
    L = c.length()
    for j in range(18):
        c.bend(L * (j + 0.5) / 18, 20.0, 3.0)
    assert abs(c.ang.sum() - 360) < 1e-6 and FC.bend_score(c, (0.0, 1.0, 360.0)) > 0.9
    assert FC.bend_score(c, (0.0, 0.3, 120.0)) < 0.5                     # гнули не там
    h = FC.CardBar(150)
    for _ in range(12):                                                   # брусок 25 мм — около 10 ударов
        h.punch(h.length() * 0.3, 5.0, 1.0)
    assert h.holes[0]["depth"] >= 1.0 and FC.holes_score(h, [(0.3, 5.0)]) > 0.85
    m0 = h.holes[0]["m"]
    h.orient = 0
    for k in range(8):
        h.strike(h.length() * (k + 0.5) / 8, 1.0, "hand")                # протянули — отверстие ушло с металлом
    assert h.holes[0]["m"] == m0 and abs(h.x_of_m(m0) / h.length() - 0.3) < 0.05
    for bar in (b, b2, u, c, h):
        assert abs(bar.volume() - bar.vol0) / bar.vol0 < 1e-6


def test_tech_cards_scoring_and_books():
    """Этапы оцениваются своей целью; итог — готовая форма + аккуратность этапов; трещины снижают. Техкарта
    мастера — книга (потолок 130%), без неё — базовая (100%)."""
    from sim import forge_card as FC
    assert FC.card_for("bracers", []) == "bracers" and FC.CARDS["bracers"]["cap"] == 1.0
    assert FC.card_for("bracers", ["c_bracers"]) == "bracers_master" and FC.CARDS["bracers_master"]["cap"] == 1.3
    assert len(FC.CARDS["bracers_master"]["stages"]) == len(FC.CARDS["bracers"]["stages"]) + 1
    for key in ("bracers", "belt", "ring", "amulet"):
        assert key in FG.RECIPES and all(st["op"] in FC.OPS for st in FC.CARDS[key]["stages"])
        assert FC.BOOK_CARDS[key] in FG.BOOKS
    raw = FC.CardBar(100)
    sc = [FC.stage_score(st, raw, FC.CARDS["rod"]["stages"]) for st in FC.CARDS["rod"]["stages"]]
    assert FC.final_score("rod", raw, sc) < 0.2                          # сырой слиток — мимо техкарты
    good = FC.CardBar(100)                                                # брусок точно по цели прута
    tgt = FC.stage_target(FC.CARDS["rod"]["stages"][-1], good, FC.CARDS["rod"]["stages"])
    xs, prof = tgt.profile(120)
    import numpy as np
    good.w, good.t, good.r = prof[:, 0].copy(), prof[:, 1].copy(), prof[:, 2].copy()
    good.dx = np.full(120, tgt.length / 120)
    good.ang = np.zeros(120)
    sc = [FC.stage_score(st, good, FC.CARDS["rod"]["stages"]) for st in FC.CARDS["rod"]["stages"]]
    best = FC.final_score("rod", good, sc)
    assert best > 0.9 and FC.final_score("rod", good, sc, cracks=2) < best * 0.75


def test_card_game_controls():
    """Игра по техкарте: удар по виду сверху — уже, по виду сбоку — тоньше; замах — сила; Enter — следующий
    этап; холодно — трещина; гибка — тянуть конец вокруг рога; пробивка — по метке."""
    import numpy as np
    from game.forge_card_game import CardGame
    pygame.init()
    rect = pygame.Rect(0, 0, 1120, 640)
    surf = pygame.Surface(rect.size)
    g = CardGame("iron", "bracers", ["punch"], 2, seed=1, mass=FG.item_mass("bracers"))
    g.draw(surf, rect)
    assert g.op == "draw" and g.can_abort()
    r, x0, ppm = g.views["top"]
    pos = (int(x0 + g.bar.length() * 0.5 * ppm), r.centery)
    w0, t0 = g.bar.w.copy(), g.bar.t.copy()
    g.pointer(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1), rect)
    g.update(0.6)
    g.pointer(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1), rect)
    for _ in range(12):
        g.update(1 / 60)
    assert g.hits == 1 and g.bar.w.min() < w0.min() and not g.can_abort()   # сверху — уже
    r, x0, ppm = g.views["side"]
    t1 = g.bar.t.min()
    g.temp = 1100
    g.strike("side", (int(x0 + g.bar.length() * 0.5 * ppm), r.centery), 1.0)
    assert g.bar.t.min() < t1                                             # сбоку — тоньше
    g.temp = 300
    g.strike("side", (int(x0 + g.bar.length() * 0.3 * ppm), r.centery), 1.0)
    assert g.cracks == 1
    g.key(pygame.K_RETURN)
    g.key(pygame.K_RETURN)
    assert g.op == "punch" and len(g.scores) == 2
    g.temp = 1100
    g.draw(surf, rect)
    r, x0, ppm = g.views["top"]
    for _ in range(25):                                                   # толстый брусок пробивать долго
        g.temp = 1100
        g.strike("top", (int(x0 + g.bar.length() * 0.12 * ppm), r.centery), 1.0)
    assert any(h["depth"] >= 1 and not h["rough"] for h in g.bar.holes)  # пробойник — ровное
    g.key(pygame.K_RETURN)
    assert g.op == "bend"
    g.temp = 900
    g.draw(surf, rect)
    (cx, cy), hr = g.horn()
    g.pointer(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(cx + 80, cy - 40), button=1), rect)
    g.pointer(pygame.event.Event(pygame.MOUSEMOTION, pos=(cx + 80, cy + 60), rel=(0, 100), buttons=(1, 0, 0)), rect)
    g.pointer(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(cx + 80, cy + 60), button=1), rect)
    assert g.bar.ang.sum() > 40                                           # тянули конец вниз вокруг рога — гнётся
    g.wheel(-1)
    g.draw(surf, rect)
    g.key(pygame.K_RETURN)
    assert g.done and set(g.result) >= {"score", "stages", "card", "len"} and len(g.result["stages"]) == 4
