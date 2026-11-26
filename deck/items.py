"""Предметы «Спуска» (квиз 2026-11-21) — как реликвии Slay the Spire: лежат в сумке весь забег и срабатывают
только при условии, которое в обычной игре выполняется редко (счётчики, «3-й ход», «ход без атак», «HP ниже
половины»…). Данные — data/deck/relics.json (пишет tools/descent_items.py).

Предмет: {id, name, icon, rarity: common|uncommon|rare|boss|shop, hero?, about, on, …фильтры, do, aim}.
  on     — событие боя: battle, turn, play, kill, hit, exhaust, create, shuffle, step, end, hp_low, last_foe,
           trap, counter, scroll, desecrated, chain, retained.
  фильтры: tag / type / card (что сыграно), turn (номер хода), every (каждые N ходов), when — список проверок
           состояния (no_attack, played_max, hand_min, hand_empty, shield_min, not_walked, hp_below, trio,
           victim_bleed, victim_burn, momentum_min, far, heat_min, foes_min), count+scope — счётчик (run | battle
           | turn): срабатывает на N-й раз и обнуляется; once — раз за turn | battle | run.
  aim    — nearest | all | around (вокруг погибшего) | source | self.
  mods   — постоянные правила (у предметов стража — с минусом): energy, hand, foe_strength, play_limit,
           retain_all, start_hp, slime, no_camp_heal, fewer_rewards, overheat_burn, revive.
  tag_bonus — пассивная прибавка картам с тегом: [{"tag": "Выстрел", "damage": 2}] или
           {"tags": ["Резонанс", "Цепочка"], "damage": 3}; block — к защите.
  retained_discount — скидка при основном розыгрыше карты, сохранённой в прошлом ходу, раз за ход.
  arm — отложенный бонус в пределах хода: {kind: block | displace, tag, n}.
"""
from .model import card_rules, tag_id
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
        self.retention = {}            # uid карты → последний ход сохранения и длина серии
        self.armed = {}                # id предмета → бонус, ожидающий подходящую карту в этом ходу

    @property
    def list(self):
        return list(getattr(self.run, "relics", []))

    def mod(self, key):
        return mod(self.run, key)

    def card_bonus(self, card, kind):
        """Пассивная прибавка к карте по её тегу: tag_bonus у предметов."""
        if card is None:
            return 0
        tags = set(card.tag_ids)
        total = 0
        for r in self.list:
            for b in r.get("tag_bonus", []):
                need = b.get("tags") or [b.get("tag")]
                if tags.intersection(map(tag_id, need)):
                    total += int(b.get(kind, 0))
        return total

    def new_turn(self):
        self.armed.clear()
        for k in [k for k in self.counts if k[0] == "turn"]:
            del self.counts[k]
        self.turn_types = []
        self.kills_turn = 0
        self.scrolls = {}
        self.retention = {uid: record for uid, record in self.retention.items() if record[0] >= self.b.turn - 1}

    def take_card_bonus(self, card, kind):
        if card is None:
            return 0
        total = 0
        for iid, relic in tuple(self.armed.items()):
            bonus = relic["arm"]
            if bonus["kind"] != kind or tag_id(bonus["tag"]) not in card.tag_ids:
                continue
            total += bonus["n"]
            del self.armed[iid]
            self.b.say(f"{relic['name']}: {about(relic, self.run)}", (170, 220, 255))
            self.b.fx("relic", unit=self.b.hero, name=relic["name"])
        return total

    def retained_discount(self, card, price, *, consume=False):
        """Вычислить скидку на розыгрыш, сохраняя заряд для первой платной карты."""
        b = self.b
        if price <= 0 or self.retention.get(card.uid, (None, 0))[0] != b.turn - 1:
            return 0
        discount = 0
        for relic in self.list:
            amount = min(price - discount, relic.get("retained_discount", 0))
            key = (relic["id"], "turn", b.turn)
            if amount <= 0 or key in self.done:
                continue
            discount += amount
            if consume:
                self.done.add(key)
                b.say(f"{relic['name']}: скидка {amount}", (170, 220, 255))
                b.fx("relic", unit=b.hero, name=relic["name"])
        return discount

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
            return sum(1 for c in b.hand if "retain" in card_rules(c.d)) >= n
        if k == "retain_streak":
            return ctx.get("retain_streak", 0) == n
        if k == "moved_to_terrain":
            cell = b.c.grid.get(h.cell)
            origin = ctx.get("origin")
            return origin is not None and origin != h.cell and cell is not None and cell.terrain in w["terrain"]
        if k == "previous_tag":
            return tag_id(w["tag"]) in ctx.get("previous_tags", ())
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
            if card is None or not any(tag_id(tag) in card.tag_ids for tag in tags):
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
        if ev == "retained":
            uid = ctx["card"].uid
            turn, streak = self.retention.get(uid, (0, 0))
            if turn == b.turn:
                return
            streak = streak + 1 if turn == b.turn - 1 else 1
            self.retention[uid] = b.turn, streak
            ctx["retain_streak"] = streak
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
        if r.get("arm"):
            self.armed[r["id"]] = r
            return
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
