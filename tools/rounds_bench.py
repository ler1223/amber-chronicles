"""Замер боя раундами: решают ли решения игрока (docs/vision.md §11).

Одни и те же бои экспедиции (первые узлы, разные отряды) в трёх вариантах игры отряда:
  aa     — только автоатаки (приказы атаки, навыков нет);
  auto   — автопилот: навыки по оценке пользы, намерения врагов не читает;
  intent — бот, читающий намерения: уходит из зон ударов, срывает касты, бьёт лекаря и заклинателя первыми.
Плюс старый ритм (без раундов) для сравнения. Печатает победы, остаток HP отряда, время, долю автоатаки в уроне.

    python tools/rounds_bench.py [боёв] [множитель силы врагов]
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sim import expedition as X  # noqa: E402
from sim import rounds as R  # noqa: E402
from sim.combat import ENEMY, PLAYER, Combat  # noqa: E402
from sim.data import GameData  # noqa: E402


def battles(n, k=1.0):
    data = GameData()
    ed = X.expedition_data(data)
    tmp = tempfile.mkdtemp()
    out = []
    for seed in range(1, n + 1):
        prof = X.ExpeditionProfile(ed, os.path.join(tmp, f"b{seed}.json"))
        i = (seed * 2) % max(1, len(prof.roster) - 1)
        run = prof.start([h.uid for h in prof.roster[i:i + 2]], seed=seed)
        run.rounds_mode = True
        nid = run.available()[0]
        run.enter(nid)
        sc = dict(run.enemy_scale())
        sc["hp"] = sc.get("hp", 1.0) * k
        sc["damage"] = sc.get("damage", 1.0) * k
        out.append((run, run.nodes[nid]["encounter"], sc))
    return out


def fight(run, enc, sc, mode, rounds=True, limit=240.0):
    run.rounds_mode = rounds
    squad = run.combat_squad()
    teams = (ENEMY, PLAYER) if mode == "auto" else (ENEMY,)
    c = Combat(run.data, enc, squad=squad, enemy_scale=sc, ai_teams=teams, rounds=rounds)
    if mode != "auto":
        c.assign_initial_targets(PLAYER)
    dealt = {"aa": 0, "other": 0}
    orig = c.damage

    def damage(target, amount, attacker=None, *a, **kw):
        hp0 = target.hp + target.shield
        r = orig(target, amount, attacker, *a, **kw)
        src = c.credit(attacker) if attacker is not None else None
        if src is not None and src.team == PLAYER and target.team != PLAYER:
            dealt["aa" if c._basic and src is attacker else "other"] += max(0, hp0 - (max(0, target.hp) +
                                                                                     target.shield))
        return r
    c.damage = damage
    while not c.result and c.time < limit:
        c.step()
        if rounds and c.rounds.awaiting:
            c.rounds.awaiting = False
            if mode == "intent":
                R.bot_round(c)
        c.events.clear()
    heroes = [u for u in c.units if u.team == PLAYER and not u.obj and not u.summon and u.owner is None]
    hp = sum(max(0, u.hp) / u.max_hp for u in heroes) / max(1, len(heroes))
    tot = dealt["aa"] + dealt["other"]
    return c.result == "victory", hp if c.result == "victory" else 0.0, c.time, dealt["aa"] / max(1, tot)


def main():
    args = [a for a in sys.argv[1:] if "=" not in a]
    n = int(args[0]) if args else 12
    k = float(args[1]) if len(args) > 1 else 1.0
    bs = battles(n, k)
    for a in sys.argv[1:]:                       # подбор чисел: aa_mult=0.6 skill_mult=2.5 …
        if "=" in a:
            key, v = a.split("=", 1)
            for run, _, _ in bs:
                run.data.rounds[key] = float(v)
    only = os.environ.get("ROWS")
    rows = [("старый ритм, автопилот", "auto", False), ("старый ритм, только автоатаки", "aa", False),
            ("раунды: только автоатаки", "aa", True), ("раунды: автопилот", "auto", True),
            ("раунды: бот по намерениям", "intent", True)]
    if only:
        rows = [r for r in rows if r[2]]
    for name, mode, rounds in rows:
        res = [fight(run, enc, sc, mode, rounds) for run, enc, sc in bs]
        w = sum(r[0] for r in res)
        print(f"{name:32s} побед {w:2d}/{n}  HP отряда {sum(r[1] for r in res) / n:.2f}  "
              f"время {sum(r[2] for r in res) / n:5.1f}с  доля автоатаки {sum(r[3] for r in res) / n:.0%}")


if __name__ == "__main__":
    main()
