"""Награда нейросетей: набор компонентов с весами, пресеты, командный дух и затухание подсказок.

Награда юнита за отрезок между его решениями:
  личное   = Σ вес_k · компонент_k                       (урон, лечение, щиты, контроль, баффы… — его заслуги)
  команда  = вес_team · (Φ_сейчас − Φ_раньше)             Φ — баланс сил: доля HP+щитов своих минус доля чужих
  подсказка = (личное + команда) · затухание               затухание: 1 → floor за anneal боёв
  итог     = (1 − τ) · подсказка + τ · средняя подсказка команды на этом шаге + разовые (смерть, победа)
τ — командный дух: растёт от tau0 к tau1 за anneal боёв (сначала каждый учится своему делу, потом — на команду).
В конце боя: победа +win (и +margin · доля HP, что осталась у команды), поражение −win. Победа/поражение
выдаются всем героям, включая павших. В пресете «команда» Φ включает потенциал цели боя, а личные заслуги
считаются по эффективному урону/лечению (без overkill) в долях HP цели; штраф за время отсекает пустое тянуть бой.

Командная часть — «потенциальная» добавка (Ng, Harada, Russell 1999): она не меняет, какая стратегия лучшая, а лишь
подсказывает направление. Личные компоненты быстрее учат роли, но их можно «фармить» — поэтому они затухают.
"""

from .teams import PLAYER

# компонент → (что берём из статистики юнита (tally), чем делим: "ref" — средний запас HP боя, "hp" — своё HP, 1)
COMPONENTS = {
    "dealt": ("dealt", "ref", "урон"),
    "healed": ("healed", "ref", "лечение"),
    "shielded": ("shielded", "ref", "щиты (поглощено)"),
    "taken": ("taken", "hp", "получено урона"),
    "dealt_frac": ("dealt_frac", 1, "эффективный урон (доля HP цели)"),
    "healed_frac": ("healed_frac", 1, "эффективное лечение (доля HP цели)"),
    "shielded_frac": ("shielded_frac", 1, "поглощённый щит (доля HP цели)"),
    "cc": ("cc", 1, "контроль, сек"),
    "buffs": ("buffs", 1, "баффы своим"),
    "debuffs": ("debuffs", 1, "дебаффы врагам"),
    "interrupts": ("interrupts", 1, "сорванные касты"),
    "taunts": ("taunts", 1, "насмешки"),
    "kills": ("kills", 1, "убийства"),
    "assists": ("assists", 1, "помощь"),
}
NAMES = dict({k: v[2] for k, v in COMPONENTS.items()}, team="баланс сил", objective="цель боя", time="время",
             death="смерть", win="победа", margin="запас HP")

PRESETS = {
    "команда": {
        "about": "потенциал команды: HP, цель боя, охрана и источники; личные заслуги — без overkill, затухают",
        "w": {"team": 4.0, "dealt_frac": 0.6, "healed_frac": 0.4, "shielded_frac": 0.4, "cc": 0.02,
              "buffs": 0.01, "debuffs": 0.01, "interrupts": 0.1, "taunts": 0.01, "kills": 0.1, "assists": 0.05},
        "death": -0.5, "win": 3.0, "margin": 0.0, "tau0": 0.0, "tau1": 0.0, "anneal": 20000, "floor": 0.0,
        "obj": 2.0, "time": 0.002,
    },
    "командный": {
        "about": "баланс сил команды + победа; личные заслуги — подсказки, затухают",
        "w": {"team": 4.0, "dealt": 0.2, "healed": 0.2, "shielded": 0.2, "taken": -0.2, "cc": 0.1, "buffs": 0.05,
              "debuffs": 0.05, "interrupts": 0.2, "taunts": 0.05, "kills": 0.2, "assists": 0.1},
        "death": -0.5, "win": 3.0, "margin": 2.0, "tau0": 0.3, "tau1": 0.9, "anneal": 30000, "floor": 0.1},
    "роли": {
        "about": "награда за каждое полезное действие своей роли; почти без командной части",
        "w": {"dealt": 1.0, "healed": 1.0, "shielded": 1.0, "taken": -0.5, "cc": 0.3, "buffs": 0.15, "debuffs": 0.15,
              "interrupts": 0.5, "taunts": 0.15, "kills": 0.3, "assists": 0.2},
        "death": -1.0, "win": 2.0, "margin": 1.0, "tau0": 0.1, "tau1": 0.3, "anneal": 0, "floor": 1.0},
    "урон": {
        "about": "прежняя награда: урон и лечение, минус полученный урон, убийства, итог боя",
        "w": {"dealt": 1.0, "healed": 0.8, "taken": -0.8, "kills": 0.3},
        "death": -1.0, "win": 1.5, "margin": 0.0, "tau0": 0.0, "tau1": 0.0, "anneal": 0, "floor": 1.0},
    "победа": {
        "about": "только итог: победа/поражение и запас HP победителя (самое «честное», самое медленное)",
        "w": {}, "death": 0.0, "win": 5.0, "margin": 2.0, "tau0": 1.0, "tau1": 1.0, "anneal": 0, "floor": 1.0},
}
DEFAULT = "команда"


def resolve(name=None, battles=0, override=None):
    """Пресет → рабочие веса на этот момент обучения: {"w", "death", "win", "margin", "tau", "scale", "name"}."""
    p = dict(PRESETS.get(name or DEFAULT, PRESETS[DEFAULT]))
    p.update(override or {})
    n = p.get("anneal") or 0
    prog = min(1.0, battles / n) if n else 0.0
    scale = 1.0 - (1.0 - p.get("floor", 1.0)) * prog if n else 1.0
    tau = p["tau0"] + (p["tau1"] - p["tau0"]) * (prog if n else 0.0)
    return {"name": name or DEFAULT, "w": dict(p["w"]), "death": p["death"], "win": p["win"], "margin": p["margin"],
            "tau": tau, "scale": scale, "progress": prog, "obj": p.get("obj", 0.0), "time": p.get("time", 0.0)}


def balance(c, team):
    """Φ: доля HP+щитов своих минус доля чужих (по всем бойцам боя, павшие — с нулём)."""
    own = own_max = foe = foe_max = 0.0
    for v in c.units:
        if v.obj or v.summon:
            continue
        val = (max(0, v.hp) + min(v.shield, v.max_hp)) if v.alive else 0.0
        if v.team == team:
            own += val
            own_max += v.max_hp
        else:
            foe += val
            foe_max += v.max_hp
    return own / max(1.0, own_max) - foe / max(1.0, foe_max)


def objective_value(c, team):
    """Прогресс цели боя для команды: 0 — никакого, 1 — цель выполнена (или сорвана у врага)."""
    ob = c.objective or {}
    typ = ob.get("type")
    if typ == "hold":
        t = float(ob.get("time") or 0.0)
        if t <= 0:
            return 0.0
        p = min(1.0, max(0.0, float(getattr(c, "hold", 0.0)) / t))
        return p if team == PLAYER else 1.0 - p
    if typ == "defend":
        guards = [g for g in c.guards() if g.alive]
        if not guards:
            return 0.0
        p = sum((max(0, g.hp) + min(g.shield, g.max_hp)) / max(1, g.max_hp) for g in guards) / len(guards)
        return p if team == PLAYER else 1.0 - p
    if typ == "destroy":
        src = [u for u in c.units if u.obj and u.obj.get("source")]
        if team == PLAYER:
            foe = [u for u in src if u.team != PLAYER]
            return 1.0 - sum(1 for u in foe if u.alive) / len(foe) if foe else 0.0
        own = [u for u in src if u.team == team]
        return sum(1 for u in own if u.alive) / len(own) if own else 0.0
    return 0.0


def potential(c, team, rw=None):
    """Φ команды: HP-баланс + (для новых пресетов) потенциал цели боя. Старые пресеты остаются HP-балансом."""
    p = balance(c, team)
    rw = rw or {}
    if rw.get("obj"):
        p += rw["obj"] * objective_value(c, team)
    return p


def parts(u, t0, ref, rw):
    """Личные компоненты за отрезок: {компонент: взвешенное значение} (без затухания)."""
    out = {}
    t1 = u.tally
    for k, w in rw["w"].items():
        if k == "team" or k not in COMPONENTS or not w:
            continue
        key, div, _ = COMPONENTS[k]
        d = t1.get(key, 0) - t0.get(key, 0)
        if not d:
            continue
        den = ref if div == "ref" else max(1, u.max_hp) if div == "hp" else 1.0
        out[k] = w * d / den
    return out
