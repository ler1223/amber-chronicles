"""Загрузка игровых данных из data/*.json и проверка ссылок между ними."""
import json
import os

SLOTS = ("weapon", "armor", "trinket")
RARITIES = ("common", "rare", "epic")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


class GameData:
    def __init__(self, data_dir=DATA_DIR):
        def load(name):
            with open(os.path.join(data_dir, name), encoding="utf-8") as f:
                return json.load(f)

        self.config = load("config.json")
        self.tags = load("tags.json")
        self.reactions = load("reactions.json")
        self.skills = load("skills.json")
        self.classes = load("classes.json")
        self.enemies = load("enemies.json")
        self.encounters = load("encounters.json")
        self.squad = load("squad.json")
        self.talents = load("talents.json")
        self.items = load("items.json")
        self.branches = load("branches.json")
        self.biomes = load("biomes.json")
        self.paths = load("paths.json")
        self.runes = load("runes.json")
        self.relics = load("relics.json")
        self.camp = load("camp.json")
        self.summons = load("summons.json")
        self.objects = load("objects.json")
        self.synergy = load("synergy.json")
        self.rules = load("rules.json")
        self.stats_mode = load("stats_mode.json")  # режим героев: атрибуты и уровни (sim/stats.py)           # правила взаимодействий по тегам (sim/rules.py)
        tr = load("traits.json")                  # особенности юнитов: плавает, тяжёлый, недвижим…
        self.traits_def = tr["defs"]
        for group in (self.classes, self.enemies, self.summons):
            for uid, proto in group.items():
                if uid in tr["units"]:
                    proto["traits"] = sorted(set(proto.get("traits", [])) | set(tr["units"][uid]))
        # глава, в которой герой открывается для найма (data/hero_unlocks.json)
        self.hero_unlocks = {cid: v for cid, v in load("hero_unlocks.json").items() if not cid.startswith("_")}
        self.hero_chapter = {h["cls"]: cid for cid, hs in self.hero_unlocks.items() for h in hs}
        # личные шкалы героев (бывшие PP): правило набора и медленная прибавка со временем
        for cid, g in load("gauges.json").items():
            if cid in self.classes:
                self.classes[cid]["gauge"] = g
                self.classes[cid]["pp_regen"] = g.get("trickle", 8.0)
        # длинные бои: волны, цели, объекты поля и фазы боссов (tools/content_battles.py)
        battles = load("battles.json")
        for enc in self.encounters:
            enc.update(battles.get(enc["id"], {}))
        # длинные бои: HP героев и врагов умножается на hp_mult, урон прежний
        for group in (self.classes, self.enemies):
            for proto in group.values():
                proto["hp"] = int(round(proto["hp"] * self.config.get("hp_mult", 1.0)))
        self._validate()

    def _validate(self):
        for group in (self.classes, self.enemies):
            for uid, proto in group.items():
                for sid in proto.get("skills", []):
                    if sid not in self.skills:
                        raise ValueError(f"{uid}: неизвестный навык {sid}")
                tag = proto["attack"].get("tag")
                if tag and tag not in self.tags:
                    raise ValueError(f"{uid}: неизвестный тег {tag}")
        for sid, sk in self.skills.items():
            for eff in sk["effects"]:
                if eff.get("tag") and eff["tag"] not in self.tags:
                    raise ValueError(f"{sid}: неизвестный тег {eff['tag']}")
                if eff["type"] == "summon" and eff["unit"] not in self.summons:
                    raise ValueError(f"{sid}: неизвестный призыв {eff['unit']}")
                if eff["type"] == "hazard" and eff["hazard"] not in self.config["hazards"]:
                    raise ValueError(f"{sid}: неизвестная клетка {eff['hazard']}")
        for sid, br in self.branches.items():
            for b in br.values():
                for t in b["tiers"]:
                    for m in t["mods"]:
                        for eff in m.get("effects", []) + ([m["add_effect"]] if "add_effect" in m else []):
                            if eff["type"] == "summon" and eff["unit"] not in self.summons:
                                raise ValueError(f"ветка {sid}: неизвестный призыв {eff['unit']}")
                            if eff.get("tag") and eff["tag"] not in self.tags:
                                raise ValueError(f"ветка {sid}: неизвестный тег {eff['tag']}")
        for group, name in ((self.talents, "талант"), (self.items, "предмет"), (self.relics, "реликвия")):
            for pid, p in group.items():
                if p.get("class", "any") not in ("any", *self.classes):
                    raise ValueError(f"{name} {pid}: неизвестный класс")
                for m in p.get("mods", []):
                    for key in ("skill", "new_skill"):
                        if m.get(key) not in (None, "*") and m[key] not in self.skills:
                            raise ValueError(f"{name} {pid}: неизвестный навык {m[key]}")
                    tags = [m.get("attack_tag"), m.get("resist"), *m.get("convert_tag", [])]
                    if any(t and t not in self.tags for t in tags):
                        raise ValueError(f"{name} {pid}: неизвестный тег")
        for cid, cls in self.classes.items():
            if len([p for p in self.paths.values() if p["class"] == cid]) < 2:
                raise ValueError(f"класс {cid}: нужно хотя бы 2 пути")
            for sid in cls["skills"]:
                if sid not in self.branches:
                    raise ValueError(f"класс {cid}: у навыка {sid} нет веток")
        for pid, path in self.paths.items():
            for sid in path["replace"].values():
                if sid not in self.branches:
                    raise ValueError(f"путь {pid}: у навыка {sid} нет веток")
        for sid, br in self.branches.items():
            if sid not in self.skills:
                raise ValueError(f"ветки: неизвестный навык {sid}")
            for b in ("A", "B"):
                if len(br[b]["tiers"]) != 2:
                    raise ValueError(f"ветки {sid}/{b}: нужно 2 ступени")
        for iid, it in self.items.items():
            if it.get("slot") not in SLOTS or it.get("rarity") not in RARITIES:
                raise ValueError(f"предмет {iid}: нужен slot из {SLOTS} и rarity из {RARITIES}")
        for pid, path in self.paths.items():
            cls = self.classes.get(path["class"])
            if not cls:
                raise ValueError(f"путь {pid}: неизвестный класс")
            for old, new in path["replace"].items():
                if old not in cls["skills"] or new not in self.skills:
                    raise ValueError(f"путь {pid}: замена {old} → {new} невозможна")
        groups = {g["id"] for g in self.camp["groups"]}
        for uid, up in self.camp["upgrades"].items():
            if up["group"] not in groups or not up["costs"]:
                raise ValueError(f"лагерь {uid}: неизвестная группа или нет цен")
        enc_ids = {e["id"] for e in self.encounters}
        enc_by_id = {e["id"]: e for e in self.encounters}
        for bid, biome in self.biomes.items():
            for level, types in biome.get("adds", {}).items():
                for t in types:
                    if t not in self.enemies:
                        raise ValueError(f"глава {bid}: неизвестный враг сложности {t}")
            for ev in biome.get("events", []):
                if ev["type"] not in ("eruption", "lightning", "avalanche", "wind", "sandstorm", "tide"):
                    raise ValueError(f"глава {bid}: неизвестное событие {ev['type']}")
            for r in biome["regions"]:
                if r["guard"] in enc_by_id and enc_by_id[r["guard"]].get("chapter", "swamp") != bid:
                    raise ValueError(f"глава {bid}/{r['id']}: страж из чужой главы")
            ids = {r["id"] for r in biome["regions"]}
            for r in biome["regions"]:
                if r["guard"] not in enc_ids:
                    raise ValueError(f"биом {bid}/{r['id']}: неизвестный страж {r['guard']}")
                if not set(r["links"]) <= ids:
                    raise ValueError(f"биом {bid}/{r['id']}: связь с неизвестным регионом")
                if len(r["tiers"]) < len(r["layers"]) - 2:
                    raise ValueError(f"биом {bid}/{r['id']}: тиров меньше, чем слоёв с боями")
        for bid in self.biomes:
            kinds = {e.get("kind") for e in self.encounters if e.get("chapter", "swamp") == bid}
            if not {"normal", "elite", "boss"} <= kinds:
                raise ValueError(f"глава {bid}: нужны бои всех типов: normal, elite, boss")
        for r in self.reactions["unit"]:
            for t in r["tags"]:
                if t not in self.tags:
                    raise ValueError(f"реакция {r['id']}: неизвестный тег {t}")
        for enc in self.encounters:
            self._validate_battle(enc)
        for enc in self.encounters:
            w = len(enc["map"][0])
            if any(len(row) != w for row in enc["map"]):
                raise ValueError(f"{enc['id']}: строки карты разной длины")
            if len(enc["player_spawn"]) < len(self.squad["units"]):
                raise ValueError(f"{enc['id']}: мало точек высадки")
            max_x = enc.get("deploy_max_x", self.config["deploy_max_x"])
            for x, y in enc["player_spawn"]:
                if x > max_x or not self.config["legend"][enc["map"][y][x]].get("passable", True):
                    raise ValueError(f"{enc['id']}: точка высадки {x},{y} вне зоны или непроходима")
            for e in enc["enemies"]:
                if e["pos"][0] <= max_x:
                    raise ValueError(f"{enc['id']}: враг {e['type']} в зоне высадки")
            for e in enc["enemies"]:
                if e["type"] not in self.enemies:
                    raise ValueError(f"{enc['id']}: неизвестный враг {e['type']}")
                x, y = e["pos"]
                if not self.config["legend"][enc["map"][y][x]].get("passable", True):
                    raise ValueError(f"{enc['id']}: враг {e['type']} на непроходимой клетке")

    def _validate_battle(self, enc):
        """Волны, цель боя, объекты и фазы: известные враги и объекты, клетки в пределах карты."""
        w, h = len(enc["map"][0]), len(enc["map"])
        spawns = [e for wave in enc.get("waves", []) for e in wave]
        spawns += [e for ph in enc.get("phases", []) for e in ph.get("spawn", [])]
        for e in spawns:
            if e["type"] not in self.enemies:
                raise ValueError(f"{enc['id']}: неизвестный враг волны {e['type']}")
        for o in enc.get("objects", []):
            if o["type"] not in self.objects:
                raise ValueError(f"{enc['id']}: неизвестный объект {o['type']}")
            for t in o.get("spawn", []):
                if t not in self.enemies:
                    raise ValueError(f"{enc['id']}: источник зовёт неизвестного врага {t}")
        cells = [e["pos"] for e in spawns] + [o["pos"] for o in enc.get("objects", [])]
        ob = enc.get("objective")
        if ob:
            if ob["type"] not in ("hold", "destroy", "defend"):
                raise ValueError(f"{enc['id']}: неизвестная цель боя {ob['type']}")
            if ob["type"] == "hold":
                cells += ob["cells"]
            if ob["type"] == "defend" and not any(self.objects[o["type"]].get("guard") for o in enc.get("objects", [])):
                raise ValueError(f"{enc['id']}: цель «Защитить» без охраняемого объекта")
            if ob["type"] == "destroy" and not any(self.objects[o["type"]].get("source")
                                                   for o in enc.get("objects", [])):
                raise ValueError(f"{enc['id']}: цель «Разрушить» без источников")
        for x, y in cells:
            if not (0 <= x < w and 0 <= y < h):
                raise ValueError(f"{enc['id']}: клетка {x},{y} вне карты")
