"""Предметы, реагирующие на клетки, намерения и установки."""

from sim.grid import cheb

from . import model as M
from .relic_choice import RelicChoice


def relic(name, icon, about, rarity="uncommon", hero=None):
    definition = {"name": name, "icon": icon, "about": about, "rarity": rarity}
    if hero:
        definition["hero"] = hero
    return definition


RELICS = {
    "ice_horseshoes": relic("Ледяные подковы", "mat_ember", "Заверши [Шаг] на воде: последняя пройденная водная клетка замёрзнет до следующего хода.", "common"),
    "smoke_jug": relic("Кувшин обратного дыма", "relic_whetstone", "Когда [Огонь] превращает воду в пар, можешь сдвинуть облако на соседнюю клетку."),
    "oil_chute": relic("Масляный желоб", "relic_whetstone", "Раз за ход можешь повернуть масляное скольжение от [Толчка] на 90° на последней клетке."),
    "briar_thimble": relic("Терновый напёрсток", "art_belt_common", "Когда [Толчок] загоняет врага в тернии, временные тернии позади него останавливают следующего врага на этой клетке."),
    "splitter_stone": relic("Камень дольщика", "mat_ember", "Если [Область] накрыла две трещины, можешь переложить один заряд между ними."),
    "edge_hook": relic("Крюк у обрыва", "mat_ember", "Раз за ход можешь направить [Толчок] вдоль края пропасти вместо падения."),
    "basalt_cup": relic("Базальтовая чашка", "mat_ember", "После [Шага] на лаву можешь поставить на соседней свободной клетке укрытие до следующего хода."),
    "reed_rattle": relic("Камышовая трещотка", "art_belt_common", "Первый [Шаг] из камыша за ход ставит трещотку. Враг, ступивший на неё, получает 1 метку.", "common"),
    "false_aim_chalk": relic("Мел чужого прицела", "art_belt_common", "Уйдя [Шагом] из отмеченной клетки, можешь оставить след. Следующий приближающийся враг делает один шаг к следу."),
    "cracked_clock": relic("Часы с трещиной", "relic_whetstone", "Раз за бой [Финал] в зоне атаки позволяет отложить одно намерение на ход. Зона остаётся на поле.", "rare"),
    "rag_double": relic("Тряпичный двойник", "art_belt_common", "Если сохранил [Защиту] под прицелом, можешь поставить рядом двойника. Первый одиночный выстрел уйдёт в него, если стрелок его видит."),
    "swappers_hook": relic("Крюк менялы", "mat_ember", "Раз за бой после [Преследования] по помеченному врагу вне отмеченных зон можешь поменяться с ним местами.", "rare"),
    "bell_salt": relic("Соль звонаря", "mat_ember", "Раз за бой можешь погасить центр вражеского креста, если твоя [Область] его накрывает."),
    "anchor_weight": relic("Якорная гиря", "relic_whetstone", "После хода без шагов, завершённого [Защитой], можешь потратить 4 щита, чтобы отменить следующее принудительное смещение."),
    "reverse_ruler": relic("Обратная линейка", "art_belt_common", "Когда [Толчок] сдвинул врага с намерением «залп по ряду», можешь перенести ряд на его новую позицию."),
    "double_spring": relic("Двойная пружина", "mat_ember", "После первого срабатывания [Ловушки] за бой можешь переставить её на соседнюю свободную клетку.", hero="hunter"),
    "piercing_seal": relic("Сквозная пломба", "relic_whetstone", "Первый [Выстрел] за ход, проходящий через твою баллисту, можешь направить в неё и дать 2 заряда.", hero="hunter"),
    "metered_shutter": relic("Мерный затвор", "mat_ember", "При залпе из баллисты с 10 зарядами можешь выстрелить на 7 и сохранить 3 заряда.", hero="hunter"),
    "repair_wedge": relic("Клин ремонтника", "art_belt_common", "После разрушения баллисты врагом [Шаг] к обломкам позволяет сделать из них соседнее укрытие.", hero="hunter"),
    "mobile_mount": relic("Подвижная опора", "mat_ember", "Если ходил [Шагом] в ход зарядки, можешь передвинуть баллисту на клетку ценой её следующего пассивного заряда.", hero="hunter"),
    "tin_bandolier": relic("Оловянный патронташ", "art_belt_common", "Первая [Пуля], попавшая в цель, пойманную капканом, может вернуться наверх колоды. Изгнание имеет приоритет.", hero="hunter"),
    "empty_pedestal": relic("Пустой постамент", "relic_whetstone", "Раз за бой после уничтожения вражеского тотема [Дроблением] можешь оставить постамент. Он ломается после первого столкновения с врагом.", "rare"),
}


class BoardRelics:
    def __init__(self, battle):
        self.battle = battle
        self.active = frozenset(item["id"] for item in battle.items.list)
        self.used = {}
        self.move_card = None
        self.playing_card = None
        self.steps = []
        self.ice = {}
        self.cover = {}
        self.positions = {}
        self.rattles = set()
        self.bramble = set()
        self.trapped = {}
        self.repaired = set()
        self.pedestals = set()
        self.delayed = {}
        self.lure = None
        self.decoy = None
        self.anchor = False
        self.player_stepped = False
        self.last_tags = frozenset()

    def ready(self, iid, scope=None):
        return iid in self.active and (scope is None or self.used.get(iid) != scope)

    def spent(self, iid, scope=None):
        if scope is not None:
            self.used[iid] = scope
        b = self.battle
        b.say(RELICS[iid]["name"], (235, 200, 140))
        b.fx("relic", unit=b.hero, name=RELICS[iid]["name"])

    def choose_cell(self, iid, cells):
        choices = [(f"Клетка {x + 1}, {y + 1}", (x, y)) for x, y in sorted(set(cells))]
        if choices:
            return (yield RelicChoice(RELICS[iid]["name"], choices))
        return None

    def near(self, p):
        b = self.battle
        return [q for q, _ in b.c.grid.neighbors(p) if b.free(q)]

    def turn_start(self):
        b = self.battle
        for p, terrain in self.ice.items():
            cell = b.c.grid.get(p)
            if cell is not None and cell.terrain == "ice_floor":
                cell.terrain = terrain
        for p, cover in self.cover.items():
            cell = b.c.grid.get(p)
            if cell is not None and cell.cover == "half":
                cell.cover = cover
        self.ice.clear()
        self.cover.clear()
        self.bramble.clear()
        self.player_stepped = False
        self.last_tags = frozenset()
        self.trapped = {u: turn for u, turn in self.trapped.items() if u.alive and turn >= b.turn}

    def begin_play(self, card, mode):
        self.playing_card = card if mode == "main" else None
        self.move_card = card if "step" in card.tag_ids and mode == "main" else None
        self.steps = []

    def record_step(self, origin, destination):
        if self.move_card is not None:
            self.steps.append((origin, destination))

    def cover_at(self, p, temporary):
        cell = self.battle.c.grid.get(p)
        if cell is not None:
            if temporary:
                self.cover.setdefault(p, cell.cover)
            cell.cover = "half"

    def warnings_at(self, p):
        return [u for u in self.battle.foes() if p in (u.intent or {}).get("cells", [])]

    def after_movement(self, card):
        if self.move_card is not card:
            return
        self.move_card = None
        if not self.steps:
            return
        b = self.battle
        self.player_stepped = True
        origin, final = self.steps[0][0], b.hero.cell
        grid = b.c.grid
        terrain = grid.get(final).terrain
        if terrain == "water" and self.ready("ice_horseshoes"):
            water = [p for p, _ in self.steps if grid.get(p).terrain == "water"]
            p = water[-1] if water else final
            cell = grid.get(p)
            self.ice[p], cell.terrain = cell.terrain, "ice_floor"
            self.spent("ice_horseshoes")
        if self.ready("reed_rattle", b.turn) and (grid.get(origin).terrain == "reeds" or grid.get(origin).cover == "reeds"):
            self.rattles.add(origin)
            self.spent("reed_rattle", b.turn)
        if self.ready("basalt_cup") and terrain in ("lava", "lava_floor"):
            p = yield from self.choose_cell("basalt_cup", self.near(final))
            if p is not None:
                self.cover_at(p, temporary=True)
                self.spent("basalt_cup")
        if self.ready("false_aim_chalk") and self.warnings_at(origin) and not self.warnings_at(final):
            leave = yield RelicChoice(RELICS["false_aim_chalk"]["name"], [("Оставить ложный след", True)])
            if leave:
                self.lure = origin
                self.spent("false_aim_chalk")
        if self.ready("repair_wedge"):
            close = {p for p in self.repaired if cheb(p, final) <= 1}
            if close:
                p = yield from self.choose_cell("repair_wedge", self.near(final))
                if p is not None:
                    self.cover_at(p, temporary=False)
                    self.repaired.remove(min(close))
                    self.spent("repair_wedge")

    def enter_enemy(self, unit, p):
        if p in self.rattles:
            self.rattles.remove(p)
            unit.ds["mark"] += 1
            self.battle._icons(unit)
        if p in self.bramble:
            self.bramble.remove(p)
            unit.ds["root"] = max(unit.ds["root"], 1)
            return True
        return False

    def steam_created(self, p):
        b = self.battle
        if b.c.grid.get(p).hazard != "fog":
            return
        target = yield from self.choose_cell("smoke_jug", self.near(p))
        if target is not None:
            original = b.c.grid.get(p)
            original.hazard, original.hazard_time = None, 0
            b.set_surface(target, "fog")
            self.spent("smoke_jug")

    def edge_direction(self, target, direction):
        b = self.battle
        iid = "edge_hook"
        if not self.ready(iid, b.turn):
            return None
        x, y = target.cell
        dx, dy = direction
        target_cell = yield from self.choose_cell(iid, ((x + a, y + c) for a, c in ((-dy, dx), (dy, -dx))
                                                         if b.free((x + a, y + c), exclude=target)))
        if target_cell is not None:
            self.spent(iid, b.turn)
        return target_cell

    def oil_direction(self, unit, direction):
        b = self.battle
        iid = "oil_chute"
        if not self.ready(iid, b.turn):
            return None
        x, y = unit.cell
        dx, dy = direction
        target = yield from self.choose_cell(iid, ((x + a, y + c) for a, c in ((-dy, dx), (dy, -dx))
                                                    if b.free((x + a, y + c), exclude=unit)))
        if target is not None:
            self.spent(iid, b.turn)
        return target

    def after_push(self, card, unit, origin):
        b = self.battle
        if card is None or "push" not in card.tag_ids or not unit.alive or origin == unit.cell:
            return
        new = b.c.grid.get(unit.cell)
        if self.ready("briar_thimble") and new.hazard == "briar":
            x, y = unit.cell
            dx, dy = x - origin[0], y - origin[1]
            back = (x - ((dx > 0) - (dx < 0)), y - ((dy > 0) - (dy < 0)))
            self.bramble.add(back)
            self.spent("briar_thimble")
        it = unit.intent or {}
        if self.ready("reverse_ruler") and it.get("shape") == "row":
            row = [p for p in b.c.grid.cells if p[1] == unit.cell[1] and p != unit.cell and b.c.grid.passable(p)]
            if row != it.get("cells"):
                change = yield RelicChoice(RELICS["reverse_ruler"]["name"], [("Перенести ряд", True)])
                if change:
                    it["cells"] = row
                    self.spent("reverse_ruler")

    def area(self, card, center, radius):
        b = self.battle
        if center is None or "area" not in card.tag_ids:
            return
        points = set(b.c.grid.in_radius(center, radius))
        if self.ready("splitter_stone"):
            cracks = {p: b.cracks_at(p) for p in points if b.cracks_at(p)}
            recipients = {p for p, n in cracks.items() if n < 5}
            donors = [p for p in cracks if recipients - {p}]
            old = yield from self.choose_cell("splitter_stone", donors)
            if old is not None:
                new = yield from self.choose_cell("splitter_stone", recipients - {old})
                if new is not None:
                    cell = b.c.grid.get(old)
                    cell.charge["cracks"] -= 1
                    if not cell.charge["cracks"]:
                        cell.charge, cell.hazard = None, None
                    b.set_surface(new, "cracks")
                    if b.cracks_at(new) >= 5:
                        b.detonate_cracks(new, src=b.hero)
                    self.spent("splitter_stone")
        if self.ready("bell_salt", "battle"):
            enemies = [u for u in b.foes() if (u.intent or {}).get("shape") == "cross"
                       and u.intent.get("cross_center") in points and u.intent["cross_center"] in u.intent.get("cells", [])]
            if enemies:
                chosen = yield RelicChoice(RELICS["bell_salt"]["name"], [(u.name, u) for u in enemies])
                if chosen is not None:
                    chosen.intent["cells"].remove(chosen.intent["cross_center"])
                    self.spent("bell_salt", "battle")

    def around_attack(self, card, target):
        b = self.battle
        if target is None or not target.alive:
            return
        if self.ready("swappers_hook", "battle") and "pursuit" in card.tag_ids and target.ds.get("mark") \
                and not self.warnings_at(target.cell):
            swap = yield RelicChoice(RELICS["swappers_hook"]["name"], [(f"Поменяться с {target.name}", True)])
            if swap:
                origin, destination = b.hero.cell, target.cell
                b.c._place(b.hero, destination, 0.2)
                b.c._place(target, origin, 0.2)
                b._enter(b.hero, destination)
                b._enter(target, origin)
                self.spent("swappers_hook", "battle")

    def finale(self, card):
        b = self.battle
        if "finale" not in M.card_rules(card.d) or not self.ready("cracked_clock", "battle"):
            return
        enemies = self.warnings_at(b.hero.cell)
        if enemies:
            enemy = yield RelicChoice(RELICS["cracked_clock"]["name"], [(f"Отложить: {u.name}", u) for u in enemies])
            if enemy is not None:
                self.delayed[enemy] = b.turn
                self.spent("cracked_clock", "battle")

    def retained(self, card):
        b = self.battle
        if "block" not in card.tag_ids or not self.ready("rag_double", b.turn) or not self.warnings_at(b.hero.cell):
            return
        p = yield from self.choose_cell("rag_double", self.near(b.hero.cell))
        if p is not None:
            self.decoy = p
            self.spent("rag_double", b.turn)

    def end_turn(self):
        b = self.battle
        if self.ready("anchor_weight") and b.walked == 0 and "block" in self.last_tags and b.hero.shield >= 4:
            anchor = yield RelicChoice(RELICS["anchor_weight"]["name"], [("Потратить 4 щита", True)])
            if anchor:
                b.hero.shield -= 4
                self.anchor = True
                self.spent("anchor_weight")

    def consume_lure(self, enemy):
        b = self.battle
        if self.lure is None or enemy.ds.get("root") or cheb(enemy.cell, b.hero.cell) <= 1:
            return None
        p = self.lure
        path = b.enemy_move_to(enemy, lambda q: q == p, lambda q: cheb(q, p))
        if path:
            self.lure = None
            return path[0]
        return None

    def take_decoy(self, enemy, intent):
        if self.decoy is None:
            return None
        b = self.battle
        visible = (b.los(enemy.cell, self.decoy) if intent.get("kind") == "zone"
                   else b.in_fire_zone(enemy, intent, self.decoy))
        if visible:
            p, self.decoy = self.decoy, None
            return p
        return None

    def trap_trigger(self, unit, p, damage):
        b = self.battle
        if self.ready("tin_bandolier"):
            self.trapped[unit] = b.turn + int(b.enemy_phase)
        if not self.ready("double_spring", "battle"):
            return
        baits = [q for q in self.near(p) if q not in b.traps]
        target = yield from self.choose_cell("double_spring", baits)
        self.used["double_spring"] = "battle"
        if target is not None:
            b.traps[target] = damage
            self.spent("double_spring", "battle")

    def shot_targets(self, card, use, trace):
        b = self.battle
        if "shot" not in card.tag_ids or not use.get("ranged") or not self.ready("piercing_seal", b.turn):
            return []
        origin = b.hero.cell
        visible = {u.cell: u for u in b.ballistas if u.charge < u.charge_max and b.los(origin, u.cell)}
        interceptors = []
        for foe in b.foes():
            if cheb(origin, foe.cell) > use.get("range", 1):
                continue
            if use.get("line") and origin[0] != foe.cell[0] and origin[1] != foe.cell[1]:
                continue
            for p in trace(origin, foe.cell)[1:-1]:
                cell = b.c.grid.get(p)
                if cell is not None and not cell.passable and cell.cover == "full":
                    break
                if p in visible:
                    interceptors.append(visible[p])
                    break
        return list(dict.fromkeys(interceptors))

    def redirect_shot(self, unit):
        b = self.battle
        unit.charge = min(unit.charge_max, unit.charge + 2)
        self.spent("piercing_seal", b.turn)

    def intercept_shot(self, card, target, line):
        b = self.battle
        iid = "piercing_seal"
        if target is None or "shot" not in card.tag_ids or not self.ready(iid, b.turn):
            return False
        choices = [u for u in b.ballistas if u.cell in line and u.charge < u.charge_max]
        if choices:
            self.used[iid] = b.turn
            unit = yield RelicChoice(RELICS[iid]["name"], [(f"Зарядить баллисту {u.cell[0] + 1}, {u.cell[1] + 1}", u)
                                                          for u in choices])
            if unit is not None:
                self.redirect_shot(unit)
                return True
        return False

    def held_charge(self, unit):
        iid = "metered_shutter"
        if unit.charge == 10 and self.ready(iid):
            keep = yield RelicChoice(RELICS[iid]["name"], [("Выстрелить на 7 и оставить 3 заряда", True)])
            if keep:
                self.spent(iid)
                return 3
        return 0

    def ballista_loaded(self, unit):
        b = self.battle
        if not self.player_stepped or not self.ready("mobile_mount") or unit.ds.get("skip_passive_charge"):
            return
        p = yield from self.choose_cell("mobile_mount", self.near(unit.cell))
        if p is not None:
            b.c._place(unit, p, 0.2)
            unit.ds["skip_passive_charge"] = True
            self.spent("mobile_mount")

    def ballista_destroyed(self, unit, attacker):
        if self.ready("repair_wedge") and attacker is not None and attacker.team != unit.team:
            self.repaired.add(unit.cell)

    def bullet_returns(self, card, tgt):
        b = self.battle
        iid = "tin_bandolier"
        if "bullet" not in card.tag_ids or tgt not in self.trapped or not self.ready(iid, b.turn):
            return False
        self.used[iid] = b.turn
        use = yield RelicChoice(RELICS[iid]["name"], [("Вернуть карту наверх колоды", True)])
        if use:
            b.draw_pile.append(card)
            self.spent(iid, b.turn)
            return True
        return False

    def pedestal(self, p):
        b = self.battle
        cell = b.c.grid.get(p)
        if cell is None or not cell.passable:
            return
        leave = yield RelicChoice(RELICS["empty_pedestal"]["name"], [("Оставить постамент", True)])
        if leave:
            self.positions[p] = cell.cover
            cell.cover, cell.passable = "full", False
            self.pedestals.add(p)
            self.spent("empty_pedestal", "battle")

    def check_totem(self, card, target):
        if card is None or "pulverize" not in card.tag_ids or target.alive:
            return
        name = getattr(target, "eid", None) or getattr(target, "cls", "")
        if (target.edef or {}).get("totem") or "totem" in (name or ""):
            if self.ready("empty_pedestal", "battle"):
                yield from self.pedestal(target.cell)

    def break_pedestal(self, p):
        if p in self.pedestals:
            self.pedestals.remove(p)
            cell = self.battle.c.grid.get(p)
            cell.cover, cell.passable = self.positions.pop(p), True
