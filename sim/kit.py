"""Механики «характеров» классов: на них построены навыки героев (data/skills.json, классы — data/classes.json).

  метки (marks)   — стаки на юните: Вызов воина, Холод криоманта, Липкая бомба подрывника… (config.marks)
                    у метки: max, per-stack эффекты (замедление), on_max — что случается на полном счёте,
                    on_expire — что случается, когда истекла (бомба взрывается), src_deals / src_takes — поединок;
  шкала класса    — gauge (data/gauges.json): навык может стоить делений (gauge_cost), тратить всю шкалу
                    (gauge_spend: "all") и усиливаться за каждое потраченное деление (per_gauge у эффекта);
  колчан          — активный тип стрел лучника: обычные атаки и выстрелы с arrow: true несут его эффект;
  зоны            — эффекты, что срабатывают раз в every сек в радиусе (колодец гравитоманта, холод у глыб);
  тотемы          — пульс всех тотемов, перенос тотема, молния между тотемами;
  прочее          — танец теней, загон на капканы, кража времени, подрыв зарядов, создать/поднять трупы.

Модуль — функции над боем (sim/combat.py вызывает их в нужных местах), своё состояние — в юнитах и combat.zones.
"""
import math

from sim.grid import cheb

TYPES = {"mark", "zone", "vault", "barrage", "shackle", "fletch", "trail", "ignite_charges", "barrel_rain",
         "ball", "storm_front", "ancestors",
         "reactive", "totem_pulse", "totem_move", "totem_link", "shadow_dance", "trap_pull",
         "time_theft", "detonate_charges", "song_notes", "inferno", "consume_fire", "bleed_feast", "raise_all",
         "song_tempo", "song_finale", "corpse_pulse", "reagent_area", "cut_tethers", "tether_heal", "tether_all",
         "terrain_wave", "note", "finale"}
HELD_LOOKS = ("trap", "net", "root", "freeze")


def mark_def(c, mid):
    return c.cfg["marks"][mid]


# ---------- метки ----------

def add_mark(c, v, mid, stacks, duration, src):
    """Стаки метки на юните; на полном счёте — on_max."""
    if not v.alive or v.obj:
        return
    d = mark_def(c, mid)
    from sim import passives as PS
    if mid == "cold" and PS.kind(src) == "fortress":   # за каждую постройку криоманта Холод дольше
        duration += PS.core(src)["cold_time"] * src.pp
    m = v.marks.get(mid)
    if m is None:
        m = v.marks[mid] = {"n": 0, "t": 0.0, "src": src, "total": duration}
    if d.get("single") and src is not None:       # вызов: метка одна на всё поле
        for u in c.units:
            if u is not v and mid in u.marks and u.marks[mid]["src"] is src:
                del u.marks[mid]
    m["n"] = min(d.get("max", 99), m["n"] + stacks)
    m["t"] = max(m["t"], duration)
    m["total"] = max(m["total"], m["t"])
    m["src"] = src or m["src"]
    c.emit("mark", unit=v, mark=mid, n=m["n"], src=src)
    _mark_side(c, v, mid, m)
    if m["n"] >= d.get("max", 99) and d.get("on_max"):
        if d.get("clear_on_max", True):
            del v.marks[mid]
        c.emit("mark_max", unit=v, mark=mid, src=src)
        c.apply_effects(src or v, d["on_max"], v.cell, v)


def _mark_side(c, v, mid, m):
    d = mark_def(c, mid)
    if d.get("slow_per"):                          # холод: каждый стак — медленнее
        c.add_buff(v, "slow", round(1 + d["slow_per"] * m["n"], 2), m["t"])
    if d.get("taunt") and m["src"] is not None:    # вызов: бьёт только вызвавшего
        v.taunted_by, v.taunt_time = m["src"], m["t"]


def tick_marks(c, u, dt):
    for mid in list(u.marks):
        m = u.marks[mid]
        m["t"] -= dt
        if m["t"] <= 0:
            del u.marks[mid]
            d = mark_def(c, mid)
            c.emit("mark_end", unit=u, mark=mid)
            if m.get("on_expire") or d.get("on_expire"):
                c.emit("mark_max", unit=u, mark=mid, src=m["src"])
                c.apply_effects(m["src"] or u, [dict(e, _n=m["n"], _powder=m.get("mult", 1.0))
                                                for e in m.get("on_expire") or d["on_expire"]], u.cell, u)


def consume_mark(c, v, mid):
    """Снять метку целиком; бомба при этом взрывается (on_expire)."""
    m = v.marks.pop(mid, None)
    if m is None:
        return 0
    d = mark_def(c, mid)
    c.emit("mark_end", unit=v, mark=mid)
    if (m.get("on_expire") or d.get("on_expire")) and d.get("burst_on_consume"):
        c.emit("mark_max", unit=v, mark=mid, src=m["src"])
        c.apply_effects(m["src"] or v, [dict(e, _n=m["n"], _powder=m.get("mult", 1.0))
                                        for e in m.get("on_expire") or d["on_expire"]], v.cell, v)
    return m["n"]


def duel_mult(c, target, attacker):
    """Поединок: вызвавший бьёт вызванного сильнее и получает от него меньше."""
    if attacker is None:
        return 1.0
    k = 1.0
    for mid, m in target.marks.items():
        d = mark_def(c, mid)
        if m["src"] is attacker and d.get("src_deals"):
            k *= d["src_deals"]
    for mid, m in attacker.marks.items():
        d = mark_def(c, mid)
        if m["src"] is target and d.get("src_takes"):
            k *= d["src_takes"]
    return k


# ---------- удар навыка ----------

def density(c, v, caster):
    """Сколько врагов кастера стоит вплотную к цели (сжатие гравитоманта)."""
    return sum(1 for w in c.units if w is not v and w.alive and not w.obj and caster.is_enemy(w)
               and cheb(w.cell, v.cell) <= 1)


def held(v):
    return v.stun > 0 and v.stun_look in HELD_LOOKS


def hit_mult(c, caster, v, eff):
    """Множители урона навыка от механик класса."""
    k = 1.0
    pm = eff.get("per_mark")
    if pm and pm["mark"] in v.marks:
        n = v.marks[pm["mark"]]["n"]
        k *= 1 + pm.get("mult", 0.25) * n
        if pm.get("consume"):
            consume_mark(c, v, pm["mark"])
    if eff.get("per_density"):
        k *= 1 + eff["per_density"] * density(c, v, caster)
    if eff.get("vs_held") and held(v):
        k *= eff["vs_held"]
    if eff.get("vs_frozen") and (held(v) and v.stun_look == "freeze" or "cold" in v.marks):
        k *= eff["vs_frozen"]
    if eff.get("_spent") and eff.get("per_gauge"):
        k *= 1 + eff["per_gauge"] * eff["_spent"]
    if eff.get("_powder"):
        k *= eff["_powder"]
    if eff.get("_n") and eff.get("per_stack"):
        k *= 1 + eff["per_stack"] * (eff["_n"] - 1)
    if eff.get("from_shadow") and max(caster.ambush, eff.get("_shadow", 1.0)) > 1.0:
        k *= eff["from_shadow"]
    return k


def after_hit(c, caster, v, eff, dealt):
    if eff.get("arrow") and v.alive:
        n = eff.get("arrows", 1)                    # «В голову»: две стрелы подряд
        for _ in range(n):
            arrow_rider(c, caster, v, eff.get("arrow_mult", 1.0))
    if eff.get("mark_on_hit") and v.alive:
        mo = eff["mark_on_hit"]
        add_mark(c, v, mo["mark"], mo.get("stacks", 1), mo.get("duration", 6), caster)


# ---------- колчаны лучника ----------
#
# У лучника до трёх колчанов (u.quivers, выбор 1 из 2 на 1 / 6 / 11 уровне, на 15 — все сильнее). Стрелы
# чередуются: каждый выстрел (обычная атака или навык с "arrow": true) берёт следующий колчан по кругу.
# Числа стрел — доли силы навыков лучника (data/config.json "arrows"); полный Разгон — эффект ×2.

def arrow_owner(c, u):
    """Чьи стрелы несёт атака u: свои (лучник), хозяина (зеркальный клон) или лучника «Оперения отряда»."""
    if u.quivers:
        return u
    if u.owner is not None and getattr(u.owner, "quivers", None) and u.proto.get("mirror"):
        return u.owner
    fid = u.buff("fletch", None)
    if fid is not None:
        return next((v for v in c.units if v.id == fid and v.alive), None)
    return None


def next_arrow(u):
    if not u.quivers:
        return None
    a = u.quivers[u.arrow_i % len(u.quivers)]
    u.arrow_i += 1
    return a


def arrow_rider(c, src, t, mult=1.0, arrow=None, owner=None):
    """Стрела долетела до t: эффект колчана. src — кто стрелял (лечение вампирских — ему), owner — чьи колчаны и
    сила навыков (лучник)."""
    owner = owner or arrow_owner(c, src)
    if owner is None or not t.alive or t.obj:
        return
    arrow = arrow or next_arrow(owner)
    a = c.cfg["arrows"].get(arrow or "")
    if not a:
        return
    from sim import passives as PS
    if PS.arrow_mult(owner) > 1:                    # полный Разгон: эффект стрел двойной
        mult *= 2.0
    if owner.proto.get("quiver_boost"):             # 15 уровень: все колчаны сильнее
        mult *= c.cfg["arrows_boost"]
    sp = c.stat_k(owner, "sp", True) * mult
    c.gain(owner, "arrow")
    c.emit("arrow", unit=t, src=src, arrow=arrow)
    flat = c._flat
    c._flat = True                                  # числа уже от силы навыков: атрибут второй раз не умножать
    try:
        if a.get("dmg"):
            c.damage(t, a["dmg"] * sp, src, a.get("tag"), "spell")
        if a.get("tag") and t.alive:
            c.apply_status(t, a["tag"], src)
        if a.get("mark") and t.alive:
            add_mark(c, t, a["mark"], a.get("stacks", 1), a.get("duration", 5), owner)
        if a.get("bleed") and t.alive:
            c.add_buff(t, "bleed", round(a["bleed"] * sp, 1), a.get("duration", 4), src=src)
        if a.get("knockback") and t.alive and not t.boss:
            c.knockback(src.cell, t, a["knockback"], src)
        if a.get("interrupt") and t.alive:
            c._interrupt(t)
        if a.get("heal") and src.alive:
            c.heal(src, int(round(a["heal"] * sp)), owner)
        if a.get("shred") and t.alive:              # бронебойные: −1 брони за стрелу (до shred_max) на время
            cur = t.buff("armor_shred", 0)
            c.add_buff(t, "armor_shred", min(a["shred_max"], cur + a["shred"]), a.get("duration", 6))
        if a.get("blast"):                          # взрывные: урон всем врагам рядом с целью
            for v in c.units_in_radius(t.cell, a["blast"]):
                if v.alive and v is not t and src.is_enemy(v) and not v.obj:
                    c.damage(v, a["blast_dmg"] * sp, src, a.get("tag"), "spell")
        if a.get("jump"):                           # грозовые / отскакивающие: следующему врагу рядом
            near = sorted((v for v in c.alive() if src.is_enemy(v) and v is not t and not v.obj
                           and cheb(v.cell, t.cell) <= a["jump"]), key=lambda v: (cheb(v.cell, t.cell), v.id))
            if near:
                v = near[0]
                amount = a["jump_dmg"] * (c.stat_k(owner, "atk", True) * mult if a.get("jump_of") == "atk" else sp)
                c.emit("chain", src=t, dst=v, tag=a.get("tag"))
                c.damage(v, amount, src, a.get("tag"), "spell")
                if a.get("jump_tag") and v.alive:
                    c.apply_status(v, a["jump_tag"], src)
    finally:
        c._flat = flat


def basic_rider(c, u, t):
    if t.obj or not t.alive:
        return
    owner = arrow_owner(c, u)
    if owner is None:
        return
    if "all_arrows" in owner.buffs and owner is u:     # «Все стрелы»: каждая атака — всеми колчанами сразу
        for a in owner.quivers:
            arrow_rider(c, u, t, 1.0, a, owner)
        return
    arrow_rider(c, u, t, 1.0, None, owner)
    k = owner.proto.get("arrow_double")
    if k and owner is u and owner.arrow_i % int(k) == 0 and t.alive:    # «Колчан с секретом»: стрела дважды
        arrow_rider(c, u, t, 1.0, owner.quivers[(owner.arrow_i - 1) % len(owner.quivers)], owner)


# ---------- молнии и тотемы шамана ----------

def own_totems(c, u):
    return [s for s in c.units if s.alive and s.owner is u and s.proto.get("group") == "totem"]


def ball_lightning(c, caster, eff, center):
    """Шаровая молния: медленный шар по прямой; бьёт током каждого врага рядом с путём (каждого — один раз)."""
    cells = line_cells(caster.cell, tuple(center), eff.get("length", 6))
    if not cells:
        c.emit("fizzle", unit=caster, skill=None)
        return
    dmg = eff["amount"] * caster.power          # power — уже от силы навыков (of: sp)
    hit = []                                    # общий список задетых — данными (бой можно копировать)
    speed = eff.get("speed", 4.0)
    c.emit("ball_start", unit=caster, cells=cells, speed=speed)
    for i, p in enumerate(cells):
        t = round((i + 1) / speed, 2)
        c.delayed.append({"left": t, "total": t, "ball": (caster, p, dmg, eff.get("radius", 1), hit,
                                                          eff.get("stun", 0)), "tunit": None})


def ball_step(c, caster, pos, dmg, r, hit, stun):
    if not caster.alive:
        return
    c.emit("ball_step", pos=pos, src=caster)
    flat = c._flat
    c._flat = True
    try:
        for v in c.units_in_radius(pos, r):
            if v.alive and not v.obj and caster.is_enemy(v) and v.id not in hit:
                hit.append(v.id)
                c.emit("chain", src=caster, dst=v, tag="storm")
                c.damage(v, dmg, caster, "storm", "spell")
                if v.alive:
                    c.apply_status(v, "storm", caster)
                if stun and v.alive:
                    c.apply_stun(v, stun, "shock")
    finally:
        c._flat = flat


def storm_front(c, caster, eff):
    """Грозовой фронт: каждую секунду молния с неба бьёт врага рядом с шаманом и с каждым его тотемом."""
    dmg = eff["amount"] * caster.power
    for i in range(int(eff.get("duration", 8))):
        t = float(i + 1)
        c.delayed.append({"left": t, "total": t, "storm_tick": (caster, dmg, eff.get("radius", 2),
                                                                eff.get("strikes", 1)), "tunit": None})
    c.emit("storm_front", unit=caster, duration=eff.get("duration", 8))


def storm_tick(c, caster, dmg, r, strikes):
    if not caster.alive:
        return
    flat = c._flat
    c._flat = True
    try:
        for src in [caster] + own_totems(c, caster):
            foes = sorted((v for v in c.alive() if caster.is_enemy(v) and not v.obj and cheb(v.cell, src.cell) <= r),
                          key=lambda v: (v.hp, v.id))
            for v in foes[:strikes]:
                c.emit("sky_bolt", pos=v.cell, src=caster)
                c.damage(v, dmg, caster, "storm", "spell")
                if v.alive:
                    c.apply_status(v, "storm", caster)
    finally:
        c._flat = flat


def ancestors(c, caster, eff):
    """Предки: по тотему каждого своего вида вокруг шамана (сверх лимита), все тотемы неуязвимы."""
    kinds = []
    for sid in caster.skills:
        for e in caster.skill_defs[sid].get("effects", []):
            if e["type"] == "summon" and c.data.summons.get(e["unit"], {}).get("group") == "totem" \
                    and e["unit"] not in kinds:
                kinds.append(e["unit"])
    for unit in kinds or ["totem_storm"]:
        c.summon(caster, {"unit": unit, "extra": True, "power": eff.get("power", 1.0)}, caster.cell)
    for s in own_totems(c, caster):
        c.add_buff(s, "dmg_taken", 0.0, eff.get("guard", 6))
    c.emit("ancestors", unit=caster)


# ---------- заряды подрывника ----------
#
# Заряды: свои бочки и ящики (объекты с volatile), мины и пороховая дорожка (клетки с charge), липкие бомбы на врагах.
# Фитиль (кнопка F) рвёт их цепочкой от ближнего к дальнему за ~1 сек; граната и взрыв заряда поджигают соседние.

def own_charges(c, u, armed=False):
    """[(вид, ссылка, клетка)] — заряды подрывника на поле. armed — только те, что ещё не горят (фитиль не дошёл)."""
    lit = set()
    if armed:
        lit = {(d["charge"][1], d["charge"][2] if d["charge"][1] == "cell" else d["charge"][2].id)
               for d in c.delayed if d.get("charge") and d["charge"][0] is u}
    out = [("obj", o, o.cell) for o in c.units
           if o.alive and o.obj and o.owner is u and (o.obj.get("volatile") is not None or o.obj.get("on_ignite"))
           and not (armed and o.fuse > 0)]
    out += [("cell", p, p) for p, cell in c.grid.cells.items()
            if cell.hazard in ("mine", "powder") and cell.hazard_owner is u and ("cell", p) not in lit]
    out += [("bomb", v, v.cell) for v in c.units if v.alive and "bomb" in v.marks and v.marks["bomb"]["src"] is u
            and ("bomb", v.id) not in lit]
    return out


def fuse_chain(c, caster, eff):
    ch = sorted(own_charges(c, caster, armed=True), key=lambda x: (cheb(x[2], caster.cell), x[2]))
    if not ch:
        c.emit("fizzle", unit=caster, skill=None)
        return
    first, span = eff.get("first", 0.3), eff.get("span", 0.7)
    n = len(ch)
    c.emit("fuse_chain", unit=caster, cells=[x[2] for x in ch], time=first + span)
    for i, (kind, ref, cell) in enumerate(ch):
        t = round(first + (span * i / (n - 1) if n > 1 else 0.0), 2)
        if kind == "obj":
            ref.fuse = min(ref.fuse, t) if ref.fuse > 0 else t
            ref.igniter = caster
            c.emit("fuse", unit=ref)
        else:
            c.delayed.append({"left": t, "total": t, "charge": (caster, kind, ref), "tunit": None})


def blow_charge(c, caster, kind, ref):
    """Заряд в клетке (мина, порох) или липкая бомба — взрыв от фитиля / соседнего взрыва."""
    if kind == "cell":
        cell = c.grid.get(ref)
        if cell is None or cell.hazard not in ("mine", "powder") or cell.hazard_owner is not caster:
            return
        ch = cell.charge or {"dmg": c.cfg["hazards"]["mine"]["trigger"]["damage"] * cell.mine_mult, "r": 1}
        was = cell.hazard
        if was == "mine":                         # мина от Фитиля рвётся вокруг себя, а не только под ногой
            ch = dict(ch, r=max(1, ch.get("r", 0)))
        cell.hazard, cell.hazard_owner, cell.charge = None, None, None
        if was == "powder":                       # дорожка прогорает: огонь на клетке (по маслу — горящее масло)
            if ch.get("oil"):
                cell.hazard = "oil"
                c.ignite_oil(ref)
            else:
                cell.hazard, cell.hazard_time, cell.hazard_team = "fire", 3.0, caster.team
                cell.blaze = False
        blow_cell(c, caster, ref, ch, "fire")
    elif kind == "bomb" and ref.alive and "bomb" in ref.marks and ref.marks["bomb"]["src"] is caster:
        consume_mark(c, ref, "bomb")
        if caster is not None:
            c.gain(caster, "blast")


def blow_cell(c, caster, pos, ch, tag=None, first=None):
    """Взрыв заряда в клетке: урон врагам в радиусе (от силы навыков героя), оглушение, соседние заряды — следом."""
    c.emit("detonate", pos=pos, src=caster)
    if caster is not None:
        c.gain(caster, "blast")
    if tag == "fire":                             # огненный взрыв поджигает масло в радиусе
        for p in c.grid.in_radius(pos, ch.get("r", 0)):
            if c.grid.get(p) is not None and c.grid.get(p).hazard == "oil":
                c.ignite_oil(p)
    flat = c._flat
    c._flat = True
    try:
        for v in c.units_in_radius(pos, ch.get("r", 0)):
            if v.alive and not v.obj and (caster is None or caster.is_enemy(v)):
                c.damage(v, ch["dmg"], caster, tag, "reaction")
                if ch.get("stun") and v.alive and v is not first:
                    c.apply_stun(v, ch["stun"], "stun")
    finally:
        c._flat = flat
    if caster is not None and ch.get("chain", True):
        ignite_charges(c, caster, pos, 1, skip=pos)


def ignite_charges(c, caster, center, radius, skip=None):
    """Огонь рядом: свои бочки, мины, порох и бомбы в радиусе — взрываются (цепная реакция)."""
    for kind, ref, cell in own_charges(c, caster):
        if cell == skip or cheb(cell, center) > radius:
            continue
        if kind == "obj":
            if ref.fuse <= 0 or ref.fuse > 0.15:
                ref.fuse, ref.igniter = 0.15, caster
        else:
            c.delayed.append({"left": 0.12, "total": 0.12, "charge": (caster, kind, ref), "tunit": None})


def line_cells(a, b, length):
    """Клетки по прямой от a к b (без a), не длиннее length."""
    (x0, y0), (x1, y1) = a, b
    n = max(abs(x1 - x0), abs(y1 - y0))
    if n == 0:
        return []
    out = []
    for i in range(1, max(n, length) + 1):
        p = (round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n))
        if p not in out:
            out.append(p)
        if len(out) >= length:
            break
    return out


def powder_trail(c, caster, eff, center):
    """Пороховая дорожка: линия пороха от подрывника к клетке; Фитиль или огонь бегут по ней, взрывая соседей."""
    k = c.stat_k(caster, "sp", True) * eff.get("_powder", 1.0)
    laid = 0
    for p in line_cells(caster.cell, tuple(center), eff.get("length", 5)):
        cell = c.grid.get(p)
        if cell is None or not cell.passable or cell.terrain == "water" or cell.hazard in ("mine", "fire"):
            continue
        oil = cell.hazard == "oil"                  # порох по маслу: прогорит горящим маслом
        cell.hazard, cell.hazard_time = "powder", eff.get("duration", 20)
        cell.hazard_team, cell.hazard_owner = caster.team, caster
        cell.charge = {"dmg": eff["blast"] * k, "r": eff.get("blast_r", 1), "stun": eff.get("stun"), "oil": oil}
        laid += 1
    if not laid:
        c.emit("fizzle", unit=caster, skill=None)
    else:
        c.emit("powder_trail", unit=caster, center=tuple(center))
        if eff.get("lit"):                        # ветка «Огненная стена»: дорожка сразу вспыхивает
            fuse_chain(c, caster, {"first": 0.2, "span": 0.5})


def barrel_rain(c, caster, eff, center):
    """Дождь бочек: на врагов в радиусе падают бочки и сразу рвутся (без подготовки)."""
    r = eff.get("radius", 3)
    foes = sorted((v for v in c.alive() if caster.is_enemy(v) and not v.obj and cheb(v.cell, center) <= r),
                  key=lambda v: (cheb(v.cell, center), v.id))
    cells = [v.cell for v in foes]
    free = [p for p in c.grid.in_radius(center, r) if c.grid.get(p).passable]
    n = eff.get("barrels", 5)
    while len(cells) < n and free:
        cells.append(free[(len(cells) * 7) % len(free)])
    dmg = eff["blast"] * c.stat_k(caster, "sp", True)
    for i, p in enumerate(cells[:n]):
        t = round(0.25 + 0.15 * i, 2)
        c.delayed.append({"left": t, "total": t, "rain_barrel": (caster, tuple(p), dmg, eff.get("blast_r", 1)),
                          "tunit": None})
    c.emit("barrel_rain", unit=caster, cells=[tuple(p) for p in cells[:n]])


def rain_barrel_land(c, caster, pos, dmg, r):
    if not caster.alive:
        return
    cell = c.grid.get(pos)
    if cell is not None and cell.passable and cell.terrain != "water" and not cell.hazard:
        cell.hazard, cell.hazard_time, cell.hazard_team = "fire", 3.0, caster.team
    blow_cell(c, caster, pos, {"dmg": dmg, "r": r}, "fire")


def reactive_armor(c, caster, eff):
    """Реактивная броня: отряду щит от здоровья подрывника; удар по союзнику рвёт на нём заряд (раз в секунду)."""
    shield = int(round(caster.max_hp * eff["shield_hp"]))
    dmg = eff["blast"] * c.stat_k(caster, "sp", True)
    for v in c.alive(caster.team):
        if v.obj or v.summon:
            continue
        v.shield, v.shield_time, v.shield_src = max(v.shield, shield), eff["duration"], c.credit(caster)
        c.emit("shield", unit=v, amount=shield)
        c.add_buff(v, "reactive", round(dmg, 1), eff["duration"])
        v.reactive_src = caster
        v.reactive_t = 0.0


def reactive_blast(c, target, attacker):
    target.reactive_t = c.time + 1.0
    src = getattr(target, "reactive_src", None)
    c.emit("detonate", pos=attacker.cell, src=src)
    flat = c._flat
    c._flat = True
    try:
        c.damage(attacker, target.buff("reactive", 0), src if src is not None and src.alive else None, "fire",
                 "reaction")
    finally:
        c._flat = flat
    if attacker.alive and not attacker.boss:
        c.knockback(target.cell, attacker, 1, target)


# ---------- выстрелы лучника ----------

def _foes_by_dist(c, u, cell, reach=99):
    return sorted((v for v in c.alive() if u.is_enemy(v) and not v.obj and cheb(v.cell, cell) <= reach),
                  key=lambda v: (cheb(v.cell, cell), v.hp, v.id))


def _shot_flight(c, u, t):
    h = c.cfg.get("hit") if c.hit_timing else None
    if not h:
        return 0.0
    sp = h["attack_speed"]
    speed = sp.get(u.proto_id) or sp.get("ranged", 10.0)
    return round(min(h["max"], max(0.06, cheb(u.cell, t.cell) / speed)), 2)


def fire_shot(c, u, t, shot, extra=None):
    """Стрела вылетает (видна как выстрел); долетит через полёт — land_shot."""
    if not u.alive or not t.alive:
        return
    flight = _shot_flight(c, u, t)
    c.emit("attack", src=u, dst=t, kind="ranged", tag=None, hit=flight)
    if flight > 0:
        c.delayed.append({"left": flight, "total": flight, "shot_hit": (u, t, shot, extra), "tunit": None})
    else:
        land_shot(c, u, t, shot, extra)


def land_shot(c, u, t, shot, extra=None):
    if not t.alive:
        return
    c.apply_effects(u, [shot], t.cell, t)
    extra = extra or {}
    if t.alive and extra.get("interrupt"):
        c._interrupt(t)
    if t.alive and extra.get("stun"):
        c.apply_stun(t, extra["stun"])


def barrage(c, caster, eff, tunit):
    """Шквал (на себя): очередь стрел в свою цель — текущую или ближайшего врага в досягаемости; веер — в разных
    врагов рядом с ней."""
    reach = eff.get("reach", 5)
    if tunit is None or tunit is caster or not tunit.alive:
        cur = caster.order.get("target") if caster.order and caster.order["type"] == "attack" else caster.last_target
        if cur is not None and cur.alive and caster.is_enemy(cur) and cheb(cur.cell, caster.cell) <= reach:
            tunit = cur
        else:
            near = _foes_by_dist(c, caster, caster.cell, reach)
            tunit = near[0] if near else None
    if tunit is None:
        c.emit("fizzle", unit=caster, skill=None)
        return
    shadow = max(caster.ambush, eff.get("_shadow", 1.0))
    n, gap = eff.get("shots", 3), eff.get("gap", 0.16)
    if shadow > 1.0 and eff.get("shadow_shots"):
        n = eff["shadow_shots"]                       # из тени — дополнительный дротик
    targets = [tunit]
    if eff.get("spread"):
        targets = [tunit] + [v for v in _foes_by_dist(c, caster, tunit.cell, eff["spread"]) if v is not tunit]
    shot = dict(eff["shot"], _shadow=shadow)
    for i in range(n):
        t = targets[i % len(targets)]
        extra = {}
        if i == n - 1 and eff.get("last_interrupt"):
            extra = {"interrupt": True, "stun": eff.get("last_stun", 0)}
        if i == 0:
            fire_shot(c, caster, t, shot, extra)
        else:
            c.delayed.append({"left": i * gap, "total": i * gap, "shot": (caster, t, shot, extra),
                              "tunit": None})


def vault(c, caster, eff):
    """Отскок: прыжок прочь от ближайшего врага (до cells клеток), сеть на старом месте, выстрел(ы)."""
    foes = _foes_by_dist(c, caster, caster.cell)
    if not foes:
        c.emit("fizzle", unit=caster, skill=None)
        return
    near = foes[0]
    old = caster.cell
    best, best_k = None, None
    for p in c.grid.in_radius(old, eff.get("cells", 3)):
        if p == old or not c.is_free(p):
            continue
        k = (min(cheb(p, f.cell) for f in foes), cheb(p, near.cell), -cheb(p, old))
        if best_k is None or k > best_k:
            best, best_k = p, k
    if best is not None and best_k[0] > min(cheb(old, f.cell) for f in foes):
        c.emit("leap", unit=caster, src=old, dst=best)
        c._place(caster, best, 0.25)
    if eff.get("net"):
        for v in _foes_by_dist(c, caster, old, 1):
            c.apply_stun(v, eff["net"], "net")
    for t in _foes_by_dist(c, caster, caster.cell)[:eff.get("targets", 1)]:
        fire_shot(c, caster, t, eff["shot"])


def shackle(c, caster, eff, tunit):
    """Связывающая стрела: за целью (по линии выстрела) враг, стена или укрытие — оба прибиты; иначе замедление."""
    if tunit is None or not tunit.alive:
        return
    dx = (tunit.cell[0] > caster.cell[0]) - (tunit.cell[0] < caster.cell[0])
    dy = (tunit.cell[1] > caster.cell[1]) - (tunit.cell[1] < caster.cell[1])
    anchor, other = False, None
    p = tunit.cell
    for _ in range(eff.get("reach", 2)):
        p = (p[0] + dx, p[1] + dy)
        if not c.grid.in_bounds(p) or not c.grid.get(p).passable:
            anchor = True
            break
        w = c.unit_at(p)
        if w is not None and w.alive:
            anchor = True
            if caster.is_enemy(w) and not w.obj:
                other = w
            break
    if anchor:
        c.emit("shackle", unit=tunit, src=caster, other=other)
        c.apply_stun(tunit, eff.get("stun", 2.5), "net")
        if other is not None:
            c.apply_stun(other, eff.get("stun", 2.5), "net")
    else:
        c.add_buff(tunit, "slow", 1.6, eff.get("slow", 2.0))


def fletch(c, caster, eff):
    """Оперение отряда: атаки союзников несут стрелы лучника (по очереди из его колчанов) и сильнее."""
    for v in c.alive(caster.team):
        if v.obj or (v.summon and not v.atk_damage):
            continue
        if v is not caster:
            c.add_buff(v, "fletch", caster.id, eff["duration"])
        c.add_buff(v, "atk_mult", eff.get("atk_mult", 1.25), eff["duration"])
        if eff.get("atk_speed"):
            c.add_buff(v, "atk_speed", eff["atk_speed"], eff["duration"])


# ---------- проверки навыка ----------

LIVE = {
    "fire_cells": lambda c, u: sum(1 for p in c.grid.in_radius(u.cell, 6) if c.grid.get(p).hazard == "fire"),
    "totems": lambda c, u: len(own(c, u, totem=True)),
    "corpses": lambda c, u: len(c.corpses),
    "song_notes": lambda c, u: u.song["notes"] if u.song else 0,
    "charges": lambda c, u: len(own_charges(c, u)),
    "traps": lambda c, u: sum(1 for cell in c.grid.cells.values()
                              if cell.hazard in ("snare", "bear_trap") and cell.hazard_owner is u),
    "cold": lambda c, u: sum(1 for v in c.units if v.alive and u.is_enemy(v) and ("cold" in v.marks or
                                                                                   (v.stun > 0 and v.stun_look == "freeze"))),
    "density": lambda c, u: max([density(c, v, u) for v in c.units if v.alive and not v.obj and u.is_enemy(v)] + [0]),
    "tags": lambda c, u: max([len(v.statuses) for v in c.units if v.alive and u.is_enemy(v)] + [0]),
    "hp_lost": lambda c, u: int(100 * (1 - u.hp / max(1, u.max_hp))),
    "tethers": lambda c, u: sum(1 for v in c.units if v.alive and v.tethered_by is u),
    "gauge": lambda c, u: int(u.pp),
    "wounded": lambda c, u: sum(1 for v in c.units if v.alive and not v.obj and u.is_enemy(v) and v.hp < v.max_hp * 0.5),
    "melody": lambda c, u: 1 if u.last_melody else 0,
}


def ult_progress(c, u, sk):
    """Условие ультимейта: (есть, нужно, подпись). count — события за бой, live — состояние поля сейчас."""
    cond = sk.get("ult_cond")
    if not cond:
        return None
    need = cond["need"]
    if "count" in cond:
        have = sum(u.ult_count.get(e, 0) for e in cond["count"].split("|"))
    else:
        have = LIVE[cond["live"]](c, u)
    return min(have, need), need, cond["desc"]


def check(c, u, sk, target):
    """Дополнительные условия навыков механик. Возвращает текст отказа или None."""
    pr = ult_progress(c, u, sk)
    if pr and pr[0] < pr[1]:
        return f"Ультимейт: {pr[2]} ({pr[0]}/{pr[1]})"
    core = bool((u.passive or {}).get("core"))     # шкала-ресурс — у героев с пассивкой-основой
    cost = sk.get("gauge_cost", 0)
    if cost and core and u.gauge and u.pp < cost:
        return f"Мало: {u.gauge.get('name', 'шкала')}"
    if sk.get("gauge_spend") == "all" and core and u.gauge and u.pp < sk.get("gauge_min", 1):
        return f"Пусто: {u.gauge.get('name', 'шкала')}"
    form = sk.get("form")
    if form == "human" and u.form is not None:
        return "Только в облике человека"
    if form and form != "human" and u.form != form:
        return "Нужен облик: " + c.data.classes.get(u.proto_id, {}).get("forms", {}).get(form, {}).get("name", form)
    if sk.get("needs_shadow") and "stealth" not in u.buffs:
        return "Только из тени"
    need = sk.get("needs_mark")
    if need and (not hasattr(target, "marks") or need not in target.marks):
        return "Нужна метка"
    if sk.get("needs_totem") and not own(c, u, totem=True):
        return "Нет тотемов"
    if sk.get("needs_banner") and not own(c, u, proto="banner"):
        return "Нет знамени"
    return None


def spend(c, u, sk):
    """Траты шкалы при применении. Возвращает потраченные деления (для per_gauge)."""
    if not u.gauge or not (u.passive or {}).get("core"):
        return 0
    n = 0
    if sk.get("gauge_spend") == "all":
        n = int(u.pp)
    elif sk.get("gauge_cost"):
        n = sk["gauge_cost"]
    if n:
        u.pp = max(0, u.pp - n)
        c.emit("gauge", unit=u, event="spend")
    if sk.get("gauge_gain"):
        u.pp = min(u.pp_max, u.pp + sk["gauge_gain"])
        c.emit("gauge", unit=u, event="gain")
    cond = sk.get("ult_cond")
    if cond and "count" in cond:              # условие-счётчик тратится: копить заново
        for e in cond["count"].split("|"):
            u.ult_count[e] = 0
    return n


def own(c, u, totem=False, proto=None):
    return [s for s in c.units if s.alive and s.owner is u and
            ((totem and s.proto_id.startswith("totem")) or (proto and s.proto_id == proto))]


# ---------- зоны ----------

def tick_zones(c, dt):
    for z in list(c.zones):
        z["left"] -= dt
        anchor = z.get("anchor")
        if z["left"] <= 0 or (anchor is not None and not anchor.alive) or not z["caster"].alive:
            c.zones.remove(z)
            continue
        z["t"] += dt
        if z["t"] >= z["every"]:
            z["t"] -= z["every"]
            center = anchor.cell if anchor is not None else z["center"]
            c.emit("zone_pulse", center=center, radius=z["radius"], src=z["caster"], kind=z.get("kind"))
            c.apply_effects(z["caster"], z["effects"], center, None)


# ---------- особые эффекты ----------

def special(c, caster, eff, center, tunit):
    t = eff["type"]
    center = tuple(center)
    if t == "barrage":
        barrage(c, caster, eff, tunit)
    elif t == "ball":
        ball_lightning(c, caster, eff, center)
    elif t == "storm_front":
        storm_front(c, caster, eff)
    elif t == "ancestors":
        ancestors(c, caster, eff)
    elif t == "trail":
        powder_trail(c, caster, eff, center)
    elif t == "ignite_charges":
        ignite_charges(c, caster, center, eff.get("radius", 1))
    elif t == "barrel_rain":
        barrel_rain(c, caster, eff, center)
    elif t == "reactive":
        reactive_armor(c, caster, eff)
    elif t == "vault":
        vault(c, caster, eff)
    elif t == "shackle":
        shackle(c, caster, eff, tunit)
    elif t == "fletch":
        fletch(c, caster, eff)
    elif t == "mark":
        aff = eff.get("affects", "enemies")
        for v in c._select(caster, center, eff.get("radius", 0), aff, tunit):
            if eff.get("if_mark") and eff["if_mark"] not in v.marks:
                continue
            if not v.obj:
                add_mark(c, v, eff["mark"], eff.get("stacks", 1), eff.get("duration", 6), caster)
                if eff.get("_powder") and eff["mark"] in v.marks:      # бомба с Порохом — ×2, без — ×0.6
                    v.marks[eff["mark"]]["mult"] = eff["_powder"]
                if eff.get("on_expire") and eff["mark"] in v.marks:    # ветка навыка: свой взрыв метки
                    v.marks[eff["mark"]]["on_expire"] = eff["on_expire"]
    elif t == "zone":
        z = {"center": center, "radius": eff.get("radius", 1), "left": eff["duration"], "every": eff.get("every", 1.0),
             "t": eff.get("every", 1.0) if eff.get("now") else 0.0, "effects": eff["effects"], "caster": caster,
             "kind": eff.get("kind"), "anchor": None}
        if eff.get("anchor") == "target" and tunit is not None:
            z["anchor"] = tunit
        c.zones.append(z)
        c.emit("zone", center=center, radius=z["radius"], src=caster, kind=z["kind"], duration=eff["duration"])
    elif t == "totem_pulse":                       # все тотемы срабатывают сразу
        tot = own(c, caster, totem=True)
        if not tot:
            c.emit("fizzle", unit=caster, skill=None)
        for s in tot:
            if s.aura:
                k = eff.get("mult", 1.0)
                effs = [dict(e, amount=e["amount"] * k) if "amount" in e else e for e in s.aura["effects"]]
                c.emit("aura", unit=s, radius=s.aura.get("radius", 0))
                c.apply_effects(s, effs, s.cell)
            elif s.atk_damage > 0:                 # тотем-стрелок: сразу разряд в ближайшего врага
                foes = [v for v in c.units if v.alive and not v.obj and s.is_enemy(v)
                        and cheb(v.cell, s.cell) <= s.atk_range]
                if foes:
                    t = min(foes, key=lambda v: cheb(v.cell, s.cell))
                    for _ in range(max(1, round(eff.get("mult", 1.0)))):
                        s.attack_timer = 0.0
                        c._basic_attack(s, t)
            if eff.get("refresh"):
                s.life = max(s.life or 0, eff["refresh"])
    elif t == "totem_move":                        # дух переходит: ближайший к точке тотем (или знамя) — в точку
        tot = own(c, caster, proto=eff["proto"]) if eff.get("proto") else own(c, caster, totem=True)
        if not tot or not c.is_free(center):
            c.emit("fizzle", unit=caster, skill=None)
            return
        s = min(tot, key=lambda s: cheb(s.cell, center))
        src = s.cell
        c._place(s, center, 0.15)
        c.emit("rewind", unit=s, src=src, dst=center)
        if eff.get("pulse") and s.aura:
            c.apply_effects(s, s.aura["effects"], s.cell)
    elif t == "totem_link":                        # молния между тотемами: всех врагов на линиях
        tot = own(c, caster, totem=True) + ([caster] if eff.get("with_self") else [])
        hit = set()
        for i, a in enumerate(tot):
            for b in tot[i + 1:]:
                c.emit("link", src=a, dst=b, color=(170, 190, 255))
                for v in _on_segment(c, a.cell, b.cell):
                    if caster.is_enemy(v) and v not in hit and not v.obj:
                        hit.add(v)
                        c.damage(v, eff["amount"] * caster.power, caster, eff.get("tag"), "spell")
        if len(tot) < 2:
            c.emit("fizzle", unit=caster, skill=None)
    elif t == "shadow_dance":                      # танец теней: прыжок к цели, удар; убил — к следующей
        _shadow_dance(c, caster, eff, tunit)
    elif t == "trap_pull":                         # загон: каждый капкан тянет ближайшего врага к себе
        traps = [p for p, cell in c.grid.cells.items()
                 if cell.hazard in ("snare", "bear_trap") and cell.hazard_team == caster.team]
        if not traps:
            c.emit("fizzle", unit=caster, skill=None)
        for p in traps:
            foes = [v for v in c.units if v.alive and not v.obj and caster.is_enemy(v) and not v.boss
                    and 0 < cheb(v.cell, p) <= eff.get("radius", 3)]
            if foes:
                v = min(foes, key=lambda v: cheb(v.cell, p))
                from sim import movement as M
                M.forced_move(c, v, cheb(v.cell, p), M.toward(p, 0), caster, "pull")
    elif t == "time_theft":                        # кража времени: враг теряет время, хрономант его получает
        if tunit is None or not tunit.alive:
            return
        for sid in tunit.skills:
            tunit.cooldowns[sid] = tunit.cooldowns.get(sid, 0) + eff.get("cooldown", 3)
        tunit.attack_timer = max(tunit.attack_timer, tunit.atk_cd)
        if tunit.cast:
            tunit.cast["left"] += eff.get("cast", 1.0)
        caster.ap = min(caster.ap_max, caster.ap + eff.get("ap", 1))
        c.add_buff(caster, "ap_rate", eff.get("ap_rate", 0.6), eff.get("duration", 4))
        c.emit("rewind", unit=tunit, src=tunit.cell, dst=tunit.cell)
    elif t == "detonate_charges":                  # подрыв: свои бочки, мины и липкие бомбы рвутся
        _detonate_charges(c, caster, eff, center)
    elif t == "song_notes":                        # соло: ноты в свою песню
        if caster.song:
            caster.song["notes"] += eff.get("notes", 2)
            c.emit("note", unit=caster)
        else:
            c.emit("fizzle", unit=caster, skill=None)
    elif t == "inferno":                           # инферно: огонь не гаснет, Вспышка его не снимает
        c.add_buff(caster, "inferno", 1, eff["duration"])
        for p in c.grid.in_radius(caster.cell, eff.get("radius", 6)):
            cell = c.grid.get(p)
            if cell.hazard == "fire":
                cell.hazard_time = max(cell.hazard_time, eff["duration"])
    elif t == "consume_fire":                      # вдохнуть пламя: огонь вокруг гаснет, маг получает щит и жар
        n = 0
        for p in c.grid.in_radius(caster.cell, eff.get("radius", 2)):
            cell = c.grid.get(p)
            if cell.hazard == "fire":
                cell.hazard = None
                n += 1
        if not n:
            c.emit("fizzle", unit=caster, skill=None)
            return
        caster.shield += int(eff.get("shield", 8) * n * caster.power)
        caster.shield_time = max(caster.shield_time, 8.0)
        c.emit("shield", unit=caster, amount=caster.shield)
        if caster.gauge:
            caster.pp = min(caster.pp_max, caster.pp + min(n, eff.get("gauge", 3)))
    elif t == "bleed_feast":                       # пир: кровь врагов вокруг — в берсерка
        n = 0
        for v in c.units_in_radius(caster.cell, eff.get("radius", 2)):
            if caster.is_enemy(v) and "bleed" in v.statuses:
                dot = v.dots.get("bleed")
                left = (dot["dps"] * dot["stacks"] * dot["left"]) if dot else 0.0
                c._clear_dot(v, "bleed")
                c.damage(v, left * eff.get("burst", 1.0), caster, None, "reaction")
                c.heal(caster, int(left * eff.get("heal", 0.6)))
                c.emit("link", src=v, dst=caster, color=(220, 40, 50))
                n += 1
        if not n:
            c.emit("fizzle", unit=caster, skill=None)
    elif t == "raise_all":                         # последний призыв: все трупы встают
        corpses = list(c.corpses)
        if not corpses:
            c.emit("fizzle", unit=caster, skill=None)
        for b in corpses[:eff.get("limit", 6)]:
            c.corpses.remove(b)
            c.emit("corpse_use", pos=b["cell"], src=caster, do="raise")
            c.summon(caster, {"unit": eff.get("unit", "skeleton_minion"), "duration": eff.get("duration", 12),
                              "limit": 99}, b["cell"])


    elif t == "song_tempo":                        # быстрее темп: такты песни чаще
        if not caster.song:
            c.emit("fizzle", unit=caster, skill=None)
            return
        caster.song["every"] = max(0.6, caster.song["every"] * eff.get("mult", 0.5))
        caster.song["notes"] += eff.get("notes", 0)
        c.emit("note", unit=caster)
    elif t == "song_finale":                       # крещендо: финал прямо сейчас, ноты ×mult
        if not caster.song:
            c.emit("fizzle", unit=caster, skill=None)
            return
        caster.song["notes"] = int(round((caster.song["notes"] + eff.get("notes", 0)) * eff.get("mult", 1.5)))
        caster.song["beat"] = caster.song["beats"] - 1
        caster.song["t"] = caster.song["every"]
        c._song_update(caster, 0.0)
    elif t == "corpse_pulse":                      # гниль: каждый труп вокруг бьёт врагов рядом с собой
        near = [b for b in c.corpses if cheb(b["cell"], caster.cell) <= eff.get("radius", 6)]
        if not near:
            c.emit("fizzle", unit=caster, skill=None)
        for b in near:
            c.emit("corpse_use", pos=b["cell"], src=caster, do="cloud")
            for v in c.units_in_radius(b["cell"], eff.get("blast", 1)):
                if caster.is_enemy(v) and not v.obj:
                    c.damage(v, eff["amount"] * caster.power, caster, eff.get("tag"), "spell")
    elif t == "reagent_area":                      # философский камень: реактив по каждому врагу в площади
        any_hit = False
        for v in c.units_in_radius(center, eff.get("radius", 2)):
            if caster.is_enemy(v) and not v.obj and v.statuses:
                any_hit = True
                from sim import passives as PS
                rk = 1 + PS.core(caster)["reagent"] * caster.pp if PS.kind(caster) == "recipe" else 1.0
                c.emit("reagent", unit=v, tags=list(v.statuses))
                c.damage(v, eff["per_tag"] * len(v.statuses) * caster.power * rk, caster, None, "spell")
        if not any_hit:
            c.emit("fizzle", unit=caster, skill=None)
    elif t == "tether_all":                        # сеть душ: нити ко всем союзникам рядом
        allies = [v for v in c._select(caster, caster.cell, eff.get("radius", 3), "allies", None)
                  if v is not caster and not v.obj and not v.summon][:eff.get("limit", 3)]
        if not allies:
            c.emit("fizzle", unit=caster, skill=None)
        for v in allies:
            v.tethered_by, v.tether_time = caster, eff["duration"]
            if eff.get("regen"):
                c.add_buff(v, "regen", eff["regen"], eff["duration"])
            c.emit("tether", unit=v, src=caster)
    elif t == "tether_heal":                       # общая жизнь: лечение каждому на нити и себе
        tied = [v for v in c.units if v.alive and v.tethered_by is caster]
        if not tied:
            c.emit("fizzle", unit=caster, skill=None)
            return
        for v in tied + [caster]:
            c.heal(v, int(round(eff["amount"] * caster.power)))
            if v is not caster:
                c.emit("link", src=caster, dst=v, color=(150, 230, 255))
    elif t == "cut_tethers":                       # перерезать нити: вспышка у каждого на нити
        tied = [v for v in c.units if v.alive and v.tethered_by is caster]
        if not tied:
            c.emit("fizzle", unit=caster, skill=None)
            return
        for v in tied:
            v.tethered_by = None
            c.heal(v, int(round(eff.get("heal", 20) * caster.power)))
            c.emit("link", src=caster, dst=v, color=(150, 230, 255))
            for w in c.units_in_radius(v.cell, eff.get("blast", 1)):
                if caster.is_enemy(w) and not w.obj:
                    c.damage(w, eff.get("amount", 18) * caster.power, caster, None, "spell")
    elif t == "terrain_wave":                      # земная волна: каждый враг в площади — по клетке под ним
        foes = [v for v in c.units_in_radius(center, eff.get("radius", 1)) if caster.is_enemy(v) and not v.obj]
        if not foes:
            c.emit("fizzle", unit=caster, skill=None)
        for v in foes:
            ground = c.grid.get(v.cell).terrain
            effs = eff["by"].get(ground) or eff["by"].get("default", [])
            c.emit("terrain_cast", unit=caster, ground=ground)
            c.apply_effects(caster, [dict(e, radius=0) for e in effs], v.cell, v)


    elif t == "note":                              # бард: нота в мелодию
        play_note(c, caster, eff["note"])
    elif t == "finale":                            # финал: последняя мелодия ещё раз, сильнее
        if not caster.last_melody:
            c.emit("fizzle", unit=caster, skill=None)
            return
        sk = c.data.skills[caster.last_melody]
        c.emit("melody", unit=caster, skill=caster.last_melody, name=sk["name"], finale=True)
        c.log(f"{caster.name}: финал — «{sk['name']}» ×{eff.get('mult', 2.0):g}", (255, 190, 230))
        c.apply_effects(caster, [_scaled(e, eff.get("mult", 2.0)) for e in sk["effects"]], caster.cell, caster)


def known_melodies(c, u):
    """Мелодии барда: открытые уровнем (proto.melodies) или все из пула класса."""
    ids = u.proto.get("melodies")
    if ids is None:
        pool = c.data.story_progression["classes"].get(u.proto_id, {}).get("skills", [])
        ids = [e["id"] for e in pool if not e.get("ult")]
    return [s for s in ids if s in c.data.skills and c.data.skills[s].get("melody")]


def notes_of_unit(c, u):
    """Ноты барда в бою по порядку Q, W, E: навыки с эффектом «note» (пусто — не бард)."""
    out = {}
    for sid in u.skills:
        for e in u.skill_defs[sid]["effects"]:
            if e["type"] == "note":
                out[e["note"]] = sid
    return [out[k] for k in "QWE" if k in out] if len(out) >= 3 else []


def play_note(c, u, note):
    """Нота в строку; последние три ноты — мелодия, если такая известна."""
    u.notes = (u.notes + [note])[-3:]
    c.emit("note_play", unit=u, note=note, notes=list(u.notes))
    seq = "".join(u.notes)
    for sid in known_melodies(c, u):
        sk = c.data.skills[sid]
        if sk["melody"] == seq:
            u.last_melody = sid
            u.notes = []
            c.emit("melody", unit=u, skill=sid, name=sk["name"], finale=False)
            c.log(f"{u.name}: мелодия «{sk['name']}»", (255, 190, 230))
            c.apply_effects(u, sk["effects"], u.cell, u)
            return


def _scaled(e, k):
    e = dict(e)
    for key in ("amount", "pct"):
        if key in e:
            e[key] = e[key] * k
    if e.get("type") in ("stun", "sleep", "buff") and "duration" in e:
        e["duration"] = e["duration"] * (1 + (k - 1) * 0.5)
    return e


def command(c, u, t):
    """Тактик вместо удара: ближайший к цели союзник бьёт её сразу (у знамени — дважды)."""
    p = u.passive or {}
    allies = [a for a in c.units if a.alive and a.team == u.team and a is not u and not a.obj and not a.static
              and a.atk_damage > 0 and cheb(a.cell, u.cell) <= p.get("reach", 5)
              and (a.passive or {}).get("core") != "commander"]
    able = [a for a in allies if cheb(a.cell, t.cell) <= c.reach(a)]
    if not able:
        c.emit("order", unit=u, src=u, name="Нет бойца у цели")
        return
    a = min(able, key=lambda a: cheb(a.cell, t.cell))
    n = 2 if banner_near(c, a) else 1
    c.emit("order", unit=a, src=u, name="Приказ!" if n == 1 else "Приказ у знамени!")
    c.emit("link", src=u, dst=a, color=(240, 200, 90))
    for _ in range(n):
        a.attack_timer = 0.0
        c._basic_attack(a, t)
    c.gain(u, "order")


def _on_segment(c, a, b):
    n = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
    cells = {(round(a[0] + (b[0] - a[0]) * i / n), round(a[1] + (b[1] - a[1]) * i / n)) for i in range(1, n)} \
        if n > 1 else set()
    return [v for v in c.units if v.alive and v.cell in cells]


def _shadow_dance(c, caster, eff, first):
    target, jumps = first, eff.get("jumps", 4)
    done = set()
    while target is not None and target.alive and jumps > 0:
        done.add(target)
        if not c._leap_next_to(caster, target):
            break
        amount = eff["amount"] * caster.power
        if c.exposed(target, caster) or caster.ambush > 1.0:
            amount *= eff.get("backstab", 1.5)
            c.emit("backstab", unit=target, src=caster)
        c.damage(target, amount, caster, None, "melee")
        jumps -= 1
        if target.alive:
            break
        nxt = [v for v in c.units if v.alive and not v.obj and caster.is_enemy(v) and v not in done
               and cheb(v.cell, caster.cell) <= eff.get("reach", 3)]
        target = min(nxt, key=lambda v: (v.hp, cheb(v.cell, caster.cell))) if nxt else None
    if eff.get("vanish"):
        c.add_buff(caster, "stealth", 1.6, eff["vanish"])


def _detonate_charges(c, caster, eff, center):
    r = eff.get("radius", 8)
    n = 0
    for o in list(c.units):
        if o.alive and o.obj and o.obj.get("volatile") is not None and o.owner is caster \
                and cheb(o.cell, caster.cell) <= r:
            if eff.get("power"):
                o.blast_mult = eff["power"]
            o.igniter = caster
            c.break_object(o, ignite=True)
            n += 1
    for p, cell in list(c.grid.cells.items()):
        if cell.hazard == "mine" and cell.hazard_team == caster.team and cheb(p, caster.cell) <= r:
            cell.hazard = None
            c.emit("detonate", pos=p, src=caster)
            for v in c.units_in_radius(p, 1):
                if caster.is_enemy(v):
                    c.damage(v, eff.get("mine", 30) * eff.get("power", 1.0) * caster.power, caster, "fire", "spell")
            n += 1
    for v in list(c.units):
        if v.alive and "bomb" in v.marks and v.marks["bomb"]["src"] is caster:
            consume_mark(c, v, "bomb")
            n += 1
    if not n:
        c.emit("fizzle", unit=caster, skill=None)


def on_kill(c, attacker, target):
    if attacker is None or not attacker.alive:
        return
    ks = attacker.proto.get("kill_stealth") or c.cfg.get("kill_stealth", {}).get(attacker.proto_id)
    if ks:                                          # ассасин: убил — снова в тени
        c.add_buff(attacker, "stealth", 1.6, ks)
        c.emit("reveal", unit=attacker)


def banner_near(c, u):
    return "banner" in u.buffs


def dist_line(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])
