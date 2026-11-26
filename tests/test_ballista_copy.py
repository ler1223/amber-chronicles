from deck import model as M
from deck.battle import BallistaShot
from test_deck import _foe, card, finish
from test_field_ballista import arena, command


def test_unique_ballista_can_only_be_duplicated_in_battle_with_slip():
    battle, run = arena()
    original = M.Card(M.BALLISTA_CARD, run.defs, picks=[2])
    slip = M.Card(M.HAND_COPY_CARD, run.defs)
    assert run.take(original)
    assert run.take(slip)
    assert not run.rewardable(M.BALLISTA_CARD)
    assert not run.take(M.Card(M.BALLISTA_CARD, run.defs))
    assert original.d["unique"] and original.d["deck_unique"]
    assert "Уникальная" in original.tags
    run_deck = list(run.deck)

    battle.hand.extend((original, slip))
    battle.energy = 0
    assert battle.targets(slip, "main") == [original]
    finish(battle.play(slip, "main", original))
    clone = next(c for c in battle.hand if c is not original)
    assert clone.cid == original.cid and clone.uid != original.uid
    assert clone.copied and clone.picks == original.picks
    assert battle.energy == 0 and slip not in battle.used and run.deck == run_deck

    battle.energy = 4
    finish(battle.play(original, "main", (2, 2)))
    assert clone in battle.hand
    finish(battle.play(clone, "main", (1, 3)))
    first, second = battle.ballistas
    assert first.hp == second.hp == 17
    battle.draw(4)
    load = next(c for c in battle.hand if c.cid == M.BALLISTA_COMMANDS[0] and c.ballista_owner is first)
    finish(battle.play(load, "main", second))
    assert first.charge == 0 and second.charge == 2
    foe = _foe(battle, "slime", (2, 3))
    battle.hurt(first, 17, foe, "zone")
    assert battle.ballistas == [second]
    assert all(c.ballista_owner is second for c in battle.hand if c.cid in M.BALLISTA_COMMANDS)
    assert [c.cid for c in battle.hand if c.cid in M.BALLISTA_COMMANDS] == list(M.BALLISTA_COMMANDS)


def test_slip_copies_ordinary_card_effect_and_preserves_original():
    battle, run = arena()
    slip = card(battle, M.HAND_COPY_CARD)
    second_slip = card(battle, M.HAND_COPY_CARD)
    assert "Уникальная" in slip.tags
    assert run.take(slip) and not run.take(second_slip)
    assert not run.rewardable(M.HAND_COPY_CARD)
    original = card(battle, "h_scope")
    original.alt_up = {"target": "self", "do": [{"op": "block", "n": 2}]}
    battle.temper[original.uid] = 4

    assert battle.targets(slip, "main") == [original]
    finish(battle.play(slip, "main", original))
    assert original in battle.hand and second_slip in battle.hand
    clone = next(c for c in battle.hand if getattr(c, "copied", False))
    assert clone.cid == original.cid and clone.alt_up == original.alt_up
    assert clone.alt_up is not original.alt_up and battle.temper[clone.uid] == 4
    finish(battle.play(clone, "main", battle.hero))
    assert original in battle.hand and battle.hero.ds["ranged_bonus"] == 2


def test_ballista_buff_forecast_and_shot_use_selected_installation():
    battle, _ = arena()
    placement = card(battle, M.BALLISTA_CARD)
    finish(battle.play(placement, "main", (2, 2)))
    ballista = battle.ballista
    foe = _foe(battle, "slime", (5, 2))
    foe.hp = foe.max_hp = 60
    battle.draw(2)
    finish(battle.play(command(battle, "h_ballista_load"), "main", ballista))

    scope = card(battle, "h_scope")
    focus = card(battle, "h_focus")
    ritual = card(battle, "h_dmg_ritual")
    assert battle.targets(scope, "main") == [battle.hero, ballista]
    finish(battle.play(scope, "main", ballista))
    finish(battle.play(focus, "main", ballista))
    finish(battle.play(ritual, "main", ballista))
    finish(battle.power_fire("turn"))
    assert ballista.ds["ranged_bonus"] == 2 and ballista.ds["strength"] == 1
    assert battle.hero.ds["ranged_bonus"] == battle.hero.ds["strength"] == 0
    assert not battle.hero.ds["focus"] and ballista.ds["focus"]

    shot = command(battle, "h_ballista_fire")
    expected = battle.ballista_damage(shot.d["main"]["do"][0], foe, ballista)
    finish(battle.play(shot, "main", BallistaShot(ballista, foe)))
    assert expected == 21 and foe.hp == 60 - expected
    assert not ballista.charge and not ballista.ds["focus"]
