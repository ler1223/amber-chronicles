import pytest

from deck import model as M
from test_deck import card, finish
from test_pyro_spirits import add_spirit, arena


def play_at_heat(battle, cid, heat, target):
    choice = card(battle, cid)
    choice.lvl = heat - 1
    battle.hero.ds["heat"] = heat
    finish(battle.play(choice, "main", target))
    assert choice not in battle.hand
    assert battle.hero.ds["heat"] == 0


def test_stoke_requires_two_distinct_cards_at_two_heat():
    battle, _ = arena()
    ember = add_spirit(battle, "t_spirit_ember")
    ash = add_spirit(battle, "t_spirit_ash")
    stoke = card(battle, "p_stoke_embers")
    stoke.lvl = 1
    battle.hero.ds["heat"] = 2
    battle.hero.hp -= 5
    hp = battle.hero.hp

    assert battle.targets(stoke, "main") == [ember, ash]
    finish(battle.play(stoke, "main", (ember, ember)))
    assert stoke in battle.hand
    assert battle.hero.ds["heat"] == 2

    finish(battle.play(stoke, "main", (ember, ash)))
    assert battle.temper[ember.uid] == 2 and battle.hero.hp == hp + 2
    assert battle.hero.shield == 4


def test_stoke_at_three_heat_offers_non_spirit_and_doubles_effect(monkeypatch):
    battle, _ = arena()
    ember = add_spirit(battle, "t_spirit_ember")
    definition = {**battle.run.defs["p_wall"], "rules": ["retain"], "ranks": [{}, {}]}
    battle.run.defs["test_non_spirit_retain"] = definition
    monkeypatch.setattr(battle.rng, "choice", lambda pool: pool[pool.index("test_non_spirit_retain")])

    play_at_heat(battle, "p_stoke_embers", 3, ember)

    created = next(c for c in battle.hand if c.cid == "test_non_spirit_retain")
    assert created.rank == 1
    assert battle.temper[ember.uid] == 4
    assert battle.hero.shield == 4


@pytest.mark.parametrize("heat,shield", [(1, 4), (2, 6), (3, 8)])
def test_ash_cover_keeps_cards_for_this_turn_only(heat, shield):
    battle, foe = arena()
    bolt = card(battle, "p_bolt")
    wall = card(battle, "p_wall")
    battle.draw_pile = [M.Card("p_bolt", battle.run.defs) for _ in range(battle.hand_size)]
    target = (bolt, wall) if heat == 2 else bolt
    play_at_heat(battle, "p_ash_cover", heat, target)
    assert battle.hero.shield == shield
    foe.ds["stun"] = True
    finish(battle.end_turn())

    assert bolt in battle.hand
    assert (wall in battle.hand) == (heat == 2)
    assert not battle.temporary_retain
    if heat == 3:
        assert battle.effective_cost(bolt) == bolt.cost - 1


@pytest.mark.parametrize("heat,damage,block", [(1, 1, 0), (2, 0, 2), (3, 1, 2)])
def test_forge_patience_rewards_only_the_cards_retained_at_turn_end(monkeypatch, heat, damage, block):
    battle, foe = arena()
    ember = add_spirit(battle, "t_spirit_ember")
    card(battle, "p_wall")
    seen_block = []
    gain_shield = battle.gain_shield

    def record_shield(unit, amount):
        seen_block.append(amount)
        return gain_shield(unit, amount)

    monkeypatch.setattr(battle, "gain_shield", record_shield)
    play_at_heat(battle, "p_forge_patience", heat, battle.hero)
    assert seen_block == [heat + 3]
    foe.ds["stun"] = True
    finish(battle.end_turn())

    assert seen_block == ([heat + 3, block] if block else [heat + 3])
    assert battle.card_damage_buff(battle.hero, ember) == damage
