"""Демонстрация дара: герой с даром сам бьёт манекенов (атаки и навыки), видно срабатывания; и замер «без дара /
с даром» — урон, полученный урон и лечение за 10 сек того же боя.

Окно рисуется тем же BattleView, что и превью навыка (ui/skill_preview.py): камера проекции смотрит в окно.
"""
import copy

from sim.combat import Combat
from sim.teams import ENEMY, PLAYER
from ui import projection as P
from ui.skill_preview import MAIN, SIDE, BACK, SkillPreview

CYCLE = 9.0          # сек на один показ
DUMMY_HP = 1400      # манекены крепкие (один слабее — видно срабатывания «при убийстве»)


def preview_data(data):
    """Копия данных с полем-тренировкой: три манекена-слизня напротив героя."""
    enc = {"id": "preview", "name": "Тренировка", "kind": "normal", "chapter": "_preview",
           "map": ["." * 10 for _ in range(6)], "player_spawn": [[3, 3], [3, 1], [0, 0], [0, 5]], "deploy_max_x": 9,
           "enemies": [{"type": "slime", "pos": list(MAIN)}, {"type": "slime", "pos": list(SIDE)},
                       {"type": "slime", "pos": list(BACK)}]}
    d = copy.copy(data)
    d.encounters = [enc]
    return d


def dummy_fight(data, cls, proto, seed=3):
    """Бой героя против манекенов: герой под ИИ (атаки и навыки сам), манекены отвечают слабым ударом —
    чтобы срабатывали дары «когда бьют» и щиты."""
    c = Combat(data, 0, seed=seed, ai_teams=(PLAYER,), squad=[{"cls": cls, "proto": proto}])
    hero = c.heroes(PLAYER)[0]
    for i, f in enumerate(c.fighters(ENEMY)):
        f.max_hp = f.hp = DUMMY_HP if i < 2 else DUMMY_HP // 6
        f.atk_damage = max(1, int(hero.max_hp * 0.025))
        f.base["atk_damage"] = f.atk_damage
        f.move_time = 99.0                       # стоят на месте
    c.ais = [a for a in c.ais if a.team == PLAYER]
    return c


def measure(data, cls, proto, seconds=10.0):
    """Урон, полученный урон и лечение героя за seconds сек боя с манекенами."""
    c = dummy_fight(preview_data(data), cls, proto)
    hero = c.heroes(PLAYER)[0]
    while c.time < seconds and hero.alive:
        c.step()
    t = hero.tally
    return {"dealt": t["dealt"], "taken": t["taken"] + t["absorbed"], "absorbed": t["absorbed"], "healed": t["healed"],
            "kills": t["kills"]}


class GiftPreview(SkillPreview):
    """Герой (прототип уже с даром) бьёт манекенов по кругу; через CYCLE сек — заново."""

    def show_hero(self, cls, proto, title=""):
        self.cls, self.proto, self.title, self.sid = cls, proto, title, None
        self.restart()

    def restart(self):
        self.t, self.acc = 0.0, 0.0
        c = dummy_fight(self._data, self.cls, self.proto)
        self.c = c
        self.scene.combat = c
        self.caster = c.heroes(PLAYER)[0]
        self.foes = c.fighters(ENEMY)
        self.view.reset(c)

    def update(self, dt):
        if self.proto is None:
            return
        P.configure(self.rect.center, self.zoom)
        self.t += dt
        c = self.c
        self.acc += min(dt, 0.1)
        while self.acc >= c.dt:
            self.acc -= c.dt
            c.step()
        self.view.consume(c.events)
        c.events.clear()
        self.view.update(dt, dt)
        if self.t >= CYCLE or not self.caster.alive:
            self.restart()
