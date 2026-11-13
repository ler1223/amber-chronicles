"""Девять глав похода и темнота Склепа: факелы, видимость и скрытые враги."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim import expedition as X  # noqa: E402
from sim.data import GameData  # noqa: E402

DATA = GameData()
ED = X.expedition_data(DATA)
XD = ED.expedition


def test_all_nine_chapters_are_playable():
    expected = ["swamp", "forge", "crypt", "pass", "steppe", "tomb", "fae", "sunken", "citadel"]
    assert set(expected) <= set(XD["chapters"])
    for cid in expected:
        view = X.chapter_view(XD, cid)
        assert len(view["acts"]) == 3, cid
        assert view["events"], cid
        for act in view["acts"]:
            for pool in act["pools"].values():
                for eid in pool:
                    X.enc_index(ED, eid)
            X.enc_index(ED, act["boss"])


def test_crypt_torches_spend_refill_and_hide_enemies():
    prof = X.ExpeditionProfile(ED)
    run = X.Expedition(ED, [prof.roster[0]], chapter="crypt")
    assert run.torch_on() and run.torches == 6 and run.torch_visibility() == 2
    run.enter(run.available()[0])                 # вход на карту — ещё без траты
    run.enter(run.available()[0])
    assert run.torches == 5
    run.torches = 0
    assert run.torch_visibility() == 1
    assert run.enemy_scale()["fog"] == 99
    run.camp_rest()
    assert run.torches == run.torch_max
    run.torches = 1
    run.gold = 100
    assert run.buy_torch() and run.torches == 3
