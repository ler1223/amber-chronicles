"""Сменный «мозг» врагов: наблюдение → действие. Точка подключения своей модели (например, обученной нейросети).

По умолчанию работает RuleBrain — нынешние правила sim/ai.py. Своя модель подключается в data/config.json:
    "enemy_brain": "rules"                      — правила (по умолчанию)
    "enemy_brain": "my_package.my_module:MyBrain" — класс с методом decide(obs) → action

Наблюдение (observe) — словарь чисел о юните и поле, действие — словарь:
    {"type": "attack", "target": <id юнита>}
    {"type": "move", "cell": [x, y]}
    {"type": "skill", "skill": <id навыка>, "target": <id юнита> | [x, y]}
    {"type": "wait"} или None — ничего не менять
Мозг вызывается раз в TeamAI.THINK секунд для каждого врага, который не кастует, не оглушён и не идёт.
"""
import importlib

from .grid import cheb


class Brain:
    """База: decide(obs) → action. Наблюдение готовит observe(), приказ выполняет apply_action()."""

    def decide(self, obs):
        return None


class RuleBrain(Brain):
    """Нынешний ИИ по правилам (sim/ai.py): он сам отдаёт приказы, наблюдение ему не нужно."""
    rules = True


def make(spec):
    if not spec or spec == "rules":
        return RuleBrain()
    mod, _, cls = spec.partition(":")
    return getattr(importlib.import_module(mod), cls or "Brain")()


def _unit(u, me):
    return {"id": u.id, "x": u.cell[0], "y": u.cell[1], "hp": u.hp, "max_hp": u.max_hp, "armor": u.total_armor(),
            "atk": u.atk_damage, "range": u.atk_range, "dist": cheb(u.cell, me.cell), "casting": bool(u.cast),
            "stun": round(u.stun, 2), "cls": u.proto_id, "statuses": sorted(u.statuses), "shield": u.shield}


def observe(c, u):
    """Числа о юните и поле для мозга: сам юнит, союзники, враги, навыки и их готовность."""
    me = _unit(u, u)
    me.update({"ap": u.ap, "ap_max": u.ap_max, "boss": u.boss, "mutator": u.mutator,
               "skills": [{"id": sid, "ready": u.skill_ready(sid, u.skill_defs[sid]),
                           "range": u.skill_defs[sid]["range"], "target": u.skill_defs[sid]["target"]}
                          for sid in u.skills]})
    return {"time": round(c.time, 2), "me": me,
            "allies": [_unit(v, u) for v in c.fighters(u.team) if v is not u],
            "foes": [_unit(v, u) for v in c.foes_of(u)],
            "board": [c.grid.w, c.grid.h]}


def apply_action(c, u, action):
    """Действие мозга → приказ бою. Неверное действие просто пропускается."""
    if not action or action.get("type") == "wait":
        return False
    by_id = {v.id: v for v in c.units if v.alive}
    t = action.get("type")
    if t == "attack" and action.get("target") in by_id:
        return c.order_attack(u, by_id[action["target"]])[0]
    if t == "move" and action.get("cell"):
        return c.order_move(u, tuple(action["cell"]))[0]
    if t == "skill" and action.get("skill") in u.skills:
        tgt = action.get("target")
        tgt = by_id.get(tgt) if isinstance(tgt, int) else (tuple(tgt) if tgt else u)
        return c.order_skill(u, action["skill"], tgt)[0] if tgt is not None else False
    return False
