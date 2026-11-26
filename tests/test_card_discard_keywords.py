import pytest

from deck import model as M
from test_deck import finish
from test_pyro_spirits import arena


def keyword_card(battle, *rules, reactions=None):
    definition = {
        "name": "Проверка",
        "cost": 0,
        "type": "skill",
        "main": {"target": "self", "do": []},
        "rules": list(rules),
        "reactions": reactions or {},
    }
    card = M.Card("keyword_test", {"keyword_test": definition})
    battle.hand.append(card)
    return card


def test_quietus_reacts_to_discard_and_stays_in_used_until_turn_end():
    battle, victim = arena()
    hero = battle.hero
    hero.hp -= 5
    hp = hero.hp
    card = keyword_card(battle, "quietus", reactions={"quietus": [{"op": "heal", "n": 2}]})
    battle.pending_discard = 1
    battle.resolve_discard([card])
    assert hero.hp == hp + 2
    assert card in battle.used and card not in battle.discard
    battle.draw(1)
    assert card not in battle.hand
    victim.ds["stun"] = True
    finish(battle.end_turn())
    assert card in battle.hand
    assert hero.hp == hp + 2


@pytest.mark.parametrize("shield,expected", [(29, 89), (30, 30)])
def test_blessing_uses_fraction_of_max_health_on_discard(shield, expected):
    battle, _ = arena()
    hero = battle.hero
    hero.max_hp = 100
    hero.shield = shield
    card = keyword_card(battle, "blessing")
    battle.pending_discard = 1
    battle.resolve_discard([card])
    assert hero.shield == expected


def test_linked_manual_play_discards_other_linked_and_spends_rules():
    battle, _ = arena()
    first = keyword_card(battle, "linked")
    second = keyword_card(battle, "linked", "quietus")
    ordinary = keyword_card(battle)
    finish(battle.play(first, "main", battle.hero))
    assert battle.hand == [ordinary]
    assert first in battle.used and second in battle.used
    assert "linked" not in first.tag_ids and "linked" not in second.tag_ids
    assert "linked" in first.base["rules"] and "linked" in second.base["rules"]


def test_automatic_linked_play_keeps_other_cards_and_the_rule():
    battle, _ = arena()
    first = keyword_card(battle, "linked")
    second = keyword_card(battle, "linked")
    finish(battle.play(first, "main", battle.hero, free=True, auto=True))
    assert second in battle.hand and "linked" in first.tag_ids
