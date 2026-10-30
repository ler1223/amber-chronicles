"""Вылазка: отряд между боями (HP, уровни, предметы, руны, реликвии), золото, карта с развилками.

Направление героя (путь, ветки, таланты) выбирается на подготовке (sim/meta.py) и в вылазке не меняется;
внутри вылазки отряд растёт вертикально: уровни дают статы, предметы, руны навыков и реликвии отряда.
Без pygame — всё проверяется тестами.
"""
import copy
import random

from . import autocast
from . import stats
from .build import build_proto, class_skills, rune_fits
from .data import RARITIES
from .teams import PLAYER

NODE_NAMES = {"battle": "Бой", "elite": "Элита", "boss": "Босс", "guard": "Страж", "rest": "Отдых", "shop": "Торговец"}
SLOT_NAMES = {"weapon": "Оружие", "armor": "Броня", "trinket": "Амулет"}
RARITY_NAMES = {"common": "обычный", "rare": "редкий", "epic": "эпический"}


class Member:
    """Герой в вылазке. build — выбор подготовки: path, branches, talents, mastery, autocast, items (из арсенала)."""

    def __init__(self, cls, build=None):
        b = build or {}
        self.cls = cls
        self.path = b.get("path")
        self.branches = {sid: tuple(v) for sid, v in b.get("branches", {}).items()}
        self.talents = list(b.get("talents", []))
        self.mastery = b.get("mastery", 1)
        self.autocast = copy.deepcopy(b.get("autocast", {}))   # переживает бои и вылазки
        self.items = {}        # слот -> id предмета
        self.runes = {}        # skill id -> [rune id]
        self.level = b.get("level", 1)       # сюжет: уровень героя растёт от вылазки к вылазке
        self.xp = b.get("xp", 0)
        self.hp = 0
        self.rpg = copy.deepcopy(b.get("rpg") or stats.new_rpg())   # режим героев: постоянный уровень


class Run:
    """region — регион биома (data/biomes.json): короткая карта и страж в конце; без него — полная вылазка
    с боссом. bonus — постоянные бонусы меты {тип: значение}. heroes — билды героев с подготовки."""

    def __init__(self, data, seed=None, region=None, bonus=None, heroes=None, chapter="swamp", difficulty="normal",
                 mode="base"):
        self.data = data
        self.stats = mode in ("stats", "story")   # режим героев и сюжет: уровень героя и атрибуты навсегда
        self.cfg = data.config["run"]
        self.region = region
        self.chapter = chapter            # глава (data/biomes.json): пул боёв и сила врагов
        self.difficulty = difficulty      # сложность главы: статы, добавочные враги, модификаторы
        self.bonus = dict(bonus or {})
        self.seed = seed if seed is not None else random.randrange(1_000_000)
        self.rng = random.Random(self.seed)
        self.gold = self.cfg["start_gold"] + int(self.bonus.get("start_gold", 0))
        self.inventory = []
        builds = heroes or [{"cls": c} for c in data.squad["units"]]
        self.squad = [Member(b["cls"], b) for b in builds]
        if self.stats:
            for m in self.squad:
                m.level, m.xp = m.rpg["level"], m.rpg["xp"]
        for b, m in zip(builds, self.squad):
            for iid in b.get("items", []):
                m.items[data.items[iid]["slot"]] = iid
        self.relics = []
        self.relics += self.random_relics(int(self.bonus.get("start_relics", 0)))
        self.rerolls = int(self.bonus.get("rerolls", 0))
        for m in self.squad:
            m.hp = self.max_hp(m)
        self.nodes = generate_map(data, self.rng, region, chapter)
        self.node = None          # id текущего узла
        self.path = []            # пройденные узлы
        self.formation = None     # последняя расстановка
        self.result = None        # None | "victory" | "defeat"
        self.battles_won = 0
        self.shop_stock = []

    @property
    def threat(self):
        return self.region["threat"] if self.region else 1

    def region_level(self):
        return stats.region_level(self.data, self.chapter, self.region, self.difficulty)

    def enemy_scale(self):
        """Множители HP/урона врагов: угроза региона × сила главы × сложность. В режиме героев — уровень региона:
        бой сам считает каждому врагу его уровень (с титулами)."""
        if self.stats:
            return {"level": self.region_level(), "stats": True}
        k = self.data.config["meta"]["threat_scale"]
        lvl = self.threat - 1
        power = self.data.biomes.get(self.chapter, {}).get("power", {})
        diff = self.data.config["difficulties"][self.difficulty]
        return {"hp": (1 + k["hp"] * lvl) * power.get("hp", 1.0) * diff["hp"],
                "damage": (1 + k["damage"] * lvl) * power.get("damage", 1.0) * diff["damage"]}

    # ---------- отряд ----------

    def extra_mods(self, m):
        """Проценты уровня вылазки, мастерства и лагеря + модификаторы реликвий."""
        if self.stats:                     # режим героев: всё растёт от атрибутов, лагерь и реликвии — как обычно
            mods = list(stats.derive(self.data, m.cls, m.rpg)["mods"])
            for key, stat in (("hp_pct", "hp"), ("power_pct", "power")):
                if self.bonus.get(key):
                    mods.append({"stat": stat, "mult": 1 + self.bonus[key]})
            if self.bonus.get("ap"):
                mods.append({"stat": "ap_max", "add": self.bonus["ap"]})
            for rid in self.relics:
                mods += self.data.relics[rid].get("mods", [])
            return mods
        ls = self.cfg["level_stats"]
        lvl = m.level - 1
        mastery = 1 + self.data.config["mastery"]["stat_per_level"] * (m.mastery - 1)
        power_pct = 1 + self.bonus.get("power_pct", 0)
        mods = [
            {"stat": "hp", "mult": (1 + ls["hp"] * lvl) * mastery * (1 + self.bonus.get("hp_pct", 0))},
            {"stat": "power", "mult": (1 + ls["power"] * lvl) * mastery * power_pct},
            {"stat": "atk_damage", "mult": (1 + ls["atk"] * lvl) * mastery * power_pct},
        ]
        if self.bonus.get("ap"):
            mods.append({"stat": "ap_max", "add": self.bonus["ap"]})
        for rid in self.relics:
            mods += self.data.relics[rid].get("mods", [])
        return mods

    def proto(self, m):
        p = build_proto(self.data, m.cls, m.talents, list(m.items.values()), m.branches, self.extra_mods(m),
                        m.path, m.runes)
        p["level"] = m.level
        if self.stats:
            stats.apply_to_proto(p, stats.derive(self.data, m.cls, m.rpg))
        return p

    def max_hp(self, m):
        return self.proto(m)["hp"]

    def autocast_for(self, m):
        """Настройки автокаста под текущий билд: новые навыки получают умолчания, лишние условия отбрасываются."""
        m.autocast = autocast.settings_for(self.proto(m)["skill_defs"], m.autocast)
        return m.autocast

    def combat_squad(self):
        return [{"cls": m.cls, "proto": self.proto(m), "hp": m.hp, "autocast": self.autocast_for(m)}
                for m in self.squad]

    def combat_fx(self):
        """Боевые эффекты реликвий: множители перемножаются, остальное складывается."""
        fx = {}
        for rid in self.relics:
            for k, v in self.data.relics[rid].get("combat", {}).items():
                fx[k] = fx.get(k, 1.0) * v if k.endswith("_mult") else fx.get(k, 0) + v
        return fx

    def relic_value(self, key):
        return sum(self.data.relics[rid].get("run", {}).get(key, 0) for rid in self.relics)

    def _keep_hp(self, members, fn):
        """Меняет билд и сохраняет урон: прибавка к макс. HP прибавляется и к текущему."""
        befores = [self.max_hp(m) for m in members]
        fn()
        for m, before in zip(members, befores):
            after = self.max_hp(m)
            m.hp = max(1, min(after, m.hp + max(0, after - before)))
            self.autocast_for(m)

    def _change_build(self, m, fn):
        self._keep_hp([m], fn)

    def heal_all(self, pct):
        for m in self.squad:
            mx = self.max_hp(m)
            m.hp = min(mx, m.hp + int(round(mx * pct)))

    def xp_to_next(self, m):
        return stats.xp_to_next(self.data, m.level) if self.stats else self.cfg["xp_per_level"]

    def stats_xp(self, node_type):
        """Режим героев: опыт за победу каждому герою (по уровню региона и разнице уровней)."""
        ups = []
        lvl = self.region_level()
        for m in self.squad:
            gained = stats.battle_xp(self.data, node_type, lvl, m.level)
            before = m.rpg["level"]
            self._change_build(m, lambda m=m, g=gained: stats.add_xp(self.data, m.rpg, g))
            m.level, m.xp = m.rpg["level"], m.rpg["xp"]
            ups += [m] * (m.rpg["level"] - before)
        return ups

    def gain_xp(self, amount):
        """Опыт всем поровну; уровень сразу даёт статы (без выбора — направление задано на подготовке)."""
        ups = []
        for m in self.squad:
            if m.level >= self.cfg["max_level"]:
                continue
            m.xp += amount
            while m.xp >= self.xp_to_next(m) and m.level < self.cfg["max_level"]:
                m.xp -= self.xp_to_next(m)
                self.level_up(m)
                ups.append(m)
            if m.level >= self.cfg["max_level"]:
                m.xp = 0
        return ups

    def level_up(self, m):
        if m.level < self.cfg["max_level"]:
            self._change_build(m, lambda: setattr(m, "level", m.level + 1))

    # ---------- предметы ----------

    def equip(self, m, item_id):
        """Надеть предмет из сумки (или новый) в его слот; старый из этого слота уходит в сумку."""
        if item_id in self.inventory:
            self.inventory.remove(item_id)
        slot = self.data.items[item_id]["slot"]
        old = m.items.get(slot)
        self._change_build(m, lambda: m.items.__setitem__(slot, item_id))
        if old:
            self.inventory.append(old)

    def unequip(self, m, slot):
        if m.items.get(slot):
            self.inventory.append(m.items[slot])
            self._change_build(m, lambda: m.items.pop(slot))

    def owned_items(self):
        return set(self.inventory) | {i for m in self.squad for i in m.items.values()}

    def rarity_weights(self, pool):
        w = dict(self.cfg["rarity_weights"][pool])
        shift = w["common"] * min(1.0, self.bonus.get("rare_chance", 0))
        w["common"] -= shift
        w["rare"] += shift * 0.7
        w["epic"] += shift * 0.3
        return w

    def random_items(self, n, pool="normal"):
        """n разных предметов: редкость по весам пула (normal/elite/shop), без уже имеющихся."""
        owned = self.owned_items()
        out = []
        w = self.rarity_weights(pool)
        for _ in range(n):
            by_rarity = {r: [i for i, it in self.data.items.items()
                             if it["rarity"] == r and i not in owned and i not in out] for r in RARITIES}
            choices = [r for r in RARITIES if by_rarity[r] and w[r] > 0] or [r for r in RARITIES if by_rarity[r]]
            if not choices:
                break
            r = self.rng.choices(choices, [max(w[c], 0.01) for c in choices])[0]
            out.append(self.rng.choice(by_rarity[r]))
        return out

    # ---------- руны и реликвии ----------

    def rune_targets(self, m):
        """Навыки героя, которые можно усилить руной: свои (класс, путь, таланты), не от предметов."""
        p = self.proto(m)
        own = class_skills(self.data, m.cls, m.path)
        own += [mm["new_skill"] for t in m.talents for mm in self.data.talents[t]["mods"] if "new_skill" in mm]
        return [(sid, p["skill_defs"][sid]) for sid in own if sid in p["skill_defs"]]

    def rune_offers(self, n):
        cand = []
        cap = self.cfg["max_runes_per_skill"]
        for i, m in enumerate(self.squad):
            for sid, sk in self.rune_targets(m):
                if len(m.runes.get(sid, [])) < cap:
                    cand += [(i, sid, rid) for rid in self.data.runes if rune_fits(self.data, sk, rid)]
        self.rng.shuffle(cand)
        out, seen = [], set()
        for i, sid, rid in cand:
            if (i, sid) not in seen and len(out) < n:
                out.append({"type": "rune", "member": i, "skill": sid, "rune": rid})
                seen.add((i, sid))
        return out

    def apply_rune(self, offer):
        m = self.squad[offer["member"]]
        self._change_build(m, lambda: m.runes.setdefault(offer["skill"], []).append(offer["rune"]))

    def random_relics(self, n):
        pool = [r for r in self.data.relics if r not in getattr(self, "relics", [])]
        return self.rng.sample(pool, min(n, len(pool)))

    def add_relic(self, rid):
        self._keep_hp(self.squad, lambda: self.relics.append(rid))

    # ---------- карта ----------

    def available(self):
        if self.result:
            return []
        if self.node is None:
            return [n["id"] for n in self.nodes.values() if n["layer"] == 0]
        return list(self.nodes[self.node]["next"])

    def enter(self, node_id):
        if node_id not in self.available():
            raise ValueError("узел недоступен")
        self.node = node_id
        self.path.append(node_id)
        node = self.nodes[node_id]
        if node["type"] == "shop":
            self.shop_stock = self.shop_offers()
        return node

    # ---------- бой ----------

    def finish_battle(self, combat, formation=None):
        """Переносит итог боя в вылазку. Возвращает сводку для экрана наград."""
        if formation:                      # храним в рядах 0..5: карта следующего боя может быть другой высоты
            h = combat.grid.h
            self.formation = [[x, round(y * 5 / (h - 1))] for x, y in formation] if h != 6 else formation
        node = self.nodes[self.node]
        units = [u for u in combat.units if u.team == PLAYER]
        for m, u in zip(self.squad, units):
            m.hp = u.hp if u.alive else self.cfg["downed_hp"]
            m.autocast = u.autocast  # настройки, изменённые в бою, переходят дальше
        if combat.result != "victory":
            self.result = "defeat"
            return {"result": "defeat"}
        self.battles_won += 1
        if not node["next"]:   # последний узел карты: босс или страж региона
            self.result = "victory"
            if self.stats:
                self.stats_xp(node["type"])
            return {"result": "victory", "boss": True}
        self.heal_all(self.cfg["post_battle_heal"] + self.bonus.get("post_battle_heal", 0)
                      + self.relic_value("post_battle_heal"))
        rw = self.cfg["rewards"][node["type"] if node["type"] in self.cfg["rewards"] else "normal"]
        gold = rw["gold"] + self.relic_value("gold_per_battle")
        self.gold += gold
        if self.stats:
            xp = stats.battle_xp(self.data, node["type"], self.region_level(), self.squad[0].level)
            ups = self.stats_xp(node["type"])
        else:
            xp = rw["xp"]
            ups = self.gain_xp(xp)
        return {"result": "victory", "gold": gold, "xp": xp, "level_ups": ups,
                "fallen": [m for m, u in zip(self.squad, units) if not u.alive]}

    # ---------- награды и торговец ----------

    def reward_options(self):
        """Обычный бой: предмет, руна, лечение или золото. Элита: реликвия, редкий предмет, руна."""
        elite = self.nodes[self.node]["type"] == "elite"
        out = []
        if elite:
            out += [{"type": "relic", "relic": r} for r in self.random_relics(1)]
        out += [{"type": "item", "item": i} for i in self.random_items(1, "elite" if elite else "normal")]
        out += self.rune_offers(1)
        if not elite:
            out.append(self.rng.choice([{"type": "heal", "pct": self.cfg["reward_heal"]},
                                        {"type": "gold", "amount": self.cfg["reward_gold"]}]))
        while len(out) < 3:
            out.append({"type": "gold", "amount": self.cfg["reward_gold"]})
        return out

    def reroll(self):
        """Переброс наград (бонус лагеря «Счастливая монета»). None — перебросов не осталось."""
        if self.rerolls <= 0:
            return None
        self.rerolls -= 1
        return self.reward_options()

    def apply_reward(self, r):
        """Золото, лечение, руна и реликвия применяются сразу; предмет возвращается — игрок выберет, кому его отдать."""
        if r["type"] == "gold":
            self.gold += r["amount"]
        elif r["type"] == "heal":
            self.heal_all(r["pct"])
        elif r["type"] == "rune":
            self.apply_rune(r)
        elif r["type"] == "relic":
            self.add_relic(r["relic"])
        elif r["type"] == "item":
            return r["item"]
        return None

    def price(self, base):
        return int(round(base * (1 - min(0.9, self.bonus.get("discount", 0)))))

    def shop_offers(self):
        n = self.cfg["shop_items"] - 1 + int(self.bonus.get("shop_items", 0))
        out = [{"type": "item", "item": i, "price": self.price(self.data.items[i]["price"])}
               for i in self.random_items(n, "shop")]
        out += [dict(o, price=self.price(self.cfg["rune_price"])) for o in self.rune_offers(1)]
        out += [{"type": "relic", "relic": r, "price": self.price(self.cfg["relic_price"])}
                for r in self.random_relics(1)]
        return out

    def buy(self, offer):
        """Покупка у торговца: (успех, id предмета для выбора героя или None)."""
        if offer not in self.shop_stock or self.gold < offer["price"]:
            return False, None
        self.gold -= offer["price"]
        self.shop_stock.remove(offer)
        return True, self.apply_reward(offer)

    def heal_price(self):
        return self.price(self.cfg["shop_heal"]["price"])

    def buy_heal(self):
        if self.gold < self.heal_price():
            return False
        self.gold -= self.heal_price()
        self.heal_all(self.cfg["shop_heal"]["pct"])
        return True


def generate_map(data, rng, region=None, chapter="swamp"):
    """Слои узлов с рёбрами к соседним узлам следующего слоя. Первый слой — бой, предпоследний — отдых/торговец,
    последний — босс (или страж региона). В середине — случайные типы по весам, минимум одна элита
    (если регион не отключил это через force_elite)."""
    cfg = data.config["run"]
    region = region or {}
    layers = region.get("layers", cfg["map_layers"])
    final = None
    if region:
        final = next(i for i, e in enumerate(data.encounters) if e["id"] == region["guard"])
    by_kind = {}
    for i, e in enumerate(data.encounters):
        if e.get("chapter", "swamp") != chapter:
            continue                           # бои только своей главы
        by_kind.setdefault((e["kind"], e.get("tier", 1)), []).append(i)
        by_kind.setdefault((e["kind"], None), []).append(i)

    weights = cfg["node_weights"]
    nodes, grid = {}, []
    for L, count in enumerate(layers):
        row = []
        for i in range(count):
            if L == 0:
                t = "battle"
            elif L == len(layers) - 1:
                t = "boss" if not region or region.get("boss") else "guard"
            elif L == len(layers) - 2:
                t = ("rest", "shop")[(i + rng.randrange(2)) % 2] if count > 1 else "rest"
            elif L == 1:
                t = "battle"
            else:
                t = rng.choices(list(weights), list(weights.values()))[0]
            nid = f"{L}-{i}"
            nodes[nid] = {"id": nid, "layer": L, "idx": i, "count": count, "type": t, "next": [], "encounter": None}
            row.append(nid)
        grid.append(row)

    middle = [nid for row in grid[2:-2] for nid in row]
    if middle and region.get("force_elite", True) and not any(nodes[n]["type"] == "elite" for n in middle):
        nodes[rng.choice(middle)]["type"] = "elite"

    tiers = region.get("tiers", cfg["tier_by_layer"])
    last_enc = None
    for row in grid:
        for nid in row:
            n = nodes[nid]
            kind = {"battle": "normal", "elite": "elite", "boss": "boss", "guard": "guard"}.get(n["type"])
            if not kind:
                continue
            if final is not None and n["layer"] == len(layers) - 1:
                n["encounter"] = final
                continue
            tier = tiers[min(n["layer"], len(tiers) - 1)] if kind == "normal" else None
            pool = by_kind.get((kind, tier)) or by_kind[(kind, None)]
            choices = [e for e in pool if e != last_enc] or pool
            n["encounter"] = last_enc = rng.choice(choices)

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
    return nodes
