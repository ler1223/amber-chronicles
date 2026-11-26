import pytest

from test_deck import card, finish
from test_pyro_spirits import add_spirit, arena


def equip(battle, *ids):
    catalog = battle.run.data["relics"]["relics"]
    battle.run.relics = [dict(catalog[cid], id=cid) for cid in ids]


def test_retain_relics_trigger_only_on_actual_end_of_turn(monkeypatch):
    battle, foe = arena()
    equip(battle, "retain_quilt", "retain_bookmark")
    cards = [add_spirit(battle, cid) for cid in ("t_spirit_ash", "t_spirit_ember")]
    draw_counts = []
    ending_shields = []
    tick_end = battle.tick_end

    def track_shield(unit):
        if unit is battle.hero:
            ending_shields.append(unit.shield)
        tick_end(unit)

    monkeypatch.setattr(battle, "draw", draw_counts.append)
    monkeypatch.setattr(battle, "tick_end", track_shield)
    turn = battle.turn

    finish(battle.card_event("retained", cards[0]))
    assert not battle.items.retention and not battle.hero.shield

    for elapsed in range(3):
        foe.ds["stun"] = True
        finish(battle.end_turn())
        assert all(battle.items.retention[c.uid] == (turn + elapsed, elapsed + 1) for c in cards)
    assert draw_counts == [battle.hand_size, battle.hand_size + 1, battle.hand_size]
    assert ending_shields == [2, 2, 2]
    assert sum(text.startswith("Стёганый чехол:") for text, _ in battle.log) == 3
    assert sum(text.startswith("Закладка с насечками:") for text, _ in battle.log) == 1


@pytest.mark.parametrize("cid,pool", [("p_bolt", "heat"), ("defend", "energy")])
def test_bellows_discount_is_paid_once_and_skips_free_cards(cid, pool):
    battle, foe = arena()
    equip(battle, "retain_bellows")
    hero = battle.hero
    paid = [card(battle, cid) for _ in range(2)]
    assert battle.effective_cost(paid[0]) == paid[0].cost
    for c in paid:
        battle.temporary_retain[c.uid] = 0
    free = add_spirit(battle, "t_spirit_ash")
    foe.ds["stun"] = True
    finish(battle.end_turn())

    hero.ds["heat"] = battle.energy = 0
    battle.sync_levels()
    finish(battle.play(free, "main", hero))
    assert battle.effective_cost(paid[0]) == 0
    assert battle.can_afford(paid[0])
    target = foe if pool == "heat" else hero
    assert target in battle.targets(paid[0], "main")
    finish(battle.play(paid[0], "main", target))

    assert paid[0] not in battle.hand
    assert hero.ds["heat"] == battle.energy == 0
    assert battle.effective_cost(paid[1]) == 1
    assert not battle.can_afford(paid[1])


def test_card_discount_that_makes_card_free_preserves_bellows():
    battle, foe = arena()
    equip(battle, "retain_bellows")
    first, second = [card(battle, "p_bolt") for _ in range(2)]
    battle.temporary_retain.update({first.uid: 1, second.uid: 0})
    foe.ds["stun"] = True
    finish(battle.end_turn())

    battle.hero.ds["heat"] = 0
    first.lvl = 0
    first.manual = True
    battle.sync_levels()
    finish(battle.play(first, "main", foe))
    assert first not in battle.hand
    assert first.uid not in battle.retained_card_discounts
    assert battle.effective_cost(second) == 0


def test_merging_resets_streak_for_a_previously_retained_instance():
    battle, foe = arena()
    equip(battle, "retain_bookmark")
    retained = add_spirit(battle, "t_spirit_ember")
    foe.ds["stun"] = True
    finish(battle.end_turn())
    battle.hand.remove(retained)
    add_spirit(battle, "t_spirit_ember")
    battle.receive_card(retained)

    assert retained.rank == 2
    assert retained.uid not in battle.items.retention
    foe.ds["stun"] = True
    finish(battle.end_turn())
    assert battle.items.retention[retained.uid][1] == 1
    assert all(not text.startswith("Закладка с насечками:") for text, _ in battle.log)
