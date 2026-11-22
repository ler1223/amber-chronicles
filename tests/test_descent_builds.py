"""Новые колоды Охотницы: три школы, метки и первые пейоффы."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deck import model as M  # noqa: E402
from deck.battle import Battle, finish  # noqa: E402
from sim.grid import cheb  # noqa: E402
from test_expedition import ED  # noqa: E402


def put(u, cell):
    u.cell = u.prev_cell = tuple(cell)


def test_hunter_variants_have_distinct_decks_and_core_rewards():
    data = M.load()
    decks = {}
    for variant in ("range", "mark", "quiver"):
        run = M.Run(data=data, seed=1, hero="hunter", variant=variant)
        decks[variant] = [c.cid for c in run.deck]
        assert len(run.deck) == 11
        core = set(run.hero["rewards_by_variant"][variant])
        offers = [c.cid for c in run.reward_offer()]
        assert len(offers) == 3
        assert all(cid in run.hero["rewards"] for cid in offers)
        assert sum(cid in core for cid in offers) == 2          # 2 карты школы + 1 свободная
    assert decks["range"] != decks["mark"] != decks["quiver"]
    assert "h_mark_burst" in decks["mark"] and "h_rapid" in decks["quiver"]


def test_mark_burst_scales_with_marks_and_has_tags():
    data = M.load()
    run = M.Run(data=data, seed=2, hero="hunter", variant="mark")
    b = Battle(ED, run, run.fights[0], seed=2)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (4, 2))
    foe.hp = foe.max_hp = 99
    foe.ds["mark"] = 4
    card = M.Card("h_mark_burst", run.defs)
    b.hand.append(card)
    b.energy = 9
    hp = foe.hp
    finish(b.play(card, "main", foe))
    assert hp - foe.hp == 4 + 3 * 4 + 4                     # 4 базовых + 3 за каждую метку + обычный бонус метки
    assert foe.ds["mark"] == 0                              # удар снял метку
    assert "Метка" in M.Card("h_mark_burst", run.defs).tags


def test_new_school_tags_are_derived():
    data = M.load()
    assert "Повтор" in M.Card("h_echo_shot", data["cards"]["cards"]).tags
    assert "Комбо" in M.Card("h_rapid", data["cards"]["cards"]).tags


def test_all_new_hunter_cards_can_be_played():
    data = M.load()
    new = ("h_scope", "h_snipe", "h_steady", "h_mark_burst", "h_mark_web", "h_hunt",
           "h_echo_shot", "h_rapid", "h_arrow_well", "h_quiver_echo")
    for cid in new:
        run = M.Run(data=data, seed=4, hero="hunter", variant="mark")
        b = Battle(ED, run, run.fights[0], seed=4)
        h, foe = b.hero, b.foes()[0]
        put(h, (2, 2))
        put(foe, (4, 2))
        foe.hp = foe.max_hp = 99
        card = M.Card(cid, run.defs)
        b.hand.append(card)
        b.energy = 9
        targets = b.targets(card, "main")
        assert targets, cid
        target = targets[0]
        finish(b.play(card, "main", target))
        assert card not in b.hand or card in b.powers, cid


def test_resonance_replays_card_instead_of_own_effect():
    data = M.load()
    run = M.Run(data=data, seed=6, hero="hunter", variant="quiver")
    b = Battle(ED, run, run.fights[0], seed=6)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (4, 2))
    foe.hp = foe.max_hp = 99
    # два выстрела уже сыграны — резонанс [Выстрел] 2 выполнен
    b.turn_tags = [{"Выстрел"}, {"Выстрел"}]
    b.played = 2
    card = M.Card("h_echo_shot", run.defs)
    b.hand.append(card)
    b.energy = 9
    hp = foe.hp
    finish(b.play(card, "main", foe))
    assert hp - foe.hp == 10                              # 5 урона, карта разыграна ещё раз


def test_quiver_rewards_guarantee_arrow_cards():
    data = M.load()
    run = M.Run(data=data, seed=7, hero="hunter", variant="quiver")
    creators = {"h_fill", "h_full_quiver", "h_master_quiver", "h_arrow_well"}
    for _ in range(12):
        offers = {c.cid for c in run.reward_offer()}
        assert offers & creators, offers


def test_arrow_well_creates_free_shots():
    data = M.load()
    run = M.Run(data=data, seed=8, hero="hunter", variant="quiver")
    b = Battle(ED, run, run.fights[0], seed=8)
    card = M.Card("h_arrow_well", run.defs)
    b.hand.append(card)
    b.energy = 9
    finish(b.play(card, "main", b.hero))
    assert sum(1 for c in b.hand if c.cid == "arrow") >= 2
