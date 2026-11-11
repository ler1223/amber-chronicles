"""Пассивки-основы классов (data/passives.json): вокруг них строится игра героя.

Стаки пассивки живут на шкале героя (u.pp, макс. u.pp_max) — их видно делениями под фигуркой и на панели.
Пассивка-условие пишет в шкалу текущее значение условия (сколько тотемов, сколько построек), чтобы его было видно.
Все величины — в процентах: «+8% урона за стак», «лечение 2% HP», а не в единицах.

  duel_fury   воин      — стак за удар по вызванному: урон ↑, получаемый урон ↓; без вызванного стаки тают
  ramp        лучник    — стак за попадание по той же цели: атаки быстрее; смена цели — стаки пополам;
                          на максимуме эффект колчана двойной
  inner_flame пиромант  — стак Жара за каждый Огонь, наложенный магом: огонь сильнее; Вспышка тратит Жар
  faith       жрец      — Вера за лечение: лечение ↑, союзники рядом получают меньше урона; чудеса тратят Веру
  backstab    ассасин   — удары в спину ×mult (просто)
  wild        друид     — зверь копит Дикость, в человека — Дикость лечит отряд; человек копит Гармонию,
                          в зверя — Гармония усиливает атаки
  dig_in      страж     — стоит на месте — стаки: получаемый урон ↓, копьё зоны ↑; на максимуме копьё оглушает
  totems      шаман     — за каждый тотем сила ↑; рядом с тотемом получаемый урон ↓
  powder      подрывник — Порох копится сам; заряд с Порохом взрывается ×2, без — ×0.6
  hardhead    таран     — столкновения ×2 и лечат тарана
  finisher    ловчий    — по пойманным ×mult
  fortress    криомант  — за каждую постройку: Холод дольше, получаемый урон ↓
  souls       некромант — души за смерти рядом и трупы: сила ↑, призванные крепче
  mass        гравитомант — стак Массы за каждого сдвинутого врага; Коллапс и Чёрная дыра тратят
  soil        геомант   — бонус по клетке под собой: трава — лечение, камень — защита, вода — AP, лава — сила
  recipe      зельевар  — каждый новый тег за бой — ингредиент: реактивы сильнее; все — реактивы не снимают теги
  near_death  берсерк   — чем меньше HP, тем сильнее и быстрее; кровоточащие рядом лечат
  compassion  связующий — урон через нити копит Сострадание: лечение ↑, на максимуме все на нитях лечатся
  time        хрономант — без AP: Время копят остановки, тратят перемотки
  commander   тактик    — сам не бьёт: вместо атаки приказывает союзнику ударить его цель
  notes       бард      — три ноты, мелодии из последних трёх нот (sim/kit.py — notes)
"""
from sim.grid import cheb


def core(u):
    p = u.passive if u is not None else None
    return p if p and p.get("core") else None


def kind(u):
    p = core(u)
    return p["core"] if p else None


def _set(u, n):
    u.pp = max(0, min(u.pp_max, n))


def _add(c, u, n=1):
    if u.pp_max <= 0:
        return
    old = u.pp
    _set(u, u.pp + n)
    if u.pp != old:
        c.emit("gauge", unit=u, event="passive")


# ---------- урон ----------

def out_mult(c, a, t, kind_, tag, basic, eff=None):
    """Множитель исходящего урона от пассивки атакующего (и его хозяина для призыва)."""
    if a is None:
        return 1.0
    owner = a.owner if a.summon and a.owner is not None else None
    k = 1.0
    p = core(a)
    if p:
        ck = p["core"]
        if ck == "duel_fury" and any(m["src"] is a for mid, m in t.marks.items() if mid in ("challenge", "duel")):
            k *= 1 + p["dmg"] * a.pp
        elif ck == "inner_flame" and tag == "fire":
            k *= 1 + p["fire"] * a.pp
        elif ck == "backstab" and c.exposed(t, a) and kind_ in ("melee", "ranged", "spell"):
            k *= p["mult"]
            c.emit("backstab", unit=t, src=a)
        elif ck == "finisher" and t.stun > 0 and t.stun_look in ("trap", "net", "root", "freeze"):
            k *= p["mult"]
        elif ck == "totems" and not basic:
            k *= 1 + p["per_totem"] * _totems(c, a)
        elif ck == "souls" and not basic:
            k *= 1 + p["power"] * a.pp
        elif ck == "soil" and not basic and _ground(c, a) == "lava":
            k *= 1 + p["lava_power"]
        elif ck == "near_death":
            k *= 1 + p["dmg"] * _missing(a)
    if owner is not None and kind(owner) == "totems" and a.proto_id.startswith("totem"):
        k *= 1 + core(owner)["per_totem"] * _totems(c, owner)
    return k


def in_mult(c, t, a, kind_):
    """Множитель входящего урона по цели от пассивок (её и союзников рядом)."""
    k = 1.0
    p = core(t)
    if p:
        ck = p["core"]
        if ck == "duel_fury" and a is not None and any(m["src"] is t for mid, m in a.marks.items()
                                                         if mid in ("challenge", "duel")):
            k *= max(0.4, 1 - p["guard"] * t.pp)
        elif ck == "dig_in":
            k *= max(0.4, 1 - p["guard"] * t.pp)
        elif ck == "totems" and any(cheb(s.cell, t.cell) <= 2 for s in _own_totems(c, t)):
            k *= 1 - p["near_guard"]
        elif ck == "fortress":
            k *= max(0.5, 1 - p["guard"] * t.pp)
        elif ck == "soil" and _ground(c, t) == "stone":
            k *= 1 - p["stone_guard"]
    for pr in c.units:                                 # Вера жреца: союзникам рядом меньше урона
        if pr is not t and pr.alive and pr.team == t.team and kind(pr) == "faith" and pr.pp > 0 \
                and cheb(pr.cell, t.cell) <= 2:
            k *= max(0.7, 1 - core(pr)["ally_guard"] * pr.pp)
    return k


def after_damage(c, a, t, dealt, kind_, tag, basic):
    """Стаки за нанесённый урон."""
    if a is None or dealt <= 0 or not a.alive:
        return
    p = core(a)
    if not p:
        return
    ck = p["core"]
    if ck == "duel_fury" and any(m["src"] is a for mid, m in t.marks.items() if mid in ("challenge", "duel")):
        _add(c, a)
        a.pass_t = 0.0
    elif ck == "ramp" and kind_ in ("ranged", "melee"):
        if a.pass_target is t or "all_arrows" in a.buffs:   # «Все стрелы»: смена цели Разгон не сбрасывает
            _add(c, a)
        else:
            _set(a, a.pp // 2)
        a.pass_target = t
        a.pass_t = 0.0
    elif ck == "wild" and a.form is not None and kind_ == "melee":
        a.wild = min(p["max"], a.wild + 1)
        _set(a, a.wild)


def atk_cd_mult(c, u):
    p = core(u)
    if not p:
        return 1.0
    if p["core"] == "ramp":
        return 1 / (1 + p["speed"] * u.pp)
    if p["core"] == "near_death":
        return 1 / (1 + p["speed"] * _missing(u))
    return 1.0


def heal_mult(c, u):
    p = core(u)
    if not p:
        return 1.0
    if p["core"] == "faith":
        return 1 + p["heal"] * u.pp
    if p["core"] == "compassion":
        return 1 + p["heal"] * u.pp
    return 1.0


def arrow_mult(u):
    p = core(u)
    return 2.0 if p and p["core"] == "ramp" and u.pp >= u.pp_max > 0 else 1.0


def collision(c, pusher, dmg):
    """Твердолобый таран: удар о преграду сильнее и лечит его."""
    p = core(pusher)
    if p and p["core"] == "hardhead":
        dmg *= p["mult"]
        c.heal(pusher, int(round(dmg * p["heal"])))
    return dmg


def zoc_mult(u):
    p = core(u)
    if p and p["core"] == "dig_in":
        return 1 + p["spear"] * u.pp, u.pp >= u.pp_max > 0
    return 1.0, False


# ---------- события ----------

def on_status(c, v, tag, attacker):
    p = core(attacker)
    if not p or attacker is None:
        return
    if p["core"] == "inner_flame" and tag == "fire":
        _add(c, attacker)
    elif p["core"] == "recipe":
        attacker.recipe.add(tag)
        _set(attacker, len(attacker.recipe))


def on_death(c, v):
    for n in c.units:
        if n.alive and kind(n) == "souls" and n.is_enemy(v) and cheb(n.cell, v.cell) <= core(n)["radius"]:
            _add(c, n)


def on_corpse(c, caster):
    if kind(caster) == "souls":
        _add(c, caster)


def on_pulled(c, caster):
    if kind(caster) == "mass":
        _add(c, caster, core(caster).get("per_pull", 1))


def on_form(c, u, old, new):
    p = core(u)
    if not p or p["core"] != "wild":
        return
    if new is None and u.wild > 0:                      # зверь → человек: Дикость лечит отряд
        for a in c.units:
            if a.alive and a.team == u.team and not a.obj and cheb(a.cell, u.cell) <= 3:
                c.heal(a, int(round(a.max_hp * p["heal_pct"] * u.wild)))
        c.emit("passive", unit=u, name=p["name"], kind="wild", detail=f"Дикость {u.wild} → лечение", other=None)
        u.wild = 0
    elif new is not None and u.harmony > 0:             # человек → зверь: Гармония усиливает атаки
        c.add_buff(u, "atk_mult", round(1 + p["harmony_atk"] * u.harmony, 2), p["harmony_time"])
        c.emit("passive", unit=u, name=p["name"], kind="wild", detail=f"Гармония {u.harmony} → сила", other=None)
        u.harmony = 0
    _set(u, u.wild if new is not None else u.harmony)


def on_heal_given(c, healer):
    p = core(healer)
    if p and p["core"] == "wild" and healer.form is None:
        healer.harmony = min(p["max"], healer.harmony + 1)
        _set(healer, healer.harmony)


def on_tether(c, binder, amount):
    p = core(binder)
    if not p or p["core"] != "compassion":
        return
    binder.pass_acc += amount
    step = binder.max_hp * p["per_pct"]
    while binder.pass_acc >= step:
        binder.pass_acc -= step
        _add(c, binder)
    if binder.pp >= binder.pp_max > 0:                   # Сострадание на максимуме: все на нитях исцеляются
        for v in c.units:
            if v.alive and (v.tethered_by is binder or v is binder):
                c.heal(v, int(round(v.max_hp * p["burst_pct"])))
                if v is not binder:
                    c.emit("link", src=binder, dst=v, color=(150, 230, 255))
        c.emit("passive", unit=binder, name=p["name"], kind="compassion", detail="все на нитях исцеляются", other=None)
        _set(binder, 0)


def summon_mult(owner):
    p = core(owner)
    if p and p["core"] == "souls":
        return 1 + p["summon"] * owner.pp
    return 1.0


# ---------- каждый шаг ----------

def tick(c, u, dt):
    p = core(u)
    if not p:
        return
    ck = p["core"]
    u.pass_t += dt
    if ck == "duel_fury":
        has = any(m["src"] is u for v in c.units if v.alive for mid, m in v.marks.items() if mid in ("challenge", "duel"))
        if not has and u.pass_t > p["keep"] and u.pp > 0 and int(u.pass_t) != int(u.pass_t - dt):
            _add(c, u, -1)
    elif ck == "ramp":
        if u.pass_t > p["keep"] and u.pp > 0 and "all_arrows" not in u.buffs:
            _set(u, 0)
            u.pass_target = None
    elif ck == "dig_in":
        if u.moving:
            if u.pp:
                _set(u, 0)
            u.pass_t = 0.0
        elif u.pass_t >= p["every"]:
            u.pass_t -= p["every"]
            _add(c, u)
    elif ck == "totems":
        _set(u, _totems(c, u))
    elif ck == "fortress":
        _set(u, sum(1 for o in c.units if o.alive and o.obj and o.owner is u))
    elif ck == "soil":
        g = _ground(c, u)
        if g == "grass" and u.pass_t >= 1.0:
            u.pass_t -= 1.0
            c.heal(u, int(round(u.max_hp * p["grass_regen"])))
        if g == "water":
            u.ap_timer += dt * p["water_ap"]
        u.soil = g
    elif ck == "near_death":
        _set(u, int(round(_missing(u) * u.pp_max)))
        if u.pass_t >= 1.0:
            u.pass_t -= 1.0
            n = sum(1 for v in c.units if v.alive and u.is_enemy(v) and "bleed" in v.statuses and cheb(v.cell, u.cell) <= 2)
            if n:
                c.heal(u, int(round(u.max_hp * p["bleed_regen"] * n)))
    elif ck == "powder":
        if u.pass_t >= p["every"]:
            u.pass_t -= p["every"]
            _add(c, u)


def _missing(u):
    return max(0.0, min(1.0, 1 - u.hp / max(1, u.max_hp)))


def _own_totems(c, u):
    return [s for s in c.units if s.alive and s.owner is u and s.proto_id.startswith("totem")]


def _totems(c, u):
    return len(_own_totems(c, u))


def _ground(c, u):
    g = c.grid.get(u.cell)
    return g.terrain if g else None


def powder_mult(c, u, sk):
    """Подрывник ставит заряд: с Порохом — ×2 (Порох тратится), без — ×0.6."""
    p = core(u)
    if not p or p["core"] != "powder" or not sk.get("powder"):
        return None
    cost = sk.get("powder_cost", 1)           # ящик динамита — 3 Пороха разом
    if u.pp >= cost:
        _add(c, u, -cost)
        return p["with"]
    return p["without"]
