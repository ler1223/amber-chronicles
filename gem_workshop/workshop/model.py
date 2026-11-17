"""Модель маленькой игры «Грань»: мастерская, камни, клиенты и экономика.

Прототип использует существующие данные и геометрию камней из основной игры,
но весь игровой цикл мастерской живёт отдельно в gem_workshop/.
"""
from __future__ import annotations

import copy
import json
import os
import random

from sim import gems as GM
from .data import load as load_workshop_data

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE_DIR = os.path.join(PROJECT_DIR, "save")
SAVE_PATH = os.path.join(SAVE_DIR, "workshop.json")

NAMES = (
    "Госпожа Вельда", "Купец Оррин", "Мастер Талия", "Ювелир Кейн",
    "Господин Рош", "Леди Мира", "Старик Фенн", "Клиент из гильдии",
    "Наследница Соль", "Капитан Варн", "Мадам Ирма", "Торговец Лот",
)

GEM_ORDER = ("ruby", "sapphire", "emerald", "topaz", "amethyst")


class Workshop:
    """Состояние бесконечного забега: дни, деньги, репутация, камни и клиенты."""

    def __init__(self, seed=None):
        self.data = load_workshop_data()
        self.xd = self.data.expedition
        self.seed = seed
        self.rng = random.Random(seed)
        self.uid = 0

        self.day = 1
        self.money = 900
        self.reputation = 0
        self.debt = 0
        self.day_closed = False

        self.known_cuts = list(GM.START_CUTS)
        self.disks = [GM.START_DISK]
        self.lenses = []
        self.autofocus = False
        self.display_slots = 3

        self.inventory = []
        self.display = []
        self.stock = []
        self.lots = []
        self.clients = []

        self.new_day(first=True)

    # ---------- данные и цены ----------

    @property
    def gem_ids(self):
        gems = self.xd.get("artifacts", {}).get("gems", {})
        return [gid for gid in GEM_ORDER if gid in gems] or list(gems)

    def gem_name(self, gid):
        return GM.gem_def(self.xd, gid).get("name", gid)

    def cut_name(self, cid):
        return GM.cut_name(cid)

    def _next_uid(self, prefix):
        self.uid += 1
        return f"{prefix}{self.uid}"

    def price_k(self):
        """Долг поднимает цены, репутация даёт небольшую скидку."""
        return 1.0 + min(0.55, self.debt / 1800.0) - min(0.15, self.reputation * 0.01)

    def _rough(self, gid=None, size=None):
        gid = gid or self.rng.choice(self.gem_ids)
        size = size if size is not None else round(self.rng.uniform(0.7, 2.8), 2)
        return GM.roll_rough(self.xd, gid, self.rng, self._next_uid("r"), size)

    def stone_price(self, rough):
        return max(25, int(GM.rough_value(self.xd, rough) * 0.40 * self.price_k()))

    def lot_price(self, stones):
        return max(40, int(sum(GM.rough_value(self.xd, r) for r in stones) * 0.26 * self.price_k()))

    # ---------- день ----------

    def new_day(self, first=False):
        if not first:
            self.day += 1
        self.day_closed = False
        self.stock = []
        self.lots = []
        self.clients = []

        # Поставщик: отдельные камни, которые можно рассмотреть.
        for _ in range(5):
            r = self._rough()
            self.stock.append({"rough": r, "price": self.stone_price(r)})

        # Лоты: дешевле, но состав известен только частично.
        for _ in range(2):
            stones = [self._rough() for _ in range(self.rng.randint(2, 3))]
            self.lots.append({"stones": stones, "price": self.lot_price(stones),
                              "label": f"Лот · {len(stones)} камня"})

        self.clients = self._make_clients()

    def _make_clients(self):
        count = 2 + (1 if self.reputation >= 8 else 0)
        out = []
        stock_gems = [s["rough"]["id"] for s in self.stock]
        for i in range(min(3, count)):
            kind = "custom" if self.rng.random() < 0.7 else "walkin"
            name = self.rng.choice(NAMES)
            if kind == "custom":
                gid = self.rng.choice(stock_gems or self.gem_ids)
                cut = self.rng.choice(self.known_cuts)
                min_ct = round(max(0.35, min(2.6, self.rng.uniform(0.5, 2.1))), 2)
                min_q = round(self.rng.uniform(0.78, 1.10), 2)
                est = GM.estimate(self.xd, gid, min_ct, 0.5, min_q, 0.9, cut=cut)
                budget = max(90, int(est * self.rng.uniform(1.15, 1.65)))
                desc = (f"Нужен {self.gem_name(gid).lower()}, огранка "
                        f"«{self.cut_name(cut)}», от {min_ct:.2f} ct, "
                        f"качество не ниже {min_q:.2f}")
            else:
                gid = None
                cut = None
                min_ct = round(self.rng.uniform(0.4, 1.8), 2)
                min_q = round(self.rng.uniform(0.70, 1.02), 2)
                est = GM.estimate(self.xd, self.rng.choice(self.gem_ids), min_ct, 0.5, min_q, 0.9)
                budget = max(80, int(est * self.rng.uniform(1.1, 1.5)))
                desc = (f"Ищет готовый камень от {min_ct:.2f} ct, "
                        f"качество не ниже {min_q:.2f}")
            out.append({
                "id": f"c{self.day}_{i}",
                "name": name,
                "kind": kind,
                "gem_id": gid,
                "cut": cut,
                "min_ct": min_ct,
                "min_q": min_q,
                "budget": budget,
                "desc": desc,
                "served": False,
                "status": None,
                "offer": 0,
                "haggle_used": False,
            })
        return out

    def remaining_clients(self):
        return [c for c in self.clients if not c["served"]]

    def all_clients_done(self):
        return not self.remaining_clients()

    # ---------- покупка ----------

    def buy_stock(self, i):
        if not 0 <= i < len(self.stock):
            return False
        item = self.stock[i]
        if self.money < item["price"]:
            return False
        self.money -= item["price"]
        self.inventory.append(item["rough"])
        self.stock.pop(i)
        return True

    def buy_lot(self, i):
        if not 0 <= i < len(self.lots):
            return False
        lot = self.lots[i]
        if self.money < lot["price"]:
            return False
        self.money -= lot["price"]
        self.inventory.extend(copy.deepcopy(lot["stones"]))
        self.lots.pop(i)
        return True

    # ---------- результат огранки ----------

    def finish_gem(self, rough, cutter):
        ct = cutter.final_ct()
        if ct is None:
            ct = round(rough.get("size", 0.5) * 0.35, 2)
        incl = cutter.final_incl() or []
        cl = GM.clarity(self.xd, incl)
        q = cutter.quality
        cut = cutter.cut["id"] if cutter.cut else self.known_cuts[0]
        star = cutter.final_star()
        value = GM.estimate(self.xd, rough["id"], ct, rough.get("col", 0.5), cl, q,
                            cut=cut, star=star)
        return {
            "uid": self._next_uid("g"),
            "id": rough["id"],
            "size": round(ct, 2),
            "col": rough.get("col", 0.5),
            "cl": cl,
            "q": q,
            "cut": cut,
            "star": star,
            "value": int(value),
            "shape": cutter.shape(),
        }

    def evaluate(self, client, gem):
        """(status, offer): ok / discount / wrong / reject."""
        if client["kind"] == "custom":
            if gem.get("id") != client["gem_id"] or gem.get("cut") != client["cut"]:
                return "wrong", 0
        size_ok = gem.get("size", 0) >= client["min_ct"]
        q_ok = gem.get("q", 0) >= client["min_q"]
        if gem.get("size", 0) < client["min_ct"] * 0.8 or gem.get("q", 0) < client["min_q"] * 0.9:
            return "reject", 0
        offer = min(client["budget"], int(gem.get("value", 0)))
        if not (size_ok and q_ok):
            return "discount", max(1, int(offer * 0.7))
        return "ok", max(1, offer)

    def haggle(self, client, offer):
        if client.get("haggle_used"):
            return offer
        client["haggle_used"] = True
        return min(client["budget"], max(offer + 1, int(offer * 1.15)))

    def add_display(self, gem):
        self.display.append(gem)
        return gem

    def sell(self, client, gem, offer, status):
        if offer <= 0:
            return False
        if gem in self.display:
            self.display.remove(gem)
        self.money += int(offer)
        self.reputation += 1 if status == "ok" else 0
        client["served"] = True
        client["status"] = status
        client["offer"] = int(offer)
        return True

    def refuse(self, client, gem=None):
        client["served"] = True
        client["status"] = "refused"
        client["offer"] = 0
        self.reputation = max(-20, self.reputation - 1)
        if gem is not None and gem not in self.display:
            self.add_display(gem)
        return True

    def skip_client(self, client):
        client["served"] = True
        client["status"] = "skipped"
        self.reputation = max(-20, self.reputation - 1)
        return True

    # ---------- вечер ----------

    def rent(self):
        return 35 + self.day * 10

    def end_day(self):
        if self.day_closed:
            return {"rent": 0, "paid": 0, "debt_added": 0}
        self.day_closed = True
        rent = self.rent()
        if self.money >= rent:
            self.money -= rent
            paid, added = rent, 0
        else:
            paid = self.money
            added = rent - self.money
            self.debt += added
            self.money = 0
        return {"rent": rent, "paid": paid, "debt_added": added}

    def upgrade_options(self):
        opts = []
        if "loupe" not in self.lenses:
            opts.append({"key": "loupe", "name": "Лупа ×2", "price": 350,
                         "desc": "Лучше видеть включения и грани."})
        if "lap_fine" not in self.disks:
            opts.append({"key": "lap_fine", "name": "Тонкий диск", "price": 450,
                         "desc": "Меньше царапин, выше качество."})
        next_cut = next((c for c in GM.CUTS if not c.get("rare") and c["id"] not in self.known_cuts), None)
        if next_cut:
            opts.append({"key": f"cut:{next_cut['id']}", "name": f"Книга: {next_cut['name']}",
                         "price": max(300, int(next_cut.get("book", 1000) * 0.35)),
                         "desc": "Новая огранка для мастерской."})
        if self.display_slots < 5:
            opts.append({"key": "display", "name": "Витрина +1", "price": 300,
                         "desc": "Больше готовых камней на продажу."})
        return opts

    def buy_upgrade(self, key):
        opts = {o["key"]: o for o in self.upgrade_options()}
        opt = opts.get(key)
        if not opt or self.money < opt["price"]:
            return False
        self.money -= opt["price"]
        if key == "loupe":
            self.lenses.append("loupe")
        elif key == "lap_fine":
            self.disks.append("lap_fine")
        elif key == "display":
            self.display_slots += 1
        elif key.startswith("cut:"):
            cid = key.split(":", 1)[1]
            if cid not in self.known_cuts:
                self.known_cuts.append(cid)
        return True

    # ---------- сохранение ----------

    def to_dict(self):
        keys = ("seed", "uid", "day", "money", "reputation", "debt", "day_closed",
                "known_cuts", "disks", "lenses", "autofocus", "display_slots",
                "inventory", "display", "stock", "lots", "clients")
        return {k: copy.deepcopy(getattr(self, k)) for k in keys}

    @classmethod
    def from_dict(cls, d):
        obj = cls(seed=d.get("seed"))
        for k, v in d.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        obj.rng = random.Random(obj.seed)
        return obj

    def save(self, path=SAVE_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=1)

    @classmethod
    def load(cls, path=SAVE_PATH):
        if not os.path.exists(path):
            return cls(seed=None)
        try:
            with open(path, encoding="utf-8") as f:
                return cls.from_dict(json.load(f))
        except (OSError, ValueError, KeyError, TypeError):
            return cls(seed=None)
