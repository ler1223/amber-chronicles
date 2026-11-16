"""Базовые проверки модели прототипа «Грань»."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from gem_workshop.workshop.model import Workshop  # noqa: E402


def test_new_day_has_supplier_clients_and_lots():
    w = Workshop(seed=1)
    assert w.day == 1
    assert 4 <= len(w.stock) <= 6
    assert len(w.clients) >= 2
    assert len(w.lots) == 2


def test_buy_stock_and_end_day_rent():
    w = Workshop(seed=2)
    money = w.money
    price = w.stock[0]["price"]
    assert w.buy_stock(0)
    assert w.money == money - price and len(w.inventory) == 1
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


def test_save_and_load(tmp_path):
    w = Workshop(seed=5)
    w.buy_stock(0)
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
