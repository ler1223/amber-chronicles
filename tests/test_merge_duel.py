"""Мини-игра «Сплав»: силы, автослияния и бой без поля."""
from merge_duel import COLORS, MergeRun


def affinity(v):
    return {tuple(sorted((a, b))): v for i, a in enumerate(COLORS) for b in COLORS[i:]}


def test_one_color_merges_when_force_above_one():
    run = MergeRun(seed=1)
    run.affinity = affinity(2)
    a = run.new_card(("red",))
    b = run.new_card(("red",))
    run.hand = [a, b]
    events = run.auto_merge()
    assert events and len(run.hand) == 1
    assert run.hand[0].colors == ("red",) and run.hand[0].level == 2


def test_two_color_needs_force_above_two():
    run = MergeRun(seed=1)
    run.affinity = affinity(2)
    a = run.new_card(("red", "blue"))
    b = run.new_card(("red", "blue"))
    run.hand = [a, b]
    assert run.auto_merge() == []
    run.affinity[("blue", "red")] = 3
    assert run.auto_merge()
    assert len(run.hand) == 1 and run.hand[0].level == 2


def test_merge_is_adjacent_and_cards_combine_colors():
    run = MergeRun(seed=1)
    run.affinity = affinity(0)
    run.affinity[("red", "yellow")] = 2
    a = run.new_card(("red",))
    gap = run.new_card(("blue",))
    b = run.new_card(("yellow",))
    run.hand = [a, gap, b]
    assert run.auto_merge() == []           # между red и yellow стоит gap
    run.swap(0, 1)
    assert len(run.hand) == 2
    assert set(run.hand[0].colors) == {"red", "yellow"} or set(run.hand[1].colors) == {"red", "yellow"}


def test_combat_damage_and_endless_wave():
    run = MergeRun(seed=2)
    run.affinity = affinity(1)
    card = run.new_card(("red",), level=1)
    run.hand = [card]
    run.energy = 3
    hp = run.enemy.hp
    run.play(0)
    assert run.enemy.hp < hp
    run.enemy.hp = 0
    run.end_turn()
    assert run.wave == 2 and run.enemy.hp > 0
