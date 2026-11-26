import pytest

from deck import model as M
from sim.grid import Grid, cheb
from test_deck import card, finish, hero_battle, put
from test_pyro_spirits import add_spirit, arena


def test_stoke_created_card_pays_heat_even_when_copied(monkeypatch):
    battle, _ = arena()
    hero = battle.hero
    spirit = add_spirit(battle, "t_spirit_ember")
    stoke = card(battle, "p_stoke_embers")
    stoke.lvl = 2
    hero.ds["heat"] = 3
    cid = "m_duelist"
    monkeypatch.setattr(battle.rng, "choice", lambda pool: pool[pool.index(cid)])

    finish(battle.play(stoke, "main", spirit))

    retained = next(c for c in battle.hand if c.cid == cid)
    ordinary = M.Card(cid, battle.run.defs)
    assert retained.preview_key() != ordinary.preview_key()
    assert retained.cost == ordinary.cost and not retained.levels
    assert battle.pay_pool(retained) == "heat" and battle.pay_pool(ordinary) == "energy"
    assert not battle.can_afford(retained) and hero.ds["heat"] == 0

    battle.copy_hand_card(retained)
    clone = next(c for c in battle.hand if c.cid == cid and c is not retained)
    assert battle.pay_pool(clone) == "heat" and clone.cost == retained.cost
    hero.ds["heat"] = 2 * retained.cost
    battle.energy = 0
    for c in (retained, clone):
        assert battle.targets(c, "main") == [hero]
        finish(battle.play(c, "main", hero))
    assert hero.ds["heat"] == battle.energy == 0


@pytest.mark.parametrize("picks, step, shield", [([], False, 0), ([1], False, 6), ([1], True, 6)])
def test_sweep_uses_initial_surround_for_every_target_and_bonus(picks, step, shield):
    battle, _ = hero_battle("hunter")
    battle.c.grid = Grid(["." * 9] * 7, {".": {}})
    hero = battle.hero
    first, second, *other_foes = battle.foes()
    for foe in other_foes:
        foe.alive = False
    origin = (3, 2) if step else (4, 3)
    put(battle, hero, origin)
    for foe, cell in ((first, (3, 3)), (second, (5, 3))):
        put(battle, foe, cell)
        foe.edef = {}
        foe.hp = 100
    defs = battle.run.defs
    if step:
        base = defs["sweep"]
        move_use = {"target": "cell_step", "step": 1}
        upgraded = dict(base["growth"][0]["options"][1])
        upgraded["main"] = {**upgraded["main"], **move_use}
        defs = {"sweep": {**base, "growth": [{"options": [None, upgraded]}]}}
        assert not battle.met({"k": "surrounded"})
    sweep = M.Card("sweep", defs, picks=picks)
    battle.hand.append(sweep)

    finish(battle.play(sweep, "main", (4, 3) if step else hero))

    assert hero.cell == (4, 3)
    assert [foe.hp for foe in (first, second)] == [93, 93]
    assert all(cheb(foe.cell, hero.cell) == 2 for foe in (first, second))
    assert hero.shield == shield
