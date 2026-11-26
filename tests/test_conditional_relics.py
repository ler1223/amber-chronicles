from deck import model as M
from test_deck import card, finish, put
from test_pyro_spirits import add_spirit, arena
from test_retain_relics import equip


def test_pathfinder_chalk_matches_first_step_to_water_or_ice():
    battle, _ = arena()
    equip(battle, "pathfinder_chalk")
    battle.hero.ds["heat"] = 3
    battle.c.grid.get((3, 2)).terrain = "water"
    battle.c.grid.get((3, 3)).terrain = "ice"

    finish(battle.play(card(battle, "p_stride"), "main", (2, 2)))
    assert battle.hero.shield == 0
    finish(battle.play(card(battle, "p_stride"), "main", (3, 2)))
    assert battle.hero.shield == 4
    finish(battle.play(card(battle, "p_stride"), "main", (3, 3)))
    assert battle.hero.shield == 4


def test_ember_clasp_adds_heat_only_on_the_following_turn():
    battle, foe = arena()
    equip(battle, "ember_clasp")
    add_spirit(battle, "t_spirit_ember", 2)
    add_spirit(battle, "t_spirit_ember")
    hero = battle.hero
    hero.ds["heat"] = 0
    foe.ds["stun"] = True

    finish(battle.end_turn())

    assert hero.ds["heat"] == battle.hero_def["heat_turn"] + 1
    assert battle.energy == 0


def test_trapper_bracket_bonuses_only_first_displacement_after_trap():
    battle, foe = arena()
    equip(battle, "trapper_bracket")
    battle.energy = 4
    put(battle, foe, (5, 2))

    finish(battle.play(card(battle, "h_trap"), "main", (1, 0)))
    finish(battle.play(card(battle, "h_lure"), "main", foe))
    assert foe.cell == (2, 2)

    put(battle, foe, (5, 2))
    finish(battle.play(card(battle, "h_trap"), "main", (1, 1)))
    finish(battle.play(card(battle, "h_lure"), "main", foe))
    assert foe.cell == (3, 2)


def test_ash_case_arms_on_ordinary_exhaust_and_rewards_next_defense_once():
    battle, _ = arena()
    equip(battle, "ash_case")
    battle.energy = 3
    hero = battle.hero

    finish(battle.exhaust_card(M.Card("t_spirit_ember", battle.run.defs)))
    finish(battle.play(card(battle, "defend"), "main", hero))
    assert hero.shield == 5

    finish(battle.exhaust_card(M.Card("strike", battle.run.defs)))
    finish(battle.play(card(battle, "defend"), "main", hero))
    assert hero.shield == 13
    finish(battle.play(card(battle, "defend"), "main", hero))
    assert hero.shield == 18


def test_duelist_braid_draws_after_first_defense_strike_pair():
    battle, foe = arena()
    equip(battle, "duelist_braid")
    battle.energy = 5
    put(battle, foe, (2, 2))
    hero = battle.hero
    battle.draw_pile = [M.Card("defend", battle.run.defs) for _ in range(2)]

    finish(battle.play(card(battle, "strike"), "main", foe))
    assert len(battle.draw_pile) == 2
    for _ in range(2):
        finish(battle.play(card(battle, "defend"), "main", hero))
        finish(battle.play(card(battle, "strike"), "main", foe))
        assert len(battle.draw_pile) == 1
