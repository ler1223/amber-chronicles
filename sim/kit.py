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

TYPES = {"mark", "quiver", "zone", "totem_pulse", "totem_move", "totem_link", "shadow_dance", "trap_pull",
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
            if d.get("on_expire"):
                c.emit("mark_max", unit=u, mark=mid, src=m["src"])
                c.apply_effects(m["src"] or u, [dict(e, _n=m["n"], _powder=m.get("mult", 1.0)) for e in d["on_expire"]],
                                u.cell, u)


def consume_mark(c, v, mid):
    """Снять метку целиком; бомба при этом взрывается (on_expire)."""
    m = v.marks.pop(mid, None)
    if m is None:
        return 0
    d = mark_def(c, mid)
    c.emit("mark_end", unit=v, mark=mid)
    if d.get("on_expire") and d.get("burst_on_consume"):
        c.emit("mark_max", unit=v, mark=mid, src=m["src"])
        c.apply_effects(m["src"] or v, [dict(e, _n=m["n"], _powder=m.get("mult", 1.0)) for e in d["on_expire"]],
                        v.cell, v)
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
        arrow_rider(c, caster, v, eff.get("arrow_mult", 1.0))
    if eff.get("mark_on_hit") and v.alive:
        mo = eff["mark_on_hit"]
        add_mark(c, v, mo["mark"], mo.get("stacks", 1), mo.get("duration", 6), caster)


# ---------- колчан ----------

def arrow_rider(c, u, t, mult=1.0):
    """Эффект стрелы из колчана на цели: огонь, холод, кровотечение, оглушение."""
    a = c.cfg["quiver"].get(u.quiver or "")
    if not a or not t.alive:
        return
    from sim import passives as PS
    if PS.arrow_mult(u) > 1 and mult == 1.0:       # полный разгон: эффект стрел двойной
        mult = 2.0
        if a.get("mark"):
            add_mark(c, t, a["mark"], a.get("stacks", 1), a.get("duration", 5), u)
    c.gain(u, "arrow")
    if a.get("tag"):
        c.apply_status(t, a["tag"], u)
    if a.get("mark"):
        add_mark(c, t, a["mark"], a.get("stacks", 1), a.get("duration", 5), u)
    if a.get("bleed"):
        value = max(a["bleed"], u.atk_damage * a.get("bleed_pct", 0))
        c.add_buff(t, "bleed", round(value * mult, 1), a.get("duration", 4), src=u)
    if a.get("knockback") and not t.boss:
        c.knockback(u.cell, t, a["knockback"], u)
    if a.get("interrupt"):
        c._interrupt(t)


def basic_rider(c, u, t):
    if u.quiver and t.alive and not t.obj:
        arrow_rider(c, u, t)
    if "all_arrows" in u.buffs and t.alive and not t.obj:      # «Все стрелы»: каждая атака — всеми видами
        keep = u.quiver
        for a in c.cfg["quiver"]:
            if a != keep:
                u.quiver = a
                arrow_rider(c, u, t, 0.6)
        u.quiver = keep


# ---------- проверки навыка ----------

LIVE = {
    "fire_cells": lambda c, u: sum(1 for p in c.grid.in_radius(u.cell, 6) if c.grid.get(p).hazard == "fire"),
    "totems": lambda c, u: len(own(c, u, totem=True)),
    "corpses": lambda c, u: len(c.corpses),
    "song_notes": lambda c, u: u.song["notes"] if u.song else 0,
    "charges": lambda c, u: (sum(1 for o in c.units if o.alive and o.obj and o.owner is u and o.obj.get("volatile") is not None)
                             + sum(1 for cell in c.grid.cells.values() if cell.hazard == "mine" and cell.hazard_team == u.team)
                             + sum(1 for v in c.units if v.alive and "bomb" in v.marks and v.marks["bomb"]["src"] is u)),
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
    if t == "mark":
        aff = eff.get("affects", "enemies")
        for v in c._select(caster, center, eff.get("radius", 0), aff, tunit):
            if eff.get("if_mark") and eff["if_mark"] not in v.marks:
                continue
            if not v.obj:
                add_mark(c, v, eff["mark"], eff.get("stacks", 1), eff.get("duration", 6), caster)
                if eff.get("_powder") and eff["mark"] in v.marks:      # бомба с Порохом — ×2, без — ×0.6
                    v.marks[eff["mark"]]["mult"] = eff["_powder"]
    elif t == "quiver":
        caster.quiver = eff["arrow"]
        if eff.get("shots"):                       # первые выстрелы новыми стрелами сильнее
            c.add_buff(caster, "atk_mult", eff.get("mult", 1.3), eff["shots"] * caster.atk_cd + 0.5)
        c.emit("quiver", unit=caster, arrow=eff["arrow"])
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
