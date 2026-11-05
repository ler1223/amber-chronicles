"""Сложности похода: враги сильнее, их больше и состав разнообразнее, у части — неприятные механики
(data/mutators.json), у боссов — фазы. Включается, если в enemy_scale боя есть "tier" (sim/expedition.py).

  против навыков  — глушащий (безмолвие и сбитый каст), гниющий (лечение вдвое слабее), пожирающий (крадёт стаки);
  поддержка стаи  — целящий (лечит врагов рядом), щитоносный (щиты соседям), вожак (аура урона);
  смерть — не конец — взрывной (взрыв после смерти), делящийся (двое меньших), неупокоенный (встаёт снова).
Все величины — доли HP или урона.
"""
from .grid import cheb
from .teams import ENEMY

DIRECT = ("melee", "ranged", "spell")


def apply(c, tier, scale):
    """В начале боя: подкрепление разных видов, механики части врагов, фазы боссов."""
    c.tier = tier
    pool = [e for e in tier.get("pool", []) if e in c.data.enemies and not c.data.enemies[e].get("boss")]
    have = {u.proto_id for u in c.alive(ENEMY)}
    fresh = [e for e in pool if e not in have] or pool     # сначала — виды, которых в бою ещё нет
    for _ in range(tier.get("adds", 0)):
        if not fresh:
            break
        etype = c.rng.choice(fresh)
        if spawn_add(c, etype, scale) is not None and etype in fresh and len(fresh) > 1:
            fresh.remove(etype)
    muts = sorted(c.data.mutators)
    foes = [u for u in c.alive(ENEMY) if not u.boss and not u.obj and not u.summon
            and not (tier.get("boss_node") and u.elite)]
    n = int(round(len(foes) * tier.get("mutated", 0.0)))
    chosen = c.rng.sample(foes, min(n, len(foes)))
    elites = [u for u in foes if u.elite and u not in chosen][:tier.get("elite_mut", 0)]
    for u in chosen + elites:
        mutate(c, u, c.rng.choice(muts))
    leaders = [u for u in c.alive(ENEMY) if u.boss] or         ([u for u in c.alive(ENEMY) if u.elite] if tier.get("boss_node") else [])   # главарь боя с боссом
    for u in leaders:
        if tier.get("boss_phases"):
            u.phases_left = [0.7, 0.35]
        if tier.get("boss_mut"):
            mutate(c, u, c.rng.choice([m for m in muts if c.data.mutators[m]["group"] != "death"]))


def spawn_add(c, etype, scale, near=None):
    """Ещё один враг на свободной клетке стороны врага (или рядом с near)."""
    if near is not None:
        cells = sorted((p for p in c.grid.in_radius(near, 2) if c.is_free(p)), key=lambda p: cheb(p, near))
    else:
        min_x = c.enc.get("deploy_max_x", c.cfg["deploy_max_x"]) + 4
        cells = [p for p, cell in sorted(c.grid.cells.items()) if cell.passable and p[0] >= min_x and c.is_free(p)
                 and cell.terrain not in ("lava", "chasm")]
    if not cells:
        return None
    pos = cells[0] if near is not None else cells[c.rng.randrange(len(cells))]
    u = c._spawn(ENEMY, etype, c.data.enemies[etype], pos)
    c._scale_enemy(u, scale)
    return u


def mutate(c, u, mid):
    d = c.data.mutators[mid]
    u.mutator = mid
    u.name = f"{d['name']} {u.name.lower()}"
    if mid == "restless":                       # неупокоенный: встаёт один раз
        u.undying = {"delay": d["delay"], "hp": d["hp"], "unless": []}


def tick(c, dt):
    for u in c.alive(ENEMY):
        if u.phases_left and u.hp <= u.max_hp * u.phases_left[0]:
            _phase(c, u)
        mid = u.mutator
        if not mid:
            continue
        d = c.data.mutators[mid]
        u.mut_t += dt
        if mid == "warlord" and u.mut_t >= 1.0:
            u.mut_t = 0.0
            for v in c.units_in_radius(u.cell, d["radius"]):
                if v is not u and v.alive and v.team == u.team and not v.obj:
                    c.add_buff(v, "atk_mult", d["atk"], 1.5)
        elif mid in ("pack_shaman", "shieldbearer") and u.mut_t >= d["every"]:
            u.mut_t = 0.0
            c.emit("aura", unit=u, radius=d["radius"])
            for v in c.units_in_radius(u.cell, d["radius"]):
                if not v.alive or v.team != u.team or v.obj:
                    continue
                if mid == "pack_shaman" and v.hp < v.max_hp:
                    c.heal(v, int(round(v.max_hp * d["heal"])))
                elif mid == "shieldbearer":
                    v.shield = max(v.shield, int(round(v.max_hp * d["shield"])))
                    v.shield_time = max(v.shield_time, d["duration"])
                    c.emit("shield", unit=v, amount=v.shield)
        if u.mut_cd > 0:
            u.mut_cd -= dt


def _phase(c, u):
    """Фаза босса: подкрепление; на последней — бешенство."""
    th = u.phases_left.pop(0)
    pool = [e for e in c.tier.get("pool", []) if e in c.data.enemies and not c.data.enemies[e].get("boss")]
    for _ in range(1 if (c.enemy_scale or {}).get("solo") else 2):
        if pool:
            spawn_add(c, c.rng.choice(pool), c.enemy_scale, near=u.cell)
    c.emit("boss_phase", unit=u, threshold=th, rage=not u.phases_left)
    if not u.phases_left:
        c.add_buff(u, "atk_speed", 0.6, 999)
        c.add_buff(u, "atk_mult", 1.3, 999)
        c.log(f"{u.name} в бешенстве!", (255, 110, 90))
    else:
        c.log(f"{u.name} зовёт подмогу!", (255, 170, 110))


def on_hit(c, a, t, dealt, kind):
    """Удар врага с механикой по герою."""
    mid = getattr(a, "mutator", None) if a is not None else None
    if not mid or dealt <= 0 or kind not in DIRECT or not t.alive or t.team == a.team:
        return
    d = c.data.mutators[mid]
    if mid == "suppressor" and a.mut_cd <= 0:
        a.mut_cd = d["icd"]
        c.add_buff(t, "silence", 1, d["silence"])
        c.emit("mutator", unit=t, src=a, mutator=mid)
    elif mid == "decay":
        c.add_buff(t, "heal_taken", d["heal_taken"], d["duration"])
    elif mid == "devourer" and a.mut_cd <= 0 and t.pp > 0 and (t.passive or {}).get("core"):
        a.mut_cd = d["icd"]
        t.pp -= d["steal"]
        c.heal(a, int(round(a.max_hp * d["heal"])))
        c.emit("gauge", unit=t, event="stolen")
        c.emit("mutator", unit=t, src=a, mutator=mid)


def on_death(c, u):
    mid = getattr(u, "mutator", None)
    if not mid or u.team != ENEMY:
        return
    d = c.data.mutators[mid]
    if mid == "explosive":
        cell, radius, pct = u.cell, d["radius"], d["pct"]
        c.emit("mutator_warn", pos=cell, radius=radius, delay=d["delay"])

        def blast():
            c.emit("mutator_blast", pos=cell, radius=radius)
            for v in c.units_in_radius(cell, radius):
                if v.alive and v.team != ENEMY and not v.obj:
                    c.damage(v, v.max_hp * pct, None, "fire", "reaction")
        c.delayed.append({"left": d["delay"], "total": d["delay"], "fn": blast, "tunit": None})
    elif mid == "splitter":
        for _ in range(d["count"]):
            v = spawn_add(c, u.proto_id, c.enemy_scale, near=u.cell)
            if v is None:
                break
            v.max_hp = v.hp = max(1, int(round(u.max_hp * d["hp"])))
            v.atk_damage = max(1, int(round(u.atk_damage * d["atk"])))
            v.base.update(atk_damage=v.atk_damage)
            v.name = f"Осколок: {c.data.enemies[u.proto_id]['name'].lower()}"
            c.emit("summon", unit=v, owner=None)
