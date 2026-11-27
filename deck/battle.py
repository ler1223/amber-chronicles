"""Бой «Спуска» (docs/descent.md §2): ход игрока — 3 энергии и 5 карт; у карты основное применение за энергию и
простое за 0; враги заранее показывают намерения (удар, выстрел по обзору, зона, защита, лечение, рёв).

Поле и фигурки — sim.combat.Combat (клетки, юниты, события для ui.battle_view), но его шаги не идут. Всё, что
двигает фигурки, — генераторы: после каждого шага они отдают ("wait", сек), экран ждёт анимацию; в тестах
генератор просто прокручивается до конца (finish).
"""
import copy
import random
from dataclasses import dataclass

from sim.combat import ENEMY, PLAYER, Combat
from sim.grid import DIRS8, cheb, sign
from sim.unit import Unit

from . import model as M
from .model import BALLISTA_CHARGES, BALLISTA_HP
from .idols import IdolCast, Idols
from .fae import FaeGarden
from .items import Items
from .relic_run import RunRelics
from .relic_hand import HandRelics
from .relic_board import BoardRelics


WAIT = ("wait", 0.0)
IMPACT = ("impact", 0.0)     # экран: проиграть выпущенный эффект и ждать попадания — урон применится после
STEP_T = 0.2                     # длительность шага фигурки (по прямой; разгон и торможение — вдвое дольше)
COLLIDE = 3                      # урон столкновения за каждую невыполненную клетку толчка
BALLISTA_DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))
ONCE = {"burn_all", "block", "heat", "draw", "energy", "heal", "lose_hp", "strength", "collide_x2", "thorns", "cleanse", "rage",
        "keep_momentum", "momentum", "ranged_bonus", "focus", "heat_regen", "add_card", "ignite", "trap", "detonate",
        "counter", "burn_card", "strength_x2", "fort", "double_next", "next_energy", "next_draw", "add_random", "resource",
        "fae", "spend_fae", "plant", "beast", "attach", "fae_ring", "blueprint",
        "stance"}
HAND_MAX = 10
COUNTER = 4                      # Контратака: ответный удар (+ Мощь)
ADVANCE = {"block", "guard", "rally", "roar", "summon", "curse", "hex", "drown", "heal", "veil"}   # и шагают
PRIEST_HAND = 5                  # Жрец: несыгранные свитки остаются в руке — до 5 (карты «толстые»)
PRIEST_WALK = 3                  # Жрец: шагов за ход (сам он только ходит)


@dataclass(frozen=True)
class BallistaShot:
    ballista: Unit
    victim: Unit


def finish(gen):
    """Прокрутить генератор до конца (тесты, бот)."""
    for _ in gen or ():
        pass


def bresenham(a, b):
    x0, y0 = a
    x1, y1 = b
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    out = []
    while True:
        out.append((x0, y0))
        if (x0, y0) == (x1, y1):
            return out
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


class Battle:
    def __init__(self, gd, run, fight, seed=None):
        """gd — данные игры с картами боёв (sim.expedition.expedition_data), run — забег, fight — описание боя."""
        self.gd = gd
        self.run = run
        self.edefs = run.data["enemies"]["enemies"]
        self.rng = random.Random(seed)
        self.fight = fight
        enc = copy.deepcopy(next(e for e in gd.encounters if e.get("id") == fight["map"]))
        hero_pos, foes = self.place(gd, enc, fight)
        enc["player_spawn"] = [list(hero_pos)]
        enc["enemies"] = [{"type": self.edefs[eid]["sprite"], "pos": list(pos)} for eid, pos in foes]
        for k in ("waves", "objective", "phases", "fog", "objects"):
            enc.pop(k, None)
        data = copy.copy(gd)
        data.encounters = [enc]
        self.c = Combat(data, 0, ai_teams=(), squad=[{"cls": run.sprite, "proto": gd.classes[run.sprite]}])
        self.c.arena = []
        for u in list(self.c.units):                      # спутники классов (пёс ловчего) — не нужны
            if u.team == PLAYER and u.summon:
                self.c.units.remove(u)
        self.hero = next(u for u in self.c.units if u.team == PLAYER and not u.obj)
        art = (getattr(run, "hero", None) or {}).get("art_sprite")
        if art:
            self.hero.art_sprite = art
        self._setup(self.hero, {"name": run.hero_name, "hp": run.max_hp}, hp=run.hp)
        self.hp_k, self.dmg_k = run.scale() if hasattr(run, "scale") else (1.0, 1.0)
        units = [u for u in self.c.units if u.team == ENEMY and not u.obj]
        for u, (eid, _) in zip(units, foes):
            self._setup(u, self.edefs[eid], eid=eid)
        self.hero_def = getattr(run, "hero", None) or {}
        self.mech = self.hero_def.get("mechanic")          # momentum | hunter | heat — у каждого героя своё
        self.variant = getattr(run, "variant", None)
        self.energy = 0
        self.max_energy = self.hero_def.get("energy", 3)
        self.hand_size = self.hero_def.get("hand", 5) if hasattr(self, "hero_def") else 5
        self.enemy_phase = False
        self.traps = {}                                   # клетка -> урон капкана Охотницы
        self._ballistas = []
        self.prey = None                                  # Охотница «Метка добычи»
        if self.mech == "heat":
            self.hero.ds["heat"] = self.hero_def.get("heat_start", 2)
        if self.mech == "fae":
            self.hero.ds["fae"] = 0
        if self.mech == "hunter" and self.variant == "mark":
            self.mark_prey()
        self.draw_pile = [card for card in run.deck if card.cid not in M.BALLISTA_COMMANDS]
        self.rng.shuffle(self.draw_pile)
        self.hand, self.used, self.discard, self.exhaust = [], [], [], []
        self.turn = 0
        self.retained_card_discounts = {}
        self.lead_discounts = set()
        self.result = None
        self.log = []
        self.collide_k = 1
        self.played = 0                                   # основных розыгрышей за ход (синергии)
        self.turn_tags = []                               # теги сыгранных основным за ход — по порядку
        self.walked = 0                                   # клеток героем за ход (С разбега)
        self.stance = None
        self.stance_uses = set()                          # сработавшие в этот ход бонусы стоек
        self.echoed = set()                               # Отклик/Цепочка: какие карты уже сработали в этот ход
        self._free_cast = False                           # Цепочка: карта играется без стоимости
        self.chain_drawn = 0                              # Цепная реакция Охотницы: добор за цепочки
        self.queue = []                                   # события для Отклика: (вид, юнит)
        self.guard = []                                   # карты, ждущие в руке ход врага (отклик на события)
        self.temper = {}                                  # Закалка: uid карты → прибавка до конца боя
        self.exhaust_plays = {}
        self.finale_pending = False
        self._mom = None                                  # разгон на момент розыгрыша (для условия «Разгон N»)
        self.zone_fx = None
        self.env = dict(fight.get("env") or {})              # природа боя: ветер / лавовый дождь (умеренно)
        self.env_now = None                                   # что природа сделает в этот ход врагов
        self.items = Items(self)                              # предметы забега (data/deck/relics.json, deck/items.py)
        self.run_relics = RunRelics(self)
        self.hand_relics = HandRelics(self)
        self.board_relics = BoardRelics(self)
        self.double_next = False                              # предмет: следующая атака — двойной урон
        self.next_energy = self.next_draw = 0                 # предмет: прибавка к следующему ходу
        self.pending_discard = 0                              # Адажио: сколько карт игрок должен выбрать для сброса
        self.temporary_retain = {}
        self.double_attacks = 0                               # улучшение: сколько атак ещё удвоить
        self.powers = []                                      # сыгранные карты-Силы: действуют до конца боя
        self.ballista_power_targets = {}                     # uid Силы → выбранная установка
        self.powered = set()                                  # (uid Силы, ход, событие) — у Сил «раз за ход»
        self.garden = FaeGarden(self) if self.mech == "fae" else None   # Эльф: феи, растения, звери, прививки
        self.attach_reveal = None                                     # «прививка сработала»: карта для показа экрану
        self.idols = Idols(self) if self.mech == "idols" else None    # Жрец: статуи богов падают на поле
        self.walk_max = PRIEST_WALK if self.idols else 0
        self.walk_left = 0
        self.battle_start_mods()
        self.draw_pile.sort(key=lambda card: "initiation" in M.card_rules(card.d))
        self.run_relics.prepare_pile()
        self.start_player_turn_now()
        finish(self.items.fire("battle"))
        finish(self.react())

    def battle_start_mods(self):
        """Постоянные правила предметов на весь бой: энергия, сила врагов, плата HP, «Тина» в колоду."""
        it = self.items
        if self.mech not in ("heat", "idols"):
            self.max_energy += it.mod("energy")
        for u in self.foes():
            u.ds["strength"] += it.mod("foe_strength")
        if it.mod("start_hp"):
            self.hurt(self.hero, it.mod("start_hp"), None, "hp_cost")
        for _ in range(it.mod("slime")):
            if "slime_rot" in self.run.defs:
                self.draw_pile.insert(self.rng.randrange(len(self.draw_pile) + 1), M.Card("slime_rot", self.run.defs))

    def place(self, gd, enc, fight):
        """Расстановка: заданная в бою или своя — герой слева посередине, враги справа в 4–8 клетках."""
        if fight.get("hero"):
            return fight["hero"], [(e[0], e[1]) for e in fight["enemies"]]
        rows = enc["map"]
        legend = gd.config["legend"]
        w, h = len(rows[0]), len(rows)
        ok = lambda p: legend[rows[p[1]][p[0]]].get("passable", True) and             not legend[rows[p[1]][p[0]]].get("hazard")   # noqa: E731
        hero = min((p for p in ((x, y) for x in range(3) for y in range(h)) if ok(p)),
                   key=lambda p: (abs(p[1] - h // 2), p[0]))
        cells = [(x, y) for x in range(w // 2, w) for y in range(h) if ok((x, y)) and 4 <= cheb((x, y), hero) <= 8]
        self.rng.shuffle(cells)
        chosen = []
        for c in sorted(cells, key=lambda c: -c[0]):
            if all(cheb(c, o) >= 2 for o in chosen):
                chosen.append(c)
            if len(chosen) == len(fight["enemies"]):
                break
        enemies = [e if isinstance(e, str) else e[0] for e in fight["enemies"]]
        return hero, list(zip(enemies, chosen))

    # ---------- юниты ----------

    def _setup(self, u, d, eid=None, hp=None):
        u.name = d["name"]
        u.max_hp = d["hp"] if not eid else max(1, int(round(d["hp"] * self.hp_k)))
        u.hp = u.max_hp if hp is None else hp
        u.ap_max = u.ap = u.pp_max = u.pp = 0
        u.skills = []
        u.shield, u.shield_time = 0, 1e9
        u.ds = {"burn": 0, "poison": 0, "frost": 0, "wet": 0, "weak": 0, "vulnerable": 0, "stun": False,
                "strength": 0, "thorns": 0, "mark": 0, "aim": 1, "rage": 0, "root": 0,
                "momentum": 0, "keep_mom": False, "heat": 0, "heat_regen": 0, "ranged_bonus": 0, "focus": False,
                "veil": 0, "hex": 0, "fort": 0, "bleed": 0, "counter": 0, "hunt": 0, "fae": 0}
        u.phase = 0                                           # фаза босса (0 — первая)
        u.eid = eid
        u.edef = d if eid else None
        u.cyc = 0
        u.intent = None
        u.speed = d.get("speed", 3)
        self._icons(u)

    def _icons(self, u):
        """Состояния — значками над полоской HP (теги нынешней игры)."""
        ds = u.ds
        st = {}
        if ds["burn"]:
            st["fire"] = float(ds["burn"])
        if ds["wet"]:
            st["water"] = float(ds["wet"])
        if ds["frost"]:
            st["ice"] = float(ds["frost"])
        if ds["poison"]:
            st["poison"] = float(ds["poison"])
        if ds.get("bleed"):
            st["bleed"] = float(ds["bleed"])
        if ds.get("veil"):                                  # туман — как «в тени» экспедиции: значок и полупрозрачность
            u.buffs["stealth"] = [1.0, 1.0]
        else:
            u.buffs.pop("stealth", None)
        u.statuses = st
        u.stun = 1.0 if ds["stun"] else 0.0
        u.stun_total = 1.0

    def fx(self, kind, **kw):
        """Событие для экрана: эффект механики или простого действия (deck/ui.py рисует его сам)."""
        self.c.emit("deck_fx", kind=kind, **kw)

    def vfx(self, u, sid, name, target=None, center=None, radius=0, tag=None, *, effect_only=False,
            empowered=False, line=()):
        """Эффект навыка из библиотеки игры (data/vfx.json): событие «skill» — экран сыграет каст, полёт и удар,
        а урон, пришедший следом, покажет в момент попадания."""
        if not sid:
            return False
        base = self.gd.skills.get(sid)
        sk = dict(base) if base else {"target": "enemy", "range": 5, "ap": 0, "cast": 0, "cooldown": 0,
                                       "effects": [{"type": "damage"}]}
        sk["name"] = name
        sk["radius"] = radius
        if tag:
            sk["effects"] = [{"type": "damage", "tag": tag}]
        u.skill_defs = dict(u.skill_defs)
        u.skill_defs[sid] = sk
        c = center if center is not None else (target.cell if target is not None else u.cell)
        self.c.emit("skill", unit=u, skill=sid, center=tuple(c), radius=radius, target=target, auto=False,
                    effect_only=effect_only, empowered=empowered, line=line)
        return True

    def elf_cast(self, source, effect, name, target=None, center=None, radius=0, *, empowered=False):
        self.vfx(source, effect, name, target=target, center=center, radius=radius, effect_only=True, empowered=empowered)
        yield IMPACT

    def foes(self):
        return [u for u in self.c.units if u.team == ENEMY and u.alive and not u.obj]

    def say(self, text, col=(220, 210, 190)):
        self.log.append((text, col))
        self.log = self.log[-40:]

    def set_stance(self, stance):
        self.stance = stance

    def attacks_locked(self, card):
        return self.stance == "guard" and card.d.get("type") == "attack"

    def shield_value(self, u, n):
        """Размер следующего начисления защиты, без расходования бонусов стойки."""
        if u is not self.hero or n <= 0:
            return n
        if self.stance == "guard":
            return (3 * n + 1) // 2
        if self.stance == "ready" and "ready" not in self.stance_uses:
            return n + 2
        return n

    def gain_shield(self, u, n):
        gained = self.shield_value(u, n)
        if u is self.hero and n > 0 and self.stance == "ready":
            self.stance_uses.add("ready")
        u.shield += gained
        self.c.emit("shield", unit=u, amount=gained)

    def gain_fae(self, n):
        """Феи 0–10; всё сверх десяти сразу становится защитой."""
        if n <= 0:
            return 0
        h = self.hero
        before = h.ds.get("fae", 0)
        total = before + n
        h.ds["fae"] = min(10, total)
        if total > 10:
            self.gain_shield(h, total - 10)
        self.say(f"Феи: {h.ds['fae']}/10", (180, 235, 190))
        self.fx("status", unit=h, el="fae")
        if h.ds["fae"] != before:
            self.fx("fae_count", count=h.ds["fae"])
        return h.ds["fae"] - before

    def spend_fae(self, n, tgt=None):
        """Потратить до n фей. Порог/Корона проверяют фактическую трату."""
        h = self.hero
        before = h.ds.get("fae", 0)
        spent = min(max(0, n), before)
        h.ds["fae"] = before - spent
        if spent:
            self.say(f"Феи: {h.ds['fae']}/10 (−{spent})", (200, 230, 170))
            self.fx("status", unit=h, el="fae")
            self.fx("fae_count", count=h.ds["fae"])
            if self.garden is not None:
                self.garden.on_spend(spent, tgt, before=before)
        return spent

    def fae_empower_spec(self, card, u):
        """Усиленная версия включается на пороге; только она сжигает фей."""
        if self.garden is None:
            return 0, {}
        fae = self.hero.ds.get("fae", 0)
        threshold = M.fae_threshold(u)
        if threshold is None or fae < threshold:
            return 0, {}
        burn = M.fae_burn_value(u, card.d.get("type"))
        if burn == 0:
            return 0, {}
        spent = fae if burn == "all" else min(fae, int(burn))
        return spent, dict(u.get("fae_bonus") or {})

    def fae_bonus(self, ctx, kind):
        return ctx.get("fae_spent", 0) * (ctx.get("fae_bonus") or {}).get(kind, 0)

    # ---------- поле ----------

    def free(self, p, exclude=None):
        cell = self.c.grid.get(p)
        if cell is None or not cell.passable:
            return False
        return all(not (v.alive and v.cell == p and v is not exclude and not v.obj) for v in self.c.units) and \
            not any(v.alive and v.obj and v.cell == p for v in self.c.units)

    def paths(self, u, limit):
        """Клетки, куда u дойдёт за limit шагов: {клетка: путь}."""
        if u is self.hero and not self.enemy_phase and self.stance == "knight":
            return {u.cell: [], **self.knight_paths(limit)}
        out = {u.cell: []}
        frontier = [u.cell]
        for _ in range(limit):
            nxt = []
            for p in frontier:
                for n, _ in self.c.grid.neighbors(p):
                    if n in out or not self.free(n, exclude=u):
                        continue
                    out[n] = out[p] + [n]
                    nxt.append(n)
            frontier = nxt
        return out

    def knight_paths(self, limit):
        """Прыжок расходует одно действие движения и касается только клетки приземления."""
        if limit <= 0:
            return {}
        h = self.hero
        x, y = h.cell
        destinations = [(x + sx * dx, y + sy * dy)
                        for dx, dy in ((1, 2), (2, 1)) for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1))]
        return {p: [p] for p in destinations if self.free(p, exclude=h)}

    def dash_paths(self, limit):
        """Траектории рывка для прицела и розыгрыша карты."""
        h = self.hero
        if self.stance == "knight" and not self.enemy_phase:
            return self.knight_paths(limit)
        out = {}
        for dx, dy in DIRS8:
            p = h.cell
            path = []
            for _ in range(limit):
                q = (p[0] + dx, p[1] + dy)
                if not self.free(q, exclude=h):
                    break
                if dx and dy and not (self.free((p[0] + dx, p[1])) and self.free((p[0], p[1] + dy))):
                    break
                path.append(q)
                out[q] = list(path)
                p = q
        return out

    def los(self, a, b):
        blockers = {u.cell for u in self.ballistas}
        if self.garden is not None:
            blockers |= {u.cell for u in self.garden.walls if u.alive and getattr(u, "blocks_los", False)}
        for p in bresenham(a, b)[1:-1]:
            cell = self.c.grid.get(p)
            if p in blockers or (cell is not None and not cell.passable and cell.cover == "full"):
                return False
        return True

    @property
    def ballista(self):
        return next((unit for unit in self._ballistas if unit.alive), None)

    @property
    def ballistas(self):
        return [unit for unit in self._ballistas if unit.alive]

    def ballista_locked(self, card):
        if card is not None and card.cid != M.BALLISTA_CARD:
            return False
        if getattr(card, "copied", False):
            return any(unit.ballista_card_uid == card.uid for unit in self.ballistas)
        return any(not unit.ballista_copied for unit in self.ballistas)

    def ballista_place_cells(self, reach=2, card=None):
        if self.ballista_locked(card):
            return []
        origin = self.hero.cell
        return [p for p in self.c.grid.in_radius(origin, reach)
                if self.free(p) and self.los(origin, p)]

    def place_ballista(self, cell, reach=2, hp=BALLISTA_HP, charge=0, card=None):
        if cell not in self.ballista_place_cells(reach, card):
            return
        color = (190, 156, 98)
        proto = {"name": "Баллиста", "label": "Ба", "color": color, "role": "object", "hp": hp,
                 "move_time": 1.0, "attack": {"damage": 0, "range": 0, "cooldown": 99.0}, "static": True,
                 "object": {"id": "ballista", "art": "ballista", "name": "Баллиста", "hp": hp, "color": color}}
        unit = self.c._spawn(PLAYER, "ballista", proto, cell)
        self._setup(unit, proto)
        unit.owner = self.hero
        unit.charge_max = BALLISTA_CHARGES
        unit.charge = min(unit.charge_max, charge)
        unit.ballista_card_uid = card.uid if card is not None else None
        unit.ballista_copied = getattr(card, "copied", False)
        self._ballistas.append(unit)
        for pile in (self.hand, self.draw_pile, self.used):
            self.discard.extend(item for item in pile if self.ballista_locked(item))
            pile[:] = [item for item in pile if not self.ballista_locked(item)]
        for cid in reversed(M.BALLISTA_COMMANDS):
            command = M.Card(cid, self.run.defs)
            command.ballista_owner = unit
            self.draw_pile.append(command)
        self.say("Баллиста установлена. Зарядка и залп наверху колоды", (236, 205, 130))

    def remove_ballista_commands(self, owner):
        for pile in (self.hand, self.draw_pile, self.used, self.discard, self.exhaust, self.guard):
            pile[:] = [card for card in pile if getattr(card, "ballista_owner", None) is not owner]
        for unit in self.c.units:
            if getattr(unit, "stolen", None):
                unit.stolen[:] = [card for card in unit.stolen if getattr(card, "ballista_owner", None) is not owner]

    def ballista_load_targets(self, reach=2):
        ballistas = self.ballistas
        if not ballistas:
            return []
        return [self.hero] + [unit for unit in ballistas if unit.charge < unit.charge_max
                             and cheb(unit.cell, self.hero.cell) <= reach]

    def ballista_lines(self, reach=6, origin=None, ballista=None):
        """По одному лучу на сторону, до препятствия или первого врага включительно."""
        if origin is None:
            ballista = ballista if ballista is not None else self.ballista
            if ballista is None or not ballista.alive:
                return []
            origin = ballista.cell
        blockers = {u.cell for u in self.c.units if u.alive and u.obj and u is not ballista}
        foes = {u.cell: u for u in self.foes()}
        lines = []
        for dx, dy in BALLISTA_DIRS:
            cells = []
            victim = None
            for step in range(1, reach + 1):
                p = (origin[0] + dx * step, origin[1] + dy * step)
                cell = self.c.grid.get(p)
                if cell is None or not cell.passable or p in blockers:
                    break
                cells.append(p)
                victim = foes.get(p)
                if victim is not None:
                    if step > 1 and victim.ds.get("veil"):  # заслонённую цель нельзя выбрать издали
                        victim = None
                    break
            lines.append((cells, victim))
        return lines

    def ballista_shooters(self, target, reach=6):
        if target is None:
            return []
        return [unit for unit in self.ballistas if unit.charge and any(
            target is victim for _, victim in self.ballista_lines(reach, ballista=unit))]

    def ballista_damage(self, op=None, target=None, ballista=None):
        """Урон из зарядов, при наведении также учитывает эффекты цели перед щитом."""
        ballista = ballista if ballista is not None else self.ballista
        if ballista is None or not ballista.alive or not ballista.charge:
            return 0
        op = op or {}
        damage = op.get("n", 5) + (ballista.charge - 1) * op.get("per_charge", 3)
        damage += ballista.ds["ranged_bonus"] + ballista.ds.get("shot_empower", 0)
        if ballista.ds["focus"]:
            damage *= 2
        if target is None:
            return damage
        damage = self.hit_value(ballista, target, damage) * self.ballista_shot_multiplier(ballista)
        if self.hidden_in_fog(target):
            damage = max(1, damage // 2)
        return max(0, damage - (target.edef or {}).get("armor", 0))

    @staticmethod
    def ballista_shot_multiplier(ballista):
        return (2 if ballista.ds.get("double_next") else 1) * (2 if ballista.ds.get("double_attacks") else 1)

    def buff_ballista(self, ballista, op, amount):
        if not ballista.alive:
            return
        key = op["op"]
        ds = ballista.ds
        if key in ("focus", "double_next"):
            ds[key] = True
        elif key == "strength_x2":
            ds["strength"] *= 2
        else:
            key = "shot_empower" if key == "empower" else key
            ds[key] = ds.get(key, 0) + amount
        self.fx("status", unit=ballista, el="rally")

    def walk(self, u, path):
        n = len(path)
        for i, p in enumerate(path):
            if not u.alive or self.result:
                return
            knight_jump = u is self.hero and not self.enemy_phase and self.stance == "knight" and \
                {abs(p[0] - u.cell[0]), abs(p[1] - u.cell[1])} == {1, 2}
            near = u.team == ENEMY and cheb(u.cell, self.hero.cell) <= 1
            # путь — одним движением: разгон на первой клетке, торможение на последней, между — ровно
            ease = "inout" if n == 1 else "in" if i == 0 else "out" if i == n - 1 else "lin"
            if u is self.hero and not self.enemy_phase:
                self.board_relics.record_step(u.cell, p)
            previous = u.cell
            self.c._place(u, p, STEP_T * {"inout": 1.5, "in": 2.0, "out": 2.0, "lin": 1.0}[ease])
            u.move_ease = (ease, tuple(p))
            yield ("move", 0.0, u)
            self._enter(u, p)
            if self.idols and tuple(p) in self.idols.mud and not getattr(u, "statue", None):   # топь: увяз
                u.ds["root"] = max(u.ds["root"], 1)
                self.wet(u)
                self._icons(u)
                self.say(f"{u.name} вязнет в трясине", (170, 200, 140))
                return
            if u.team == ENEMY and u.alive and not near and cheb(u.cell, self.hero.cell) <= 1:   # подошёл вплотную
                self.queue.append(("near", u))
                yield from self.react()
            if u is self.hero and not self.enemy_phase:
                self.walked += 1
                yield from self.hand_relics.stepped(previous, knight_jump)
                if knight_jump and u.alive and "knight" not in self.stance_uses:
                    self.stance_uses.add("knight")
                    self.gain_shield(u, 3)
                if self.powers:
                    yield from self.power_fire("step")
                yield from self.items.fire("step")
            if u is self.hero and self.mech == "momentum" and not self.enemy_phase:     # Разгон: шаг — +1
                u.ds["momentum"] = min(self.hero_def.get("momentum_max", 5), u.ds["momentum"] + 1)
                self.fx("momentum_step", unit=u, n=u.ds["momentum"])
            if (yield from self.trigger_trap(u, p)):
                return
            if u.team == ENEMY and u.alive and self.board_relics.enter_enemy(u, p):
                return

    SURFACES = ("fire", "poison", "oil", "fog", "briar", "cracks")

    def trigger_trap(self, unit, cell):
        if unit.team != ENEMY or not unit.alive or cell not in self.traps:
            return False
        dmg = self.traps.pop(cell)
        self.say(f"{unit.name} попал в капкан: −{dmg}, встал", (255, 220, 140))
        self.hurt(unit, dmg, self.hero, "trap")
        unit.ds["root"] = max(unit.ds["root"], 1)
        self.queue.append(("trap", unit))
        yield from self.board_relics.trap_trigger(unit, cell, dmg)
        return True

    def set_surface(self, p, kind, n=1):
        """Покрытие клетки (docs/descent_field.md 1.2): огонь, яд, масло, туман, тернии, трещины (заряд копится).
        Огонь на масле — вспышка радиус 1; огонь на воде — пар (туман); вода гасит огонь."""
        cell = self.c.grid.get(p)
        if cell is None or not cell.passable:
            return
        steam = kind == "fire" and cell.terrain == "water"
        if steam:
            kind = "fog"                                            # пар
        if kind == "fire" and cell.hazard == "oil":                 # масло вспыхивает
            cell.hazard, cell.hazard_time, cell.blaze = "fire", -1.0, True
            self.say("Масло вспыхнуло!", (255, 170, 80))
            self.fx("react", unit=self.unit_at(p) or self.hero, what="flare")
            for q in self.c.grid.in_radius(p, 1):
                v = self.unit_at(q)
                if v is not None and not self.fireproof(v):
                    self.add_burn(v, 3)
                qc = self.c.grid.get(q)
                if q != p and qc is not None and qc.hazard == "oil":
                    self.set_surface(q, "fire")
            return
        if kind == "cracks":                                        # трещины копят заряд (до 5)
            have = cell.charge.get("cracks", 0) if cell.hazard == "cracks" and isinstance(cell.charge, dict) else 0
            cell.hazard, cell.hazard_time = "cracks", -1.0
            cell.charge = {"cracks": min(5, have + max(1, n))}
            return
        if kind == "fire" and cell.terrain == "ice_floor":
            return
        cell.hazard, cell.hazard_time = kind, -1.0
        cell.blaze = False
        if kind != "cracks":
            cell.charge = None
        card = self.board_relics.playing_card
        if steam and self.board_relics.ready("smoke_jug") and card is not None and "fire" in card.tag_ids:
            self.queue.append(("relic_job", self.board_relics.steam_created(tuple(p))))

    def unit_at(self, p):
        return next((v for v in self.c.units if v.alive and not v.obj and v.cell == tuple(p)), None)

    def cracks_at(self, p):
        cell = self.c.grid.get(p)
        if cell is None or cell.hazard != "cracks" or not isinstance(cell.charge, dict):
            return 0
        return cell.charge.get("cracks", 0)

    def detonate_cracks(self, p, k=2, src=None):
        """Трещина взрывается: урон = заряд ×k тому, кто на клетке; трещина исчезает."""
        n = self.cracks_at(p)
        if not n:
            return 0
        cell = self.c.grid.get(p)
        cell.hazard, cell.charge = None, None
        v = self.unit_at(p)
        self.zone_fx = ([tuple(p)], 0.5)
        if v is not None:
            self.say(f"Трещина взрывается под {v.name}: −{n * k}", (230, 190, 140))
            self.fx("react", unit=v, what="flare")
            self.hurt(v, n * k, src, "spell")
        return n

    def slippery(self, p):
        cell = self.c.grid.get(p)
        return cell is not None and (cell.terrain == "ice_floor" or cell.hazard == "oil")

    def hidden_in_fog(self, u):
        cell = self.c.grid.get(u.cell)
        return cell is not None and cell.hazard == "fog"

    def fireproof(self, u):
        return u is self.hero and self.mech == "heat"                    # Пиромантка не горит на своём огне

    def _enter(self, u, p):
        cell = self.c.grid.get(p)
        if cell.hazard == "cracks" and u.team == ENEMY and u.alive:  # враг ступил на трещину — она лопается
            self.detonate_cracks(p, 2, self.hero)
        if cell.hazard == "briar" and u.alive:                       # тернии: колют и держат
            self.hurt(u, 2, None, "spell")
            u.ds["root"] = max(u.ds["root"], 1)
        if cell.terrain == "water":
            self.wet(u)
        if cell.hazard == "fire" and not self.fireproof(u):
            self.add_burn(u, 2)
        if cell.hazard == "poison" and u.alive:
            self.add_poison(u, 2)

    def add_poison(self, u, n):
        if not u.ds["poison"]:
            self.fx("status", unit=u, el="poison")
        u.ds["poison"] += n
        self._icons(u)

    # ---------- состояния ----------

    def wet(self, u):
        if u.ds["burn"]:
            u.ds["burn"] = 0
            self.say(f"{u.name}: вода гасит горение", (150, 200, 255))
            self.fx("react", unit=u, what="steam")
        elif not u.ds["wet"]:
            self.fx("status", unit=u, el="water")
        u.ds["wet"] = 2
        self._icons(u)

    def add_burn(self, u, n):
        if u.ds["wet"]:                                     # огонь по мокрому — пар, мокрый снят
            u.ds["wet"] = 0
            self.say(f"{u.name}: пар — мокрый высох", (200, 200, 200))
            self.fx("react", unit=u, what="steam")
        else:
            if not u.ds["burn"]:
                self.fx("status", unit=u, el="fire")
            u.ds["burn"] += n
        self._icons(u)

    def add_frost(self, u, n):
        if u.ds["wet"]:                                     # мокрый + холод — сразу лёд
            u.ds["wet"] = 0
            u.ds["frost"] = 0
            u.ds["stun"] = True
            self.say(f"{u.name}: лёд! пропустит ход", (150, 220, 255))
            self.fx("react", unit=u, what="ice")
        else:
            if n and not u.ds["frost"]:
                self.fx("status", unit=u, el="ice")
            u.ds["frost"] += n
            if u.ds["frost"] >= 10:
                u.ds["frost"] = 0
                u.ds["stun"] = True
                self.say(f"{u.name}: мороз сковал — пропустит ход", (150, 220, 255))
                self.fx("react", unit=u, what="ice")
        self._icons(u)

    # ---------- урон ----------

    def attack_value(self, src, n):
        """Урон удара с силой и слабостью атакующего (без цели)."""
        v = n + src.ds["strength"]
        if src.ds["weak"]:
            v = int(v * 0.75)
        return max(0, v)

    def hit_value(self, src, tgt, n):
        v = self.attack_value(src, n)
        if tgt.ds["vulnerable"]:
            v = int(v * 1.5)
        return v + tgt.ds["mark"]

    def strike(self, src, tgt, n, kind="melee", el=None, anim=True, tag=None, mult=1):
        """Удар (генератор): замах/снаряд, ожидание попадания, потом урон — цифра и полоска HP в момент удара."""
        if not tgt.alive:
            return
        if kind in ("melee", "shot") and anim:
            self.c.emit("attack", src=src, dst=tgt, kind="melee" if kind == "melee" else "ranged", tag=tag)
            yield IMPACT
            if not tgt.alive or not src.alive:
                return
        v = self.hit_value(src, tgt, n) * mult
        tgt.ds["mark"] = 0
        if el == "lightning" and tgt.ds["wet"]:
            v *= 2
            tgt.ds["wet"] = 0
            self.say("Мокрый + молния: урон ×2", (255, 240, 140))
            self.fx("react", unit=tgt, what="shock")
        self.hurt(tgt, v, src, kind)
        if el == "cold":
            self.add_frost(tgt, 0)
        if tgt.ds["thorns"] and src.alive and cheb(src.cell, tgt.cell) <= 1 and kind == "melee":
            self.hurt(src, tgt.ds["thorns"], tgt, "thorns")
        ed = tgt.edef or {}
        if src is self.hero and kind == "melee" and cheb(src.cell, tgt.cell) <= 1:
            if ed.get("spikes") and src.alive:                         # колючий: бьёшь вплотную — ранишься
                self.say(f"{tgt.name}: колючки — {ed['spikes']}", (230, 200, 140))
                self.hurt(src, ed["spikes"], tgt, "thorns")
            if ed.get("retaliate") and tgt.alive and not getattr(tgt, "retaliated", 0) == self.turn:
                tgt.retaliated = self.turn                             # отвечает на удар вплотную (раз за ход)
                self.queue.append(("retaliate", tgt))

    def hurt(self, u, v, src=None, kind="melee"):
        """Урон с поглощением защитой (горение и яд защиту не учитывают)."""
        if not u.alive or v <= 0 or getattr(u, "statue", None):
            return
        if u is self.hero and self.idols is not None:
            if kind == "shot" and u.ds.get("windward"):                # Стрибог: встречный ветер
                v = max(1, v // 2)
            if u.ds.get("weave") and src is not None and src.team == ENEMY:   # Мокошь: удар уходит связанному
                bound = [f for f in self.foes() if f.ds.get("bound")]
                if bound:
                    u.ds["weave"] = 0
                    self.say(f"Нить: удар ушёл в {bound[0].name}", (210, 180, 240))
                    self.hurt(bound[0], v, None, "spell")
                    return
        if kind == "shot" and self.hidden_in_fog(u):                # в тумане: выстрел вслепую — вполсилы
            v = max(1, v // 2)
        ed = u.edef or {}
        if ed.get("armor") and kind in ("melee", "shot", "spell", "collision", "trap"):   # броня: −N от удара
            v = max(0, v - ed["armor"])
            if v <= 0:
                self.c.emit("damage", unit=u, amount=0, absorbed=0, kind="melee", tag=None, cover=False,
                            blocked="броня")
                return
        if ed.get("share") and kind not in ("burn", "poison", "bleed", "hp_cost", "share") and v >= 2:
            mates = [f for f in self.foes() if f is not u and cheb(f.cell, u.cell) <= 1]
            if mates:                                                   # стая: половину удара берёт сосед
                mate = min(mates, key=lambda f: -f.hp)
                half = v // 2
                v -= half
                self.hurt(mate, half, src, "share")
        absorbed = 0
        if kind not in ("burn", "poison", "hp_cost", "bleed") and u.shield > 0:
            absorbed = min(u.shield, v)
            u.shield -= absorbed
            v -= absorbed
        cap = (u.edef or {}).get("cap")
        if cap and kind not in ("burn", "poison", "hp_cost", "bleed"):    # рой / чешуя: от удара — не больше cap
            v = min(v, cap)
        u.hp -= v
        if u is self.hero and u.hp > 0 and u.hp * 2 < u.max_hp and not self.items.hp_low_fired:
            self.items.hp_low_fired = True
            self.queue.append(("hp_low", None))
        mate = getattr(u, "bound_to", None)
        if u.ds.get("bound") and kind != "bound" and mate is not None and mate.alive and v >= 2:   # нить: половина
            self.hurt(mate, v // 2, src, "bound")
        if u is self.hero and src is not None and src.team == ENEMY and kind in ("melee", "shot", "zone"):
            self.queue.append(("hit", src))
            if self.garden is not None and u.hp > 0:
                self.garden.snake_retaliate(src)
            if kind == "melee" and u.ds["counter"] > 0 and cheb(src.cell, u.cell) <= 1:   # Контратака: ответ
                self.queue.append(("counter", src))
        if u.hp <= 0 and u.team == ENEMY and (src is self.hero or src in self._ballistas):
            self.queue.append(("kill", u))
        self.c.emit("damage", unit=u, amount=v, absorbed=absorbed,
                    kind={"burn": "dot", "poison": "dot", "bleed": "dot"}.get(
                        kind, "melee" if kind in ("melee", "thorns", "collision") else "ranged" if kind == "shot"
                        else "spell"),
                    tag={"burn": "fire", "poison": "poison", "bleed": "bleed"}.get(kind), cover=False, blocked=None)
        if u.hp <= 0:
            self.die(u, src)
        elif (u.edef or {}).get("phases"):
            self.check_phase(u)

    def check_phase(self, u):
        """Фазы босса: HP ниже порога — новая фаза: объявление, то, что делает сразу, новые намерения."""
        phases = u.edef["phases"]
        while u.alive and u.phase < len(phases) and u.hp <= phases[u.phase]["at"] * u.max_hp:
            ph = phases[u.phase]
            u.phase += 1
            u.cyc = 0
            self.say(f"{u.name}: «{ph['name']}»!", (255, 200, 120))
            self.fx("phase", unit=u, name=ph["name"])
            for it in ph.get("enter", []):
                self.instant(u, it)
            self.choose_intent(u)

    def instant(self, u, it):
        """Действие врага без ожидания (вход в фазу): призыв, сила и щиты своим, сглаз."""
        k = it["kind"]
        if k == "summon":
            self.summon(u, it)
        elif k == "rally":
            self.rally(u, it)
        elif k == "guard":
            self.guard_allies(u, it)
        elif k == "hex":
            self.hero.ds["hex"] += it.get("n", 1)

    def summon(self, u, it):
        spots = [p for p in self.c.grid.in_radius(u.cell, 2) if self.free(p)]
        self.rng.shuffle(spots)
        for p in spots[:it.get("n", 1)]:
            d = self.edefs[it["unit"]]
            self.fx("portal", cell=p)
            v = self.c._spawn(ENEMY, d["sprite"], self.gd.enemies[d["sprite"]], p)
            self._setup(v, d, eid=it["unit"])
            self.choose_intent(v)
        self.say(f"{u.name}: {it['name']}", (200, 230, 140))

    def allies(self, u, r):
        return [a for a in self.foes() if cheb(a.cell, u.cell) <= r]

    def rally(self, u, it):
        for a in (self.allies(u, it.get("r", 3)) if it.get("r", 3) else [u]):
            a.ds["strength"] += it.get("n", 1)
            self.fx("status", unit=a, el="rally")
        self.say(f"{u.name}: {it['name']} — сила своим +{it.get('n', 1)}", (255, 180, 140))
        self.fx("roar", unit=u, r=max(1, it.get("r", 1)))

    def guard_allies(self, u, it):
        for a in self.allies(u, it.get("r", 2)):
            a.shield += it.get("n", 5)
            self.c.emit("shield", unit=a, amount=it.get("n", 5))
        self.say(f"{u.name}: {it['name']} — защита своим {it.get('n', 5)}", (200, 200, 230))

    def die(self, u, attacker=None):
        if u is self.hero and self.items.mod("revive") and not self.run.relic_state.get("revived"):
            self.run.relic_state["revived"] = True                  # предмет: раз за забег — встать
            u.hp = max(1, u.max_hp // 2)
            self.say(f"{u.name} поднимается! (предмет)", (255, 230, 150))
            self.fx("relic", unit=u, name="Второе дыхание")
            return
        u.hp = 0
        u.alive = False
        self.c.emit("death", unit=u, expire=False, rises=False)
        if u is self.hero:
            self.result = "defeat"
            self.say(f"{self.hero.name} пал(а)", (255, 120, 100))
            return
        if self.garden is not None:
            if getattr(u, "plant_id", None):
                self.garden.plant_destroyed(u)
                self.say(f"{u.name} уничтожено", (230, 160, 130))
                return
            if getattr(u, "wall_turns", None):
                self.garden.wall_died(u)
                return
            if self.garden.is_beast(u):
                self.garden.beast_died(u)
                self.say(f"{u.name} погиб", (230, 160, 130))
                return
        if u in self._ballistas:
            self.board_relics.ballista_destroyed(u, attacker)
            self._ballistas.remove(u)
            self.remove_ballista_commands(u)
            self.say("Баллиста разрушена. Карта установки снова доступна из сброса", (230, 160, 130))
            return
        if u.obj:
            self.say(f"{u.name} выбыла из боя", (230, 160, 130))
            return
        self.say(f"{u.name} повержен", (200, 230, 160))
        if u is self.prey and self.foes():                               # Метка добычи: дальше, +энергия, +карта
            self.energy += 1
            self.draw(1)
            self.mark_prey()
            self.say(f"Добыча пала: +1 энергия, +1 карта. Новая добыча — {self.prey.name}", (255, 220, 120))
        if hasattr(self.run, "kills"):
            self.run.kills += 1
        if u.ds.get("rot") and u.ds["poison"]:                  # Порча: яд — соседям
            for f in [f for f in self.foes() if cheb(f.cell, u.cell) <= 1]:
                self.add_poison(f, u.ds["poison"])
                self._icons(f)
            self.say("Порча расползается на соседей", (170, 220, 120))
        od = (u.edef or {}).get("on_death") or {}
        for c in getattr(u, "stolen", []):                     # украденные карты — обратно в руку
            if not self.ballista_locked(c) and (len(self.hand) < HAND_MAX or self.merge_partner(c) is not None):
                self.receive_card(c)
            else:
                self.discard.append(c)
            self.say(f"«{c.name}» вернулась", (170, 255, 170))
        u.stolen = []
        if od.get("avenge"):                                   # мститель: соседи звереют
            for f in [f for f in self.foes() if cheb(f.cell, u.cell) <= 2]:
                f.ds["strength"] += od["avenge"]
                self.fx("status", unit=f, el="rally")
            self.say(f"Смерть {u.name}: остальные звереют (+{od['avenge']} силы)", (255, 150, 110))
        if od.get("curse") and "slime_rot" in self.run.defs:
            for _ in range(od["curse"]):
                self.discard.append(M.Card("slime_rot", self.run.defs))
            self.say(f"{u.name}: «Тина» в сброс ×{od['curse']}", (190, 220, 140))
        if od.get("rise") and not getattr(u, "risen", False):   # эволюция: встаёт в другой форме
            d = self.edefs[od["rise"]]
            v = self.c._spawn(ENEMY, d["sprite"], self.gd.enemies[d["sprite"]], u.cell)
            self._setup(v, d, eid=od["rise"])
            v.risen = True
            self.choose_intent(v)
            self.fx("portal", cell=u.cell)
            self.say(f"{u.name} восстаёт: {d['name']}!", (230, 180, 255))
        if od.get("split"):                                  # слизень распадается
            spots = [p for p in self.c.grid.in_radius(u.cell, 1) if self.free(p)]
            for p in spots[:od.get("n", 2)]:
                d = self.edefs[od["split"]]
                v = self.c._spawn(ENEMY, d["sprite"], self.gd.enemies[d["sprite"]], p)
                self._setup(v, d, eid=od["split"])
                self.choose_intent(v)
            self.say("Слизень распался!", (190, 230, 140))
        if od.get("fire_cell"):
            self.set_surface(u.cell, "fire")
        ex = od.get("explode")
        if ex:                                               # взрыв при смерти: урон, яд, лужи
            r = ex.get("r", 1)
            self.fx("react", unit=u, what="flare" if ex.get("dmg") else "steam")
            for x in [x for x in self.c.units if x.alive and not x.obj and x is not u and cheb(x.cell, u.cell) <= r]:
                if ex.get("dmg"):
                    self.hurt(x, ex["dmg"], None, "spell")
                if ex.get("poison") and x.alive:
                    self.add_poison(x, ex["poison"])
            if ex.get("hazard") == "poison":
                for p in self.c.grid.in_radius(u.cell, r):
                    cell = self.c.grid.get(p)
                    if cell is not None and cell.passable:
                        cell.hazard, cell.hazard_time = "poison", -1.0
            self.say(f"{u.name} лопается!", (210, 230, 140))
        if od.get("hex"):
            self.hero.ds["hex"] += od["hex"]
            self.say(f"{u.name}: сглаз — на ход меньше {od['hex']} карт", (200, 160, 255))
        if len(self.foes()) == 1 and u.team == ENEMY:
            self.queue.append(("last_foe", self.foes()[0]))
        if not self.foes():
            self.run_relics.observe_victory()
            self.result = "victory"

    def mark_prey(self):
        foes = self.foes()
        self.prey = min(foes, key=lambda f: (cheb(f.cell, self.hero.cell), f.hp)) if foes else None

    def push(self, src, tgt, n, toward=False, d=None, card=None):
        """Толчок (или притягивание): по клетке; упёрся — столкновение, урон обоим (стена — только цели).
        По льду и маслу цель скользит дальше (до 3 клеток сверх). d — направление сразу (ветер)."""
        if not tgt.alive or tgt.obj:
            return
        board = self.board_relics
        if tgt is self.hero and board.anchor and n > 0:
            board.anchor = False
            return
        tagged = src is self.hero and card is not None and "push" in card.tag_ids
        if d is None:
            d = (sign(src.cell[0] - tgt.cell[0]), sign(src.cell[1] - tgt.cell[1])) if toward else \
                (sign(tgt.cell[0] - src.cell[0]), sign(tgt.cell[1] - src.cell[1]))
        if d == (0, 0):
            return
        slid = 0
        oil_slide = False
        k = 0
        while k < n:
            k += 1
            nxt = (tgt.cell[0] + d[0], tgt.cell[1] + d[1])
            if toward and nxt == src.cell:
                return
            cell = self.c.grid.get(nxt)
            if cell is not None and cell.terrain == "chasm" and tgt is self.hero:   # герой цепляется за край
                self.say(f"{tgt.name} едва удержался на краю пропасти: −5", (255, 200, 120))
                self.hurt(tgt, 5, None, "collision")
                return
            if cell is not None and cell.terrain == "chasm":
                if tagged:
                    turn = yield from board.edge_direction(tgt, d)
                    if turn is not None:
                        self.c._place(tgt, turn, STEP_T)
                        yield WAIT
                        self._enter(tgt, turn)
                        return
                self.say(f"{tgt.name} падает в пропасть!", (255, 200, 120))
                self.hurt(tgt, 15 if (tgt.edef or {}).get("elite") else 999, src, "collision")
                return
            if not self.free(nxt, exclude=tgt):
                left = n - k + 1
                dmg = COLLIDE * left * self.collide_k + (2 if self.variant == "press" and src is self.hero
                                                          and tgt is not self.hero else 0)
                other = next((v for v in self.c.units if v.alive and v.cell == nxt and v is not tgt), None)
                self.c.emit("collision", unit=tgt, amount=dmg)
                self.say(f"Столкновение: {tgt.name} −{dmg}" + (f", {other.name} −{dmg}" if other else ""),
                         (255, 210, 140))
                self.hurt(tgt, dmg, src, "collision")
                if other is not None and not other.obj:
                    self.hurt(other, dmg, src, "collision")
                if tgt.team == ENEMY:
                    board.break_pedestal(nxt)
                return
            self.c._place(tgt, nxt, STEP_T)
            yield ("wait", 0.0)
            self._enter(tgt, nxt)
            if tgt.team == ENEMY and tgt.alive and board.enter_enemy(tgt, nxt):
                return
            if k == n and slid < 3 and not toward and self.slippery(nxt) and tgt.alive:   # скользит дальше
                oil_slide = oil_slide or cell.hazard == "oil"
                next_cell = (nxt[0] + d[0], nxt[1] + d[1])
                last_slide = slid == 2 or not self.slippery(next_cell) or not self.free(next_cell, exclude=tgt)
                if tagged and oil_slide and last_slide:
                    turn = yield from board.oil_direction(tgt, d)
                    if turn is not None:
                        self.c._place(tgt, turn, STEP_T)
                        yield WAIT
                        self._enter(tgt, turn)
                        return
                n += 1
                slid += 1
                if slid == 1:
                    self.say(f"{tgt.name} скользит", (180, 220, 255))

    # ---------- ход игрока ----------

    def start_player_turn_now(self):
        finish(self.start_player_turn())

    def start_player_turn(self):
        self.lead_discounts.clear()
        self.turn += 1
        self.board_relics.turn_start()
        self.retained_card_discounts = {uid: discount for uid, discount in self.retained_card_discounts.items()
                                        if discount[0] >= self.turn}
        for unit in self.c.units:
            buffs = getattr(unit, "ds", {}).get("card_damage_buffs", {})
            for key in tuple(buffs):
                if key[0] < self.turn:
                    del buffs[key]
        self.stance_uses.clear()
        for ballista in self.ballistas:
            if not ballista.ds.pop("skip_passive_charge", False):
                ballista.charge = min(ballista.charge_max, ballista.charge + 1)
            ballista.ds.pop("shot_empower", None)
        h = self.hero
        for u in self.foes():
            if self.board_relics.delayed.get(u) != self.turn - 1:
                self.choose_intent(u)
        h.shield = h.shield // 2 if h.ds.get("fort") else 0          # «Оборона»: половина защиты остаётся
        h.ds["fort"] = 0
        self.collide_k = 1
        self.discard += self.used                            # остатки Used (отклики врага) — в сброс
        self.used = []
        self.played = 0
        self.turn_tags, self.walked, self.echoed = [], 0, set()
        self.chain_drawn = 0
        for c in self.guard:                                             # ждали ход врага и не сработали — в сброс
            if c in self.hand:
                self.hand.remove(c)
                self.place_discarded_card(c)
                self.queue_card_event("discarded", c)
        self.guard = []
        self.items.new_turn()
        self.energy = self.max_energy + h.ds["rage"] + self.next_energy
        if self.mech == "heat":                                          # жар: +1 за ход (и от Сердца феникса)
            hd = self.hero_def
            h.ds["heat"] = min(hd.get("heat_max", 12), h.ds["heat"] + hd.get("heat_turn", 1) + h.ds["heat_regen"] +
                               self.items.mod("energy") + self.next_energy + h.ds.pop("next_heat", 0))
        if h.ds["rage"]:
            self.hurt(h, 2 * h.ds["rage"], None, "hp_cost")
            self.say(f"Боевой раж: +{h.ds['rage']} энергии, −{2 * h.ds['rage']} HP", (255, 150, 120))
        yield from self.tick_start(h)
        if self.result:
            return
        hx = h.ds["hex"]
        if hx:
            self.say(f"Сглаз: на {hx} карт меньше", (200, 160, 255))
            h.ds["hex"] = 0
        self.hand_relics.before_draw(PRIEST_HAND if self.idols is not None else HAND_MAX)
        if self.idols is not None:                            # Жрец: 3 в начале боя, дальше +2 (рука до 5)
            self.idols.start_turn()
            pinned = any(cheb(f.cell, h.cell) <= 1 for f in self.foes())      # «Скован»: враг вплотную — шаг 1
            self.walk_left = 0 if h.ds.get("iced") else 1 if pinned else self.walk_max + self.idols.walk_bonus
            if pinned and not h.ds.get("iced"):
                self.say("Жрец скован: враг вплотную — только 1 шаг", (220, 170, 150))
            h.ds["iced"] = 0
            self.draw(max(1, (3 if self.turn == 1 else 2) + self.idols.extra_draw - hx + self.items.mod("energy") +
                          self.next_draw + self.next_energy))
            self.idols.extra_draw = 0
        else:
            self.draw(max(1, self.hand_size - hx + self.items.mod("hand") + self.next_draw))
        self.next_energy = self.next_draw = 0
        yield from self.items.fire("turn")
        yield from self.react()
        self.env_plan()
        yield from self.power_fire("turn")
        if self.garden is not None:
            self.garden.turn_start()
        if self.mech == "hunter" and self.variant == "quiver":           # Колчан: стрела в руку
            self.add_tokens("arrow", 1)
        yield from self.react_card_events()
        self.lead_discounts = {c.uid for c in self.hand if "lead" in M.card_rules(c.d) and self.rng.random() < 0.5}
        if self.garden is not None:
            self.garden.force_lead()
        yield from self.hand_relics.turn_start()
        self.sync_levels()
        if self.garden is not None:
            yield from self.garden.flush_assemblies()

    def draw(self, n):
        for _ in range(n):
            if not self.draw_pile:
                drawable = [c for c in self.discard if not self.ballista_locked(c)]
                drawable.extend(self.run_relics.release_held())
                if not drawable:
                    return
                self.draw_pile = drawable
                self.discard = [c for c in self.discard if self.ballista_locked(c)]
                self.rng.shuffle(self.draw_pile)
                self.queue.append(("shuffle", None))
            if (len(self.hand) >= (PRIEST_HAND if self.idols is not None else HAND_MAX)
                    and self.merge_partner(self.draw_pile[-1]) is None):
                return
            c = self.draw_pile.pop()
            if self.limits_unique_hand(c) and self.has_unique():  # Единственная: вторая — под низ колоды
                self.draw_pile.insert(0, c)
                if all(self.limits_unique_hand(x) for x in self.draw_pile):
                    return
                continue
            c.manual = False
            self.receive_card(c)

    def merge_partner(self, card):
        if card not in self.hand_relics.fleeting and "merge" in M.card_rules(card.d) and card.rank < len(M.card_ranks(card.base)):
            return next((held for held in self.hand
                         if held is not card and held.cid == card.cid and held.rank == card.rank
                         and held not in self.hand_relics.fleeting
                         and held.uid not in self.hand_relics.deferred_merge
                         and "merge" in M.card_rules(held.d)), None)
        return None

    def receive_card(self, card, *, relic_offer=True):
        if relic_offer and self.hand_relics.defer_merge(card, PRIEST_HAND if self.idols is not None else HAND_MAX):
            return
        while (partner := self.merge_partner(card)) is not None:
            self.hand.remove(partner)
            for merged in (card, partner):
                self.items.retention.pop(merged.uid, None)
                self.retained_card_discounts.pop(merged.uid, None)
            bonus = max(self.temper.get(card.uid, 0), self.temper.pop(partner.uid, 0))
            if bonus:
                self.temper[card.uid] = bonus
            card.rank += 1
            self.say(f"{card.name}: слияние", (255, 190, 110))
            self.queue_card_event("merged", card)
        self.hand.append(card)
        self.queue_card_event("entered_hand", card)
        if self.garden is not None:
            self.garden.check_assembly()

    def queue_card_event(self, event, card):
        ops = self.card_event_ops(event, card)
        if ops:
            self.queue.append(("card_event", (card, ops)))

    def card_event(self, event, card, target=None):
        yield from self.apply(self.hero, self.card_event_ops(event, card), target, {"card": card})

    @staticmethod
    def card_event_ops(event, card):
        ops = M.card_reactions(card.d, event)
        if event != "discarded":
            return ops
        rules = M.card_rules(card.d)
        if "quietus" in rules:
            ops += M.card_reactions(card.d, "quietus")
        if "blessing" in rules:
            ops += ({"op": "discard_blessing"},)
        return ops

    def place_discarded_card(self, card):
        self.hand_relics.untouched.discard(card.uid)
        if self.garden is not None:
            self.garden.drop_attachment(card)
        pile = self.used if "quietus" in M.card_rules(card.d) else self.discard
        pile.append(card)

    def linked_play(self, card):
        if "linked" not in M.card_rules(card.d):
            return
        if card.d.get("pair"):                     # эльфийская Связь: партнёры остаются в руке
            card.linked_spent = True
            return
        card.linked_spent = True
        others = [held for held in self.hand if "linked" in M.card_rules(held.d)]
        for held in others:
            held.linked_spent = True
            self.hand.remove(held)
            self.place_discarded_card(held)
        for held in others:
            yield from self.card_event("discarded", held)
        yield from self.hand_relics.link(others)

    def react_card_events(self):
        # Synchronous pile changes queue their reactions for the current battle job.
        while not self.result:
            pending = next((i for i, (kind, _) in enumerate(self.queue)
                            if kind in ("card_event", "relic_job")), None)
            if pending is None:
                return
            kind, event = self.queue.pop(pending)
            if kind == "relic_job":
                yield from event
            else:
                card, ops = event
                yield from self.apply(self.hero, ops, None, {"card": card})

    @staticmethod
    def limits_unique_hand(card):
        return "unique" in M.card_rules(card.d) and not card.d.get("deck_unique") and not getattr(card, "copied", False)

    def has_unique(self):
        return any(self.limits_unique_hand(c) for c in self.hand)

    def has_mod(self, mod):
        """Сила с постоянным правилом («горение не спадает»…) — сыграна."""
        return any((c.d["main"].get("power") or {}).get("mod") == mod for c in self.powers)

    def mod_sum(self, mod):
        return sum((c.d["main"].get("power") or {}).get("n", 0) for c in self.powers
                   if (c.d["main"].get("power") or {}).get("mod") == mod)

    def tick_start(self, u):
        """Начало хода юнита: горение, яд и кровотечение, защита врага спадает."""
        ds = u.ds
        if ds["burn"]:
            self.fx("dot", unit=u, el="burn", n=ds["burn"])
            self.hurt(u, ds["burn"], None, "burn")
            if not (u.team == ENEMY and self.has_mod("burn_keep")):       # Вечный огонь: горение врагов не спадает
                ds["burn"] -= 1
            self._icons(u)
            yield ("wait", 0.4)
        if u.alive and ds["poison"]:
            self.fx("dot", unit=u, el="poison", n=ds["poison"])
            self.hurt(u, ds["poison"], None, "poison")
            ds["poison"] -= 1
            self._icons(u)
            yield ("wait", 0.4)
        if u.alive and ds["bleed"]:                                    # кровотечение: урон, затем вдвое меньше
            self.fx("dot", unit=u, el="bleed", n=ds["bleed"])
            self.hurt(u, ds["bleed"], None, "bleed")
            if not (u.team == ENEMY and self.has_mod("bleed_keep")):    # Открытые раны: кровотечение не тает
                ds["bleed"] //= 2
            self._icons(u)
            yield ("wait", 0.4)
        if u.alive and self.c.grid.get(u.cell).hazard == "fire" and not self.fireproof(u):
            self.add_burn(u, 2)
        if u.alive and self.c.grid.get(u.cell).hazard == "poison":
            self.add_poison(u, 2)
        self._icons(u)
        yield WAIT

    def tick_end(self, u):
        ds = u.ds
        for k in ("weak", "vulnerable", "wet", "root"):
            if ds[k]:
                ds[k] -= 1
        ds["thorns"] = 0
        self._icons(u)

    # ---------- цели карт ----------

    def add_tokens(self, cid, n, force=False, *, heat_payment=False):
        """Создать карту: временные карты в руку (после розыгрыша — Изгнание)."""
        if self.run.defs.get(cid, {}).get("deck_unique"):
            return
        for _ in range(n):
            c = M.Card(cid, self.run.defs)
            if force or len(self.hand) < HAND_MAX or self.merge_partner(c) is not None:
                if self.limits_unique_hand(c) and self.has_unique():
                    continue
                c.manual = False
                c.heat_payment = heat_payment and not c.levels and (c.cost > 0 or bool(c.d.get("x_cost")))
                self.receive_card(c)
                self.fx("created", unit=self.hero, uid=c.uid)
                self.queue.append(("create", c))

    def spread_positions(self, size, count):
        """Случайные позиции вставки, разнесённые по полосам стопки."""
        if count <= 0:
            return []
        if count == 1:
            return [self.rng.randint(0, size)]
        out = []
        for i in range(count):
            lo = round(i * (size + 1) / count)
            hi = round((i + 1) * (size + 1) / count) - 1
            out.append(self.rng.randint(lo, max(lo, hi)))
        return out

    def scatter_parts(self, cards):
        """Разложить части оружия по добору и сбросу; вернуть [(карта, "draw"/"discard")]."""
        cards = list(cards)
        if not cards:
            return []
        self.rng.shuffle(cards)
        n = len(cards)
        if n == 1:
            groups = [("draw" if self.rng.random() < 0.5 else "discard", cards)]
        else:
            to_draw = n // 2
            if n % 2:
                to_draw += self.rng.choice((0, 1))
            to_draw = max(1, min(n - 1, to_draw))
            groups = [("draw", cards[:to_draw]), ("discard", cards[to_draw:])]
        out = []
        for dest, group in groups:
            pile = self.draw_pile if dest == "draw" else self.discard
            slots = sorted(self.spread_positions(len(pile), len(group)), reverse=True)
            for pos, card in zip(slots, group):
                pile.insert(pos, card)
                out.append((card, dest))
        return out

    def copy_hand_card(self, source):
        clone = M.Card(source.cid, {source.cid: source.base}, uses=source.uses, picks=source.picks)
        clone.divine = source.divine
        clone.alt_up = copy.deepcopy(source.alt_up)
        clone.lvl = source.lvl
        clone.rank = source.rank
        clone.heat_payment = source.heat_payment
        clone.linked_spent = source.linked_spent
        clone.manual = getattr(source, "manual", False)
        clone.copied = True
        owner = getattr(source, "ballista_owner", None)
        if owner is not None:
            clone.ballista_owner = owner
        if source.uid in self.temper:
            self.temper[clone.uid] = self.temper[source.uid]
        self.receive_card(clone)
        self.fx("created", unit=self.hero, uid=clone.uid)
        self.queue.append(("create", clone))
        self.say(f"Слепок превращается в «{clone.name}»", (170, 225, 245))

    def pay_pool(self, card):
        """Чем платят за карту: жаром (карты с уровнями) или энергией."""
        return "heat" if card.uses_heat else "energy"

    def available_card_resource(self, card):
        return self.hero.ds["heat"] if self.pay_pool(card) == "heat" else self.energy

    def effective_cost(self, card, price=None, *, consume=False):
        price = card.cost if price is None else price
        if card.d.get("x_cost"):
            return price
        if card.uid in self.lead_discounts:
            price = max(0, price - 1)
        turn, discount = self.retained_card_discounts.get(card.uid, (None, 0))
        if turn == self.turn and price > 0:
            price = max(0, price - discount)
            if consume:
                del self.retained_card_discounts[card.uid]
        price -= self.items.retained_discount(card, price, consume=consume)
        return self.run_relics.price(card, price, consume)

    def can_afford(self, card):
        if self._free_cast:
            return True
        if card.d.get("x_cost"):
            return self.available_card_resource(card) >= 1
        return self.available_card_resource(card) >= self.effective_cost(card)

    def sync_levels(self):
        """Уровень карт с жаром: сам — высший, на который хватает (если игрок не выбрал колесом)."""
        heat = self.hero.ds["heat"]
        for c in self.hand:
            lv = c.levels
            if lv and not getattr(c, "manual", False):
                ok = [i for i, L in enumerate(lv) if self.effective_cost(c, L["heat"]) <= heat]
                c.lvl = ok[-1] if ok else 0

    def targets(self, card, mode, auto=False):
        """Куда можно сыграть: список юнитов или клеток (для self — [герой]). Пусто — нельзя."""
        if self.result or self.attacks_locked(card) or "unactivatable" in M.card_rules(card.d):
            return []
        if card.d.get("auto_end") and not auto:               # авто-стрела не играется вручную
            return []
        if mode == "main" and not self.can_afford(card):
            return []
        lim = self.items.mod("play_limit") if hasattr(self, "items") else 0
        if mode == "main" and lim and self.played >= lim and not card.d.get("token"):
            return []
        u = card.d[mode]
        if mode == "main" and u.get("seal") and not self.met(u["seal"]):     # Печать: сперва условие
            return []
        if u["target"] == "none" or (mode == "main" and card.d.get("react")):  # реакция / нет простого
            return []
        t = u["target"]
        h = self.hero
        if t == "ballista_place":
            return self.ballista_place_cells(u.get("range", 2), card)
        if t == "ballista_load":
            return self.ballista_load_targets(u.get("range", 2))
        if t == "ballista_fire":
            return list(dict.fromkeys(
                victim for unit in self.ballistas if unit.charge
                for _, victim in self.ballista_lines(u.get("range", 6), ballista=unit) if victim is not None))
        if t == "statue":                                 # свиток Жреца — на статую, где бог может исполнить смысл
            if self.idols is None:
                return []
            m = card.d["meaning"]                         # заглушённой статуе — только Движение (отогнать)
            return [s for s in self.idols.statues if (m == "move" or not self.idols.silenced(s))
                    and self.idols.can_cast(s, m)]
        if t == "self":
            return [h, *self.ballistas] if M.can_buff_ballista(u) else [h]
        if t == "copy_hand":
            return [c for c in self.hand if c is not card and c.cid != M.HAND_COPY_CARD]
        if t in ("hand_retain", "hand_other"):
            options = [c for c in self.hand if c is not card and (
                t == "hand_other" or "retain" in M.card_rules(c.d) or c.uid in self.temporary_retain)]
            return options if len(options) >= u.get("count", 1) else []
        if t == "hand_attach":
            options = [c for c in self.hand if c is not card and not c.d.get("token")
                       and not c.d.get("attach") and not (self.garden and self.garden.attached(c))]
            return options if len(options) >= u.get("count", 1) else []
        if t == "hand_link":
            options = [c for c in self.hand if c is not card and "linked" in M.card_rules(c.d)]
            return options if len(options) >= u.get("count", 1) else []
        if t == "plant":
            r = u.get("range", 4)
            return [p for p, cell in self.c.grid.cells.items()
                    if cell.passable and 0 < cheb(p, h.cell) <= r and self.free(p)]
        if t == "enemy":                                  # в тумане — только вплотную
            r = u.get("range", 1)
            out = [f for f in self.foes() if cheb(h.cell, f.cell) <= r and (r <= 1 or not u.get("los", r > 1)
                                                                            or self.los(h.cell, f.cell))
                    and not (f.ds.get("veil") and cheb(h.cell, f.cell) > 1)]
            if self.line_only(u):                         # только горизонталь/вертикаль
                out = [f for f in out if h.cell[0] == f.cell[0] or h.cell[1] == f.cell[1]]
            if mode == "main":
                out += self.board_relics.shot_targets(card, u, bresenham)
            return out
        if t == "reach":
            reach = self.paths(h, u.get("reach", 1))
            return [f for f in self.foes() if any(cheb(p, f.cell) <= 1 for p in reach)]
        if t == "cell_step":
            return [p for p in self.paths(h, self.move_value(u, "step")) if p != h.cell or u.get("allow_stay")]
        if t == "area":
            r = u.get("range", 5)
            return [p for p, c in self.c.grid.cells.items() if c.passable and cheb(p, h.cell) <= r
                    and self.los(h.cell, p)]
        if t == "cell_any":
            r = u.get("range", 4)
            return [p for p, c in self.c.grid.cells.items() if c.passable and 0 < cheb(p, h.cell) <= r
                    and self.free(p) and self.los(h.cell, p)]
        if t == "cell_dash":
            return list(self.dash_paths(self.move_value(u, "dash")))
        return []

    def move_value(self, u, key):
        """Дальность шага/рывка с феями, «Связью» и Оленем-проводником."""
        n = u.get(key, 1)
        fae = self.hero.ds.get("fae", 0)
        if u.get(key + "_fae"):
            n += fae // max(1, u[key + "_fae"])
        if u.get(key + "_linked") and any("linked" in M.card_rules(c.d) for c in self.hand):
            n += u[key + "_linked"]
        if self.garden is not None:
            n += self.garden.step_bonus
        thr = u.get(key + "_thr")
        if thr and fae >= thr.get("fae", 99):
            n = max(n, thr.get("n", n))
        return max(1, n)

    def line_only(self, u):
        return bool(u.get("line") or (u.get("line_fae") and self.hero.ds.get("fae", 0) >= u["line_fae"]))

    def effect_radius(self, u):
        r = u.get("radius", 1)
        rf = u.get("radius_fae")
        if rf and self.hero.ds.get("fae", 0) >= rf.get("fae", 99):
            r = max(r, rf.get("r", r))
        return r

    def radius_for_op(self, op):
        radius = op.get("r", 1)
        expanded = op.get("r_fae") or {}
        if self.hero.ds.get("fae", 0) >= expanded.get("fae", 99):
            radius = max(radius, expanded.get("r", radius))
        return radius

    def reach_spots(self, card, mode):
        """«Подойти и ударить»: куда можно встать (клетка в досягаемости, рядом враг) → [враги рядом].
        Игрок выбирает клетку сам — можно обойти врага сзади (больше разгона, толчок в нужную сторону)."""
        u = card.d[mode]
        if u["target"] != "reach" or not self.targets(card, mode):
            return {}
        out = {}
        for p in self.paths(self.hero, u.get("reach", 1)):
            near = [f for f in self.foes() if cheb(p, f.cell) <= 1]
            if near:
                out[p] = near
        return out

    @staticmethod
    def is_spot(target):
        """Цель «подойти и ударить» вида (клетка, враг)."""
        return isinstance(target, tuple) and len(target) == 2 and hasattr(target[1], "cell")

    def range_cells(self, card, mode):
        """Дальность применения — клетки, куда оно дотягивается, даже если целей там нет и не хватает цены:
        удар — клетки в радиусе (с обзором, если нужен), «подойти и ударить» — куда дойдёт + соседние, шаг —
        куда дойдёт, область и клетка — в дальности. Для подсветки, пока карту держат."""
        if self.attacks_locked(card):
            return []
        u = card.d[mode]
        t = u["target"]
        h = self.hero
        cells = self.c.grid.cells
        if t == "ballista_place":
            return self.ballista_place_cells(u.get("range", 2), card)
        if t == "ballista_load":
            return [target.cell for target in self.ballista_load_targets(u.get("range", 2))]
        if t == "ballista_fire":
            return list(dict.fromkeys(p for unit in self.ballistas
                                      for ray, _ in self.ballista_lines(u.get("range", 6), ballista=unit) for p in ray))
        if t == "enemy":
            r = u.get("range", 1)
            need = r > 1 and u.get("los", r > 1)
            out = [p for p, c in cells.items() if 0 < cheb(p, h.cell) <= r and c.passable
                   and (not need or self.los(h.cell, p))]
            if self.line_only(u):
                out = [p for p in out if p[0] == h.cell[0] or p[1] == h.cell[1]]
            return out
        if t == "reach":
            reach = self.paths(h, u.get("reach", 1))
            out = set(reach)
            for p in reach:
                out |= {q for q in self.c.grid.in_radius(p, 1) if q in cells and cells[q].passable}
            out.discard(h.cell)
            return sorted(out)
        if t == "cell_step":
            return [p for p in self.paths(h, self.move_value(u, "step")) if p != h.cell or u.get("allow_stay")]
        if t == "plant":
            r = u.get("range", 4)
            return [p for p, cell in cells.items() if cell.passable and 0 < cheb(p, h.cell) <= r and self.free(p)]
        if t in ("area", "cell_any"):
            r = u.get("range", 5)
            return [p for p, c in cells.items() if c.passable and 0 < cheb(p, h.cell) <= r and self.los(h.cell, p)]
        if t == "cell_dash":
            saved = self.energy, h.ds["heat"]
            self.energy, h.ds["heat"] = 99, 99
            try:
                return self.targets(card, mode)
            finally:
                self.energy, h.ds["heat"] = saved
        return []

    # ---------- условия карт (docs/descent_tags.md) ----------

    def met(self, c, tgt=None, before=None, ctx=None):
        """Выполнено ли условие c. tgt — цель (для условий по цели); before — сколько сыграно до этой карты
        (во время розыгрыша; иначе — сейчас). ctx — текущая карта (для «была скидка», «второе применение»)."""
        k = c["k"]
        h = self.hero
        played = self.played if before is None else before
        log = self.turn_tags[:played]
        if k == "linked_hand":
            return sum("linked" in M.card_rules(card.d) for card in self.hand) >= c.get("n", 1)
        if k == "had_lead":
            return bool(ctx and ctx.get("had_lead"))
        if k == "fae_before":
            return (ctx.get("fae_before", h.ds.get("fae", 0)) if ctx else h.ds.get("fae", 0)) >= c["n"]
        if k == "second_fae":
            card = (ctx or {}).get("card")
            return h.ds.get("fae", 0) >= c["n"] and card is not None and card.uses >= 2
        if k == "series":
            return played >= c["n"]
        if k == "after":
            return bool(log) and M.tag_id(c["tag"]) in log[-1]
        if k == "resonance":
            tag = M.tag_id(c["tag"])
            return sum(tag in t for t in log) >= c["n"]
        if k == "first":
            return played == 0
        if k == "allin":
            return (h.ds["heat"] if self.mech == "heat" else self.energy) == 0
        if k == "run":
            return self.walked >= c["n"]
        if k == "not_walked":
            return self.walked == 0
        if k == "momentum":
            return (self._mom if self._mom is not None else h.ds["momentum"]) >= c["n"]
        if k in ("fae", "fae_min"):
            return h.ds.get("fae", 0) >= c["n"]
        if k == "shielded":
            return h.shield >= c["n"]
        if k == "hurt":
            return h.hp * 2 < h.max_hp
        if k == "duel":
            return sum(1 for f in self.foes() if cheb(f.cell, h.cell) <= 1) == 1
        if k == "back_wall":
            for dx, dy in DIRS8:
                cell = self.c.grid.get((h.cell[0] + dx, h.cell[1] + dy))
                if cell is None or not cell.passable:
                    return True
            return False
        if k == "surrounded":
            return sum(1 for f in self.foes() if cheb(f.cell, h.cell) <= 1) >= 2
        if k == "cover":
            for p in self.c.grid.in_radius(h.cell, 1):
                cell = self.c.grid.get(p)
                if p != h.cell and cell is not None and (not cell.passable or cell.cover):
                    return True
            return False
        if tgt is None or not hasattr(tgt, "cell"):
            return False
        if k == "adjacent":
            return cheb(h.cell, tgt.cell) <= 1
        if k == "far":
            return cheb(h.cell, tgt.cell) >= c["n"]
        if k == "wall":
            d = (sign(tgt.cell[0] - h.cell[0]), sign(tgt.cell[1] - h.cell[1]))
            nxt = (tgt.cell[0] + d[0], tgt.cell[1] + d[1])
            return d != (0, 0) and not self.free(nxt, exclude=tgt)
        if k in ("burning", "wet", "poisoned", "marked"):
            return bool(tgt.ds[{"burning": "burn", "poisoned": "poison", "marked": "mark"}.get(k, k)])
        if k == "wounded":
            return tgt.hp * 2 < tgt.max_hp
        if k == "stunned":
            return bool(tgt.ds["stun"])
        if k == "weakened":
            return bool(tgt.ds["weak"])
        if k == "vulnerable":
            return bool(tgt.ds["vulnerable"])
        if k == "bleeding":
            return bool(tgt.ds["bleed"])
        if k == "guarded":
            return tgt.shield > 0
        return False

    def lit(self, card):
        """Какие условия карты сейчас выполнены (для подсветки в руке): "seal", ("if", i), "echo", "keep".
        Условие по цели — если подходит хоть одна доступная цель."""
        d = card.d
        u = d["main"]
        out = set()
        if u.get("seal") and self.met(u["seal"]):
            out.add("seal")
        conds = u.get("if", [])
        if conds:
            saved = self.energy, self.hero.ds["heat"]
            self.energy, self.hero.ds["heat"] = 99, 99
            try:
                ts = [t for t in self.targets(card, "main") if hasattr(t, "cell") and t is not self.hero]
            finally:
                self.energy, self.hero.ds["heat"] = saved
            ts = ts or self.foes()
            for i, c in enumerate(conds):
                w = c["when"]
                if (w["k"] in M.TARGET_CONDS and any(self.met(w, t) for t in ts)) or \
                        (w["k"] not in M.TARGET_CONDS and self.met(w)):
                    out.add(("if", i))
        if d.get("chain") and self.met(d["chain"]["when"]):
            out.add("chain")
        e = d.get("echo")
        if e and e.get("when") and (e.get("on") is None) and self.met(e["when"]):
            out.add("echo")
        tp = d.get("temper")
        if tp and tp.get("when") and tp["when"]["k"] not in M.TARGET_CONDS and self.met(tp["when"]):
            out.add("temper")
        if d.get("keep") and self.met(d["keep"]):
            out.add("keep")
        return frozenset(out)

    def echoes(self):
        """Отклик/Цепочка по условию хода: карты в руке, чьё условие выполнено, срабатывают сами (раз за ход)."""
        yield from self.chains()
        for c in list(self.hand):
            e = c.d.get("echo")
            if not e or e.get("on") or c.uid in self.echoed or self.result or not self.met(e["when"]):
                continue
            yield from self.fire_echo(c, None)

    def chains(self):
        """Цепочка: карта с этим тегом играется сама, когда выполнено её условие.
        После розыгрыша пересматриваем руку: добор мог принести следующую цепочку."""
        while not self.result:
            acted = False
            for c in list(self.hand):
                ch = c.d.get("chain")
                if not ch or c.uid in self.echoed or self.attacks_locked(c) or not self.met(ch["when"]):
                    continue
                choice = self.chain_needs_choice(c)
                if choice:
                    if not self.targets(c, "main"):
                        continue
                    target = None
                else:
                    target = self.chain_target(c)
                    if target is None:
                        continue
                self.echoed.add(c.uid)
                # Экран: показать карту крупно и дать игроку прочитать, что играет само.
                yield ("chain_card", 0.8, c)
                if choice:
                    # Не-атаку с выбором цели игрок ведёт сам: шаг, область, метка и т.п.
                    target = yield ("chain_choice", c, "main")
                    if target is None:                         # тесты/бот: запасной автовыбор
                        target = self.chain_target(c)
                    if target is None:
                        self.echoed.discard(c.uid)
                        continue
                self.say(f"Цепочка: {c.name}", (170, 255, 170))
                self.fx("chain", unit=self.hero, uid=c.uid, target=target)
                old = self._free_cast
                self._free_cast = True
                try:
                    yield from self.play(c, "main", target, free=True)
                    yield from self.items.fire("chain", card=c)
                    if self.mech == "hunter" and self.variant == "chain" and self.chain_drawn < 2:
                        self.chain_drawn += 1
                        self.draw(1)
                        self.say("Цепная реакция: карта", (180, 255, 190))
                finally:
                    self._free_cast = old
                if not self.result:
                    yield ("wait", 0.45)                      # пауза между цепочками
                acted = True
                break
            if not acted:
                return

    def chain_needs_choice(self, c):
        """Не-атака с целью пусть выбирает игрок: шаг, область, метка и т.п."""
        t = c.d["main"].get("target")
        return t not in ("self", "none", "statue") and not self.is_attack(c, "main")

    def chain_target(self, c):
        """Куда сама сыграет карта Цепочки: атака — лучшая цель, шаг — первая доступная клетка."""
        u = c.d["main"]
        t = u["target"]
        old = self._free_cast
        self._free_cast = True
        try:
            if t == "self":
                return self.hero
            if t in ("enemy", "area", "reach"):
                return self.auto_target(c, "main") or (self.targets(c, "main") or [None])[0]
            if t in ("cell_step", "cell_dash", "cell_any"):
                return (self.targets(c, "main") or [None])[0]
            if t == "copy_hand":
                return next(iter(self.targets(c, "main")), None)
            if t in ("hand_retain", "hand_other"):
                options = self.targets(c, "main")
                count = u.get("count", 1)
                return (tuple(options[:count]) if count > 1 else options[0]) if options else None
            return None
        finally:
            self._free_cast = old

    def react(self):
        """Отклик на события (убийство, получил удар, враг вплотную): разобрать очередь."""
        while self.queue and not self.result:
            kind, src = self.queue.pop(0)
            if kind == "relic_job":
                yield from src
                continue
            if kind == "card_event":
                card, ops = src
                yield from self.apply(self.hero, ops, None, {"card": card})
                continue
            if kind == "counter":
                yield from self.counter_strike(src)
                continue
            if kind == "retaliate":
                if src.alive and self.hero.alive and cheb(src.cell, self.hero.cell) <= 1:
                    self.say(f"{src.name} отвечает ударом", (255, 170, 140))
                    yield from self.strike(src, self.hero, src.edef["retaliate"])
                continue
            if kind == "create":
                yield from self.items.fire("create", card=src)
                continue
            if kind in ("shuffle", "hp_low", "last_foe", "trap", "desecrated"):
                yield from self.items.fire(kind, src=src)
                continue
            if kind == "kill" and not self.enemy_phase:
                self.items.kills_turn += 1
            if kind in ("kill", "hit"):
                yield from self.items.fire(kind, src=src)
                yield from self.power_fire(kind, src=src)
            for c in list(self.hand):
                e = c.d.get("echo")
                if not e or e.get("on") != kind or c.uid in self.echoed or self.result:
                    continue
                if e.get("when") and not self.met(e["when"], src if src is not None and src.alive else None):
                    continue
                yield from self.fire_echo(c, src)

    def counter_strike(self, src):
        """Контратака: враг ударил вплотную — ответный удар (4 + Мощь), стак тратится."""
        h = self.hero
        if not h.alive or src is None or not src.alive or h.ds["counter"] <= 0 or cheb(src.cell, h.cell) > 1:
            return
        h.ds["counter"] -= 1
        self.say(f"Контратака: {h.name} отвечает — {src.name}", (255, 210, 150))
        self.fx("counter", unit=h, target=src)
        yield from self.strike(h, src, COUNTER + self.mod_sum("counter_plus"))
        if src.alive and self.has_mod("counter_bleed"):
            src.ds["bleed"] += 2
        self._icons(h)
        yield from self.items.fire("counter", src=src)

    def power_fire(self, ev, card=None, src=None):
        """Силы до конца боя: событие ev (turn, play, step, kill, hit, exhaust, end) — их действия."""
        h = self.hero
        for pc in list(self.powers):
            pw = pc.d["main"].get("power") or {}
            if pw.get("on") != ev or self.result:
                continue
            if pw.get("tag") and (card is None or M.tag_id(pw["tag"]) not in card.tag_ids):
                continue
            if pw.get("once"):
                key = (pc.uid, self.turn, ev)
                if key in self.powered:
                    continue
                self.powered.add(key)
            aim = pw.get("aim", "self")
            tgts = [None]
            foes = self.foes()
            if aim == "nearest":
                if not foes:
                    continue
                tgts = [min(foes, key=lambda f: (cheb(f.cell, h.cell), f.hp))]
            elif aim == "source":
                if src is None or not src.alive or src.team != ENEMY:
                    continue
                tgts = [src]
            elif aim == "adjacent":
                tgts = [f for f in foes if cheb(f.cell, h.cell) <= 1]
            elif aim == "all":
                tgts = foes
            if not tgts:
                continue
            self.fx("power", unit=h, uid=pc.uid, name=pc.name)
            buff_target = self.ballista_power_targets.get(pc.uid)
            for t in tgts:
                yield from self.apply(h, pw.get("do", []), t, {"before": self.played, "buff_target": buff_target})

    def exhaust_card(self, card):
        """Изгнание: карта уходит до конца боя (не временная — будит Силы «при изгнании»)."""
        if self.garden is not None:
            self.garden.drop_attachment(card)
        self.exhaust.append(card)
        self.run_relics.observe_exhaust(card)
        yield from self.card_event("exhausted", card)
        if not card.d.get("token"):
            self.fx("exhaust", unit=self.hero, uid=card.uid)
            yield from self.power_fire("exhaust", card=card)
            yield from self.items.fire("exhaust", card=card)

    def per_count(self, per, tgt, ctx):
        """«За каждую…»: сколько раз прибавить шаг масштабирования."""
        if per.get("div"):
            return self.per_count({k: v for k, v in per.items() if k != "div"}, tgt, ctx) // max(1, per["div"])
        h = self.hero
        w = per["what"]
        before = ctx.get("before")
        before = self.played if before is None else before
        if w == "played":
            return before
        if w.startswith("tag:"):
            tag = M.tag_id(w[4:])
            return sum(tag in t for t in self.turn_tags[:before])
        if w == "strength":
            return max(0, h.ds["strength"])
        if w in ("bleed", "burn", "poison", "mark", "vulnerable", "weak"):
            return tgt.ds[w] if tgt is not None and hasattr(tgt, "ds") else 0
        if w == "exhausted":
            return sum(1 for c in self.exhaust if not c.d.get("token"))
        if w == "hand":
            return len(self.hand)
        if w == "counter":
            return h.ds["counter"]
        if w == "shield":
            return h.shield
        if w == "heat":
            return h.ds["heat"]
        if w == "hunt":
            return h.ds.get("hunt", 0)
        if w == "fae":
            return h.ds.get("fae", 0)
        if w == "walked":
            return self.walked
        if w in ("foes_burning", "foes_bleeding"):
            k = {"foes_burning": "burn", "foes_bleeding": "bleed"}[w]
            return sum(1 for f in self.foes() if f.ds[k])
        if w == "foes":
            return len(self.foes())
        if w == "powers":
            return len(self.powers)
        return 0

    def fire_echo(self, c, src):
        """Карта срабатывает сама: бесплатно, раз за ход; реакция после этого — в сброс, остальные остаются."""
        if self.attacks_locked(c):
            return
        e = c.d["echo"]
        h = self.hero
        aim = e.get("aim", "nearest")
        tgt = None
        if aim == "source" and src is not None and src.alive and src.team == ENEMY:
            tgt = src
        elif aim in ("nearest", "source"):
            foes = [f for f in self.foes() if cheb(f.cell, h.cell) <= e.get("range", 99)]
            if not foes:
                return
            tgt = min(foes, key=lambda f: (cheb(f.cell, h.cell), f.hp))
        self.echoed.add(c.uid)
        c.uses += 1                                         # отклик тоже копит прозрение
        self.try_insight(c)
        self.say(f"Отклик: {c.name}", (170, 255, 170))
        self.fx("echo", unit=h, uid=c.uid, target=tgt)
        if c.d.get("react") and c in self.hand:
            self.hand.remove(c)
            self.used.append(c)                               # отклик — тоже использование карты
        if e.get("vfx"):
            self.vfx(h, e["vfx"], c.name, target=tgt)
            yield IMPACT
        yield from self.apply(h, e["do"], tgt, {"vfx": bool(e.get("vfx")), "temper": self.temper.get(c.uid, 0)})

    def line_enemies(self, target, rng):
        """Враги на горизонтальной/вертикальной линии от героя до цели (и дальше в том же направлении)."""
        h = self.hero
        dx = sign(target.cell[0] - h.cell[0])
        dy = sign(target.cell[1] - h.cell[1])
        if dx and dy:                                      # диагональ не считается «по прямой»
            return [target]
        out = []
        p = h.cell
        blockers = {u.cell for u in self.ballistas}
        for _ in range(max(1, rng)):
            p = (p[0] + dx, p[1] + dy)
            cell = self.c.grid.get(p)
            if cell is None or not cell.passable or p in blockers:
                break
            f = next((u for u in self.foes() if u.cell == p), None)
            if f is not None:
                out.append(f)
        return out

    def is_attack(self, card, mode):
        """Сторона карты бьёт врага (для автоприменения): цель — враг, подход или область, и есть урон."""
        u = card.d[mode]
        if u["target"] not in ("enemy", "reach", "area"):
            return False
        ops = [o["op"] for o in u.get("do", [])] + [x["op"] for o in u.get("do", []) for x in o.get("do", [])]
        return bool({"damage", "body_slam"} & set(ops))

    def auto_target(self, card, mode, auto=False):
        """Куда ударит атака, если её просто разыграли: ближайший враг в досягаемости (при равенстве — слабее);
        область — туда, где заденет больше врагов (при равенстве — ближе). Не атака / некого — None."""
        if not self.is_attack(card, mode):
            return None
        ts = self.targets(card, mode, auto=auto)
        if not ts:
            return None
        h = self.hero
        if card.d[mode]["target"] == "area":
            r = card.d[mode].get("radius", 1)
            hits = lambda p: sum(1 for f in self.foes() if cheb(f.cell, p) <= r)        # noqa: E731
            best = max(ts, key=lambda p: (hits(p), -cheb(p, h.cell)))
            return best if hits(best) else None
        return min(ts, key=lambda f: (cheb(f.cell, h.cell), f.hp))

    def can_play(self, card, mode):
        return bool(self.targets(card, mode))

    def play(self, card, mode, target, free=False, auto=False):
        relics = self.run_relics
        previous, relics.active_card = relics.active_card, card if mode == "main" else None
        try:
            yield from self._play(card, mode, target, free=free, auto=auto)
        finally:
            relics.active_card = previous

    def _play(self, card, mode, target, free=False, auto=False):
        """Сыграть карту из руки: mode "main" (энергия, копит прозрение) или "alt" (бесплатно).
        free — Цепочка: полный розыгрыш без оплаты; auto — автоматическая карта в конце хода."""
        rules = M.card_rules(card.d)
        if card not in self.hand or self.attacks_locked(card) or "unactivatable" in rules:
            return
        if card.d.get("auto_end") and not auto:
            return
        if card.d[mode].get("target") == "statue":            # свиток Жреца: через статую бога
            yield from self.play_scroll(card, target, manual=not free and not auto)
            return
        shooter = None
        if card.d[mode].get("target") == "ballista_fire":
            explicit = isinstance(target, BallistaShot)
            if explicit:
                shooter, target = target.ballista, target.victim
            shooters = self.ballista_shooters(target, card.d[mode].get("range", 6))
            if not shooters or (explicit and shooter not in shooters):
                return
            if not explicit:
                shooter = shooters[0]
        hand_targets = ()
        if card.d[mode]["target"] in ("hand_retain", "hand_other", "hand_attach", "hand_link"):
            hand_targets = target if isinstance(target, tuple) else (target,)
            options = self.targets(card, mode, auto=auto)
            if (len(hand_targets) != card.d[mode].get("count", 1)
                    or any(c not in options for c in hand_targets)
                    or len(set(hand_targets)) != len(hand_targets)):
                return
        elif self.is_spot(target):                            # подойти на выбранную клетку и ударить
            spot, foe = target
            if foe not in self.reach_spots(card, mode).get(spot, []):
                return
        elif target not in self.targets(card, mode, auto=auto):
            return
        u = card.d[mode]
        board = self.board_relics
        board.begin_play(card, mode)
        self.hand.remove(card)
        paid, mom0 = card.cost, self.hero.ds["momentum"]
        x_paid = 0
        if mode == "main":
            resource = self.pay_pool(card)
            self.run_relics.observe_play(card)
            if not free:
                if card.d.get("x_cost"):
                    x_paid = self.available_card_resource(card)
                    paid = x_paid
                else:
                    paid = self.effective_cost(card, consume=True)
                if resource == "heat":
                    self.hero.ds["heat"] -= paid
                else:
                    self.energy -= paid
            card.uses += 1
            self.try_insight(card)
            before = self.played
            self.played += 1
            self.say(f"{card.name}: {card.text('main')}", (255, 230, 160))
        else:
            self.say(f"{card.name} (просто): {card.text('alt')}", (200, 200, 180))
        had_lead = card.uid in self.lead_discounts
        self.hand_relics.lost_lead(card)
        self.lead_discounts.clear()
        self.hand_relics.played.add(card.uid)
        h = self.hero
        fae_spent, fae_rates = self.fae_empower_spec(card, u) if mode == "main" else (0, {})
        threshold = M.fae_threshold(u) if self.garden is not None and mode == "main" else None
        empowered = threshold is not None and h.ds.get("fae", 0) >= threshold
        origin = h.cell
        walked_before = self.walked
        previous_tags = self.turn_tags[-1] if self.turn_tags else ()
        armed_block = self.items.take_card_bonus(card, "block") if mode == "main" else 0
        t = u["target"]
        command_installation = getattr(card, "ballista_owner", None)
        if t == "reach":                                      # подойти к врагу — на выбранную клетку или ближе всего
            reach = self.paths(h, u.get("reach", 1))
            if self.is_spot(target):
                best, target = target
            else:
                best = min((p for p in reach if cheb(p, target.cell) <= 1), key=lambda p: len(reach[p]))
            yield from self.walk(h, reach[best])
        elif t == "cell_step":
            yield from self.walk(h, self.paths(h, self.move_value(u, "step"))[target])
        elif t == "cell_dash":
            yield from self.walk(h, self.dash_paths(self.move_value(u, "dash"))[target])
        elif t == "area" and mode == "main":
            target = yield from self.hand_relics.area_center(target, u)
        tgt = target if hasattr(target, "cell") and target is not h and t != "self" else None
        ctx = {"ranged": u.get("ranged", False), "center": target if isinstance(target, tuple) else None,
               "push_bonus": 0, "tag": u.get("tag"), "card": card if mode == "main" else None,
               "x": x_paid, "fae_before": h.ds.get("fae", 0), "had_lead": had_lead,
               "fae_spent": fae_spent, "fae_bonus": fae_rates, "elf_empowered": empowered}
        if t == "hand_attach" and hand_targets:
            ctx["attach_host"] = hand_targets[0]
        if t in ("ballista_place", "ballista_load", "ballista_fire"):
            ctx["range"] = u.get("range", 6 if t == "ballista_fire" else 2)
        if shooter is not None:
            ctx["ballista"] = shooter
        if t == "copy_hand":
            ctx["copy_target"] = target
        if hand_targets:
            ctx["hand_targets"] = hand_targets
        if t == "self" and target in self.ballistas:
            ctx["buff_target"] = target
        if mode == "main":
            conds = list(u.get("if", []))
            echo = card.d.get("echo") or {}
            if echo.get("when", {}).get("k") == "resonance":
                conds.append({"when": echo["when"], "repeat": 1})     # резонанс = повтор розыгрыша
            ctx["conds"], ctx["before"] = conds, before
            if any(c["when"].get("k") == "surrounded" for c in conds):
                ctx["surrounded"] = self.met({"k": "surrounded"})
            self._mom = h.ds["momentum"]
            ctx["emp"] = 0 if shooter is not None else self.card_damage_buff(h, card, consume=True)
            ctx["temper"] = self.temper.get(card.uid, 0)
        ops = u.get("do", [])
        redirected = False
        if mode == "main":
            if t == "area":
                yield from board.area(card, target, self.effect_radius(u))
            if shooter is None and tgt is not None and u.get("ranged"):
                if t == "enemy" and tgt in self.ballistas:
                    board.redirect_shot(tgt)
                    redirected = True
                else:
                    redirected = yield from board.intercept_shot(card, tgt, bresenham(h.cell, tgt.cell)[1:-1])
        elf_vfx = card.d.get("cast_vfx") if self.garden is not None and mode == "main" else None
        cast_vfx = u.get("vfx") or elf_vfx
        vfx_center = None if hand_targets else ctx["center"]
        vfx_radius = self.effect_radius(u) if t == "area" else 0
        if elf_vfx and t != "area":
            area_ops = [op for op in ops if op["op"] in ("aoe_radius", "fae_ring")]
            for condition in ctx.get("conds", ()):
                extra_areas = [op for op in condition.get("do", ()) if op["op"] in ("aoe_radius", "fae_ring")]
                if extra_areas and self.play_condition(condition["when"], tgt, ctx):
                    area_ops.extend(extra_areas)
            vfx_radius = max((self.radius_for_op(op) for op in area_ops), default=0)
        if cast_vfx and not redirected:
            ctx["vfx"] = True
            visual_target = ctx.get("buff_target") or tgt
            line = ()
            if elf_vfx and u.get("pierce") and tgt is not None and h.ds.get("fae", 0) >= u.get("line_fae", 0):
                line = self.line_enemies(tgt, u.get("range", 6))
                if line:
                    visual_target = line[-1]
            self.vfx(h, cast_vfx, card.name, target=visual_target, center=vfx_center,
                     radius=vfx_radius, tag=u.get("tag"), effect_only=bool(elf_vfx),
                     empowered=empowered, line=tuple(unit.cell for unit in line[:-1]))
            yield IMPACT                                      # ждём попадания — урон и HP в этот миг
            if u.get("shake"):
                self.fx("shake", unit=h, n=10)
        elif mode == "alt":                                   # простое — свой скромный эффект
            kinds = [o["op"] for o in ops]
            kind = ("step" if t in ("cell_step", "cell_dash") else "heat" if "heat" in kinds else
                    "block" if "block" in kinds else "push" if ("push" in kinds or "pull" in kinds) else
                    "mark" if "mark" in kinds else "card" if "add_card" in kinds else
                    "poison" if "poison" in kinds else "strike" if "damage" in kinds else "buff")
            self.fx("alt", what=kind, unit=h, target=tgt)
        reps = 1 + sum((1 if c["when"].get("k") == "resonance" else c.get("repeat", 0))
                       for c in ctx.get("conds", [])
                       if self.play_condition(c["when"], tgt, ctx)
                       and (c.get("repeat") or c["when"].get("k") == "resonance"))
        resonance = any(c["when"].get("k") == "resonance" and self.play_condition(c["when"], tgt, ctx)
                        for c in ctx.get("conds", []))
        combo = any(c["when"].get("k") in ("after", "series", "first", "allin")
                    and self.play_condition(c["when"], tgt, ctx) for c in ctx.get("conds", []))
        effect_target = tgt
        for rep in range(0 if redirected else reps):         # Близнец: дважды
            if rep == 1 and resonance and not self.result:
                effect_target = yield from self.hand_relics.resonance_target(card, tgt, u)
            if rep and (self.result or (effect_target is not None and not effect_target.alive)):
                break
            if rep and cast_vfx:                              # второй раз — снова эффект и попадание
                self.vfx(h, cast_vfx, card.name, target=effect_target, center=vfx_center,
                         radius=vfx_radius, tag=u.get("tag"), effect_only=bool(elf_vfx), empowered=empowered)
                yield IMPACT
            pierce = u.get("pierce")
            if pierce and u.get("line_fae") and self.hero.ds.get("fae", 0) < u["line_fae"]:
                pierce = False                                   # «Лунная стрела» пробивает только на пороге
            if pierce and effect_target is not None:             # линия: пробивает всех на пути
                for f in self.line_enemies(effect_target, u.get("range", 6)):
                    yield from self.apply(h, [o for o in ops if o["op"] not in ONCE], f, ctx)
                    yield from self.cond_extras(ctx, f, area=True)
                yield from self.apply(h, [o for o in ops if o["op"] in ONCE], None, ctx)
            elif t == "area":                                # область: каждому врагу в радиусе
                r = self.effect_radius(u)
                for f in [f for f in self.foes() if cheb(f.cell, target) <= r]:
                    yield from self.apply(h, [o for o in ops if o["op"] not in ONCE], f, ctx)
                    yield from self.cond_extras(ctx, f, area=True)
                yield from self.apply(h, [o for o in ops if o["op"] in ONCE], None, ctx)
                for c in ctx.get("conds", []):                       # «раз за область» части условий
                    extra = [o for o in c.get("do", []) if o["op"] in ONCE]
                    if extra and self.play_condition(c["when"], None, ctx):
                        yield from self.apply(h, extra, None, dict(ctx, conds=[]))
            else:
                yield from self.apply(h, ops, effect_target, ctx)
                yield from self.cond_extras(ctx, effect_target)
        board.playing_card = None
        if mode == "main":
            yield from board.after_movement(card)
            if not redirected:
                yield from self.hunt_followup(card, tgt)
                yield from board.around_attack(card, tgt)
            if self.garden is not None:
                yield from self.garden.after_card(card, tgt)
            board.last_tags = frozenset(card.tag_ids)
            if armed_block:
                self.gain_shield(h, armed_block)
        card.manual = False
        back = False
        if mode == "main":
            self.turn_tags.append(frozenset(card.tag_ids))
            self.items.turn_types.append(card.d.get("type"))
            if card.d.get("type") == "skill":                    # злится от умений героя
                for f in self.foes():
                    if (f.edef or {}).get("enrage"):
                        f.ds["strength"] += f.edef["enrage"]
                        self.fx("status", unit=f, el="rally")
                        self.say(f"{f.name} злится: +{f.edef['enrage']} силы", (255, 150, 110))
            if not u.get("power"):
                yield from self.power_fire("play", card=card)
            tp = card.d.get("temper")
            if tp and (not tp.get("when") or self.met(tp["when"], tgt, before)):
                self.temper[card.uid] = self.temper.get(card.uid, 0) + tp.get("n", 1)
            back = bool(u.get("back")) and self.met(u["back"], tgt, before)
            self._mom = None
            yield from self.echoes()
            yield from self.card_event("played", card, tgt)
            yield from self.react()
        else:
            yield from self.card_event("played", card, tgt)
        if not free and not auto:
            yield from self.linked_play(card)
        exhaust_limit = M.exhaust_limit(rules) if mode == "main" else None
        exhausted = False
        if exhaust_limit and exhaust_limit > 1:
            self.exhaust_plays[card.uid] = self.exhaust_plays.get(card.uid, 0) + 1
            exhausted = self.exhaust_plays[card.uid] >= exhaust_limit
        if t == "ballista_place":
            self.discard.append(card)
        elif back and not exhausted:                          # Возврат: снова в руке
            self.receive_card(card)
            self.say(f"Возврат: {card.name} снова в руке", (170, 255, 170))
        elif mode == "main" and u.get("power"):               # Сила: действует до конца боя
            self.powers.append(card)
            if ctx.get("buff_target") is not None:
                self.ballista_power_targets[card.uid] = ctx["buff_target"]
            self.items.turn_types.append("power")
            self.say(f"Сила: {card.name} — до конца боя", (210, 170, 255))
            self.fx("power", unit=h, uid=card.uid, name=card.name)
        elif card.d.get("token") or exhausted or exhaust_limit == 1:
            yield from self.exhaust_card(card)
        elif t != "copy_hand" and (command_installation is None or command_installation.alive):
            returned = not redirected and (yield from board.bullet_returns(card, tgt))
            if not returned:
                self.used.append(card)                        # CZN: до конца хода — в Used, не в Discard
        if mode == "main" and not self.result:                # предметы: что сыграно (после розыгрыша — рука видна)
            if "exhaust_2" in rules:
                yield from self.hand_relics.exhaust_count(card, self.exhaust_plays[card.uid])
            yield from self.hand_relics.after_card(card, combo, self.walked > walked_before)
            yield from self.items.fire("play", card=card, tgt=tgt, mom=mom0,
                                       heat=paid if resource == "heat" else 0,
                                       origin=origin, previous_tags=previous_tags)
            yield from self.react()
        if mode == "main" and fae_spent and not self.result:
            if fae_rates.get("self_block"):
                self.gain_shield(h, fae_spent * fae_rates["self_block"])
            self.spend_fae(fae_spent, tgt)
        self.sync_levels()
        if self.garden is not None:
            yield from self.garden.flush_assemblies()
        if mode == "main" and "finale" in rules and not auto:
            yield from board.finale(card)
            if not self.result:
                yield from self.run_relics.finale()
            self.finale_pending = True
        if self.finale_pending and not free and not auto and not self.enemy_phase and not self.result:
            self.finale_pending = False
            self.run_relics.active_card = None
            yield from self.end_turn(from_finale=True)

    def try_insight(self, card):
        """Прозрение: 5% за основное применение, с гарантией после 20 неудач."""
        if card.growth_next() is None or card.ready:
            return
        card.insight_misses += 1
        if card.insight_misses >= M.INSIGHT_PITY or self.rng.random() < M.INSIGHT_CHANCE:
            card.ready = True
            self.say(f"Прозрение: {card.name}", (255, 230, 150))

    def hunt_followup(self, card, tgt):
        """Преследование: после одноцелевой атаки с тегом [Преследование] — дополнительный выстрел за стаки."""
        if tgt is None or not getattr(tgt, "alive", False) or "pursuit" not in card.tag_ids:
            return
        n = self.hero.ds.get("hunt", 0)
        if n <= 0 or not self.is_attack(card, "main"):
            return
        self.say(f"Преследование: {card.name} — ещё {n}", (255, 210, 120))
        self.fx("react", unit=tgt, what="shot")
        yield from self.strike(self.hero, tgt, n, kind="shot" if card.d["main"].get("ranged") else "melee",
                               tag="Преследование")

    def play_scroll(self, card, target, *, manual=True):
        """Свиток через статую: target — IdolCast(статуя, цель). Бесплатно; добил с Мёртвой водой — в руку."""
        idols = self.idols
        if idols is None or not isinstance(target, IdolCast) or target.statue not in idols.statues:
            return
        m = card.d["meaning"]
        ch = idols.choices(target.statue, m)
        if ch is not None and target.tgt not in ch:
            return
        self.hand.remove(card)
        self.hand_relics.lost_lead(card)
        self.lead_discounts.clear()
        self.hand_relics.played.add(card.uid)
        self.run_relics.observe_play(card)
        card.uses += 1
        self.try_insight(card)
        self.played += 1
        yield from idols.cast_card(target.statue, card, target.tgt)
        yield from self.card_event("played", card, target.tgt)
        if manual:
            yield from self.linked_play(card)
        self.items.scrolls[id(target.statue)] = self.items.scrolls.get(id(target.statue), 0) + 1
        yield from self.items.fire("scroll", card=card, statue=target.statue)
        yield from self.hand_relics.after_scroll(target.statue)
        if idols.killed and idols.dead_water:
            idols.dead_water = False
            self.receive_card(card)
            self.say(f"Мёртвая вода: «{card.name}» снова в руке", (180, 220, 255))
        else:
            self.used.append(card)
        yield from self.react()

    def walk_cells(self):
        """Жрец: куда дойдёт шагами этого хода."""
        if self.idols is None or self.walk_left <= 0 or self.result:
            return {}
        return {p: path for p, path in self.paths(self.hero, self.walk_left).items() if p != self.hero.cell}

    def hero_walk(self, cell):
        """Жрец идёт на клетку (тратит шаги)."""
        path = self.walk_cells().get(tuple(cell))
        if not path:
            return
        self.walk_left -= len(path)
        yield from self.walk(self.hero, path)

    def play_condition(self, when, tgt, ctx):
        if when["k"] == "surrounded" and "surrounded" in ctx:
            return ctx["surrounded"]
        return self.met(when, tgt, ctx.get("before"), ctx)

    def cond_extras(self, ctx, tgt, area=False):
        """Усиление: действия условий («В окружении: защита 4») — после основных."""
        h = self.hero
        for c in ctx.get("conds", []):
            if c["when"].get("k") == "resonance":
                continue                         # у резонанса нет отдельного эффекта
            if c.get("do") and self.play_condition(c["when"], tgt, ctx):
                ops = [o for o in c["do"] if not area or o["op"] not in ONCE]
                yield from self.apply(h, ops, tgt, dict(ctx, conds=[]))

    def card_damage_buff(self, unit, card, *, consume=False):
        buffs = unit.ds.get("card_damage_buffs", {})
        if not buffs:
            return 0
        tags, card_type = card.tag_ids, card.d.get("type")
        matching = [key for key in buffs if key[0] == self.turn
                    and (not key[1] or key[1] in tags)
                    and (not key[2] or key[2] == card_type)]
        return sum(buffs.pop(key) if consume else buffs[key] for key in matching)

    def damage_preview(self, card, mode):
        """Реальный урон карты по герою без уязвимости/метки/брони цели.

        Учитываются баффы героя (сила, разгон, дальний бонус, фокус), закалка,
        «следующая карта», бонусы предметов и выполненные условия самой карты.
        Урон по конкретной цели (дальность, добыча, уязвимость) здесь намеренно
        не учитывается: это ориентир силы карты, как в руке до выбора цели.
        """
        u = card.d.get(mode) or {}
        if mode not in ("main", "alt"):
            return []
        h, ds = self.hero, self.hero.ds
        ctx = {"ranged": u.get("ranged", False), "tag": u.get("tag"),
               "card": card if mode == "main" else None, "before": self.played,
               "temper": 0, "emp": 0,
               "x": self.available_card_resource(card) if card.d.get("x_cost") and mode == "main" else 0}
        if mode == "main":
            ctx["temper"] = self.temper.get(card.uid, 0)
            ctx["emp"] = self.card_damage_buff(h, card)
        emp, mom, focus, dbl = ctx["emp"], (ds["momentum"] if self.mech == "momentum" else 0), \
            bool(ds["focus"]), bool(self.double_next and mode == "main")
        out = []
        for op in u.get("do", []):
            kind = op.get("op")
            if kind not in ("damage", "body_slam"):
                continue
            n = op.get("n", 0)
            if kind == "body_slam":
                n += h.shield
            if kind == "damage" and op.get("per"):
                n += op["per"].get("k", 1) * self.per_count(op["per"], None, ctx)
            if kind == "damage" and mode == "main":
                n += ctx["temper"] + emp
                n += op.get("x", 0) * ctx.get("x", 0)
                emp = 0
            if mom:
                n += mom * op.get("mom_k", 1)
                mom = 0
            if ctx["ranged"]:
                n += ds["ranged_bonus"]
                if focus:
                    n *= 2
                    focus = False
            if kind == "damage" and mode == "main":
                for c in u.get("if", []):
                    if c["when"].get("k") == "resonance":
                        continue
                    if self.met(c["when"], None, ctx["before"]):
                        n = (n + c.get("plus", 0)) * c.get("mult", 1)
                n += self.items.card_bonus(card, "damage")
                if self.variant == "ash" and "area" in card.tag_ids:
                    n += 2
            n += ds["strength"]
            if ds["weak"]:
                n = int(n * 0.75)
            if kind == "damage" and dbl:
                n *= 2
                dbl = False
            if kind in ("damage", "body_slam") and mode == "main" and card.d.get("type") == "attack" \
                    and self.double_attacks > 0:
                n *= 2
            out.append(max(0, int(n)))
        return out

    def hero_bonus(self, tgt, n, op, ctx):
        """Урон удара героя с его механикой: разгон, дистанция, добыча, азарт, сосредоточение."""
        h = self.hero
        ds = h.ds
        if self.mech == "momentum" and ds["momentum"]:             # Разгон — в удар, и тратится
            mom = ds["momentum"]
            n += mom * op.get("mom_k", 1)
            if mom >= 3:
                ctx["push_bonus"] = 1
            ds["momentum"] = 0
            if mom >= 2:
                self.fx("momentum_hit", unit=tgt, n=mom)
        d = cheb(h.cell, tgt.cell)
        if op.get("far") and d >= op["far"]["d"]:
            n += op["far"]["bonus"]
        if ctx.get("ranged"):
            if self.mech == "hunter" and self.variant == "range":
                n += min(4, max(0, d - 3))
            n += ds["ranged_bonus"]
            if ds["focus"]:
                n *= 2
                ds["focus"] = False
        if tgt is self.prey:
            n += 3
        return n

    def resolve_discard(self, cards):
        finish(self.resolve_discard_gen(cards))

    def resolve_discard_gen(self, cards):
        """Игрок выбрал карты для сброса (Адажио/подобные эффекты)."""
        discarded = []
        for c in list(cards):
            if self.pending_discard <= 0:
                break
            if c in self.hand:
                self.hand.remove(c)
                self.place_discarded_card(c)
                discarded.append(c)
                self.pending_discard -= 1
        if discarded:
            self.say(f"Сброшено карт: {len(discarded)}", (220, 210, 180))
        if not self.hand:
            self.pending_discard = 0
        for card in discarded:
            yield from self.hand_relics.manual_discard(card)
        yield from self.react_card_events()
        self.sync_levels()

    def apply(self, src, ops, tgt, ctx=None):
        ctx = ctx if ctx is not None else {}
        h = self.hero
        emp = ctx.get("emp", 0) if src is h else 0          # «Следующая карта»: к первому удару по цели
        for op in ops:
            if self.result and op["op"] not in ("block",):
                return
            if op.get("when") and not self.play_condition(op["when"], tgt, ctx):
                continue
            k = op["op"]
            n = op.get("n", 0)
            if op.get("per") and src is h:                                  # «за каждую…»
                n += op["per"].get("k", 1) * self.per_count(op["per"], tgt, ctx)
            buff_target = ctx.get("buff_target")
            if src is h and buff_target is not None and M.ballista_buff_op(op):
                self.buff_ballista(buff_target, op, n)
                continue
            if k == "damage" and tgt is not None:
                dbl = 1
                if src is h and ctx.get("card") is not None and ctx["card"].d.get("type") == "attack":
                    if not ctx.get("double_done") and self.double_attacks > 0:
                        ctx["double_done"] = True
                        self.double_attacks -= 1
                        self.say("Двойной залп!", (255, 220, 120))
                    if ctx.get("double_done"):
                        dbl = 2
                if src is h:
                    n += ctx.get("temper", 0) + emp
                    n += op.get("x", 0) * ctx.get("x", 0)
                    emp = 0
                    n = self.hero_bonus(tgt, n, op, ctx)
                    for c in ctx.get("conds", []):            # Усиление: «ещё +N», «урон ×N»
                        if c["when"].get("k") == "resonance":
                            continue                          # резонанс только повторяет карту
                        if (c.get("plus") or c.get("mult")) and self.play_condition(c["when"], tgt, ctx):
                            n = (n + c.get("plus", 0)) * c.get("mult", 1)
                    n += self.fae_bonus(ctx, "damage")
                    n += self.items.card_bonus(ctx.get("card"), "damage")   # предметы: карты тега сильнее
                    if self.variant == "ash" and ctx.get("card") is not None and "area" in ctx["card"].tag_ids:
                        n += 2                                              # Пепел: области сильнее
                    if self.double_next and ctx.get("card") is not None:     # предмет: двойной урон (итоговый)
                        dbl = 2
                        self.double_next = False
                        self.say("Двойной урон!", (255, 220, 120))
                    if tgt.shield > 0 and ctx.get("card") is not None and "pulverize" in ctx["card"].tag_ids:
                        n = n * 6 // 5
                hp, shield = tgt.hp, tgt.shield
                saved_shield = tgt.shield
                if op.get("ignore_shield"):
                    tgt.shield = 0
                yield from self.strike(src, tgt, n, kind="shot" if ctx.get("ranged") else "melee",
                                       el=op.get("el"), anim=not ctx.get("vfx"), tag=ctx.get("tag"), mult=dbl)
                if op.get("ignore_shield"):
                    tgt.shield = saved_shield
                if src is h and not self.result:
                    yield from self.board_relics.check_totem(ctx.get("card"), tgt)
                if src is h:
                    yield from self.hand_relics.hit(ctx.get("card"), tgt, hp, shield)
            elif k == "body_slam" and tgt is not None:
                n += src.shield
                if src is h:
                    n = self.hero_bonus(tgt, n, op, ctx)
                    n += self.items.card_bonus(ctx.get("card"), "damage")
                dbl = 1
                if src is h and ctx.get("card") is not None and ctx["card"].d.get("type") == "attack":
                    if not ctx.get("double_done") and self.double_attacks > 0:
                        ctx["double_done"] = True
                        self.double_attacks -= 1
                        self.say("Двойной залп!", (255, 220, 120))
                    if ctx.get("double_done"):
                        dbl = 2
                hp, shield = tgt.hp, tgt.shield
                yield from self.strike(src, tgt, n, anim=not ctx.get("vfx"), mult=dbl)
                if src is h:
                    yield from self.hand_relics.hit(ctx.get("card"), tgt, hp, shield)
            elif k == "double_next":
                self.double_next = True
            elif k == "resource":                                          # энергия / жар / свиток — по герою
                if self.mech == "heat":
                    h.ds["heat"] = min(self.hero_def.get("heat_max", 12), h.ds["heat"] + n)
                elif self.idols is not None:
                    self.draw(n)
                else:
                    self.energy += n
            elif k == "next_energy":
                self.next_energy += n
            elif k == "next_heat":
                src.ds["next_heat"] = src.ds.get("next_heat", 0) + n
            elif k == "next_draw":
                self.next_draw += n
            elif k == "add_random":                                        # случайные карты героя — только на бой
                pool = [cid for cid in self.hero_def.get("rewards", []) if cid in self.run.defs
                        and not self.run.defs[cid].get("deck_unique")]
                for _ in range(n):
                    if pool and len(self.hand) < HAND_MAX:
                        self.receive_card(M.Card(self.rng.choice(pool), self.run.defs))
            elif k == "spread" and ctx.get("dead") is not None and tgt is not None:   # перекинуть состояние
                d = ctx["dead"]
                what = op.get("what", "bleed")
                v = d.ds.get(what, 0)
                if v:
                    if what == "burn":
                        self.add_burn(tgt, v)
                    else:
                        tgt.ds[what] += v
            elif k == "bleed" and tgt is not None:
                if not tgt.ds["bleed"]:
                    self.fx("status", unit=tgt, el="bleed")
                tgt.ds["bleed"] += n
            elif k == "counter":
                src.ds["counter"] += n
                self.fx("status", unit=src, el="counter")
            elif k == "strength_x2":
                src.ds["strength"] *= 2
                self.fx("status", unit=src, el="rally")
            elif k == "note":
                pass
            elif k == "discard_hand":
                for c in list(ctx.get("hand_targets", ())):
                    if c in self.hand:
                        self.hand.remove(c)
                        self.place_discarded_card(c)
                        yield from self.card_event("discarded", c)
            elif k == "burn_card":                                         # Изгнать из руки N карт (случайно)
                pool = [c for c in self.hand if not c.d.get("token")]
                self.rng.shuffle(pool)
                for c in pool[:max(1, n)]:
                    self.hand.remove(c)
                    self.say(f"Изгнание: {c.name}", (255, 170, 120))
                    yield from self.exhaust_card(c)
            elif k == "chain" and tgt is not None:                         # молния перескакивает на соседей цели
                hit, cur = {tgt}, tgt
                for _ in range(op.get("jumps", 2)):
                    nxt = [f for f in self.foes() if f not in hit and cheb(f.cell, cur.cell) <= 3]
                    if not nxt:
                        break
                    previous, cur = cur, min(nxt, key=lambda f: cheb(f.cell, cur.cell))
                    hit.add(cur)
                    if self.garden is not None and src is h:
                        yield from self.elf_cast(previous, "_elf_storm_jump", "Прыжок молнии", target=cur,
                                                 empowered=ctx.get("elf_empowered", False))
                    else:
                        self.fx("react", unit=cur, what="shock")
                    self.hurt(cur, self.attack_value(h, n) if src is h else n, src, "spell")
                    if op.get("stun") and cur.alive:
                        cur.ds["stun"] = True
            elif k == "block":
                if op.get("mom_k") and src is h:                           # Резкая остановка: разгон — в защиту
                    n += src.ds["momentum"] * op["mom_k"]
                    src.ds["momentum"] = 0
                if src is h:
                    n += ctx.get("temper", 0)
                    n += self.fae_bonus(ctx, "block")
                    n += self.items.card_bonus(ctx.get("card"), "block")
                self.gain_shield(src, n)
            elif k == "stance" and src is h and not ctx.get("stance_applied"):
                stance = op["id"]
                ctx["stance_applied"] = True
                self.set_stance(None if self.stance == stance else stance)
                yield from self.hand_relics.changed_stance()
            elif k in ("push", "pull") and tgt is not None:
                start = tgt.cell
                bonus = self.items.take_card_bonus(ctx.get("card"), "displace") if src is h and tgt.alive and n else 0
                if k == "push":
                    bonus += ctx.get("push_bonus", 0)
                yield from self.push(src, tgt, n + bonus, toward=k == "pull", card=ctx.get("card"))
                if src is h:
                    yield from self.board_relics.after_push(ctx.get("card"), tgt, start)
                if op.get("burn_on_move") and tgt.alive and tgt.cell != start:
                    self.add_burn(tgt, op["burn_on_move"])
                if k == "push" and src is h and self.variant == "press":
                    src.ds["momentum"] = min(self.hero_def.get("momentum_max", 5), src.ds["momentum"] + 1)
            elif k == "retreat" and tgt is not None:                       # отскок от цели
                if src is h and self.stance == "knight" and not self.enemy_phase:
                    jumps = self.knight_paths(n)
                    distance = cheb(src.cell, tgt.cell)
                    destination = max(jumps, key=lambda p: cheb(p, tgt.cell), default=src.cell)
                    if cheb(destination, tgt.cell) > distance:
                        yield from self.walk(src, jumps[destination])
                    continue
                d = (sign(src.cell[0] - tgt.cell[0]), sign(src.cell[1] - tgt.cell[1]))
                path, p = [], src.cell
                for _ in range(n):
                    q = (p[0] + d[0], p[1] + d[1])
                    if d == (0, 0) or not self.free(q, exclude=src):
                        break
                    path.append(q)
                    p = q
                yield from self.walk(src, path)
            elif k == "root" and tgt is not None:
                tgt.ds["root"] = max(tgt.ds["root"], n + self.fae_bonus(ctx, "stack"))
                self.say(f"{tgt.name}: корни — не двигается", (180, 230, 140))
            elif k == "add_card":
                pool = op.get("pool")
                force = bool(op.get("force"))
                if pool and op.get("same"):
                    self.add_tokens(self.rng.choice(pool), n, force=force)
                elif pool and op.get("distinct"):
                    first = op.get("first")
                    choices = [cid for cid in dict.fromkeys(pool) if cid != first]
                    chosen = [first] if first and n else []
                    chosen += self.rng.sample(choices, min(max(0, n - len(chosen)), len(choices)))
                    for cid in chosen:
                        self.add_tokens(cid, 1, force=force)
                elif pool:
                    count = n if force else min(n, HAND_MAX - len(self.hand))
                    for _ in range(count):
                        self.add_tokens(self.rng.choice(pool), 1, force=force)
                else:
                    self.add_tokens(op.get("card", "arrow"), n, force=force)
            elif k == "copy_hand" and ctx.get("copy_target") is not None:
                self.copy_hand_card(ctx.pop("copy_target"))
            elif k == "trigger_retain":
                for c in ctx.get("hand_targets", ()):
                    for _ in range(n):
                        if c not in self.hand:
                            break
                        event = "retained" if M.card_reactions(c.d, "retained") else "hand_turn_end"
                        yield from self.card_event(event, c)
                        yield from self.react_card_events()
            elif k == "grant_retain":
                for c in ctx.get("hand_targets", ()):
                    self.temporary_retain[c.uid] = max(n, self.temporary_retain.get(c.uid, 0))
            elif k == "retain_rewards":
                rewards = src.ds.setdefault("retain_rewards", {"damage": 0, "block": 0})
                rewards["damage"] += n
                rewards["block"] += op.get("block", 0)
            elif k == "create_retain":
                pool = [cid for cid, d in self.run.defs.items() if "retain" in M.card_rules(d)
                        and not d.get("deck_unique") and (self.idols is not None or not d.get("meaning"))]
                for _ in range(n):
                    if pool:
                        self.add_tokens(self.rng.choice(pool), 1, heat_payment=self.mech == "heat")
            elif k == "ranged_bonus":
                src.ds["ranged_bonus"] += n
            elif k == "focus":
                src.ds["focus"] = True
            elif k == "heat":
                hd = self.hero_def
                src.ds["heat"] = max(0, min(hd.get("heat_max", 12), src.ds["heat"] + n))
                self.fx("heat_gain" if n > 0 else "heat_cool", unit=src, n=n)
            elif k == "heat_regen":
                src.ds["heat_regen"] += n
            elif k == "fort":                                               # половина защиты — на следующий ход
                src.ds["fort"] = 1
            elif k == "keep_momentum":
                src.ds["keep_mom"] = True
            elif k == "momentum":
                src.ds["momentum"] = min(self.hero_def.get("momentum_max", 5), src.ds["momentum"] + n)
            elif k == "fae" and src is h:
                self.gain_fae(n + self.fae_bonus(ctx, "fae"))
            elif k == "spend_fae" and src is h:
                self.spend_fae(n, tgt)
            elif k == "plant" and self.garden is not None:
                center = ctx.get("center") or (tgt.cell if tgt is not None else src.cell)
                yield from self.garden.plant(op, center, extra_growth=self.fae_bonus(ctx, "growth"),
                                             empowered=ctx.get("elf_empowered", False))
            elif k == "beast" and self.garden is not None:
                self.garden.summon_beast(op["beast"], bonus=self.fae_bonus(ctx, "beast"), extra=op.get("stats"),
                                         empowered=ctx.get("elf_empowered", False))
            elif k == "attach" and self.garden is not None:
                self.garden.attach(ctx.get("card"), ctx.get("attach_host"), op["attach"],
                                   bonus=self.fae_bonus(ctx, "growth"), extra=op.get("bonus"))
            elif k == "fae_ring" and self.garden is not None:
                center = ctx.get("center") or (tgt.cell if tgt is not None else src.cell)
                self.garden.add_ring(center, op.get("n", 3) + src.ds.get("fae", 0) // 4
                                     + self.fae_bonus(ctx, "duration"), radius=op.get("r", 1),
                                     trap=bool(op.get("trap")))
            elif k == "blueprint" and self.garden is not None and ctx.get("card") is not None:
                self.garden.make_parts(ctx["card"])
            elif k == "execute_below" and tgt is not None and tgt.alive:
                if tgt.hp * 100 < tgt.max_hp * n:
                    self.say(f"Казнь: {tgt.name}", (255, 170, 120))
                    self.hurt(tgt, tgt.hp + 999, src, "spell")
            elif k == "damage_nearest" and src is h:
                target = self.garden.nearest_foe(h.cell) if self.garden is not None else None
                if target is not None:
                    yield from self.elf_cast(h, "_elf_fate_thread", "Разрыв связи", target=target,
                                             empowered=ctx.get("elf_empowered", False))
                    self.hurt(target, self.attack_value(h, n) + self.fae_bonus(ctx, "damage"), h, "spell")
            elif k in ("aoe_target", "aoe_center"):
                center = (ctx.get("center") if k == "aoe_center" else None) or \
                         (tgt.cell if tgt is not None else ctx.get("center") or h.cell)
                for f in [f for f in self.foes() if cheb(f.cell, center) <= op.get("r", 1)]:
                    yield from self.apply(src, op["do"], f, dict(ctx, center=None))
            elif k == "trap" and ctx.get("center"):
                self.traps[ctx["center"]] = n
            elif k == "ballista_place" and src is h:
                self.place_ballista(ctx.get("center"), ctx.get("range", 2),
                                    hp=op.get("hp", BALLISTA_HP), charge=op.get("charge", 0), card=ctx.get("card"))
            elif k == "ballista_load" and src is h and tgt is not None and tgt in self.ballistas:
                if tgt in self.ballista_load_targets(ctx.get("range", 2)):
                    tgt.charge = min(tgt.charge_max, tgt.charge + n)
                    self.say(f"Баллиста заряжена: {tgt.charge}/{tgt.charge_max}", (236, 205, 130))
                    yield from self.board_relics.ballista_loaded(tgt)
            elif k == "ballista_fire" and src is h and tgt is not None:
                ballista = ctx.get("ballista")
                if ballista is not None and ballista in self.ballista_shooters(tgt, ctx.get("range", 6)):
                    kept_charge = yield from self.board_relics.held_charge(ballista)
                    ballista.charge -= kept_charge
                    damage = self.ballista_damage(op, ballista=ballista)
                    mult = self.ballista_shot_multiplier(ballista)
                    ballista.ds["focus"] = False
                    ballista.ds.pop("shot_empower", None)
                    ballista.ds.pop("double_next", None)
                    if ballista.ds.get("double_attacks"):
                        ballista.ds["double_attacks"] -= 1
                    ballista.charge = kept_charge
                    self.say(f"Выстрел баллисты: {tgt.name}", (236, 205, 130))
                    yield from self.strike(ballista, tgt, damage, kind="shot", mult=mult)
            elif k == "ignite":                                            # поджечь клетки
                c0 = ctx.get("center") or (tgt.cell if tgt is not None else src.cell)
                for p in self.c.grid.in_radius(c0, n):
                    self.set_surface(p, "fire")
                self.zone_fx = (list(self.c.grid.in_radius(c0, n)), 0.6)
            elif k == "detonate":                                          # вспышка горящих
                for f in [f for f in self.foes() if f.ds["burn"] and cheb(f.cell, src.cell) <= op.get("r", 4)]:
                    dmg = f.ds["burn"] * max(1, n)
                    if op.get("clear"):
                        f.ds["burn"] = 0
                    self.say(f"Вспышка: {f.name} −{dmg}", (255, 170, 90))
                    self.fx("react", unit=f, what="flare")
                    self.hurt(f, dmg, src, "spell")
            elif k == "burn" and tgt is not None:
                self.add_burn(tgt, n)
            elif k == "burn_all":
                for f in [f for f in self.foes() if f.ds["burn"]]:
                    self.add_burn(f, n)
            elif k == "poison" and tgt is not None:
                if not tgt.ds["poison"]:
                    self.fx("status", unit=tgt, el="poison")
                tgt.ds["poison"] += n
            elif k == "frost" and tgt is not None:
                self.add_frost(tgt, n)
            elif k == "wet" and tgt is not None:
                self.wet(tgt)
            elif k in ("weak", "vulnerable") and tgt is not None:
                self.fx("status", unit=tgt, el=k)
                tgt.ds[k] += n + self.fae_bonus(ctx, "stack")
            elif k == "stun" and tgt is not None:
                tgt.ds["stun"] = True
                self.say(f"{tgt.name} оглушён — пропустит намерение", (255, 230, 140))
            elif k == "mark" and tgt is not None:
                tgt.ds["mark"] += n
            elif k == "hunt" and src is h:
                src.ds["hunt"] = min(5, src.ds.get("hunt", 0) + n)
                self.say(f"Преследование +{n}", (255, 220, 120))
            elif k == "draw":
                self.draw(n + self.fae_bonus(ctx, "draw"))
            elif k == "discard_choose":
                self.pending_discard += max(0, n)
                self.say(f"Выберите {self.pending_discard} карт(ы) для сброса", (220, 210, 180))
            elif k == "discard_blessing":
                if src.shield * 10 < src.max_hp * 3:
                    amount = src.max_hp * 3 // 5
                    recipient = yield from self.run_relics.blessing_target(src)
                    recipient.shield += amount
                    self.c.emit("shield", unit=recipient, amount=amount)
            elif k == "energy":
                self.energy += n
            elif k == "heal":
                n += self.fae_bonus(ctx, "heal")
                src.hp = min(src.max_hp, src.hp + n)
                self.c.emit("heal", unit=src, amount=n)
            elif k in ("temper_card", "temper_spirit"):
                card = ctx["card"]
                self.temper[card.uid] = self.temper.get(card.uid, 0) + n
                self.say(f"«{card.name}»: +{n} урона", (255, 220, 120))
            elif k in ("empower", "card_damage_buff", "next_fire_damage"):
                # next_fire_damage встречается в прежних определениях карт из сохранений.
                tag = M.tag_id(op.get("tag", "fire" if k == "next_fire_damage" else ""))
                card_type = op.get("type", "attack" if k == "next_fire_damage" else "")
                key = (self.turn + op.get("delay", 0 if k == "empower" else 1), tag, card_type)
                buffs = src.ds.setdefault("card_damage_buffs", {})
                buffs[key] = buffs.get(key, 0) + n
            elif k == "reduce_burn":
                src.ds["burn"] = max(0, src.ds["burn"] - n)
                self._icons(src)
            elif k == "spirit_ignite" and tgt is not None:
                x, y = tgt.cell
                self.set_surface(tgt.cell, "fire")
                if n:
                    for cell in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                        self.set_surface(cell, "fire")
            elif k == "lose_hp":
                self.hurt(src, n, None, "hp_cost")
            elif k == "strength":
                src.ds["strength"] += n
            elif k == "double_attacks":
                self.double_attacks += n
                self.say(f"Следующие {self.double_attacks} атак — двойной урон", (255, 220, 120))
            elif k == "collide_x2":
                self.collide_k = max(self.collide_k, op.get("n") or 2)
            elif k == "thorns":
                src.ds["thorns"] += n
            elif k == "cleanse":
                src.ds["weak"] = src.ds["vulnerable"] = 0
            elif k == "rage":
                src.ds["rage"] += 1
            elif k == "aoe_adjacent":
                for f in [f for f in self.foes() if cheb(f.cell, src.cell) <= 1]:
                    yield from self.apply(src, op["do"], f, ctx)
            elif k == "aoe_radius":
                r = self.radius_for_op(op) if src is h else op.get("r", 1)
                for f in [f for f in self.foes() if cheb(f.cell, src.cell) <= r]:
                    yield from self.apply(src, op["do"], f, ctx)
            for v in (src, tgt):
                if v is not None:
                    self._icons(v)
            yield WAIT

    # ---------- ход врагов ----------

    def auto_end_turn(self):
        """Автоматические карты в руке (например, «Стрела охоты») играются сами."""
        for c in list(self.hand):
            if not c.d.get("auto_end"):
                continue
            target = self.auto_target(c, "main", auto=True)
            if target is None:
                if c in self.hand:
                    self.hand.remove(c)
                    self.place_discarded_card(c)
                    yield from self.card_event("discarded", c)
                continue
            yield from self.play(c, "main", target, free=True, auto=True)
            if self.result:
                return

    def end_turn(self, *, from_finale=False):
        """Конец хода игрока: рука в сброс, враги исполняют намерения, начинается новый ход."""
        if self.result:
            return
        yield from self.hand_relics.before_end(from_finale)
        self.finale_pending = False
        h = self.hero
        pact = self.run_relics.pact_turn == self.turn + 1
        protected = self.run_relics.pact_card if pact else None
        if self.mech == "heat" and not pact:                             # перегрев: ожог за каждую единицу сверх
            hd = self.hero_def
            over = h.ds["heat"] - hd.get("overheat", 8)
            if over > 0 and self.items.mod("overheat_burn"):          # предмет: перегрев — пламя врагам
                h.ds["heat"] = hd.get("overheat", 8)
                self.say(f"Перегрев уходит в пламя: горение {over * 2} всем врагам", (255, 170, 90))
                for f in self.foes():
                    self.add_burn(f, over * 2)
                over = 0
            if over > 0:
                h.ds["heat"] = hd.get("overheat", 8)
                self.say(f"Перегрев! −{over * hd.get('overheat_dmg', 2)} HP", (255, 140, 90))
                self.fx("overheat", unit=h, n=over)
                self.hurt(h, over * hd.get("overheat_dmg", 2), None, "hp_cost")
                if self.result:
                    return
        if not h.ds["keep_mom"]:
            h.ds["momentum"] = 0
        yield from self.power_fire("end")
        yield from self.items.fire("end")
        if self.result:
            return
        for c in list(self.hand):
            if c in self.hand:
                yield from self.card_event("hand_turn_end", c)
        yield from self.auto_end_turn()
        if self.result:
            return
        for c in list(self.hand):
            if c in self.hand and c is not protected and "ephemeral" in M.card_rules(c.d):
                self.hand.remove(c)
                yield from self.exhaust_card(c)
                yield from self.hand_relics.on_ephemeral(c)
        self.hand_relics.clear_fleeting()
        self.discard += self.used                            # CZN: Used → Discard только в конце хода
        self.used = []
        temporary, self.temporary_retain = self.temporary_retain, {}
        retain_all = self.has_mod("retain") or self.items.mod("retain_all")
        retained = {c for c in self.hand if c.uid in temporary or "retain" in M.card_rules(c.d) or retain_all
                    or (self.garden is not None and self.garden.attached(c))}
        kept = [c for c in self.hand if c in retained or (c.d.get("keep") and self.met(c.d["keep"]))]
        if self.idols is not None:                            # Жрец: несыгранные свитки остаются
            kept = [c for c in self.hand if not c.d.get("token")][:PRIEST_HAND]
            if protected in self.hand and protected not in kept:
                kept = [*kept[:PRIEST_HAND - 1], protected]
        self.guard = [c for c in self.hand if c not in kept and (c.d.get("echo") or {}).get("on")]
        discarded = [c for c in self.hand if not c.d.get("token") and c not in kept and c not in self.guard]
        for c in discarded:
            self.place_discarded_card(c)
        self.hand = kept + self.guard                       # отклик на ход врага ждёт в руке
        retained_count = 0
        for c in kept:
            if c in self.hand:
                self.say(f"{c.name} остаётся в руке", (170, 255, 170))
                yield from self.card_event("retained", c)
                if c in retained:
                    retained_count += 1
                    self.hand_relics.retained(c)
                    if discount := temporary.get(c.uid, 0):
                        self.retained_card_discounts[c.uid] = (self.turn + 1, discount)
                    yield from self.board_relics.retained(c)
                    yield from self.items.fire("retained", card=c)
        rewards = h.ds.pop("retain_rewards", {})
        if retained_count and rewards.get("damage"):
            yield from self.apply(h, [{"op": "card_damage_buff", "n": rewards["damage"] * retained_count,
                                       "tag": "fire", "type": "attack"}], None)
        if retained_count and rewards.get("block"):
            self.gain_shield(h, rewards["block"] * retained_count)
        for c in discarded:
            yield from self.card_event("discarded", c)
        yield from self.react_card_events()
        if self.garden is not None:
            yield from self.garden.end_turn()
            if self.result:
                return
        self.tick_end(self.hero)
        if self.idols is not None:                            # статуи играют свои свитки, призванные — ход
            yield from self.idols.end_of_turn()
            if self.result:
                return
        yield from self.board_relics.end_turn()
        self.enemy_phase = True
        yield from self.env_resolve()
        if self.result:
            return
        for u in list(self.foes()):
            if self.result:
                return
            if self.board_relics.delayed.get(u) == self.turn:
                continue
            u.shield = 0
            yield from self.tick_start(u)
            if not u.alive:
                continue
            yield from self.enemy_traits(u)
            if not u.alive:
                continue
            if u.ds["stun"]:
                u.ds["stun"] = False
                self.say(f"{u.name} оглушён и пропускает ход", (255, 230, 140))
                self._icons(u)
            else:
                yield from self.act(u)
                yield from self.react()
            self.tick_end(u)
            yield ("wait", 0.25)
        self.enemy_phase = False
        if not self.result:
            yield from self.start_player_turn()

    def enemy_traits(self, u):
        """Свойства врага в начале его хода: регенерация, рост, лечение и защита соседей, слияние слизней."""
        ed = u.edef or {}
        if ed.get("regen") and u.hp < u.max_hp:
            n = min(ed["regen"], u.max_hp - u.hp)
            u.hp += n
            self.c.emit("heal", unit=u, amount=n)
        if ed.get("grow"):
            u.ds["strength"] += ed["grow"]
            self.fx("status", unit=u, el="rally")
            self.say(f"{u.name} крепнет: +{ed['grow']} силы", (255, 170, 120))
        near = [f for f in self.foes() if f is not u and cheb(f.cell, u.cell) <= 1]
        if ed.get("mend"):
            for f in near:
                if f.hp < f.max_hp:
                    n = min(ed["mend"], f.max_hp - f.hp)
                    f.hp += n
                    self.c.emit("heal", unit=f, amount=n)
        if ed.get("protect"):
            for f in near:
                f.shield += ed["protect"]
                self.c.emit("shield", unit=f, amount=ed["protect"])
        if ed.get("merge"):
            mate = next((f for f in near if (f.edef or {}).get("merge") and f.eid == u.eid), None)
            if mate is not None:                                        # слизни сливаются в одного
                u.max_hp += mate.max_hp
                u.hp += mate.hp
                u.ds["strength"] += max(1, mate.ds["strength"] + 1)
                mate.hp = 0
                mate.alive = False
                self.c.emit("death", unit=mate, expire=False, rises=False)
                self.c.emit("heal", unit=u, amount=mate.max_hp)
                self.say(f"{u.name} сливается с соседом: HP {u.hp}, сила +1", (190, 230, 140))
                self.fx("react", unit=u, what="steam")
        self._icons(u)
        yield WAIT

    ENV_NAMES = {"gust": "Порыв ветра", "lava_rain": "Лавовый дождь"}

    def env_plan(self):
        """Начало хода: природа предупреждает, что сделает в ход врагов (каждые every ходов с start)."""
        e = self.env
        self.env_now = None
        if not e or self.result:
            return
        start, every = e.get("start", 3), e.get("every", 4)
        if self.turn < start or (self.turn - start) % every:
            return
        h = self.hero
        g = self.c.grid
        if e["kind"] == "gust":
            dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            d = dirs[self.rng.randrange(4)]
            path, p = [], h.cell
            for _ in range(e.get("n", 2)):
                p = (p[0] + d[0], p[1] + d[1])
                if not g.in_bounds(p):
                    break
                path.append(p)
            self.env_now = {"kind": "gust", "dir": d, "n": e.get("n", 2), "cells": path,
                            "name": self.ENV_NAMES["gust"]}
            arrow = {(1, 0): "→", (-1, 0): "←", (0, 1): "↓", (0, -1): "↑"}[d]
            self.say(f"Порыв ветра: в ход врагов сдует на {e.get('n', 2)} клетки {arrow} (кто стоит на открытом)",
                     (190, 220, 255))
        elif e["kind"] == "lava_rain":
            near = [p for p in g.in_radius(h.cell, 3) if g.get(p) is not None and g.get(p).passable]
            self.rng.shuffle(near)
            cells = [h.cell] + [p for p in near if p != h.cell][:e.get("n", 4)]
            self.env_now = {"kind": "lava_rain", "cells": cells, "dmg": e.get("dmg", 6),
                            "name": self.ENV_NAMES["lava_rain"]}
            self.say(f"Лавовый дождь: отмеченные клетки обожжёт ({e.get('dmg', 6)}) в ход врагов", (255, 170, 90))

    def env_resolve(self):
        """Ход врагов начинается с природы: ветер сдувает героя, лава падает на отмеченные клетки."""
        e = self.env_now
        self.env_now = None
        if not e:
            return
        h = self.hero
        if e["kind"] == "gust":
            near_cover = any(self.c.grid.get(p) is not None and (not self.c.grid.get(p).passable or
                                                                  self.c.grid.get(p).cover)
                             for p in self.c.grid.in_radius(h.cell, 1) if p != h.cell)
            if near_cover or h.ds.get("root"):
                self.say("Ветер: герой укрылся и устоял", (190, 220, 255))
                return
            self.say("Порыв ветра сдувает героя!", (190, 220, 255))
            self.fx("shake", unit=h, n=6)
            yield from self.push(h, h, e["n"], d=e["dir"])
        elif e["kind"] == "lava_rain":
            self.zone_fx = (list(e["cells"]), 0.7)
            for p in e["cells"]:
                v = self.unit_at(p)
                if v is not None:
                    self.hurt(v, int(round(e["dmg"] * self.dmg_k)), None, "spell")
                self.set_surface(p, "fire")
            self.say("Лава падает с потолка!", (255, 150, 80))
            yield ("wait", 0.4)

    def choose_intent(self, u):
        d = u.edef
        if d.get("smart") == "shaman":
            hurt = [a for a in self.foes() if a.max_hp - a.hp >= 6]
            mv = d["moves"]["heal" if hurt and u.cyc % 2 == 0 else "splash"]
            u.cyc += 1
        else:
            cyc = d["phases"][u.phase - 1]["cycle"] if u.phase else d["cycle"]
            mv = cyc[u.cyc % len(cyc)]
            u.cyc += 1
        it = dict(mv)
        if "dmg" in it:                                       # глубже — больнее
            it["dmg"] = int(round(it["dmg"] * self.dmg_k))
        if it["kind"] == "charge":                           # рывок: линия к герою отмечается сразу
            h = self.hero
            dd = (sign(h.cell[0] - u.cell[0]), sign(h.cell[1] - u.cell[1]))
            cells, p = [], u.cell
            for _ in range(it.get("range", 4)):
                p = (p[0] + dd[0], p[1] + dd[1])
                cell = self.c.grid.get(p)
                if cell is None or not cell.passable or dd == (0, 0):
                    break
                cells.append(p)
            it["cells"], it["dir"] = cells, dd
        if it["kind"] == "zone":                             # зона отмечается сразу и не двигается
            it["cells"] = self.zone_cells(u, it)
            if it.get("shape") == "cross":
                it["cross_center"] = self.hero.cell
        u.intent = it

    def zone_cells(self, u, it):
        """Клетки зоны врага по форме: target (вокруг героя), self (вокруг себя), cell (клетка героя — снайпер),
        row / col / cross (ряд, столбец, крест через героя), beam (луч от врага через героя до края)."""
        g = self.c.grid
        h = self.hero.cell
        shape = it.get("shape", "self")
        ok = lambda p: g.in_bounds(p) and g.get(p) is not None and g.get(p).passable   # noqa: E731
        if shape == "cell":
            return [h]
        if shape in ("row", "col", "cross"):
            out = []
            if shape in ("row", "cross"):
                out += [(x, h[1]) for x in range(g.w)]
            if shape in ("col", "cross"):
                out += [(h[0], y) for y in range(g.h)]
            return sorted({p for p in out if ok(p) and p != u.cell})
        if shape == "beam":
            d = (sign(h[0] - u.cell[0]), sign(h[1] - u.cell[1]))
            out, p = [], u.cell
            while d != (0, 0):
                p = (p[0] + d[0], p[1] + d[1])
                if not g.in_bounds(p) or g.get(p) is None or (not g.get(p).passable and g.get(p).cover == "full"):
                    break
                out.append(p)
            return out
        c = h if shape == "target" else u.cell
        return sorted(p for p in g.in_radius(c, it.get("r", 1)) if g.in_bounds(p) and (shape == "target" or p != u.cell))

    def zone_hit_cells(self, it):
        """Луч останавливается на баллисте, даже если её поставили после прицеливания."""
        cells = it.get("cells", [])
        if it.get("shape") == "beam":
            blockers = {u.cell for u in self.ballistas}
            for i, p in enumerate(cells):
                if p in blockers:
                    return cells[:i + 1]
        return cells

    def intent_damage(self, u):
        """Сколько получит герой, если намерение сработает (для значка)."""
        it = u.intent or {}
        if it.get("kind") == "melee":                       # дойдёт с ходу (больше половины хода) — вполсилы
            if self.desecrate_target(u) is not None:
                return 0
            steps = max(0, cheb(u.cell, self.hero.cell) - 1)
            dmg = it["dmg"] if steps * 2 <= u.speed else max(1, it["dmg"] // 2)
            return self.hit_value(u, self.hero, dmg) if steps <= u.speed else 0
        if it.get("kind") == "zone":                          # зона: только если герой в её клетках
            return self.hit_value(u, self.hero, it["dmg"]) if self.hero.cell in self.zone_hit_cells(it) else 0
        if it.get("kind") == "shot":
            return self.hit_value(u, self.hero, it["dmg"] * u.ds["aim"]) if self.in_fire_zone(u, it) else 0
        if it.get("kind") == "charge":
            return self.hit_value(u, self.hero, it["dmg"]) if self.hero.cell in it.get("cells", []) else 0
        if it.get("kind") == "pull":
            return self.hit_value(u, self.hero, it["dmg"]) if self.in_fire_zone(u, it) else 0
        return 0

    def desecrate_target(self, u):
        """Жрец: ближний враг (один раз за бой) идёт глушить статую, если она заметно ближе Жреца и не заглушена."""
        if self.idols is None or u.edef.get("keep_range") or u.ds["root"] or getattr(u, "desecrated", False):
            return None
        h = self.hero
        dh = cheb(u.cell, h.cell)
        if dh <= 1:
            return None
        free = [s for s in self.idols.statues if not self.idols.silenced(s)]
        if not free:
            return None
        st = min(free, key=lambda s: cheb(s.cell, u.cell))
        return st if cheb(st.cell, u.cell) + 2 <= dh else None

    def rod(self, h):
        """Статуя Перуна с «Священным дубом», рядом с которой стоит Жрец (громоотвод), или None."""
        if self.idols is None:
            return None
        return next((s for s in self.idols.statues if s.rod and cheb(s.cell, h.cell) <= 2), None)

    def shot_range(self, u):
        return max([m.get("range", 5) for m in (u.edef or {}).get("cycle", []) if m.get("kind") == "shot"] or [5])

    def in_fire_zone(self, u, it=None, cell=None):
        """Попадёт ли выстрел стрелка u по герою (или по клетке cell): дальность и линия обзора; стрелок не ходит."""
        it = it or u.intent or {}
        c = cell or self.hero.cell
        if self.idols is not None and any(s.cell in bresenham(u.cell, c)[1:-1] for s in self.idols.statues):
            return False                                     # статуя загораживает выстрел
        return cheb(u.cell, c) <= it.get("range", self.shot_range(u)) and self.los(u.cell, c)

    def fire_zone(self, u, it=None):
        """Клетки, по которым стрелок попадёт со своего места (для подсветки)."""
        it = it or u.intent or {}
        rng_ = it.get("range", self.shot_range(u))
        return [p for p in self.c.grid.in_radius(u.cell, rng_) if self.c.grid.in_bounds(p) and p != u.cell
                and self.los(u.cell, p)]

    def take_firing_spot(self, u, rng_):
        """Перебежка стрелка: туда, откуда герой в зоне и на виду, не ближе keep_range."""
        h = self.hero
        keep = u.edef.get("keep_range", 0)
        ok = lambda p: cheb(p, h.cell) <= rng_ and self.los(p, h.cell)   # noqa: E731
        if ok(u.cell) and cheb(u.cell, h.cell) >= keep:
            return
        path = self.enemy_move_to(u, lambda p: ok(p) and cheb(p, h.cell) >= keep,
                                  lambda p: (not ok(p), abs(cheb(p, h.cell) - keep)))
        yield from self.walk(u, path)

    def enemy_move_to(self, u, goal_ok, score):
        if u.ds["root"]:                                      # корни/капкан: стоит на месте
            return []
        reach = self.paths(u, u.speed)
        good = [p for p in reach if goal_ok(p)]
        if good:
            p = min(good, key=lambda p: (len(reach[p]), score(p)))
        else:
            p = min(reach, key=lambda p: (score(p), len(reach[p])))
        return reach[p]

    def act(self, u):
        it = u.intent or {}
        h = self.hero
        k = it.get("kind")
        if u.ds.get("veil") and k != "veil":                 # туман рассеивается, когда враг действует
            u.ds["veil"] = 0
            self._icons(u)
        if k in ADVANCE and not u.edef.get("keep_range") and not u.ds["root"] and cheb(u.cell, h.cell) > 1 \
                and not (self.idols is not None and h.ds.get("navfog")):     # ближний — наступает в любой ход
            path = self.enemy_move_to(u, lambda p: cheb(p, h.cell) <= 1, lambda p: cheb(p, h.cell))
            yield from self.walk(u, path)
            if not u.alive or self.result:
                return
        if self.idols is not None and h.ds.get("navfog") and k in ("melee", "shot", "pull", "charge", "aim") \
                and cheb(u.cell, h.cell) > 1:                # Велес: туман Нави — потерял Жреца
            self.say(f"{u.name} потерял Жреца в тумане", (170, 210, 170))
            yield WAIT
            return
        if k == "melee":
            blocker = self.garden.blocker_for(u) if self.garden is not None else None
            if blocker is not None:                          # сад загораживает героя — враг рубит его
                self.say(f"{u.name} рубит {blocker.name}", (220, 190, 150))
                yield from self.strike(u, blocker, it.get("dmg", 1))
                yield WAIT
                return
            st = self.desecrate_target(u)
            if st is not None:                               # глушить статую Жреца — вместо удара
                path = self.enemy_move_to(u, lambda p: cheb(p, st.cell) <= 1, lambda p: cheb(p, st.cell))
                yield from self.walk(u, path)
                if u.alive and cheb(u.cell, st.cell) <= 1:
                    st.silence = 1
                    u.desecrated = True
                    self.queue.append(("desecrated", u))
                    self.say(f"{u.name} оскверняет статую: {st.god['name']} молчит ход", (220, 160, 160))
                    self.fx("status", unit=st, el="hex")
                yield WAIT
                return
            walked = 0
            lure = self.board_relics.consume_lure(u)
            if lure is not None:
                yield from self.walk(u, [lure])
                walked = 1
                if not u.alive or self.result:
                    return
            if cheb(u.cell, h.cell) > 1:
                path = self.enemy_move_to(u, lambda p: cheb(p, h.cell) <= 1, lambda p: cheb(p, h.cell))
                path = path[:max(0, u.speed - walked)]
                walked += len(path)
                yield from self.walk(u, path)
            if u.alive and cheb(u.cell, h.cell) <= 1:
                dmg = it["dmg"]
                if walked * 2 > u.speed:                     # с ходу — вполсилы (шаг ИЛИ удар)
                    dmg = max(1, dmg // 2)
                    self.say(f"{u.name} бьёт с ходу — вполсилы", (200, 200, 200))
                self.say(f"{u.name}: {it['name']} {self.hit_value(u, h, dmg)}", (255, 160, 140))
                hp = h.hp
                yield from self.strike(u, h, dmg)
                if u.edef.get("steal") and h.hp < hp and self.draw_pile:      # крадёт карту до своей смерти
                    c = self.draw_pile.pop()
                    u.stolen = getattr(u, "stolen", []) + [c]
                    self.say(f"{u.name} утащил «{c.name}» — убейте, чтобы вернуть", (255, 200, 140))
                    self.fx("curse", unit=u, n=1)
                if it.get("drain") and u.alive and h.hp < hp:          # пьёт кровь
                    amt = min(hp - h.hp, u.max_hp - u.hp)
                    if amt:
                        u.hp += amt
                        self.c.emit("heal", unit=u, amount=amt)
                yield from self.apply(u, it.get("add", []), h)
            else:
                self.say(f"{u.name} не дотянулся", (180, 180, 180))
        elif k == "shot":                                   # стоит и стреляет: в зоне и на виду — попал
            decoy = self.board_relics.take_decoy(u, it)
            if decoy is not None:
                self.say(f"{u.name}: выстрел ушёл в двойника", (190, 220, 255))
                self.zone_fx = ([decoy], 0.5)
                u.ds["aim"] = 1
                yield IMPACT
            elif self.in_fire_zone(u, it):
                dmg = it["dmg"] * u.ds["aim"]
                u.ds["aim"] = 1
                rod = self.rod(h)
                if rod is not None:                          # Перун: выстрел ушёл в статую-громоотвод
                    self.say(f"{u.name}: {it['name']} — ушёл в громоотвод", (190, 220, 255))
                    self.c.emit("attack", src=u, dst=rod, kind="ranged", tag=None)
                    yield IMPACT
                else:
                    self.say(f"{u.name}: {it['name']} {self.hit_value(u, h, dmg)}", (255, 160, 140))
                    yield from self.strike(u, h, dmg, kind="shot")
            else:                                           # вне зоны — перебегает, выстрела нет
                self.say(f"{u.name}: цель вне зоны — перебегает, выстрела нет", (180, 220, 255))
                yield from self.take_firing_spot(u, it.get("range", 5))
        elif k == "zone":
            self.say(f"{u.name}: {it['name']}", (255, 160, 140))
            cells = self.zone_hit_cells(it)
            if it.get("shape") == "cell" and it.get("vfx") == "aimed_shot" and h.cell in cells:
                decoy = self.board_relics.take_decoy(u, it)
                if decoy is not None:
                    self.say(f"{u.name}: выстрел ушёл в двойника", (190, 220, 255))
                    self.zone_fx = ([decoy], 0.5)
                    yield IMPACT
                    return
            self.zone_fx = (list(cells), 0.6)                # вспышка зоны — рисует экран
            if cells and self.vfx(u, it.get("vfx"), it["name"], center=cells[len(cells) // 2], radius=it.get("r", 1)):
                yield IMPACT
            for ballista in self.ballistas:
                if ballista.cell in cells:
                    yield from self.strike(u, ballista, it["dmg"], kind="zone")
            if h.cell in cells:
                yield from self.strike(u, h, it["dmg"], kind="zone")
                yield from self.apply(u, it.get("add", []), h)
            else:
                self.say(f"{h.name}: ушли из зоны", (180, 230, 180))
            if it.get("hazard"):                             # лужи яда, расплав, масло, туман, тернии
                for p in cells:
                    self.set_surface(p, it["hazard"])
        elif k == "block":
            if self.vfx(u, it.get("vfx"), it["name"]):
                yield IMPACT
            u.shield += it["n"]
            self.c.emit("shield", unit=u, amount=it["n"])
            self.say(f"{u.name}: {it['name']} (+{it['n']} защиты)", (200, 200, 230))
        elif k == "aim":
            yield from self.take_firing_spot(u, self.shot_range(u))   # прицел: сперва занять позицию
            if self.vfx(u, it.get("vfx"), it["name"], target=h):
                yield IMPACT
            u.ds["aim"] = it.get("mult", 2)
            self.say(f"{u.name} целится: следующий выстрел ×{u.ds['aim']}", (255, 200, 140))
        elif k == "heal":
            allies = self.foes()
            a = max(allies, key=lambda a: a.max_hp - a.hp)
            amt = min(it["n"], a.max_hp - a.hp)
            if self.vfx(u, it.get("vfx"), it["name"], target=a):
                yield IMPACT
            a.hp += amt
            self.c.emit("heal", unit=a, amount=amt)
            self.say(f"{u.name}: {it['name']} — {a.name} +{amt}", (160, 230, 160))
        elif k == "summon":
            self.summon(u, it)
        elif k == "charge":                                 # рывок по отмеченной линии
            cells = it.get("cells", [])
            self.zone_fx = (list(cells), 0.6)
            path, hit = [], False
            for p in cells:
                if p == h.cell:
                    hit = True
                    break
                if not self.free(p, exclude=u):
                    break
                path.append(p)
            yield from self.walk(u, path)
            if hit and u.alive and cheb(u.cell, h.cell) <= 1 and not self.result:
                self.say(f"{u.name}: {it['name']} {self.hit_value(u, h, it['dmg'])}", (255, 160, 140))
                yield from self.strike(u, h, it["dmg"])
                if it.get("push"):
                    yield from self.push(u, h, it["push"])
            else:
                self.say(f"{u.name}: {it['name']} — мимо", (180, 220, 255))
        elif k == "pull":                                   # утягивание: дальность и линия обзора
            if self.in_fire_zone(u, it):
                self.say(f"{u.name}: {it['name']}", (255, 160, 140))
                yield from self.strike(u, h, it["dmg"], kind="shot")
                if h.alive:
                    yield from self.push(u, h, it.get("n", 2), toward=True)
            else:
                self.say(f"{u.name}: не дотянулся — подходит", (180, 220, 255))
                yield from self.take_firing_spot(u, it.get("range", 4))
        elif k == "guard":
            if self.vfx(u, it.get("vfx"), it["name"]):
                yield IMPACT
            self.guard_allies(u, it)
        elif k == "rally":
            if self.vfx(u, it.get("vfx"), it["name"]):
                yield IMPACT
            self.rally(u, it)
        elif k == "veil":
            u.ds["veil"] = 1
            self.fx("status", unit=u, el="veil")
            self.say(f"{u.name}: {it['name']} — не достать издали", (190, 190, 220))
            self._icons(u)
        elif k == "curse":                                  # «Тина» в сброс
            for _ in range(it.get("n", 1)):
                self.discard.append(M.Card(it.get("card", "slime_rot"), self.run.defs))
            self.fx("curse", unit=u, n=it.get("n", 1))
            self.say(f"{u.name}: {it['name']} (+{it.get('n', 1)} в сброс)", (200, 170, 255))
        elif k == "hex":
            if self.vfx(u, it.get("vfx"), it["name"]):
                yield IMPACT
            h.ds["hex"] += it.get("n", 1)
            if it.get("weak") and cheb(u.cell, h.cell) <= it.get("r", 3):
                h.ds["weak"] += it["weak"]
            self.fx("status", unit=h, el="hex")
            self.say(f"{u.name}: {it['name']} — на следующий ход меньше карт", (200, 160, 255))
            self._icons(h)
        elif k == "drown":                                  # утащить карты из колоды до конца боя
            gone = []
            for _ in range(it.get("n", 1)):
                if self.draw_pile:
                    c = self.draw_pile.pop(self.rng.randrange(len(self.draw_pile)))
                    self.exhaust.append(c)
                    gone.append(c.name)
            self.fx("curse", unit=u, n=len(gone))
            self.say(f"{u.name}: {it['name']}" + (f" — {', '.join(gone)}" if gone else ""), (200, 170, 255))
        elif k == "roar":
            if self.vfx(u, it.get("vfx"), it["name"]):
                yield IMPACT
            self.fx("roar", unit=u, r=it.get("r", 3))
            if cheb(u.cell, h.cell) <= it.get("r", 3):
                h.ds["weak"] += it.get("weak", 1)
                self.say(f"{u.name}: {it['name']} — слабость {it.get('weak', 1)}", (255, 180, 140))
            self._icons(h)
        keep = u.edef.get("keep_range", 0)
        if keep and k not in ("melee", "shot", "aim", "pull", "charge") and u.alive and cheb(u.cell, h.cell) < keep and not self.result:
            path = self.enemy_move_to(u, lambda p: cheb(p, h.cell) >= keep, lambda p: -cheb(p, h.cell))
            yield from self.walk(u, path)
        yield WAIT

    # ---------- итог ----------

    def finish_into_run(self):
        """Итог боя — в забег: HP героя."""
        self.hand_relics.clear_fleeting()
        self.run.hp = max(0, self.hero.hp)
        for card in self.run.deck:
            card.linked_spent = False
