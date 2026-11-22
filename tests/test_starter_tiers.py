"""Тиры карт, нейтральные карты и своя стартовая колода."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deck import model as M  # noqa: E402


def test_every_playable_card_has_category_and_tier():
    data = M.load()
    cards = data["cards"]["cards"]
    for cid, c in cards.items():
        assert c.get("category") in ("basic", "neutral", "hero", "token"), cid
        if c["category"] == "token":
            assert c.get("rarity") == 0, cid
        elif c["category"] == "basic":
            assert c.get("rarity") == 0 and c.get("basic_role") in ("attack", "defense", "movement"), cid
        else:
            assert 1 <= c.get("rarity", 0) <= 4, cid


def test_basic_starter_has_six_cards_and_tier1_pool_for_every_hero():
    data = M.load()
    for hero in ("merc", "hunter", "pyro", "priest"):
        basic = M.basic_starter(data, hero)
        assert len(basic) == 6
        roles = [data["cards"]["cards"][cid]["basic_role"] for cid in basic]
        assert roles.count("attack") == 2 and roles.count("defense") == 2 and roles.count("movement") == 2
        pool = M.tier1_pool(data, hero)
        assert len(pool) >= 4, (hero, pool)
        assert all(data["cards"]["cards"][cid].get("rarity") == 1 for cid in pool)


def test_custom_starter_run_is_ten_cards():
    data = M.load()
    basic = M.basic_starter(data, "hunter")
    picks = M.tier1_pool(data, "hunter")[:4]
    run = M.Run(data=data, seed=41, hero="hunter", variant="mark", starter=basic + picks)
    assert len(run.deck) == 10
    assert {c.cid for c in run.deck} >= set(basic + picks)


def test_rewards_have_no_basic_cards_and_can_offer_neutral():
    data = M.load()
    neutral = set(data["cards"].get("neutral", []))
    assert neutral
    for hero in ("merc", "hunter", "pyro", "priest"):
        run = M.Run(data=data, seed=42, hero=hero)
        for _ in range(20):
            offer = run.reward_offer()
            assert len(offer) == 3
            for c in offer:
                assert c.category not in ("basic", "token"), (hero, c.cid)
                assert c.rarity >= 1
