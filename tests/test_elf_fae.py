"""Эльф: феи, пороги, растения, прививки, звери и сборка оружия."""
from deck import model as M
from deck.battle import finish
from test_deck import card, hero_battle, put


def test_elf_starts_with_fae_starter_and_mechanic():
    b, run = hero_battle("elf")
    assert b.mech == "fae"
    assert run.hero_name == "Эльф"
    assert [c.cid for c in run.deck] == [
        "e_basic_attack", "e_basic_attack", "e_basic_defense", "e_basic_defense",
        "e_basic_move", "e_basic_move", "e_call_fae", "e_moon_arrow",
        "e_moon_shield", "e_astral_step",
    ]
    assert b.hero.ds["fae"] == 0


def test_fae_are_capped_and_excess_becomes_shield():
    b, _ = hero_battle("elf")
    b.gain_fae(12)
    assert b.hero.ds["fae"] == 10
    assert b.hero.shield == 2


def test_moon_arrow_scales_from_current_fae_and_has_line_threshold():
    b, _ = hero_battle("elf")
    h = b.hero
    h.ds["fae"] = 5
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    arrow = card(b, "e_moon_arrow")
    hp = foe.hp
    finish(b.play(arrow, "main", foe))
    assert hp - foe.hp == 11
    h.ds["fae"] = 6
    assert b.line_only(arrow.d["main"])


def test_plant_grows_each_turn_and_matures():
    b, _ = hero_battle("elf")
    b.energy = 9
    seed = card(b, "e_thorn_seed")
    spots = b.targets(seed, "main")
    assert spots
    finish(b.play(seed, "main", spots[0]))
    plant = b.garden.plants[0]
    assert plant.growth == 0
    finish(b.end_turn())
    assert plant.growth == 1
    finish(b.end_turn())
    assert plant.growth == 2
    finish(b.end_turn())
    assert plant not in b.garden.plants


def test_attachment_gives_host_retain_and_triggers_after_main_card():
    b, _ = hero_battle("elf")
    h = b.hero
    host = card(b, "e_basic_attack")
    graft = card(b, "e_ivy_graft")
    finish(b.play(graft, "main", host))
    assert b.garden.attached(host)
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    finish(b.play(host, "main", foe))
    assert not b.garden.attached(host)
    assert h.ds["fae"] == 2
    assert h.shield >= 4


def test_blueprint_assembles_weapon_when_all_parts_are_in_hand():
    b, _ = hero_battle("elf")
    b.energy = 9
    blueprint = card(b, "e_moon_scythe")
    finish(b.play(blueprint, "main", b.hero))
    weapons = [c for c in b.hand if c.cid == "e_weapon_scythe"]
    assert len(weapons) == 1
    assert not any(c.cid.startswith("e_part_scythe") for c in b.hand)


def test_linked_partner_stays_in_hand_and_boosts_damage():
    b, _ = hero_battle("elf")
    h = b.hero
    first = card(b, "e_ariadne_thread")
    partner = card(b, "e_twin_stars")
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    hp = foe.hp
    finish(b.play(first, "main", foe))
    assert partner in b.hand
    assert hp - foe.hp == 9


def test_fae_crown_and_forest_pact_gain_fae_and_shield_at_turn_start():
    b, _ = hero_battle("elf")
    h = b.hero
    h.ds["fae"] = 5
    b.energy = 9
    for cid in ("e_fae_crown", "e_forest_pact"):
        finish(b.play(card(b, cid), "main", h))
    finish(b.start_player_turn())
    assert h.ds["fae"] == 7                                  # по +1 от каждой Силы
    assert h.shield >= 7                                     # Корона: 2 сверх 5, Лесной завет: 5


def test_eclipse_spends_all_and_stuns_at_threshold():
    b, _ = hero_battle("elf")
    h = b.hero
    h.ds["fae"] = 8
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    foe.hp = foe.max_hp = 100
    finish(b.play(card(b, "e_eclipse"), "main", h))
    assert h.ds["fae"] == 0
    assert foe.ds["stun"]


def test_weapon_balance_spends_all_and_heals_at_threshold():
    b, _ = hero_battle("elf")
    h = b.hero
    h.ds["fae"] = 8
    h.hp = 30
    foe = b.foes()[0]
    put(b, foe, (h.cell[0] + 1, h.cell[1]))
    weapon = card(b, "e_weapon_balance")
    finish(b.play(weapon, "main", foe.cell))
    assert h.ds["fae"] == 0
    assert h.shield >= 10 and h.hp == 38


def test_owl_herald_draws_at_the_start_of_the_next_turn():
    b, _ = hero_battle("elf")
    b.energy = 9
    owl = card(b, "e_owl_herald")
    finish(b.play(owl, "main", b.hero))
    assert "owl" in b.garden.beasts
    b.hand = []
    b.draw_pile = [M.Card("e_basic_attack", b.run.defs) for _ in range(10)] + b.draw_pile
    finish(b.start_player_turn())
    assert len(b.hand) == 6                                   # 5 обычных + карта совы
