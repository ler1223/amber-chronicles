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
from . import surface as SURF
from . import apprentice as AP

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE_DIR = os.path.join(PROJECT_DIR, "save")
SAVE_PATH = os.path.join(SAVE_DIR, "workshop.json")

NAMES = (
    "Госпожа Вельда", "Купец Оррин", "Мастер Талия", "Ювелир Кейн",
    "Господин Рош", "Леди Мира", "Старик Фенн", "Клиент из гильдии",
    "Наследница Соль", "Капитан Варн", "Мадам Ирма", "Торговец Лот",
)

GEM_ORDER = ("ruby", "sapphire", "emerald", "topaz", "amethyst")

# Откуда партии: только для подписи и характера (docs/rough_to_gem_reality.md, §3).
SOURCES = ("с рынка в Ратнапуре", "от могокского перекупщика", "из каравана", "с ярмарки в Идаре",
           "от старателя с россыпи", "из бразильского ящика", "с уральской копи", "от мадагаскарского торговца")
PARCEL_K = 0.12          # партия — доля видимой цены кусков (продавец берёт оптом и не знает нутра)
SCRAP_K = 0.04           # скупщик мусора: за бесценок


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

        self.apprentice_day = 1        # ученичество у мастера: 1..3, 0 — мастер ушёл, лавка своя
        self.lesson_given = False
        self.samples = []              # образцы мастера: камни с известным ответом
        self.retired_note = False

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
        size = size if size is not None else round(self.rng.uniform(0.5, 2.2), 2)   # куски в мешочках некрупные
        return GM.roll_rough(self.xd, gid, self.rng, self._next_uid("r"), size)

    def rough_market_value(self, rough):
        """Оценка куска по тому, что видно снаружи (масса, форма, цвет), без знания нутра.

        Так оценивают продавец и скупщик; что внутри — узнаёт только огранщик."""
        return max(1.0, GM.rough_visible_value(self.xd, rough))

    def scrap_price(self, rough):
        return max(3, int(self.rough_market_value(rough) * SCRAP_K))

    def saw(self, rough, pieces):
        """Распиленный кусок заменяется двумя."""
        if rough not in self.inventory or not pieces:
            return False
        i = self.inventory.index(rough)
        self.inventory[i:i + 1] = pieces
        return True

    def sell_scrap(self, rough):
        """Продать кусок скупщику за бесценок."""
        if rough not in self.inventory:
            return 0
        price = self.scrap_price(rough)
        self.inventory.remove(rough)
        self.money += price
        return price

    def stone_price(self, rough):
        return max(25, int(self.rough_market_value(rough) * 0.40 * self.price_k()))

    def lot_price(self, stones):
        noise = self.rng.uniform(0.85, 1.15)              # торг: где-то переплата, где-то находка
        return max(40, int(sum(self.rough_market_value(r) for r in stones) * PARCEL_K * self.price_k() * noise))

    def _parcel(self):
        """Партия-мешочек: 5–8 кусков вперемешку, минерал каждого подписан честно."""
        n = self.rng.randint(5, 8)
        stones = [self._rough() for _ in range(n)]
        ct = sum(r["size"] for r in stones)
        label = f"Мешочек {self.rng.choice(SOURCES)}"
        return {"stones": stones, "price": self.lot_price(stones), "label": label,
                "desc": f"{n} кусков · {ct:.1f} ct"}

    # ---------- день ----------

    def new_day(self, first=False):
        if not first:
            self.day += 1
            if self.apprentice_day:
                self.apprentice_day = self.apprentice_day + 1 if self.apprentice_day < AP.DAYS else 0
                self.lesson_given = False
        self.day_closed = False
        self.stock = []
        self.lots = []
        self.clients = []

        # Поставщик продаёт только партиями: высыпать на стол и смотреть можно всё,
        # выбирать поштучно — нельзя.
        for _ in range(self.rng.randint(2, 4)):
            self.lots.append(self._parcel())

        self.clients = self._make_clients()

    def _make_clients(self):
        count = 2 + (1 if self.reputation >= 8 else 0)
        out = []
        stock_gems = [r["id"] for lot in self.lots for r in lot["stones"]] + [r["id"] for r in self.inventory]
        for i in range(min(3, count)):
            kind = "custom" if self.rng.random() < 0.7 else "walkin"
            name = self.rng.choice(NAMES)
            small = kind == "custom" and self.rng.random() < 0.35
            if kind == "custom":
                gid = self.rng.choice(stock_gems or self.gem_ids)
                cut = self.rng.choice(self.known_cuts)
                if small:
                    # дешёвый заказ: маленький, но чистый камень — как раз вырезать из засорённого куска
                    min_ct = round(self.rng.uniform(0.12, 0.3), 2)
                    min_q = round(self.rng.uniform(0.7, 0.95), 2)
                    min_col = round(self.rng.uniform(0.2, 0.45), 2)
                    min_cl = round(self.rng.uniform(0.7, 0.9), 2)
                else:
                    min_ct = round(max(0.35, min(2.6, self.rng.uniform(0.5, 2.1))), 2)
                    min_q = round(self.rng.uniform(0.78, 1.10), 2)
                    min_col = round(self.rng.uniform(0.32, 0.68), 2)
                    min_cl = round(self.rng.uniform(0.40, 0.82), 2)
                est = GM.estimate(self.xd, gid, min_ct, min_col, min_cl, min_q, cut=cut)
                budget = max(90, int(est * self.rng.uniform(1.15, 1.65)))
                desc = (f"Нужен {self.gem_name(gid).lower()}, огранка "
                        f"«{self.cut_name(cut)}», от {min_ct:.2f} ct, "
                        f"цвет не ниже {GM.color_word(self.xd, min_col)}, "
                        f"чистота не ниже {GM.grade(self.xd, min_cl).lower()}, "
                        f"качество от {min_q:.2f}")
            else:
                gid = None
                cut = None
                min_ct = round(self.rng.uniform(0.4, 1.8), 2)
                min_q = round(self.rng.uniform(0.70, 1.02), 2)
                min_col = round(self.rng.uniform(0.25, 0.60), 2)
                min_cl = round(self.rng.uniform(0.35, 0.75), 2)
                est = GM.estimate(self.xd, self.rng.choice(self.gem_ids), min_ct,
                                  min_col, min_cl, min_q)
                budget = max(80, int(est * self.rng.uniform(1.1, 1.5)))
                desc = (f"Ищет готовый камень от {min_ct:.2f} ct, "
                        f"цвет не ниже {GM.color_word(self.xd, min_col)}, "
                        f"чистота не ниже {GM.grade(self.xd, min_cl).lower()}, "
                        f"качество от {min_q:.2f}")
            out.append({
                "id": f"c{self.day}_{i}",
                "name": name,
                "kind": kind,
                "gem_id": gid,
                "cut": cut,
                "min_ct": min_ct,
                "min_q": min_q,
                "min_col": min_col,
                "min_cl": min_cl,
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
        stones = copy.deepcopy(lot["stones"])
        vis = [self.rough_market_value(r) for r in stones]
        total = sum(vis) or 1.0
        for r, v in zip(stones, vis):                 # доля цены партии — для «до и после»
            r["cost"] = round(lot["price"] * v / total)
        self.inventory.extend(stones)
        self.lots.pop(i)
        return True

    # ---------- результат огранки ----------

    def finish_gem(self, rough, cutter):
        ct = cutter.final_ct()
        if ct is None:
            ct = round(rough.get("size", 0.5) * 0.35, 2)
        incl = cutter.final_incl() or []
        cl = GM.clarity(self.xd, incl, gid=rough["id"])
        q = cutter.quality
        cut = cutter.cut["id"] if cutter.cut else self.known_cuts[0]
        star = cutter.final_star()
        surface = SURF.from_cutter(cutter)
        value = GM.estimate(self.xd, rough["id"], ct, rough.get("col", 0.5), cl, q,
                            cut=cut, star=star)
        # Видимая поверхность — часть товара: грязь и царапины снижают цену,
        # даже если внутренняя чистота и огранка хороши.
        value = max(1.0, value * SURF.value_factor(surface))
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
            "surface": surface,
            "cf": cutter.cfield(),
            "cz": cutter.final_colors(),
        }

    def evaluate(self, client, gem):
        """(status, offer): ok / discount / wrong / reject."""
        if client["kind"] == "custom":
            if gem.get("id") != client["gem_id"] or gem.get("cut") != client["cut"]:
                return "wrong", 0
        size_ok = gem.get("size", 0) >= client["min_ct"]
        q_ok = gem.get("q", 0) >= client["min_q"]
        color_ok = gem.get("col", 1.0) >= client.get("min_col", 0.0) * 0.92
        clarity_ok = gem.get("cl", 1.0) >= client.get("min_cl", 0.0) * 0.92
        if (gem.get("size", 0) < client["min_ct"] * 0.8
                or gem.get("q", 0) < client["min_q"] * 0.9
                or gem.get("col", 1.0) < client.get("min_col", 0.0) * 0.75
                or gem.get("cl", 1.0) < client.get("min_cl", 0.0) * 0.75):
            return "reject", 0
        offer = min(client["budget"], int(gem.get("value", 0)))
        if not (size_ok and q_ok and color_ok and clarity_ok):
            return "discount", max(1, int(offer * 0.7))
        return "ok", max(1, offer)

    def haggle(self, client, offer):
        if client.get("haggle_used"):
            return offer
        client["haggle_used"] = True
        return min(client["budget"], max(offer + 1, int(offer * 1.15)))

    def clean_stone(self, stone):
        """Снять поверхностную грязь. Внутренние включения это не убирает."""
        rough = "seed" in stone and "q" not in stone
        old = stone.get("surface_clean") or SURF.for_stone(stone, rough=rough, cleaned=False)
        new = SURF.for_stone(stone, rough=rough, cleaned=True)
        stone["surface_clean"] = new
        if stone.get("value"):
            f0 = SURF.value_factor(old)
            f1 = SURF.value_factor(new)
            stone["value"] = max(1, int(round(stone["value"] * f1 / max(0.55, f0))))
        return new

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

    # ---------- ученичество ----------

    def lesson(self):
        return AP.LESSONS.get(self.apprentice_day) if self.apprentice_day else None

    def take_lesson_stones(self):
        """Мастер выдаёт учебные камни дня (один раз в день). Копии — в шкаф образцов."""
        if not self.apprentice_day or self.lesson_given:
            return []
        stones = AP.make_stones(self.xd, self.apprentice_day)
        for st in stones:
            st["uid"] = self._next_uid("L")
            self.samples.append(AP.sample_copy(st))
        self.inventory.extend(stones)
        self.lesson_given = True
        return stones

    def end_day(self):
        if self.day_closed:
            return {"rent": 0, "paid": 0, "debt_added": 0}
        self.day_closed = True
        rent = 0 if self.apprentice_day else self.rent()        # пока учишься — аренду платит мастер
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
                "inventory", "display", "stock", "lots", "clients",
                "apprentice_day", "lesson_given", "samples", "retired_note")
        return {k: copy.deepcopy(getattr(self, k)) for k in keys}

    @classmethod
    def from_dict(cls, d):
        obj = cls(seed=d.get("seed"))
        fresh = d.get("day", 1) <= 1 and not d.get("inventory") and not d.get("display")
        if "apprentice_day" not in d and not fresh:    # старое сохранение с игрой: ученичество позади
            obj.apprentice_day = 0
            obj.retired_note = True
        for k, v in d.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        obj.rng = random.Random(obj.seed)
        if "apprentice_day" not in d and fresh:        # старое, но не начатое: с мастером и мешочками
            obj.new_day(first=True)
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
