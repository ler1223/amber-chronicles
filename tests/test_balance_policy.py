"""Балансный пакет: стоимость, альтернативы и выбор сброса у Адажио."""
from deck import model as M
from deck.battle import Battle, finish
from tests.test_expedition import ED


def put(u, cell):
    u.cell = u.prev_cell = tuple(cell)


def test_zero_cost_policy_and_alt_allowlist():
    data = M.load()
    cards = data["cards"]["cards"]
    allowed_alt = {"strike", "defend", "h_shot", "h_dodge", "p_bolt", "p_ward", "p_stride",
                   "sc_attack", "sc_defense", "sc_move", "charge", "body_slam", "riposte"}
    for cid, c in cards.items():
        if c.get("cost") == 0:
            assert (c.get("token") or cid.startswith("sc_") or c.get("rarity", 0) >= 3 or
                    cid in {"h_backstep", "h_knife", "h_second_wind", "p_cool", "p_czn_unity",
                            "p_stoke", "m_battle_plan", "n_czn_adagio"}), cid
        if (c.get("alt") or {}).get("target") not in (None, "none"):
            assert cid in allowed_alt, cid
    assert cards["h_rng_guilty"]["cost"] == 1
    assert next(o for o in cards["h_rng_guilty"]["main"]["do"] if o["op"] == "draw")["n"] == 2
    assert cards["m_run"]["cost"] == 1


def test_adagio_sets_pending_discard_and_player_resolves():
    data = M.load()
    run = M.Run(data=data, seed=81, hero="merc")
    b = Battle(ED, run, run.fights[0], seed=81)
    h, foe = b.hero, b.foes()[0]
    put(h, (2, 2))
    put(foe, (3, 2))
    b.hand = [M.Card("n_czn_adagio", run.defs)]
    b.energy = 9
    finish(b.play(b.hand[0], "main", h))
    assert b.pending_discard == 2
    assert len(b.hand) >= 2
    chosen = b.hand[:2]
    b.resolve_discard(chosen)
    assert b.pending_discard == 0
    assert all(c in b.discard for c in chosen)
