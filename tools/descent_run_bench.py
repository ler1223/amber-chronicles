"""Стенд баланса «Спуска»: каждый герой проходит спуск целиком ботом (deck/bot.py) — с наградами, прозрениями,
реликвиями, ветками богов, отдыхом. На этаже: 3 боя, элита, костёр, страж. Печатает по героям: сколько этажей
пройдено в среднем, доля дошедших до конца главы 1 и всего спуска, HP после каждого этажа, где чаще гибнут.

Запуск: python tools/descent_run_bench.py [забегов на героя=6] [герои через запятую]
"""
import collections
import os
import random
import statistics
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from deck import model as M  # noqa: E402
from deck.battle import Battle  # noqa: E402
from deck.bot import play_battle  # noqa: E402
from deck.floor import make_fight  # noqa: E402
from deck.game import DescentGame  # noqa: E402

VARIANT = {"hunter": "mark", "priest": "storm"}
PLAN = ["battle", "battle", "elite", "battle", "camp", "boss"]


def card_value(c):
    d = c.d
    if d.get("acts"):
        return sum(a.get("q", 1) + 0.6 * (a.get("n", 1) - 1) for a in d["acts"]) + (1.2 if d.get("chorus") or d.get("then") else 0)
    if d["main"].get("power"):                                   # Сила до конца боя — ценна в долгих боях
        return 3.0
    W = {"damage": 1, "block": 1, "heal": 1, "bleed": 1.2, "burn": 1.2, "poison": 1.1, "counter": 2.5,
         "strength": 3, "add_card": 3, "vulnerable": 2, "weak": 2, "trap": 0.7, "draw": 2}
    v = 0.0
    for o in d["main"].get("do", []):
        v += W.get(o["op"], 0) * o.get("n", 1) + (3 * o["per"]["k"] if o.get("per") else 0)
    return v / max(1, c.cost + 1)


def fight(gd, run, kind, rng):
    pools = run.floor_cfg["pools"]
    fight = make_fight({"pools": {kind: pools[kind]}}, kind, rng)
    b = Battle(gd, run, fight, seed=rng.randrange(1 << 30))
    play_battle(b, turns=30)
    if b.result != "victory":
        b.result = b.result or "timeout"
    b.finish_into_run()
    return b.result


def after_win(run, kind, rng):
    run.fight += 1
    if run.hero.get("mechanic") != "idols":
        run.hp = min(run.max_hp, run.hp + max(1, round(run.max_hp * 0.1)))
    offer = run.reward_offer()
    if offer:
        run.take(max(offer, key=card_value))
    for c in run.insights():
        c.choose(0)
    while getattr(run, "god_pending", None):
        god, level = run.god_pending.pop(0)
        from deck.idols import Idols
        opts = Idols.branch_offer(run, god, level)
        if opts:
            run.god_picks.setdefault(god, []).append(opts[0][0])
    if kind in ("elite", "boss"):
        rel = run.relic_offer(1)
        if rel:
            run.relics.append(rel[0])


def one_run(hero, seed):
    g = DescentGame(seed=seed)
    g.start_run(hero, VARIANT.get(hero))
    run = g.run
    rng = random.Random(seed)
    total = sum(len(c["floors"]) for c in run.chapters)
    hp_by_floor = []
    while True:
        for kind in PLAN:
            if kind == "camp":
                run.hp = min(run.max_hp, run.hp + int(run.max_hp * 0.3))
                continue
            res = fight(g.gd, run, kind, rng)
            if res != "victory" or run.hp <= 0:
                return run.depth - 1, hp_by_floor, (run.depth, kind)
            after_win(run, kind, rng)
        hp_by_floor.append(run.hp / run.max_hp)
        if run.depth >= total:
            return run.depth, hp_by_floor, None
        k = 1.0 if run.chapter_end else run.floor_cfg["boss_heal"]
        run.hp += int((run.max_hp - run.hp) * k)
        run.next_floor()


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    heroes = sys.argv[2].split(",") if len(sys.argv) > 2 else ["merc", "hunter", "pyro", "priest"]
    print(f"{'герой':8} {'этажей':>7} {'гл.1':>5} {'всё':>5}   HP после этажей            гибель (этаж, бой)")
    for hero in heroes:
        t0 = time.time()
        floors, deaths = [], collections.Counter()
        hps = collections.defaultdict(list)
        for s in range(n):
            f, hp, death = one_run(hero, 1000 + s)
            floors.append(f)
            for i, v in enumerate(hp):
                hps[i + 1].append(v)
            if death:
                deaths[death] += 1
        hp_txt = " ".join(f"{d}:{statistics.mean(v):.0%}" for d, v in sorted(hps.items()))
        print(f"{hero:8} {statistics.mean(floors):7.1f} {sum(f >= 3 for f in floors) / n:5.0%} "
              f"{sum(f >= 6 for f in floors) / n:5.0%}   {hp_txt:28} {dict(deaths.most_common(4))}  [{time.time() - t0:.0f} с]")


if __name__ == "__main__":
    main()
