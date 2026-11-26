from deck.battle import Battle
from test_deck import card, finish
from test_pyro_spirits import arena


def tagged(battle, *rules, tags=()):
    cid = "keyword_test"
    battle.run.defs[cid] = {
        "name": "Keyword test",
        "cost": 0,
        "type": "skill",
        "rules": rules,
        "tags": tags,
        "main": {"target": "self", "do": []},
    }
    return card(battle, cid)


def test_initiation_puts_card_in_opening_hand():
    battle, _ = arena()
    opening = tagged(battle, "initiation")
    battle.run.deck.append(opening)

    restarted = Battle(battle.gd, battle.run, battle.fight, seed=5)

    assert restarted.hand[0] is opening


def test_exhaust_two_counts_plays_not_draws():
    battle, _ = arena()
    twice = tagged(battle, "exhaust_2")

    finish(battle.play(twice, "main", battle.hero))
    assert twice in battle.used and twice not in battle.exhaust
    battle.used.remove(twice)
    battle.draw_pile.append(twice)
    battle.draw(1)
    finish(battle.play(twice, "main", battle.hero))

    assert twice in battle.exhaust and twice not in battle.used


def test_ephemeral_overrides_retain_at_the_end_of_the_turn():
    battle, foe = arena()
    fading = tagged(battle, "ephemeral", "retain")
    foe.ds["stun"] = True

    finish(battle.end_turn())

    assert fading in battle.exhaust
    assert fading not in battle.hand and fading not in battle.discard


def test_pulverize_uses_current_target_shield_and_bullet_is_a_family_tag():
    battle, foe = arena()
    shell = tagged(battle, "pulverize", tags=("bullet",))
    shell.base["main"] = {"target": "enemy", "range": 4, "do": [{"op": "damage", "n": 10}]}
    foe.shield = 5

    finish(battle.play(shell, "main", foe))
    assert foe.hp == 93 and foe.shield == 0
    assert shell.tag_ids.count("bullet") == 1
    battle.used.remove(shell)
    battle.receive_card(shell)
    finish(battle.play(shell, "main", foe))
    assert foe.hp == 83


def test_unactivatable_blocks_both_target_selection_and_direct_play():
    battle, _ = arena()
    inert = tagged(battle, "unactivatable")
    for auto in (False, True):
        assert not battle.targets(inert, "main", auto=auto)
        finish(battle.play(inert, "main", battle.hero, free=True, auto=auto))
    assert inert in battle.hand


def test_finale_ends_the_turn_after_play():
    battle, foe = arena()
    final = tagged(battle, "finale")
    foe.ds["stun"] = True
    turn = battle.turn

    finish(battle.play(final, "main", battle.hero))

    assert battle.turn == turn + 1
    assert final in battle.hand or final in battle.discard
