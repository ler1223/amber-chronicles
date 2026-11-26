from test_deck import card, finish, hero_battle


def test_lead_discounts_until_the_next_successful_play(monkeypatch):
    battle, _ = hero_battle("merc")
    battle.hand.clear()
    battle.draw_pile.clear()
    base = battle.run.defs["defend"]
    for cid in ("lead_low", "lead_high"):
        battle.run.defs[cid] = dict(base, rules=["lead"])
    low, high = (card(battle, cid) for cid in ("lead_low", "lead_high"))
    values = iter((0.1, 0.9))
    monkeypatch.setattr(battle.rng, "random", lambda: next(values, 0.9))
    finish(battle.start_player_turn())
    assert battle.effective_cost(low) == low.cost - 1
    assert battle.effective_cost(high) == high.cost
    assert "lead" in low.tag_ids

    finish(battle.play(high, "main", None))
    assert battle.effective_cost(low) == low.cost - 1
    finish(battle.play(high, "main", battle.hero))
    assert battle.effective_cost(low) == low.cost
