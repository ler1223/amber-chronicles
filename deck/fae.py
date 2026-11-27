"""Эльф-садовник: феи, растения, звери, прививки и составное оружие.

Механика героя `fae` (docs/descent_elf_fae.md). Феи — стаки 0–10 на герое: карты
масштабируются от текущего числа, порог открывает дополнительный эффект, избыток
сверх 10 даёт защиту. Растения и звери живут на поле, прививки — на картах в руке,
оружие собирается из частей в руке.

Battle держит `self.garden = FaeGarden(self)` только у эльфа. Садовник сам не
рисует интерфейс: он даёт события хода/карт, а `deck/ui.py` показывает счётчик фей.
"""
import copy
from itertools import combinations

from sim.combat import PLAYER
from sim.grid import cheb

from . import model as M

FAE_MAX = 10


# садовые растения: сколько роста нужно, спрайт, цвет
PLANTS = {
    "thorn_seed": {"name": "Семя терновника", "grow": 3, "sprite": "glow_tree", "color": (150, 210, 132)},
    "moon_flower": {"name": "Лунный цветок", "grow": 3, "sprite": "glow_tree", "color": (220, 235, 255)},
    "world_tree": {"name": "Мировое древо", "grow": 5, "sprite": "spirit_tree", "color": (140, 220, 150)},
    "thorn_garden": {"name": "Терновый сад", "grow": 3, "sprite": "glow_tree", "color": (150, 200, 120)},
    "hunting_vine": {"name": "Хищная лоза", "grow": 2, "sprite": "glow_tree", "color": (120, 210, 130)},
    "living_hedge": {"name": "Живая изгородь", "grow": 2, "sprite": "spirit_tree", "color": (130, 200, 120)},
    "glowing_moss": {"name": "Светящийся мох", "grow": 2, "sprite": "glow_tree", "color": (180, 245, 180)},
    "mushroom_web": {"name": "Грибная сеть", "grow": 3, "sprite": "glow_tree", "color": (200, 170, 230)},
    "crusher_root": {"name": "Корень-дробитель", "grow": 2, "sprite": "spirit_tree", "color": (170, 130, 90)},
    "grove_gift": {"name": "Дар рощи", "grow": 2, "sprite": "glow_tree", "color": (190, 235, 170)},
}

# звери: базовые HP и спрайт; числа с феями считаются при призыве
BEASTS = {
    "wolf": {"name": "Лунный волк", "hp": 8, "sprite": "druid_wolf", "color": (170, 190, 230)},
    "owl": {"name": "Сова-вестник", "hp": 4, "sprite": "shade_fae", "color": (220, 220, 250)},
    "snake": {"name": "Змей-хранитель", "hp": 8, "sprite": "bog_croc", "color": (140, 220, 160)},
    "deer": {"name": "Олень-проводник", "hp": 6, "sprite": "druid_bear", "color": (220, 200, 150)},
}

# чертёж → (собранное оружие, части)
BLUEPRINTS = {
    "e_moon_scythe": ("e_weapon_scythe", ("e_part_scythe_arc", "e_part_scythe_blade", "e_part_scythe_seal")),
    "e_light_shadow": ("e_weapon_balance", ("e_part_light_light", "e_part_light_shadow", "e_part_light_seal")),
    "e_dawn_blade": ("e_weapon_dawn", ("e_part_dawn_hilt", "e_part_dawn_guard", "e_part_dawn_blade")),
    "e_storm_spear": ("e_weapon_storm", ("e_part_storm_shaft", "e_part_storm_tip", "e_part_storm_core")),
}


class FaeGarden:
    def __init__(self, b):
        self.b = b
        self.plants = []
        self.beasts = {}
        self.attachments = {}          # uid карты-хозяина → {"card", "id", "growth"}
        self.rings = []                # {"cell", "cells", "turns"}
        self.walls = []
        self.pending_assemblies = []   # [(blueprint, parts, weapon_cid)] — собрать после текущего эффекта
        self.blueprint_recipes = {}    # blueprint cid → {"parts", "assemble_min", "weapon_mods"}
        self.crown_used = False
        self.step_bonus = 0

    # ---------- феи ----------

    def fae(self):
        return self.b.hero.ds.get("fae", 0)

    def gain(self, n):
        return self.b.gain_fae(n)

    def crown_active(self):
        return any(c.cid == "e_fae_crown" for c in self.b.powers)

    def forest_active(self):
        return any(c.cid == "e_forest_pact" for c in self.b.powers)

    # ---------- начало хода ----------

    def turn_start(self):
        self.step_bonus = 0
        hero = self.b.hero
        for ring in self.rings:
            if hero.cell in ring["cells"]:
                self.gain(2)
                self.b.say("Фейное кольцо: +2 феи", (170, 240, 180))
                break
        for ring in self.rings:
            if ring.get("trap"):
                for f in [x for x in self.b.foes() if x.cell in ring["cells"]]:
                    f.ds["root"] = max(f.ds["root"], 1)
        if self.crown_active():
            extra = max(0, self.fae() - 5)
            if extra:
                self.b.gain_shield(hero, extra)
        if self.forest_active():
            heal = self.fae() // 3
            if heal:
                hero.hp = min(hero.max_hp, hero.hp + heal)
                self.b.c.emit("heal", unit=hero, amount=heal)
            if self.fae() >= 6:
                self.b.gain_shield(hero, 5)
                self.b.say("Лесной завет: первая фея даёт 5 защиты", (180, 240, 190))
        owl = self.beasts.get("owl")
        if owl is not None and owl.alive:
            self.b.fx("elf_effect", unit=owl, target=hero, look="twins")
            self.b.draw(owl.draw_n)
            if getattr(owl, "block_n", 0):
                self.b.gain_shield(hero, owl.block_n)
            if getattr(owl, "energy_n", 0):
                self.b.energy += owl.energy_n
        deer = self.beasts.get("deer")
        if deer is not None and deer.alive:
            self.b.fx("elf_effect", unit=deer, target=hero, look="step")
            self.step_bonus = deer.step_n

    def force_lead(self):
        if self.fae() >= 6:
            for c in self.b.hand:
                if "lead" in M.card_rules(c.d):
                    self.b.lead_discounts.add(c.uid)

    def on_spend(self, spent, tgt=None, before=None):
        """Корона фей: первая трата 3+ фей даёт карту, с порогом 6 — ещё уязвимость."""
        if not self.crown_active() or self.crown_used or spent < 3:
            return
        self.crown_used = True
        self.b.draw(1)
        self.b.say("Корона фей: первая крупная трата — карта", (220, 240, 180))
        if (before if before is not None else self.fae()) >= 6 and tgt is not None and hasattr(tgt, "ds"):
            tgt.ds["vulnerable"] += 1
            self.b._icons(tgt)

    # ---------- конец хода ----------

    def end_turn(self):
        b = self.b
        for u in list(self.plants):
            if not u.alive:
                continue
            rate = 1
            if self.fae() >= 6 and self.in_ring(u.cell):
                rate += 1
            u.growth += rate
            spec = PLANTS[u.plant_id]
            if u.growth >= spec["grow"]:
                yield from self.mature(u)
        if self.fae() >= 6:                               # кольцо растит и зверей в нём
            for beast in self.beasts.values():
                if beast.alive and self.in_ring(beast.cell):
                    beast.max_hp += 1
                    beast.hp += 1
                    if hasattr(beast, "dmg"):
                        beast.dmg += 1
        for wall in list(self.walls):
            wall.wall_turns -= 1
            if wall.wall_turns <= 0:
                wall.alive = False
                self.walls.remove(wall)
        wolf = self.beasts.get("wolf")
        if wolf is not None and wolf.alive:
            foes = b.foes()
            if foes:
                target = min(foes, key=lambda f: (cheb(f.cell, wolf.cell), f.hp))
                b.say(f"Лунный волк бьёт {target.name}", (190, 210, 255))
                yield from b.elf_cast(wolf, "e_claw", wolf.name, target=target)
                yield from b.strike(wolf, target, wolf.dmg, kind="melee", anim=False)
                if wolf.double and target.alive:
                    yield from b.elf_cast(wolf, "e_claw", wolf.name, target=target)
                    yield from b.strike(wolf, target, wolf.dmg, kind="melee", anim=False)
        for att in self.attachments.values():
            att["growth"] += 1
            if att["id"] == "moon_moss":
                self.gain(1 + att["growth"] // 2)
        for ring in list(self.rings):
            ring["turns"] -= 1
            if ring["turns"] <= 0:
                self.rings.remove(ring)

    # ---------- карты ----------

    def attach(self, card, host, sid, bonus=0, extra=None):
        if host is None or self.attachments.get(host.uid) or getattr(host, "attached_id", None):
            return False
        self.attachments[host.uid] = {"card": card, "id": sid, "growth": bonus, "bonus": dict(extra or {})}
        host.attached_id = sid
        self.b.say(f"«{card.name}» привита к «{host.name}»", (180, 240, 180))
        return True

    def attached(self, card):
        return card.uid in self.attachments

    def drop_attachment(self, card):
        att = self.attachments.pop(card.uid, None)
        if att is not None:
            card.attached_id = None
        return att

    def after_card(self, card, tgt):
        """Срабатывание прививки после основной карты-хозяина."""
        att = self.attachments.pop(card.uid, None)
        if att is None:
            return
        self.b.attach_reveal = (att["card"], card.name)
        card.attached_id = None
        b, hero, fae = self.b, self.b.hero, self.fae()
        sid = att["id"]
        growth = att.get("growth", 0)
        target = tgt if hasattr(tgt, "cell") and tgt is not hero else self.nearest_foe(hero.cell)
        if sid == "symbiosis":
            b.fx("elf_effect", unit=hero, look="leaves")
            self.gain(1 + fae // 4 + growth)
            b.draw(1)
        elif sid == "ivy_graft":
            b.fx("elf_effect", unit=hero, look="bark")
            self.gain(2)
            b.gain_shield(hero, 4 + fae + growth)
        elif sid == "thorn_graft":
            if target is not None:
                yield from b.elf_cast(hero, "_elf_thorn_seed", att["card"].name, target=target)
                b.hurt(target, 6 + fae + growth, hero, "spell")
                target.ds["root"] = max(target.ds["root"], 1)
                if fae >= 6:
                    yield from b.apply(hero, [{"op": "aoe_target", "r": 1, "do": [{"op": "root", "n": 1}]}],
                                       target, {"center": target.cell})
        elif sid == "moon_moss":
            b.fx("elf_effect", unit=hero, look="dew")
            b.draw(1)
        elif sid == "parasite_flower":
            if target is not None:
                yield from b.elf_cast(hero, "e_wither", att["card"].name, target=target)
                b.hurt(target, 4 + fae + growth, hero, "spell")
                if fae >= 6:
                    target.ds["root"] = max(target.ds["root"], 1)
            heal = 8 if fae >= 6 else 4
            hero.hp = min(hero.max_hp, hero.hp + heal + growth)
            b.c.emit("heal", unit=hero, amount=heal + growth)
        bonus = att.get("bonus") or {}
        if bonus:
            ops = []
            for key, opname in (("fae", "fae"), ("block", "block"), ("heal", "heal"), ("draw", "draw"),
                                ("energy", "energy"), ("damage", "damage"), ("root", "root"),
                                ("poison", "poison"), ("weak", "weak"), ("vulnerable", "vulnerable"),
                                ("counter", "counter"), ("thorns", "thorns")):
                if bonus.get(key):
                    ops.append({"op": opname, "n": int(bonus[key])})
            if ops:
                yield from b.apply(hero, ops, target, {"card": att["card"]})
            if bonus.get("root_all"):
                center = target.cell if target is not None and hasattr(target, "cell") else hero.cell
                for f in [x for x in b.foes() if cheb(x.cell, center) <= 1]:
                    f.ds["root"] = max(f.ds["root"], int(bonus["root_all"]))
            if bonus.get("return"):
                b.receive_card(att["card"])
        b.say(f"Прививка: {att['card'].name}", (180, 240, 180))

    # ---------- растения ----------

    def plant(self, op, center, extra_growth=0, *, empowered=False):
        b = self.b
        sid = op["plant"]
        spec = PLANTS[sid]
        n = op.get("n", 1)
        cells = []
        if center is not None and b.free(center):
            cells.append(center)
        for p in sorted(b.c.grid.in_radius(center or b.hero.cell, 3), key=lambda p: cheb(p, center or b.hero.cell)):
            if len(cells) >= n:
                break
            if p not in cells and b.free(p):
                cells.append(p)
        initial = (self.fae() // max(1, op.get("grow_fae", 4)) if op.get("grow_fae") else 0) + extra_growth
        for cell in cells[:n]:
            u = self.spawn_plant(sid, cell, initial, op.get("bonus"), empowered=empowered)
            if sid == "world_tree" and self.fae() >= 8:
                u.growth = spec["grow"]
                yield from self.mature(u)

    def spawn_plant(self, sid, cell, growth=0, bonus=None, *, empowered=False):
        b = self.b
        spec = PLANTS[sid]
        proto = {"name": spec["name"], "label": spec["name"][:2], "color": spec["color"], "role": "object",
                 "hp": 2, "move_time": 1.0, "attack": {"damage": 0, "range": 0, "cooldown": 99.0},
                 "static": True,
                 "object": {"id": sid, "name": spec["name"], "hp": 2, "color": spec["color"], "art": spec["sprite"],
                            "growth_art": (f"elf_plants/{sid}", spec["grow"])}}
        u = b.c._spawn(PLAYER, spec["sprite"], proto, cell)
        b._setup(u, {"name": spec["name"], "hp": 2})
        u.plant_id = sid
        u.plant_bonus = dict(bonus or {})
        u.growth = growth
        u.max_hp = u.hp = 2
        u.obj = proto["object"]
        self.plants.append(u)
        b.fx("elf_effect", unit=u, look="plant", empowered=empowered)
        b.say(f"Посажено: {spec['name']} (рост {growth}/{spec['grow']})", (170, 235, 170))
        return u

    def mature(self, u):
        b = self.b
        sid = u.plant_id
        if u in self.plants:
            self.plants.remove(u)
        u.alive = False
        cell = u.cell
        fae = self.fae()
        if sid != "living_hedge":
            b.fx("plant_mature", unit=u)
        b.say(f"{PLANTS[sid]['name']} созрело", (180, 245, 180))
        if sid == "thorn_seed":
            target = self.nearest_foe(cell)
            if target is not None:
                yield from b.elf_cast(u, "_elf_thorn_seed", u.name, target=target, empowered=fae >= 6)
                b.hurt(target, 6, b.hero, "spell")
                target.ds["root"] = max(target.ds["root"], 1)
            if fae >= 6:
                for f in [f for f in b.foes() if cheb(f.cell, cell) <= 1]:
                    f.ds["root"] = max(f.ds["root"], 1)
        elif sid == "moon_flower":
            yield from b.elf_cast(u, "rejuvenate", u.name, target=b.hero, empowered=fae >= 6)
            b.gain_shield(b.hero, 6 + fae)
            b.hero.hp = min(b.hero.max_hp, b.hero.hp + 4)
            b.c.emit("heal", unit=b.hero, amount=4)
            if fae >= 6:
                self.gain(2)
        elif sid == "world_tree":
            yield from b.elf_cast(u, "spirit_tree", u.name, empowered=fae >= 8)
            b.energy += 1
            b.draw(2)
        elif sid == "thorn_garden":
            if fae >= 6:
                yield from b.elf_cast(u, "_elf_thorn_attack", u.name, center=cell, radius=1, empowered=True)
                for f in [f for f in b.foes() if cheb(f.cell, cell) <= 1]:
                    f.ds["root"] = max(f.ds["root"], 1)
        elif sid == "hunting_vine":
            target = self.nearest_foe(cell)
            if target is not None:
                yield from b.elf_cast(u, "_elf_thorn_attack", u.name, target=target, empowered=fae >= 6)
                b.hurt(target, 10 + fae, b.hero, "spell")
                target.ds["root"] = max(target.ds["root"], 1)
                if fae >= 6:
                    for f in [f for f in b.foes() if cheb(f.cell, target.cell) <= 1]:
                        f.ds["root"] = max(f.ds["root"], 1)
        elif sid == "living_hedge":
            self.spawn_wall(cell, 6 + fae + (6 if fae >= 6 else 0) + getattr(u, "plant_bonus", {}).get("wall_hp", 0), 3)
        elif sid == "glowing_moss":
            b.fx("elf_effect", unit=u, target=b.hero, look="call")
            self.gain(3 + fae // 4)
        elif sid == "mushroom_web":
            yield from b.elf_cast(u, "e_plague", u.name, center=cell, radius=2, empowered=fae >= 6)
            for f in [f for f in b.foes() if cheb(f.cell, cell) <= 2]:
                f.ds["weak"] += 1 + fae // 4
                if fae >= 6:
                    f.ds["vulnerable"] += 1
                b._icons(f)
        elif sid == "crusher_root":
            target = self.nearest_foe(cell)
            if target is not None:
                yield from b.elf_cast(u, "earth_power", u.name, target=target, empowered=fae >= 6 and target.shield > 0)
                dmg = 8 + fae
                if target.shield > 0 and fae < 6:
                    dmg = dmg * 6 // 5
                if fae >= 6 and target.shield > 0:
                    saved = target.shield
                    target.shield = 0
                    b.hurt(target, dmg, b.hero, "spell")
                    target.shield = saved
                else:
                    b.hurt(target, dmg, b.hero, "spell")
        elif sid == "grove_gift":
            b.fx("elf_effect", unit=u, target=b.hero, look="bark")
            b.gain_shield(b.hero, max(6 + fae, 10 if fae >= 6 else 0))
        self.apply_plant_bonus(u, cell)
        yield from self.plant_matured()

    def apply_plant_bonus(self, u, cell):
        """Дополнительные эффекты созревания/гибели из прозрений."""
        bonus = getattr(u, "plant_bonus", {}) or {}
        if not bonus:
            return
        b, hero = self.b, self.b.hero
        if bonus.get("block"):
            b.gain_shield(hero, int(bonus["block"]))
        if bonus.get("heal"):
            n = int(bonus["heal"])
            hero.hp = min(hero.max_hp, hero.hp + n)
            b.c.emit("heal", unit=hero, amount=n)
        if bonus.get("fae"):
            self.gain(int(bonus["fae"]))
        if bonus.get("energy"):
            b.energy += int(bonus["energy"])
        if bonus.get("draw"):
            b.draw(int(bonus["draw"]))
        if bonus.get("grow_all"):
            for plant in self.plants:
                plant.growth += int(bonus["grow_all"])
        target = self.nearest_foe(cell)
        if target is not None:
            if bonus.get("damage"):
                b.vfx(u, "e_entangle", u.name, target=target, effect_only=True)
                b.hurt(target, int(bonus["damage"]), hero, "spell")
            if bonus.get("root"):
                target.ds["root"] = max(target.ds["root"], int(bonus["root"]))
            if bonus.get("poison"):
                target.ds["poison"] += int(bonus["poison"])
                b._icons(target)
        if bonus.get("root_all"):
            for f in [x for x in b.foes() if cheb(x.cell, cell) <= 1]:
                f.ds["root"] = max(f.ds["root"], int(bonus["root_all"]))
        if bonus.get("all_damage"):
            b.vfx(u, "e_entangle", u.name, center=cell, radius=1, effect_only=True)
            for f in [x for x in b.foes() if cheb(x.cell, cell) <= 1]:
                b.hurt(f, int(bonus["all_damage"]), hero, "spell")

    def plant_destroyed(self, u):
        """Семя убили до созревания: срабатывает «Дар рощи» и бонус прозрения."""
        if u.plant_id == "grove_gift":
            self.b.gain_shield(self.b.hero, max(6 + self.fae(), 10 if self.fae() >= 6 else 0))
            self.b.say("Дар рощи: семя погибло, но дала защиту", (180, 235, 180))
        self.apply_plant_bonus(u, u.cell)
        if u in self.plants:
            self.plants.remove(u)

    def plant_matured(self):
        for c in list(self.b.hand):
            if "unactivatable" in M.card_rules(c.d) and M.card_reactions(c.d, "plant_matured"):
                self.b.fx("elf_effect", unit=self.b.hero, look="firefly")
                yield from self.b.card_event("plant_matured", c)
                if self.fae() >= 6:
                    yield from self.b.card_event("plant_matured", c)

    def in_ring(self, cell):
        return any(cell in ring["cells"] for ring in self.rings)

    def add_ring(self, center, turns=3, radius=1, trap=False):
        cells = set(self.b.c.grid.in_radius(center, radius))
        self.rings.append({"cell": center, "cells": cells, "turns": turns, "trap": trap})
        self.b.fx("portal", cell=center)
        self.b.say(f"Фейное кольцо на {turns} хода", (180, 240, 180))

    # ---------- звери ----------

    def summon_beast(self, kind, bonus=0, extra=None, *, empowered=False):
        b = self.b
        spec = BEASTS[kind]
        fae = self.fae()
        extra = extra or {}
        stats = {}
        if kind == "wolf":
            stats = {"hp": 8 + bonus, "dmg": 6 + fae + bonus, "double": fae >= 6}
        elif kind == "owl":
            stats = {"hp": 4 + bonus, "draw_n": 1, "block_n": 0, "energy_n": 0}
        elif kind == "snake":
            stats = {"hp": 8 + fae + bonus, "poison": 2, "root": 1, "root_all": fae >= 6}
        elif kind == "deer":
            stats = {"hp": 6 + fae + bonus, "step_n": 2 if fae >= 6 else 1}
        stats["hp"] += int(extra.get("hp", 0))
        if "dmg" in stats:
            stats["dmg"] += int(extra.get("dmg", 0))
        if "draw_n" in stats:
            stats["draw_n"] += int(extra.get("draw", 0))
        if "block_n" in stats:
            stats["block_n"] += int(extra.get("block", 0))
        if "energy_n" in stats:
            stats["energy_n"] += int(extra.get("energy", 0))
        if "step_n" in stats:
            stats["step_n"] += int(extra.get("step", 0))
        if "poison" in stats:
            stats["poison"] += int(extra.get("poison", 0))
        if extra.get("root_all"):
            stats["root_all"] = True
        if extra.get("fae"):
            self.gain(int(extra["fae"]))
        if extra.get("block"):
            b.gain_shield(b.hero, int(extra["block"]))
        if extra.get("energy"):
            b.energy += int(extra["energy"])
        old = self.beasts.get(kind)
        if old is not None and old.alive:
            old.max_hp = old.hp = stats["hp"]
            for key, value in stats.items():
                setattr(old, key, value)
            old.summon_fae = fae
            b.fx("elf_effect", unit=old, look="summon", empowered=empowered)
            b.say(f"{spec['name']} обновлён", (180, 240, 180))
            return old
        cell = self.free_near(b.hero.cell)
        if cell is None:
            return None
        proto = {"name": spec["name"], "label": spec["name"][:2], "color": spec["color"], "role": "summon",
                 "hp": stats["hp"], "move_time": 0.5, "attack": {"damage": 0, "range": 1, "cooldown": 1.0}}
        u = b.c._spawn(PLAYER, spec["sprite"], proto, cell)
        b._setup(u, {"name": spec["name"], "hp": stats["hp"]})
        u.summon = True
        u.beast = kind
        u.summon_fae = fae
        for key, value in stats.items():
            setattr(u, key, value)
        self.beasts[kind] = u
        b.fx("elf_effect", unit=u, look="summon", empowered=empowered)
        b.c.emit("summon", unit=u, owner=b.hero)
        b.say(f"Призван {spec['name']} ({stats['hp']} HP)", (180, 240, 180))
        return u

    def is_beast(self, u):
        return getattr(u, "beast", None) is not None

    def beast_died(self, u):
        if self.beasts.get(getattr(u, "beast", None)) is u:
            self.beasts.pop(u.beast, None)

    def blocker_for(self, u):
        """Ближний враг, которому мешает растение, стена или зверь под рукой."""
        if cheb(u.cell, self.b.hero.cell) <= 1:
            return None
        near = [v for v in [*self.plants, *self.walls, *self.beasts.values()]
                if v.alive and cheb(v.cell, u.cell) <= 1]
        return min(near, key=lambda v: (v.hp, not getattr(v, "plant_id", False))) if near else None

    def snake_retaliate(self, src):
        snake = self.beasts.get("snake")
        if snake is None or not snake.alive or src is None or not getattr(src, "alive", False):
            return
        self.b.fx("elf_effect", unit=snake, target=src, look="venom")
        self.b.add_poison(src, snake.poison)
        src.ds["root"] = max(src.ds["root"], snake.root)
        self.b.say(f"Змей-хранитель: {src.name} отравлен и скован", (150, 230, 160))
        if snake.root_all:
            for f in [f for f in self.b.foes() if cheb(f.cell, self.b.hero.cell) <= 1]:
                f.ds["root"] = max(f.ds["root"], 1)

    # ---------- стены ----------

    def spawn_wall(self, cell, hp, turns):
        b = self.b
        proto = {"name": "Живая изгородь", "label": "Изг", "color": (110, 180, 110), "role": "object",
                 "hp": hp, "move_time": 1.0, "attack": {"damage": 0, "range": 0, "cooldown": 99.0},
                 "static": True,
                 "object": {"id": "hedge", "name": "Живая изгородь", "hp": hp, "color": (110, 180, 110),
                            "art": "bone_wall", "sprite": f"elf_plants/living_hedge_{PLANTS['living_hedge']['grow']}"}}
        u = b.c._spawn(PLAYER, "bone_wall", proto, cell)
        b._setup(u, {"name": "Живая изгородь", "hp": hp})
        u.max_hp = u.hp = hp
        u.obj = proto["object"]
        u.wall_turns = turns
        u.blocks_los = self.fae() >= 6
        self.walls.append(u)
        b.fx("elf_effect", unit=u, look="leaves")
        b.say(f"Выросла живая изгородь ({hp} HP, {turns} хода)", (150, 220, 150))
        return u

    def wall_died(self, u):
        if u in self.walls:
            self.walls.remove(u)

    # ---------- составное оружие ----------

    def make_parts(self, blueprint):
        """Рассыпать части чертежа по колоде добора и сбросу."""
        if isinstance(blueprint, M.Card):
            card = blueprint
            blueprint = card.cid
            main = card.d.get("main", {})
        else:
            main = {}
        default = BLUEPRINTS.get(blueprint, (None, ()))[1]
        parts = list(main.get("parts") or default)
        self.blueprint_recipes[blueprint] = {
            "parts": parts,
            "assemble_min": int(main.get("assemble_min", len(parts))),
            "weapon_mods": dict(main.get("weapon_mods") or {}),
        }
        cards = [M.Card(pid, self.b.run.defs) for pid in parts]
        placed = self.b.scatter_parts(cards)
        if placed:
            self.b.fx("parts_fly", unit=self.b.hero,
                      parts=[card for card, _ in placed],
                      dests=[dest for _, dest in placed])

    def check_assembly(self):
        """Найти полные комплекты в руке и поставить их в очередь на сборку."""
        b = self.b
        used = {c.uid for _, parts, _ in self.pending_assemblies for c in parts}
        for blueprint, (weapon_cid, default_parts) in BLUEPRINTS.items():
            recipe = self.blueprint_recipes.get(blueprint) or {
                "parts": list(default_parts), "assemble_min": len(default_parts), "weapon_mods": {}
            }
            parts = recipe["parts"]
            need = max(1, min(recipe.get("assemble_min", len(parts)), len(parts)))
            for combo in combinations(parts, need):
                chosen = []
                local = set(used)
                for pid in combo:
                    card = next((c for c in b.hand if c.cid == pid and c.uid not in local), None)
                    if card is None:
                        break
                    chosen.append(card)
                    local.add(card.uid)
                else:
                    self.pending_assemblies.append((blueprint, chosen, weapon_cid))
                    used = local
                    break

    def make_weapon(self, weapon_cid, mods):
        if not mods:
            return M.Card(weapon_cid, self.b.run.defs)
        d = copy.deepcopy(self.b.run.defs[weapon_cid])
        main = d["main"]

        def walk(node):
            if isinstance(node, dict):
                yield node
                for value in node.values():
                    yield from walk(value)
            elif isinstance(node, list):
                for value in node:
                    yield from walk(value)

        for op in walk(main.get("do", [])):
            kind = op.get("op")
            if kind == "damage" and mods.get("damage"):
                op["n"] = op.get("n", 0) + int(mods["damage"])
            elif kind == "aoe_radius" and mods.get("radius"):
                op["r"] = max(int(op.get("r", 1)), int(mods["radius"]))
        extra = []
        for key, opname in (("vulnerable", "vulnerable"), ("root", "root"), ("poison", "poison"),
                            ("stun", "stun"), ("block", "block"), ("heal", "heal"),
                            ("energy", "energy"), ("draw", "draw"), ("fae", "fae")):
            if mods.get(key):
                extra.append({"op": opname, "n": int(mods[key])})
        if mods.get("execute_below"):
            extra.append({"op": "execute_below", "n": int(mods["execute_below"])})
        main.setdefault("do", []).extend(extra)
        return M.Card(weapon_cid, {weapon_cid: d})

    def flush_assemblies(self):
        """Собрать отложенные комплекты; каждая сборка ждёт свою анимацию."""
        b = self.b
        while self.pending_assemblies:
            blueprint, parts, weapon_cid = self.pending_assemblies.pop(0)
            if not all(card in b.hand for card in parts):
                continue
            recipe = self.blueprint_recipes.get(blueprint, {})
            for card in parts:
                b.hand.remove(card)
            weapon = self.make_weapon(weapon_cid, recipe.get("weapon_mods") or {})
            b.hand.append(weapon)
            b.queue_card_event("entered_hand", weapon)
            b.say(f"Собрано оружие: {weapon.name}", (220, 240, 180))
            b.fx("merge_weapon", unit=b.hero, parts=parts, weapon=weapon, dur=0.75)
            self.check_assembly()
            yield ("wait", 0.75)

    # ---------- помощники ----------

    def free_near(self, cell):
        spots = [p for p in self.b.c.grid.in_radius(cell, 1) if self.b.free(p)]
        return min(spots, key=lambda p: cheb(p, cell)) if spots else None

    def nearest_foe(self, cell):
        foes = self.b.foes()
        return min(foes, key=lambda f: (cheb(f.cell, cell), f.hp)) if foes else None
