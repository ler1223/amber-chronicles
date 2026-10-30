"""Сюжетный режим (data/story.json): JRPG-начало. Отдельный профиль — основная игра и режим героев не меняются.

Начинаем вдвоём (Воин и Пиромант); в каждой вылазке главы 1–2 к отряду присоединяется новый герой — в бой он
идёт сразу, с обучением своей механике. Вылазка — цепочка 3–4 боёв: между боями только частичное лечение и
перестановка, награда (янтарь, трофей) — в конце. Предметы покупаются у торговца в лагере, улучшения — в кузнице.

Профиль сюжета — тот же Profile (герои, подготовка, арсенал, лагерь, отряд), но состав героев задаёт сюжет:
открыты только присоединившиеся, в бою до 6. Прогресс — как в режиме героев (sim/stats.py): уровень героя,
атрибуты и очки остаются навсегда; у каждой вылазки свой уровень врагов (data/story.json, «level»).
"""
import copy
import json
import os
import random

from sim.profile import Profile
from sim.run import Run

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_story():
    with open(os.path.join(ROOT, "data", "story.json"), encoding="utf-8") as f:
        return json.load(f)


def story_data(data, story=None):
    """Копия данных игры с боями сюжета (обучающие карты) в конце списка боёв."""
    story = story or load_story()
    sd = copy.copy(data)
    known = {e["id"] for e in data.encounters}
    sd.encounters = list(data.encounters) + [e for e in story["encounters"] if e["id"] not in known]
    sd.story = story
    return sd


class StoryProfile(Profile):
    def __init__(self, data, path=None, sandbox=False):
        self.story = getattr(data, "story", None) or load_story()
        self.done = []             # пройденные вылазки (id)
        self.joined = list(self.story["start"])
        self.help_seen = False     # справка окна героя показана
        super().__init__(data, path, sandbox=sandbox, mode="story")
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    d = json.load(f).get("story", {})
                ids = {x["id"] for x in self.expeditions_list()}
                self.done = [x for x in d.get("done", []) if x in ids]
                self.joined = [c for c in d.get("joined", self.joined) if c in data.classes] or self.joined
                self.help_seen = bool(d.get("help_seen"))
            except (OSError, ValueError):
                pass
        if sandbox:
            self.joined = [c for c in self.all_story_heroes()]
        self.sync_heroes()
        self.squad = [c for c in self.squad if c in self.unlocked][:self.squad_size()] or self.unlocked[:self.squad_size()]

    # ---------- сюжет ----------

    def expeditions_list(self):
        return [dict(e, chapter=ch["id"], chapter_name=ch["name"]) for ch in self.story["chapters"]
                for e in ch["expeditions"]]

    def all_story_heroes(self):
        return list(self.story["start"]) + [e["join"] for e in self.expeditions_list() if e.get("join")]

    def current(self):
        """Следующая вылазка сюжета или None — всё пройдено."""
        return next((e for e in self.expeditions_list() if e["id"] not in self.done), None)

    def character(self, who):
        return self.story["characters"].get(who, {"name": who, "color": [220, 220, 220]})

    # ---------- герои: состав задаёт сюжет ----------

    def sync_heroes(self):
        self.unlocked = [c for c in self.joined if c in self.data.classes]
        return []

    def new_heroes(self):
        return []

    def hero_available(self, cls):
        return cls in self.unlocked

    def hero_lock_reason(self, cls):
        return "Присоединится по сюжету"

    def squad_size(self):
        return min(self.story["squad_max"], max(1, len(self.unlocked)))

    def level(self, cls):
        return self.heroes[cls]["rpg"]["level"]

    # ---------- вылазка: цепочка боёв ----------

    def start_chain(self, seed=None):
        """Начать текущую вылазку: присоединить героя сюжета (он идёт в бой обязательно) и собрать цепочку."""
        exp = self.current()
        if exp is None:
            raise ValueError("сюжет пройден")
        join = exp.get("join")
        if join and join not in self.joined:
            # новичок вступает на среднем уровне отряда (как в JRPG): не отстаёт и не тянет назад
            lv = [self.level(c) for c in self.unlocked]
            rpg = self.heroes[join]["rpg"]
            rpg["level"] = max(rpg["level"], int(round(sum(lv) / len(lv))) if lv else 1)
            self.joined.append(join)
            self.sync_heroes()
        cap = self.squad_size()
        if join:
            rest = [c for c in self.squad if c != join and c in self.unlocked]
            self.squad = [join] + rest[:cap - 1]
        else:
            self.squad = [c for c in self.squad if c in self.unlocked][:cap]
        for c in self.unlocked:                        # новенький — в отряд, если есть место
            if len(self.squad) < cap and c not in self.squad:
                self.squad.append(c)
        self.save()
        run = Run(self.data, seed, None, self.bonuses(), self.hero_builds(), exp["chapter"], "normal", mode="story")
        lvl = exp.get("level", 1)
        scale = {"level": lvl, "stats": True, "titles": lvl >= self.story.get("titles_from", 3),
                 "mods": self.story.get("enemy_mods", {})}
        run.enemy_scale = lambda: dict(scale)       # уровень врагов — у вылазки сюжета, а не у региона
        run.region_level = lambda: lvl
        index = {e["id"]: i for i, e in enumerate(self.data.encounters)}
        n = len(exp["battles"])
        run.nodes = {}
        for i, b in enumerate(exp["battles"]):
            enc = self.data.encounters[index[b["encounter"]]]
            kind = "boss" if i == n - 1 and enc.get("kind") in ("boss", "guard", "elite") else "battle"
            run.nodes[i] = {"id": i, "type": kind, "layer": i, "encounter": index[b["encounter"]],
                            "next": [i + 1] if i + 1 < n else [], "story": b}
        run.region_id = exp["id"]
        run.story = exp
        run.formation = self.formation_positions()
        return run

    def finish_chain(self, run):
        """Итог вылазки сюжета: янтарь за бои, опыт мастерства, уровни героев; победа — вылазка пройдена,
        трофеи на выбор. Возвращает сводку."""
        rw = self.story["rewards"]
        win = run.result == "victory"
        amber = rw["amber_per_battle"] * run.battles_won + (rw["amber_bonus"] if win else 0)
        self.amber += amber
        self.expeditions += 1
        if win:
            self.victories += 1
            if run.region_id not in self.done:
                self.done.append(run.region_id)
        xp = self.mastery_xp_for(run)
        for m in run.squad:
            h = self.heroes[m.cls]
            h["xp"] += xp
            h["autocast"] = copy.deepcopy(m.autocast)
            self.heroes[m.cls]["rpg"] = copy.deepcopy(m.rpg)
        trophies = self.trophies(run) if win else []
        self.save()
        return {"amber": amber, "mastery_xp": xp, "trophies": trophies, "result": run.result,
                "captured": False, "bonus": None, "biome_done": False, "mastery": {}, "opened": []}

    def trophies(self, run):
        pool = [i for i, it in self.data.items.items() if it["rarity"] in ("rare", "epic") and i not in self.arsenal]
        rng = random.Random(run.seed)
        return rng.sample(pool, min(self.story["rewards"]["trophies"], len(pool)))

    # ---------- торговец ----------

    def shop_stock(self):
        """Торговец в лагере: обычные предметы, с главы 2 — и редкие; чего ещё нет в арсенале."""
        exp = self.current() or self.expeditions_list()[-1]
        rar = ("common",) if exp["chapter"] == self.story["chapters"][0]["id"] else ("common", "rare")
        items = [(i, it) for i, it in self.data.items.items() if it["rarity"] in rar and i not in self.arsenal]
        return sorted(items, key=lambda x: (x[1]["slot"], x[1].get("price", 50)))

    def buy(self, iid):
        price = self.data.items[iid].get("price", 50)
        if self.amber < price or iid in self.arsenal:
            return False
        self.amber -= price
        self.arsenal.append(iid)
        self.save()
        return True

    # ---------- хранение ----------

    def save(self):
        super().save()
        if not self.path:
            return
        with open(self.path, encoding="utf-8") as f:
            d = json.load(f)
        d["story"] = {"done": self.done, "joined": self.joined, "help_seen": self.help_seen}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)
