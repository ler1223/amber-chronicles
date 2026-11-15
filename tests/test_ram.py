"""Землетряс: шкала Тряски, трещины и падающие валуны."""
from test_characters import setup
from test_rework1 import events, run


def test_ram_gauge_fills_from_quake_and_stun():
    c, h, foes = setup("ram", ["quake_strike"])
    h.pp = 0
    c._resolve_skill(h, "quake_strike", foes[0])
    run(c, 0.6)
    assert h.pp >= 2
    assert any(e["t"] == "gauge" and e.get("event") in ("quake", "stun") for e in c.events)


def test_ram_charged_skill_gets_unique_effect_and_spends_gauge():
    c, h, foes = setup("ram", ["quake_strike"])
    h.pp = h.pp_max
    h.cooldowns.clear()
    c._resolve_skill(h, "quake_strike", foes[0])
    run(c, 0.6)
    assert h.pp < h.pp_max
    assert events(c, "charged")
    assert any(z["kind"] == "quake" for z in c.zones)     # усиление оставляет трещину


def test_ram_stone_fist_charged_breaks_armor():
    c, h, foes = setup("ram", ["stone_fist"])
    h.pp = h.pp_max
    h.cooldowns.clear()
    c._resolve_skill(h, "stone_fist", foes[0])
    run(c, 0.4)
    assert "armor_shred" in foes[0].buffs
    assert events(c, "charged")


def test_ram_cracks_marks_cells_as_fissures():
    c, h, foes = setup("ram", ["cracks"])
    h.pp = 0
    h.cooldowns.clear()
    c._resolve_skill(h, "cracks", (5, 3))
    run(c, 0.8)
    assert c.grid.get((5, 3)).hazard == "cracks"
    assert c.grid.get((5, 3)).hazard_time > 0


def test_ram_collapse_drops_boulders_and_leaves_cracks():
    c, h, foes = setup("ram", ["ram_collapse"])
    h.pp = 0
    h.cooldowns.clear()
    c._resolve_skill(h, "ram_collapse", (5, 3))
    run(c, 0.8)
    assert any(u.alive and u.proto_id == "boulder" and u.owner is h for u in c.units)
    assert any(cell.hazard == "cracks" for cell in c.grid.cells.values())
    assert events(c, "rockfall")
