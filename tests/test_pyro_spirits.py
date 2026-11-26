import pygame
import pytest

from deck import model as M
from deck.battle import HAND_MAX
from deck.ui import Inspector
from sim.grid import Grid
from test_deck import card, finish, hero_battle, put
from ui import theme as T


SPIRITS = {"t_spirit_ember", "t_spirit_draft", "t_spirit_ash"}
ELEMENTALS = {"t_elemental_forge", "t_elemental_ash"}


def arena():
    battle, _ = hero_battle("pyro")
    battle.hand.clear()
    battle.draw_pile.clear()
    battle.c.grid = Grid(["." * 9] * 7, {".": {}})
    victim, *other_foes = battle.foes()
    for foe in other_foes:
        foe.alive = False
    victim.hp = victim.max_hp = 100
    victim.edef = {"cycle": [{"kind": "block", "n": 0, "name": "Защита"}]}
    put(battle, battle.hero, (1, 2))
    put(battle, victim, (4, 2))
    return battle, victim


def add_spirit(battle, cid, rank=1):
    battle.add_tokens(cid, 2 ** (rank - 1))
    return next(c for c in battle.hand if c.cid == cid and c.spirit_rank == rank)


def test_card_events_support_non_spirit_cards_with_explicit_rules():
    battle, foe = arena()
    hero = battle.hero
    hero.hp -= 30
    hp = hero.hp
    cid = "test_ranked_skill"
    definition = {
        **battle.run.defs["p_wall"],
        "name": "Ranked skill", "token": True, "tags": [],
        "rules": ["retain", "merge"],
        "reactions": {"entered_hand": [{"op": "heal", "n": 1}]},
        "ranks": [{}, {"reactions": {
            "merged": [{"op": "heal", "n": 3}],
            "retained": [{"op": "heal", "n": 5}],
            "discarded": [{"op": "heal", "n": 7}],
        }}],
    }
    battle.run.defs[cid] = definition

    battle.add_tokens(cid, 2)
    merged, = battle.hand
    assert merged.rank == 2 and "Дух" not in merged.tags
    finish(battle.react())
    assert hero.hp == hp + 5

    foe.ds["stun"] = True
    finish(battle.end_turn())
    assert merged in battle.hand and hero.hp == hp + 10

    battle.pending_discard = 1
    battle.resolve_discard([merged])
    assert merged in battle.discard and hero.hp == hp + 17


@pytest.mark.parametrize("mode", ["main", "alt"])
def test_card_play_and_exhaust_reactions_run_for_either_use(mode):
    battle, _ = arena()
    hero = battle.hero
    hero.hp -= 10
    hp = hero.hp
    cid = "test_token"
    self_use = {"target": "self", "do": []}
    battle.run.defs[cid] = {
        **battle.run.defs["t_spirit_ash"],
        "ranks": [], "rules": [],
        "main": self_use, "alt": self_use,
        "reactions": {
            "played": [{"op": "heal", "n": 2}],
            "exhausted": [{"op": "heal", "n": 3}],
        },
    }
    battle.add_tokens(cid, 1)
    token, = battle.hand

    finish(battle.play(token, mode, hero))

    assert token in battle.exhaust and hero.hp == hp + 5


def test_spirit_cards_are_created_from_the_displayed_pool():
    battle, run = hero_battle("pyro")
    battle.hand.clear()
    embers = card(battle, "p_living_embers")
    assert set(M.created_ids(embers.d)) == SPIRITS
    inspector = Inspector(embers, pinned=True)
    inspector.draw(pygame.Surface((T.SCREEN_W, T.SCREEN_H)), (0, 0))
    assert {c.cid for _, c in inspector.made_rects} == SPIRITS
    assert all(rect.bottom <= T.SCREEN_H for rect, _ in inspector.made_rects)
    assert "Создание" in embers.tags and "Дух" not in embers.tags
    assert embers.cid in M.tier1_pool(run.data, "pyro")

    embers.lvl = 0
    heat = battle.hero.ds["heat"]
    finish(battle.play(embers, "main", battle.hero))
    spirit, = battle.hand
    assert spirit.cid in SPIRITS and spirit.cost == 0 and "Дух" in spirit.tags
    assert spirit.spirit_rank == 1 and "retain" in M.card_rules(spirit.d)
    assert battle.hero.ds["heat"] == heat - 1
    assert all(c.cid not in SPIRITS for c in run.deck)


@pytest.mark.parametrize("heat", [1, 2, 3])
@pytest.mark.parametrize("guaranteed_coal", [False, True])
def test_living_embers_heat_modes(heat, guaranteed_coal):
    battle, _ = arena()
    embers = card(battle, "p_living_embers")
    if guaranteed_coal:
        embers.picks.append(1)
    battle.hero.ds["heat"] = 3
    embers.lvl = heat - 1

    finish(battle.play(embers, "main", battle.hero))

    assert battle.hero.ds["heat"] == 3 - heat
    assert all(c.cid in SPIRITS for c in battle.hand)
    assert len({c.cid for c in battle.hand}) == (2 if heat == 2 else 1)
    assert [c.rank for c in battle.hand] == ([1, 1] if heat == 2 else [2] if heat == 3 else [1])
    if guaranteed_coal:
        assert any(c.cid == "t_spirit_ember" for c in battle.hand)


def test_circle_creates_elemental_right_after_a_spirit():
    battle, _ = hero_battle("pyro")
    battle.hand.clear()
    circle = card(battle, "p_spirit_circle")
    assert set(M.created_ids(circle.d)) == ELEMENTALS
    finish(battle.play(circle, "main", battle.hero))
    assert not battle.hand and battle.hero.shield == 6

    spirit = add_spirit(battle, "t_spirit_ash")
    finish(battle.play(spirit, "main", battle.hero))
    assert spirit in battle.exhaust
    circle = card(battle, "p_spirit_circle")
    finish(battle.play(circle, "main", battle.hero))
    assert battle.hero.shield == 15
    elemental, = battle.hand
    assert elemental.cid in ELEMENTALS and elemental.cost == 0 and "Дух" in elemental.tags


@pytest.mark.parametrize("heat,damage", [(1, 7), (2, 10), (3, 14)])
def test_fire_whip_rewards_one_burning_enemy(heat, damage):
    battle, victim = arena()
    whip = card(battle, "p_whip")
    whip.lvl = heat - 1
    battle.hero.ds["heat"] = heat
    battle.add_burn(victim, 1)
    before = victim.hp

    finish(battle.play(whip, "main", victim))

    assert before - victim.hp == damage


def test_long_range_fire_lance_can_reach_its_bonus_threshold():
    battle, victim = arena()
    lance = M.Card("p_lance", battle.run.defs, picks=[1])
    battle.hand.append(lance)
    battle.hero.ds["heat"] = 1
    put(battle, victim, (6, 2))
    before = victim.hp
    assert victim in battle.targets(lance, "main")

    finish(battle.play(lance, "main", victim))

    assert before - victim.hp == 9


def test_furnace_draft_uses_number_of_spirits_played_this_turn():
    battle, _ = hero_battle("pyro")
    battle.c.grid = Grid(["." * 9] * 7, {".": {}})
    victim, *other_foes = battle.foes()
    for foe in other_foes:
        foe.alive = False
    put(battle, battle.hero, (1, 2))
    put(battle, victim, (5, 2))
    finish(battle.play(card(battle, "p_furnace_draft"), "main", victim))
    assert victim.cell == (4, 2)

    put(battle, victim, (5, 2))
    for _ in range(2):
        finish(battle.play(add_spirit(battle, "t_spirit_ash"), "main", battle.hero))
    finish(battle.play(card(battle, "p_furnace_draft"), "main", victim))
    assert victim.cell == (2, 2)


@pytest.mark.parametrize("cid", sorted(SPIRITS))
def test_equal_spirits_merge_and_rank_three_is_terminal(cid):
    battle, _ = arena()
    battle.add_tokens(cid, 1)
    assert [c.spirit_rank for c in battle.hand] == [1]

    battle.add_tokens(cid, 1)
    assert [c.spirit_rank for c in battle.hand] == [2]

    battle.add_tokens(cid, 1)
    assert sorted(c.spirit_rank for c in battle.hand) == [1, 2]

    battle.add_tokens(cid, 1)
    assert [c.spirit_rank for c in battle.hand] == [3]

    battle.add_tokens(cid, 4)
    assert [c.spirit_rank for c in battle.hand] == [3, 3]


@pytest.mark.parametrize("rank_two_bonus,rank_one_bonus", [(16, 9), (6, 13)])
def test_ember_keeps_strongest_accumulated_bonus_after_chain_merge(rank_two_bonus, rank_one_bonus):
    battle, _ = arena()
    rank_two = add_spirit(battle, "t_spirit_ember", 2)
    rank_one = add_spirit(battle, "t_spirit_ember")
    battle.temper[rank_two.uid] = rank_two_bonus
    battle.temper[rank_one.uid] = rank_one_bonus

    battle.add_tokens("t_spirit_ember", 1)
    rank_three, = battle.hand
    assert rank_three.spirit_rank == 3
    assert battle.temper[rank_three.uid] == max(rank_two_bonus, rank_one_bonus)


@pytest.mark.parametrize("created", [True, False])
def test_spirit_can_merge_into_a_full_hand(created):
    battle, _ = arena()
    add_spirit(battle, "t_spirit_ember")
    filler = [card(battle, "p_bolt") for _ in range(HAND_MAX - 1)]
    if created:
        battle.add_tokens("t_spirit_draft", 1)
    else:
        nonmatching = M.Card("t_spirit_draft", battle.run.defs)
        battle.draw_pile.append(nonmatching)
        battle.draw(1)
        assert battle.draw_pile == [nonmatching]
    assert len(battle.hand) == HAND_MAX and all(c.cid != "t_spirit_draft" for c in battle.hand)
    if created:
        battle.add_tokens("t_spirit_ember", 1)
    else:
        battle.draw_pile.append(M.Card("t_spirit_ember", battle.run.defs))
        battle.draw(1)
        assert battle.draw_pile == [nonmatching]
    assert len(battle.hand) == HAND_MAX and all(c in battle.hand for c in filler)
    assert [c.spirit_rank for c in battle.hand if c.cid == "t_spirit_ember"] == [2]


@pytest.mark.parametrize("rank,heal,growth,fire_bonus", [(1, 2, 2, 2), (2, 3, 3, 3), (3, 4, 5, 4)])
def test_retained_spirits_gain_their_rank_bonuses_each_turn(rank, heal, growth, fire_bonus):
    battle, victim = arena()
    hero = battle.hero
    ember = add_spirit(battle, "t_spirit_ember", rank)
    draft = add_spirit(battle, "t_spirit_draft", rank)
    ash = add_spirit(battle, "t_spirit_ash", rank)
    battle.temper[ember.uid] = 30
    hero.hp -= 10
    hp = hero.hp

    for elapsed in (1, 2):
        victim.ds["stun"] = True
        finish(battle.end_turn())
        assert set(battle.hand) == {ember, draft, ash}
        assert hero.hp == hp + elapsed * heal
        assert battle.temper[ember.uid] == 30 + elapsed * growth

    # Огненный навык перед атакой не расходует бонус, первая огненная атака расходует его целиком.
    hero.ds["heat"] = 4
    wall = card(battle, "p_wall")
    assert wall.d["type"] == "skill" and "Огонь" in wall.tags
    finish(battle.play(wall, "main", (2, 3)))
    for bonus in (fire_bonus, 0):
        bolt = card(battle, "p_bolt")
        assert "Огонь" in bolt.tags
        before = victim.hp
        finish(battle.play(bolt, "main", victim))
        assert before - victim.hp == 4 + bonus


def test_retained_spirits_at_rank_three_each_trigger():
    battle, victim = arena()
    for cid in sorted(SPIRITS):
        battle.add_tokens(cid, 8)
    assert len(battle.hand) == 6 and all(c.spirit_rank == 3 for c in battle.hand)
    embers = [c for c in battle.hand if c.cid == "t_spirit_ember"]
    battle.hero.hp -= 10
    hp = battle.hero.hp
    victim.ds["stun"] = True

    finish(battle.end_turn())
    assert len(battle.hand) == 6 and battle.hero.hp == hp + 8
    assert [battle.temper[c.uid] for c in embers] == [5, 5]
    attack = card(battle, "p_bolt")
    before = victim.hp
    finish(battle.play(attack, "main", victim))
    assert before - victim.hp == 12


def test_unit_card_damage_buff_uses_tag_type_and_turn():
    battle, victim = arena()
    hero = battle.hero
    bolt = card(battle, "p_bolt")
    buff = {"op": "card_damage_buff", "n": 3, "tag": "fire", "type": "attack"}
    finish(battle.apply(victim, [buff], None))
    finish(battle.apply(hero, [dict(buff, delay=2)], None))
    assert hero.ds["card_damage_buffs"] is not victim.ds["card_damage_buffs"]
    assert battle.card_damage_buff(hero, bolt) == 0
    finish(battle.start_player_turn())
    assert battle.card_damage_buff(hero, bolt) == 0
    finish(battle.start_player_turn())
    assert battle.card_damage_buff(hero, bolt) == 3
    assert battle.card_damage_buff(hero, bolt, consume=True) == 3
    assert battle.card_damage_buff(hero, bolt) == 0


@pytest.mark.parametrize("rank,damage", [(1, 4), (2, 7), (3, 11)])
def test_ember_play_damage_and_ignition_shape(rank, damage):
    battle, victim = arena()
    ember = add_spirit(battle, "t_spirit_ember", rank)
    hp = victim.hp
    heat = battle.hero.ds["heat"]
    finish(battle.play(ember, "main", victim))
    assert victim.hp == hp - damage and battle.hero.ds["heat"] == heat
    assert ember in battle.exhaust
    fires = {p for p, cell in battle.c.grid.cells.items() if cell.hazard == "fire"}
    x, y = victim.cell
    expected = (set(), {victim.cell}, {victim.cell, (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)})
    assert fires == expected[rank - 1]


@pytest.mark.parametrize("rank,pull,burn", [(1, 1, 0), (2, 2, 0), (3, 2, 2)])
def test_draft_play_scales_pull_and_burns_if_target_moves(rank, pull, burn):
    battle, victim = arena()
    draft = add_spirit(battle, "t_spirit_draft", rank)
    finish(battle.play(draft, "main", victim))
    assert victim.cell == (4 - pull, 2) and victim.ds["burn"] == burn
    assert draft in battle.exhaust

    if rank == 3:
        close = (2, 2)
        put(battle, victim, close)
        victim.ds["burn"] = 0
        second = add_spirit(battle, "t_spirit_draft", 3)
        finish(battle.play(second, "main", victim))
        assert victim.cell == close and victim.ds["burn"] == 0


@pytest.mark.parametrize("rank,block,burn,move", [(1, 3, 3, False), (2, 5, 2, False),
                                                 (3, 6, 2, False), (3, 6, 2, True)])
def test_ash_play_blocks_clears_burn_and_can_step_at_rank_three(rank, block, burn, move):
    battle, _ = arena()
    hero = battle.hero
    ash = add_spirit(battle, "t_spirit_ash", rank)
    hero.ds["burn"] = 3
    origin = hero.cell
    target = (1, 3) if move else origin if rank == 3 else hero
    assert target in battle.targets(ash, "main")
    finish(battle.play(ash, "main", target))
    assert hero.cell == ((1, 3) if move else origin)
    assert hero.shield == block and hero.ds["burn"] == burn
    assert ash in battle.exhaust
