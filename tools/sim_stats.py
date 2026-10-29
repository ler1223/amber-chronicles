"""Прогон всех боёв без окна: длительность, исход, число реакций. python tools/sim_stats.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.combat import ENEMY, PLAYER, Combat  # noqa: E402
from sim.data import GameData  # noqa: E402

d = GameData()
for teams, label in (((PLAYER, ENEMY), "ИИ против ИИ"), ((ENEMY,), "игрок бездействует")):
    print("==", label)
    for i, e in enumerate(d.encounters):
        c = Combat(d, i, ai_teams=teams)
        while not c.result and c.time < 240:
            c.step()
        reactions = sum(1 for x in c.events if x["t"] == "reaction")
        print(f"  {e['id']:6} {c.result} {c.time:5.1f}s  "
              f"P:{[u.hp for u in c.alive(PLAYER)]} E:{[u.hp for u in c.alive(ENEMY)]}  реакций:{reactions}")
