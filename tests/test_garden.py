"""Сад алхимика: изометрическое поле, соседи, три стадии, сбор растений и траты на артефакты."""
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.data import GameData  # noqa: E402
from sim import expedition as X  # noqa: E402
from sim import artifacts as A  # noqa: E402

DATA = GameData()
ED = X.expedition_data(DATA)
XD = ED.expedition


def test_garden_data_and_costs():
    g = XD["garden"]
    assert g["cols"] * g["rows"] >= 6
    assert len(g["seeds"]) == 14
    for sid, seed in g["seeds"].items():
        assert seed["time"] > 0 and seed["yield"] >= 1 and seed["neighbors"]
        assert sid in XD["materials"]
    art = {"rarity": "common", "set": next(iter(XD["artifacts"]["sets"])), "level": 0}
    assert A.upgrade_cost(XD, art)["sunleaf"] >= 1
    assert A.enchant_cost(XD, art)["glory"] >= 1
    assert len(XD["artifacts"]["enchant_combos"]) >= 3
    assert {"bloodpoppy", "stormlotus", "bonemoss", "sugarvine", "tearcap",
            "dreampollen", "ironthorn", "sunpumpkin"} <= set(XD["artifacts"]["plant_effects"])


def test_garden_cycle_and_persistence(tmp_path):
    path = str(tmp_path / "profile.json")
    p = X.ExpeditionProfile(ED, path)
    assert len(p.garden) == p.garden_cols() * p.garden_rows()
    assert (p.garden_cols(), p.garden_rows()) == (3, 3)
    assert p.garden_seeds["sunleaf"] > 0
    assert p.garden_plant(0, "sunleaf")
    assert p.garden_plot(0)["state"] == "dry"
    assert p.garden_water(0)
    assert p.garden_plot(0)["state"] == "growing"
    assert not p.garden_water(0)
    p.garden[0]["watered"] = time.time() - 1000
    got = p.garden_harvest(0)
    assert got == {"sunleaf": XD["garden"]["seeds"]["sunleaf"]["yield"]}
    assert p.garden[0] is None
    assert p.mats["sunleaf"] == got["sunleaf"]
    p.save()
    again = X.ExpeditionProfile(ED, path)
    assert len(again.garden) == len(p.garden)
    assert again.garden_seeds == p.garden_seeds


def test_garden_three_growth_stages():
    p = X.ExpeditionProfile(ED)
    assert p.garden_plant(0, "sunleaf") and p.garden_water(0)
    total = 60.0 / p.garden_factor(0)
    p.garden[0]["watered"] = time.time() - total * 0.1
    assert p.garden_stage(0) == 0
    p.garden[0]["watered"] = time.time() - total * 0.5
    assert p.garden_stage(0) == 1
    p.garden[0]["watered"] = time.time() - total * 0.9
    assert p.garden_stage(0) == 2


def test_garden_neighbors_change_growth():
    p = X.ExpeditionProfile(ED)
    assert p.garden_plant(0, "sunleaf")
    assert p.garden_plant(1, "moonroot")
    p.garden_water(0)
    p.garden[0]["watered"] = time.time() - 10
    factor = p.garden_factor(0)
    assert factor > 1.0 and p.garden_neighbor_effects(0)
    assert p.garden_stage(0) in (0, 1)
    p.garden[1] = None
    p.garden[2] = {"seed": "frostbell", "watered": None}
    assert p.garden_factor(0) < factor
    assert p.garden_plot(0)["factor"] < factor


def test_garden_ui_plant_water_harvest(tmp_path):
    import pygame
    from tests.test_expedition_ui import new_app, frame, key, click
    from game import tavern_rooms as R

    app = new_app(tmp_path)
    prof = app.profile
    prof.glory = 500
    prof.buildings["ws_alchemy"] = 1
    key(app, pygame.K_3)
    click(app, ("station", "ws_alchemy"))
    assert isinstance(app.scene, R.StationScene)
    assert app.scene.overlay.mode == "garden"
    frame(app)
    click(app, ("seed", "sunleaf"))
    click(app, ("plot", 0))
    assert prof.garden[0] and prof.garden[0]["seed"] == "sunleaf"
    click(app, ("plot", 0))
    assert prof.garden[0]["watered"]
    prof.garden[0]["watered"] = time.time() - 1000
    click(app, ("plot", 0))
    assert prof.garden[0] is None
    assert prof.mats.get("sunleaf", 0) >= 1
    assert "sunleaf" in prof.garden_unlocked
    assert "thornbud" not in prof.garden_unlocked


def test_garden_expands_through_trader():
    p = X.ExpeditionProfile(ED)
    p.glory = 9999
    p.garden[0] = {"seed": "sunleaf", "watered": None}
    sizes = []
    while p.garden_upgrade_info():
        assert p.garden_upgrade()
        sizes.append((p.garden_cols(), p.garden_rows()))
    assert sizes == [(4, 3), (5, 3), (6, 3), (6, 4)]
    assert p.garden[0] and p.garden[0]["seed"] == "sunleaf"
    assert p.garden_upgrade_info() is None


def test_seed_tiers_open_with_chapters():
    p = X.ExpeditionProfile(ED)
    base = {"thornbud", "starflower", "emberfern", "frostbell"}
    assert {x["id"] for x in p.roll_seed_offers(random.Random(1))} <= base
    p.chapter_wins = {"swamp": 1}
    assert {x["id"] for x in p.roll_seed_offers(random.Random(1))} <= base | {"sugarvine", "sunpumpkin"}
    p.chapter_wins = {"swamp": 1, "forge": 1, "crypt": 1, "pass": 1}
    assert {x["id"] for x in p.roll_seed_offers(random.Random(1))} <= set(XD["garden"]["seeds"])


def test_seed_trader_unlocks_plant(tmp_path):
    p = X.ExpeditionProfile(ED, str(tmp_path / "profile.json"))
    assert p.garden_unlocked == ["sunleaf", "moonroot"]
    assert "thornbud" not in p.garden_unlocked
    p.glory = 500
    p.market["seeds"] = [{"id": "thornbud", "price": 48}]
    assert p.buy_trader_seed("thornbud")
    assert "thornbud" in p.garden_unlocked
    assert p.garden_seeds["thornbud"] == 1
    assert p.garden_plant(0, "thornbud")
    again = X.ExpeditionProfile(ED, str(tmp_path / "profile.json"))
    assert "thornbud" in again.garden_unlocked
    assert again.garden_seeds["thornbud"] == 0       # семя уже посажено


def test_seed_trader_ui(tmp_path):
    import pygame
    from tests.test_expedition_ui import new_app, frame, click
    from game import tavern_rooms as R

    app = new_app(tmp_path)
    prof = app.profile
    prof.glory = 500
    prof.market["seeds"] = [{"id": "thornbud", "price": 48}]
    R.go(app, "market")
    frame(app)
    click(app, "seed_trader")
    assert isinstance(app.scene.overlay, R.SeedTraderOverlay)
    click(app, ("seed_trader_buy", "thornbud"))
    assert "thornbud" in prof.garden_unlocked
    assert prof.garden_seeds["thornbud"] == 1


def test_enchant_overlay_ui(tmp_path):
    import pygame
    from tests.test_expedition_ui import new_app, frame, key, click
    from game import tavern_rooms as R

    app = new_app(tmp_path)
    prof = app.profile
    prof.glory = 9999
    prof.mats = {m: 99 for m in prof.xd["materials"]}
    prof.buildings.update(ws_forge=3, ws_alchemy=3)
    prof.garden_unlocked = list(prof.xd["garden"]["seeds"])
    art = prof.craft("ws_forge", "bracers", next(iter(prof.xd["artifacts"]["sets"])), 1.0)
    key(app, pygame.K_3)
    click(app, ("station", "ws_alchemy"))
    station = app.scene
    station.overlay.act(("mode", "art"))
    station.overlay.art_sel = art["uid"]
    frame(app)
    click(app, "enchant")
    assert isinstance(app.scene.overlay, R.EnchantOverlay)
    for pid in ("sunleaf", "moonroot", "starflower"):
        click(app, ("plant", pid))
    click(app, "apply")
    assert art["extra"] and art["extra"]["combo"] == "eclipse"


def test_enchant_three_plants_and_combo(tmp_path):
    p = X.ExpeditionProfile(ED, str(tmp_path / "profile.json"))
    p.glory = 9999
    p.mats = {m: 99 for m in XD["materials"]}
    p.buildings.update(ws_forge=3, ws_alchemy=3)
    p.garden_unlocked = list(XD["garden"]["seeds"])
    art = p.craft("ws_forge", "bracers", next(iter(XD["artifacts"]["sets"])), 1.0)
    res = p.enchant_with_plants(art["uid"], ["sunleaf", "moonroot", "starflower"])
    assert res and res["combo"]["id"] == "eclipse"
    assert art["garden_plants"] == ["sunleaf", "moonroot", "starflower"]
    assert art["extra"]["id"] == "third_spell" and art["extra"]["combo"] == "eclipse"
    assert p.mats["sunleaf"] < 99 and p.mats["moonroot"] < 99 and p.mats["starflower"] < 99
    lines = A.art_lines(XD, art)
    assert any("Растения:" in x for x in lines) and any("Затмение" in x for x in lines)
    mods, extra, rules = A.effects(XD, [art])
    assert mods and extra.get("enchants") and extra["enchants"][0]["id"] == "third_spell"
