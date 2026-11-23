"""Каталог CZN и перенесённый пакет карт."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deck import model as M  # noqa: E402


def test_czn_catalog_is_complete():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "czn", "cards.json")
    data = json.load(open(path, encoding="utf-8"))
    assert data["count"] == 979 and len(data["cards"]) == 979
    assert sum(c["variant"] == "Base" for c in data["cards"]) == 341
    assert {"character", "name", "variant", "slot", "type", "rarity", "cost", "traits", "effect"} <= \
        set(data["cards"][0])


def test_czn_adapted_cards_are_marked_and_playable_defs():
    data = M.load()
    cards = data["cards"]["cards"]
    adapted = [c for c in cards.values() if (c.get("source") or {}).get("game") == "CZN"]
    assert len(adapted) == 59
    assert all(c.get("category") in ("hero", "neutral") for c in adapted)
    assert all(1 <= c.get("rarity", 0) <= 4 for c in adapted)
    neutral = set(data["cards"]["neutral"])
    assert {"n_czn_quick_shell", "n_czn_reorganize", "n_czn_pierce"} <= neutral
    for hid in ("hunter", "merc", "pyro"):
        h = data["heroes"]["heroes"][hid]
        assert any(cid.startswith({"hunter": "h_czn_", "merc": "m_czn_", "pyro": "p_czn_"}[hid])
                   for cid in h["rewards"])


def test_czn_catalog_marks_hunter_ranger_pack():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "czn", "cards.json")
    catalog = json.load(open(path, encoding="utf-8"))["cards"]
    marked = {cid for card in catalog for cid in card.get("adapted_as", [])}
    assert "h_volley" in marked
    assert "h_rng_full_burst" in marked
    assert len([cid for cid in marked if cid.startswith("h_rng_")]) == 24


def test_adapted_czn_cards_can_be_played():
    data = M.load()
    ids = [cid for cid, c in data["cards"]["cards"].items()
           if (c.get("source") or {}).get("game") == "CZN"]
    from deck.battle import Battle, finish
    from test_expedition import ED

    def put(u, cell):
        u.cell = u.prev_cell = tuple(cell)

    for cid in ids:
        hero = "hunter" if cid.startswith("h_") else "merc" if cid.startswith("m_") else \
            "pyro" if cid.startswith("p_") else "merc"
        run = M.Run(data=data, seed=51, hero=hero)
        b = Battle(ED, run, run.fights[0], seed=51)
        h, foe = b.hero, b.foes()[0]
        put(h, (2, 2))
        put(foe, (3, 2))
        foe.hp = foe.max_hp = 99
        c = M.Card(cid, run.defs)
        b.hand = [c]
        b.energy = 99
        h.ds["heat"] = 99
        targets = b.targets(c, "main")
        assert targets, cid
        finish(b.play(c, "main", targets[0]))
        assert c not in b.hand, cid
