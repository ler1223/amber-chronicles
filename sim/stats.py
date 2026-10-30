"""Режим героев: атрибуты, уровни и скейлы (отдельный режим, основа игры его не использует).

Три атрибута, как в Dota 2 / Diablo:
  Сила      — здоровье, урон ближних навыков и столкновений;
  Ловкость  — скорость атак, броня, крит, уклонение, урон стрел;
  Интеллект — урон заклинаний и реакций, лечение и щиты, восстановление и запас AP.
У героя основной атрибут (растёт быстрее, обычная атака скейлится от него), авторост за уровень по классу и
3 свободных очка за уровень. Прибавки считаются от стартовых атрибутов героя: на 1 уровне герой ровно такой же,
как в основной игре, дальше — сильнее по тому, во что вложился.

Навыки скейлятся от атрибута по виду урона (config «schools»): ближний — Сила, стрелы — Ловкость,
заклинания и реакции — Интеллект, лечение и щиты — Интеллект. Множитель — proto["scale"][вид], его применяет бой.
Враги получают уровень региона (+титул «ветеран»/«чемпион»), их HP, урон и сила навыков растут с уровнем.
Числа — data/stats_mode.json.
"""
import math

ATTRS = ("str", "agi", "int")


def cfg(data):
    return data.stats_mode


def new_rpg():
    return {"level": 1, "xp": 0, "points": {a: 0 for a in ATTRS}}


def attrs(data, cls, rpg):
    c = cfg(data)["classes"][cls]
    lvl = rpg.get("level", 1)
    pts = rpg.get("points", {})
    return {a: c["start"][a] + c["gain"][a] * (lvl - 1) + pts.get(a, 0) for a in ATTRS}


def points_total(data, rpg):
    return (rpg.get("level", 1) - 1) * cfg(data)["free_points"]


def points_free(data, rpg):
    return points_total(data, rpg) - sum(rpg.get("points", {}).values())


def derive(data, cls, rpg):
    """Всё, что дают атрибуты: модификаторы прототипа (HP, броня, скорость атак, AP), множители навыков по виду,
    крит и уклонение. delta — прибавка атрибутов к стартовым."""
    k = cfg(data)
    pp = k["per_point"]
    c = k["classes"][cls]
    at = attrs(data, cls, rpg)
    d = {a: at[a] - c["start"][a] for a in ATTRS}
    prim = c["primary"]
    scale = {school: 1 + pp["dmg_pct"] * d[a] for school, a in k["schools"].items()}
    scale["heal"] = 1 + pp["heal_pct"] * d["int"]
    scale["basic"] = 1 + pp["dmg_pct"] * d[prim]           # обычная атака — от основного атрибута
    mods = [
        {"stat": "hp", "mult": 1 + pp["hp_pct"] * d["str"]},
        {"stat": "armor", "add": round(pp["armor"] * d["agi"], 2)},
        {"stat": "atk_cooldown", "mult": 1 / (1 + pp["atk_speed_pct"] * d["agi"])},
        {"stat": "ap_regen", "mult": 1 / (1 + pp["ap_regen_pct"] * d["int"])},
        {"stat": "ap_max", "add": int(max(0, d["int"]) // pp["ap_per"])},
    ]
    crit = min(k["max_crit"], k["base_crit"] + pp["crit"] * max(0, d["agi"]))
    dodge = min(k["max_dodge"], pp["dodge"] * max(0, d["agi"]))
    return {"attrs": at, "delta": d, "primary": prim, "scale": scale, "mods": mods, "crit": round(crit, 3),
            "dodge": round(dodge, 3), "crit_mult": k["crit_mult"]}


def apply_to_proto(p, der):
    p["scale"] = der["scale"]
    p["crit"], p["dodge"], p["crit_mult"] = der["crit"], der["dodge"], der["crit_mult"]
    p["attrs"] = der["attrs"]


# ---------- опыт ----------

def xp_to_next(data, level):
    x = cfg(data)["xp"]
    return x["next_base"] + x["next_per_level"] * level


def battle_xp(data, node_type, region_level, hero_level):
    """Опыт герою за победу: больше за элиту и стража, меньше, если герой сильно выше уровня региона."""
    x = cfg(data)["xp"]
    base = (x["battle_base"] + x["battle_per_level"] * region_level) * x["node_mult"].get(node_type, 1.0)
    over = hero_level - region_level - x["over_level_free"]
    share = max(x["min_share"], 1 - x["over_level_cut"] * over) if over > 0 else 1.0
    return int(round(base * share))


def add_xp(data, rpg, amount):
    """Начислить опыт; возвращает число полученных уровней."""
    cap = cfg(data)["level_cap"]
    ups = 0
    rpg["xp"] = rpg.get("xp", 0) + amount
    while rpg["level"] < cap and rpg["xp"] >= xp_to_next(data, rpg["level"]):
        rpg["xp"] -= xp_to_next(data, rpg["level"])
        rpg["level"] += 1
        ups += 1
    if rpg["level"] >= cap:
        rpg["xp"] = 0
    return ups


# ---------- регионы и враги ----------

def region_level(data, chapter, region, difficulty="normal"):
    r = cfg(data)["regions"]
    order = data.biomes.get(chapter, {}).get("order", 0)
    lvl = 1 + r["per_chapter"] * order + r["per_threat"] * ((region or {}).get("threat", 1) - 1)
    if region and region.get("boss"):
        lvl += r["boss"]
    return int(round(lvl + r["difficulty"].get(difficulty, 0)))


def enemy_mults(data, level):
    e = cfg(data)["enemy"]
    k = level - 1
    return {"hp": 1 + e["hp_pct"] * k, "damage": 1 + e["dmg_pct"] * k, "power": 1 + e["dmg_pct"] * k,
            "armor": e["armor"] * k}


def roll_title(data, rng):
    """Титул врага: «ветеран» (+2 уровня), «чемпион» (+4) — или ничего."""
    r = rng.random()
    acc = 0.0
    for t in cfg(data)["enemy"]["titles"]:
        acc += t["chance"]
        if r < acc:
            return t
    return None


def level_color(diff):
    """Цвет уровня врага относительно героя: серый — слабее, жёлтый — равный, красный — опаснее."""
    if diff <= -3:
        return (150, 150, 160)
    if diff <= 1:
        return (240, 220, 120)
    if diff <= 3:
        return (255, 160, 80)
    return (255, 90, 80)


def squad_level(levels):
    return int(math.floor(sum(levels) / max(1, len(levels))))
