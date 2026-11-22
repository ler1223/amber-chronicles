"""Замер главы 1 «Спуска» ботом: каждый бой каждого этажа (обычные, элиты, страж) за каждого героя, несколько
сидов. Колода — стартовая + несколько наград (чем глубже, тем больше), HP — полное. Печатает победы, средний
урон герою и ошибки.

Запуск: python tools/descent_bench.py [сидов=4]
"""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def main(seeds=4):
    from deck import bot
    from deck import model as M
    from deck.battle import Battle
    from deck.floor import make_fight
    from test_expedition import ED
    import random
    data = M.load()
    errors = []
    for depth, fl in enumerate(data["enemies"]["chapter"]["floors"], 1):
        print(f"=== этаж {depth}: {fl['name']}")
        for kind in ("battle", "elite", "boss"):
            for pool in fl["pools"][kind]:
                row = []
                for hero, var in (("merc", None), ("hunter", "mark"), ("pyro", None)):
                    wins, dmg = 0, 0
                    for seed in range(seeds):
                        run = M.Run(data=data, seed=seed, hero=hero, variant=var)
                        while run.depth < depth:
                            run.next_floor()
                        rng = random.Random(seed)
                        for cid in rng.sample(run.hero["rewards"], min(len(run.hero["rewards"]), 2 + 2 * depth)):
                            run.take(M.Card(cid, run.defs))
                        fight = make_fight({"pools": {kind: [pool]}}, kind, rng)
                        try:
                            b = Battle(ED, run, fight, seed=seed)
                            bot.play_battle(b, turns=40)
                            wins += b.result == "victory"
                            dmg += run.max_hp - max(0, b.hero.hp)
                        except Exception:
                            errors.append((fl["name"], pool["name"], hero, traceback.format_exc().splitlines()[-1]))
                    row.append(f"{hero} {wins}/{seeds} ({dmg / seeds:.0f})")
                print(f"  {kind:6} {pool['name']:24} " + " · ".join(row))
    print("ошибок:", len(errors))
    for e in errors[:15]:
        print("  ", e)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4)
