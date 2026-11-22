"""Предметы «Спуска» (квиз 2026-11-21) — как реликвии Slay the Spire: лежат в сумке весь забег и срабатывают
только при условии, которое в обычной игре выполняется редко (счётчики, «3-й ход», «ход без атак», «HP ниже
половины»…). Данные — data/deck/relics.json (пишет tools/descent_items.py).

Предмет: {id, name, icon, rarity: common|uncommon|rare|boss|shop, hero?, about, on, …фильтры, do, aim}.
  on     — событие боя: battle, turn, play, kill, hit, exhaust, create, shuffle, step, end, hp_low, last_foe,
           trap, counter, scroll, desecrated, chain.
  фильтры: tag / type / card (что сыграно), turn (номер хода), every (каждые N ходов), when — список проверок
           состояния (no_attack, played_max, hand_min, hand_empty, shield_min, not_walked, hp_below, trio,
           victim_bleed, victim_burn, momentum_min, far, heat_min, foes_min), count+scope — счётчик (run | battle
           | turn): срабатывает на N-й раз и обнуляется; once — раз за turn | battle | run.
  aim    — nearest | all | around (вокруг погибшего) | source | self.
  mods   — постоянные правила (у предметов стража — с минусом): energy, hand, foe_strength, play_limit,
           retain_all, start_hp, slime, no_camp_heal, fewer_rewards, overheat_burn, revive.
  tag_bonus — пассивная прибавка картам с тегом: [{"tag": "Выстрел", "damage": 2}] или
           {"tags": ["Резонанс", "Цепочка"], "damage": 3}; block — к защите.
"""
from sim.grid import cheb

RARITY_NAME = {"common": "обычный", "uncommon": "необычный", "rare": "редкий", "boss": "предмет стража",
               "shop": "товар"}
RARITY_COLOR = {"common": (200, 190, 170), "uncommon": (120, 200, 255), "rare": (255, 205, 90),
                "boss": (230, 120, 255), "shop": (150, 230, 150)}
OFFER_WEIGHTS = {"chest": {"common": 50, "uncommon": 35, "rare": 15},
                 "elite": {"common": 40, "uncommon": 40, "rare": 20},
                 "shop": {"common": 40, "uncommon": 35, "rare": 10, "shop": 30},
                 "boss": {"boss": 100}}


RES = {"heat": ("жар", "жара"), "idols": ("свиток", "свитка")}


def about(item, run=None, hero=None):
    """Текст предмета: {res} / {res2} — ресурс героя (энергия, жар Пиромантки, свиток Жреца)."""
    mech = (getattr(run, "hero", None) or {}).get("mechanic") if run is not None else         {"pyro": "heat", "priest": "idols"}.get(hero)
    one, few = RES.get(mech, ("энергия", "энергии"))
    return item.get("about", "").replace("{res2}", few).replace("{res}", one)


def fits(item, hero):
    return item.get("hero") in (None, hero)


def mod(run, key):
    """Сумма постоянного правила по всем предметам забега (energy, hand, foe_strength…)."""
    return sum(r.get("mods", {}).get(key, 0) for r in getattr(run, "relics", []))


def counter_of(run, item, battle=None):
    """Показ счётчика на значке: сколько набрано (run — из забега, battle/turn — из боя)."""
    if not item.get("count"):
        return None
    sc = item.get("scope", "run")
    if sc == "run":
        return getattr(run, "relic_state", {}).get(item["id"], 0)
    if battle is None or getattr(battle, "items", None) is None:
        return None
    return battle.items.counts.get((sc, item["id"]), 0)


class Items:
    """Предметы в бою: принимает события и решает, что сработало."""

    def __init__(self, b):
        self.b = b
        self.run = b.run
        if not hasattr(self.run, "relic_state"):
            self.run.relic_state = {}
        self.counts = {}               # (scope, id) → набрано (battle / turn)
        self.done = set()              # (id, scope-ключ) — once
        self.turn_types = []           # типы карт, сыгранных основным за ход
        self.kills_turn = 0
        self.hp_low_fired = False
        self.scrolls = {}              # Жрец: свитков в статую за ход

    @property
    def list(self):
        return list(getattr(self.run, "relics", []))

    def mod(self, key):
        return mod(self.run, key)

    def card_bonus(self, card, kind):
        """Пассивная прибавка к карте по её тегу: tag_bonus у предметов."""
        if card is None:
            return 0
        tags = set(card.tags)
        total = 0
        for r in self.list:
            for b in r.get("tag_bonus", []):
                need = b.get("tags") or [b.get("tag")]
                if tags & set(need):
                    total += int(b.get(kind, 0))
        return total

    def new_turn(self):
        for k in [k for k in self.counts if k[0] == "turn"]:
            del self.counts[k]
        self.turn_types = []
        self.kills_turn = 0
        self.scrolls = {}

    # ---------- проверки ----------

    def check(self, w, ctx):
        b = self.b
        h = b.hero
        k, n = w["k"], w.get("n", 0)
        if k == "no_attack":
            return "attack" not in self.turn_types
        if k == "played_max":
            return b.played <= n
        if k == "hand_min":
            return len(b.hand) >= n
        if k == "hand_empty":
            return not b.hand
        if k == "shield_min":
            return h.shield >= n
        if k == "not_walked":
            return b.walked == 0
        if k == "hp_below":
            return h.hp * 100 < n * h.max_hp
        if k == "trio":
            return {"attack", "skill", "power"} <= set(self.turn_types)
        if k == "victim_bleed":
            d = ctx.get("src")
            return d is not None and d.ds.get("bleed", 0) >= n
        if k == "victim_burn":
            d = ctx.get("src")
            return d is not None and d.ds.get("burn", 0) >= max(1, n)
        if k == "momentum_min":
            return ctx.get("mom", 0) >= n
        if k == "far":
            t = ctx.get("tgt")
            return t is not None and hasattr(t, "cell") and cheb(t.cell, h.cell) >= n
        if k == "heat_min":
            return ctx.get("heat", 0) >= n
        if k == "foes_min":
            return len(b.foes()) >= n
        if k == "kills_turn":
            return self.kills_turn >= n
        if k == "played_min":
            return b.played >= n
        if k == "victim_poison":
            d = ctx.get("src")
            return d is not None and d.ds.get("poison", 0) >= n
        if k == "heat_zero":
            return h.ds.get("heat", 0) == 0
        if k == "retained":
            return sum(1 for c in b.hand if c.d.get("retain")) >= n
        if k == "all_fed":
            return b.idols is not None and all(getattr(s, "fed", False) for s in b.idols.statues)
        if k == "same_statue":
            st = ctx.get("statue")
            return st is not None and self.scrolls.get(id(st), 0) >= n
        return False

    def matches(self, r, ev, ctx):
        if r.get("on") != ev:
            return False
        card = ctx.get("card")
        if r.get("tag"):
            tags = r["tag"] if isinstance(r["tag"], list) else [r["tag"]]
            if card is None or not set(tags) & set(card.tags):
                return False
        if r.get("type") and (card is None or card.d.get("type") != r["type"]):
            return False
        if r.get("card") and (card is None or card.cid != r["card"]):
            return False
        if r.get("turn") and self.b.turn != r["turn"]:
            return False
        if r.get("every") and self.b.turn % r["every"]:
            return False
        return all(self.check(w, ctx) for w in r.get("when", []))

    # ---------- срабатывание ----------

    def fire(self, ev, **ctx):
        """Событие ev: предметы, у которых выполнены фильтры, — считают или срабатывают."""
        b = self.b
        for r in self.list:
            if b.result:
                return
            if not self.matches(r, ev, ctx):
                continue
            once = r.get("once")
            okey = (r["id"], once, b.turn if once == "turn" else 0)
            if once == "run" and self.run.relic_state.get(f"once:{r['id']}"):
                continue
            if once and okey in self.done:
                continue
            if r.get("count"):
                sc = r.get("scope", "run")
                if sc == "run":
                    v = self.run.relic_state.get(r["id"], 0) + 1
                    self.run.relic_state[r["id"]] = v % r["count"]
                else:
                    v = self.counts.get((sc, r["id"]), 0) + 1
                    self.counts[(sc, r["id"])] = v % r["count"]
                if v < r["count"]:
                    continue
            if once:
                self.done.add(okey)
                if once == "run":
                    self.run.relic_state[f"once:{r['id']}"] = True
            yield from self.trigger(r, ctx)

    def trigger(self, r, ctx):
        b = self.b
        h = b.hero
        aim = r.get("aim", "self")
        foes = b.foes()
        src = ctx.get("src")
        if aim == "nearest":
            tgts = [min(foes, key=lambda f: (cheb(f.cell, h.cell), f.hp))] if foes else []
        elif aim == "all":
            tgts = foes
        elif aim == "around":                                  # вокруг погибшего / источника
            tgts = [f for f in foes if src is not None and cheb(f.cell, src.cell) <= 1 and f is not src]
        elif aim == "source":
            tgts = [src] if src is not None and src.alive and src in foes else []
        elif aim == "target":
            t = ctx.get("tgt")
            tgts = [t] if t is not None and getattr(t, "alive", False) else []
        else:
            tgts = [None]
        if not tgts:
            return
        b.say(f"{r['name']}: {about(r, self.run)}", (170, 220, 255))
        b.fx("relic", unit=h, name=r["name"])
        for t in tgts:
            yield from b.apply(h, r.get("do", []), t, {"before": b.played, "dead": src})
