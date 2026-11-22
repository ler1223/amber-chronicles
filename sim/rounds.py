"""Бой раундами (прототип, docs/vision.md §11).

Время боя режется на раунды по len секунд (data/rounds.json). Перед каждым раундом экран встаёт на паузу: враги уже
решили, что сделают (намерение: кого бьют, какой навык готовят и куда), игрок отдаёт приказы, Space — раунд идёт.

Правила раунда:
  * герой ходит и бьёт автоатакой всегда, а навык (с ценой AP > 0) — один за раунд; AP нет (полные в начале
    раунда), откаты считаются в раундах (rounds_cd навыка или из старого отката и цены AP);
  * без приказа герой только бьёт автоатакой (автокаст отряда молчит; бот замеров — AutoCaster(force=True));
  * автоатака героя — aa_mult урона (решения важнее фона);
  * ульт и самый дорогой навык — заряды на день (тратятся до привала, sim/expedition.py);
  * враг в начале раунда планирует: цель атаки и один навык (навык своей роли первым) — с моментом удара fire;
    навык заказывается так, чтобы попасть к fire (fire − каст); не успел к fire + late — не применяет.
Роли врагов (громила, стрелок, заклинатель, лекарь, щитовик) дают навык по роли — data/rounds.json.
"""
import math

from .grid import cheb
from .teams import PLAYER

READY_FAR = 1e6              # откат «в раундах»: время не снимает его — снимает начало нужного раунда


class Rounds:
    def __init__(self, c):
        self.c = c
        self.cfg = c.data.rounds
        self.L = float(self.cfg["len"])
        self.t = 0.0             # секунд с начала раунда
        self.n = 0               # номер раунда (с 1)
        self.started = False
        self.awaiting = False    # раунд только начался — экран ставит паузу и сбрасывает флаг
        self.ready = {}          # (id юнита, навык) -> с какого раунда снова доступен
        self._ais = {}
        for u in c.units:
            if u.alive and not u.obj and u.team != PLAYER:
                self.ensure_role(u)

    # ---------- такт ----------

    def pre_step(self):
        if not self.started or self.t >= self.L - 1e-6:
            self.begin()

    def post_step(self, dt):
        self.t += dt

    def skill_k(self, caster):
        """Множитель навыков героя в раундах (не призывов и не врагов)."""
        if caster is None or caster.team != PLAYER or caster.summon or caster.owner is not None or caster.obj:
            return 1.0
        return float(self.cfg.get("skill_mult", 1.0))

    def left(self):
        return max(0.0, self.L - self.t)

    def begin(self):
        c = self.c
        self.started = True
        self.n += 1
        self.t = 0.0
        self.awaiting = True
        for u in c.units:
            if not u.alive or u.obj:
                continue
            u.round_lock = False
            for sid in list(u.cooldowns):
                key = (u.id, sid)
                if key in self.ready and self.ready[key] <= self.n:
                    del u.cooldowns[sid]
            if u.ap_max:
                u.ap = u.ap_max
        self.ready = {k: v for k, v in self.ready.items()
                      if v > self.n and k[1] in c.units[k[0]].cooldowns}
        for u in list(c.units):
            if u.alive and not u.obj and u.team != PLAYER:
                self.plan(u)
        c.emit("round", n=self.n)

    # ---------- навыки: замок раунда, откат, заряды ----------

    def locks(self, u, sk):
        """Тратит ли навык «навык раунда»: у героя — всё, что стоит AP (механики за 0 AP — свободны), у врага — всё."""
        return u.team != PLAYER or sk.get("ap", 0) > 0 or bool(sk.get("ult"))

    def cd_rounds(self, sk):
        if "rounds_cd" in sk:
            return int(sk["rounds_cd"])
        by_cd = math.ceil(sk.get("cooldown", 0) / self.L - 0.01) if sk.get("cooldown") else 0
        by_ap = int(round(sk.get("ap", 0) * self.cfg.get("cd_ap_k", 1.0))) - 1
        return max(0, by_cd, by_ap)

    def rounds_left(self, u, sid):
        """Сколько раундов ждать навык (0 — готов в следующем раунде или сейчас)."""
        r = self.ready.get((u.id, sid))
        return max(0, r - self.n) if r is not None and sid in u.cooldowns else 0

    def on_cast(self, u, sid, sk):
        """Каст начался: навык раунда потрачен, откат — в раундах, заряд на день — минус один."""
        if not self.locks(u, sk):
            return False
        u.round_lock = True
        k = self.cd_rounds(sk)
        if k > 0:
            u.cooldowns[sid] = READY_FAR
            self.ready[(u.id, sid)] = self.n + k + 1
        else:
            u.cooldowns.pop(sid, None)
        if sid in u.day_charges:
            u.day_charges[sid] = max(0, u.day_charges[sid] - 1)
        return True

    def undo(self, u, sid):
        """Каст отменён игроком: всё вернуть."""
        sk = u.skill_defs.get(sid, {})
        if not self.locks(u, sk):
            return
        u.round_lock = False
        self.ready.pop((u.id, sid), None)
        u.cooldowns.pop(sid, None)
        if sid in u.day_charges:
            u.day_charges[sid] += 1

    def why_not(self, u, sid, sk):
        if u.round_lock and self.locks(u, sk):
            return "Навык раунда уже применён"
        if u.day_charges.get(sid, 1) <= 0:
            return "Нет зарядов до привала"
        return ""

    def broken(self, u):
        """Врага оглушили (или заставили молчать) до удара — задуманный навык в этом раунде сорван."""
        it = u.intent
        if it and it.get("skill") and not it.get("done") and u.team != PLAYER:
            it["done"] = it["broken"] = True
            if u.order and u.order["type"] == "skill":
                u.order = None
            self.c.emit("intent_broken", unit=u, name=it.get("name", ""))

    # ---------- враги: роль и намерение ----------

    def role_of(self, u):
        if u.summon or u.owner is not None:
            return None
        return self.cfg["enemy_roles"].get(u.proto_id) or self.cfg["by_role"].get(u.role)

    def ensure_role(self, u):
        if getattr(u, "round_role_set", False):
            return
        u.round_role_set = True
        k = float(self.cfg.get("enemy_hp", 1.0))   # раунды: бой короче — враги тоньше
        if k != 1.0 and not u.obj:
            u.max_hp = max(1, int(round(u.max_hp * k)))
            u.hp = max(1, int(round(u.hp * k)))
        role = self.role_of(u)
        u.round_role = role
        if not role:
            return
        sid = self.cfg["roles"][role]["skill"]
        u.skill_defs = dict(u.skill_defs)
        sk = dict(self.cfg["skills"][sid])
        m = float(self.cfg.get("role_dmg", 1.0))   # сила ударов ролей — подбор баланса замером
        sk["effects"] = [dict(e, amount=e["amount"] * m) if e["type"] == "damage" else e for e in sk["effects"]]
        u.skill_defs[sid] = sk
        u.skills = [sid] + [s for s in u.skills if s != sid]

    def ai(self, team):
        from .ai import TeamAI
        if team not in self._ais:
            self._ais[team] = next((a for a in self.c.ais if a.team == team), None) or TeamAI(self.c, team)
        return self._ais[team]

    def plan(self, u):
        """Намерение врага на раунд: цель атаки и навык (с целью, зоной и моментом удара)."""
        c = self.c
        self.ensure_role(u)
        foes = c.foes_of(u)
        allies = c.fighters(u.team)
        ai = self.ai(u.team)
        attack = ai.pick_target(u, foes) if foes else None
        it = {"attack": attack, "skill": None}
        u.intent = it
        if not foes or u.stun >= self.L * 0.6:
            return
        for sid in u.skills:
            sk = u.skill_defs[sid]
            if not u.skill_ready(sid, sk) or "silence" in u.buffs:
                continue
            tgt = self.skill_target(u, sk, foes, allies, attack, ai)
            if tgt is None:
                continue
            fire = float(sk.get("fire", self.cfg["default_fire"]))
            start = max(0.0, fire - sk.get("cast", 0.0))
            center = u.cell if sk["target"] == "self" else (tgt.cell if hasattr(tgt, "cell") else tuple(tgt))
            r = sk.get("radius", 0)
            from .autocast import hits_enemies
            hostile = hits_enemies(sk)
            zone = sorted(c.grid.in_radius(center, r)) if r and sk["target"] in ("cell", "self") else []
            it.update(skill=sid, target=tgt, start=start, fire=fire, zone=zone, hostile=hostile,
                      name=sk["name"], done=False)
            return

    def skill_target(self, u, sk, foes, allies, attack, ai):
        kind = sk.get("ai")
        if kind == "smash":                      # громила: зона вокруг героя, которого он бьёт — если дотянется
            if attack is None or cheb(u.cell, attack.cell) > sk.get("range", 1) + 2:
                return None
            return tuple(attack.cell)
        if kind == "guard":                      # щитовик: когда рядом бой
            return u if any(cheb(f.cell, u.cell) <= 4 for f in foes) else None
        if sk["target"] == "enemy" and kind == "enemy_in_range":   # стрелок дотянется за раунд
            cand = [f for f in foes if cheb(u.cell, f.cell) <= sk["range"] + 1 and not f.obj]
            if not cand:
                return None
            if u.taunted_by in cand:
                return u.taunted_by
            return min(cand, key=lambda f: f.hp / max(1, f.max_hp))
        return ai.skill_target(u, sk, foes, allies)

    def think(self, ai, u):
        """Враг в раунде: навык намерения — к своему моменту, остальное время — бьёт цель намерения."""
        c = self.c
        it = getattr(u, "intent", None)
        if it is None:
            self.plan(u)
            it = u.intent
        o = u.order
        if o and o["type"] == "skill":
            if not u.cast and self.t > it.get("start", 0.0) + self.cfg["late"]:
                u.order = None                   # не успел к моменту удара — не бьёт по пустому позже
            else:
                return
        sid = it.get("skill")
        if sid and not it.get("done") and self.t >= it["start"]:
            it["done"] = True
            tgt = it["target"]
            if self.t <= it["start"] + self.cfg["late"] and not (hasattr(tgt, "alive") and not tgt.alive):
                if c.order_skill(u, sid, tgt)[0]:
                    return
        foes = c.foes_of(u)
        if not foes:
            return
        if u.role in ("ranged", "caster", "support") and u.kite_cd <= 0 and any(cheb(f.cell, u.cell) <= 1
                                                                                 for f in foes):
            cell = ai.retreat_cell(u, foes)
            if cell:
                c.order_move(u, cell)
                u.kite_cd = 3.0
                return
        if o and o["type"] == "move":
            return
        if ai.objective_order(u, foes):
            return
        t = it.get("attack")
        if u.taunted_by and u.taunted_by.alive:
            t = u.taunted_by
        if t is None or not t.alive or t not in foes:
            t = ai.pick_target(u, foes)
            it["attack"] = t
        cur = o["target"] if o and o["type"] == "attack" else None
        if cur is not t:
            c.order_attack(u, t)


# ---------- прогноз навыка (при прицеливании) ----------

def forecast(c, u, sid, target):
    """Примерный итог навыка прямо сейчас: {индекс юнита: (снято HP+щита, добьёт ли)} — по копии боя, без полёта
    снарядов. Не учитывает то, что случится позже (доты, призывы)."""
    from .planner import clone
    from .unit import Unit
    d = clone(c)
    d.hit_timing = False
    du = d.units[c.units.index(u)]
    if isinstance(target, Unit):
        tgt = d.units[c.units.index(target)]
    else:
        tgt = tuple(target)
    sk = du.skill_defs[sid]
    if sk["target"] == "self":
        tgt = du
    elif sk["target"] == "cell" and isinstance(tgt, Unit):
        tgt = tgt.cell
    before = [(v.hp, v.shield) for v in d.units]
    try:
        d._resolve_skill(du, sid, tgt)
        for item in list(d.delayed):            # отложенные попадания навыка — сразу
            if item.get("caster") is du:
                item["left"] = 0.0
        d._delayed_update(0.0)
    except Exception:                            # прогноз — подсказка, не должен ронять бой
        return {}
    out = {}
    for i, (v, (hp0, sh0)) in enumerate(zip(d.units, before)):
        lost = (hp0 + sh0) - (max(0, v.hp) + v.shield)
        if lost > 0 and not v.obj:
            out[i] = (int(round(lost)), not v.alive or v.hp <= 0)
    return out


# ---------- бот, читающий намерения (замеры, демо) ----------

FOCUS = {"healer": 0, "caster": 1, "shooter": 2, "guard": 4, "brute": 3}
BREAKS = ("stun", "sleep")


def breaks_cast(sk):
    """Навык срывает намерение врага: оглушение, сон, безмолвие."""
    from .autocast import flat_effects
    return any(e["type"] in BREAKS or (e["type"] == "buff" and e.get("stat") == "silence")
               for e in flat_effects(sk))


def focus_target(c, h):
    foes = [f for f in c.foes_of(h) if not f.obj]
    if not foes:
        return None
    reach = c.reach(h)
    return min(foes, key=lambda f: (cheb(h.cell, f.cell) > reach + 3, FOCUS.get(f.round_role, 5),
                                    f.hp / max(1, f.max_hp), cheb(h.cell, f.cell)))


def bot_round(c):
    """Приказы отряду в начале раунда: уйти из зон ударов, сорвать опасный каст, фокус по ролям, лучший навык."""
    from . import autopilot
    threats = [(e, e.intent) for e in c.units if e.alive and e.team != PLAYER and not e.obj and e.intent
               and e.intent.get("skill") and not e.intent.get("done")]
    danger = set()
    for e, it in threats:
        if it.get("hostile") and it.get("zone"):
            danger |= set(it["zone"])
    for h in c.heroes(PLAYER):
        if not h.alive or h.summon:
            continue
        h.queue.clear()
        focus = focus_target(c, h)
        moved = False
        if h.cell in danger:                    # уйти из зоны — ближайшая свободная клетка вне зон
            cells = [p for p in c.grid.in_radius(h.cell, 2) if p not in danger and c.is_free(p)]
            if cells:
                aim = focus.cell if focus is not None else h.cell
                cell = min(cells, key=lambda p: (cheb(p, h.cell), abs(cheb(p, aim) - c.reach(h))))
                moved = c.order_move(h, cell)[0]
        pick = None
        for e, it in sorted(threats, key=lambda x: FOCUS.get(x[0].round_role, 5)):
            for sid in h.skills:                # сорвать навык врага
                sk = h.skill_defs[sid]
                if breaks_cast(sk) and h.skill_ready(sid, sk) and cheb(h.cell, e.cell) <= sk["range"] + 1 \
                        and c.check_skill(h, sid, e if sk["target"] != "self" else h)[0]:
                    if sk["target"] == "self" and cheb(h.cell, e.cell) > sk.get("radius", 0):
                        continue
                    pick = (sid, e if sk["target"] != "self" else h)
                    break
            if pick:
                break
        if pick is None:
            pick = autopilot.choose(c.autocaster, h, scored=True)
        if moved:
            if pick:
                c.queue_order(h, {"type": "skill", "skill": pick[0], "target": pick[1]})
            if focus is not None:
                c.queue_order(h, {"type": "attack", "target": focus})
            continue
        if focus is not None:
            c.order_attack(h, focus)
        if pick:
            c.order_skill(h, pick[0], pick[1])
