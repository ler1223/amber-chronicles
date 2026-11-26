"""Эльф-садовник: феи, растения, звери, прививки и составное оружие.

Механика героя `fae` (docs/descent_elf_fae.md). Феи — стаки 0–10 на герое: карты
масштабируются от текущего числа, порог открывает дополнительный эффект, избыток
сверх 10 даёт защиту. Растения и звери живут на поле, прививки — на картах в руке,
оружие собирается из частей в руке.

Battle держит `self.garden = FaeGarden(self)` только у эльфа. Садовник сам не
рисует интерфейс: он даёт события хода/карт, а `deck/ui.py` показывает счётчик фей.
"""
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
        self.weapons_done = set()
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
            self.b.draw(owl.draw_n)
        deer = self.beasts.get("deer")
        if deer is not None and deer.alive:
            self.step_bonus = deer.step_n
            if deer.step_n >= 2:
                self.b.draw(1)

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
                yield from b.strike(wolf, target, wolf.dmg, kind="melee")
                if wolf.double and target.alive:
                    yield from b.strike(wolf, target, wolf.dmg, kind="melee")
        for att in self.attachments.values():
            att["growth"] += 1
            if att["id"] == "moon_moss":
                self.gain(1)
        for ring in list(self.rings):
            ring["turns"] -= 1
            if ring["turns"] <= 0:
                self.rings.remove(ring)

    # ---------- карты ----------

    def attach(self, card, host, sid):
        if host is None or self.attachments.get(host.uid) or getattr(host, "attached_id", None):
            return False
        self.attachments[host.uid] = {"card": card, "id": sid, "growth": 0}
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
        card.attached_id = None
        b, hero, fae = self.b, self.b.hero, self.fae()
        sid = att["id"]
        target = tgt if hasattr(tgt, "cell") and tgt is not hero else self.nearest_foe(hero.cell)
        if sid == "symbiosis":
            self.gain(1 + fae // 4)
            b.draw(1)
        elif sid == "ivy_graft":
            self.gain(2)
            b.gain_shield(hero, 4 + fae)
            if fae >= 6:
                b.draw(1)
        elif sid == "thorn_graft":
            if target is not None:
                b.hurt(target, 6 + fae, hero, "spell")
                target.ds["root"] = max(target.ds["root"], 1)
                if fae >= 6:
                    yield from b.apply(hero, [{"op": "aoe_target", "r": 1, "do": [{"op": "root", "n": 1}]}],
                                       target, {"center": target.cell})
        elif sid == "moon_moss":
            b.draw(2 if fae >= 6 else 1)
        elif sid == "parasite_flower":
            if target is not None:
                b.hurt(target, 4 + fae, hero, "spell")
                if fae >= 6:
                    target.ds["root"] = max(target.ds["root"], 1)
            heal = 8 if fae >= 6 else 4
            hero.hp = min(hero.max_hp, hero.hp + heal)
            b.c.emit("heal", unit=hero, amount=heal)
        b.say(f"Прививка: {att['card'].name}", (180, 240, 180))

    # ---------- растения ----------

    def plant(self, op, center):
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
        initial = self.fae() // max(1, op.get("grow_fae", 4)) if op.get("grow_fae") else 0
        for cell in cells[:n]:
            u = self.spawn_plant(sid, cell, initial)
            if sid == "world_tree" and self.fae() >= 8:
                u.growth = spec["grow"]
                yield from self.mature(u)

    def spawn_plant(self, sid, cell, growth=0):
        b = self.b
        spec = PLANTS[sid]
        proto = {"name": spec["name"], "label": spec["name"][:2], "color": spec["color"], "role": "object",
                 "hp": 2, "move_time": 1.0, "attack": {"damage": 0, "range": 0, "cooldown": 99.0},
                 "static": True,
                 "object": {"id": sid, "name": spec["name"], "hp": 2, "color": spec["color"], "art": spec["sprite"]}}
        u = b.c._spawn(PLAYER, spec["sprite"], proto, cell)
        b._setup(u, {"name": spec["name"], "hp": 2})
        u.plant_id = sid
        u.growth = growth
        u.max_hp = u.hp = 2
        u.obj = proto["object"]
        self.plants.append(u)
        b.fx("portal", cell=cell)
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
        b.say(f"{PLANTS[sid]['name']} созрело", (180, 245, 180))
        if sid == "thorn_seed":
            target = self.nearest_foe(cell)
            if target is not None:
                b.hurt(target, 6, b.hero, "spell")
                target.ds["root"] = max(target.ds["root"], 1)
            if fae >= 6:
                for f in [f for f in b.foes() if cheb(f.cell, cell) <= 1]:
                    f.ds["root"] = max(f.ds["root"], 1)
        elif sid == "moon_flower":
            b.gain_shield(b.hero, 6 + fae)
            b.hero.hp = min(b.hero.max_hp, b.hero.hp + 4)
            b.c.emit("heal", unit=b.hero, amount=4)
            if fae >= 6:
                self.gain(2)
        elif sid == "world_tree":
            b.energy += 1
            b.draw(2)
        elif sid == "thorn_garden":
            if fae >= 6:
                for f in [f for f in b.foes() if cheb(f.cell, cell) <= 1]:
                    f.ds["root"] = max(f.ds["root"], 1)
        elif sid == "hunting_vine":
            target = self.nearest_foe(cell)
            if target is not None:
                b.hurt(target, 10 + fae, b.hero, "spell")
                target.ds["root"] = max(target.ds["root"], 1)
                if fae >= 6:
                    for f in [f for f in b.foes() if cheb(f.cell, target.cell) <= 1]:
                        f.ds["root"] = max(f.ds["root"], 1)
        elif sid == "living_hedge":
            self.spawn_wall(cell, 6 + fae + (6 if fae >= 6 else 0), 3)
        elif sid == "glowing_moss":
            self.gain(3 + fae // 4)
            if fae >= 6:
                b.draw(1)
        elif sid == "mushroom_web":
            for f in [f for f in b.foes() if cheb(f.cell, cell) <= 2]:
                f.ds["weak"] += 1 + fae // 4
                if fae >= 6:
                    f.ds["vulnerable"] += 1
                b._icons(f)
        elif sid == "crusher_root":
            target = self.nearest_foe(cell)
            if target is not None:
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
            b.gain_shield(b.hero, max(6 + fae, 10 if fae >= 6 else 0))
        yield from self.plant_matured()

    def plant_destroyed(self, u):
        """Семя убили до созревания: срабатывает только «Дар рощи»."""
        if u.plant_id == "grove_gift":
            self.b.gain_shield(self.b.hero, max(6 + self.fae(), 10 if self.fae() >= 6 else 0))
            self.b.say("Дар рощи: семя погибло, но дала защиту", (180, 235, 180))
        if u in self.plants:
            self.plants.remove(u)

    def plant_matured(self):
        for c in list(self.b.hand):
            if "unactivatable" in M.card_rules(c.d) and M.card_reactions(c.d, "plant_matured"):
                yield from self.b.card_event("plant_matured", c)
                if self.fae() >= 6:
                    yield from self.b.card_event("plant_matured", c)

    def in_ring(self, cell):
        return any(cell in ring["cells"] for ring in self.rings)

    def add_ring(self, center, turns=3):
        cells = set(self.b.c.grid.in_radius(center, 1))
        self.rings.append({"cell": center, "cells": cells, "turns": turns})
        self.b.fx("portal", cell=center)
        self.b.say(f"Фейное кольцо на {turns} хода", (180, 240, 180))

    # ---------- звери ----------

    def summon_beast(self, kind):
        b = self.b
        spec = BEASTS[kind]
        fae = self.fae()
        stats = {}
        if kind == "wolf":
            stats = {"hp": 8, "dmg": 6 + fae, "double": fae >= 6}
        elif kind == "owl":
            draw = 1 + fae // 5
            stats = {"hp": 4, "draw_n": max(2, draw) if fae >= 6 else draw}
        elif kind == "snake":
            stats = {"hp": 8 + fae, "poison": 2, "root": 1, "root_all": fae >= 6}
        elif kind == "deer":
            stats = {"hp": 6 + fae, "step_n": 2 if fae >= 6 else 1}
        old = self.beasts.get(kind)
        if old is not None and old.alive:
            old.max_hp = old.hp = stats["hp"]
            for key, value in stats.items():
                setattr(old, key, value)
            old.summon_fae = fae
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
        b.fx("portal", cell=cell)
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
                            "art": "bone_wall"}}
        u = b.c._spawn(PLAYER, "bone_wall", proto, cell)
        b._setup(u, {"name": "Живая изгородь", "hp": hp})
        u.max_hp = u.hp = hp
        u.obj = proto["object"]
        u.wall_turns = turns
        u.blocks_los = self.fae() >= 6
        self.walls.append(u)
        b.say(f"Выросла живая изгородь ({hp} HP, {turns} хода)", (150, 220, 150))
        return u

    def wall_died(self, u):
        if u in self.walls:
            self.walls.remove(u)

    # ---------- составное оружие ----------

    def make_parts(self, blueprint):
        parts = BLUEPRINTS.get(blueprint, (None, ()))[1]
        for pid in parts:
            self.b.add_tokens(pid, 1, force=True)

    def check_assembly(self):
        b = self.b
        for blueprint, (weapon_cid, parts) in BLUEPRINTS.items():
            if blueprint in self.weapons_done:
                continue
            chosen = []
            for pid in parts:
                card = next((c for c in b.hand if c.cid == pid), None)
                if card is None:
                    break
                chosen.append(card)
            else:
                for card in chosen:
                    b.hand.remove(card)
                weapon = M.Card(weapon_cid, b.run.defs)
                b.hand.append(weapon)
                self.weapons_done.add(blueprint)
                b.say(f"Собрано оружие: {weapon.name}", (220, 240, 180))
                b.fx("created", unit=b.hero, uid=weapon.uid)
                b.queue_card_event("entered_hand", weapon)

    # ---------- помощники ----------

    def free_near(self, cell):
        spots = [p for p in self.b.c.grid.in_radius(cell, 1) if self.b.free(p)]
        return min(spots, key=lambda p: cheb(p, cell)) if spots else None

    def nearest_foe(self, cell):
        foes = self.b.foes()
        return min(foes, key=lambda f: (cheb(f.cell, cell), f.hp)) if foes else None
