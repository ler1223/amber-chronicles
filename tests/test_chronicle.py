"""Летопись и смерть героя (квиз 2026-11-11): третье падение за поход — гибель насовсем, вещи павшего — в сумку,
дары — наследием; летопись, подвиги и прозвища остаются с героем навсегда (и у ветерана), павшие — в зал славы."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.data import GameData  # noqa: E402
from sim import expedition as X  # noqa: E402
from sim.teams import PLAYER  # noqa: E402

DATA = GameData()
ED = X.expedition_data(DATA)


def make_run(n=3):
    prof = X.ExpeditionProfile(ED)
    run = prof.start([h.uid for h in prof.hall()[:n]], seed=5)
    return prof, run


def fight(run, kill=(), win=True):
    """Бой текущего узла: kill — индексы героев, павших в бою; остальное — победа."""
    run.node = next(nid for nid, x in run.nodes.items() if x["type"] == "battle")
    from sim.combat import Combat
    c = Combat(run.data, run.nodes[run.node]["encounter"], seed=1, squad=run.combat_squad(),
               enemy_scale=run.enemy_scale())
    us = run.player_units(c)
    for i in kill:
        us[i].alive, us[i].hp = False, 0
    if win:
        c.win_now()
    else:
        for u in us:
            u.alive = False
        c._check_end()
    return run.finish_battle(c)


def test_third_fall_kills_hero_and_leaves_legacy():
    prof, run = make_run()
    h = run.heroes[0]
    h.gifts = [next(iter(run.xd["gifts"]))]
    item_n = len(h.gear)
    bag0 = len(run.bag)
    for i in range(2):
        s = fight(run, kill=[0])
        assert h in run.heroes and h.falls == i + 1 and h.wounded
    s = fight(run, kill=[0])
    assert h not in run.heroes and len(run.heroes) == 2
    assert s["dead"] == [h.name] and s["legacy_gifts"] == h.gifts
    assert len(run.bag) == bag0 + item_n                      # вещи павшего — в сумке отряда
    assert h.chronicle[-1]["kind"] == "death"
    run.result = "victory"
    prof.finish(run)
    rec = next(f for f in prof.fallen if f["name"] == h.name)
    assert rec["name"] == h.name and rec["chronicle"] and rec["reason"].startswith("погиб")


def test_chronicle_and_titles_survive_veteran_return():
    prof, run = make_run(2)
    h = run.heroes[0]
    h.feats["kills"] = 99
    fight(run)
    assert any(r["kind"] == "start" for r in h.chronicle)
    h.feats["kills"] = 150
    out = run.award_titles()
    assert "slayer" in h.titles and any(t == "Истребитель" for _, t in out)
    p0 = run.proto(h)["attack"]["damage"]
    run.result = "victory"
    prof.finish(run)
    vet = next(v for v in prof.roster if v.uid == h.uid)
    assert "slayer" in vet.titles and vet.chronicle and vet.feats.get("runs_won") == 1 and vet.falls == 0
    assert any(r["kind"] == "win" for r in vet.chronicle)
    assert p0 > 0


def test_title_bonus_is_in_prototype():
    prof, run = make_run(2)
    h = run.heroes[0]
    base = run.proto(h)["hp"]
    h.titles = ["unbroken"]
    assert run.proto(h)["hp"] > base
