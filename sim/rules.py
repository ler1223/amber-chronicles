"""Правила взаимодействий: «когда случилось событие с такими тегами — сделать вот это».

Каждое событие боя приходит сюда с тегами: что случилось и с какими свойствами. Правила лежат в data/rules.json
(общие для всех), а у героя, предмета или таланта — в proto["rules"] (срабатывают для своего хозяина). Так новые
эффекты действуют на результат старых без правки кода: «реакция Пар → ослепить», «столкновение горящего → поджечь
того, в кого врезался», «мой огненный удар добил врага → огонь вокруг».

События и их участники:
  status     unit — на кого повесили состояние;           теги — теги состояния (fire, control, root…)
  removed    unit — с кого сняли;                          теги — теги снятого
  reaction   unit, source;                                 теги — reaction, id реакции, обе стихии, friendly
  hit        unit — кого ударили, source — кто;            теги — вид удара (melee, spell, collision…), стихия
  kill       unit — кто погиб, source — кто добил;         теги — теги удара + состояния погибшего
  moved      unit — кого сдвинули, source — кто;           теги — forced, knockback / pull / gather / toss / swap…
  collision  unit — кто врезался, other — во что, source;  теги — collision + состояния врезавшегося
Кроме тегов события правило может требовать теги состояний участника: "unit_has", "other_has", "source_has",
и рельеф клетки участника: "where" (water, lava…).

Правило:
  {"id": "...", "name": "...", "on": "collision", "tags": [...все нужны], "not": [...ни одного],
   "unit_has": [...], "owner": "source|unit|any" (только для правил юнита), "do": [действия]}
Действие: {"type": status|cleanse|damage|stun|buff|hazard|push|heal, "to": unit|other|source|area, ...параметры}
  status: tag; cleanse: tags; damage: amount, tag, kind; stun: duration, look; buff: stat, value, duration;
  hazard: hazard, duration, radius; push: cells (от source); heal: amount; area: radius, side (enemies/allies/all
  относительно source).
"""
from .grid import cheb

MAX_DEPTH = 4


class Rules:
    def __init__(self, combat, rules):
        self.c = combat
        self.rules = [dict(r) for r in rules if "on" in r]
        self.depth = 0
        self.fired = []          # (id правила, событие) — для тестов и журнала

    def fire(self, event, tags, unit=None, source=None, other=None, **extra):
        if self.depth >= MAX_DEPTH or unit is None:
            return
        tags = set(tags)
        cand = [(r, None) for r in self.rules if r["on"] == event]
        for owner in (source, unit):          # правила с героя или предмета
            if owner is not None and owner.proto.get("rules"):
                cand += [(r, owner) for r in owner.proto["rules"] if r["on"] == event]
        if not cand:
            return
        self.depth += 1
        try:
            for r, owner in cand:
                if self._matches(r, owner, tags, unit, source, other):
                    self.fired.append((r.get("id"), event))
                    self.c.emit("rule", id=r.get("id"), name=r.get("name", ""), unit=unit)
                    for act in r["do"]:
                        self._do(act, owner, unit, source, other)
        finally:
            self.depth -= 1

    def _matches(self, r, owner, tags, unit, source, other):
        from .conditions import unit_tags
        if owner is not None:
            who = r.get("owner", "source")
            if who == "source" and owner is not source:
                return False
            if who == "unit" and owner is not unit:
                return False
        if not set(r.get("tags", [])) <= tags or set(r.get("not", [])) & tags:
            return False
        where = r.get("where")                   # рельеф клетки, где стоит участник
        if where and self.c.grid.get(unit.cell).terrain not in ([where] if isinstance(where, str) else where):
            return False
        for key, u in (("unit_has", unit), ("other_has", other), ("source_has", source)):
            need = r.get(key)
            if need and (u is None or not set(need) <= unit_tags(self.c, u)):
                return False
        return True

    def _targets(self, act, owner, unit, source, other):
        to = act.get("to", "unit")
        if to == "area":
            base = source or owner or unit
            side = act.get("side", "enemies")
            out = []
            for v in self.c.units_in_radius(unit.cell, act.get("radius", 1)):
                if v.obj and act["type"] not in ("damage", "push"):
                    continue
                if side == "enemies" and base is not None and not base.is_enemy(v):
                    continue
                if side == "allies" and base is not None and base.is_enemy(v):
                    continue
                out.append(v)
            return out
        v = {"unit": unit, "other": other, "source": source, "owner": owner}.get(to)
        return [v] if v is not None and v.alive else []

    def _do(self, act, owner, unit, source, other):
        c = self.c
        t = act["type"]
        by = owner or source
        if t == "hazard":
            for p in c.grid.in_radius(unit.cell, act.get("radius", 0)):
                cell = c.grid.get(p)
                if cell.passable and cell.terrain not in ("water", "chasm"):
                    cell.hazard, cell.hazard_time = act["hazard"], act.get("duration", 4)
                    cell.hazard_team = by.team if by is not None else None
            return
        for v in self._targets(act, owner, unit, source, other):
            if t == "status":
                c._touch_status(v, act["tag"], by)
            elif t == "cleanse":
                c.cleanse(v, act.get("tags"), by)
            elif t == "damage":
                c.damage(v, act["amount"], by, act.get("tag"), act.get("kind", "reaction"))
            elif t == "stun":
                c.apply_stun(v, act["duration"], act.get("look"))
            elif t == "buff":
                c.add_buff(v, act["stat"], act["value"], act["duration"])
            elif t == "heal":
                c.heal(v, act["amount"])
            elif t == "push" and by is not None and v is not by:
                c.force_push(by.cell if cheb(by.cell, v.cell) else unit.cell, v, act.get("cells", 1), by, "rule")
