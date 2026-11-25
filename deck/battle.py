"""Бой «Спуска» (docs/descent.md §2): ход игрока — 3 энергии и 5 карт; у карты основное применение за энергию и
простое за 0; враги заранее показывают намерения (удар, выстрел по обзору, зона, защита, лечение, рёв).

Поле и фигурки — sim.combat.Combat (клетки, юниты, события для ui.battle_view), но его шаги не идут. Всё, что
двигает фигурки, — генераторы: после каждого шага они отдают ("wait", сек), экран ждёт анимацию; в тестах
генератор просто прокручивается до конца (finish).
"""
import copy
import random

from sim.combat import ENEMY, PLAYER, Combat
from sim.grid import DIRS8, cheb, sign

from . import model as M
from .idols import IdolCast, Idols
from .items import Items


WAIT = ("wait", 0.0)
IMPACT = ("impact", 0.0)     # экран: проиграть выпущенный эффект и ждать попадания — урон применится после
STEP_T = 0.2                     # длительность шага фигурки (по прямой; разгон и торможение — вдвое дольше)
COLLIDE = 3                      # урон столкновения за каждую невыполненную клетку толчка
ONCE = {"burn_all", "block", "heat", "draw", "energy", "heal", "lose_hp", "strength", "collide_x2", "thorns", "cleanse", "rage",
        "keep_momentum", "momentum", "ranged_bonus", "focus", "heat_regen", "add_card", "ignite", "trap", "detonate",
        "counter", "burn_card", "strength_x2", "fort", "double_next", "next_energy", "next_draw", "add_random", "resource"}
HAND_MAX = 10
COUNTER = 4                      # Контратака: ответный удар (+ Мощь)
ADVANCE = {"block", "guard", "rally", "roar", "summon", "curse", "hex", "drown", "heal", "veil"}   # и шагают
PRIEST_HAND = 5                  # Жрец: несыгранные свитки остаются в руке — до 5 (карты «толстые»)
PRIEST_WALK = 3                  # Жрец: шагов за ход (сам он только ходит)


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
        self.prey = None                                  # Охотница «Метка добычи»
        if self.mech == "heat":
            self.hero.ds["heat"] = self.hero_def.get("heat_start", 2)
        if self.mech == "hunter" and self.variant == "mark":
            self.mark_prey()
        self.draw_pile = list(run.deck)
        self.rng.shuffle(self.draw_pile)
        self.hand, self.used, self.discard, self.exhaust = [], [], [], []
        self.turn = 0
        self.result = None
        self.log = []
        self.collide_k = 1
        self.played = 0                                   # основных розыгрышей за ход (синергии)
        self.turn_tags = []                               # теги сыгранных основным за ход — по порядку
        self.walked = 0                                   # клеток героем за ход (С разбега)
        self.echoed = set()                               # Отклик/Цепочка: какие карты уже сработали в этот ход
        self._free_cast = False                           # Цепочка: карта играется без стоимости
        self.chain_drawn = 0                              # Цепная реакция Охотницы: добор за цепочки
        self.queue = []                                   # события для Отклика: (вид, юнит)
        self.guard = []                                   # карты, ждущие в руке ход врага (отклик на события)
        self.empower = {}                                 # «Следующая карта [Тег]»: бонус урона
        self.temper = {}                                  # Закалка: uid карты → прибавка до конца боя
        self._mom = None                                  # разгон на момент розыгрыша (для условия «Разгон N»)
        self.zone_fx = None
        self.env = dict(fight.get("env") or {})              # природа боя: ветер / лавовый дождь (умеренно)
        self.env_now = None                                   # что природа сделает в этот ход врагов
        self.items = Items(self)                              # предметы забега (data/deck/relics.json, deck/items.py)
        self.double_next = False                              # предмет: следующая атака — двойной урон
        self.next_energy = self.next_draw = 0                 # предмет: прибавка к следующему ходу
        self.pending_discard = 0                              # Адажио: сколько карт игрок должен выбрать для сброса
        self.double_attacks = 0                               # улучшение: сколько атак ещё удвоить
        self.powers = []                                      # сыгранные карты-Силы: действуют до конца боя
        self.powered = set()                                  # (uid Силы, ход, событие) — у Сил «раз за ход»
        self.idols = Idols(self) if self.mech == "idols" else None    # Жрец: статуи богов падают на поле
        self.walk_max = PRIEST_WALK if self.idols else 0
        self.walk_left = 0
        self.battle_start_mods()
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
                "veil": 0, "hex": 0, "fort": 0, "bleed": 0, "counter": 0, "hunt": 0}
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

    def vfx(self, u, sid, name, target=None, center=None, radius=0, tag=None):
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
        self.c.emit("skill", unit=u, skill=sid, center=tuple(c), target=target, auto=False)
        return True

    def foes(self):
        return [u for u in self.c.units if u.team == ENEMY and u.alive and not u.obj]

    def say(self, text, col=(220, 210, 190)):
        self.log.append((text, col))
        self.log = self.log[-40:]

    # ---------- поле ----------

    def free(self, p, exclude=None):
        cell = self.c.grid.get(p)
        if cell is None or not cell.passable:
            return False
        return all(not (v.alive and v.cell == p and v is not exclude and not v.obj) for v in self.c.units) and \
            not any(v.alive and v.obj and v.cell == p for v in self.c.units)

    def paths(self, u, limit):
        """Клетки, куда u дойдёт за limit шагов: {клетка: путь}."""
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

    def los(self, a, b):
        for p in bresenham(a, b)[1:-1]:
            cell = self.c.grid.get(p)
            if cell is not None and not cell.passable and cell.cover == "full":
                return False
        return True

    def walk(self, u, path):
        n = len(path)
        for i, p in enumerate(path):
            if not u.alive or self.result:
                return
            near = u.team == ENEMY and cheb(u.cell, self.hero.cell) <= 1
            # путь — одним движением: разгон на первой клетке, торможение на последней, между — ровно
            ease = "inout" if n == 1 else "in" if i == 0 else "out" if i == n - 1 else "lin"
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
                if self.powers:
                    yield from self.power_fire("step")
                yield from self.items.fire("step")
            if u is self.hero and self.mech == "momentum" and not self.enemy_phase:     # Разгон: шаг — +1
                u.ds["momentum"] = min(self.hero_def.get("momentum_max", 5), u.ds["momentum"] + 1)
                self.fx("momentum_step", unit=u, n=u.ds["momentum"])
            if u.team == ENEMY and p in self.traps and u.alive:                            # капкан Охотницы
                dmg = self.traps.pop(p)
                self.say(f"{u.name} попал в капкан: −{dmg}, встал", (255, 220, 140))
                self.hurt(u, dmg, self.hero, "trap")
                u.ds["root"] = max(u.ds["root"], 1)
                self.queue.append(("trap", u))
                return

    SURFACES = ("fire", "poison", "oil", "fog", "briar", "cracks")

    def set_surface(self, p, kind, n=1):
        """Покрытие клетки (docs/descent_field.md 1.2): огонь, яд, масло, туман, тернии, трещины (заряд копится).
        Огонь на масле — вспышка радиус 1; огонь на воде — пар (туман); вода гасит огонь."""
        cell = self.c.grid.get(p)
        if cell is None or not cell.passable:
            return
        if kind == "fire" and cell.terrain == "water":
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
            if kind == "melee" and u.ds["counter"] > 0 and cheb(src.cell, u.cell) <= 1:   # Контратака: ответ
                self.queue.append(("counter", src))
        if u.hp <= 0 and u.team == ENEMY and src is self.hero:
            self.queue.append(("kill", u))
        self.c.emit("damage", unit=u, amount=v, absorbed=absorbed,
                    kind={"burn": "dot", "poison": "dot", "bleed": "dot"}.get(
                        kind, "melee" if kind in ("melee", "thorns", "collision") else "ranged" if kind == "shot"
                        else "spell"),
                    tag={"burn": "fire", "poison": "poison", "bleed": "bleed"}.get(kind), cover=False, blocked=None)
        if u.hp <= 0:
            self.die(u)
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

    def die(self, u):
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
            (self.hand if len(self.hand) < HAND_MAX else self.discard).append(c)
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
            self.result = "victory"

    def mark_prey(self):
        foes = self.foes()
        self.prey = min(foes, key=lambda f: (cheb(f.cell, self.hero.cell), f.hp)) if foes else None

    def push(self, src, tgt, n, toward=False, d=None):
        """Толчок (или притягивание): по клетке; упёрся — столкновение, урон обоим (стена — только цели).
        По льду и маслу цель скользит дальше (до 3 клеток сверх). d — направление сразу (ветер)."""
        if not tgt.alive or tgt.obj:
            return
        if d is None:
            d = (sign(src.cell[0] - tgt.cell[0]), sign(src.cell[1] - tgt.cell[1])) if toward else \
                (sign(tgt.cell[0] - src.cell[0]), sign(tgt.cell[1] - src.cell[1]))
        if d == (0, 0):
            return
        slid = 0
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
                return
            self.c._place(tgt, nxt, STEP_T)
            yield ("wait", 0.0)
            self._enter(tgt, nxt)
            if k == n and slid < 3 and not toward and self.slippery(nxt) and tgt.alive:   # скользит дальше
                n += 1
                slid += 1
                if slid == 1:
                    self.say(f"{tgt.name} скользит", (180, 220, 255))

    # ---------- ход игрока ----------

    def start_player_turn_now(self):
        finish(self.start_player_turn())

    def start_player_turn(self):
        self.turn += 1
        h = self.hero
        for u in self.foes():
            self.choose_intent(u)
        h.shield = h.shield // 2 if h.ds.get("fort") else 0          # «Оборона»: половина защиты остаётся
        h.ds["fort"] = 0
        self.collide_k = 1
        self.discard += self.used                            # остатки Used (отклики врага) — в сброс
        self.used = []
        self.played = 0
        self.turn_tags, self.walked, self.echoed = [], 0, set()
        self.chain_drawn = 0
        self.empower = {}
        for c in self.guard:                                             # ждали ход врага и не сработали — в сброс
            if c in self.hand:
                self.hand.remove(c)
                self.discard.append(c)
        self.guard = []
        self.items.new_turn()
        self.energy = self.max_energy + h.ds["rage"] + self.next_energy
        if self.mech == "heat":                                          # жар: +1 за ход (и от Сердца феникса)
            hd = self.hero_def
            h.ds["heat"] = min(hd.get("heat_max", 12), h.ds["heat"] + hd.get("heat_turn", 1) + h.ds["heat_regen"] +
                               self.items.mod("energy") + self.next_energy)
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
        if self.mech == "hunter" and self.variant == "quiver":           # Колчан: стрела в руку
            self.add_tokens("arrow", 1)
        self.sync_levels()

    def draw(self, n):
        for _ in range(n):
            if not self.draw_pile:
                if not self.discard:
                    return
                self.draw_pile = self.discard
                self.discard = []
                self.rng.shuffle(self.draw_pile)
                self.queue.append(("shuffle", None))
            if len(self.hand) >= (PRIEST_HAND if self.idols is not None else HAND_MAX):
                return
            c = self.draw_pile.pop()
            if c.d.get("unique") and self.has_unique():           # Единственная: вторая — под низ колоды
                self.draw_pile.insert(0, c)
                if all(x.d.get("unique") for x in self.draw_pile):
                    return
                continue
            c.manual = False
            self.hand.append(c)

    def has_unique(self):
        return any(c.d.get("unique") for c in self.hand)

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

    def add_tokens(self, cid, n, force=False):
        """Создать карту: временные карты в руку (после розыгрыша — Изгнание)."""
        for _ in range(n):
            if force or len(self.hand) < HAND_MAX:
                c = M.Card(cid, self.run.defs)
                if c.d.get("unique") and self.has_unique():
                    continue
                c.manual = False
                self.hand.append(c)
                self.fx("created", unit=self.hero, uid=c.uid)
                self.queue.append(("create", c))

    def pay_pool(self, card):
        """Чем платят за карту: жаром (карты с уровнями) или энергией."""
        return "heat" if card.levels else "energy"

    def can_afford(self, card):
        if self._free_cast:
            return True
        if card.d.get("x_cost"):
            return self.energy >= 1
        if card.levels:
            return self.hero.ds["heat"] >= card.cost
        return self.energy >= card.cost

    def sync_levels(self):
        """Уровень карт с жаром: сам — высший, на который хватает (если игрок не выбрал колесом)."""
        heat = self.hero.ds["heat"]
        for c in self.hand:
            lv = c.levels
            if lv and not getattr(c, "manual", False):
                ok = [i for i, L in enumerate(lv) if L["heat"] <= heat]
                c.lvl = ok[-1] if ok else 0

    def targets(self, card, mode, auto=False):
        """Куда можно сыграть: список юнитов или клеток (для self — [герой]). Пусто — нельзя."""
        if self.result:
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
        if t == "statue":                                 # свиток Жреца — на статую, где бог может исполнить смысл
            if self.idols is None:
                return []
            m = card.d["meaning"]                         # заглушённой статуе — только Движение (отогнать)
            return [s for s in self.idols.statues if (m == "move" or not self.idols.silenced(s))
                    and self.idols.can_cast(s, m)]
        if t == "self":
            return [h]
        if t == "enemy":                                  # в тумане — только вплотную
            r = u.get("range", 1)
            out = [f for f in self.foes() if cheb(h.cell, f.cell) <= r and (r <= 1 or not u.get("los", r > 1)
                                                                            or self.los(h.cell, f.cell))
                    and not (f.ds.get("veil") and cheb(h.cell, f.cell) > 1)]
            if u.get("line"):                             # только горизонталь/вертикаль
                out = [f for f in out if h.cell[0] == f.cell[0] or h.cell[1] == f.cell[1]]
            return out
        if t == "reach":
            reach = self.paths(h, u.get("reach", 1))
            return [f for f in self.foes() if any(cheb(p, f.cell) <= 1 for p in reach)]
        if t == "cell_step":
            return [p for p in self.paths(h, u.get("step", 1)) if p != h.cell]
        if t == "area":
            r = u.get("range", 5)
            return [p for p, c in self.c.grid.cells.items() if c.passable and cheb(p, h.cell) <= r
                    and self.los(h.cell, p)]
        if t == "cell_any":
            r = u.get("range", 4)
            return [p for p, c in self.c.grid.cells.items() if c.passable and 0 < cheb(p, h.cell) <= r
                    and self.free(p) and self.los(h.cell, p)]
        if t == "cell_dash":
            out = []
            for d in DIRS8:
                p = h.cell
                for _ in range(u.get("dash", 1)):
                    q = (p[0] + d[0], p[1] + d[1])
                    if not self.free(q, exclude=h):
                        break
                    if d[0] and d[1] and not (self.free((p[0] + d[0], p[1])) and self.free((p[0], p[1] + d[1]))):
                        break
                    out.append(q)
                    p = q
            return out
        return []

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
        u = card.d[mode]
        t = u["target"]
        h = self.hero
        cells = self.c.grid.cells
        if t == "enemy":
            r = u.get("range", 1)
            need = r > 1 and u.get("los", r > 1)
            out = [p for p, c in cells.items() if 0 < cheb(p, h.cell) <= r and c.passable
                   and (not need or self.los(h.cell, p))]
            if u.get("line"):
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
            return [p for p in self.paths(h, u.get("step", 1)) if p != h.cell]
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

    def met(self, c, tgt=None, before=None):
        """Выполнено ли условие c. tgt — цель (для условий по цели); before — сколько сыграно до этой карты
        (во время розыгрыша; иначе — сейчас)."""
        k = c["k"]
        h = self.hero
        played = self.played if before is None else before
        log = self.turn_tags[:played]
        if k == "series":
            return played >= c["n"]
        if k == "after":
            return bool(log) and c["tag"] in log[-1]
        if k == "resonance":
            return sum(c["tag"] in t for t in log) >= c["n"]
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
                if not ch or c.uid in self.echoed or not self.met(ch["when"]):
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
            return None
        finally:
            self._free_cast = old

    def react(self):
        """Отклик на события (убийство, получил удар, враг вплотную): разобрать очередь."""
        while self.queue and not self.result:
            kind, src = self.queue.pop(0)
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
            if pw.get("tag") and (card is None or pw["tag"] not in card.tags):
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
            for t in tgts:
                yield from self.apply(h, pw.get("do", []), t, {"before": self.played})

    def exhaust_card(self, card):
        """Изгнание: карта уходит до конца боя (не временная — будит Силы «при изгнании»)."""
        self.exhaust.append(card)
        if not card.d.get("token"):
            self.fx("exhaust", unit=self.hero, uid=card.uid)
            yield from self.power_fire("exhaust", card=card)
            yield from self.items.fire("exhaust", card=card)

    def per_count(self, per, tgt, ctx):
        """«За каждую…»: сколько раз прибавить шаг масштабирования."""
        h = self.hero
        w = per["what"]
        before = ctx.get("before")
        before = self.played if before is None else before
        if w == "played":
            return before
        if w.startswith("tag:"):
            return sum(w[4:] in t for t in self.turn_tags[:before])
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
        for _ in range(max(1, rng)):
            p = (p[0] + dx, p[1] + dy)
            cell = self.c.grid.get(p)
            if cell is None or not cell.passable:
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
        """Сыграть карту из руки: mode "main" (энергия, копит прозрение) или "alt" (бесплатно).
        free — Цепочка: полный розыгрыш без оплаты; auto — автоматическая карта в конце хода."""
        if card not in self.hand:
            return
        if card.d.get("auto_end") and not auto:
            return
        if card.d[mode].get("target") == "statue":            # свиток Жреца: через статую бога
            yield from self.play_scroll(card, target)
            return
        if self.is_spot(target):                              # подойти на выбранную клетку и ударить
            spot, foe = target
            if foe not in self.reach_spots(card, mode).get(spot, []):
                return
        elif target not in self.targets(card, mode, auto=auto):
            return
        u = card.d[mode]
        self.hand.remove(card)
        paid, mom0 = card.cost, self.hero.ds["momentum"]
        x_paid = 0
        if mode == "main":
            if not free:
                if card.d.get("x_cost"):
                    x_paid = self.energy
                    paid = x_paid
                    self.energy = 0
                elif card.levels:
                    self.hero.ds["heat"] -= card.cost
                else:
                    self.energy -= card.cost
            card.uses += 1
            self.try_insight(card)
            before = self.played
            self.played += 1
            self.say(f"{card.name}: {card.text('main')}", (255, 230, 160))
        else:
            self.say(f"{card.name} (просто): {card.text('alt')}", (200, 200, 180))
        h = self.hero
        t = u["target"]
        if t == "reach":                                      # подойти к врагу — на выбранную клетку или ближе всего
            reach = self.paths(h, u.get("reach", 1))
            if self.is_spot(target):
                best, target = target
            else:
                best = min((p for p in reach if cheb(p, target.cell) <= 1), key=lambda p: len(reach[p]))
            yield from self.walk(h, reach[best])
        elif t == "cell_step":
            yield from self.walk(h, self.paths(h, u.get("step", 1))[target])
        elif t == "cell_dash":
            d = (sign(target[0] - h.cell[0]), sign(target[1] - h.cell[1]))
            path = []
            p = h.cell
            while p != target:
                p = (p[0] + d[0], p[1] + d[1])
                path.append(p)
            yield from self.walk(h, path)
        tgt = target if hasattr(target, "cell") and target is not h else None
        ctx = {"ranged": u.get("ranged", False), "center": target if isinstance(target, tuple) else None,
               "push_bonus": 0, "tag": u.get("tag"), "card": card if mode == "main" else None,
               "x": x_paid}
        if mode == "main":
            conds = list(u.get("if", []))
            echo = card.d.get("echo") or {}
            if echo.get("when", {}).get("k") == "resonance":
                conds.append({"when": echo["when"], "repeat": 1})     # резонанс = повтор розыгрыша
            ctx["conds"], ctx["before"] = conds, before
            self._mom = h.ds["momentum"]
            ctx["emp"] = sum(self.empower.pop(tg, 0) for tg in card.tags)      # «Следующая карта [Тег]»
            ctx["temper"] = self.temper.get(card.uid, 0)
        ops = u.get("do", [])
        if u.get("vfx"):                                      # свой эффект карты (по уровню у Пиромантки)
            ctx["vfx"] = True
            self.vfx(h, u["vfx"], card.name, target=tgt, center=ctx["center"],
                     radius=u.get("radius", 0) if t == "area" else 0, tag=u.get("tag"))
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
                       if self.met(c["when"], tgt, before) and (c.get("repeat") or c["when"].get("k") == "resonance"))
        for rep in range(reps):                              # Близнец: дважды
            if rep and (self.result or (tgt is not None and not tgt.alive)):
                break
            if rep and u.get("vfx"):                          # второй раз — снова эффект и попадание
                self.vfx(h, u["vfx"], card.name, target=tgt, center=ctx["center"],
                         radius=u.get("radius", 0) if t == "area" else 0, tag=u.get("tag"))
                yield IMPACT
            if u.get("pierce") and tgt is not None:           # линия: пробивает всех на пути
                for f in self.line_enemies(tgt, u.get("range", 6)):
                    yield from self.apply(h, [o for o in ops if o["op"] not in ONCE], f, ctx)
                    yield from self.cond_extras(ctx, f, area=True)
                yield from self.apply(h, [o for o in ops if o["op"] in ONCE], None, ctx)
            elif t == "area":                                # область: каждому врагу в радиусе
                r = u.get("radius", 1)
                for f in [f for f in self.foes() if cheb(f.cell, target) <= r]:
                    yield from self.apply(h, [o for o in ops if o["op"] not in ONCE], f, ctx)
                    yield from self.cond_extras(ctx, f, area=True)
                yield from self.apply(h, [o for o in ops if o["op"] in ONCE], None, ctx)
            else:
                yield from self.apply(h, ops, tgt, ctx)
                yield from self.cond_extras(ctx, tgt)
        if mode == "main":
            yield from self.hunt_followup(card, tgt)
        card.manual = False
        back = False
        if mode == "main":
            self.turn_tags.append(set(card.tags))
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
            yield from self.react()
        if back:                                              # Возврат: снова в руке
            self.hand.append(card)
            self.say(f"Возврат: {card.name} снова в руке", (170, 255, 170))
        elif mode == "main" and u.get("power"):               # Сила: действует до конца боя
            self.powers.append(card)
            self.items.turn_types.append("power")
            self.say(f"Сила: {card.name} — до конца боя", (210, 170, 255))
            self.fx("power", unit=h, uid=card.uid, name=card.name)
        elif card.d.get("token") or (mode == "main" and card.d.get("exhaust")):
            yield from self.exhaust_card(card)
        else:
            self.used.append(card)                            # CZN: до конца хода — в Used, не в Discard
        if mode == "main" and not self.result:                # предметы: что сыграно (после розыгрыша — рука видна)
            yield from self.items.fire("play", card=card, tgt=tgt, mom=mom0, heat=paid if card.levels else 0)
            yield from self.react()
        self.sync_levels()

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
        if tgt is None or not getattr(tgt, "alive", False) or "Преследование" not in card.tags:
            return
        n = self.hero.ds.get("hunt", 0)
        if n <= 0 or not self.is_attack(card, "main"):
            return
        self.say(f"Преследование: {card.name} — ещё {n}", (255, 210, 120))
        self.fx("react", unit=tgt, what="shot")
        yield from self.strike(self.hero, tgt, n, kind="shot" if card.d["main"].get("ranged") else "melee",
                               tag="Преследование")

    def play_scroll(self, card, target):
        """Свиток через статую: target — IdolCast(статуя, цель). Бесплатно; добил с Мёртвой водой — в руку."""
        idols = self.idols
        if idols is None or not isinstance(target, IdolCast) or target.statue not in idols.statues:
            return
        m = card.d["meaning"]
        ch = idols.choices(target.statue, m)
        if ch is not None and target.tgt not in ch:
            return
        self.hand.remove(card)
        card.uses += 1
        self.try_insight(card)
        self.played += 1
        yield from idols.cast_card(target.statue, card, target.tgt)
        self.items.scrolls[id(target.statue)] = self.items.scrolls.get(id(target.statue), 0) + 1
        yield from self.items.fire("scroll", card=card, statue=target.statue)
        if idols.killed and idols.dead_water:
            idols.dead_water = False
            self.hand.append(card)
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

    def cond_extras(self, ctx, tgt, area=False):
        """Усиление: действия условий («В окружении: защита 4») — после основных."""
        h = self.hero
        for c in ctx.get("conds", []):
            if c["when"].get("k") == "resonance":
                continue                         # у резонанса нет отдельного эффекта
            if c.get("do") and self.met(c["when"], tgt, ctx.get("before")):
                ops = [o for o in c["do"] if not area or o["op"] not in ONCE]
                yield from self.apply(h, ops, tgt, dict(ctx, conds=[]))

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
               "x": self.energy if card.d.get("x_cost") and mode == "main" else 0}
        if mode == "main":
            ctx["temper"] = self.temper.get(card.uid, 0)
            ctx["emp"] = sum(self.empower.get(tag, 0) for tag in card.tags)
        emp, mom, focus, dbl = ctx["emp"], (ds["momentum"] if self.mech == "momentum" else 0), \
            bool(ds["focus"]), bool(self.double_next and mode == "main")
        out = []
        for op in u.get("do", []):
            kind = op.get("op")
            if kind not in ("damage", "body_slam"):
                continue
            n = h.shield if kind == "body_slam" else op.get("n", 0)
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
                if self.variant == "ash" and "Область" in card.tags:
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
        """Игрок выбрал карты для сброса (Адажио/подобные эффекты)."""
        n = 0
        for c in list(cards):
            if self.pending_discard <= 0:
                break
            if c in self.hand:
                self.hand.remove(c)
                self.discard.append(c)
                self.pending_discard -= 1
                n += 1
        if n:
            self.say(f"Сброшено карт: {n}", (220, 210, 180))
        if not self.hand:
            self.pending_discard = 0
        self.sync_levels()

    def apply(self, src, ops, tgt, ctx=None):
        ctx = ctx if ctx is not None else {}
        h = self.hero
        emp = ctx.get("emp", 0) if src is h else 0          # «Следующая карта»: к первому удару по цели
        for op in ops:
            if self.result and op["op"] not in ("block",):
                return
            k = op["op"]
            n = op.get("n", 0)
            if op.get("per") and src is h:                                  # «за каждую…»
                n += op["per"].get("k", 1) * self.per_count(op["per"], tgt, ctx)
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
                        if (c.get("plus") or c.get("mult")) and self.met(c["when"], tgt, ctx.get("before")):
                            n = (n + c.get("plus", 0)) * c.get("mult", 1)
                    n += self.items.card_bonus(ctx.get("card"), "damage")   # предметы: карты тега сильнее
                    if self.variant == "ash" and ctx.get("card") is not None and "Область" in ctx["card"].tags:
                        n += 2                                              # Пепел: области сильнее
                    if self.double_next and ctx.get("card") is not None:     # предмет: двойной урон (итоговый)
                        dbl = 2
                        self.double_next = False
                        self.say("Двойной урон!", (255, 220, 120))
                yield from self.strike(src, tgt, n, kind="shot" if ctx.get("ranged") else "melee",
                                       el=op.get("el"), anim=not ctx.get("vfx"), tag=ctx.get("tag"), mult=dbl)
            elif k == "body_slam" and tgt is not None:
                n = self.hero_bonus(tgt, src.shield, op, ctx) if src is h else src.shield
                if src is h:
                    n += self.items.card_bonus(ctx.get("card"), "damage")
                dbl = 1
                if src is h and ctx.get("card") is not None and ctx["card"].d.get("type") == "attack":
                    if not ctx.get("double_done") and self.double_attacks > 0:
                        ctx["double_done"] = True
                        self.double_attacks -= 1
                        self.say("Двойной залп!", (255, 220, 120))
                    if ctx.get("double_done"):
                        dbl = 2
                yield from self.strike(src, tgt, n, anim=not ctx.get("vfx"), mult=dbl)
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
            elif k == "next_draw":
                self.next_draw += n
            elif k == "add_random":                                        # случайные карты героя — только на бой
                pool = [cid for cid in self.hero_def.get("rewards", []) if cid in self.run.defs]
                for _ in range(n):
                    if pool and len(self.hand) < HAND_MAX:
                        self.hand.append(M.Card(self.rng.choice(pool), self.run.defs))
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
                    cur = min(nxt, key=lambda f: cheb(f.cell, cur.cell))
                    hit.add(cur)
                    self.fx("react", unit=cur, what="shock")
                    self.hurt(cur, self.attack_value(h, n) if src is h else n, src, "spell")
            elif k == "block":
                if op.get("mom_k") and src is h:                           # Резкая остановка: разгон — в защиту
                    n += src.ds["momentum"] * op["mom_k"]
                    src.ds["momentum"] = 0
                if src is h:
                    n += ctx.get("temper", 0)
                    n += self.items.card_bonus(ctx.get("card"), "block")
                src.shield += n
                self.c.emit("shield", unit=src, amount=n)
            elif k in ("push", "pull") and tgt is not None:
                yield from self.push(src, tgt, n + (ctx.get("push_bonus", 0) if k == "push" else 0), toward=k == "pull")
                if k == "push" and src is h and self.variant == "press":
                    src.ds["momentum"] = min(self.hero_def.get("momentum_max", 5), src.ds["momentum"] + 1)
            elif k == "retreat" and tgt is not None:                       # отскок от цели
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
                tgt.ds["root"] = max(tgt.ds["root"], n)
                self.say(f"{tgt.name}: корни — не двигается", (180, 230, 140))
            elif k == "add_card":
                self.add_tokens(op.get("card", "arrow"), n, force=bool(op.get("force")))
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
            elif k == "trap" and ctx.get("center"):
                self.traps[ctx["center"]] = n
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
            elif k == "empower":
                self.empower[op["tag"]] = self.empower.get(op["tag"], 0) + n
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
                tgt.ds[k] += n
            elif k == "stun" and tgt is not None:
                tgt.ds["stun"] = True
                self.say(f"{tgt.name} оглушён — пропустит намерение", (255, 230, 140))
            elif k == "mark" and tgt is not None:
                tgt.ds["mark"] += n
            elif k == "hunt" and src is h:
                src.ds["hunt"] = min(5, src.ds.get("hunt", 0) + n)
                self.say(f"Преследование +{n}", (255, 220, 120))
            elif k == "draw":
                self.draw(n)
            elif k == "discard_choose":
                self.pending_discard += max(0, n)
                self.say(f"Выберите {self.pending_discard} карт(ы) для сброса", (220, 210, 180))
            elif k == "energy":
                self.energy += n
            elif k == "heal":
                src.hp = min(src.max_hp, src.hp + n)
                self.c.emit("heal", unit=src, amount=n)
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
                for f in [f for f in self.foes() if cheb(f.cell, src.cell) <= op.get("r", 1)]:
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
                    self.discard.append(c)
                continue
            yield from self.play(c, "main", target, free=True, auto=True)
            if self.result:
                return

    def end_turn(self):
        """Конец хода игрока: рука в сброс, враги исполняют намерения, начинается новый ход."""
        if self.result:
            return
        h = self.hero
        if self.mech == "heat":                                          # перегрев: ожог за каждую единицу сверх
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
        for c in list(self.hand):                         # заряжающиеся стрелы растут в руке
            g = c.d.get("grow_end")
            if g:
                n = int(g.get("n", 1))
                self.temper[c.uid] = self.temper.get(c.uid, 0) + n
                self.say(f"«{c.name}»: +{n} урона", (255, 220, 120))
        yield from self.auto_end_turn()
        if self.result:
            return
        self.discard += self.used                            # CZN: Used → Discard только в конце хода
        self.used = []
        kept = [c for c in self.hand if (c.d.get("keep") and self.met(c.d["keep"])) or c.d.get("retain")
                or self.has_mod("retain") or self.items.mod("retain_all")]    # Задел / Сохранение
        if self.idols is not None:                            # Жрец: несыгранные свитки остаются
            kept = [c for c in self.hand if not c.d.get("token")][:PRIEST_HAND]
        for c in kept:
            self.say(f"Задел: {c.name} остаётся в руке", (170, 255, 170))
        self.guard = [c for c in self.hand if c not in kept and (c.d.get("echo") or {}).get("on")]
        kept += self.guard                                  # отклик на ход врага — ждёт в руке
        self.discard += [c for c in self.hand if not c.d.get("token") and c not in kept]   # стрелы не копятся
        self.hand = kept
        self.tick_end(self.hero)
        if self.idols is not None:                            # статуи играют свои свитки, призванные — ход
            yield from self.idols.end_of_turn()
            if self.result:
                return
        self.enemy_phase = True
        yield from self.env_resolve()
        if self.result:
            return
        for u in list(self.foes()):
            if self.result:
                return
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
            return self.hit_value(u, self.hero, it["dmg"]) if self.hero.cell in it.get("cells", []) else 0
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
            if cheb(u.cell, h.cell) > 1:
                path = self.enemy_move_to(u, lambda p: cheb(p, h.cell) <= 1, lambda p: cheb(p, h.cell))
                walked = len(path)
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
            if self.in_fire_zone(u, it):
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
            self.zone_fx = (list(it["cells"]), 0.6)          # вспышка зоны — рисует экран
            mid = it["cells"][len(it["cells"]) // 2]
            if self.vfx(u, it.get("vfx"), it["name"], center=mid, radius=it.get("r", 1)):
                yield IMPACT
            if h.cell in it["cells"]:
                yield from self.strike(u, h, it["dmg"], kind="zone")
                yield from self.apply(u, it.get("add", []), h)
            else:
                self.say(f"{h.name}: ушли из зоны", (180, 230, 180))
            if it.get("hazard"):                             # лужи яда, расплав, масло, туман, тернии
                for p in it["cells"]:
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
        self.run.hp = max(0, self.hero.hp)
