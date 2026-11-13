"""Артефакты и мастерские (квиз 2026-11-11): хранилище таверны, ячеек = ранг (1–5), сеты с бонусами за 2 и 4 вещи,
ковка с качеством из мини-игры, улучшение +1…+10 и самоцветы; слой артефактов множится на рост похода;
материалы — с боёв (редкие главы — с элиты и боссов) и с поручений; 10 ступеней сложности."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.data import GameData  # noqa: E402
from sim import expedition as X  # noqa: E402
from sim import artifacts as A  # noqa: E402

DATA = GameData()
ED = X.expedition_data(DATA)
XD = ED.expedition
ART = XD["artifacts"]


def rich(tmp_path=None, **builds):
    p = X.ExpeditionProfile(ED, str(tmp_path / "exp.json") if tmp_path else None)
    p.glory = 99999
    p.mats = {m: 99 for m in XD["materials"]}
    p.trophies = {t: 9 for t in XD["trophies"]}
    for ws in ("ws_forge", "ws_jewel", "ws_leather", "ws_alchemy"):
        p.buildings[ws] = len(XD["buildings"][ws]["levels"])
    p.buildings.update(builds)
    import random
    rng = random.Random(7)
    for gid in XD["artifacts"]["gems"]:                # необработанные камни — огранять есть что
        for _ in range(3):
            p.add_rough(gid, rng)
    return p


def sets_of(rarity):
    return [s for s, v in ART["sets"].items() if v["rarity"] == rarity]


def test_data_is_consistent():
    for k, v in ART["kinds"].items():
        assert v["workshop"] in XD["buildings"] and v["workshop"] in ART["main_mat"]
    for s, v in ART["sets"].items():
        assert v["rarity"] in ART["rarities"] and set(v["bonus"]) <= {"2", "3", "4", "5"}
        assert v["mat"] is None or XD["materials"][v["mat"]]["rare"]
        for b in v["bonus"].values():
            for r in b.get("rules", []):
                assert r["trigger"] in XD["items"]["triggers"] and all(e in XD["items"]["effects"] for e in r["do"])
    assert all(x in XD["items"]["stat_affixes"] for x in ART["extras"])
    assert len(XD["config"]["tiers"]) == 10
    assert [int(k) for k in XD["tavern"]["ranks"]] == [1, 2, 3, 4, 5]


def test_craft_pays_and_quality_matters():
    p = rich()
    s = sets_of("rare")[0]
    cost = A.craft_cost(XD, "ws_forge", s)
    g0, ore0 = p.glory, p.mats["ore"]
    lo = p.craft("ws_forge", "bracers", s, 0.7)
    hi = p.craft("ws_forge", "bracers", s, 1.3)
    assert lo and hi and p.glory == g0 - 2 * cost["glory"] and p.mats["ore"] == ore0 - 2 * cost.get("ore", 0)
    assert A.power_k(XD, hi) > A.power_k(XD, lo)
    assert hi["extra"] and not lo["extra"]                      # работа мастера — свойство
    assert not p.craft("ws_jewel", "bracers", s, 1.0)            # наручи — только в кузне


def test_workshop_level_gates_rarity_and_costs():
    p = rich(ws_forge=1)
    assert p.craft("ws_forge", "belt", sets_of("common")[0], 1.0)
    assert not p.craft("ws_forge", "belt", sets_of("rare")[0], 1.0)
    p.buildings["ws_forge"] = 0
    assert not p.craft("ws_forge", "belt", sets_of("common")[0], 1.0)
    p = rich()
    p.mats["stardust"] = 0
    assert not p.craft("ws_forge", "belt", sets_of("legendary")[0], 1.0)     # легендарное — со звёздной пылью


def test_slots_follow_rank_and_one_per_kind():
    p = rich()
    h = p.hall()[0]
    h.rank = 2
    s = sets_of("common")[0]
    a1 = p.craft("ws_forge", "bracers", s, 1.0)
    a2 = p.craft("ws_forge", "belt", s, 1.0)
    a3 = p.craft("ws_jewel", "ring", s, 1.0)
    a4 = p.craft("ws_forge", "bracers", s, 1.2)
    assert p.equip(h, a1["uid"]) and p.equip(h, a2["uid"])
    assert not p.equip(h, a3["uid"])                           # ранг 2 — две ячейки
    assert p.equip(h, a4["uid"]) and a1["uid"] not in h.arts   # тот же вид — замена
    other = p.hall()[1]
    assert p.equip(other, a2["uid"]) and a2["uid"] not in h.arts     # с другого героя — снимается
    assert p.unequip(other, a2["uid"]) and p.art_owner(a2["uid"]) is None


def test_artifacts_go_into_run_and_multiply_power():
    p = rich()
    h = p.hall()[0]
    h.rank = 5
    s = sets_of("legendary")[0]
    for kind, ws in (("bracers", "ws_forge"), ("belt", "ws_forge"), ("ring", "ws_jewel"), ("amulet", "ws_jewel")):
        art = p.craft(ws, kind, s, 1.0)
        art["level"] = 10
        assert p.equip(h, art["uid"])
    base = X.Expedition(ED, [X.Hero(h.to_dict() | {"arts": []})], 1, 0).proto(X.Hero(h.to_dict() | {"arts": []}))
    run = p.start([h.uid] + [x.uid for x in p.hall()[1:2]], seed=2)
    rh = next(x for x in run.heroes if x.uid == h.uid)
    pr = run.proto(rh)
    assert len(run.arts) == 4 and pr["hp"] > base["hp"] * 1.2 and pr["attack"]["damage"] > base["attack"]["damage"] * 1.2
    assert any(":set:" in r["id"] for r in pr["rules"])         # бонус 4 вещей сета — правило боя
    assert p.art_locked(h.arts[0]) and not p.upgrade_art(h.arts[0])   # в походе — не трогать
    again = X.Expedition.from_dict(ED, run.to_dict())
    assert again.proto(next(x for x in again.heroes if x.uid == h.uid))["hp"] == pr["hp"]


def test_full_legendary_set_is_about_double():
    arts = []
    s = sets_of("legendary")[0]
    for i, k in enumerate(ART["kinds"]):
        a = A.make(XD, f"x{i}", k, s, 1.0)
        a["level"] = ART["max_level"]
        a["gems"] = [{"id": "ruby" if j % 2 else "emerald", "q": 1.0} for j in range(A.sockets(XD, a))]
        arts.append(a)
    assert 1.7 <= A.power_score(XD, arts) <= 2.8


def test_set_bonus_needs_pieces():
    s = sets_of("epic")[0]
    one = [A.make(XD, "a", "bracers", s, 1.0)]
    two = one + [A.make(XD, "b", "belt", s, 1.0)]
    four = two + [A.make(XD, "c", "ring", s, 1.0), A.make(XD, "d", "amulet", s, 1.0)]
    assert not A.active_bonuses(XD, one)
    assert [n for _, n, _ in A.active_bonuses(XD, two)] == [2]
    assert [n for _, n, _ in A.active_bonuses(XD, four)] == [2, 4]


def test_upgrade_enchant_gems():
    p = rich(ws_alchemy=1)
    art = p.craft("ws_forge", "bracers", sets_of("common")[0], 1.0)
    for _ in range(3):
        assert p.upgrade_art(art["uid"])
    assert art["level"] == 3 and not p.upgrade_art(art["uid"])        # потолок алхимии 1-го уровня — +3
    ex = p.enchant(art["uid"], 1.2)
    assert ex and art["extra"]["q"] == 1.2
    rare = p.craft("ws_jewel", "ring", sets_of("rare")[0], 1.0)
    g = p.cut_gem("ruby", 1.1)
    assert g and p.socket(rare["uid"], g["uid"]) and rare["gems"][0]["q"] == 1.1
    g2 = p.cut_gem("emerald", 1.0)
    assert not p.socket(rare["uid"], g2["uid"])                        # у редкого — одно гнездо
    assert not p.socket(art["uid"], g2["uid"])                         # у обычного — нет гнёзд


def test_stash_survives_save_and_death(tmp_path):
    p = rich(tmp_path)
    h = p.hall()[0]
    art = p.craft("ws_leather", "talisman", sets_of("common")[0], 1.0)
    p.equip(h, art["uid"])
    again = X.ExpeditionProfile(ED, p.path)
    assert art["uid"] in again.stash and next(x for x in again.roster if x.uid == h.uid).arts == [art["uid"]]
    run = again.start([x.uid for x in again.hall()[:2]], seed=1)
    run.result = "defeat"
    again.finish(run)                                  # отряд пал — артефакт остаётся в хранилище
    assert art["uid"] in again.stash and again.art_owner(art["uid"]) is None


def test_battles_drop_materials_and_finish_keeps_them():
    p = rich()
    p.mats = {}
    run = p.start([h.uid for h in p.hall()[:2]], seed=4, tier=0)
    run.node = next(n for n, v in run.nodes.items() if v["type"] == "boss")
    got = run.drop_loot("boss", run.nodes[run.node])
    rare = next(m for m, v in XD["materials"].items() if v.get("chapter") == run.chapter)
    assert got.get(rare, 0) >= 1 and sum(got.values()) >= 3
    run.result = "victory"
    out = p.finish(run)
    assert out["loot"] and all(p.mats.get(k, 0) >= v for k, v in out["loot"].items())


def test_higher_steps_drop_more():
    def total(tier):
        p = X.ExpeditionProfile(ED, sandbox=True)
        n = 0
        for seed in range(20):
            run = X.Expedition(ED, [h for h in p.hall()[:2]], seed, 0, tier=tier)
            run.node = next(nid for nid, v in run.nodes.items() if v["type"] == "battle")
            n += sum(run.drop_loot("elite", run.nodes[run.node]).values())
        return n
    assert total(9) > total(0)


def test_old_save_tiers_migrate(tmp_path):
    import json
    p = rich(tmp_path)
    p.save()
    d = json.loads(open(p.path, encoding="utf-8").read())
    d.pop("tiers10")
    d["tier_open"], d["chapter_tiers"] = 2, {"forge": 1}
    open(p.path, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False))
    again = X.ExpeditionProfile(ED, p.path)
    mig = XD["config"]["tier_migrate"]
    assert again.tier_open == mig["2"] and again.chapter_tiers["forge"] == mig["1"]


def test_workshop_and_artifacts_screens(tmp_path):
    """Мастерская (3): станция кузни → ковка (мини-игра до конца) → артефакт в сундуке; ювелир — огранка;
    Сборы (2) — надеть артефакт из сундука."""
    import pygame
    from tests.test_expedition_ui import new_app, frame, key, click
    from game import tavern_rooms as R, workshop_scenes as WS, workshop_games as G
    app = new_app(tmp_path)
    prof = app.profile
    prof.glory, prof.mats = 5000, {m: 30 for m in XD["materials"]}
    prof.buildings.update(ws_forge=1, ws_jewel=1, ws_alchemy=1, ws_leather=1)
    key(app, pygame.K_3)
    room = app.scene
    assert isinstance(room, R.WorkshopRoom)
    click(app, ("station", "ws_leather"))
    station = app.scene                              # мастерская — отдельный экран
    assert isinstance(station, R.StationScene)
    st = station.overlay
    assert isinstance(st, R.StationOverlay) and st.full
    click(app, ("set", sets_of("common")[0]))
    key(app, pygame.K_RETURN)
    assert isinstance(app.scene, WS.MiniGameScene) and isinstance(app.scene.game, G.LeatherTrace)
    for _ in range(260):
        frame(app)
    assert app.scene.game.done
    key(app, pygame.K_RETURN)
    assert app.scene is station and station.overlay is st and len(prof.stash) == 1 and st.result
    key(app, pygame.K_ESCAPE)                        # Esc — назад в Мастерскую
    assert isinstance(app.scene, R.WorkshopRoom)
    room = app.scene
    for ws in ("ws_jewel", "ws_forge", "ws_alchemy"):       # все станции рисуются
        room.overlay = R.StationOverlay(room, ws)
        room.overlay.art_sel = next(iter(prof.stash))
        frame(app)
    room.overlay = R.StationOverlay(room, "ws_jewel")
    import random
    rough = prof.add_rough("ruby", random.Random(3))
    click(app, ("mode", "cut"))
    click(app, ("cut", rough["uid"]))
    g = app.scene.game
    key(app, pygame.K_ESCAPE)                       # ни одной грани — выход без потерь, камень цел
    assert app.scene is room and rough in prof.rough and not prof.gems
    click(app, ("cut", rough["uid"]))
    g = app.scene.game
    key(app, pygame.K_1)                            # выбрать огранку → разметка (Esc тоже без потерь)
    assert g.phase == "plan" and g.can_abort()
    key(app, pygame.K_RETURN)                       # на станок; сделать грань — дальше Esc уже досрочно
    assert g.phase == "cut"
    g.scores[0] = 0.5
    key(app, pygame.K_ESCAPE)
    assert g.done and g.quality < 0.85
    key(app, pygame.K_RETURN)
    assert prof.gems and rough not in prof.rough
    room.overlay = None
    click(app, "chest")
    assert isinstance(room.overlay, R.ChestOverlay)
    for tab in ("gems", "mats", "arts"):
        click(app, ("tab", tab))
    key(app, pygame.K_2)
    uid = next(iter(prof.stash))
    h = prof.hall()[0]
    click(app, ("slot", h.uid))
    click(app, ("art", uid))
    assert prof.art_owner(uid) is h


def cut_gem_game(cut, ang_err=0.0, overcut=0.0, index_err=0, diff=1, g=None):
    """Бот-огранщик: выбирает огранку (id), ставит индекс (с ошибкой), угол оправки (с ошибкой), опускает камень до
    пунктира (или глубже) и принимает грань."""
    import pygame
    from game import workshop_games as G
    from sim import gems as GM
    if g is None:
        g = G.JewelCut(3, diff=diff, disks=["lap_fine"])        # тонкий диск — грань без царапин
        g.choose(G.CUTS.index(GM.CUT_BY_ID[cut]))
    while not g.done:
        if g.need_flip():                              # низ готов — перевернуть камень на оправке
            g.key(pygame.K_f)
            for _ in range(200):
                g.update(1 / 60)
        f = g.facets[g.active]
        g.index = (f["dial"] + index_err) % G.NOTCHES
        g.theta = f["ang"] + ang_err
        n, off = g.target(f)
        g.press()
        for _ in range(4000):
            g.update(1 / 120)
            if g.extent() <= off - overcut + 0.3:
                break
        g.release()
        g.key(pygame.K_RETURN)
    return g


def test_gem_cutting_rewards_precision():
    import pygame
    from game import workshop_games as G
    from sim import gems as GM
    em = GM.CUT_BY_ID["emerald"]
    good = cut_gem_game("emerald")
    assert good.done and (good.quality - 0.7) / (em["cap"] - 0.7) > 0.93 and good.n == sum(G.cut_counts(em))
    skew = cut_gem_game("emerald", ang_err=6)
    deep = cut_gem_game("emerald", overcut=12)
    wrong = cut_gem_game("emerald", index_err=3)
    for bad in (skew, deep, wrong):
        assert bad.quality < good.quality - 0.08
    best = cut_gem_game("brilliant")                    # бриллиантовая — 33 грани, предел выше
    easy = cut_gem_game("table")
    assert best.n > easy.n and best.quality > easy.quality
    assert not hasattr(best, "time_left")               # огранка без ограничения по времени
    g = G.JewelCut(1)
    g.stop()
    assert g.done and g.quality == G.Q_LO

    g = G.JewelCut(2)
    g.key(pygame.K_1)
    while g.side_left(1):                              # низ не огранён — верх гранить нельзя, пока не перевернёшь
        g.scores[g.active] = 1.0
        g.pick_active()
    g.key(pygame.K_RETURN)
    assert g.need_flip() and None in g.scores
    g.key(pygame.K_f)
    assert g.side == -1 and g.facets[g.active]["side"] == -1


def test_inspect_during_cutting():
    """Tab — снять камень и рассмотреть: шлифовать нельзя, мышь вращает камень; Tab — назад на станок."""
    import pygame
    from game import workshop_games as G
    g = G.JewelCut(4)
    g.key(pygame.K_1)
    g.key(pygame.K_TAB)
    assert g.inspect is not None
    g.press()
    assert not g.hold
    rect = pygame.Rect(0, 0, 1120, 520)
    m0 = g.inspect.m
    g.pointer(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(300, 200), button=1), rect)
    g.pointer(pygame.event.Event(pygame.MOUSEMOTION, pos=(360, 230), rel=(60, 30), buttons=(1, 0, 0)), rect)
    assert g.inspect.m != m0
    g.pointer(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB, mod=0, unicode=""), rect)
    assert g.inspect is None


def test_cut_gem_keeps_shape_for_inventory(tmp_path):
    from game import gem3d as G3
    g = cut_gem_game("cushion")
    shape = g.shape()
    p = rich(tmp_path)
    gem = p.cut_gem("ruby", g.quality, shape=shape, cut=g.cut["id"])
    again = X.ExpeditionProfile(ED, p.path)
    saved = next(x for x in again.gems if x["uid"] == gem["uid"])
    assert saved["cut"] == "cushion" and len(G3.from_planes(saved["shape"])) == len(G3.polished(g.stone))


def test_minigames_score_range():
    from game import workshop_games as G
    for cls in G.GAMES.values():
        if cls is G.JewelCut:
            continue
        g = cls(1)
        for _ in range(400):
            g.update(1 / 30)
            if hasattr(g, "STRIKES") or hasattr(g, "FACETS"):
                g.press()
                g.update(1 / 30)
                g.release()
            if g.done:
                break
        assert g.done and G.Q_LO <= g.quality <= G.Q_HI


def test_rough_gems_are_rare_and_traded(tmp_path):
    """Самоцветы — редкость: огранить можно только свой необработанный камень; рынок продаёт и покупает,
    товар — после каждого похода; в вылазке — шанс от добытой крошки."""
    import random
    p = X.ExpeditionProfile(ED, str(tmp_path / "exp.json"))
    p.glory = 5000
    p.buildings["ws_jewel"] = 1
    assert p.cut_gem("ruby", 1.0) is None                 # нет камня — нечего гранить
    assert p.market.get("rough")
    lot = p.market["rough"][0]
    price = p.market_price("rough", lot)
    assert p.buy("rough", lot["uid"]) and p.glory == 5000 - price and lot in p.rough
    g = p.cut_gem(lot["uid"], 1.2)
    assert g and g["id"] == lot["id"] and not p.rough and g["size"] == round(lot["size"] * 0.2, 2)
    gold = p.glory
    assert p.sell("cut", g["uid"]) and p.glory == gold + int(p.market_price("cut", g) * XD["market"]["sell_k"])
    assert p.market_price("cut", dict(g, q=1.3)) > p.market_price("cut", dict(g, q=0.7))
    again = X.ExpeditionProfile(ED, p.path)
    assert any(x["uid"] == g["uid"] for x in again.market["cut"])
    found = 0
    for seed in range(200):                                # шанс в вылазке — от крошки, не каждый раз
        run = X.Expedition(ED, [h for h in p.hall()[:2]], seed, 0)
        run.loot = {"gems": 3}
        found += p.rough_drops(run) is not None
    assert 10 < found < 60
    run.loot = {}
    assert p.rough_drops(run) is None
    assert random


def test_same_rough_same_stone():
    """Камень предопределён: одинаковый seed — одинаковая заготовка на станке."""
    from game import workshop_games as G, gem3d as G3
    a, b = G.JewelCut(4242), G.JewelCut(4242)
    a.choose(2)
    b.choose(2)
    assert abs(G3.volume(a.stone) - G3.volume(b.stone)) < 1e-6


def test_jeweler_crafts_rings_without_minigame(tmp_path):
    import pygame
    from tests.test_expedition_ui import new_app, key, click
    from game import tavern_rooms as R
    app = new_app(tmp_path)
    prof = app.profile
    prof.glory, prof.mats = 5000, {m: 50 for m in XD["materials"]}
    prof.buildings["ws_jewel"] = 1
    key(app, pygame.K_3)
    room = app.scene
    room.overlay = R.StationOverlay(room, "ws_jewel")
    click(app, ("set", sets_of("common")[0]))
    click(app, "craft")
    assert not prof.stash                           # без оправы из кузни — нельзя
    prof.forge["prims"].append({"uid": "w1", "kind": "wire", "alloy": "silver925", "mass": 40, "q": 0.9, "cast": False})
    click(app, "craft")
    from tests.test_forge import assemble
    assemble(app, app.scene.game)                    # оправа собирается: проволоку — на контур, заклёпка, отжиг
    key(app, pygame.K_RETURN)
    art = next(iter(prof.stash.values()))
    assert app.scene is room and len(prof.stash) == 1 and art["alloys"] == ["silver925"] and not prof.forge["prims"]
    key(app, pygame.K_7)
    assert isinstance(app.scene, R.MarketRoom)
