"""Полное наблюдение и новая сеть: всё поле, все юниты и объекты, общие признаки; та же сеть на torch и numpy;
короткий шаг лаборатории на полном наблюдении. Старый battle_obs при этом не меняется."""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

pytest.importorskip("torch")

from test_expedition import ED  # noqa: E402
from sim import entity_net as E  # noqa: E402
from sim import full_obs as F  # noqa: E402
from sim import neural as NN  # noqa: E402
from sim import nn_lab as LAB  # noqa: E402
from sim import np_net as NP  # noqa: E402
from sim import trials as T  # noqa: E402
from sim.combat import ENEMY, PLAYER, Combat  # noqa: E402


def combat_with(**enc_changes):
    """Бой с целью, охраной, источником и нейтральным объектом — чтобы проверить полное наблюдение."""
    data = copy.copy(ED)
    data.encounters = copy.deepcopy(ED.encounters)
    data.encounters[0].update(copy.deepcopy(enc_changes))
    return Combat(data, 0)


def test_full_observation_has_whole_battlefield_and_objects():
    c = combat_with(
        objective={"type": "hold", "cells": [[4, 2], [5, 2], [4, 3], [5, 3]], "time": 25.0},
        objects=[{"type": "cart", "pos": [0, 2]},
                 {"type": "nest", "pos": [9, 0], "spawn": ["slime"]},
                 {"type": "boulder", "pos": [7, 5]}],
    )
    v = F.View(c)
    hero = c.heroes(PLAYER)[0]
    obs, cands = v.observe(hero)
    sc = F.schema(c.data)
    mi = {n: i for i, n in enumerate(sc["map"])}
    ui = {n: i for i, n in enumerate(sc["unit"])}
    gi = {n: i for i, n in enumerate(sc["glob"])}

    assert len(v.units) == len([u for u in c.units if u.alive])
    assert len(cands["units"]) == len(v.units) and cands["units"][0] is hero
    assert obs["units"].shape == (len(v.units), len(sc["unit"]))
    assert obs["map"].shape == (len(sc["map"]), F.SIDE, F.SIDE)
    assert obs["glob"].shape == (len(sc["glob"]),)
    assert obs["tmask"].shape == (F.N_TYPES,) and obs["umask"].shape == (F.N_TYPES, F.MAX_U)
    assert obs["cmask"].shape == (F.N_TYPES, F.SIDE * F.SIDE)

    # Цель, охрана, источник и нейтральный объект видны отдельными слоями и признаками.
    assert obs["map"][mi["hold"]].sum() == 4
    assert obs["map"][mi["guard"]].sum() == 1
    assert obs["map"][mi["source"]].sum() == 1
    assert obs["map"][mi["neutral"]].sum() == 1
    assert obs["glob"][gi["objective_hold"]] == 1 and obs["glob"][gi["hold_time"]] > 0
    assert obs["glob"][gi["n_guards"]] > 0 and obs["glob"][gi["n_sources"]] > 0
    guard = next(u for u in cands["units"] if u.obj and u.obj.get("guard"))
    source = next(u for u in cands["units"] if u.obj and u.obj.get("source"))
    neutral = next(u for u in cands["units"] if u.obj and u.team != PLAYER and u.team != ENEMY)
    for u, flag in ((guard, "is_guard"), (source, "is_source"), (neutral, "is_neutral_object")):
        row = cands["units"].index(u)
        assert obs["units"][row, ui[flag]] == 1

    # Атака по цели и шаг по полной карте переводятся в действие и обратно без потери клетки.
    a = F.encode(hero, {"type": "attack", "target": next(u for u in cands["units"] if hero.is_enemy(u))},
                 obs, cands)
    assert a is not None and F.decode(cands, obs["ttype"], *a)[0] == "attack"
    j = int(np.flatnonzero(obs["cmask"][F.T_MOVE])[0])
    cell = cands["cells"][j]
    a = F.encode(hero, {"type": "move", "cell": cell}, obs, cands)
    assert a == (F.T_MOVE, j)
    assert F.decode(cands, obs["ttype"], *a) == ("move", cell)


def test_full_observation_knows_cell_types_and_arena_events():
    """Клетка — не просто «опасно»: видны рельеф, тип опасности, таймер, укрытие и владелец.
    События поля (ковш расплава, меха) видны как предупреждение, таймер и направление."""
    c = combat_with()
    cell = c.grid.get((1, 1))
    cell.terrain = "lava"
    cell.base_terrain = "stone"
    cell.hazard = "oil"
    cell.hazard_time = 5.0
    cell.hazard_team = None
    cell.cover = "half"
    cell.portal = True
    c.arena = [
        {"type": "ladle", "pending": 1.5, "timer": 10.0, "cells": [(1, 1)], "damage": 20, "burn": 5},
        {"type": "bellows", "pending": 0.8, "timer": 12.0, "dir": (-1, 0), "push": 1},
    ]
    v = F.View(c)
    obs, _ = v.observe(c.heroes(PLAYER)[0])
    sc = F.schema(c.data)
    mi = {n: i for i, n in enumerate(sc["map"])}
    gi = {n: i for i, n in enumerate(sc["glob"])}

    # Все типы рельефа и опасностей из data/config.json имеют собственные каналы.
    for name in sc["terrains"]:
        assert f"terrain_{name}" in mi
    for name in sc["hazards"]:
        assert f"hazard_{name}" in mi

    assert obs["map"][mi["terrain_lava"], 1, 1] == 1
    assert obs["map"][mi["base_terrain_id"], 1, 1] > 0 and obs["map"][mi["terrain_changed"], 1, 1] == 1
    assert obs["map"][mi["hazard_oil"], 1, 1] == 1
    assert obs["map"][mi["hazard_time"], 1, 1] == pytest.approx(0.25)
    assert obs["map"][mi["hazard_foes_only"], 1, 1] == 1
    assert obs["map"][mi["hazard_team_none"], 1, 1] == 1
    assert obs["map"][mi["cover_half"], 1, 1] == 1
    assert obs["map"][mi["portal"], 1, 1] == 1

    assert obs["map"][mi["arena_ladle"], 1, 1] == 1
    assert obs["map"][mi["arena_warn"], 1, 1] == 1
    assert obs["map"][mi["arena_pending"], 1, 1] == pytest.approx(0.3)
    assert obs["glob"][gi["arena_ladle_on"]] == 1 and obs["glob"][gi["arena_ladle_pending"]] > 0
    assert obs["glob"][gi["arena_ladle_damage"]] > 0 and obs["glob"][gi["arena_ladle_burn"]] > 0
    assert obs["glob"][gi["arena_bellows_on"]] == 1
    assert obs["glob"][gi["arena_bellows_dir_x"]] == -1 and obs["glob"][gi["arena_bellows_dir_y"]] == 0
    assert obs["glob"][gi["arena_bellows_push"]] > 0


def test_full_numpy_net_matches_torch():
    c = combat_with(objective={"type": "hold", "cells": [[4, 2], [5, 2]], "time": 25.0},
                    objects=[{"type": "nest", "pos": [9, 0], "spawn": ["slime"]}])
    v = F.View(c)
    obs = [v.observe(u)[0] for u in v.units[:5]]
    names = F.names(v.sc)
    net = E.make_net({k: len(x) for k, x in names.items()}, F.ARCH).eval()
    import torch
    with torch.inference_mode():
        ref = [t.numpy() for t in net(E.collate(obs, max_u=F.MAX_U, max_s=F.MAX_S, n_types=F.N_TYPES))]
    P = {k: w.numpy() for k, w in net.state_dict().items()}
    ob = NP.collate(obs, F.MAX_U, F.MAX_S)
    got = NP.forward(P, net.arch, ob)
    for r, g, m in zip(ref, got, (ob["tmask"], ob["umask"], ob["cmask"], None)):
        assert np.abs(r - g if m is None else (r - g)[m]).max() < 1e-3


def test_full_lab_battle_and_learner_step(tmp_path):
    torch = __import__("torch")
    tr = LAB.Trainer(str(tmp_path), {"workers": 1, "device": "cpu", "batch": 64, "full": True}, fresh=True)
    assert tr.obs_mod is F and tr.defaults == LAB.DEFAULTS_FULL
    sc = LAB.scenario(tr.ed, 5)
    agents = tr.showcase_agents()
    run, c, ctl = LAB.play(tr.ed, sc, agents, dict(tr.cfg, max_time=8))
    assert ctl.B is F and all(u.team == PLAYER for u in ctl.agents)
    batches, _, cls_r, _, _ = LAB.battle_report(run, c, ctl, agents, tr.cfg)
    assert set(batches) == {NN.HERO_KEY} and set(cls_r) == set(sc["squad"])
    b = batches[NN.HERO_KEY]
    assert b["obs"]["map"].dtype == np.uint8 and len(b["obs"]["units"]) == len(b["adv"]) > 0
    before = tr.agents[NN.HERO_KEY].net.state_dict()["unit_in.weight"].clone()
    tr.pending[NN.HERO_KEY] = [b]
    tr._update(NN.HERO_KEY)
    assert not torch.equal(tr.agents[NN.HERO_KEY].net.state_dict()["unit_in.weight"], before)
    tr.publish_weights()
    got, _ = NP.load(LAB.weights_path(tr.wdir, tr.version))
    assert got[NN.HERO_KEY]["arch"]["side"] == F.SIDE
    assert got[NN.HERO_KEY]["net"]["map_in.weight"].shape[1] == len(F.schema(tr.ed)["map"])


def test_full_agent_does_not_load_incompatible_old_weights():
    old = NN.Agent("hero")
    old.ensure(ED)
    ag = NN.Agent("hero", old.state(), obs=F, net=E, arch=F.ARCH)
    ag.ensure(ED)                                  # старая ёмкость не подходит: новые веса, без ошибки формы
    assert ag.net.arch["d"] == F.ARCH["d"]
    assert ag.names["unit"] == F.schema(ED)["unit"]


def test_full_trial_random_uses_full_observation():
    sc = T.scenarios(ED, 1, seed=8)[0]
    r = T.run_trial(ED, sc, "random", cfg={"max_time": 1.0, "full": True})
    assert r["mode"] == "random" and r["seed"] == sc["seed"] and 0.0 <= r["hp"] <= 1.0


def test_full_trials_resolve_separate_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(T.LAB, "ROOT", str(tmp_path))
    live = tmp_path / "save" / "lab_full" / "live"
    live.mkdir(parents=True)
    (live / "version.txt").write_text("7", encoding="utf-8")
    assert T.resolve_checkpoint(None, {"full": True}) == str(live)
    assert T.resolve_checkpoint(None, {}) == T.LAB.DEFAULTS
