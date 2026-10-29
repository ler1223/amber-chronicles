"""Мета-прогресс между вылазками: главы и их сложности (регионы, боссы), янтарь, лагерь, арсенал,
герои (найм, отряд, мастерство, билды).

Хранится в json. Без pygame — проверяется тестами. path=None — профиль только в памяти (тесты, демо).
"""
import copy
import json
import os

from . import meta
from .run import Run

VERSION = 4


class Profile:
    def __init__(self, data, path=None, sandbox=False):
        """sandbox — песочница: открыто всё (герои, главы, сложности, регионы, лагерь, арсенал), очков с запасом."""
        self.data = data
        self.sandbox = sandbox
        self.cfg = data.config["meta"]
        self.path = path
        self.biome_id = self.cfg["biome"]          # выбранная глава
        self.difficulty = "normal"                 # выбранная сложность главы
        self.progress = {}                         # глава -> сложность -> {"captured": [...], "done": bool}
        self.amber = 0
        self.expeditions = 0
        self.victories = 0
        self.heroes = {cls: meta.new_hero() for cls in data.classes}
        self.unlocked = [c for c, v in data.classes.items() if v.get("unlock", 0) == 0]   # нанятые герои
        self.squad = list(data.squad["units"])                                            # кто идёт в вылазку
        self.arsenal = []         # трофейные предметы — навсегда
        self.camp = {}            # id улучшения лагеря -> уровень
        self.formation = {}       # герой отряда -> клетка зоны высадки [x, y] (x 0..2, y 0..5)
        self.seen_heroes = []     # о ком уже показали «Новые союзники»
        self.presets = [None, None, None]   # сохранённые составы: {"squad": [...], "formation": {...}}
        if path and os.path.exists(path):
            self._load()
        if sandbox:
            self.open_everything()
        self.sync_heroes()

    def open_everything(self):
        """Песочница: всё нанято и открыто, мастерство на максимуме, лагерь улучшен, весь арсенал в наличии.
        Выбор героев (пути, ветки, таланты, предметы) сохраняется между запусками."""
        self.amber = max(self.amber, 999999)
        self.unlocked = list(self.data.classes)
        top = self.data.config["mastery"]["xp_levels"][-1]
        for hero in self.heroes.values():
            hero["xp"] = max(hero["xp"], top)
            hero["bonus_points"] = 40
        self.camp = {uid: len(up["costs"]) for uid, up in self.data.camp["upgrades"].items()}
        self.arsenal = list(self.data.items)

    # ---------- хранение ----------

    def _load(self):
        with open(self.path, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("version") not in (1, 2, 3, VERSION) or d.get("biome") not in self.data.biomes:
            return  # чужой формат — начинаем заново
        self.biome_id = d["biome"]
        if d.get("difficulty") in self.data.config["difficulties"]:
            self.difficulty = d["difficulty"]
        if "progress" in d:
            for cid, diffs in d["progress"].items():
                if cid not in self.data.biomes:
                    continue
                ids = {r["id"] for r in self.data.biomes[cid]["regions"]}
                for diff, st in diffs.items():
                    if diff in self.data.config["difficulties"]:
                        self._state(cid, diff).update(captured=[r for r in st.get("captured", []) if r in ids],
                                                      done=bool(st.get("done")))
        else:   # v1–v3: была одна глава без сложностей
            ids = {r["id"] for r in self.biome["regions"]}
            self._state(self.biome_id, "normal").update(
                captured=[r for r in d.get("captured", []) if r in ids], done=bool(d.get("biome_done")))
        if not self.difficulty_unlocked(self.biome_id, self.difficulty):
            self.biome_id, self.difficulty = self.cfg["biome"], "normal"
        self.amber = d.get("amber", 0)
        self.expeditions = d.get("expeditions", 0)
        self.victories = d.get("victories", 0)
        # v1 → v2: героев, арсенала и лагеря ещё не было — остаются по умолчанию
        for cls, h in d.get("heroes", {}).items():
            if cls in self.heroes:
                hero = meta.new_hero()
                hero.update({k: v for k, v in h.items() if k in hero})
                self._sanitize_hero(cls, hero)
                self.heroes[cls] = hero
        self.arsenal = [i for i in d.get("arsenal", []) if i in self.data.items]
        # v2 → v3: найма и выбора отряда не было — открыты базовые, отряд по умолчанию
        hired = [c for c in d.get("unlocked", []) if c in self.data.classes]
        self.unlocked = list(dict.fromkeys(self.unlocked + hired))
        squad = [c for c in d.get("squad", self.squad) if c in self.unlocked]
        self.squad = list(dict.fromkeys(squad))[:self.squad_size()] or list(self.data.squad["units"])
        self.camp = {u: lvl for u, lvl in d.get("camp", {}).items() if u in self.data.camp["upgrades"]}
        self.formation = {c: list(p) for c, p in d.get("formation", {}).items() if c in self.squad and self._cell_ok(p)}
        self.seen_heroes = [c for c in d.get("seen_heroes", []) if c in self.data.classes]
        self.presets = [(p if p and all(c in self.data.classes for c in p.get("squad", [])) else None)
                        for p in (d.get("presets") or [None] * 3)][:3] + [None] * (3 - len(d.get("presets") or []))

    def _sanitize_hero(self, cls, hero):
        """Данные могли поменяться между версиями: выкидываем исчезнувшие пути, ветки, таланты."""
        if hero["path"] not in meta.paths_for(self.data, cls):
            hero["path"] = None
        skills = meta.hero_skills(self.data, cls, hero)
        hero["branches"] = {sid: list(v) for sid, v in hero["branches"].items()
                            if sid in skills and sid in self.data.branches and v[0] in ("A", "B")}
        hero["talents"] = [t for t in hero["talents"] if t in self.data.talents
                           and meta.talent_fits(self.data, cls, hero, t)]
        hero["loadout"] = [i for i in hero["loadout"] if i in self.data.items]
        meta.trim_to_points(self.data, hero)

    def save(self):
        if not self.path:
            return
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        d = {"version": VERSION, "biome": self.biome_id, "difficulty": self.difficulty, "progress": self.progress,
             "amber": self.amber, "expeditions": self.expeditions, "victories": self.victories,
             "heroes": self.heroes, "arsenal": self.arsenal, "camp": self.camp, "unlocked": self.unlocked,
             "squad": self.squad, "formation": self.formation, "presets": self.presets,
             "seen_heroes": self.seen_heroes}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    # ---------- главы и сложности ----------

    def _state(self, cid, diff):
        return self.progress.setdefault(cid, {}).setdefault(diff, {"captured": [], "done": False})

    @property
    def captured(self):
        """Захваченные регионы выбранной главы на выбранной сложности."""
        return self._state(self.biome_id, self.difficulty)["captured"]

    @captured.setter
    def captured(self, value):
        self._state(self.biome_id, self.difficulty)["captured"] = list(value)

    @property
    def biome_done(self):
        return self._state(self.biome_id, self.difficulty)["done"]

    @biome_done.setter
    def biome_done(self, value):
        self._state(self.biome_id, self.difficulty)["done"] = bool(value)

    def chapters(self):
        return sorted(self.data.biomes, key=lambda c: self.data.biomes[c].get("order", 0))

    def done(self, cid, diff="normal"):
        return self.progress.get(cid, {}).get(diff, {}).get("done", False)

    def chapter_unlocked(self, cid):
        """Глава открывается победой над боссом предыдущей на обычной сложности."""
        order = self.chapters()
        i = order.index(cid)
        return self.sandbox or i == 0 or self.done(order[i - 1], "normal")

    def difficulty_unlocked(self, cid, diff):
        """Сложность открывается победой над боссом главы на предыдущей сложности."""
        levels = self.data.config["difficulty_order"]
        i = levels.index(diff)
        return self.sandbox or (self.chapter_unlocked(cid) and (i == 0 or self.done(cid, levels[i - 1])))

    def set_chapter(self, cid, diff=None):
        diff = diff or self.difficulty
        if not self.difficulty_unlocked(cid, diff):
            diff = "normal"
        if not self.difficulty_unlocked(cid, diff):
            return False
        self.biome_id, self.difficulty = cid, diff
        self.save()
        return True

    # ---------- карта главы ----------

    @property
    def biome(self):
        return self.data.biomes[self.biome_id]

    def region(self, rid):
        return next(r for r in self.biome["regions"] if r["id"] == rid)

    def boss_need(self):
        return self.biome["boss_after"]

    def regular_captured(self):
        return [rid for rid in self.captured if not self.region(rid).get("boss")]

    def lock_reason(self, rid):
        """None — регион доступен, иначе причина для подсказки."""
        if self.sandbox:
            return None
        r = self.region(rid)
        reachable = r.get("start") or any(link in self.captured for link in r["links"])
        if r.get("boss") and len(self.regular_captured()) < self.boss_need():
            return f"Нужно захватить {self.boss_need()} региона ({len(self.regular_captured())}/{self.boss_need()})"
        if not reachable:
            return "Сначала захватите соседний регион"
        return None

    def available(self):
        return [r["id"] for r in self.biome["regions"] if self.lock_reason(r["id"]) is None]

    # ---------- лагерь ----------

    def camp_level(self, uid):
        return self.camp.get(uid, 0)

    def camp_cost(self, uid):
        """Цена следующего уровня или None, если улучшение на максимуме."""
        costs = self.data.camp["upgrades"][uid]["costs"]
        lvl = self.camp_level(uid)
        return costs[lvl] if lvl < len(costs) else None

    def buy_upgrade(self, uid):
        cost = self.camp_cost(uid)
        if cost is None or self.amber < cost:
            return False
        self.amber -= cost
        self.camp[uid] = self.camp_level(uid) + 1
        self.save()
        return True

    def region_bonuses(self):
        """Бонусы всех захваченных регионов всех глав — каждый один раз, на какой бы сложности ни взяли."""
        regions = {}
        for cid, diffs in self.progress.items():
            for st in diffs.values():
                for rid in st["captured"]:
                    regions[(cid, rid)] = True
        out = []
        for cid, rid in regions:
            r = next((r for r in self.data.biomes[cid]["regions"] if r["id"] == rid), None)
            if r and r.get("bonus"):
                out.append(r["bonus"])
        return out

    def bonuses(self):
        """Суммарные бонусы захваченных регионов и лагеря: {тип: значение}."""
        out = {}
        for b in self.region_bonuses():
            out[b["type"]] = out.get(b["type"], 0) + b["value"]
        for uid, lvl in self.camp.items():
            up = self.data.camp["upgrades"][uid]
            out[up["bonus"]] = out.get(up["bonus"], 0) + up["per_level"] * lvl
        return out

    # ---------- герои: найм и отряд ----------

    def squad_size(self):
        return self.data.config["meta"].get("squad_size", 4)

    def unlock_cost(self, cls):
        return self.data.classes[cls].get("unlock", 0)

    def sync_heroes(self):
        """Герои бесплатны: каждый вступает в лагерь, как только открыта его глава (базовые — сразу).
        Возвращает тех, кто вступил сейчас."""
        new = [c for c in self.data.classes if c not in self.unlocked and self.hero_available(c)]
        self.unlocked += new
        return new

    def hero_available(self, cls):
        """Можно ли нанять: базовые — всегда, остальные — когда открыта их глава (data/hero_unlocks.json)."""
        cid = self.data.hero_chapter.get(cls)
        return self.sandbox or cls in self.unlocked or cid is None or self.chapter_unlocked(cid)

    def hero_lock_reason(self, cls):
        cid = self.data.hero_chapter.get(cls)
        if self.hero_available(cls) or cid is None:
            return None
        b = self.data.biomes[cid]
        return f"Откроется в главе {b.get('order', 0) + 1} «{b['name']}»"

    def new_heroes(self):
        """Герои открытых глав, о которых ещё не рассказали: [(глава, запись из hero_unlocks)]."""
        self.sync_heroes()
        out = []
        for cid in self.chapters():
            for h in self.data.hero_unlocks.get(cid, []):
                cls = h["cls"]
                if cls not in self.seen_heroes and self.hero_available(cls):
                    out.append((cid, h))
        return out

    def mark_seen(self, classes):
        self.seen_heroes = list(dict.fromkeys(self.seen_heroes + list(classes)))
        self.save()

    def unlock_hero(self, cls):
        """Найма нет: герой открывается своей главой бесплатно. True — герой в лагере."""
        self.sync_heroes()
        return cls in self.unlocked

    def toggle_squad(self, cls):
        """Взять героя в отряд или убрать. Возвращает (успех, причина)."""
        if cls in self.squad:
            if len(self.squad) <= 1:
                return False, "В отряде должен остаться хотя бы один герой"
            self.squad.remove(cls)
        elif cls not in self.unlocked:
            return False, "Героя сначала нужно нанять"
        elif len(self.squad) >= self.squad_size():
            return False, f"В отряде не больше {self.squad_size()} героев — сначала уберите кого-то"
        else:
            self.squad.append(cls)
        self.formation_cells()
        self.save()
        return True, ""

    # ---------- герои и арсенал ----------

    def arsenal_slots(self):
        if self.sandbox:
            return 99
        return self.cfg["arsenal_slots_base"] + int(self.bonuses().get("arsenal_slots", 0))

    def loadout_count(self):
        return sum(len(h["loadout"]) for h in self.heroes.values())

    def loadout_owner(self, iid):
        return next((cls for cls, h in self.heroes.items() if iid in h["loadout"]), None)

    def toggle_loadout(self, cls, iid):
        """Взять предмет арсенала герою на вылазку (предмет того же слота заменяется) или снять его."""
        hero = self.heroes[cls]
        if iid in hero["loadout"]:
            hero["loadout"].remove(iid)
            return True
        if iid not in self.arsenal or self.loadout_owner(iid):
            return False
        slot = self.data.items[iid]["slot"]
        same = [i for i in hero["loadout"] if self.data.items[i]["slot"] == slot]
        if not same and self.loadout_count() >= self.arsenal_slots():
            return False
        for i in same:
            hero["loadout"].remove(i)
        hero["loadout"].append(iid)
        return True

    def trim_loadouts(self):
        while self.loadout_count() > self.arsenal_slots():
            next(h for h in self.heroes.values() if h["loadout"])["loadout"].pop()

    def mastery(self, cls):
        return meta.mastery_level(self.data, self.heroes[cls]["xp"])

    def hero_builds(self):
        self.trim_loadouts()
        out = []
        for cls in self.squad:
            h = self.heroes[cls]
            out.append({"cls": cls, "path": h["path"], "branches": copy.deepcopy(h["branches"]),
                        "talents": list(h["talents"]), "mastery": self.mastery(cls),
                        "autocast": copy.deepcopy(h["autocast"]), "items": list(h["loadout"])})
        return out

    # ---------- вылазка ----------

    def start_run(self, rid, seed=None):
        if rid not in self.available():
            raise ValueError("регион недоступен")
        run = Run(self.data, seed, self.region(rid), self.bonuses(), self.hero_builds(), self.biome_id,
                  self.difficulty)
        run.region_id = rid
        run.formation = self.formation_positions()        # расстановка с экрана «Отряд» — в первый бой
        return run

    # ---------- расстановка отряда ----------

    ZONE = (3, 6)                        # зона высадки: 3 колонки × 6 рядов
    DEFAULT_SPOTS = [(2, 2), (0, 1), (0, 3), (1, 4), (2, 3), (1, 1)]

    def _cell_ok(self, p):
        return isinstance(p, (list, tuple)) and len(p) == 2 and 0 <= p[0] < self.ZONE[0] and 0 <= p[1] < self.ZONE[1]

    def formation_cells(self):
        """Клетка каждого героя отряда; у кого нет — первая свободная из стандартных."""
        taken = {tuple(self.formation[c]) for c in self.squad if c in self.formation}
        for c in self.squad:
            if c not in self.formation:
                spot = next(p for p in self.DEFAULT_SPOTS + [(x, y) for x in range(3) for y in range(6)]
                            if p not in taken)
                self.formation[c] = list(spot)
                taken.add(spot)
        for c in list(self.formation):
            if c not in self.squad:
                del self.formation[c]
        return {c: tuple(self.formation[c]) for c in self.squad}

    def formation_positions(self):
        cells = self.formation_cells()
        return [list(cells[c]) for c in self.squad]

    def hero_at(self, cell):
        cells = self.formation_cells()
        return next((c for c, p in cells.items() if p == tuple(cell)), None)

    def place(self, cls, cell):
        """Поставить героя на клетку зоны. Занятая клетка: свой — меняются местами, чужой — заменяется.
        Возвращает (успех, причина)."""
        cell = tuple(cell)
        if cls not in self.unlocked:
            return False, "Героя сначала нужно нанять"
        if not self._cell_ok(cell):
            return False, "Только в зоне высадки"
        cells = self.formation_cells()
        other = self.hero_at(cell)
        if cls in self.squad:
            if other and other != cls:
                self.formation[other] = list(cells[cls])
            self.formation[cls] = list(cell)
        elif other:
            i = self.squad.index(other)
            self.squad[i] = cls
            del self.formation[other]
            self.formation[cls] = list(cell)
        elif len(self.squad) >= self.squad_size():
            return False, f"В отряде уже {self.squad_size()} — перетащите героя на занятую клетку, чтобы заменить"
        else:
            self.squad.append(cls)
            self.formation[cls] = list(cell)
        self.save()
        return True, ""

    def remove_from_squad(self, cls):
        if cls not in self.squad:
            return False, ""
        if len(self.squad) <= 1:
            return False, "В отряде должен остаться хотя бы один герой"
        self.squad.remove(cls)
        self.formation.pop(cls, None)
        self.save()
        return True, ""

    def save_preset(self, i):
        self.presets[i] = {"squad": list(self.squad), "formation": {c: list(p) for c, p in self.formation_cells().items()}}
        self.save()

    def load_preset(self, i):
        pr = self.presets[i]
        if not pr:
            return False, "Состав пуст — сначала сохраните"
        squad = [c for c in pr["squad"] if c in self.unlocked][:self.squad_size()]
        if not squad:
            return False, "Герои этого состава не наняты"
        self.squad = squad
        self.formation = {c: list(p) for c, p in pr["formation"].items() if c in squad}
        self.formation_cells()
        self.save()
        return True, ""

    def amber_for(self, run, rid):
        """Янтарь за вылазку: бои + награда за стража; повторная зачистка — меньше; поражение — часть."""
        c, r = self.cfg, self.region(rid)
        mult = self.reward_mult()
        amber = run.battles_won * c["amber_per_battle"]
        if run.result == "victory":
            bonus = c["amber_boss"] if r.get("boss") else c["amber_capture"] + c["amber_per_threat"] * r["threat"]
            if rid in self.captured:
                bonus *= c["replay_mult"]
            amber += bonus
        else:
            amber *= c["defeat_keep"]
        return int(round(amber * mult))

    def reward_mult(self, cid=None, diff=None):
        """Награды растут с номером главы и сложностью."""
        cid, diff = cid or self.biome_id, diff or self.difficulty
        order = self.data.biomes[cid].get("order", 0)
        return (1 + self.cfg.get("chapter_reward", 0.25) * order) * self.data.config["difficulties"][diff]["amber"]

    def mastery_xp_for(self, run):
        m = self.data.config["mastery"]
        xp = run.battles_won * m["xp_per_battle"] + (m["xp_win"] if run.result == "victory" else 0)
        return int(round(xp * self.data.config["difficulties"][run.difficulty]["xp"]))

    def trophy_options(self, run):
        """Трофеи за стража/босса: редкие и эпические предметы, которых ещё нет в арсенале."""
        pool = [i for i, it in self.data.items.items() if it["rarity"] in ("rare", "epic") and i not in self.arsenal]
        epic = [i for i in pool if self.data.items[i]["rarity"] == "epic"]
        out = []
        chance = self.data.config["difficulties"][run.difficulty]["epic"]     # на высокой сложности — эпики
        for _ in range(min(self.cfg["trophy_choices"], len(pool))):
            src = [i for i in (epic if epic and run.rng.random() < chance else pool) if i not in out] or \
                  [i for i in pool if i not in out]
            out.append(run.rng.choice(src))
        return out

    def add_trophy(self, iid):
        if iid not in self.arsenal:
            self.arsenal.append(iid)
            self.save()

    def finish_run(self, run):
        """Записывает итог вылазки в профиль и сохраняет. Возвращает сводку для экрана итогов."""
        rid = run.region_id
        amber = self.amber_for(run, rid)
        new_capture = run.result == "victory" and rid not in self.captured
        self.amber += amber
        self.expeditions += 1
        if run.result == "victory":
            self.victories += 1
        if new_capture:
            self.captured.append(rid)
        boss_down = run.result == "victory" and self.region(rid).get("boss", False)
        first_boss = boss_down and not self.biome_done
        opened = []
        if boss_down:
            before = {(c, d) for c in self.chapters() for d in self.data.config["difficulty_order"]
                      if self.difficulty_unlocked(c, d)}
            self.biome_done = True
            opened = [(c, d) for c in self.chapters() for d in self.data.config["difficulty_order"]
                      if self.difficulty_unlocked(c, d) and (c, d) not in before]
        xp = self.mastery_xp_for(run)
        mastery = {}
        for m in run.squad:
            h = self.heroes[m.cls]
            before = self.mastery(m.cls)
            h["xp"] += xp
            h["autocast"] = copy.deepcopy(m.autocast)
            mastery[m.cls] = (before, self.mastery(m.cls))
        trophies = self.trophy_options(run) if run.result == "victory" else []
        self.sync_heroes()                 # победа над боссом открыла главу — её герои уже в лагере
        self.save()
        bonus = self.region(rid).get("bonus") if new_capture else None
        return {"amber": amber, "captured": new_capture, "bonus": bonus, "biome_done": first_boss,
                "mastery_xp": xp, "mastery": mastery, "trophies": trophies, "opened": opened}
