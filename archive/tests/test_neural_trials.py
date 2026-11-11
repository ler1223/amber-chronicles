"""Испытания сетей: постоянные сценарии, случайные ходы и таблица результатов (docs/neural_lab.md, 9–10)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_expedition import ED  # noqa: E402

from sim import nn_lab as LAB  # noqa: E402
from sim import trials as T  # noqa: E402
from sim.combat import PLAYER  # noqa: E402


def test_scenarios_are_fixed_and_powered():
    """Все режимы получают одни и те же номера сценариев; сила врагов — общий множитель."""
    scs = T.scenarios(ED, 3, seed=1234, power=0.7)
    assert [s["seed"] for s in scs] == [1234, 1235, 1236]
    assert all(s["power"] == 0.7 for s in scs)
    again = T.scenarios(ED, 3, seed=1234, power=0.7)
    assert [(s["seed"], s["chapter"], s["act"], s["squad"], s["boss"]) for s in scs] == \
           [(s["seed"], s["chapter"], s["act"], s["squad"], s["boss"]) for s in again]


def test_random_controller_makes_valid_orders():
    """Случайные ходы идут через те же маски, что сеть: приказы появляются, правила героев молчат."""
    sc = T.scenarios(ED, 1, seed=7)[0]
    run, c = LAB.build_battle(ED, sc)
    ctl = T.RandomController(c, seed=sc["seed"])
    c.controllers.append(ctl)
    for _ in range(int(4 / c.dt)):
        c.step()
    assert ctl.decisions > 0
    assert not [ai for ai in c.ais if ai.team == PLAYER]


def test_run_trial_modes_and_summary():
    """Один и тот же бой играется бездействием, автопилотом и случайными ходами; итог — победа и HP."""
    sc = T.scenarios(ED, 1, seed=8)[0]
    for mode in ("idle", "autopilot", "random"):
        r = T.run_trial(ED, sc, mode, cfg={"max_time": 1.0})
        assert r["mode"] == mode and r["seed"] == sc["seed"]
        assert isinstance(r["win"], bool) and 0.0 <= r["hp"] <= 1.0
    rows = T.run_trials(ED, ("idle", "random"), 1, [1.0], seed=8, cfg={"max_time": 1.0})
    assert [(p, m) for p, m, _ in rows] == [(1.0, "idle"), (1.0, "random")]
    assert all(len(got) == 1 for _, _, got in rows)


def test_summary_confidence_and_breakdown():
    """Сводка несёт 95 % интервал и разбивку: на 100 боях видно, где именно сеть проседает."""
    got = [{"win": True, "hp": 0.8, "time": 10, "objective": "hold", "act": 0, "boss": False},
           {"win": False, "hp": 0.0, "time": 12, "objective": "hold", "act": 1, "boss": True}]
    s = T.summarize(got)
    assert s["wins"] == 1 and s["ci95"][0] < s["win_rate"] < s["ci95"][1]
    by = T.breakdown(got, "objective")
    assert by["hold"]["battles"] == 2 and by["hold"]["wins"] == 1


def test_format_table():
    """Таблица повторяет вид из docs/neural_lab.md: победы и среднее HP, для нескольких сил врагов — столбцы."""
    one = [(1.0, "autopilot", [{"win": True, "hp": 0.5, "time": 10}]),
           (1.0, "idle", [{"win": False, "hp": 0.0, "time": 10}])]
    text = T.format_table(one)
    assert "автопилот" in text and "1/1" in text and "50%" in text and "ничего не делать" in text
    many = [(0.6, "autopilot", [{"win": True, "hp": 0.6, "time": 10}]),
            (0.6, "planner", [{"win": True, "hp": 0.8, "time": 10}]),
            (0.8, "autopilot", [{"win": False, "hp": 0.0, "time": 10}]),
            (0.8, "planner", [{"win": True, "hp": 0.4, "time": 10}])]
    text = T.format_table(many)
    assert "0.60" in text and "0.80" in text and "планировщик" in text


def test_cli_smoke(capsys):
    """CLI без сети: бездействие на одном коротком бою — печатает таблицу и не падает."""
    assert T.main(["--modes", "idle", "--battles", "1", "--max-time", "1"]) == 0
    out = capsys.readouterr().out
    assert "ничего не делать" in out and "0/1" in out or "1/1" in out
