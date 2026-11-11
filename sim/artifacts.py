"""Артефакты героев (вне похода): хранилище таверны, ковка в мастерских, сеты, улучшение и самоцветы.

Артефакт — словарь {"uid", "kind", "set", "rarity", "q", "level", "extra", "gems"}:
  kind   — вид (наручи, пояс, кольцо, амулет, талисман), у героя не больше одного каждого вида;
  set    — сет (у сета своя редкость), бонусы за 2 и 4 вещи сета на герое;
  q      — качество ковки (мини-игра) 0.7–1.3;
  level  — улучшение +0…+10 (алхимия);
  extra  — свойство зачарования {"id": свойство вещи, "q": качество} или None;
  gems   — вставленные самоцветы [{"id", "q"}] (гнёзд — по редкости).
Слой артефактов множится на остальной рост героя (бонусы внутри слоя складываются)."""
import math
import random

RARITY_ORDER = ("common", "rare", "epic", "legendary")


def cfg(xd):
    return xd["artifacts"]


def level_k(xd, art):
    return 1 + cfg(xd)["level_step"] * art.get("level", 0)


def power_k(xd, art):
    """Множитель силы вещи: редкость × качество × улучшение."""
    a = cfg(xd)
    return a["rarities"][art["rarity"]]["mult"] * art.get("q", 1.0) * level_k(xd, art)


def scale_entry(entry, k):
    """Свойство-стат (как у вещей похода) с числами ×k."""
    out = dict(entry)
    for key in ("pct", "add", "speed", "ap_regen", "reaction"):
        if key in out and isinstance(out[key], (int, float)):
            out[key] = out[key] * k
    if "skill_cd" in out and out["skill_cd"] < 0.5:
        out["skill_cd"] = out["skill_cd"] * k
    return out


def _stat(xd, entry, k):
    from sim.expedition import _stat_mods
    return _stat_mods(xd, scale_entry(entry, k), 1)


def sockets(xd, art):
    return cfg(xd)["rarities"][art["rarity"]]["sockets"]


def set_counts(xd, arts):
    out = {}
    for a in arts:
        out[a["set"]] = out.get(a["set"], 0) + 1
    return out


def active_bonuses(xd, arts):
    """[(сет, порог, бонус)] — что включено на герое."""
    out = []
    for sid, n in set_counts(xd, arts).items():
        s = cfg(xd)["sets"].get(sid)
        if not s:
            continue
        for need, b in sorted(s["bonus"].items(), key=lambda kv: int(kv[0])):
            if n >= int(need):
                out.append((sid, int(need), b))
    return out


def effects(xd, arts, owner="h"):
    """Артефакты героя → (модификаторы слоя, добавки крита/уклонения, правила боя)."""
    from sim.expedition import make_rule, merge_bonus
    a = cfg(xd)
    mods, extra, rules = [], {}, []

    def add(m, e):
        mods.extend(m)
        for kk, v in e.items():
            extra[kk] = extra.get(kk, 0) + v
    for art in arts:
        k = power_k(xd, art)
        for entry in a["kinds"][art["kind"]]["stats"]:
            add(*_stat(xd, entry, k))
        ex = art.get("extra")
        if ex and ex["id"] in xd["items"]["stat_affixes"]:
            add(*_stat(xd, xd["items"]["stat_affixes"][ex["id"]], a["extra_k"] * k * ex.get("q", 1.0) / art.get("q", 1.0)))
        for g in art.get("gems", []):
            gd = a["gems"].get(g["id"])
            if gd:
                for entry in gd["stats"]:
                    add(*_stat(xd, entry, g.get("q", 1.0)))
    for art in arts:                                     # металл кованой вещи: твёрдость, вязкость, дамаск
        for m in metal_mods(art.get("metal")):
            if "extra" in m:
                extra[m["extra"]] = extra.get(m["extra"], 0) + m["add"]
            else:
                mods.append(m)
    for n, (sid, need, b) in enumerate(active_bonuses(xd, arts)):
        for entry in b.get("stats", []):
            add(*_stat(xd, entry, 1.0))
        tier = 1 + RARITY_ORDER.index(a["sets"][sid]["rarity"]) // 2
        for m_, spec in enumerate(b.get("rules", [])):
            rules.append(make_rule(xd, spec, tier, f"{owner}:set:{sid}:{need}:{m_}"))
    stat_mods = [m for m in mods if "stat" in m and set(m) <= {"stat", "mult"}]
    rest = [m for m in mods if m not in stat_mods]
    return merge_bonus(stat_mods) + rest, extra, rules


def metal_mods(metal):
    """Металл кованой вещи → модификаторы: твёрдость — урон атак и сила навыков, вязкость — здоровье,
    дамаск (слои × узор) — шанс крита."""
    if not metal:
        return []
    h, t = metal.get("hard", 0.5), metal.get("tough", 0.5)
    out = [{"stat": "atk_damage", "mult": round(1 + 0.08 * (h - 0.5), 4)},
           {"stat": "power", "mult": round(1 + 0.05 * (h - 0.5), 4)},
           {"stat": "hp", "mult": round(1 + 0.08 * (t - 0.5) + metal.get("heavy", 0), 4)}]
    layers, pat = metal.get("layers", 0), metal.get("pattern", 0)
    if layers >= 16 and pat > 0:
        out.append({"extra": "crit", "add": round(0.006 * math.log2(layers / 8) * pat, 4)})
    return out


def metal_text(metal):
    if not metal:
        return ""
    s_ = f"Металл: твёрдость {metal['hard'] * 100:.0f}%, вязкость {metal['tough'] * 100:.0f}%"
    if metal.get("mass"):
        s_ += f", {metal['mass']} г" + (f" (массивнее: здоровье +{metal['heavy'] * 100:.1f}%)" if metal.get("heavy")
                                        else "")
    if metal.get("layers", 0) >= 16 and metal.get("pattern", 0) > 0:
        s_ += f", дамаск {metal['layers']} слоёв"
    return s_


# ---------- описание ----------

def art_name(xd, art):
    a = cfg(xd)
    s = a["sets"][art["set"]]["name"]
    lv = f" +{art['level']}" if art.get("level") else ""
    return f"{a['kinds'][art['kind']]['name']} «{s}»{lv}"


def quality_word(q):
    return ("грубая работа" if q < 0.85 else "добротная работа" if q < 1.0 else "тонкая работа" if q < 1.15
            else "работа мастера")


def entry_text(entry, k=1.0):
    """«+5% урона атак» для свойства-стата артефакта."""
    names = {"atk_damage": "урона атак", "power": "силы навыков", "hp": "здоровья", "armor": "брони",
             "lifesteal": "вампиризма", "dot_poison_mult": "урона ядом", "dot_fire_mult": "урона горением"}
    if "pct" in entry and "vs" in entry:
        return f"+{entry['pct'] * k * 100:.1f}% урона по {'горящим' if entry['vs'] == 'burning' else 'ослабленным'}"
    if "pct" in entry:
        return f"+{entry['pct'] * k * 100:.1f}% {names.get(entry['stat'], entry['stat'])}"
    if entry.get("stat") == "armor":
        return f"+{entry['add'] * k:.1f} брони"
    if entry.get("stat") == "lifesteal":
        return f"вампиризм {entry['add'] * k * 100:.1f}%"
    if entry.get("extra") == "crit":
        return f"+{entry['add'] * k * 100:.1f}% шанса крита"
    if "speed" in entry:
        return f"+{entry['speed'] * k * 100:.1f}% скорости атак"
    if "ap_regen" in entry:
        return f"+{entry['ap_regen'] * k * 100:.1f}% восстановления AP"
    if "skill_cd" in entry:
        return f"−{entry['skill_cd'] * k * 100:.1f}% перезарядки навыков"
    return ""


def art_lines(xd, art):
    """Строки описания: база, свойство, самоцветы, гнёзда."""
    from sim.expedition import affix_text
    a = cfg(xd)
    k = power_k(xd, art)
    out = [entry_text(e, k) for e in a["kinds"][art["kind"]]["stats"]]
    ex = art.get("extra")
    if ex:
        v = a["extra_k"] * k * ex.get("q", 1.0) / art.get("q", 1.0)
        s = xd["items"]["stat_affixes"][ex["id"]]
        out.append("Свойство: " + _affix_scaled(xd, s, v, affix_text))
    for g in art.get("gems", []):
        gd = a["gems"][g["id"]]
        out.append(f"{gd['name']}: " + "; ".join(entry_text(e, g.get("q", 1.0)) for e in gd["stats"]))
    if art.get("metal"):
        out.append(metal_text(art["metal"]))
    free = sockets(xd, art) - len(art.get("gems", []))
    if free > 0:
        out.append("Свободных гнёзд: " + str(free))
    return [x for x in out if x]


def _affix_scaled(xd, s, k, affix_text):
    if "pct" in s:
        v = s["pct"] * k * 100
    elif "reaction" in s:
        v = s["reaction"] * k * 100
    else:
        v = (s.get("add") or s.get("speed") or s.get("skill_cd") or s.get("ap_regen") or 0) * k * 100
    return s["text"].format(v=f"{v:.1f}")


# ---------- ковка ----------

def craft_cost(xd, ws, set_id):
    """Цена ковки: основной материал мастерской, редкий материал сета, звёздная пыль, золото."""
    a = cfg(xd)
    s = a["sets"][set_id]
    c = a["craft_cost"][s["rarity"]]
    out = {"glory": c["gold"], a["main_mat"][ws]: c["main"]}
    if c.get("rare"):
        out[s["mat"] or "stardust"] = out.get(s["mat"] or "stardust", 0) + c["rare"]
    if c.get("stardust"):
        out["stardust"] = out.get("stardust", 0) + c["stardust"]
    return out


def make(xd, uid, kind, set_id, q, rng=None):
    """Новый артефакт: качество из мини-игры; высокое качество — шанс свойства."""
    a = cfg(xd)
    rng = rng or random.Random(uid)
    lo, hi = a["quality"]
    q = round(max(lo, min(hi, q)), 3)
    art = {"uid": uid, "kind": kind, "set": set_id, "rarity": a["sets"][set_id]["rarity"], "q": q, "level": 0,
           "extra": None, "gems": []}
    if q >= a["extra_at"]:
        art["extra"] = {"id": rng.choice(a["extras"]), "q": q}
    return art


def upgrade_cost(xd, art):
    a = cfg(xd)
    u = a["upgrade_cost"]
    lv = art.get("level", 0)
    rk = RARITY_ORDER.index(art["rarity"]) + 1
    out = {"glory": int((u["gold"] + u["gold_per_level"] * lv) * rk),
           "herbs": u["herbs"] + lv // u["herbs_every"]}
    if lv + 1 >= u["rare_from"]:
        mat = a["sets"][art["set"]]["mat"] or "stardust"
        out[mat] = out.get(mat, 0) + 1
    return out


def enchant_cost(xd, art):
    a = cfg(xd)
    e = a["enchant_cost"]
    out = {"glory": e["gold"] * (RARITY_ORDER.index(art["rarity"]) + 1), "herbs": e["herbs"]}
    if RARITY_ORDER.index(art["rarity"]) >= RARITY_ORDER.index(e["rare_from"]):
        mat = a["sets"][art["set"]]["mat"] or "stardust"
        out[mat] = out.get(mat, 0) + 1
    return out


def power_score(xd, arts):
    """Грубая «сила» набора: множитель урона × здоровья (для экрана и баланса)."""
    mods, _, _ = effects(xd, arts)
    dmg = hp = 1.0
    for m in mods:
        if m.get("stat") == "atk_damage" and "mult" in m:
            dmg = max(dmg, m["mult"])
        if m.get("stat") == "hp" and "mult" in m:
            hp = m["mult"]
    return dmg * hp


# ---------- самоцветы: цена ----------

def rough_value(xd, r):
    """Цена необработанного камня: вид × размер."""
    return int(xd["artifacts"]["gems"][r["id"]].get("price", 200) * r.get("size", 1.0))


def cut_value(xd, g):
    """Цена огранённого камня: вид × размер × качество огранки (70% — дешевле сырого, 130% — вдвое дороже)."""
    lo, hi = xd.get("market", {}).get("cut_value", [0.6, 2.2])
    k = lo + (hi - lo) * max(0.0, min(1.0, (g["q"] - 0.7) / 0.6))
    return int(xd["artifacts"]["gems"][g["id"]].get("price", 200) * g.get("size", 1.0) * k)
