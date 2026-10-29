"""ИИ команды: простые правила по роли юнита. Отдаёт те же приказы, что и игрок.

Навыки отряда игрока ИИ не трогает — их применяет автокаст (sim/autocast.py)."""
from .grid import cheb
from .teams import PLAYER

RANGED_ROLES = ("ranged", "caster", "support")


class TeamAI:
    THINK = 0.4

    def __init__(self, combat, team):
        self.c = combat
        self.team = team

    def update(self, dt):
        for u in self.c.fighters(self.team):
            if u.cast or u.stun > 0 or u.moving:
                continue
            u.ai_timer -= dt
            if u.ai_timer > 0:
                continue
            u.ai_timer = self.THINK
            self.think(u)

    def think(self, u):
        c = self.c
        foes = c.foes_of(u)
        if not foes:
            return
        allies = c.fighters(u.team)
        if u.order and u.order["type"] == "skill":
            return  # уже идёт применять навык

        for sid in (u.skills if self.team != PLAYER else []):
            sk = u.skill_defs[sid]
            if not u.skill_ready(sid, sk):
                continue
            target = self.skill_target(u, sk, foes, allies)
            if target is not None and c.order_skill(u, sid, target)[0]:
                return

        if u.role in RANGED_ROLES and u.kite_cd <= 0 and any(cheb(f.cell, u.cell) <= 1 for f in foes):
            cell = self.retreat_cell(u, foes)
            if cell:
                c.order_move(u, cell)
                u.kite_cd = 3.0
                return
        if u.order and u.order["type"] == "move":
            return
        if self.objective_order(u, foes):
            return

        target = self.pick_target(u, foes)
        cur = u.order["target"] if u.order and u.order["type"] == "attack" else None
        # не дёргаться между целями, если новая ненамного ближе
        if cur and cur.alive and not u.taunted_by and cheb(u.cell, cur.cell) <= cheb(u.cell, target.cell) + 1:
            return
        c.order_attack(u, target)

    def objective_order(self, u, foes):
        """Цель боя важнее ближайшего противника: ближники лезут в круг удержания (и враги, и бот отряда),
        каждый второй ближник врага идёт к обозу, ближники отряда их перехватывают; бот отряда ломает источники."""
        c = self.c
        ob = c.objective
        if not ob or u.taunted_by or u.static:
            return False
        nobody = not any(c.in_hold(a.cell) for a in c.fighters(u.team) if not a.summon)
        if ob["type"] == "hold" and (u.role not in RANGED_ROLES or (u.team == PLAYER and nobody)) \
                and not c.in_hold(u.cell):
            if any(cheb(f.cell, u.cell) <= 1 for f in foes):
                return False                     # связан боем — сначала отбиться
            cells = [tuple(p) for p in ob["cells"] if c.is_free(tuple(p))]
            if cells:
                return c.order_move(u, min(cells, key=lambda p: cheb(p, u.cell)))[0]
        if ob["type"] == "destroy" and u.team == PLAYER and not any(cheb(f.cell, u.cell) <= 1 for f in foes
                                                                    if not f.obj):
            srcs = [f for f in foes if f.obj and f.obj.get("source")]
            if srcs:                             # бот отряда ломает источники, если его не держат в бою
                t = min(srcs, key=lambda f: cheb(f.cell, u.cell))
                cur = u.order["target"] if u.order and u.order["type"] == "attack" else None
                return cur is t or c.order_attack(u, t)[0]
        if ob["type"] == "defend" and u.team == PLAYER and u.role not in RANGED_ROLES:
            raiders = [f for f in foes if f.order and f.order.get("target") in c.guards()
                       and cheb(f.cell, u.cell) <= 4]
            if raiders:                          # бот отряда перехватывает тех, кто идёт к обозу
                t = min(raiders, key=lambda f: cheb(f.cell, u.cell))
                cur = u.order["target"] if u.order and u.order["type"] == "attack" else None
                return cur is t or c.order_attack(u, t)[0]
        if ob["type"] == "defend" and u.team != PLAYER and u.role not in RANGED_ROLES and u.id % 2 == 0:
            guards = [g for g in c.guards() if g.alive]
            if guards:
                g = min(guards, key=lambda g: cheb(g.cell, u.cell))
                cur = u.order["target"] if u.order and u.order["type"] == "attack" else None
                return cur is g or c.order_attack(u, g)[0]
        return False

    def pick_target(self, u, foes):
        if u.taunted_by and u.taunted_by.alive:
            return u.taunted_by
        if u.role in ("ranged", "caster"):
            in_range = [f for f in foes if cheb(u.cell, f.cell) <= self.c.reach(u)]
            if in_range:
                return min(in_range, key=lambda f: f.hp)
        return min(foes, key=lambda f: (cheb(u.cell, f.cell), f.hp))

    def retreat_cell(self, u, foes):
        def safety(p):
            return min(cheb(p, f.cell) for f in foes)
        best, best_s = None, safety(u.cell)
        for n, _ in self.c.grid.neighbors(u.cell):
            if self.c.is_free(n) and safety(n) > best_s:
                best, best_s = n, safety(n)
        return best

    def skill_target(self, u, sk, foes, allies):
        ai = sk.get("ai")
        rng = sk["range"]
        if ai == "enemy_in_range":
            cand = [f for f in foes if cheb(u.cell, f.cell) <= rng]
            if u.taunted_by in cand:
                return u.taunted_by
            return min(cand, key=lambda f: f.hp) if cand else None
        if ai == "heal_ally":
            cand = [a for a in allies if a.hp < a.max_hp * 0.6 and cheb(u.cell, a.cell) <= rng + 2]
            return min(cand, key=lambda a: a.hp / a.max_hp) if cand else None
        if ai == "summon_self":
            limit = next((e.get("limit", 1) for e in sk["effects"] if e["type"] == "summon"), 1)
            mine = sum(1 for s in self.c.units if s.alive and s.owner is u)
            return u if mine < limit and any(cheb(f.cell, u.cell) <= 6 for f in foes) else None
        if ai == "shield_ally":
            cand = [a for a in allies if a.shield <= 0 and a.hp < a.max_hp * 0.85 and cheb(u.cell, a.cell) <= rng]
            return min(cand, key=lambda a: a.hp / a.max_hp) if cand else None
        if ai == "self_buff":
            return u if any(cheb(f.cell, u.cell) <= 3 for f in foes) else None
        if ai == "adjacent_foes":
            return u if any(cheb(f.cell, u.cell) <= 1 for f in foes) else None
        if ai == "cluster":
            r = sk.get("radius", 1)
            best, best_n = None, 0
            for p in self.c.grid.in_radius(u.cell, rng):
                n = sum(1 for f in foes if cheb(f.cell, p) <= r)
                if n > best_n:
                    best, best_n = p, n
            return best if best_n >= sk.get("min_targets", 1) else None
        return None
