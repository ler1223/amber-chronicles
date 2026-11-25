"""Мини-игра «Сплав»: шестиугольные соты 6×6, силы и встречные слияния."""
from merge_duel import BOARD, COLORS, MergeRun


def affinity(v):
    return {tuple(sorted((a, b))): v for i, a in enumerate(COLORS) for b in COLORS[i:]}


def test_place_only_on_empty_board_cell():
    run = MergeRun(seed=1)
    run.affinity = affinity(2)
    run.board = {}
    run.hand = [run.new_card(("red",)), run.new_card(("blue",))]

    assert run.place(0, (2, 2)) == ["Выложена: Алая искра 1"]
    assert (2, 2) in run.board
    assert len(run.hand) == 1

    # уже выложенную карту нельзя переставить: клетка занята
    assert run.place(0, (2, 2)) == ["Клетка занята"]
    assert len(run.hand) == 1


def test_distance_costs_one_unit_of_force():
    run = MergeRun(seed=1)
    run.affinity = affinity(2)
    a = run.new_card(("red",))
    b = run.new_card(("red",))
    run.board = {(0, 0): a, (3, 0): b}

    pair = run.pair_force(a, b)
    assert pair == 4.0
    assert run.force_at((0, 0), (3, 0)) == 1.0


def test_negative_force_also_fades_with_distance():
    run = MergeRun(seed=1)
    run.affinity = affinity(-4)
    a = run.new_card(("red",))
    b = run.new_card(("blue",))
    run.board = {(0, 0): a, (1, 0): b}

    assert run.pair_force(a, b) == -2.0
    assert run.force_at((0, 0), (1, 0)) == -1.0
    run.board = {(0, 0): a, (3, 0): b}
    assert run.force_at((0, 0), (3, 0)) == 0.0


def test_one_iteration_moves_each_card_at_most_one_cell():
    run = MergeRun(seed=1)
    run.affinity = affinity(2)
    run.board = {(0, 0): run.new_card(("red",)), (3, 0): run.new_card(("red",))}

    targets = run.movement_targets()
    assert targets == {(0, 0): (1, 0), (3, 0): (2, 0)}
    assert set(run.board) == {(0, 0), (3, 0)}       # предпросмотр не двигает карты

    assert run.move_iteration() is True
    assert (0, 0) not in run.board
    assert (3, 0) not in run.board
    assert sorted(run.board) == [(1, 0), (2, 0)]


def test_cards_moving_toward_each_other_merge_after_shift():
    run = MergeRun(seed=1)
    run.affinity = affinity(2)
    run.board = {(0, 0): run.new_card(("red",)), (3, 0): run.new_card(("red",))}

    events = run.move_and_merge()
    assert events
    assert len(run.board) == 1
    merged = next(iter(run.board.values()))
    assert merged.level == 2


def test_adjacent_cards_with_mutual_intentions_merge():
    run = MergeRun(seed=1)
    run.affinity = affinity(2)
    a = run.new_card(("red",))
    b = run.new_card(("yellow",))
    run.board = {(2, 2): a, (3, 2): b}

    assert run.adjacent_merge_preview() == [((2, 2), (3, 2))]
    assert run.force_at((2, 2), (3, 2)) > 1
    assert run.merge_moving()
    assert len(run.board) == 1
    merged = next(iter(run.board.values()))
    assert merged.colors == ("red", "yellow")
    assert merged.level == 2
    assert a.name in merged.parts and b.name in merged.parts


def test_adjacent_cards_without_mutual_intentions_do_not_merge():
    run = MergeRun(seed=1)
    run.affinity = affinity(2)
    a = run.new_card(("red",))
    b = run.new_card(("yellow",))
    old = {(2, 2): a, (3, 2): b}
    run.board = dict(old)
    intents = {(2, 2): (2, 1), (3, 2): (3, 3)}  # обе уходят в стороны

    assert run.merge_moving(intents, {id(c): p for p, c in old.items()}) == []
    assert set(run.board) == {(2, 2), (3, 2)}


def test_approaching_cards_merge_and_keep_both_parts():
    run = MergeRun(seed=1)
    run.affinity = affinity(2)
    a = run.new_card(("red",))
    b = run.new_card(("yellow",))
    run.board = {(2, 2): a, (4, 2): b}

    events = run.move_and_merge()
    assert events
    assert len(run.board) == 1
    merged = next(iter(run.board.values()))
    assert merged.colors == ("red", "yellow")
    assert merged.level == 2
    assert a.name in merged.parts and b.name in merged.parts


def test_adjacent_cards_that_move_apart_do_not_merge():
    run = MergeRun(seed=1)
    run.affinity = affinity(2)
    a = run.new_card(("red",))
    b = run.new_card(("yellow",))
    old = {(2, 2): a, (3, 2): b}
    run.board = dict(old)
    intents = {(2, 2): (2, 1), (3, 2): (3, 3)}

    assert run.merge_moving(intents, {id(c): p for p, c in old.items()}) == []
    assert set(run.board) == {(2, 2), (3, 2)}


def test_one_card_moving_toward_another_is_not_enough():
    run = MergeRun(seed=1)
    run.affinity = affinity(2)
    a = run.new_card(("red",))
    b = run.new_card(("yellow",))
    old = {(2, 2): a, (3, 2): b}
    run.board = dict(old)
    intents = {(2, 2): (3, 2), (3, 2): (3, 3)}  # первая тянется, вторая уходит

    assert run.merge_moving(intents, {id(c): p for p, c in old.items()}) == []
    assert set(run.board) == {(2, 2), (3, 2)}


def test_two_color_card_needs_force_above_two():
    run = MergeRun(seed=1)
    run.affinity = affinity(1)
    a = run.new_card(("red", "blue"))
    b = run.new_card(("red", "blue"))
    run.board = {(0, 0): a, (2, 0): b}

    # после сближения сила ровно 2 — порог не пройден
    assert run.move_and_merge() == ["Одна итерация движения"]
    assert len(run.board) == 2

    run.board = {(0, 0): a, (2, 0): b}
    run.affinity[("blue", "red")] = 2
    run.affinity[("red", "red")] = 2
    run.affinity[("blue", "blue")] = 2
    assert run.move_and_merge()
    assert len(run.board) == 1


def test_board_cards_pulse_and_endless_wave_starts():
    run = MergeRun(seed=2)
    run.affinity = affinity(2)
    run.board = {(3, 3): run.new_card(("red",), level=1)}
    run.enemy.hp = 100

    run.end_turn()
    assert run.enemy.hp < 100

    run.enemy.hp = 0
    run.end_turn()
    assert run.wave == 2
    assert run.enemy.hp > 0


def test_hex_board_distance_and_six_neighbors():
    run = MergeRun(seed=1)
    assert run.distance((1, 1), (1, 1)) == 0
    assert run.distance((1, 1), (1, 0)) == 1
    assert run.distance((1, 1), (0, 1)) == 1
    assert run.distance((1, 1), (2, 2)) == 1
    assert run.distance((0, 0), (1, 1)) == 2
    assert len(run.neighbor_cells((1, 1))) == 6
    assert len(run.neighbor_cells((0, 0))) == 2


def test_play_order_is_top_to_bottom_then_left_to_right():
    run = MergeRun(seed=1)
    run.board = {
        (3, 2): run.new_card(("red",)),
        (0, 0): run.new_card(("blue",)),
        (1, 1): run.new_card(("yellow",)),
    }
    assert run.play_order() == [(0, 0), (1, 1), (3, 2)]


def test_play_card_at_applies_only_one_card_effect():
    run = MergeRun(seed=1)
    run.affinity = affinity(2)
    run.board = {
        (0, 0): run.new_card(("red",)),
        (2, 0): run.new_card(("red",)),
    }
    run.enemy.hp = 50
    events = run.play_card_at((0, 0))
    assert events == ["Разыграна: Алая искра 1", "Урон 5"]
    assert run.enemy.hp == 45


def test_board_size_is_six_by_six():
    assert BOARD == 6
