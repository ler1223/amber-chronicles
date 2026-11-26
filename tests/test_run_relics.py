from deck import model as M
from deck.battle import Battle, finish
from deck.game import DescentGame
from deck.relic_run import CREST, DEBT, LABEL, MIRROR, OATH, PACT, RELICS, TROPHIES, tagged_card
from deck.save import run_from, run_to
from sim.grid import Grid
from test_deck import ED, put


def setup(*items, hero="merc"):
    run = M.Run(seed=3, hero=hero)
    run.relics = [dict(RELICS[item], id=item) for item in items]
    battle = Battle(ED, run, run.fights[0], seed=3)
    battle.c.grid = Grid(["." * 9] * 7, {".": {}})
    put(battle, battle.hero, (4, 3))
    return battle, run


def test_crest_hides_one_of_three_actual_exiles_and_releases_after_shuffle():
    battle, run = setup(CREST)
    exiles = [M.Card("strike", run.defs) for _ in range(3)]
    run.deck.extend(exiles)
    for card in exiles:
        finish(battle.exhaust_card(card))
    [(relic, choices)] = battle.run_relics.victory_choices()
    assert relic == CREST and choices == exiles
    battle.run_relics.record_choice(relic, exiles[0])
    next_battle = Battle(ED, run, run.fights[0], seed=4)
    assert next_battle.run_relics.hidden is exiles[0]
    assert exiles[0] not in next_battle.hand + next_battle.draw_pile
    next_battle.hand.clear()
    next_battle.draw_pile.clear()
    next_battle.draw(1)
    assert exiles[0] in next_battle.hand


def test_label_survives_save_and_marks_exact_deck_card():
    battle, run = setup(LABEL)
    card = run.deck[0]
    battle.run_relics.record_choice(LABEL, card)
    data = run_to(run)
    # Production reload resolves the item by ID through the catalogue.
    run.data["relics"]["relics"][LABEL] = RELICS[LABEL]
    loaded = run_from(run.data, data)
    original = [c for c in loaded.deck if getattr(c, "relic_key", None) == card.relic_key]
    assert len(original) == 1
    same_floor = Battle(ED, loaded, loaded.fights[0], seed=4)
    assert same_floor.run_relics.state[LABEL]["floor"] == loaded.depth + 1
    loaded.depth += 1
    next_floor = Battle(ED, loaded, loaded.fights[0], seed=4)
    assert next_floor.hand[0] is original[0]
    assert LABEL not in loaded.relic_state


def test_trophy_reads_the_killing_card_and_oath_breaks_on_main_play():
    battle, run = setup(TROPHIES, OATH)
    existing = battle.foes()
    for enemy in existing[1:]:
        enemy.alive = False
    target = existing[0]
    put(battle, target, (5, 3))
    target.edef = {}
    target.hp = 1
    strike = M.Card("strike", run.defs)
    battle.hand[:] = [strike]
    battle.run_relics.oath_tag = "strike"
    run.relic_state[TROPHIES] = "block"
    finish(battle.play(strike, "main", target))
    assert battle.result == "victory"
    assert battle.run_relics.reward_tags() == (("block", "strike"), None)


def test_oath_reward_added_with_real_insight():
    battle, run = setup(OATH)
    extra = tagged_card(run, "strike", [], insight=True)
    assert extra.tier == 1
    game = DescentGame(seed=3, gd=ED)
    game.run, game._gold = run, 10
    game._battle_run_relics = battle.run_relics
    battle.run_relics.oath_tag = "strike"
    game._card_reward()
    assert len(game.scene.options) == 4
    assert game.scene.options[-1][1].tier == 1


def test_oath_upgrades_a_priest_scroll_without_changing_catalogue():
    from deck.idols import Idols

    run = M.Run(seed=3, hero="priest")
    sample = tagged_card(run, "scroll", [], insight=True)
    assert sample.cid.startswith("sc_g")
    assert max(act.get("q", 1) for act in Idols.acts(sample)) >= 2
    assert sample.cid not in run.data["cards"]["cards"]


def test_debt_can_be_paid_on_first_positive_cost_strike_only():
    _, run = setup(DEBT)
    run.relic_state[DEBT] = True
    next_battle = Battle(ED, run, run.fights[0], seed=4)
    strike = M.Card("strike", run.defs)
    defend = M.Card("defend", run.defs)
    assert next_battle.effective_cost(defend, consume=True) == defend.cost
    assert next_battle.effective_cost(strike) == strike.cost + 1
    assert next_battle.effective_cost(strike, consume=True) == strike.cost + 1
    assert next_battle.effective_cost(strike) == strike.cost


def test_mirror_records_preceding_card_on_shared_primary_tag():
    battle, run = setup(MIRROR)
    prior = M.Card("strike", run.defs)
    unique = dict(prior.base, unique=True)
    qualifier = M.Card("trigger", {"trigger": unique})
    rules = battle.run_relics
    rules.observe_play(prior)
    rules.observe_play(qualifier)
    assert run.relic_state[MIRROR]["cid"] == prior.cid
    next_battle = Battle(ED, run, run.fights[0], seed=4)
    opening = next_battle.run_relics.opening()
    request = next(opening)
    clone = request.options[0][1]
    assert clone is not prior and clone.cid == prior.cid
    assert MIRROR not in run.relic_state
    try:
        opening.send(clone)
    except StopIteration:
        pass
    finish(opening)
    assert clone in next_battle.hand and clone not in run.deck


def test_debt_transfers_blessing_shield_and_books_next_battle_debt():
    battle, run = setup(DEBT)
    hero = battle.hero
    dummy = type("Installation", (), {"team": hero.team, "alive": True, "obj": True,
                                      "name": "Мишень", "shield": 0})()
    battle.c.units.append(dummy)
    proc = battle.apply(hero, [{"op": "discard_blessing"}], None, {})
    request = next(proc)
    assert request.options == [(dummy.name, dummy)]
    try:
        proc.send(dummy)
    except StopIteration:
        pass
    finish(proc)
    assert dummy.shield == hero.max_hp * 3 // 5
    assert hero.shield == 0 and run.relic_state[DEBT] is True


def test_pact_carries_energy_and_increases_finale_price_for_only_one_turn():
    battle, run = setup(PACT)
    finale_def = dict(run.defs["strike"], rules=["finale"])
    finale = M.Card("finale", {"finale": finale_def})
    battle.energy = 2
    battle.hand.clear()
    finish(battle.run_relics.finale())
    assert battle.next_energy == 2
    finish(battle.start_player_turn())
    assert battle.energy == battle.max_energy + 2
    assert battle.effective_cost(finale) == finale.cost + 1
    finish(battle.start_player_turn())
    assert battle.effective_cost(finale) == finale.cost


def test_pact_preserves_selected_ephemeral_card_and_overheat_once():
    battle, run = setup(PACT, hero="pyro")
    fleeting = M.Card("fleeting", {"fleeting": dict(run.defs["p_bolt"], rules=["ephemeral"])})
    battle.hand[:] = [fleeting]
    battle.hero.ds["heat"] = 10
    for foe in battle.foes():
        foe.ds["stun"] = True
    pact = battle.run_relics.finale()
    assert next(pact).options[0][1] is fleeting
    try:
        pact.send(fleeting)
    except StopIteration:
        pass
    hp = battle.hero.hp
    finish(battle.end_turn())
    assert fleeting in battle.hand
    assert battle.hero.hp == hp and battle.hero.ds["heat"] > 10
