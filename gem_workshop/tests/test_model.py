"""Базовые проверки модели прототипа «Грань»."""
import os
import sys

# Проект самостоятельный: его sim/, game/, workshop/ — раньше одноимённых пакетов основной игры
# (см. conftest.py: корень репозитория тоже попадает в путь).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workshop.model import Workshop  # noqa: E402
import game.jewel_view  # noqa: E402,F401 — сразу из проекта, пока его путь первый
import workshop.marks  # noqa: E402,F401


def test_new_day_has_parcels_and_clients():
    w = Workshop(seed=1)
    assert w.day == 1
    assert not w.stock                                  # поштучно не продают — только партии
    assert len(w.clients) >= 2
    assert 2 <= len(w.lots) <= 4
    assert all(5 <= len(lot["stones"]) <= 8 for lot in w.lots)


def test_buy_parcel_and_end_day_rent():
    w = Workshop(seed=2)
    w.money = 100000
    money = w.money
    price = w.lots[0]["price"]
    n = len(w.lots[0]["stones"])
    assert w.buy_lot(0)
    assert w.money == money - price and len(w.inventory) == n
    assert abs(sum(r["cost"] for r in w.inventory) - price) <= n
    w.apprentice_day = 0                                 # своя лавка — аренда своя
    report = w.end_day()
    assert report["rent"] > 0
    assert w.money == max(0, money - price - report["paid"])


def test_custom_client_accepts_matching_gem():
    w = Workshop(seed=3)
    c = next(c for c in w.clients if c["kind"] == "custom")
    gem = {"id": c["gem_id"], "cut": c["cut"], "size": c["min_ct"] + 0.1,
           "q": c["min_q"] + 0.05, "value": c["budget"]}
    status, offer = w.evaluate(c, gem)
    assert status == "ok" and offer > 0
    assert w.sell(c, gem, offer, status)
    assert c["served"] and w.money > 0


def test_wrong_gem_is_rejected():
    w = Workshop(seed=4)
    c = next(c for c in w.clients if c["kind"] == "custom")
    gem = {"id": "ruby" if c["gem_id"] != "ruby" else "sapphire", "cut": c["cut"],
           "size": c["min_ct"] + 0.1, "q": c["min_q"] + 0.05, "value": 100}
    status, offer = w.evaluate(c, gem)
    assert status == "wrong" and offer == 0


def test_client_rejects_bad_color_or_clarity():
    w = Workshop(seed=4)
    c = next(c for c in w.clients if c["kind"] == "custom")
    gem = {"id": c["gem_id"], "cut": c["cut"], "size": c["min_ct"] + 0.1,
           "q": c["min_q"] + 0.05, "col": 0.0, "cl": 0.0, "value": 100}
    status, offer = w.evaluate(c, gem)
    assert status == "reject" and offer == 0


def test_scrap_sale_returns_little():
    w = Workshop(seed=3)
    w.money = 100000
    w.buy_lot(0)
    r = w.inventory[0]
    before = w.money
    got = w.sell_scrap(r)
    assert 0 < got < r["cost"] + 1 and w.money == before + got and r not in w.inventory


def test_save_and_load(tmp_path):
    w = Workshop(seed=5)
    w.money = 100000
    w.buy_lot(0)
    path = tmp_path / "save.json"
    w.save(str(path))
    again = Workshop.load(str(path))
    assert again.day == w.day and again.money == w.money
    assert len(again.inventory) == len(w.inventory)


def test_upgrade_is_bought_once():
    w = Workshop(seed=6)
    w.money = 5000
    assert w.buy_upgrade("loupe")
    assert "loupe" in w.lenses
    assert not w.buy_upgrade("loupe")


def test_apprenticeship_three_days_then_own_shop():
    w = Workshop(seed=7)
    assert w.apprentice_day == 1 and w.lesson()
    stones = w.take_lesson_stones()
    assert len(stones) == 2 and all(st in w.inventory for st in stones)
    assert len(w.samples) == 2 and all(s_.get("sample") for s_ in w.samples)
    assert not w.take_lesson_stones()                    # раз в день
    assert w.end_day()["rent"] == 0                      # пока учишься — аренду платит мастер
    for _ in range(3):
        w.new_day()
        w.take_lesson_stones()
        w.end_day()
    assert w.apprentice_day == 0 and w.end_day()["rent"] == 0   # день уже закрыт
    w.new_day()
    assert w.end_day()["rent"] > 0


def test_saw_splits_rough_into_two():
    from workshop import marks as MK
    w = Workshop(seed=12)
    w.money = 100000
    w.buy_lot(0)
    st = max(w.inventory, key=lambda r: r["size"])
    pieces = MK.saw_split(st, ((1.0, 0.0, 0.0), 0.0))
    assert pieces and w.saw(st, pieces)
    a, b = pieces
    assert 0.9 * st["size"] < a["size"] + b["size"] < st["size"]
    assert a in w.inventory and b in w.inventory and st not in w.inventory
