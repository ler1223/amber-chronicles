"""Экспедиция: рогалик-поход отряда (data/expedition.json). Отдельный режим — основа, режим героев и сюжет не меняются.

Цикл:
  таверна — в зале сидят случайные герои (класс, имя, черта, ранг, свой набор навыков и стартовая вещь);
            игрок берёт 2–3. Слава за походы улучшает таверну: больше героев, выше ранги, новые классы, золото.
  поход   — глава целиком (прототип — Болото): 3 акта, у каждого своя карта с развилками и босс в конце.
            Узлы: бой, элита, событие, лагерь, торговец, босс. События — короткие выборы, многошаговые сцены,
            сюжетные нити (добавляют узлы на карту и меняют финального босса) и события спутников (по классам
            и чертам отряда). Проверки — d20 + бонус героя против сложности, как в настольных ролевых играх.
  рост    — кратный: уровень (опыт за бои) даёт % урона и HP, атрибуты и очко навыка; ранги навыков и ветки
            A/B — только внутри похода; снаряжение по актам (тир) из 4 слотов с базой и свойствами-блоками
            (триггер + эффект + условие, sim/rules.py); редкие личные дары (босс и первая элита акта) — сильное
            усиление одного героя под его класс. Общих бафов отряда нет: сочетания тегов строятся из классов.
            Теги сами вешают только эпические и уникальные вещи, и таких за поход не больше двух.
            Враги растут по актам и глубине карты, так что к третьему акту урон уходит в сотни и тысячи.
  смерть  — павший в бою герой ранен до лагеря (слабее); поход проигран, только если пал весь отряд.
Поход сохраняется после каждого шага (в профиль экспедиции), из него можно выйти и вернуться.
Без pygame — всё проверяется тестами.
"""
import copy
import json
import os
import random
import re

from . import stats, story_meta
from .build import build_proto
from .teams import PLAYER

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLOTS = ("weapon", "armor", "amulet", "ring")
ATTRS = stats.ATTRS
VERSION = 1


def load_expedition():
    with open(os.path.join(ROOT, "data", "expedition.json"), encoding="utf-8") as f:
        return json.load(f)


def load_chapters(xd):
    """Главы похода: Болото — в самом expedition.json, остальные — свои файлы (data/expedition_<глава>.json)."""
    out = {}
    for cid, meta in xd.get("chapters", {}).items():
        if meta.get("file"):
            with open(os.path.join(ROOT, "data", meta["file"]), encoding="utf-8") as f:
                out[cid] = json.load(f)
    return out


def vow_sum(xd, vows, key):
    """Сумма эффекта обетов: {id: ступень} × per[key]."""
    return sum(xd["vows"][v]["per"].get(key, 0) * r for v, r in (vows or {}).items() if v in xd.get("vows", {}))


def building_value(xd, build, bid):
    """Значение постройки на её уровне (0 — не построена)."""
    lv = (build or {}).get(bid, 0)
    b = xd.get("buildings", {}).get(bid)
    return b["levels"][lv - 1].get("value") if b and lv else None


def run_cfg(xd, solo, vows, build):
    """Конфиг похода: одиночка, обеты (меньше лечения), лазарет (больше)."""
    cfg = solo_cfg(xd["config"]) if solo else dict(xd["config"])
    heal = cfg["post_battle_heal"] + vow_sum(xd, vows, "heal") + (building_value(xd, build, "infirmary") or 0)
    cfg["post_battle_heal"] = round(max(0.0, heal), 3)
    return cfg


def solo_cfg(cfg):
    """Конфиг похода одиночки: отряд из одного героя, без спутников."""
    s = cfg.get("solo", {})
    return dict(cfg, squad_min=1, squad_start=1, squad_max=1, **s.get("cfg", {}))


def chapter_view(xd, chapter):
    """Данные похода глазами главы: свои акты, события, проклятия, фракции, механики; общие — конфиг, таверна,
    вещи (плюс шедевры главы), дары."""
    cd = xd.get("chapter_data", {}).get(chapter)
    if not cd:
        return xd
    v = dict(xd)
    v["acts"], v["events"] = cd["acts"], cd["events"]
    v["curses"] = {**xd["curses"], **cd.get("curses", {})}
    v["factions"] = cd.get("factions", {})
    v["trade_faction"] = cd.get("trade_faction")
    v["mechanics"] = cd.get("mechanics", {})
    v["mats"] = cd.get("mats", {})
    v["boss_rules"] = cd.get("boss_rules", [])
    if cd.get("uniques"):
        v["items"] = dict(xd["items"], uniques={**xd["items"]["uniques"], **cd["uniques"]})
    v["chapter"] = chapter
    return v


def expedition_data(data, xd=None):
    """Копия данных игры с боями и врагами экспедиции (всех глав похода)."""
    xd = xd or load_expedition()
    xd.setdefault("chapter_data", load_chapters(xd))
    ed = copy.copy(data)
    from .story import load_story            # бои глав из сюжета тоже идут в пулы актов
    chapters = set(xd.get("chapters", {"swamp": {}})) | {"swamp"}
    extra = [e for e in load_story()["encounters"] if e.get("chapter", "swamp") in chapters] + xd["encounters"]
    for cd in xd["chapter_data"].values():
        extra += cd.get("encounters", [])
    known = {e["id"] for e in data.encounters}
    ed.encounters = list(data.encounters)
    for e in extra:
        if e["id"] not in known:
            ed.encounters.append(e)
            known.add(e["id"])
    ed.enemies = dict(data.enemies)
    ed.enemies.update(xd.get("enemies", {}))
    for cd in xd["chapter_data"].values():
        ed.enemies.update(cd.get("enemies", {}))
    ed.expedition = xd
    return ed


def enc_index(data, eid):
    for i, e in enumerate(data.encounters):
        if e["id"] == eid:
            return i
    raise KeyError(f"нет боя {eid}")


# ---------- снаряжение ----------

def tier_k(xd, tier):
    tm = xd["items"]["tier_mult"]
    return tm[min(len(tm), max(1, tier)) - 1]


def _soft(tier):
    """Мягкий рост для шансов, крита и уклонения: тир 3 — ×2."""
    return 1 + 0.5 * (max(1, tier) - 1)


def roll_rarity(xd, rng, pool):
    w = xd["items"]["drop_weights"][pool]
    keys = [k for k in w if w[k] > 0]
    return rng.choices(keys, [w[k] for k in keys])[0]


def has_tags(xd, item):
    """Вещь сама вешает теги (поджог, Лёд, Вода…)? Таких за поход мало."""
    it = xd["items"]
    acts = []
    if item.get("unique"):
        for spec in it["uniques"][item["unique"]].get("rules", []):
            acts += spec.get("raw", [])
            if any(it["effects"][e].get("tags") for e in spec.get("do", [])):
                return True
    for a in item.get("affixes", []):
        if a["kind"] == "proc" and it["effects"][a["effect"]].get("tags"):
            return True
    return any(x["type"] == "status" or x.get("tag") for x in acts)


def make_item(xd, rng, tier, rarity="common", slot=None, unique=None, uid=0, allow_tags=False):
    """Новая вещь: база слота и тира + свойства-блоки по редкости. unique — ручная вещь главы.
    allow_tags — можно ли свойству вешать теги (только эпик и уникальные, пока лимит похода не выбран)."""
    it = xd["items"]
    if unique or rarity == "unique":
        pool = sorted(u for u, v in it["uniques"].items() if not v.get("masterpiece"))
        if not unique and not allow_tags:
            pool = [u for u in pool if not has_tags(xd, {"unique": u, "affixes": []})] or pool
        uid_ = unique or rng.choice(pool)
        u = it["uniques"][uid_]
        base = it["bases"][u["base"]]
        return {"uid": uid, "base": u["base"], "slot": base["slot"], "tier": tier, "rarity": "unique",
                "name": u["name"], "unique": uid_, "affixes": []}
    bases = [b for b, v in it["bases"].items() if slot is None or v["slot"] == slot]
    base = rng.choice(sorted(bases))
    n = it["rarities"][rarity]["affixes"]
    affixes, procs = [], 0
    max_procs = 2 if rarity == "epic" else 1
    stat_ids = sorted(s for s in it["stat_affixes"] if not it["stat_affixes"][s].get("dot"))
    for _ in range(n):
        if procs < max_procs and rng.random() < 0.45:
            affixes.append(roll_proc(xd, rng, allow_tags and rarity == "epic"))
            procs += 1
        else:
            free = [s for s in stat_ids if s not in [a.get("id") for a in affixes]]
            affixes.append({"kind": "stat", "id": rng.choice(free)})
    # дот-свойства — отдельный пул: не ломают прежний порядок случайных статов и добавляются сверху
    dot_ids = sorted(s for s in it["stat_affixes"] if it["stat_affixes"][s].get("dot"))
    if dot_ids:
        aux = random.Random()
        aux.setstate(rng.getstate())
        if aux.random() < 0.35:
            used = [a.get("id") for a in affixes]
            free = [s for s in dot_ids if s not in used]
            if free:
                affixes.append({"kind": "stat", "id": aux.choice(free)})
    first = next((a for a in affixes if a["kind"] == "stat"), None)
    name = it["bases"][base]["name"]
    if first:
        name += " " + it["stat_affixes"][first["id"]]["name"]
    return {"uid": uid, "base": base, "slot": it["bases"][base]["slot"], "tier": tier, "rarity": rarity,
            "name": name, "unique": None, "affixes": affixes}


def roll_proc(xd, rng, allow_tags=False):
    """Свойство-срабатывание: триггер × совместимый эффект × (иногда) условие. Эффекты с тегами — только если
    allow_tags (эпическая вещь, лимит похода не выбран)."""
    it = xd["items"]
    trig = rng.choice(sorted(it["triggers"]))
    t = it["triggers"][trig]
    effects = [e for e, v in it["effects"].items() if (t["foe"] or not v.get("needs_foe"))
               and (allow_tags or not v.get("tags"))]
    eff = rng.choice(sorted(effects))
    cond = None
    if t["foe"] and t["on"] in ("hit", "crit") and rng.random() < 0.3:
        # условие не повторяет эффект: «окатить водой мокрых» или «поджечь горящих» бессмысленно
        same = {"soak": "wet", "ignite": "burning", "chill": "cold", "venom": "dot"}.get(eff)
        cond = rng.choice(sorted(c for c in it["conditions"] if c != same))
    return {"kind": "proc", "trigger": trig, "effect": eff, "cond": cond}


def _scaled_actions(xd, acts, tier, trig):
    out = []
    for a in acts:
        a = copy.deepcopy(a)
        for key in ("atk_pct", "hp_pct"):
            if key in a:
                a[key] = round(a[key] * (1 + 0.25 * (tier - 1)), 3)
        to = a.get("to")
        if to == "foe":
            a["to"] = trig["foe"] or "unit"
        elif to == "self":
            a["to"] = "owner"
        out.append(a)
    return out


def make_rule(xd, spec, tier, rid):
    """Правило боя (sim/rules.py) из блоков: {"trigger", "do": [эффекты], "raw": [действия], "cond", "chance", "icd"}."""
    it = xd["items"]
    trig = it["triggers"][spec["trigger"]]
    acts = []
    for eid in spec.get("do", []):
        acts += it["effects"][eid]["do"]
    acts += spec.get("raw", [])
    base_ch = spec.get("chance", trig.get("chance", 1.0))
    chance = min(0.6, base_ch * (1 + 0.15 * (tier - 1))) if base_ch < 1.0 else 1.0
    r = {"id": rid, "on": trig["on"], "owner": trig["owner"], "do": _scaled_actions(xd, acts, tier, trig)}
    if trig.get("not"):
        r["not"] = list(trig["not"])
    if chance < 1.0:
        r["chance"] = round(chance, 3)
    icd = spec.get("icd", trig.get("icd"))
    if icd:
        r["icd"] = icd
    if spec.get("cond"):
        key = "unit_has" if trig["foe"] == "unit" else "source_has"
        r[key] = list(it["conditions"][spec["cond"]]["tags"])
    return r


def _stat_mods(xd, entry, tier, scaled=True):
    """База или свойство-статы → (модификаторы прототипа, добавки крита/уклонения)."""
    mods, extra = [], {}
    k = tier_k(xd, tier) if scaled else 1.0
    if "pct" in entry and "stat" in entry:
        mods.append({"stat": entry["stat"], "mult": round(1 + entry["pct"] * k, 4)})
    if "mult" in entry:
        mods.append({"stat": entry["stat"], "mult": entry["mult"]})
    if "flat" in entry:
        mods.append({"stat": entry["stat"], "add": entry["flat"] * tier})
    if "add" in entry and "stat" in entry:
        v = entry["add"] if entry["stat"] == "ap_max" else round(entry["add"] * _soft(tier), 3)
        mods.append({"stat": entry["stat"], "add": v})
    if "extra" in entry:
        extra[entry["extra"]] = extra.get(entry["extra"], 0) + round(entry["add"] * _soft(tier), 3)
    if "speed" in entry:
        mods.append({"stat": "atk_cooldown", "mult": round(1 / (1 + entry["speed"] * _soft(tier)), 4)})
    if "skill_cd" in entry:
        v = entry["skill_cd"]
        v = 1 - v * _soft(tier) if v < 0.5 else v          # свойство «−6%» или база «×0.95»
        mods.append({"skill": "*", "cooldown_mult": round(v, 3)})
    if "ap_regen" in entry:
        mods.append({"stat": "ap_regen", "mult": round(1 / (1 + entry["ap_regen"] * _soft(tier)), 4)})
    if "vs" in entry:                                   # урон по горящим / мокрым… (складывается по вещам)
        extra["vs:" + entry["vs"]] = round(entry["pct"] * tier_k(xd, tier), 4)
        mods = [m for m in mods if m.get("stat") != entry.get("stat")]
    if "reaction" in entry:
        extra["reaction"] = round(entry["reaction"] * tier_k(xd, tier), 4)
    return mods, extra


def item_effects(xd, item):
    """Вещь → (модификаторы, добавки крита/уклонения, правила)."""
    it = xd["items"]
    tier = item["tier"]
    mods, extra, rules = [], {}, []

    def add(m, e):
        mods.extend(m)
        for kk, v in e.items():
            extra[kk] = extra.get(kk, 0) + v
    for st in it["bases"][item["base"]]["stats"]:
        add(*_stat_mods(xd, st, tier))
    if item.get("unique"):
        u = it["uniques"][item["unique"]]
        for st in u.get("stats", []):
            add(*_stat_mods(xd, st, tier))
        for n, spec in enumerate(u.get("rules", [])):
            rules.append(make_rule(xd, spec, tier, f"{item['uid']}:u{n}"))
        mods.extend(u.get("mods", []))        # классовая вещь: правит пассивку и навыки класса
    for n, a in enumerate(item.get("affixes", [])):
        if a["kind"] == "stat":
            add(*_stat_mods(xd, it["stat_affixes"][a["id"]], tier))
        else:
            spec = {"trigger": a["trigger"], "do": [a["effect"]], "cond": a.get("cond")}
            rules.append(make_rule(xd, spec, tier, f"{item['uid']}:{n}"))
    return mods, extra, rules


def affix_text(xd, a, tier):
    it = xd["items"]
    if a["kind"] == "stat":
        s = it["stat_affixes"][a["id"]]
        if "pct" in s:
            v = s["pct"] * tier_k(xd, tier) * 100
        elif "reaction" in s:
            v = s["reaction"] * tier_k(xd, tier) * 100
        else:
            v = (s.get("add") or s.get("speed") or s.get("skill_cd") or s.get("ap_regen")) * _soft(tier) * 100
        return s["text"].format(v=f"{v:.0f}")
    t = it["triggers"][a["trigger"]]
    e = it["effects"][a["effect"]]
    ch = t.get("chance", 1.0)
    ch = min(0.6, ch * (1 + 0.15 * (tier - 1))) if ch < 1.0 else 1.0
    p = next((x.get("atk_pct") for x in e["do"] if x.get("atk_pct")), 0) * (1 + 0.25 * (tier - 1)) * 100
    h = next((x.get("hp_pct") for x in e["do"] if x.get("hp_pct")), 0) * (1 + 0.25 * (tier - 1)) * 100
    txt = t["text"] + (f" ({ch * 100:.0f}%)" if ch < 1.0 else "") + ": " + e["text"].format(p=f"{p:.0f}", h=f"{h:.0f}")
    if a.get("cond"):
        txt += ", " + it["conditions"][a["cond"]]["text"]
    return txt


def base_text(xd, item):
    """Строки базы вещи: «+20% урона атак» и т.п."""
    it = xd["items"]
    names = {"atk_damage": "урона атак", "power": "силы навыков", "hp": "здоровья"}
    out = []
    stats_list = list(it["bases"][item["base"]]["stats"])
    if item.get("unique"):
        stats_list += it["uniques"][item["unique"]].get("stats", [])
    for st in stats_list:
        tier = item["tier"]
        if "pct" in st:
            out.append(f"+{st['pct'] * tier_k(xd, tier) * 100:.0f}% {names.get(st['stat'], st['stat'])}")
        elif "flat" in st:
            out.append(f"+{st['flat'] * tier} брони")
        elif st.get("stat") == "ap_max":
            out.append(f"+{st['add']} AP")
        elif st.get("stat") == "lifesteal":
            out.append(f"вампиризм {st['add'] * _soft(tier) * 100:.0f}%")
        elif st.get("extra") == "crit":
            out.append(f"+{st['add'] * _soft(tier) * 100:.0f}% крита")
        elif st.get("extra") == "crit_mult":
            out.append(f"+{st['add'] * _soft(tier) * 100:.0f}% урона крита")
        elif st.get("extra") == "dodge":
            out.append(f"+{st['add'] * _soft(tier) * 100:.0f}% уклонения")
        elif st.get("stat") == "atk_cooldown":
            out.append(f"атаки {'медленнее' if st['mult'] > 1 else 'быстрее'} на {abs(st['mult'] - 1) * 100:.0f}%")
        elif st.get("stat") == "move_time":
            out.append(f"шаг медленнее на {(st['mult'] - 1) * 100:.0f}%")
        elif st.get("stat") == "ap_regen":
            out.append(f"AP быстрее на {(1 - st['mult']) * 100:.0f}%")
        elif "skill_cd" in st:
            out.append(f"перезарядка навыков −{(1 - st['skill_cd']) * 100:.0f}%")
    return out


def item_lines(xd, item):
    """Описание вещи для экрана: база, свойства, особенность уникальной."""
    out = base_text(xd, item)
    if item.get("unique"):
        out.append(xd["items"]["uniques"][item["unique"]]["desc"])
    out += [affix_text(xd, a, item["tier"]) for a in item.get("affixes", [])]
    return out


def item_name(item):
    """Имя с тиром: «Кольчуга живучести II» (тир растёт с актом и перековкой)."""
    return item["name"] + ("", "", " II", " III")[min(3, item["tier"])]


def item_price(xd, item):
    return int(xd["items"]["rarities"][item["rarity"]]["price"] * (1 + 0.6 * (item["tier"] - 1)))


# ---------- герой похода ----------

class Hero:
    """Герой таверны и похода. Всё, что растёт в походе (уровень, ранги, ветки, вещи), сбрасывается с концом."""

    def __init__(self, d):
        self.uid = d["uid"]
        self.name = d["name"]
        self.cls = d["cls"]
        self.rank = d.get("rank", 1)
        self.trait = d.get("trait")
        self.skills = list(d["skills"])
        self.doctrine = d.get("doctrine")
        self.level = d.get("level", 1)
        self.xp = d.get("xp", 0)
        self.points = dict(d.get("points") or {a: 0 for a in ATTRS})
        self.sp = d.get("sp", 0)                        # невыбранные улучшения (карты навыков)
        self.uses = {k: int(v) for k, v in (d.get("uses") or {}).items()}   # применения навыков за поход
        self.pick_offer = d.get("pick_offer")           # выпавшие карты улучшения — до выбора
        self.ranks = {k: int(v) for k, v in (d.get("ranks") or {}).items()}
        self.branches = {k: tuple(v) for k, v in (d.get("branches") or {}).items()}
        self.gear = {k: v for k, v in (d.get("gear") or {}).items() if v}
        self.hp = d.get("hp")
        self.wounded = bool(d.get("wounded"))
        self.autocast = copy.deepcopy(d.get("autocast") or {})
        self.gifts = list(d.get("gifts") or [])         # личные дары похода
        self.perks = list(d.get("perks") or [])         # личные последствия событий: {"name", "mods"}
        self.solo = bool(d.get("solo"))                 # герой режима «Одиночка»: до 5 навыков + ультимейт
        self.vet = dict(d.get("vet") or {})             # ветеран таверны: {"runs", "wins", "chapters"}
        self.quivers = list(d.get("quivers") or [])     # лучник: выбранные колчаны (1 / 6 / 11 уровень)
        self.ac_order = list(d.get("ac_order") or [])   # приоритет автокаста (порядок навыков)
        self.ac_reserve = dict(d.get("ac_reserve") or {})   # резерв AP под навыки выше: {навык: AP}
        self.falls = int(d.get("falls", 0))              # падений в этом походе: третье — гибель
        self.chronicle = list(d.get("chronicle") or [])  # летопись героя (навсегда): [{"text", "kind", "run"}]
        self.feats = dict(d.get("feats") or {})          # счётчики подвигов (навсегда): убийства, боссы…
        self.titles = list(d.get("titles") or [])        # прозвища за подвиги (навсегда), последнее — главное
        self.dorm = bool(d.get("dorm"))                  # живёт в общежитии таверны (выкуплен)
        self.task = d.get("task")                        # на поручении: {"id", "left", "chance", "with": [uid]}
        self.rest = int(d.get("rest", 0))                # ранен на поручении: пропускает столько походов
        self.arts = list(d.get("arts") or [])            # надетые артефакты: uid из хранилища таверны

    def to_dict(self):
        return {"uid": self.uid, "name": self.name, "cls": self.cls, "rank": self.rank, "trait": self.trait,
                "skills": self.skills, "doctrine": self.doctrine, "level": self.level, "xp": self.xp,
                "points": self.points, "sp": self.sp, "ranks": self.ranks,
                "branches": {k: list(v) for k, v in self.branches.items()}, "gear": self.gear, "hp": self.hp,
                "wounded": self.wounded, "autocast": self.autocast, "gifts": self.gifts, "perks": self.perks,
                "uses": self.uses, "pick_offer": self.pick_offer, "solo": self.solo, "vet": self.vet,
                "quivers": self.quivers, "ac_order": self.ac_order, "ac_reserve": self.ac_reserve,
                "falls": self.falls, "chronicle": self.chronicle, "feats": self.feats, "titles": self.titles,
                "dorm": self.dorm, "task": self.task, "rest": self.rest, "arts": self.arts}

    @property
    def rpg(self):
        return {"level": self.level, "xp": 0, "points": self.points}

    def rank_of(self, sid):
        return self.ranks.get(sid, 1)

    def sp_spent(self, xd):
        """Выборы, вложенные в ветки (ранги растут от применения навыков — их не вернуть)."""
        h = xd["config"]["hero"]
        return sum(sum(h["branch_cost"][:t]) for b, t in self.branches.values())


def merge_bonus(mods):
    """Бонусы к одному стату складываются: «+50% здоровья» и «+40% здоровья» = +90%, а не ×2.1.
    Множители mult (стат или навык) сводятся в один: 1 + Σ(mult − 1); add и прочее — как есть."""
    out, stat_k, skill_k = [], {}, {}
    for m in mods:
        if "stat" in m and set(m) <= {"stat", "mult"}:
            stat_k[m["stat"]] = stat_k.get(m["stat"], 0.0) + (m["mult"] - 1)
        elif "skill" in m and set(m) <= {"skill", "cooldown_mult", "amount_mult"}:
            d = skill_k.setdefault(m["skill"], {})
            for k in ("cooldown_mult", "amount_mult"):
                if k in m:
                    d[k] = d.get(k, 0.0) + (m[k] - 1)
        else:
            out.append(m)
    for st, k in stat_k.items():
        out.append({"stat": st, "mult": round(max(0.2, 1 + k), 4)})
    for sid, d in skill_k.items():
        out.append({"skill": sid, **{k: round(max(0.3, 1 + v), 4) for k, v in d.items()}})
    return out


def fix_kit(data, h):
    """Набор героя под нынешние навыки класса: старый или сломанный набор (нет механики, нет облика к навыкам
    медведя, нет тотема к пульсу…) пересобирается; ультимейт — всегда четвёртым."""
    pool = set(story_meta.all_skills(data, h.cls)) | set(story_meta.notes_of(data, h.cls))
    ults = story_meta.ults_of(data, h.cls)
    ult = next((s for s in h.skills if s in ults), None) or (
        random.Random(f"ult:{h.uid}").choice(ults) if ults else None)      # свой ультимейт: старый — случайный
    slot = [s for s in h.skills if s in pool and s not in ults]
    n = story_meta.slots(data)
    extra = 2                                  # слоты D, F одиночки: выученные навыки остаются и у ветерана
    if not n <= len(slot) <= n + extra or not story_meta.kit_ok(data, h.cls, slot[:n]):
        h.skills = story_meta.random_kit(data, h.cls, random.Random(str(h.uid)))
    else:
        h.skills = slot[:n] + ([ult] if ult else []) + slot[n:]
    h.ranks = {k: v for k, v in h.ranks.items() if k in h.skills}
    h.doctrine = None                          # доктрины — только в сюжете
    h.branches = {k: v for k, v in h.branches.items() if k in h.skills}
    return h


def new_recruit(data, xd, rng, uid, classes, rank_weights, used_names=()):
    """Случайный герой таверны: класс, имя, черта, ранг, 3 навыка из пула класса (первый — базовый), вещь."""
    tav = xd["tavern"]
    cls = rng.choice(classes)
    names = [n for n in tav["names"] if n not in used_names] or tav["names"]
    keys = sorted(rank_weights, key=int)
    rank = int(rng.choices(keys, [rank_weights[k] for k in keys])[0])
    rk = tav["ranks"][str(rank)]
    skills = story_meta.random_kit(data, cls, rng)        # цельный набор: механика класса + ультимейт на R
    doctrine = None                                      # доктрины — только в сюжете
    item = make_item(xd, rng, 1, rk["rarity"], uid=f"{uid}-0")
    h = Hero({"uid": uid, "name": rng.choice(names), "cls": cls, "rank": rank,
              "trait": rng.choice(sorted(tav["traits"])), "skills": skills, "doctrine": doctrine,
              "level": rk["level"], "gear": {item["slot"]: item}})
    h.sp = rk["level"] - 1
    h.points = auto_points(data, h)
    return h


def auto_points(data, h, points=None):
    """Свободные очки атрибутов — в основной атрибут класса (и немного в второй по росту)."""
    pts = dict(points or {a: 0 for a in ATTRS})
    free = stats.points_total(data, {"level": h.level}) - sum(pts.values())
    c = data.stats_mode["classes"][h.cls]
    order = sorted(ATTRS, key=lambda a: -c["gain"][a])
    for i in range(max(0, free)):
        pts[order[0] if i % 3 else order[1]] += 1
    return pts


# ---------- поход ----------

class Expedition:
    def __init__(self, data, heroes, seed=None, gold=None, chapter="swamp", tier=0, solo=False, vows=None,
                 build=None, arts=None):
        self.data = data                       # expedition_data(...)
        self.arts = dict(arts or {})           # артефакты отряда (копии из хранилища): {uid: артефакт}
        self.loot = {}                         # материалы для мастерских, добытые в походе
        self.chapter = chapter if chapter in data.expedition.get("chapters", {"swamp": 1}) else "swamp"
        self.xd = chapter_view(data.expedition, self.chapter)
        self.solo = solo                       # режим «Одиночка»: один герой, меньше врагов, камера за героем
        self.vows = {k: v for k, v in (vows or {}).items() if v}     # обеты тяжести: {id: ступень}
        self.build = dict(build or {})                               # уровни построек таверны на этот поход
        self.cfg = run_cfg(self.xd, solo, self.vows, self.build)
        self.trophies = {}                     # трофеи глав, добытые в этом походе
        self.seed = seed if seed is not None else random.randrange(1_000_000)
        self.rng = random.Random(self.seed)
        self.heroes = [fix_kit(data, h if isinstance(h, Hero) else Hero(h)) for h in heroes]
        self.tier = tier                       # сложность похода: 0 — Странник, 1 — Ветеран, 2 — Легенда
        self.gold = self.cfg["start_gold"] if gold is None else gold
        self.act = 0
        self.nodes = {}
        self.node = None
        self.path = []
        self.flags = {}
        self.curses = []
        self.bag = []
        self.pending = []                    # узлы сюжетных нитей на следующие акты: {"act", "event", "ahead", ...}
        self.boss_override = None
        self.battle_mods = []                  # последствия на ближайшие бои: засада, ослабленные враги…
        self.guests = []                       # союзники-гости на N боёв
        self.boss_mods = []                    # изменения финального боя (ослаблен, с подмогой…)
        self.heat = 0                          # Жар (глава с извержением): растёт с шагами, на порогах — лава
        self.heat_hits = 0                     # сколько порогов Жара пройдено в этом акте
        self.lava_next = []                    # узлы, которые зальёт следующее извержение (видно на карте)
        self.news = []                         # что случилось на последнем шаге (извержение) — для карты
        self.mats = {}                         # руда и редкие металлы (глава с ковкой)
        self.seen_events = []
        self.result = None                   # None | "victory" | "defeat"
        self.counts = {"battle": 0, "elite": 0, "boss": 0, "event": 0}
        self.formation = None
        self.after_battle = []               # действия события, которые сработают после победы
        self.stage = None                    # где сейчас игрок внутри узла (для продолжения после выхода)
        self.uid_n = 0
        self.saves = 0
        self.autocast_mode = "default"         # начальный автокаст навыков: default | on | off (выбор в таверне)
        self.dead = []                         # погибшие в походе (третье падение): их записи для зала славы
        for h in self.heroes:
            h.falls = 0
            self.note(h, "start", f"Ушёл в поход: {self.xd['chapters'].get(self.chapter, {}).get('name', self.chapter)}"
                                  f", {self.xd['config']['tiers'][self.tier]['name'].lower()}")
        for h in self.heroes:                  # лучник: выбор колчанов, положенных по уровню
            self.fix_quivers(h)
        self.new_map()
        for _ in range(int(vow_sum(self.xd, self.vows, "curses"))):     # обет рока: поход начинается с проклятиями
            free = [c for c in sorted(self.xd["curses"]) if c not in self.curses]
            if free:
                self.add_curse(self.rng.choice(free))

    # ---------- хранение ----------

    def to_dict(self):
        return {"version": VERSION, "seed": self.seed, "chapter": self.chapter, "heroes": [h.to_dict() for h in self.heroes],
                "gold": self.gold, "act": self.act, "nodes": self.nodes, "node": self.node, "path": self.path,
                "flags": self.flags, "curses": self.curses, "bag": self.bag,
                "pending": self.pending, "boss_override": self.boss_override, "seen_events": self.seen_events,
                "battle_mods": self.battle_mods, "guests": self.guests, "boss_mods": self.boss_mods,
                "result": self.result, "counts": self.counts, "formation": self.formation,
                "after_battle": self.after_battle, "stage": self.stage, "uid_n": self.uid_n,
                "saves": self.saves + 1, "tier": self.tier, "heat": self.heat, "heat_hits": self.heat_hits,
                "lava_next": self.lava_next, "mats": self.mats, "solo": self.solo, "vows": self.vows,
                "build": self.build, "trophies": self.trophies, "autocast_mode": self.autocast_mode,
                "dead": self.dead, "arts": self.arts, "loot": self.loot}

    @classmethod
    def from_dict(cls, data, d):
        x = cls.__new__(cls)
        x.data = data
        x.chapter = d.get("chapter", "swamp")
        x.xd = chapter_view(data.expedition, x.chapter)
        x.solo = d.get("solo", False)
        x.vows, x.build, x.trophies = d.get("vows", {}), d.get("build", {}), d.get("trophies", {})
        x.arts, x.loot = dict(d.get("arts") or {}), dict(d.get("loot") or {})
        x.cfg = run_cfg(x.xd, x.solo, x.vows, x.build)
        x.seed = d["seed"]
        x.saves = d.get("saves", 0)
        x.rng = random.Random(f"{x.seed}:{x.saves}:{len(d.get('path', []))}")
        x.heroes = [fix_kit(x.data, Hero(h)) for h in d["heroes"]]
        x.tier = d.get("tier", 0)
        x.battle_mods = d.get("battle_mods", [])
        x.guests = d.get("guests", [])
        x.boss_mods = d.get("boss_mods", [])
        x.heat, x.heat_hits = d.get("heat", 0), d.get("heat_hits", 0)
        x.lava_next, x.mats = d.get("lava_next", []), d.get("mats", {})
        x.news = []
        x.autocast_mode = d.get("autocast_mode", "default")
        x.dead = list(d.get("dead") or [])
        for key in ("gold", "act", "nodes", "node", "path", "flags", "curses", "bag", "pending",
                    "boss_override", "seen_events", "result", "counts", "formation", "after_battle", "stage",
                    "uid_n"):
            setattr(x, key, copy.deepcopy(d.get(key)))
        x.after_battle = x.after_battle or []
        x.formation = x.formation or None
        for h in x.heroes:                     # старое сохранение: лучнику — выбор колчанов
            x.fix_quivers(h)
        return x

    def new_uid(self, prefix="i"):
        self.uid_n += 1
        return f"{prefix}{self.uid_n}"

    # ---------- карта ----------

    @property
    def act_def(self):
        return self.xd["acts"][self.act]

    @property
    def layers(self):
        return self.cfg["map"]["layers"]

    def new_map(self):
        """Карта акта: слои с развилками. Первый — бой, предпоследний — лагерь (и торговец), последний — босс.
        В середине — бои, события, элита, торговец и лагерь по весам; хотя бы одна элита и два события."""
        rng = self.rng
        layers = self.layers
        w = self.act_def.get("weights") or self.cfg["map"]["weights"]
        nodes, grid = {}, []
        last = len(layers) - 1
        for L, count in enumerate(layers):
            row = []
            for i in range(count):
                if L == 0:
                    t = "battle"
                elif L == last:
                    t = "boss"
                elif L == last - 1:
                    t = tuple(self.act_def.get("rest", ("camp", "shop")))[i % 2] if count > 1 else "camp"
                elif L == 1:
                    t = rng.choice(["battle", "event"])
                else:
                    kinds = [k for k in w if not (k == "elite" and L < 3)]
                    t = rng.choices(kinds, [w[k] for k in kinds])[0]
                nid = f"{self.act}-{L}-{i}"
                nodes[nid] = {"id": nid, "layer": L, "idx": i, "count": count, "type": t, "next": [],
                              "encounter": None, "event": None, "label": None, "thread": False}
                row.append(nid)
            grid.append(row)
        middle = [n for row in grid[3:-2] for n in row]
        if middle and not any(nodes[n]["type"] == "elite" for n in middle):
            nodes[rng.choice(middle)]["type"] = "elite"
        mid2 = [n for row in grid[1:-2] for n in row]
        while sum(nodes[n]["type"] == "event" for n in mid2) < 2:
            cand = [n for n in mid2 if nodes[n]["type"] == "battle"]
            if not cand:
                break
            nodes[rng.choice(cand)]["type"] = "event"
        for L in range(len(grid) - 1):
            cur, nxt = grid[L], grid[L + 1]
            pos = lambda nid: (nodes[nid]["idx"] + 0.5) / nodes[nid]["count"]
            for a in cur:
                ranked = sorted(nxt, key=lambda b: abs(pos(a) - pos(b)))
                nodes[a]["next"].append(ranked[0])
                if len(ranked) > 1 and abs(pos(a) - pos(ranked[1])) < 0.45 and rng.random() < 0.6:
                    nodes[a]["next"].append(ranked[1])
            for b in nxt:
                if not any(b in nodes[a]["next"] for a in cur):
                    nearest = min(cur, key=lambda a: abs(pos(a) - pos(b)))
                    nodes[nearest]["next"].append(b)
        self.nodes = nodes
        self.node = None
        self.path = []
        self._assign_encounters()
        for spec in [p for p in self.pending if p.get("act") == self.act]:
            self.pending.remove(spec)
            self.insert_thread_node(spec, layer=spec.get("ahead", 2))
        if self.heat_on():
            self.heat_hits = sum(1 for t in self.heat_cfg()["thresholds"] if self.heat >= t)
            self.plan_lava()

    def _assign_encounters(self):
        pools = self.act_def["pools"]
        last = None
        for n in sorted(self.nodes.values(), key=lambda n: (n["layer"], n["idx"])):
            if n["type"] in ("battle", "elite") and n["encounter"] is None:
                pool = [e for e in pools[n["type"]] if e != last] or pools[n["type"]]
                last = self.rng.choice(pool)
                n["encounter"] = enc_index(self.data, last)
        boss = next(n for n in self.nodes.values() if n["type"] == "boss")
        boss["encounter"] = enc_index(self.data, self.act_def["boss"])

    def boss_encounter(self):
        """Финальный бой акта; в третьем акте нити могут его сменить."""
        if self.act == len(self.xd["acts"]) - 1:
            if self.boss_override:
                return enc_index(self.data, self.boss_override)
            for rule in self.xd.get("boss_rules", []):     # правила главы: Жар на пределе — проснулся вулкан
                if self.meets(rule["requires"]):
                    return enc_index(self.data, rule["enc"])
            if self.flags.get("witch_broken") or self.flags.get("witch_enemy"):
                return enc_index(self.data, "ex_witch_wrath")
        return enc_index(self.data, self.act_def["boss"])

    def insert_thread_node(self, spec, layer=None):
        """Узел сюжетной нити: на `ahead` слоёв впереди текущего (не дальше лагеря), связан со всем вокруг.
        Если в этом акте места уже нет — узел ждёт начала следующего акта. Возвращает id узла или None."""
        last = len(self.layers) - 1
        cur = self.nodes[self.node]["layer"] if self.node else -1
        L = layer if layer is not None else cur + spec.get("ahead", 2)
        L = max(1, min(last - 2, L))
        if L <= cur:
            L = cur + 1
        if L > last - 1:
            if self.act < len(self.xd["acts"]) - 1:
                self.pending.append(dict(spec, act=self.act + 1, ahead=2))
            return None
        row = sorted([n for n in self.nodes.values() if n["layer"] == L], key=lambda n: n["idx"])
        nid = f"{self.act}-{L}-t{len(row)}"
        count = len(row) + 1
        for n in row:
            n["count"] = count
        node = {"id": nid, "layer": L, "idx": len(row), "count": count, "type": spec.get("type", "event"),
                "next": [], "encounter": None, "event": spec.get("event"), "label": spec.get("label"),
                "thread": True}
        if node["type"] in ("battle", "elite") and spec.get("encounter"):
            node["encounter"] = enc_index(self.data, spec["encounter"])
        self.nodes[nid] = node
        for n in list(self.nodes.values()):
            if n["layer"] == L - 1 and (L - 1 > cur or n["id"] == self.node):
                n["next"].append(nid)
        node["next"] = [n["id"] for n in self.nodes.values() if n["layer"] == L + 1]
        return nid

    def available(self):
        if self.result:
            return []
        if self.node is None:
            return [n["id"] for n in self.nodes.values() if n["layer"] == 0]
        return list(self.nodes[self.node]["next"])

    def enter(self, nid):
        if nid not in self.available():
            raise ValueError("узел недоступен")
        self.node = nid
        self.path.append(nid)
        n = self.nodes[nid]
        if self.heat_on():                     # каждый шаг разогревает кузню; новости — на карту
            self.news = self.add_heat(self.heat_cfg()["step"])
        if n["type"] == "boss":
            n["encounter"] = self.boss_encounter()
        if n["type"] == "event" and not n["event"]:
            n["event"] = self.pick_event()
        if n["type"] == "shop":
            n["stock"] = self.shop_stock()
        self.stage = {"node": nid, "kind": n["type"]}
        return n

    def depth(self, node=None):
        n = node or self.nodes.get(self.node) or {"layer": 0}
        return self.act * len(self.layers) + n["layer"]

    def enemy_scale(self, node=None):
        n = node or self.nodes[self.node]
        e = self.cfg["enemy"]
        L = n["layer"]
        hp = e["act_hp"][self.act] * (1 + e["layer_hp"] * L)          # по слоям карты — линейно
        dmg = e["act_dmg"][self.act] * (1 + e["layer_dmg"] * L)
        t = self.tier_now()
        hp, dmg = hp * t["hp"], dmg * t["dmg"]
        for m in self.battle_mods:                 # последствия выборов: засада, ослабленные враги
            hp *= m.get("hp", 1.0)
            dmg *= m.get("dmg", 1.0)
        hp *= 1 + vow_sum(self.xd, self.vows, "hp")             # обеты тяжести
        dmg *= 1 + vow_sum(self.xd, self.vows, "dmg")
        if n.get("molten"):                        # огненный бой (залит лавой): враги крепче
            hp *= self.heat_cfg()["molten_hp"] if self.heat_on() else 1.15
        boss = n["type"] == "boss" and self.act == len(self.xd["acts"]) - 1
        if boss:
            for b in self.boss_mods:
                hp *= b.get("hp", 1.0)
                dmg *= b.get("dmg", 1.0)
        out = {"hp": round(hp, 3), "damage": round(dmg, 3), "power": round(dmg, 3), "level": 1 + self.depth(n)}
        adds = [a for m in self.battle_mods for a in m.get("adds", [])]
        horde = int(vow_sum(self.xd, self.vows, "adds"))         # обет орды: в каждом бою ещё враги
        if horde and n["type"] in ("battle", "elite", "event"):
            pool = [e for e in self.act_enemies() if not self.data.enemies[e].get("boss")]
            rng = random.Random(f"{self.seed}:horde:{n['id']}")
            adds += [rng.choice(pool) for _ in range(horde)] if pool else []
        if boss:
            adds += [a for b in self.boss_mods for a in b.get("adds", [])]
        guests = [g["unit"] for g in self.guests] + ([u for b in self.boss_mods for u in b.get("guests", [])] if boss else [])
        if adds:
            out["extra_adds"] = adds
        if guests:
            out["guests"] = guests
        if self.solo:                              # одиночка: врагов в бою меньше, у босса — меньше свиты
            out["solo"] = {k: self.cfg["solo"][k] for k in ("keep", "boss_keep", "phase_max")}
        if self.heat_on():                         # опасности поля чаще с Жаром; в огненном бою — ещё чаще
            hc = self.heat_cfg()
            st = self.heat_stage() + (1 if n.get("molten") else 0)
            out["arena_rate"] = round(1 + hc["arena_per_stage"] * st, 3)
            out["arena_extra"] = [dict(e) for e in self.act_def.get("arena", [])]
            out["heat"] = self.heat
        if self.tier:                              # тяжёлые сложности: подкрепление, механики, фазы боссов
            out["tier"] = {**t, "pool": self.act_enemies(), "boss_node": n["type"] == "boss"}
        return out

    def tier_now(self):
        """Сложность в этом акте: значения-списки — по актам (к третьему акту — в полную силу)."""
        a = min(self.act, 2)
        return {k: (v[min(a, len(v) - 1)] if isinstance(v, list) else v) for k, v in self.tier_def.items()}

    @property
    def tier_def(self):
        tiers = self.cfg["tiers"]
        return tiers[max(0, min(len(tiers) - 1, self.tier))]

    def act_enemies(self):
        """Все виды врагов из боёв этого акта — пул для подкрепления."""
        pools = self.act_def["pools"]
        out = set()
        for eid in pools.get("battle", []) + pools.get("elite", []):
            try:
                enc = self.data.encounters[enc_index(self.data, eid)]
            except KeyError:
                continue
            out |= {e["type"] for e in enc["enemies"]}
        return sorted(out)

    def battle_skills(self, h):
        """Навыки героя в бой: слоты и ультимейт (клавиша R), когда герой дорос до него."""
        ult = story_meta.ult_of(self.data, h.cls, h.skills)
        regular = [s for s in h.skills if s != ult]
        if not self.solo:                          # в отряде — три навыка и ультимейт (D, F — только в одиночке)
            regular = regular[:story_meta.slots(self.data)]
        out = regular[:story_meta.slots(self.data)] + ([ult] if ult in h.skills and ult_open(self.data, h) else [])
        out += regular[story_meta.slots(self.data):]
        mech = story_meta.mech_of(self.data, h.cls)    # кнопка механики класса (Фитиль) — всегда, клавиша F
        if mech and mech in self.data.skills and mech not in out:
            out.append(mech)
        return out

    @property
    def difficulty(self):
        return self.act_def["difficulty"]

    # ---------- герои в бою ----------

    def party_mods(self):
        """Общее на отряд — только проклятия (небольшие минусы, снимаются в лагере-торговце)."""
        mods = []
        for cid in self.curses:
            mods += self.xd["curses"][cid].get("mods", [])
        return mods

    def proto(self, h, party=True):
        """Прототип героя для боя. party=False — без проклятий отряда (чистые числа для листа героя)."""
        hc = self.cfg["hero"]
        der = stats.derive(self.data, h.cls, h.rpg)
        mods = list(der["mods"])
        lvl = h.level - 1                      # рост с уровнем — линейный: +N% за уровень, не сложный процент
        mods += [{"stat": "atk_damage", "mult": round(1 + hc["dmg_per_level"] * lvl, 4)},
                 {"stat": "power", "mult": round(1 + hc["dmg_per_level"] * lvl, 4)},
                 {"stat": "hp", "mult": round(1 + hc["hp_per_level"] * lvl, 4)}]
        gear = []                              # бонусы вещей, даров, черты и отряда — складываются (merge_bonus)
        extra, rules = {}, []
        for item in h.gear.values():
            m, e, r = item_effects(self.xd, item)
            gear += m
            rules += r
            for k, v in e.items():
                extra[k] = extra.get(k, 0) + v
        vs, react = {}, 1.0
        for k, v in list(extra.items()):
            if k.startswith("vs:"):
                vs[k[3:]] = 1 + v
            elif k == "reaction":
                react += v
        for n, gid in enumerate(h.gifts):
            g = self.xd["gifts"][gid]
            gear += g.get("mods", [])
            for k, v in g.get("extra", {}).items():
                extra[k] = extra.get(k, 0) + v
            for tg, k in g.get("dmg_vs", {}).items():        # +% урона по тегу — тоже складывается
                vs[tg] = vs.get(tg, 1.0) + (k - 1)
            react += g.get("reaction_mult", 1.0) - 1
            for m_, spec in enumerate(g.get("rules", [])):
                rules.append(make_rule(self.xd, spec, 1, f"{h.uid}:g{n}:{m_}"))
        if party:
            gear += self.party_mods()
        tr = self.xd["tavern"]["traits"].get(h.trait, {})
        gear += tr.get("mods", [])
        for pk in h.perks:                         # последствия событий (жертва, благословение, шрам)
            gear += pk.get("mods", [])
        titles = self.data.expedition.get("chronicle", {}).get("titles", {})
        for tid in h.titles:                       # прозвища за подвиги — небольшой бонус навсегда
            gear += titles.get(tid, {}).get("mods", [])
        if self.solo:                              # одиночка: один за отряд — здоровье, урон, AP
            gear += self.cfg["solo"]["hero_mods"]
            role = self.data.classes[h.cls].get("role", "melee")   # стрелку и магу не за кем прятаться
            gear += self.cfg["solo"].get("role_mods", {}).get(role, [])
        mods += merge_bonus(gear)
        worn = [self.arts[u] for u in h.arts if u in self.arts]
        if worn:                                   # артефакты таверны — отдельный слой (×) поверх роста похода
            from . import artifacts as AR
            am, ae, ar = AR.effects(self.xd, worn, h.uid)
            mods += am
            rules += ar
            for k, v in ae.items():
                if k.startswith("vs:"):
                    vs[k[3:]] = vs.get(k[3:], 1.0) + v
                elif k == "reaction":
                    react += v
                else:
                    extra[k] = extra.get(k, 0) + v
        for k, v in tr.get("extra", {}).items():
            extra[k] = extra.get(k, 0) + v
        for sid, r in h.ranks.items():
            if r > 1:
                mods.append({"skill": sid, "amount_mult": round(1 + hc["rank_amount"] * (r - 1), 3),
                             "cooldown_mult": round(1 - hc["rank_cooldown"] * (r - 1), 3)})
        if h.wounded:
            k = self.cfg["wound_mult"]
            mods += [{"stat": "atk_damage", "mult": k}, {"stat": "power", "mult": k}, {"stat": "hp", "mult": k}]
        p = build_proto(self.data, h.cls, (), (), h.branches, mods, None, None, skills=self.battle_skills(h),
                        doctrine=None)        # доктрины — только в сюжете
        stats.apply_to_proto(p, der, self.data, h.cls)
        p["crit"] = round(min(0.75, p["crit"] + extra.get("crit", 0)), 3)
        p["dodge"] = round(min(0.45, p["dodge"] + extra.get("dodge", 0)), 3)
        p["crit_mult"] = round(p["crit_mult"] + extra.get("crit_mult", 0), 3)
        p["rules"] = rules
        if vs:
            p["dmg_vs"] = {k: round(v, 3) for k, v in vs.items()}
        if react != 1.0:
            p["reaction_mult"] = round(react, 3)
        p["level"] = h.level
        if h.quivers:                              # лучник: колчаны в бой, с 15 уровня — сильнее
            p["quivers"] = list(h.quivers)
            p["quiver_boost"] = h.level >= self.data.config["quiver_boost_level"]
        p["start_ap"] = max(0.0, self.data.config.get("start_ap", 0.5) + vow_sum(self.xd, self.vows, "start_ap"))
        if story_meta.notes_of(self.data, h.cls):
            p["melodies"] = story_meta.melodies(self.data, h.cls, h.level)
        p["name"] = h.name
        p["class_name"] = self.data.classes[h.cls]["name"]
        return p

    def max_hp(self, h):
        return self.proto(h)["hp"]

    def hp_of(self, h):
        mx = self.max_hp(h)
        return mx if h.hp is None else max(1, min(mx, h.hp))

    def combat_squad(self):
        out = []
        for h in self.heroes:
            p = self.proto(h)
            self.preset_autocast(h, p["skill_defs"])
            out.append({"cls": h.cls, "proto": p, "hp": self.hp_of(h), "autocast": h.autocast or None,
                        "ac_order": h.ac_order, "ac_reserve": h.ac_reserve})
        return out

    def preset_autocast(self, h, skill_defs=None):
        """Режим похода «всё включено / выключено»: навыкам без своей настройки — начальное состояние по режиму.
        Уже настроенные (переключённые в бою) не трогает; новые навыки похода получают тот же режим."""
        if self.autocast_mode not in ("on", "off"):
            return
        from . import autocast as AC
        defs = skill_defs if skill_defs is not None else self.proto(h)["skill_defs"]
        for sid, sk in defs.items():
            if sid not in h.autocast:
                st = AC.default_setting(sk)
                st["on"] = self.autocast_mode == "on"
                h.autocast[sid] = st

    def heal_all(self, pct):
        for h in self.heroes:
            mx = self.max_hp(h)
            h.hp = min(mx, self.hp_of(h) + int(round(mx * pct)))
            if h.hp >= mx:
                h.hp = None

    def hurt(self, h, pct):
        mx = self.max_hp(h)
        h.hp = max(1, self.hp_of(h) - int(round(mx * pct)))

    def _keep_hp(self, fn):
        """Изменение героя (вещь, ранг, благословение) не лечит и не ранит: доля HP сохраняется."""
        frac = {h.uid: self.hp_of(h) / max(1, self.max_hp(h)) for h in self.heroes}
        fn()
        for h in self.heroes:
            if h.hp is not None:
                h.hp = max(1, int(round(self.max_hp(h) * frac[h.uid])))

    # ---------- колчаны лучника ----------

    def has_quivers(self, h):
        return bool(story_meta.cfg(self.data)["classes"].get(h.cls, {}).get("quivers"))

    def quivers_due(self, h):
        """Сколько колчанов положено герою на его уровне (выбор на 1 / 6 / 11)."""
        if not self.has_quivers(h):
            return 0
        return sum(1 for lv in self.data.config["quiver_levels"] if h.level >= lv)

    def quiver_pending(self, h):
        return max(0, self.quivers_due(h) - len(h.quivers))

    def fix_quivers(self, h):
        """Выборов хватает на положенные колчаны (новичок 1 уровня — сразу выбор первого)."""
        need = self.quiver_pending(h)
        if need > h.sp:
            h.sp = need

    # ---------- опыт и рост ----------

    def xp_next(self, h):
        x = self.cfg["xp"]
        return x["next_base"] + x["next_per_level"] * h.level

    def gain_xp(self, h, amount):
        """Опыт → уровни: каждый уровень — % урона и HP, атрибуты (сами по классу + свободные очки) и очко навыка."""
        ups = 0
        cap = self.cfg["hero"]["level_cap"]
        h.xp += int(amount)
        while h.level < cap and h.xp >= self.xp_next(h):
            h.xp -= self.xp_next(h)
            frac = self.hp_of(h) / max(1, self.max_hp(h))
            h.level += 1
            if h.level % self.cfg["hero"]["pick_every"] == 0:      # ключевой уровень — карты улучшения навыков
                h.sp += self.cfg["hero"]["skill_points"]
            if self.solo and h.level in self.cfg["solo"]["slot_levels"]:   # одиночка: открылся слот — новый навык
                h.sp += 1
            if self.has_quivers(h) and h.level in self.data.config["quiver_levels"]:   # лучник: новый колчан
                h.sp += 1
            h.points = auto_points(self.data, h, h.points)
            if h.hp is not None:
                h.hp = max(1, int(round(self.max_hp(h) * frac)))
            ups += 1
        return ups

    def battle_xp(self, node_type):
        x = self.cfg["xp"]
        return int((x["battle_base"] + x["battle_per_depth"] * self.depth()) * x["node_mult"].get(node_type, 1.0))

    # ---------- ранги от применения и карты улучшений ----------

    def uses_for_rank(self, h, sid, rank):
        """Сколько применений навыка нужно до ранга rank (ультимейт — в несколько раз меньше)."""
        hc = self.cfg["hero"]
        need = hc["rank_uses"][rank - 2]
        if sid == story_meta.ult_of(self.data, h.cls, h.skills):
            need = max(1, need // hc["ult_uses_div"])
        return need

    def rank_progress(self, h, sid):
        """(применений, нужно до следующего ранга) или None — ранг максимальный."""
        r = h.rank_of(sid)
        if r >= self.cfg["hero"]["max_rank"]:
            return None
        return h.uses.get(sid, 0), self.uses_for_rank(h, sid, r + 1)

    def learn_from(self, h, uses):
        """Применения навыков за бой → ранги. Возвращает [(навык, новый ранг)]."""
        out = []
        for sid, n in uses.items():
            if sid not in h.skills:
                continue
            h.uses[sid] = h.uses.get(sid, 0) + n
            while True:
                pr = self.rank_progress(h, sid)
                if pr is None or pr[0] < pr[1]:
                    break
                self._keep_hp(lambda sid=sid: h.ranks.__setitem__(sid, h.rank_of(sid) + 1))
                out.append((sid, h.rank_of(sid)))
        return out

    def pick_cards(self, h):
        """Карты улучшения героя (выпадают один раз и ждут выбора): ступени веток навыков из набора; не хватает —
        мастерство (ранг навыка), совсем нечего — закалка."""
        if h.sp <= 0:
            return []
        if h.pick_offer:
            return h.pick_offer
        hc = self.cfg["hero"]
        n = hc["pick_cards_big"] if h.level % hc["pick_big_every"] == 0 else hc["pick_cards"]
        n += self.library_cards().get("cards", 0)
        rng = random.Random(f"{self.seed}:{h.uid}:{h.level}:{h.sp}:{len(h.branches)}:{self.flag('reroll')}")
        if self.quiver_pending(h):                 # лучник: колчан на выбор — 1 из 2 ещё не взятых
            free = [a for a in self.data.config["arrows"] if a not in h.quivers]
            rng.shuffle(free)
            h.pick_offer = [{"type": "quiver", "arrow": a} for a in free[:2]]
            return h.pick_offer
        learn = self.learnable(h)
        if learn:                                  # одиночка: свободный слот — сначала новый навык
            rng.shuffle(learn)
            h.pick_offer = [{"type": "learn", "skill": sid} for sid in learn[:n]]
            return h.pick_offer
        cards = []
        usable = self.battle_skills(h)             # закрытый ультимейт (до 10 ур.) не улучшается
        for sid in usable:
            for b in sorted(self.data.branches.get(sid, {})):
                nxt = self.branch_next(h, sid, b)
                if nxt and h.rank_of(sid) >= nxt[1]:
                    cards.append({"type": "branch", "skill": sid, "branch": b,
                                  "tier": h.branches.get(sid, (b, 0))[1] + 1})
        rng.shuffle(cards)
        # не больше двух карт одного навыка — выбор разнообразнее
        picked, per = [], {}
        for c in cards:
            if per.get(c["skill"], 0) < 2 and len(picked) < n:
                picked.append(c)
                per[c["skill"]] = per.get(c["skill"], 0) + 1
        ranks = [sid for sid in usable if h.rank_of(sid) < hc["max_rank"]]
        rng.shuffle(ranks)
        for sid in ranks:
            if len(picked) >= n:
                break
            picked.append({"type": "rank", "skill": sid})
        while len(picked) < n:
            picked.append({"type": "stat", "stat": ["hp", "atk_damage", "power"][len(picked) % 3]})
        h.pick_offer = picked
        return picked

    def slots_open(self, h):
        """Сколько обычных навыков у героя может быть (одиночке слоты D, F открываются по уровням)."""
        n = story_meta.slots(self.data)
        if self.solo:
            n += sum(1 for lv in self.cfg["solo"]["slot_levels"] if h.level >= lv)
        return n

    def learnable(self, h):
        """Навыки класса, которые одиночка может выучить в свободный слот."""
        if not self.solo or story_meta.notes_of(self.data, h.cls):
            return []
        ult = story_meta.ult_of(self.data, h.cls, h.skills)
        have = [s for s in h.skills if s != ult]
        if len(have) >= self.slots_open(h):
            return []
        return [s for s in story_meta.unlocked_skills(self.data, h.cls, h.level) if s not in h.skills]

    def rerolls_left(self):
        return self.library_cards().get("rerolls", 0) - self.flag("reroll")

    def reroll_cards(self, h):
        """Библиотека таверны: перебросить карты улучшения героя (за поход — сколько даёт постройка)."""
        if self.rerolls_left() <= 0 or h.sp <= 0:
            return False
        self.flags["reroll"] = self.flag("reroll") + 1
        h.pick_offer = None
        self.pick_cards(h)
        return True

    def card_hero(self, h, card):
        """Копия героя, как если бы карту взяли: для демонстрации и цифр «было → станет»."""
        hh = Hero(h.to_dict())
        if card["type"] == "branch":
            hh.branches[card["skill"]] = (card["branch"], card["tier"])
        elif card["type"] == "rank":
            hh.ranks[card["skill"]] = h.rank_of(card["skill"]) + 1
        elif card["type"] == "learn":
            hh.skills.append(card["skill"])
        elif card["type"] == "quiver":
            hh.quivers.append(card["arrow"])
        else:
            hh.perks.append({"name": "", "mods": [{"stat": card["stat"], "mult": 1.08}]})
        return hh

    def card_text(self, h, card):
        """(заголовок, строки) карты улучшения для экрана."""
        sk = self.data.skills.get(card.get("skill"), {})
        if card["type"] == "learn":
            keys = "QWER" + "DG"
            ult = story_meta.ult_of(self.data, h.cls, h.skills)
            k = len([s for s in h.skills if s != ult])
            return f"Новый навык: {sk.get('name', '')}", [f"в слот {('D', 'G')[min(1, k - 3)] if k >= 3 else keys[k]}",
                                                         sk.get("desc", "")]
        if card["type"] == "branch":
            br = self.data.branches[card["skill"]][card["branch"]]
            tier = br["tiers"][card["tier"] - 1]
            cur = h.branches.get(card["skill"])
            head = f"{sk.get('name', '')}: {tier['name']}"
            sub = (f"ветка «{br['name']}», ступень {card['tier']}" + ("" if cur else " — другая ветка закроется"))
            full = next((m["set"]["desc"] for m in tier.get("mods", []) if m.get("set", {}).get("desc")), None)
            now = self.proto(h, party=False)["skill_defs"].get(card["skill"], sk).get("desc", "")
            if full and full != now:
                return head, [sub, f"Сейчас: {now}", f"Станет: {full}"]
            return head, [sub, tier.get("desc", "")]
        if card["type"] == "quiver":
            a = self.data.config["arrows"][card["arrow"]]
            n = len(h.quivers) + 1
            return f"Колчан {n}: {a['name']}", [a["desc"], "Стрелы колчанов чередуются: каждый выстрел — следующий",
                                                "Числа — от силы навыков лучника"]
        if card["type"] == "rank":
            r = h.rank_of(card["skill"])
            hc = self.cfg["hero"]
            return (f"{sk.get('name', '')}: мастерство",
                    [f"ранг {r} → {r + 1}", f"+{hc['rank_amount'] * 100:.0f}% силы, "
                                           f"−{hc['rank_cooldown'] * 100:.0f}% перезарядки"])
        name = {"hp": "Закалка", "atk_damage": "Твёрдая рука", "power": "Сосредоточенность"}[card["stat"]]
        what = {"hp": "здоровья", "atk_damage": "урона атак", "power": "силы навыков"}[card["stat"]]
        return name, [f"+8% {what} до конца похода"]

    def take_card(self, h, i):
        """Взять карту улучшения: тратит выбор, следующая порция карт выпадет заново."""
        cards = self.pick_cards(h)
        if not 0 <= i < len(cards):
            return False
        c = cards[i]
        if c["type"] == "quiver":
            if not self.quiver_pending(h) or c["arrow"] in h.quivers:
                return False
            h.quivers.append(c["arrow"])
            h.sp -= 1
            h.pick_offer = None
            return True
        if c["type"] == "learn":
            if c["skill"] not in self.learnable(h):
                return False
            self._keep_hp(lambda: h.skills.append(c["skill"]))
            h.sp -= 1
            h.pick_offer = None
            return True
        if c["type"] == "branch":
            hc = self.cfg["hero"]
            cost = hc["branch_cost"][c["tier"] - 1]
            h.sp += cost - 1                           # карта — один выбор, сколько бы ни стоила ступень
            if not self.take_branch(h, c["skill"], c["branch"]):
                h.sp -= cost - 1
                return False
        elif c["type"] == "rank":
            self._keep_hp(lambda: h.ranks.__setitem__(c["skill"], h.rank_of(c["skill"]) + 1))
            h.uses[c["skill"]] = max(h.uses.get(c["skill"], 0), self.uses_for_rank(h, c["skill"], h.rank_of(c["skill"])))
            h.sp -= 1
        else:
            name = self.card_text(h, c)[0]
            self._keep_hp(lambda: h.perks.append({"name": name, "desc": self.card_text(h, c)[1][0],
                                                  "mods": [{"stat": c["stat"], "mult": 1.08}]}))
            h.sp -= 1
        h.pick_offer = None
        return True

    def can_rank(self, h, sid):
        return h.sp > 0 and h.rank_of(sid) < self.cfg["hero"]["max_rank"]

    def rank_up(self, h, sid):
        if not self.can_rank(h, sid):
            return False
        self._keep_hp(lambda: h.ranks.__setitem__(sid, h.rank_of(sid) + 1))
        h.sp -= 1
        return True

    def branch_next(self, h, sid, branch):
        """Следующая ступень ветки: (стоимость, нужный ранг) или None, если ветку не взять."""
        hc = self.cfg["hero"]
        if sid not in self.data.branches:
            return None
        cur = h.branches.get(sid)
        if cur and cur[0] != branch:
            return None
        tier = (cur[1] if cur else 0) + 1
        if tier > len(self.data.branches[sid][branch]["tiers"]) or tier > len(hc["branch_cost"]):
            return None
        return hc["branch_cost"][tier - 1], hc["branch_rank"][tier - 1]

    def take_branch(self, h, sid, branch):
        nxt = self.branch_next(h, sid, branch)
        if not nxt or h.sp < nxt[0] or h.rank_of(sid) < nxt[1]:
            return False
        tier = h.branches.get(sid, (branch, 0))[1] + 1
        self._keep_hp(lambda: h.branches.__setitem__(sid, (branch, tier)))
        h.sp -= nxt[0]
        return True

    def respec(self, h):
        """Сброс веток (в лагере): выборы возвращаются, карты выпадут заново. Ранги от применения остаются."""
        back = h.sp_spent(self.xd)
        self._keep_hp(lambda: h.branches.clear())
        h.sp += back
        h.pick_offer = None

    def add_point(self, h, attr):
        if stats.points_free(self.data, h.rpg) <= 0:
            return False
        self._keep_hp(lambda: h.points.__setitem__(attr, h.points.get(attr, 0) + 1))
        return True

    # ---------- снаряжение ----------

    def item_tier(self):
        return self.act + 1

    def tag_items(self):
        """Сколько в походе вещей, которые сами вешают теги (сумка, герои, прилавки)."""
        items = self.all_items() + [o["item"] for n in self.nodes.values() for o in (n.get("stock") or []) if o]
        return sum(1 for i in items if has_tags(self.xd, i))

    def new_item(self, pool="normal", slot=None, unique=None, rarity=None):
        rarity = rarity or ("unique" if unique else roll_rarity(self.xd, self.rng, pool))
        allow = self.tag_items() < self.cfg.get("tag_items_max", 2)
        owned = {i.get("unique") for i in self.all_items() if i.get("unique")}
        if rarity == "unique" and not unique:
            classes = {h.cls for h in self.heroes}
            uq = self.xd["items"]["uniques"]
            free = [u for u in uq if u not in owned and uq[u].get("class", "any") in classes | {"any"}
                    and not uq[u].get("masterpiece")                       # шедевры — только с наковальни
                    and (allow or not has_tags(self.xd, {"unique": u, "affixes": []}))]
            mine = [u for u in free if uq[u].get("class") in classes]
            if mine and self.rng.random() < 0.6:  # классовые вещи отряда выпадают чаще
                free = mine
            if not free:
                rarity = "epic"
            else:
                unique = self.rng.choice(sorted(free))
        return make_item(self.xd, self.rng, self.item_tier(), rarity, slot, unique, self.new_uid(), allow_tags=allow)

    def fits(self, h, item):
        """Классовая уникальная вещь — только своему классу."""
        cls = self.xd["items"]["uniques"].get(item.get("unique") or "", {}).get("class")
        return cls is None or cls == h.cls

    def all_items(self):
        return list(self.bag) + [i for h in self.heroes for i in h.gear.values()]

    def equip(self, h, uid):
        item = next((i for i in self.bag if i["uid"] == uid), None)
        if item is None or not self.fits(h, item):
            return False
        old = h.gear.get(item["slot"])

        def do():
            self.bag.remove(item)
            h.gear[item["slot"]] = item
            if old:
                self.bag.append(old)
        self._keep_hp(do)
        return True

    def unequip(self, h, slot):
        if slot in h.gear:
            self._keep_hp(lambda: self.bag.append(h.gear.pop(slot)))

    def upgrade_item(self, item):
        """Перековка: тир вещи +1 (до тира текущего акта + 1)."""
        if item["tier"] >= 3:
            return False
        self._keep_hp(lambda: item.__setitem__("tier", item["tier"] + 1))
        return True

    def best_upgrade_targets(self, n):
        items = [i for h in self.heroes for i in h.gear.values() if i["tier"] < 3]
        items.sort(key=lambda i: (i["tier"], -["common", "rare", "epic", "unique"].index(i["rarity"])))
        return items[:n]

    def sell(self, uid):
        item = next((i for i in self.bag if i["uid"] == uid), None)
        if not item:
            return 0
        self.bag.remove(item)
        price = item_price(self.xd, item) // 3
        self.gold += price
        return price

    # ---------- личные дары ----------

    def gift_ok(self, h, gid):
        """Подходит ли дар герою: любой / по классу / по роли; один дар — один раз."""
        g = self.xd["gifts"][gid]
        if gid in h.gifts:
            return False
        if g.get("group") and any(self.xd["gifts"].get(x, {}).get("group") == g["group"] for x in h.gifts):
            return False                           # «души» и прочие взаимоисключающие дары — одна на героя
        if g.get("any"):
            return True
        return h.cls in g.get("classes", []) or self.data.classes[h.cls]["role"] in g.get("roles", [])

    def gift_offers(self, n=3, ids=None):
        """Дары на выбор: подходящие отряду, классовые — чаще. ids — конкретные (из события)."""
        if ids:
            return [g for g in ids if any(self.gift_ok(h, g) for h in self.heroes)]
        cand = []
        for gid, g in self.xd["gifts"].items():
            if g.get("thread") or not any(self.gift_ok(h, gid) for h in self.heroes):
                continue
            w = 3.0 if g.get("classes") else 1.5 if g.get("roles") else 1.0
            cand.append((gid, w))
        out = []
        while cand and len(out) < n:
            gid = self.rng.choices([c[0] for c in cand], [c[1] for c in cand])[0]
            out.append(gid)
            cand = [c for c in cand if c[0] != gid]
        return out

    def give_gift(self, h, gid):
        if not self.gift_ok(h, gid):
            return False
        self._keep_hp(lambda: h.gifts.append(gid))
        return True

    def add_curse(self, cid):
        self._keep_hp(lambda: self.curses.append(cid))

    def remove_curse(self):
        if self.curses:
            self._keep_hp(lambda: self.curses.pop(0))
            return True
        return False


    # ---------- бой ----------

    # ---------- летопись, подвиги, гибель ----------

    def chron_cfg(self):
        return self.data.expedition.get("chronicle", {})

    def max_falls(self):
        return int(self.chron_cfg().get("max_falls", 3))

    def note(self, h, kind, text):
        """Запись в летопись героя (навсегда): что, где, в каком по счёту походе."""
        h.chronicle.append({"kind": kind, "text": text, "run": h.vet.get("runs", 0) + 1, "chapter": self.chapter})
        if len(h.chronicle) > 200:
            h.chronicle = h.chronicle[-200:]

    def count_feats(self, h, u, node, won):
        f = h.feats
        t = u.tally
        for k in ("kills", "dealt", "healed", "shielded"):
            f[k] = f.get(k, 0) + int(t.get(k, 0))
        f["battles"] = f.get("battles", 0) + 1
        if won and node["type"] in ("elite", "boss"):
            f[node["type"] + "_kills"] = f.get(node["type"] + "_kills", 0) + 1
        if not u.alive:
            f["falls"] = f.get("falls", 0) + 1

    def award_titles(self):
        """Новые прозвища за подвиги: [(герой, прозвище)]. Бонус прозвища — навсегда (в прототипе)."""
        out = []
        for h in self.heroes:
            for tid, td in self.chron_cfg().get("titles", {}).items():
                if tid in h.titles:
                    continue
                if all(h.feats.get(k, 0) >= v for k, v in td["need"].items()):
                    self._keep_hp(lambda h=h, tid=tid: h.titles.append(tid))
                    self.note(h, "title", f"Получил прозвище «{td['name']}»: {td['desc']}")
                    out.append((h.name, td["name"]))
        return out

    def bury(self, h, reason):
        """Третье падение: герой погибает насовсем. Вещи — в сумку отряда, дары — наследием живым (на выбор)."""
        self.note(h, "death", f"Погиб: {reason}, акт {self.act + 1}")
        for item in h.gear.values():
            self.bag.append(item)
        rec = {"hero": h.to_dict(), "name": h.name, "reason": reason, "act": self.act + 1, "gifts": list(h.gifts)}
        self.dead.append(rec)
        self.heroes = [x for x in self.heroes if x is not h]
        return rec

    def player_units(self, combat):
        return [u for u in combat.units if u.team == PLAYER and not u.summon and not u.obj][:len(self.heroes)]

    def finish_battle(self, combat, formation=None):
        """Итог боя: HP, раны, опыт, золото. Возвращает сводку для экрана наград."""
        if formation:
            h_ = combat.grid.h
            self.formation = [[x, round(y * 5 / (h_ - 1))] for x, y in formation] if h_ != 6 else formation
        node = self.nodes[self.node]
        units = self.player_units(combat)
        fallen = []
        learned = []
        dying = []                                   # третье падение за поход — гибель насовсем
        for h, u in zip(self.heroes, units):
            h.autocast = u.autocast
            h.ac_order, h.ac_reserve = list(u.ac_order), dict(u.ac_reserve)     # приоритет, поправленный в бою
            if combat.result == "victory":
                learned += [(h.name, self.data.skills[sid]["name"], r) for sid, r in self.learn_from(h, u.uses)]
            self.count_feats(h, u, node, combat.result == "victory")
            if u.alive:
                h.hp = u.hp
            else:
                h.hp = 1
                h.falls += 1
                enc = self.data.encounters[node["encounter"]]["name"] if node.get("encounter") is not None else "бою"
                if h.falls >= self.max_falls() and combat.result == "victory":
                    dying.append(h)
                    continue
                if not h.wounded:
                    self._keep_hp(lambda h=h: setattr(h, "wounded", True))
                    h.hp = 1
                self.note(h, "fall", f"Пал в бою «{enc}» (акт {self.act + 1}) — рана, падений: {h.falls}/"
                                     f"{self.max_falls()}")
                fallen.append(h)
        legacy = [self.bury(h, f"погиб в бою «{self.data.encounters[node['encounter']]['name']}»"
                               if node.get("encounter") is not None else "погиб в бою") for h in dying]
        self.last_stats = combat.battle_stats()
        if combat.result != "victory":
            self.result = "defeat"
            self.stage = None
            return {"result": "defeat", "stats": self.last_stats}
        kind = node["type"] if node["type"] in ("elite", "boss") else "battle"
        self.counts[kind] = self.counts.get(kind, 0) + 1
        trophy = (self.xd.get("chapters", {}).get(self.chapter) or {}).get("trophy")
        enc = self.data.encounters[node["encounter"]] if node.get("encounter") is not None else {}
        if trophy and (kind == "boss" or (node["type"] == "event" and enc.get("kind") == "boss")):
            n_ = 1 + (self.cfg["trophy_final"] if kind == "boss" and self.act >= len(self.xd["acts"]) - 1 else 0)
            self.trophies[trophy] = self.trophies.get(trophy, 0) + n_     # трофеи главы — на постройки таверны
        for lst in (self.battle_mods, self.guests):
            for m in lst:
                m["battles"] -= 1
            lst[:] = [m for m in lst if m["battles"] > 0]
        xp = self.battle_xp(kind)
        ups = []
        for h in self.heroes:
            n = self.gain_xp(h, xp)
            ups += [h] * n
        g = self.cfg["gold"]
        gold = int(g[kind] * g["act_mult"][self.act] * self.gold_mult())
        ore = 0
        if self.forge_on():                        # руда за бой; огненный — вдвое, плюс металл
            fc = self.forge_cfg()
            ore = fc["battle_ore"][kind] * (2 if node.get("molten") else 1)
            self.add_mat("ore", ore)
            if node.get("molten") or kind in ("elite", "boss"):
                metal = self.rng.choice(["obsidian", "obsidian", "starsteel"]) if kind != "boss" else "emberheart"
                self.add_mat(metal, 1)
                out_metal = metal
            if node.get("molten"):
                gold = int(gold * 1.5)
        self.gold += gold
        got = self.drop_loot(kind, node)
        self.heal_all(self.cfg["post_battle_heal"])
        extra = self.apply_ops(self.after_battle, None) if self.after_battle else []
        self.after_battle = []
        out = {"result": "victory", "kind": kind, "xp": xp, "gold": gold, "level_ups": ups, "fallen": fallen,
               "extra": extra, "learned": learned, "stats": self.last_stats,
               "dead": [x["name"] for x in legacy], "legacy_gifts": [g for x in legacy for g in x["gifts"]],
               "titles": self.award_titles()}
        if kind in ("elite", "boss"):
            enc = self.data.encounters[node["encounter"]]["name"] if node.get("encounter") is not None else ""
            for h in self.heroes:
                self.note(h, kind, ("Одолел босса: " if kind == "boss" else "Разбил элиту: ") + enc)
        if ore:
            out["extra"] = [f"Руда +{ore}" + (f", {self.xd['mats'][out_metal]['name'].lower()} +1"
                                              if (node.get("molten") or kind in ("elite", "boss")) else "")] + extra
        if got:
            out["loot"] = got
            names = self.xd.get("materials", {})
            out["extra"] = list(out["extra"]) + ["Материалы: " + ", ".join(
                f"{names[k]['name']} +{v}" for k, v in got.items())]
        if self.heat_on() and kind != "boss":      # бой разогревает кузню
            out["extra"] = out["extra"] + self.add_heat(self.heat_cfg()["battle"])
        if kind == "boss":
            out["act_done"] = self.act
            if self.act >= len(self.xd["acts"]) - 1:
                self.result = "victory"
        self.stage = {"node": self.node, "kind": "reward"}
        return out

    def drop_loot(self, kind, node):
        """Материалы для мастерских: общие — за бои, редкие главы — с элиты и боссов, звёздная пыль — с боссов
        (чаще на высоких ступенях). Количество растёт со ступенью."""
        md = self.cfg.get("mat_drops")
        mats = self.xd.get("materials", {})
        if not md:
            return {}
        rng = random.Random(f"{self.seed}:loot:{node['id']}:{self.act}")
        t = self.tier_def
        k = t.get("mats", 1.0)
        got = {}

        def add(m, n):
            if n > 0 and m in mats:
                got[m] = got.get(m, 0) + n
        final = kind == "boss" and self.act >= len(self.xd["acts"]) - 1
        spec = md.get(kind, md["battle"])
        weights = md["common"].get(self.chapter) or {m: 1 for m, v in mats.items() if not v.get("rare")}
        lo, hi = spec.get("common", [0, 0])
        n = rng.randint(lo, hi)
        n = int(n * k) + (1 if rng.random() < n * k - int(n * k) else 0)
        keys = sorted(weights)
        for _ in range(n):
            add(rng.choices(keys, [weights[x] for x in keys])[0], 1)
        rare = next((m for m, v in mats.items() if v.get("rare") and v.get("chapter") == self.chapter), None)
        r = spec.get("rare")
        if rare and r:
            add(rare, rng.randint(*r) if isinstance(r, list) else (1 if rng.random() < r * k else 0))
        if kind == "boss":
            if rng.random() < t.get("stardust", 0.1):
                add("stardust", 1)
            if final:
                fs = md.get("final", {})
                if rare and fs.get("rare"):
                    add(rare, rng.randint(*fs["rare"]))
                add("stardust", fs.get("stardust", 0))
        for m, v in got.items():
            self.loot[m] = self.loot.get(m, 0) + v
        return got

    def gold_mult(self):
        return max(0.2, 1 + sum(self.xd["tavern"]["traits"].get(h.trait, {}).get("gold", 0) for h in self.heroes)
                   + vow_sum(self.xd, self.vows, "gold"))

    def next_act(self):
        """Босс акта побеждён: следующий акт — новая карта, отряд полностью здоров, раны зажили."""
        self.act += 1
        if self.heat_on():                      # между актами кузня остывает, но не до конца
            self.heat = int(self.heat * self.heat_cfg()["act_carry"])
        for h in self.heroes:
            h.wounded = False
            h.hp = None
        self.new_map()
        self.stage = None

    def reward_offers(self, kind):
        """Награда боя на выбор. Бой: вещь, вещь или золото, лечение или очко навыка. Босс и первая элита акта —
        личный дар одному герою; остальная элита — редкие вещи (вещь сверху даётся сразу)."""
        g = self.cfg["gold"]["act_mult"][self.act]
        first_elite = kind == "elite" and not self.flags.get(f"elite_gift_{self.act}")
        if kind == "boss" or first_elite:
            if first_elite:
                self.flags[f"elite_gift_{self.act}"] = 1
            return [{"type": "gift", "id": gid} for gid in self.gift_offers(self.cfg.get("gift_choices", 2))]
        if kind == "elite":
            return [{"type": "item", "item": self.new_item("elite", rarity=r)} for r in ("rare", "rare", "epic")]
        out = [{"type": "item", "item": self.new_item("normal")}]
        out.append(self.rng.choice([{"type": "item", "item": self.new_item("normal")},
                                    {"type": "gold", "amount": int(45 * g)}]))
        out.append(self.rng.choice([{"type": "heal", "pct": 0.35}, {"type": "skill_point", "amount": 1}]))
        return out

    def bonus_item(self, kind):
        """Элита и босс дают вещь сверх выбора."""
        return self.new_item("boss" if kind == "boss" else "elite")

    def apply_offer(self, o, hero=None):
        """hero — кому дар (для дара обязателен)."""
        if o["type"] == "gift":
            return self.give_gift(hero, o["id"]) if hero is not None else False
        if o["type"] == "item":
            self.bag.append(o["item"])
        elif o["type"] == "gold":
            self.gold += o["amount"]
        elif o["type"] == "heal":
            self.heal_all(o["pct"])
        elif o["type"] == "skill_point":
            for h in self.heroes:
                h.sp += o["amount"]
        return True

    # ---------- лагерь и торговец ----------

    def camp_rest(self):
        for h in self.heroes:
            if h.wounded:
                self._keep_hp(lambda h=h: setattr(h, "wounded", False))
        self.heal_all(self.cfg["camp_heal"])

    def camp_cool(self):
        """Лагерь в кузнях: залить ближние горны — Жар ниже (извержение откладывается)."""
        self.heat = max(0, self.heat - self.heat_cfg().get("camp_cool", 30))
        self.heat_hits = sum(1 for t in self.heat_cfg()["thresholds"] if self.heat >= t)

    def camp_train(self):
        for h in self.heroes:
            h.sp += 1
            self.gain_xp(h, self.xp_next(h) // 2)

    def shop_stock(self):
        n = self.cfg["shop"]["items"]
        out = []
        for _ in range(n):
            it = self.new_item("shop")
            out.append({"type": "item", "item": it, "price": int(item_price(self.xd, it) * self.price_k())})
        return out

    def price_k(self):
        return [1.0, 1.5, 2.2][self.act] * self.trade_mult() * (1 + vow_sum(self.xd, self.vows, "price"))

    def rep(self, faction):
        return self.flags.get("rep:" + faction, 0)

    def trade_faction(self):
        return self.xd.get("trade_faction") or "toads"

    def trade_mult(self):
        """Торговая фракция главы (жабы на болоте, гильдия в кузнях): каждая единица репутации — цены ∓10%
        (от ×0.6 до ×2)."""
        return max(0.6, min(2.0, 1 - 0.1 * self.rep(self.trade_faction())))

    def pay_price(self, amount):
        return int(round(amount * self.trade_mult()))

    def consequences(self):
        """Что сейчас действует из-за выборов: для карты и экрана похода."""
        out = []
        tf = self.trade_faction()
        fac = self.xd.get("factions") or {"toads": "Жабы", "village": "Деревня Камышинка",
                                          "hunters": "Охотники на ведьм", "rivals": "Отряд Ржавых"}
        r = self.rep(tf)
        if r:
            out.append((f"{fac.get(tf, tf)}: {'помнят добро' if r > 0 else 'запомнили вас'} — цены "
                        f"×{self.trade_mult():.2f}", r > 0))
        for f, name in fac.items():
            v = self.rep(f)
            if v and f != tf:
                out.append((f"{name}: {'союзники' if v > 0 else 'враги'} ({v:+d})", v > 0))
        if self.heat_on():
            out.append((f"Жар кузни: {self.heat}/{self.heat_cfg()['max']}", self.heat_stage() == 0))
        for m in self.battle_mods:
            out.append((f"{m['name']} — ещё боёв: {m['battles']}", m.get("good", False)))
        for g in self.guests:
            out.append((f"С отрядом: {g['name']} — ещё боёв: {g['battles']}", True))
        for b in self.boss_mods:
            out.append((f"Финальный бой: {b['name']}", b.get("good", False)))
        return out

    def buy(self, nid, i):
        stock = self.nodes[nid].get("stock", [])
        if i >= len(stock) or stock[i] is None or self.gold < stock[i]["price"]:
            return False
        self.gold -= stock[i]["price"]
        self.bag.append(stock[i]["item"])
        stock[i] = None
        return True

    def heal_price(self):
        return int(self.cfg["shop"]["heal_price"] * self.price_k())

    def buy_heal(self):
        if self.gold < self.heal_price():
            return False
        self.gold -= self.heal_price()
        self.heal_all(self.cfg["shop"]["heal_pct"])
        return True

    def curse_price(self):
        return int(self.cfg["shop"]["curse_price"] * self.price_k())

    def buy_uncurse(self):
        if not self.curses or self.gold < self.curse_price():
            return False
        self.gold -= self.curse_price()
        return self.remove_curse()

    # ---------- события ----------

    def any_hero(self):
        """«Кто-то из отряда» в тексте события ({hero_any}) — он же получает перк с who="any"."""
        return self.heroes[(len(self.path) * 7) % len(self.heroes)]

    def _who(self, who, hero):
        if who == "all":
            return list(self.heroes)
        if who == "any" or hero is None:
            return [self.any_hero()]
        return [hero]

    # ---------- Жар и извержения (глава с mechanics.heat) ----------

    def heat_on(self):
        return bool(self.xd.get("mechanics", {}).get("heat"))

    def heat_cfg(self):
        return self.xd["mechanics"]["heat"]

    def heat_stage(self):
        """0 — тихо, 1 — тлеет, 2 — пылает, 3 — на пределе: от этого бои горячее."""
        return sum(1 for t in self.heat_cfg()["thresholds"] if self.heat >= t) if self.heat_on() else 0

    def add_heat(self, n):
        """Жар ± n. Перешёл порог — извержение заливает отмеченные узлы. Возвращает строки «что случилось»."""
        if not self.heat_on():
            return []
        hc = self.heat_cfg()
        self.heat = max(0, min(hc["max"], self.heat + n))
        lines = []
        while self.heat_hits < len(hc["thresholds"]) and self.heat >= hc["thresholds"][self.heat_hits]:
            self.heat_hits += 1
            lines += self.erupt(big=self.heat_hits == len(hc["thresholds"]))
        if self.heat_hits and self.heat < hc["thresholds"][self.heat_hits - 1]:
            self.heat_hits = sum(1 for t in hc["thresholds"] if self.heat >= t)
        return lines

    def _future(self):
        cur = self.nodes[self.node]["layer"] if self.node else -1
        nxt = set(self.available())
        return [n for n in self.nodes.values() if n["layer"] > cur and n["type"] != "boss" and n["id"] not in nxt]

    def plan_lava(self):
        """Куда пойдёт следующее извержение: узлы впереди (не ближайшие), чаще — дальше от отряда."""
        hc = self.heat_cfg()
        k = hc["flood"][min(self.heat_hits, len(hc["flood"]) - 1)]
        cand = [n for n in self._future() if n["type"] not in ("ash", "molten")]
        rng = random.Random(f"{self.seed}:lava:{self.act}:{self.heat_hits}:{len(self.path)}:{self.flag('lava_shift')}")
        rng.shuffle(cand)
        cand.sort(key=lambda n: -n["layer"] + rng.random() * 3)
        self.lava_next = [n["id"] for n in cand[:k]]

    def erupt(self, big=False):
        """Лава заливает отмеченные узлы: бои становятся огненными (сильнее, больше руды и золота), остальное
        сгорает в пепел. Большое извержение (предел Жара) — сгорают все лагеря и лавки впереди, ожоги отряду, Жар
        сбрасывается. После — новые отметки."""
        hc = self.heat_cfg()
        targets = [self.nodes[i] for i in self.lava_next if i in self.nodes]
        if big:
            targets += [n for n in self._future() if n["type"] in ("camp", "shop", "anvil") and n not in targets]
        burnt, molten = 0, 0
        for n in targets:
            if n["type"] in ("battle", "elite"):
                n["molten"] = True
                molten += 1
            elif n["type"] not in ("boss", "ash"):
                n["was"] = n["type"]
                n["type"] = "ash"
                n["event"] = None
                burnt += 1
        lines = [f"Извержение! Лава залила узлы: сгорело {burnt}, огненных боёв {molten}"]
        if big:
            if hc.get("big_curse"):
                self.add_curse(hc["big_curse"])
                lines.append(f"Проклятие: {self.xd['curses'][hc['big_curse']]['name']}")
            self.heat = hc["after_big"]
            self.heat_hits = sum(1 for t in hc["thresholds"] if self.heat >= t)
        self.plan_lava()
        self.flags["eruptions"] = self.flags.get("eruptions", 0) + 1
        return lines

    # ---------- руда и ковка (глава с mechanics.forge) ----------

    def forge_on(self):
        return bool(self.xd.get("mechanics", {}).get("forge"))

    def forge_cfg(self):
        return self.xd["mechanics"]["forge"]

    def mat(self, key):
        return self.mats.get(key, 0)

    def add_mat(self, key, n):
        self.mats[key] = max(0, self.mats.get(key, 0) + n)

    def can_pay(self, cost):
        return all(self.mat(k) >= v for k, v in cost.items())

    def pay_mats(self, cost):
        if not self.can_pay(cost):
            return False
        for k, v in cost.items():
            self.add_mat(k, -v)
        return True

    def mats_line(self, cost):
        return ", ".join(f"{self.xd['mats'][k]['name']} {v}" for k, v in cost.items() if v)

    def anvil_offer(self, node):
        """Что предлагает наковальня узла (один раз — повторный заход не перебросит): базы по слотам и свойства."""
        if node.get("forge"):
            return node["forge"]
        fc = self.forge_cfg()
        rng = random.Random(f"{self.seed}:anvil:{node['id']}")
        it = self.xd["items"]
        props = [{"kind": "stat", "id": s} for s in rng.sample(
            sorted(s for s in it["stat_affixes"] if not it["stat_affixes"][s].get("dot")), fc["stat_offers"])]
        allow = self.tag_items() < self.cfg.get("tag_items_max", 2)
        props += [roll_proc(self.xd, rng, allow) for _ in range(fc["proc_offers"])]
        dot_ids = sorted(s for s in it["stat_affixes"] if it["stat_affixes"][s].get("dot"))
        if dot_ids:
            aux = random.Random()
            aux.setstate(rng.getstate())
            if aux.random() < 0.5:
                props.append({"kind": "stat", "id": aux.choice(dot_ids)})
        bases = {}
        for slot in SLOTS:
            opts = sorted(b for b, v in it["bases"].items() if v["slot"] == slot)
            bases[slot] = rng.choice(opts)
        node["forge"] = {"props": props, "bases": bases}
        return node["forge"]

    def prop_cost(self, prop):
        fc = self.forge_cfg()
        return dict(fc["cost_stat"] if prop["kind"] == "stat" else fc["cost_proc"])

    def forge_cost(self, props):
        total = dict(self.forge_cfg()["cost_base"])
        for p in props:
            for k, v in self.prop_cost(p).items():
                total[k] = total.get(k, 0) + v
        return total

    def forge_item(self, node, slot, picks, temper=False):
        """Выковать вещь: база слота наковальни и выбранные свойства (1–3, по ним редкость). temper — закалка сердцем
        углей: тир вещи выше на 1. Возвращает вещь (в сумку) или None."""
        off = self.anvil_offer(node)
        picks = sorted(set(picks))[:3]
        if not picks or any(not 0 <= i < len(off["props"]) for i in picks):
            return None
        props = [copy.deepcopy(off["props"][i]) for i in picks]
        cost = self.forge_cost(props)
        if temper:
            cost["emberheart"] = cost.get("emberheart", 0) + 1
        if not self.pay_mats(cost):
            return None
        rarity = {1: "common", 2: "rare", 3: "epic"}[len(props)]
        base = off["bases"][slot]
        it = self.xd["items"]
        name = it["bases"][base]["name"]
        first = next((a for a in props if a["kind"] == "stat"), None)
        if first:
            name += " " + it["stat_affixes"][first["id"]]["name"]
        item = {"uid": self.new_uid(), "base": base, "slot": slot, "tier": self.item_tier() + (1 if temper else 0),
                "rarity": rarity, "name": name, "unique": None, "affixes": props,
                "forged": True}
        self.bag.append(item)
        self.flags["forged"] = self.flags.get("forged", 0) + 1
        return item

    def reforge_cost(self, item):
        return dict(self.forge_cfg()["cost_upgrade"])

    def reforge(self, item):
        """Перековать: тир вещи +1 за руду и обсидиан."""
        if not self.pay_mats(self.reforge_cost(item)):
            return False
        self.upgrade_item(item)
        return True

    def smelt_value(self, item):
        fc = self.forge_cfg()
        return fc["smelt"].get(item["rarity"], 2) + item.get("tier", 1) - 1

    def smelt(self, item):
        """Переплавить вещь из сумки в руду."""
        if item not in self.bag:
            return 0
        self.bag.remove(item)
        n = self.smelt_value(item)
        self.add_mat("ore", n)
        return n

    def masterpieces(self):
        """Шедевры главы, которые можно выковать (ещё нет у отряда; классовые — под отряд)."""
        uq = self.xd["items"]["uniques"]
        owned = {i.get("unique") for i in self.all_items()}
        classes = self.squad_classes()
        return [u for u, v in sorted(uq.items()) if v.get("masterpiece") and u not in owned
                and v.get("class", "any") in classes | {"any"}]

    def forge_masterpiece(self, uid):
        if uid not in self.masterpieces() or not self.pay_mats(self.forge_cfg()["cost_masterpiece"]):
            return None
        item = make_item(self.xd, self.rng, self.item_tier() + 1, "unique", unique=uid, uid=self.new_uid())
        self.bag.append(item)
        self.flags["masterpiece"] = self.flags.get("masterpiece", 0) + 1
        return item

    # ---------- события ----------

    def best_roller(self, check):
        """Кто бросает кубик: герой с наибольшим шансом (при равенстве — тот, у кого бонус выше)."""
        return max(self.heroes, key=lambda h: (self.chance(h, check), self.check_bonus(h, check)))

    def squad_classes(self):
        return {h.cls for h in self.heroes}

    def flag(self, key):
        return self.flags.get(key, 0)

    def meets(self, req, hero=None):
        """Условие события или варианта."""
        if not req:
            return True
        if "class_any" in req and not set(req["class_any"]) & self.squad_classes():
            return False
        if "trait_any" in req and not any(h.trait in req["trait_any"] for h in self.heroes):
            return False
        if "gold" in req and self.gold < req["gold"]:
            return False
        if "flag" in req and not self.flag(req["flag"]):
            return False
        if "not_flag" in req and self.flag(req["not_flag"]):
            return False
        for k, v in req.get("flag_at_least", {}).items():
            if self.flag(k) < v:
                return False
        if "squad_below" in req and len(self.heroes) >= min(req["squad_below"], self.cfg["squad_max"]):
            return False
        if "squad_at_least" in req and len(self.heroes) < req["squad_at_least"]:
            return False
        for f, v in req.get("rep_at_least", {}).items():
            if self.rep(f) < v:
                return False
        for f, v in req.get("rep_below", {}).items():
            if self.rep(f) >= v:
                return False
        if "pay" in req and self.gold < self.pay_price(req["pay"]):
            return False
        if "items_at_least" in req and len(self.all_items()) < req["items_at_least"]:
            return False
        if "curse_any" in req and not self.curses:
            return False
        if "level_at_least" in req and max((h.level for h in self.heroes), default=0) < req["level_at_least"]:
            return False
        for k, v in req.get("flag_below", {}).items():
            if self.flag(k) >= v:
                return False
        if "heat_at_least" in req and self.heat < req["heat_at_least"]:
            return False
        if "heat_below" in req and self.heat >= req["heat_below"]:
            return False
        for k, v in req.get("mat_at_least", {}).items():
            if self.mat(k) < v:
                return False
        return True

    def pick_event(self):
        """Событие узла: подходит к акту и отряду, «разовые» не повторяются. Нити с выполненным условием —
        с большим весом."""
        evs = self.xd["events"]
        cand = []
        for eid, e in evs.items():
            if self.act + 1 not in e.get("acts", []):
                continue
            if eid in self.seen_events and (e.get("once") or e.get("kind") == "thread"):
                continue
            if not self.meets(e.get("requires")):
                continue
            w = e.get("weight", 5)
            if eid in self.seen_events:
                w *= 0.25
            cand.append((eid, w))
        if not cand:
            return "abandoned_camp"
        return self.rng.choices([c[0] for c in cand], [c[1] for c in cand])[0]

    def event(self, eid):
        return self.xd["events"][eid]

    def start_event(self, eid):
        if eid not in self.seen_events:
            self.seen_events.append(eid)
        self.counts["event"] = self.counts.get("event", 0) + 1
        self.stage = {"node": self.node, "kind": "event", "event": eid, "step": "start"}

    def option_ok(self, opt):
        return self.meets(opt.get("requires"))

    def hero_by_class(self, classes):
        return next((h for h in self.heroes if h.cls in classes), None)

    def check_bonus(self, h, check):
        """Бонус героя к проверке: атрибут (и уровень), класс, черта."""
        c = self.cfg["checks"]
        at = stats.attrs(self.data, h.cls, h.rpg)[check["attr"]]
        bonus = min(c["attr_max"], int(at // c["attr_div"])) + h.level // c["level_div"]
        if h.cls in check.get("classes", []):
            bonus += c["class_bonus"]
        tr = self.xd["tavern"]["traits"].get(h.trait, {})
        if h.trait in check.get("traits", []):
            bonus += c["trait_bonus"]
        tc = tr.get("checks", {})
        bonus += tc.get(check["attr"], 0) + tc.get("all", 0)
        for tag in check.get("tags", []):
            bonus += tc.get(tag, 0)
        if h.wounded:
            bonus -= 2
        return bonus

    def dc(self, check):
        return check["dc"] + 2 * self.act

    def chance(self, h, check):
        """Шанс успеха (натуральная 20 — всегда успех, 1 — всегда провал)."""
        need = self.dc(check) - self.check_bonus(h, check)
        wins = sum(1 for d in range(1, 21) if d == 20 or (d != 1 and d >= need))
        if self.crit_on(h) < 20 and need > 19:
            wins += 20 - self.crit_on(h)
        return min(1.0, wins / 20)

    def crit_on(self, h):
        return self.xd["tavern"]["traits"].get(h.trait, {}).get("crit_on", 20)

    def roll(self, h, check):
        d = self.rng.randint(1, 20)
        total = d + self.check_bonus(h, check)
        dc = self.dc(check)
        if d >= self.crit_on(h):
            res = "crit"
        elif d == 1:
            res = "fumble"
        else:
            res = "success" if total >= dc else "fail"
        return {"d20": d, "bonus": self.check_bonus(h, check), "total": total, "dc": dc, "result": res}

    def outcome(self, opt, res):
        """Исход варианта по броску: крит → crit или success, провал на 1 → fumble или fail."""
        if res == "crit":
            return opt.get("crit") or opt["success"]
        if res == "fumble":
            return opt.get("fumble") or opt["fail"]
        return opt["success"] if res == "success" else opt["fail"]

    def fill(self, text, hero=None, event=None):
        """Подстановка имён: {hero} — кто бросал, {class_hero} — герой нужного класса, {hero_any}, {trait_hero}."""
        names = {"hero": hero.name if hero else (self.heroes[0].name if self.heroes else "")}
        cls_req = None
        if event:
            req = event.get("requires") or {}
            cls_req = req.get("class_any")
            if req.get("trait_any"):
                th = next((h for h in self.heroes if h.trait in req["trait_any"]), None)
                names["trait_hero"] = th.name if th else names["hero"]
        ch = self.hero_by_class(cls_req) if cls_req else None
        names["class_hero"] = ch.name if ch else names["hero"]
        names.setdefault("trait_hero", names["hero"])
        names["hero_any"] = self.any_hero().name if self.heroes else ""
        out = re.sub(r"\{price:(\d+)\}", lambda m: str(self.pay_price(int(m.group(1)))), text)
        for k, v in names.items():
            out = out.replace("{" + k + "}", v)
        return out

    def apply_ops(self, ops, hero):
        """Действия исхода события. Возвращает строки «что изменилось»; бой — словарь {"battle": ...} в конце."""
        lines = []
        for op in ops or []:
            who = op.get("who")
            targets = [hero] if who == "hero" and hero else list(self.heroes)
            if "gold" in op:
                g = op["gold"]
                if g > 0:
                    g = int(g * self.cfg["gold"]["act_mult"][self.act] * self.gold_mult())
                self.gold = max(0, self.gold + g)
                lines.append(f"Золото {'+' if g >= 0 else ''}{g}")
            elif "heal" in op:
                self.heal_all(op["heal"])
                lines.append(f"Отряд лечится на {op['heal'] * 100:.0f}%")
            elif "hurt" in op:
                for h in targets:
                    self.hurt(h, op["hurt"])
                lines.append((f"{hero.name}" if who == "hero" and hero else "Отряд") +
                             f" теряет {op['hurt'] * 100:.0f}% здоровья")
            elif "xp" in op:
                amount = int(op["xp"] * (1 + 0.6 * self.act))
                ups = 0
                for h in targets:
                    ups += self.gain_xp(h, amount)
                lines.append(f"Опыт +{amount}" + (f" (новых уровней: {ups})" if ups else ""))
            elif "skill_point" in op:
                for h in targets:
                    h.sp += op["skill_point"]
                lines.append(f"Карты улучшения +{op['skill_point']}" + (f" — {hero.name}" if who == "hero" and hero
                                                                        else " каждому"))
            elif "item" in op:
                spec = op["item"]
                if isinstance(spec, dict):
                    item = self.new_item("elite", slot=spec.get("slot"), unique=spec.get("unique"))
                else:
                    item = self.new_item(spec)
                self.bag.append(item)
                lines.append(f"Добыча: {item_name(item)}")
            elif "gift" in op:
                gid = op["gift"]
                offers = self.gift_offers(self.cfg.get("gift_choices", 2)) if gid == "random" else self.gift_offers(ids=[gid])
                if offers:
                    lines.append({"gift": offers})
            elif "curse" in op:
                cid = op["curse"]
                if cid == "random":
                    cid = self.rng.choice(sorted(self.xd["curses"]))
                self.add_curse(cid)
                lines.append(f"Проклятие: {self.xd['curses'][cid]['name']}")
            elif "remove_curse" in op:
                if self.remove_curse():
                    lines.append("Проклятие снято")
            elif "wound" in op:
                h = hero if op["wound"] == "hero" and hero else self.rng.choice(self.heroes)
                self._keep_hp(lambda h=h: setattr(h, "wounded", True))
                lines.append(f"{h.name} ранен до отдыха")
            elif "flag" in op:
                key = op["flag"]
                self.flags[key] = self.flags.get(key, 0) + op.get("add", 1)
                if key == "shard":
                    lines.append(f"Осколков янтаря: {self.flags[key]}")
            elif "recruit" in op:
                if len(self.heroes) < self.cfg["squad_max"]:
                    h = self.join_recruit()
                    lines.append(f"{h.name} ({self.data.classes[h.cls]['name']}) присоединяется к отряду")
            elif "add_node" in op:
                spec = dict(op["add_node"])
                if spec.get("in_act", 0) - 1 > self.act:   # тропа появится в заданном акте (1, 2, 3)
                    self.pending.append(dict(spec, act=spec["in_act"] - 1, ahead=spec.get("ahead", 2)))
                    label = spec.get("label") or self.event(spec["event"])["title"]
                    lines.append(f"Тропа «{label}» ждёт вас в акте {spec['in_act']}")
                    continue
                nid = self.insert_thread_node(spec)
                label = spec.get("label") or self.event(spec["event"])["title"]
                lines.append(f"На карте новая тропа: {label}" if nid else f"Тропа «{label}» откроется в следующем акте")
            elif "boss" in op:
                self.boss_override = op["boss"]
                lines.append("Финальный бой изменился")
            elif "upgrade_item" in op:
                for item in self.best_upgrade_targets(op["upgrade_item"]):
                    self.upgrade_item(item)
                    lines.append(f"Перековано: {item_name(item)}")
            elif "lose_hero" in op:
                if len(self.heroes) > 1:
                    h = min(self.heroes, key=lambda x: (x.level, x.rank))
                    self.heroes.remove(h)
                    lines.append(f"{h.name} покидает отряд навсегда")
            elif "rep" in op:                         # репутация у фракции
                key = "rep:" + op["rep"]
                self.flags[key] = self.flags.get(key, 0) + op.get("add", 1)
                if op["rep"] == self.trade_faction():
                    who = (self.xd.get("factions") or {}).get(op["rep"], "Жабы")
                    lines.append(f"{who}: {'запомнили добро' if op.get('add', 1) > 0 else 'вас запомнили'} — "
                                 f"цены ×{self.trade_mult():.2f}")
                else:
                    lines.append(op.get("text") or f"Репутация {op['rep']}: {self.flags[key]:+d}")
            elif "pay" in op:                         # плата с учётом репутации у жаб
                g = self.pay_price(op["pay"])
                self.gold = max(0, self.gold - g)
                lines.append(f"Золото −{g}")
            elif "battle_mod" in op:                  # последствие на ближайшие бои
                m = dict(op["battle_mod"])
                m.setdefault("battles", 2)
                self.battle_mods.append(m)
                lines.append(f"{m['name']}: ближайшие бои ({m['battles']})")
            elif "boss_mod" in op:                    # изменение финального боя
                self.boss_mods.append(dict(op["boss_mod"]))
                lines.append(f"Финальный бой: {op['boss_mod']['name']}")
            elif "guest" in op:                       # союзник-гость на несколько боёв
                g = dict(op["guest"])
                g.setdefault("battles", 3)
                self.guests.append(g)
                lines.append(f"{g['name']} идёт с отрядом ({g['battles']} боя)")
            elif "perk" in op:                        # личное последствие героя на весь поход
                pk = op["perk"]
                hs = self._who(pk.get("who", "hero"), hero)
                for h in hs:
                    self._keep_hp(lambda h=h: h.perks.append({"name": pk["name"], "mods": pk.get("mods", []),
                                                              "desc": pk.get("desc", "")}))
                lines.append(f"{pk['name']}: " + (hs[0].name if len(hs) == 1 else "весь отряд") +
                             (f" — {pk['desc']}" if pk.get("desc") else ""))
            elif "chance" in op:                      # случайный исход без броска
                branch = op["do"] if self.rng.random() < op["chance"] else op.get("else", [])
                lines += self.apply_ops(branch, hero)
            elif "lose_item" in op:
                pool = list(self.bag) or [i for h in self.heroes for i in h.gear.values()]
                if pool:
                    it = self.rng.choice(pool)
                    if it in self.bag:
                        self.bag.remove(it)
                    else:
                        for h in self.heroes:
                            for slot, v in list(h.gear.items()):
                                if v is it:
                                    self._keep_hp(lambda h=h, slot=slot: h.gear.pop(slot))
                    lines.append(f"Потеряно: {item_name(it)}")
            elif "trait" in op:                       # новая черта героя
                h = self._who(op.get("who", "hero"), hero)[0]
                tid = op["trait"] if op["trait"] != "random" else self.rng.choice(sorted(self.xd["tavern"]["traits"]))
                h.trait = tid
                lines.append(f"{h.name}: черта «{self.xd['tavern']['traits'][tid]['name']}»")
            elif "say" in op:                         # строка-последствие для игрока
                lines.append(op["say"])
            elif "heat" in op:                        # Жар кузни ±
                n = op["heat"]
                lines.append(f"Жар {'+' if n >= 0 else ''}{n}")
                lines += self.add_heat(n)
            elif "erupt" in op:                       # извержение сейчас
                lines += self.erupt()
            elif "lava_shift" in op:                  # лава пойдёт другим путём (отметки на карте меняются)
                self.flags["lava_shift"] = self.flag("lava_shift") + 1
                if self.heat_on():
                    self.plan_lava()
                lines.append("Лава повернула: на карте новые отметки извержения")
            elif "mat" in op:                         # руда и металлы
                self.add_mat(op["mat"], op.get("add", 1))
                lines.append(f"{self.xd['mats'][op['mat']]['name']} {'+' if op.get('add', 1) >= 0 else ''}"
                             f"{op.get('add', 1)}")
            elif "gold_all" in op:
                lines.append(f"Отдано всё золото: {self.gold}")
                self.gold = 0
            elif "battle" in op:
                self.after_battle = list(op.get("after", []))
                lines.append({"battle": op["battle"]})
        return lines

    def battle_from_event(self, spec):
        """Бой из события: пул акта ("battle"/"elite") или id боя."""
        n = self.nodes[self.node]
        if spec in ("battle", "elite"):
            enc = enc_index(self.data, self.rng.choice(self.act_def["pools"][spec]))
            n["fight"] = spec
        else:
            enc = enc_index(self.data, spec)
            n["fight"] = self.data.encounters[enc]["kind"] if self.data.encounters[enc]["kind"] in ("elite",) else "battle"
        n["encounter"] = enc
        self.stage = {"node": self.node, "kind": "battle"}
        return enc

    def node_kind(self, n):
        """Вид боя узла для наград: событие с боем — бой или элита."""
        if n["type"] == "event":
            return n.get("fight", "battle")
        return n["type"]

    def join_recruit(self):
        """Спутник из события: класс из стартовых, уровень — средний по отряду минус один."""
        classes = self.xd["tavern"]["start_classes"]
        lvl = max(1, sum(h.level for h in self.heroes) // max(1, len(self.heroes)) - 1)
        h = new_recruit(self.data, self.xd, self.rng, self.new_uid("h"), classes, {"1": 1},
                        [x.name for x in self.heroes])
        h.level = lvl
        h.sp = lvl - 1
        h.points = auto_points(self.data, h)
        for item in list(h.gear.values()):
            item["tier"] = self.item_tier()
        self.heroes.append(h)
        return h

    # ---------- итоги ----------

    def glory(self):
        g = self.cfg["glory"]
        total = (self.counts.get("battle", 0) * g["battle"] + self.counts.get("elite", 0) * g["elite"]
                 + self.counts.get("boss", 0) * g["boss"] + self.act * g["act"])
        if self.result == "victory":
            total += g["victory"]
        return int(round(total * self.tier_def.get("glory", 1.0) * self.vow_glory()))

    def vow_glory(self):
        """Обеты тяжести — больше славы: 1 + Σ ступень × слава обета."""
        return 1 + sum(self.xd["vows"][v]["glory"] * r for v, r in self.vows.items() if v in self.xd.get("vows", {}))

    def library_cards(self):
        return building_value(self.xd, self.build, "library") or {}


# ---------- профиль: таверна и слава ----------

def ult_open(data, h):
    """Ультимейт героя похода открывается с уровнем (как в сюжете — data/story_progression.json)."""
    ult = story_meta.ult_of(data, h.cls, h.skills)
    return ult is not None and h.level >= story_meta.skill_level(data, h.cls, ult)


class ExpeditionProfile:
    """Мета экспедиции: слава, улучшения таверны, герои в зале и начатый поход (сохраняется целиком)."""

    def __init__(self, data, path=None, sandbox=False, solo=False):
        self.data = data if hasattr(data, "expedition") else expedition_data(data)
        self.xd = self.data.expedition
        self.path = path
        self.sandbox = sandbox
        self.solo = solo                         # режим «Одиночка»: свой профиль, в поход — один герой
        self.mode = "solo" if solo else "expedition"
        self.glory = 0
        self.tier_open = 9 if sandbox else 0     # открытая ступень Болота (песочница — все)
        self.chapter_tiers = {}                  # открытая сложность остальных глав
        self.chapter_wins = {}                   # победы по главам: открывают следующие
        self.trophies = {}                       # трофеи глав (янтарь болота, сердце горна…) — на постройки
        self.buildings = {}                      # постройки таверны: {id: уровень}
        self.vows = {}                           # выбранные обеты тяжести на следующий поход: {id: ступень}
        self.fallen = []                         # зал славы: павшие герои
        self.upgrades = {}
        self.roster = []
        self.runs = 0
        self.wins = 0
        self.best_act = 0
        self.run_state = None
        self.uid_n = 0
        self.seed_n = 0
        self.mats = {}                           # материалы для мастерских: руда, кожа, травы, самоцветы
        self.offers = []                         # доска поручений: заказы на выбор [{"id", "seed"}]
        self.news = []                           # вести с поручений после последнего похода
        self.away = []                           # ушедшие ветераны (могут вернуться в таверну)
        self.stash = {}                          # хранилище артефактов таверны: {uid: артефакт}
        self.gems = []                           # огранённые самоцветы: [{"uid", "id", "q", "size", "shape"}]
        self.rough = []                          # необработанные самоцветы: [{"uid", "id", "seed", "size"}]
        self.smith = {}                          # кузня: куски, пакеты, части, инструменты, заказы (sim/smithing.py)
        self.market = {}                         # товар рынка: {"key", "rough": [...], "cut": [...]}
        self.art_n = 0
        self.glory = self.xd["tavern"].get("start_treasury", 0)     # новая таверна: стартовая казна на найм
        if path and os.path.exists(path):
            self._load()
        if not self.offers:
            self.refresh_offers()
        if not self.market:
            self.refresh_market()
        for k in ("pieces", "billets", "parts", "tools", "orders"):
            self.smith.setdefault(k, [])
        if not self.smith["orders"] and self.xd.get("smithing"):
            self.refresh_orders()
        if not self.roster:
            self.roll_roster()
        if sandbox:
            self.sandbox_fill()

    def sandbox_fill(self):
        """Песочница: открыта вся прокачка таверны и всё для проверки — золото, материалы, трофеи, постройки и
        мастерские на максимуме, камни, артефакты в сундуке, ветераны 5-го ранга в общежитии, павшие на кладбище."""
        from . import artifacts as AR
        xd = self.xd
        self.glory = max(self.glory, 99999)
        for k in xd.get("materials", {}):
            self.mats[k] = max(self.mats.get(k, 0), 999)
        for k in xd.get("trophies", {}):
            self.trophies[k] = max(self.trophies.get(k, 0), 99)
        for bid, b in xd.get("buildings", {}).items():
            self.buildings[bid] = len(b["levels"])
        grown = False
        for uid, up in xd["tavern"]["upgrades"].items():
            if self.upgrades.get(uid, 0) < len(up["costs"]):
                self.upgrades[uid] = len(up["costs"])
                grown = True
        if grown:
            self.roll_roster(keep=True)
        if len(self.gems) < len(xd["artifacts"]["gems"]):
            for gid in xd["artifacts"]["gems"]:
                for q in (0.9, 1.15):
                    self.art_n += 1
                    self.gems.append({"uid": f"g{self.art_n}", "id": gid, "q": q, "size": 1.0})
        if xd.get("smithing"):                        # кузня: все инструменты и запас кусков всех металлов
            from . import smithing as SM
            for tk in SM.cfg(xd)["tools"]:
                if tk not in self.smith["tools"]:
                    self.smith["tools"].append(tk)
            if len(self.smith["pieces"]) < 8:
                rng = random.Random("sandbox-metal")
                for m in SM.cfg(xd)["metals"]:
                    for _ in range(3):
                        self.smith["pieces"].append(SM.new_piece(xd, self.suid("p"), m, rng))
            if not self.market.get("smith"):
                self.market["smith"] = SM.roll_wanderer(dict(xd, smithing=dict(SM.cfg(xd), wanderer=dict(
                    SM.cfg(xd)["wanderer"], chance=1.0))), random.Random(1), [], lambda: self.suid("p"))
        if len(self.rough) < len(xd["artifacts"]["gems"]):
            rng = random.Random("sandbox-rough")
            for gid in xd["artifacts"]["gems"]:
                for _ in range(2):
                    self.add_rough(gid, rng)
        if not self.stash:
            a = xd["artifacts"]
            for sid, s_ in a["sets"].items():
                kinds = list(a["kinds"]) if s_["rarity"] in ("legendary", "epic") else list(a["kinds"])[:2]
                for kind in kinds:
                    self.art_n += 1
                    art = AR.make(xd, f"a{self.art_n}", kind, sid, 1.0 + 0.05 * (self.art_n % 5),
                                  random.Random(self.art_n))
                    art["level"] = {"legendary": 10, "epic": 6, "rare": 3}.get(s_["rarity"], 0)
                    art["gems"] = [{"id": g, "q": 1.1} for g in list(a["gems"])[:AR.sockets(xd, art)]]
                    self.stash[art["uid"]] = art
        if not any(h.dorm for h in self.roster):
            free = [h for h in self.roster if not h.task][-2:]
            legend = [u for u, art in self.stash.items() if art["rarity"] == "legendary"]
            sets = sorted({self.stash[u]["set"] for u in legend})
            for h, sid in zip(free, sets):
                h.rank = max(int(k) for k in xd["tavern"]["ranks"])
                h.vet = dict(h.vet, wins=h.vet.get("wins", 0) + 4, runs=h.vet.get("runs", 0) + 4,
                             chapters=sorted(xd.get("chapters", {})))
                h.dorm = True
                h.arts = [u for u in legend if self.stash[u]["set"] == sid][:self.art_slots(h)]
                h.feats.update(kills=160, battles=30, boss_kills=3, elite_kills=6, runs_won=4)
                h.chronicle.append({"kind": "win", "text": "Песочница: прошёл все главы", "run": 4, "chapter": "swamp"})
        if not self.fallen:
            classes = [c for c in self.classes() if c in self.data.classes][:5]
            for i, cls in enumerate(classes):
                self.fallen.append({
                    "name": xd["tavern"]["names"][i % len(xd["tavern"]["names"])], "cls": cls, "level": 4 + i * 2,
                    "chapter": "swamp", "act": 1 + i % 3, "reason": "погиб в бою (песочница)", "solo": False,
                    "wins": i % 3, "titles": [],
                    "chronicle": [{"kind": "start", "text": "Ушёл в поход: Болото", "run": 1, "chapter": "swamp"},
                                  {"kind": "death", "text": "Погиб в бою", "run": 1, "chapter": "swamp"}],
                    "feats": {"kills": 10 * (i + 1), "battles": 3 + i}})
        self.save()

    @property
    def uses_stats(self):
        return True

    # совместимость с общими экранами (главное меню, костёр)
    @property
    def squad(self):
        if self.run_state:
            return [h["cls"] for h in self.run_state.get("heroes", [])][:4]
        return [h.cls for h in self.recruitable()[:4]]

    @property
    def expeditions(self):
        return self.runs

    @property
    def amber(self):
        return self.glory

    captured = ()
    done = ()

    @property
    def unlocked(self):
        return self.classes()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            return
        if d.get("mode") != "expedition":
            return
        self.glory = d.get("glory", 0)            # казна: золото таверны (до 2026-11-11 — «слава», ×5)
        if not d.get("econ"):
            self.glory *= 5
        self.mats = dict(d.get("mats") or {})
        self.offers = list(d.get("offers") or [])
        self.news = list(d.get("news") or [])
        self.away = list(d.get("away") or [])
        self.stash = dict(d.get("stash") or {})
        self.gems = list(d.get("gems") or [])
        self.rough = list(d.get("rough") or [])
        self.smith = dict(d.get("smith") or {})
        self.market = dict(d.get("market") or {})
        self.art_n = d.get("art_n", 0)
        if not d.get("tiers10"):                 # старые 3 сложности → 10 ступеней
            mig = self.xd["config"].get("tier_migrate", {})
            self.tier_open = mig.get(str(d.get("tier_open", 0)), 0)
            self.chapter_tiers = {k: mig.get(str(v), 0) for k, v in d.get("chapter_tiers", {}).items()}
            if d.get("run"):
                d["run"]["tier"] = mig.get(str(d["run"].get("tier", 0)), 0)
        if d.get("tiers10"):
            self.tier_open = d.get("tier_open", 0)
            self.chapter_tiers = d.get("chapter_tiers", {})
        self.chapter_wins = d.get("chapter_wins", {})
        self.trophies = d.get("trophies", {})
        self.buildings = {k: v for k, v in d.get("buildings", {}).items() if k in self.xd.get("buildings", {})}
        self.vows = {k: v for k, v in d.get("vows", {}).items() if k in self.xd.get("vows", {})}
        self.fallen = d.get("fallen", [])
        if d.get("wins") and not self.chapter_wins:
            self.chapter_wins = {"swamp": d["wins"]}     # старое сохранение: все победы — на Болоте
        self.upgrades = {k: v for k, v in d.get("upgrades", {}).items() if k in self.xd["tavern"]["upgrades"]}
        self.runs, self.wins, self.best_act = d.get("runs", 0), d.get("wins", 0), d.get("best_act", 0)
        self.uid_n, self.seed_n = d.get("uid_n", 0), d.get("seed_n", 0)
        self.roster = [fix_kit(self.data, Hero(dict(h, solo=False))) for h in d.get("roster", [])
                       if h.get("cls") in self.data.classes]
        for h in self.roster:                  # старое сохранение: ветеран с навыками в D, F — из одиночного похода
            if h.vet and "solo" not in h.vet:
                h.vet["solo"] = len(h.skills) > story_meta.slots(self.data) + 1
        self.run_state = d.get("run")

    def save(self, run=None):
        if run is not None:
            self.run_state = run.to_dict() if not run.result else None
        if not self.path:
            return
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        d = {"mode": "expedition", "version": VERSION, "glory": self.glory, "upgrades": self.upgrades,
             "runs": self.runs, "wins": self.wins, "best_act": self.best_act, "uid_n": self.uid_n,
             "seed_n": self.seed_n, "roster": [h.to_dict() for h in self.roster], "run": self.run_state,
             "tier_open": self.tier_open, "chapter_tiers": self.chapter_tiers, "chapter_wins": self.chapter_wins,
             "trophies": self.trophies, "buildings": self.buildings, "vows": self.vows, "fallen": self.fallen,
             "solo": self.solo, "econ": 1, "mats": self.mats, "offers": self.offers, "news": self.news,
             "away": self.away, "stash": self.stash, "gems": self.gems, "art_n": self.art_n, "tiers10": 1,
             "rough": self.rough, "market": self.market, "smith": self.smith}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, self.path)

    def remember_autocast(self, run):
        pass

    # ---------- таверна ----------

    def level(self, uid):
        return self.upgrades.get(uid, 0)

    def value(self, uid):
        up = self.xd["tavern"]["upgrades"][uid]
        return up["values"][min(len(up["values"]) - 1, self.level(uid))]

    def upgrade_cost(self, uid):
        up = self.xd["tavern"]["upgrades"][uid]
        lv = self.level(uid)
        return up["costs"][lv] if lv < len(up["costs"]) else None

    def buy_upgrade(self, uid):
        cost = self.upgrade_cost(uid)
        if cost is None or self.glory < cost:
            return False
        self.glory -= cost
        self.upgrades[uid] = self.level(uid) + 1
        if uid in ("hall", "guests", "renown"):
            self.roll_roster(keep=True)
        self.save()
        return True

    def classes(self):
        tav = self.xd["tavern"]
        out = list(tav["start_classes"])
        vals = tav["upgrades"]["guests"]["values"]
        for lv in range(1, self.level("guests") + 1):
            out += vals[min(lv, len(vals) - 1)]
        return [c for c in dict.fromkeys(out) if c in self.data.classes]

    def hall_size(self):
        return self.value("hall")

    @staticmethod
    def solo_vet(h):
        return bool(h.vet.get("solo"))

    def hall(self, solo=None):
        """Гости таверны (зал): ветераны-одиночки (6 навыков) — только в одиночке; новички и ветераны отряда — в
        обоих режимах. Не больше размера зала. Жильцы общежития и герои на поручении в зале не стоят."""
        solo = self.solo if solo is None else solo
        return [h for h in self.roster if not h.task and not h.dorm and (solo or not self.solo_vet(h))][:self.hall_size()]

    def lodgers(self, solo=None):
        """Жильцы общежития, что дома (не на поручении): живут отдельно от зала и мест в нём не занимают."""
        solo = self.solo if solo is None else solo
        return [h for h in self.roster if h.dorm and not h.task and (solo or not self.solo_vet(h))]

    def recruitable(self, solo=None):
        """Кого можно взять в поход или на поручение: жильцы общежития и гости зала."""
        return self.lodgers(solo) + self.hall(solo)

    def ready(self, h):
        """Можно ли взять героя в поход: не на поручении и не отдыхает после раны."""
        return not h.task and h.rest <= 0

    # ---------- казна, найм, общежитие ----------

    def hire_cost(self, h):
        """Новичок рангом выше стоит золота при выходе в поход; ветераны (свои герои) — бесплатно."""
        if h.dorm or h.vet:
            return 0
        return int(self.xd["tavern"].get("hire_cost", {}).get(str(h.rank), 0))

    def dorm_slots(self):
        return building_value(self.xd, self.buildings, "dorm") or self.xd["tavern"].get("dorm_base", 0)

    def dorm_heroes(self):
        return [h for h in self.roster if h.dorm]

    def dorm_cost(self, h):
        c = self.xd["tavern"]["dorm_cost"]
        return int(c["base"] + c["per_rank"] * (h.rank - 1) + c["per_title"] * len(h.titles)
                   + c["per_win"] * h.vet.get("wins", 0))

    def keep_in_dorm(self, h):
        """Выкупить ветерана в общежитие: останется в таверне, пока не отпустите."""
        if h.dorm or not h.vet or len(self.dorm_heroes()) >= self.dorm_slots():
            return False
        cost = self.dorm_cost(h)
        if self.glory < cost:
            return False
        self.glory -= cost
        h.dorm = True
        h.vet.pop("stay", None)
        self.save()
        return True

    def release(self, h):
        """Отпустить из общежития: ветеран уйдёт из таверны после следующего похода."""
        if not h.dorm:
            return False
        h.dorm = False
        h.vet["stay"] = self.xd["tavern"].get("vet_stay", 1)
        self.save()
        return True

    def _vet_returns(self):
        """Ушедший ветеран может снова заглянуть в таверну (тогда его можно выкупить в общежитие)."""
        chance = self.xd["tavern"].get("vet_return", 0.3)
        rng = random.Random(f"vetback:{self.seed_n}:{self.runs}")
        if not self.away or rng.random() >= chance:
            return []
        d = self.away.pop(rng.randrange(len(self.away)))
        if d.get("cls") not in self.data.classes:
            return []
        h = fix_kit(self.data, Hero(dict(d, solo=False)))
        h.vet["stay"] = self.xd["tavern"].get("vet_stay", 1)
        h.vet["back"] = True                       # «вернулся» — пометка в таверне
        return [h]

    def add_mats(self, mats):
        for k, v in (mats or {}).items():
            if v:
                self.mats[k] = self.mats.get(k, 0) + v

    # ---------- артефакты: хранилище, ячейки, мастерские ----------

    def art_slots(self, h):
        """Ячеек артефактов у героя — по рангу (1–5)."""
        return int(self.xd["tavern"]["ranks"].get(str(h.rank), {}).get("slots", h.rank))

    def art_owner(self, uid):
        return next((h for h in self.roster if uid in h.arts), None)

    def art_locked(self, uid):
        """Артефакт на герое в идущем походе — не снять."""
        st = self.run_state or {}
        return any(uid in (h.get("arts") or []) for h in st.get("heroes", []))

    def worn(self, h):
        return [self.stash[u] for u in h.arts if u in self.stash]

    def equip(self, h, uid):
        """Надеть артефакт из хранилища: свободная ячейка, один вид — одна вещь; с другого героя — снимается."""
        art = self.stash.get(uid)
        if not art or self.art_locked(uid) or uid in h.arts:
            return False
        same = [u for u in h.arts if self.stash.get(u, {}).get("kind") == art["kind"]]
        if same:
            h.arts.remove(same[0])                 # тот же вид — замена
        elif len(h.arts) >= self.art_slots(h):
            return False
        other = self.art_owner(uid)
        if other and other is not h:
            other.arts.remove(uid)
        h.arts.append(uid)
        self.save()
        return True

    def unequip(self, h, uid):
        if uid not in h.arts:
            return False
        h.arts.remove(uid)
        self.save()
        return True

    def workshop_level(self, ws):
        return self.building_level(ws)

    def can_craft(self, ws, set_id):
        from . import artifacts as AR
        a = self.xd["artifacts"]
        rk = a["rarities"][a["sets"][set_id]["rarity"]]["rank"]
        return (building_value(self.xd, self.buildings, ws) or 0) >= rk and self.can_pay(AR.craft_cost(self.xd, ws, set_id))

    def craft(self, ws, kind, set_id, q, seed=None):
        """Ковка: цена рецепта, качество — из мини-игры. Возвращает артефакт или None."""
        from . import artifacts as AR
        a = self.xd["artifacts"]
        if a["kinds"][kind]["workshop"] != ws or not self.can_craft(ws, set_id):
            return None
        self.pay(AR.craft_cost(self.xd, ws, set_id))
        self.art_n += 1
        uid = f"a{self.art_n}"
        art = AR.make(self.xd, uid, kind, set_id, q, random.Random(f"art:{uid}:{seed}"))
        self.stash[uid] = art
        self.save()
        return art

    def upgrade_cap(self):
        return building_value(self.xd, self.buildings, "ws_alchemy") or 0

    def upgrade_art(self, uid):
        """Улучшение +1 в алхимии (потолок — уровень мастерской)."""
        from . import artifacts as AR
        art = self.stash.get(uid)
        if not art or self.art_locked(uid) or art["level"] >= min(self.upgrade_cap(), self.xd["artifacts"]["max_level"]):
            return False
        if not self.pay(AR.upgrade_cost(self.xd, art)):
            return False
        art["level"] += 1
        self.save()
        return True

    def enchant(self, uid, q, seed=None):
        """Зачарование: новое свойство (качество — из мини-игры смешивания)."""
        from . import artifacts as AR
        art = self.stash.get(uid)
        if not art or self.art_locked(uid) or not self.upgrade_cap():
            return None
        if not self.pay(AR.enchant_cost(self.xd, art)):
            return None
        a = self.xd["artifacts"]
        rng = random.Random(f"ench:{uid}:{art['level']}:{seed}")
        old = (art.get("extra") or {}).get("id")
        pool = [x for x in a["extras"] if x != old]
        lo, hi = a["quality"]
        art["extra"] = {"id": rng.choice(pool), "q": round(max(lo, min(hi, q)), 3)}
        self.save()
        return art["extra"]

    def new_rough(self, gid, rng, size=None):
        """Новый необработанный самоцвет: вид, свой seed (форма заготовки), размер."""
        m = self.xd["market"]
        self.art_n += 1
        return {"uid": f"r{self.art_n}", "id": gid, "seed": rng.randrange(1, 10 ** 6),
                "size": round(size if size is not None else rng.uniform(*m["size"]), 2)}

    def add_rough(self, gid, rng=None, size=None):
        r = self.new_rough(gid, rng or random.Random(f"rough:{self.art_n}"), size)
        self.rough.append(r)
        return r

    def find_rough(self, src):
        """Камень по uid или первый камень этого вида."""
        return next((r for r in self.rough if r["uid"] == src), None) or \
            next((r for r in self.rough if r["id"] == src), None)

    def cut_gem(self, src, q, shape=None, cut=None):
        """Огранка (ювелирная): именно этот необработанный камень (uid или вид) — в огранённый, качество из мини-игры."""
        a = self.xd["artifacts"]
        r = self.find_rough(src)
        if not (building_value(self.xd, self.buildings, "ws_jewel") or 0) or r is None:
            return None
        if not self.pay({"glory": a["gem_cost"]["gold"]}):
            return None
        self.rough.remove(r)
        self.art_n += 1
        lo, hi = a["quality"]
        g = {"uid": f"g{self.art_n}", "id": r["id"], "q": round(max(lo, min(hi, q)), 3), "size": r.get("size", 1.0)}
        if shape:                                  # форма огранённого камня — для витрины в инвентаре
            g["shape"], g["cut"] = shape, cut
        self.gems.append(g)
        self.save()
        return g

    # ---------- кузня (sim/smithing.py) ----------

    def suid(self, pre):
        self.art_n += 1
        return f"{pre}{self.art_n}"

    def has_tool(self, tid):
        return tid in self.smith.get("tools", [])

    def smelt(self, carbon, heat_ok, slag, seed=0):
        """Плавка: руда → куски (железо/сталь), чистота — от удержания жара и снятого шлака."""
        from . import smithing as SM
        cost = {"ore": SM.cfg(self.xd)["smelt"]["ore"]}
        if not self.pay(cost):
            return None
        out = SM.smelt_result(self.xd, carbon, heat_ok, slag, random.Random(f"smelt:{seed}:{self.art_n}"),
                              lambda: self.suid("p"))
        self.smith["pieces"] += out
        self.save()
        return out

    def stack(self, grid, used_uids):
        """Пакет со стола: куски уходят в пакет."""
        from . import smithing as SM
        used = [p for p in self.smith["pieces"] if p["uid"] in used_uids]
        if not used:
            return None
        b = SM.billet_from(self.xd, self.suid("b"), grid, used)
        self.smith["pieces"] = [p for p in self.smith["pieces"] if p["uid"] not in used_uids]
        self.smith["billets"].append(b)
        self.save()
        return b

    def fold_max(self):
        from . import smithing as SM
        return SM.cfg(self.xd)["weld"]["fold_max"] + (2 if self.has_tool("tongs") else 0)

    def store_billet(self, b):
        """Сварка закончена: пакет обновлён в сундуке."""
        self.smith["billets"] = [b if x["uid"] == b["uid"] else x for x in self.smith["billets"]]
        self.save()

    def cut_parts(self, b_uid, cuts, cold, wide=False):
        """Разделка: брусок — на части любой массы (cuts — массы, остаток — последней частью)."""
        from . import smithing as SM
        b = next((x for x in self.smith["billets"] if x["uid"] == b_uid), None)
        if b is None:
            return None
        parts = [SM.cut_part(self.xd, self.suid("c"), b, m, cold, wide) for m in cuts if m >= 5]
        self.smith["parts"] += parts
        self.smith["billets"].remove(b)
        self.save()
        return parts

    def forge_item(self, kind, set_id, part_uids, shape_scores, quench, seed=None):
        """Ковка вещи из частей: цена рецепта, качество — подготовка металла и ковка, металл — в артефакт."""
        from . import artifacts as AR, smithing as SM
        a = self.xd["artifacts"]
        ws = a["kinds"][kind]["workshop"]
        parts = [p for uid in part_uids for p in self.smith["parts"] if p["uid"] == uid]
        if len(parts) != len(SM.parts_for(self.xd, kind)) or not self.can_craft(ws, set_id):
            return None
        self.pay(AR.craft_cost(self.xd, ws, set_id))
        parts = SM.match_parts(self.xd, kind, parts) or parts
        q = SM.final_quality(self.xd, parts, shape_scores, kind)
        self.art_n += 1
        uid = f"a{self.art_n}"
        art = AR.make(self.xd, uid, kind, set_id, q, random.Random(f"art:{uid}:{seed}"))
        art["metal"] = SM.merge_props(parts, quench)
        art["metal"]["mass"] = sum(p["mass"] for p in parts)
        art["metal"]["heavy"] = SM.mass_bonus(parts, SM.parts_for(self.xd, kind))
        art["look"] = parts[0].get("look")                  # узор металла — для вида вещи
        self.stash[uid] = art
        self.smith["parts"] = [p for p in self.smith["parts"] if p["uid"] not in part_uids]
        self.save()
        return art

    def refresh_orders(self):
        from . import smithing as SM
        if not self.xd.get("smithing"):
            return
        self.smith["orders"] = SM.roll_orders(self.xd, random.Random(f"orders:{self.seed_n}:{self.runs}"))

    def fulfil(self, order_id, art_uid):
        """Сдать вещь по заказу: вещь уходит, награда — золото (и материалы)."""
        from . import smithing as SM
        o = next((x for x in self.smith["orders"] if x["id"] == order_id), None)
        art = self.stash.get(art_uid)
        if o is None or art is None or self.art_locked(art_uid) or not SM.order_ok(self.xd, o, art):
            return False
        owner = self.art_owner(art_uid)
        if owner:
            owner.arts.remove(art_uid)
        del self.stash[art_uid]
        self.glory += o["gold"]
        self.add_mats(o.get("mats", {}))
        self.smith["orders"].remove(o)
        self.save()
        return True

    def buy_tool(self, tid):
        """Инструмент или урок у бродячего кузнеца."""
        from . import smithing as SM
        w = self.market.get("smith") or {}
        t = SM.cfg(self.xd)["tools"].get(tid)
        if t is None or tid not in w.get("tools", []) or self.has_tool(tid) or not self.pay({"glory": t["price"]}):
            return False
        self.smith["tools"].append(tid)
        w["tools"].remove(tid)
        self.save()
        return True

    def buy_piece(self, uid):
        w = self.market.get("smith") or {}
        p = next((x for x in w.get("pieces", []) if x["uid"] == uid), None)
        if p is None or not self.pay({"glory": p["price"]}):
            return False
        w["pieces"].remove(p)
        self.smith["pieces"].append({k: v for k, v in p.items() if k != "price"})
        self.save()
        return True

    # ---------- рынок ----------

    def refresh_market(self):
        """Новый товар рынка (после похода): несколько необработанных камней и иногда — огранённые."""
        m = self.xd.get("market")
        if not m:
            return
        rng = random.Random(f"market:{self.seed_n}:{self.runs}")
        ids = sorted(self.xd["artifacts"]["gems"])
        weights = [1.0 / self.xd["artifacts"]["gems"][g].get("price", 200) for g in ids]   # дорогие — реже
        rough = [self.new_rough(rng.choices(ids, weights)[0], rng) for _ in range(rng.randint(*m["rough_stock"]))]
        cut = []
        for _ in range(rng.randint(*m["cut_stock"])):
            r = self.new_rough(rng.choices(ids, weights)[0], rng)
            self.art_n += 1
            cut.append({"uid": f"g{self.art_n}", "id": r["id"], "q": round(rng.uniform(0.85, 1.15), 2),
                        "size": r["size"], "cut": rng.choice(["baguette", "emerald", "cushion", "oval", "brilliant"])})
        from . import smithing as SM
        smith = SM.roll_wanderer(self.xd, rng, self.smith.get("tools", []), lambda: self.suid("p")) \
            if self.xd.get("smithing") else None
        self.market = {"key": self.runs, "rough": rough, "cut": cut, "smith": smith}

    def market_price(self, kind, item):
        from . import artifacts as AR
        return AR.rough_value(self.xd, item) if kind == "rough" else AR.cut_value(self.xd, item)

    def sell_price(self, kind, item):
        return int(self.market_price(kind, item) * self.xd["market"]["sell_k"])

    def buy(self, kind, uid):
        """Купить камень с рынка (kind: rough | cut)."""
        lot = self.market.get(kind, [])
        item = next((x for x in lot if x["uid"] == uid), None)
        if item is None or not self.pay({"glory": self.market_price(kind, item)}):
            return False
        lot.remove(item)
        (self.rough if kind == "rough" else self.gems).append(item)
        self.save()
        return True

    def sell(self, kind, uid):
        """Продать свой камень рынку за половину цены."""
        own = self.rough if kind == "rough" else self.gems
        item = next((x for x in own if x["uid"] == uid), None)
        if item is None:
            return False
        self.glory += self.sell_price(kind, item)
        own.remove(item)
        self.market.setdefault(kind, []).append(item)       # рынок перепродаёт
        self.save()
        return True

    def rough_drops(self, run):
        """Вылазка: за каждую добытую крошку — небольшой шанс найти настоящий самоцвет (один на поход)."""
        m = self.xd.get("market")
        if not m:
            return None
        chips = getattr(run, "loot", {}).get("gems", 0)
        chance = min(m["rough_drop_max"], m["rough_drop_per_chip"] * chips)
        rng = random.Random(f"roughdrop:{run.seed}:{self.runs}")
        if chips <= 0 or rng.random() >= chance:
            return None
        ids = sorted(self.xd["artifacts"]["gems"])
        weights = [1.0 / self.xd["artifacts"]["gems"][g].get("price", 200) for g in ids]
        r = self.new_rough(rng.choices(ids, weights)[0], rng)
        self.rough.append(r)
        return r

    def socket(self, uid, gem_uid):
        """Вставить самоцвет в свободное гнездо (насовсем)."""
        from . import artifacts as AR
        art = self.stash.get(uid)
        g = next((x for x in self.gems if x["uid"] == gem_uid), None)
        if not art or not g or self.art_locked(uid) or len(art["gems"]) >= AR.sockets(self.xd, art):
            return False
        art["gems"].append({"id": g["id"], "q": g["q"]})
        self.gems.remove(g)
        self.save()
        return True

    # ---------- поручения ----------

    def board_slots(self):
        return building_value(self.xd, self.buildings, "board") or self.xd.get("contracts", {}).get("base_slots", 0)

    def tasks(self):
        """Идущие поручения: {id: [герои]}."""
        out = {}
        for h in self.roster:
            if h.task:
                out.setdefault(h.task["key"], []).append(h)
        return out

    def refresh_offers(self):
        """Новые заказы на доске (после каждого похода): шаблоны поручений — случайно, без повторов."""
        cfg = self.xd.get("contracts")
        if not cfg:
            return
        rng = random.Random(f"offers:{self.seed_n}:{self.runs}")
        ids = sorted(cfg["templates"])
        rng.shuffle(ids)
        self.offers = [{"id": i, "key": f"{i}:{self.runs}:{k}"} for k, i in enumerate(ids[:cfg["offers"]])]

    def contract_chance(self, cid, heroes):
        """Шанс успеха: риск, подходящие герои (класс/роль/атрибут), ранг."""
        cfg = self.xd["contracts"]
        t = cfg["templates"][cid]
        ch = cfg["chance"]
        p = ch[t["risk"]]
        fit = t.get("fit", {})
        for h in heroes:
            c = self.data.classes[h.cls]
            ok = (h.cls in fit.get("classes", []) or c.get("role") in fit.get("roles", [])
                  or (fit.get("attr") and self.data.stats_mode["classes"][h.cls]["primary"] == fit["attr"]))
            p += ch["fit"] if ok else 0.0
            p += ch["rank"] * (h.rank - 1)
        return round(min(ch["max"], p), 2)

    def send(self, offer, uids):
        """Отправить героев на поручение. Нужно свободное место на доске и ровно столько героев, сколько просят."""
        cfg = self.xd["contracts"]
        t = cfg["templates"][offer["id"]]
        heroes = [h for h in self.roster if h.uid in uids and self.ready(h)]
        if len(heroes) != t["heroes"] or len(self.tasks()) >= self.board_slots():
            return False
        chance = self.contract_chance(offer["id"], heroes)
        for h in heroes:
            h.task = {"id": offer["id"], "key": offer["key"], "left": t["runs"], "chance": chance,
                      "with": [x.uid for x in heroes]}
            h.vet.pop("stay", None)                # на поручении из таверны не уходит
        self.offers = [o for o in self.offers if o["key"] != offer["key"]]
        self.save()
        return True

    def tick_tasks(self):
        """Прошёл поход: поручения продвигаются; закончившиеся — развязка. Возвращает вести [{...}]."""
        cfg = self.xd.get("contracts")
        news = []
        for key, heroes in self.tasks().items():
            task = heroes[0].task
            for h in heroes:
                h.task["left"] -= 1
            if task["left"] > 0:
                continue
            t = cfg["templates"][task["id"]]
            rng = random.Random(f"task:{key}:{self.runs}")
            roll = rng.random()
            res = "success" if roll < task["chance"] else (
                "partial" if roll < task["chance"] + cfg["chance"]["partial"] else "fail")
            got = self._task_reward(t, rng, 1.0 if res == "success" else 0.5 if res == "partial" else 0.0)
            item = {"name": t["name"], "result": res, "heroes": [h.name for h in heroes], "reward": got,
                    "hurt": [], "dead": []}
            for h in heroes:
                h.task = None
                h.feats["tasks"] = h.feats.get("tasks", 0) + (1 if res != "fail" else 0)
                if res == "fail":
                    if t["risk"] == "high" and rng.random() < cfg["death"].get("high", 0):
                        item["dead"].append(h.name)
                        self._task_death(h, t)
                        continue
                    h.rest = 1
                    item["hurt"].append(h.name)
                self._task_note(h, t, res)
            news.append(item)
            back = [h for h in heroes if h in self.roster]
            self.roster = back + [h for h in self.roster if h not in back]
        for h in self.roster:
            if not h.task and h.rest > 0 and not any(h.name in n["hurt"] for n in news):
                h.rest -= 1
        return news

    def _task_reward(self, t, rng, k):
        r = t["reward"]
        got = {}
        if not k:
            return got
        if r.get("gold"):
            got["gold"] = int(rng.randint(*r["gold"]) * k)
            self.glory += got["gold"]
        mats = {m: int(round(rng.randint(*v) * k)) for m, v in r.get("mats", {}).items()}
        mats = {m: v for m, v in mats.items() if v}
        if mats:
            got["mats"] = mats
            self.add_mats(mats)
        if r.get("trophy") and k >= 1:
            got["trophy"] = dict(r["trophy"])
            for tk, v in r["trophy"].items():
                self.trophies[tk] = self.trophies.get(tk, 0) + v
        if r.get("recruit") and k >= 1:
            self.uid_n += 1
            h = new_recruit(self.data, self.xd, rng, f"h{self.uid_n}", self.classes(),
                            {str(r["recruit"]): 1}, [x.name for x in self.roster])
            self.roster.insert(0, h)
            got["recruit"] = h.name
        return got

    def _task_note(self, h, t, res):
        word = {"success": "выполнил", "partial": "наполовину выполнил", "fail": "провалил"}[res]
        h.chronicle.append({"kind": "task" if res != "fail" else "fall",
                            "text": f"Поручение «{t['name']}»: {word}" + (" — ранен" if res == "fail" else ""),
                            "run": h.vet.get("runs", 0) + 1, "chapter": "tavern"})
        titles = self.xd.get("chronicle", {}).get("titles", {})
        for tid, td in titles.items():
            if tid not in h.titles and all(h.feats.get(k, 0) >= v for k, v in td["need"].items()):
                h.titles.append(tid)

    def _task_death(self, h, t):
        h.chronicle.append({"kind": "death", "text": f"Погиб на поручении «{t['name']}»",
                            "run": h.vet.get("runs", 0) + 1, "chapter": "tavern"})
        titles = self.xd.get("chronicle", {}).get("titles", {})
        self.fallen.append({"name": h.name, "cls": h.cls, "level": h.level, "chapter": "tavern", "act": 0,
                            "reason": f"погиб на поручении «{t['name']}»", "solo": False,
                            "wins": h.vet.get("wins", 0), "titles": [titles[x]["name"] for x in h.titles if x in titles],
                            "chronicle": list(h.chronicle), "feats": dict(h.feats)})
        self.roster = [x for x in self.roster if x is not h]

    def roll_roster(self, keep=False):
        """Новый зал таверны. keep — оставить уже сидящих, добрать до размера зала (в обоих режимах)."""
        rng = random.Random(f"tavern:{self.seed_n}:{self.uid_n}")
        self.seed_n += 1
        roster = list(self.roster) if keep else []
        n = self.hall_size()

        def short():
            free = [h for h in roster if not (h.dorm or h.task)]
            squad = sum(1 for h in free if not self.solo_vet(h))
            return squad < n or len(free) < n
        while short():
            self.uid_n += 1
            h = new_recruit(self.data, self.xd, rng, f"h{self.uid_n}", self.classes(), self.value("renown"),
                            [h.name for h in roster])
            roster.append(h)
        fixed = [h for h in roster if h.dorm or h.task]               # общежитие и поручения — не место в зале
        roster = [h for h in roster if not (h.dorm or h.task)]
        solo_vets = [h for h in roster if self.solo_vet(h)][:n]       # ветераны-одиночки ждут своего режима
        rest = [h for h in roster if not self.solo_vet(h)][:n]
        self.roster = fixed + solo_vets + rest

    def reroll(self):
        cost = self.xd["tavern"]["reroll_cost"]
        if self.glory < cost:
            return False
        self.glory -= cost
        keep = [h for h in self.roster if h.dorm or h.task]
        self.roll_roster()
        self.roster = keep + self.roster
        self.save()
        return True

    # ---------- постройки таверны ----------

    def building_level(self, bid):
        return self.buildings.get(bid, 0)

    def building_cost(self, bid):
        """Цена следующего уровня постройки: {"glory": n, трофей: n} или None — построено до конца."""
        b = self.xd["buildings"][bid]
        lv = self.building_level(bid)
        return dict(b["levels"][lv]["cost"]) if lv < len(b["levels"]) else None

    def have(self, k):
        if k == "glory":
            return self.glory
        if k in self.xd.get("materials", {}):
            return self.mats.get(k, 0)
        return self.trophies.get(k, 0)

    def can_pay(self, cost):
        return all(self.have(k) >= v for k, v in cost.items())

    def pay(self, cost):
        if not self.can_pay(cost):
            return False
        for k, v in cost.items():
            if k == "glory":
                self.glory -= v
            elif k in self.xd.get("materials", {}):
                self.mats[k] = self.mats.get(k, 0) - v
            else:
                self.trophies[k] = self.trophies.get(k, 0) - v
        return True

    def build(self, bid):
        cost = self.building_cost(bid)
        if cost is None or not self.pay(cost):
            return False
        self.buildings[bid] = self.building_level(bid) + 1
        self.save()
        return True

    def apply_buildings(self, run):
        """Постройки в начале похода: кузня — оружие, двор — уровни, библиотека — выбор, алтарь — дар на выбор."""
        bv = lambda bid: building_value(self.xd, self.buildings, bid)        # noqa: E731
        rng = random.Random(f"{run.seed}:build")
        yard = bv("yard") or 0
        for h in run.heroes:
            target = h.level + yard
            while h.level < target:
                run.gain_xp(h, run.xp_next(h))
        smith = bv("smithy")
        if smith:
            for h in run.heroes:
                item = make_item(self.xd, rng, run.item_tier() + smith.get("tier", 0), smith["rarity"], "weapon",
                                 uid=run.new_uid())
                if "weapon" in h.gear:
                    run.bag.append(item)
                else:
                    h.gear["weapon"] = item
        lib = bv("library") or {}
        for h in run.heroes:
            h.sp += lib.get("start_picks", 0)
        altar = bv("altar")
        run.start_offers = None
        if altar:
            run.start_offers = run.gift_offers(altar["offers"])
            if altar.get("all"):                   # высшая ступень: остальным — случайный подходящий дар
                for h in run.heroes[1:]:
                    gs = [g for g in run.gift_offers(4) if run.gift_ok(h, g)]
                    if gs:
                        run.give_gift(h, gs[0])

    # ---------- обеты тяжести ----------

    def vows_open(self):
        """Обеты — после первой победы в любой главе (песочница — сразу)."""
        return self.sandbox or sum(self.chapter_wins.values()) > 0 or self.wins > 0

    def set_vow(self, vid, rank):
        v = self.xd["vows"][vid]
        self.vows[vid] = max(0, min(v["ranks"], rank))
        if not self.vows[vid]:
            del self.vows[vid]
        self.save()

    def vow_glory(self):
        return 1 + sum(self.xd["vows"][v]["glory"] * r for v, r in self.vows.items())

    # ---------- ветераны и зал славы ----------

    def return_veterans(self, run):
        """Победа: выжившие возвращаются в зал ветеранами — ранг выше (старт с большим уровнем), набор навыков и
        черта остаются, одна ветка навыка — первой ступенью; вещи и прочий рост — нет."""
        cfg = self.xd["tavern"]
        top = max(int(k) for k in cfg["ranks"])
        out = []
        for h in run.heroes:
            d = h.to_dict()
            rank = min(top, h.rank + 1)
            rk = cfg["ranks"][str(rank)]
            best = max(h.branches.items(), key=lambda kv: kv[1][1], default=None)
            vet = dict(h.vet)
            vet["runs"] = vet.get("runs", 0) + 1
            vet["wins"] = vet.get("wins", 0) + 1
            vet["chapters"] = sorted(set(vet.get("chapters", [])) | {run.chapter})
            vet["solo"] = bool(run.solo)               # одиночка (6 навыков) — только для одиночных походов
            d.update(rank=rank, level=rk["level"], xp=0, points=None, sp=max(0, rk["level"] // 3), ranks={}, uses={},
                     branches={best[0]: [best[1][0], 1]} if best else {}, gear={}, hp=None, wounded=False, gifts=[],
                     perks=[], pick_offer=None, solo=False, vet=vet, falls=0)    # летопись и прозвища — с ним
            v = fix_kit(self.data, Hero(d))
            v.points = auto_points(self.data, v)
            out.append(v)
        return out

    def to_hall(self, run, reason):
        for h in run.heroes:
            run.note(h, "death", f"Погиб: поход проигран, акт {run.act + 1}")
            self._hall_entry(run, h, reason, run.act + 1)
        self.fallen = self.fallen[-60:]

    def _hall_entry(self, run, h, reason, act):
        titles = self.xd.get("chronicle", {}).get("titles", {})
        self.fallen.append({"name": h.name, "cls": h.cls, "level": h.level, "chapter": run.chapter,
                            "act": act, "reason": reason, "solo": run.solo, "wins": h.vet.get("wins", 0),
                            "titles": [titles[t]["name"] for t in h.titles if t in titles],
                            "chronicle": list(h.chronicle), "feats": dict(h.feats)})

    def bury_dead(self, run):
        """Погибшие в походе (третье падение) — в зал славы с летописью."""
        for rec in run.dead:
            self._hall_entry(run, Hero(rec["hero"]), rec["reason"], rec["act"])
        run.dead = []

    def squad_cfg(self):
        """Сколько героев берут в поход (одиночка — одного)."""
        return solo_cfg(self.xd["config"]) if self.solo else self.xd["config"]

    def chapters(self):
        """Главы похода по порядку: [(id, название, открыта ли)]."""
        out = []
        for cid, meta in sorted(self.xd.get("chapters", {"swamp": {"name": "Болото"}}).items(),
                                key=lambda kv: kv[1].get("order", 0)):
            need = meta.get("unlock")
            out.append((cid, meta["name"], self.sandbox or not need or self.chapter_wins.get(need, 0) > 0))
        return out

    def chapter_open(self, cid):
        return any(c == cid and ok for c, _, ok in self.chapters())

    def tier_open_of(self, cid):
        if self.sandbox:
            return len(self.xd["config"]["tiers"]) - 1
        return self.tier_open if cid == "swamp" else self.chapter_tiers.get(cid, 0)

    def start(self, uids, seed=None, tier=0, chapter="swamp", autocast="default"):
        """Поход с выбранными героями (2–3) на открытой сложности открытой главы."""
        if not self.chapter_open(chapter):
            chapter = "swamp"
        tier = max(0, min(tier, self.tier_open_of(chapter)))
        cfg = self.squad_cfg()
        picked = [h for h in self.recruitable() if h.uid in uids and self.ready(h)]
        if not cfg["squad_min"] <= len(picked) <= cfg["squad_start"]:
            raise ValueError("нужно 2–3 героя" if not self.solo else "нужен один герой")
        cost = sum(self.hire_cost(h) for h in picked)
        if cost > self.glory:
            raise ValueError("не хватает золота на найм")
        self.glory -= cost                          # новички рангом выше — за золото казны
        seed = seed if seed is not None else random.randrange(1_000_000)
        gold = cfg["start_gold"] + self.value("provisions")
        for h in picked:                           # артефакты: не больше ячеек ранга и только из хранилища
            h.arts = [u for u in h.arts if u in self.stash][:self.art_slots(h)]
        arts = {u: dict(self.stash[u]) for h in picked for u in h.arts}
        run = Expedition(self.data, [Hero(dict(h.to_dict(), solo=self.solo)) for h in picked], seed, gold,
                         chapter=chapter, tier=tier, solo=self.solo, vows={},     # обеты убраны (2026-11-11)
                         build=self.buildings, arts=arts)
        run.uid_n = 1000
        run.autocast_mode = autocast if autocast in ("on", "off") else "default"
        if run.autocast_mode != "default":            # начало похода: все навыки — по выбранному режиму
            for h in run.heroes:
                h.autocast = {}
                run.preset_autocast(h)
        self.apply_buildings(run)
        self.roster = [h for h in self.roster if h.uid not in uids]
        self.runs += 1
        self.save(run)
        return run

    def resume(self):
        if not self.run_state:
            return None
        try:
            return Expedition.from_dict(self.data, self.run_state)
        except (KeyError, TypeError, ValueError, StopIteration):
            self.run_state = None
            return None

    def abandon(self):
        if self.run_state:
            try:
                self.to_hall(Expedition.from_dict(self.data, self.run_state), "брошен")
            except (KeyError, TypeError, ValueError):
                pass
        self.run_state = None
        self.roll_roster(keep=True)
        self.save()

    def finish(self, run):
        """Конец похода: слава, рекорд, новый зал таверны."""
        glory = run.glory() + int(max(0, run.gold) * self.xd["config"].get("treasury_share", 0.25))
        self.glory += glory                         # казна: награда похода + доля оставшегося золота
        if run.result == "victory":
            self.wins += 1
            self.chapter_wins[run.chapter] = self.chapter_wins.get(run.chapter, 0) + 1   # открывает следующие главы
            top = len(self.xd["config"]["tiers"]) - 1
            if run.chapter == "swamp":
                if run.tier >= self.tier_open and self.tier_open < top:
                    self.tier_open = run.tier + 1          # победа открывает следующую сложность
            elif run.tier >= self.chapter_tiers.get(run.chapter, 0) and run.tier < top:
                self.chapter_tiers[run.chapter] = run.tier + 1
        self.best_act = max(self.best_act, run.act + (1 if run.result == "victory" else 0))
        for k, v in run.trophies.items():          # трофеи глав остаются и после поражения
            self.trophies[k] = self.trophies.get(k, 0) + v
        keep = 1.0 if run.result == "victory" else self.xd["config"].get("mat_drops", {}).get("defeat_keep", 1.0)
        self.add_mats({k: int(v * keep) for k, v in getattr(run, "loot", {}).items()})   # материалы — в мастерские
        found = self.rough_drops(run)                # редкость: настоящий самоцвет среди крошки
        vets = []
        self.bury_dead(run)
        if run.result == "victory":
            for h in run.heroes:
                run.note(h, "win", f"Победа: {self.xd['chapters'].get(run.chapter, {}).get('name', run.chapter)} пройдена")
                h.feats["runs_won"] = h.feats.get("runs_won", 0) + 1
            run.award_titles()
            vets = self.return_veterans(run)
        else:
            self.to_hall(run, "пал")
        self.run_state = None
        stay = self.xd["tavern"].get("vet_stay", 1)
        old = []
        for h in self.roster:                       # ветеран вне общежития и не на поручении — уходит в свой срок
            if h.vet and not h.dorm and not h.task:
                left = h.vet.get("stay", stay)
                if left <= 1:
                    h.vet.pop("stay", None)
                    self.away = (self.away + [h.to_dict()])[-20:]     # ушёл странствовать — может вернуться
                    continue
                h.vet["stay"] = left - 1
            old.append(h)
        for v in vets:
            if not v.dorm:
                v.vet["stay"] = stay
        back = self._vet_returns()
        self.roster = vets + back + old             # ветераны — первыми в зале (лишних отрежет roll_roster)
        self.news = self.tick_tasks()
        self.refresh_offers()
        self.refresh_market()
        self.refresh_orders()
        self.roll_roster(keep=True)
        self.save()
        return {"glory": glory, "result": run.result, "act": run.act, "counts": dict(run.counts), "chapter": run.chapter,
                "trophies": dict(run.trophies), "veterans": [h.name for h in vets], "news": list(self.news),
                "loot": dict(getattr(run, "loot", {})), "rough": found,
                "heroes": [(h.name, h.cls, h.level) for h in run.heroes]}
