"""Режим обучения: признаки и варианты действий, контроллер сетей в бою (свои и подмога), обучение PPO и
подражание, хранение сетей (герой, школа, враги), приказ игрока как пример; призванные ходят сами, статы от
хозяина; бард играет мелодиями."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

pytest.importorskip("torch")

from test_expedition import ED, X  # noqa: E402
from sim import neural as NN  # noqa: E402
from sim.combat import ENEMY, PLAYER, Combat  # noqa: E402


def fight(classes=("warrior", "priest", "archer"), seed=3):
    h = [X.Hero({"uid": f"u{i}", "name": "Т", "cls": c, "skills": []}) for i, c in enumerate(classes)]
    run = X.Expedition(ED, h, seed=seed)
    nid = run.available()[0]
    run.enter(nid)
    c = Combat(run.data, run.nodes[nid]["encounter"], squad=run.combat_squad(), enemy_scale=run.enemy_scale(),
               ai_teams=(ENEMY,))
    return run, c


def factory_for(run, c, store):
    hs = c.heroes(PLAYER)
    return lambda u: (store.hero(run.heroes[hs.index(u)]) if u in hs else None) if u.team == PLAYER \
        else store.enemy(u.proto_id)


def test_observation_tokens_and_masks():
    """Наблюдение: все юниты (сам — первый), навыки, карта 11×11, маски; приказ ↔ действие туда и обратно."""
    from sim import battle_obs as B
    run, c = fight()
    for _ in range(40):
        c.step()
    v = B.View(c)
    u = c.heroes(PLAYER)[0]
    obs, cands = v.observe(u)
    sc = B.schema(c.data)
    assert obs["units"].shape[1] == len(sc["unit"]) and cands["units"][0] is u
    assert len(cands["units"]) == len([w for w in c.units if w.alive and not w.obj])   # видит всех, не 4 ближайших
    assert obs["map"].shape == (len(sc["map"]), B.SIDE, B.SIDE) and obs["skills"].shape[0] == len(u.skills)
    assert np.isfinite(obs["units"]).all() and np.isfinite(obs["map"]).all()
    assert obs["tmask"][B.T_HOLD] and obs["tmask"][B.T_ATK]
    foe = next(w for w in cands["units"] if u.is_enemy(w))
    a = B.encode(u, {"type": "attack", "target": foe}, obs, cands)
    assert B.decode(cands, obs["ttype"], *a) == ("attack", foe)
    i = sc["unit"].index("buff:armor")
    u.buffs["armor"] = [5, 3.0]
    obs2, _ = B.View(c).observe(u)
    assert obs2["units"][0, i] != 0                                     # бафф виден сети


def test_lava_is_marked_as_danger():
    """Лава — не только отдельный слой: она попадает в danger, terrain_dps и в признак «стою в опасности»."""
    from sim import battle_obs as B
    run, c = fight()
    u = c.heroes(PLAYER)[0]
    cell = c.grid.get(u.cell)
    old = cell.terrain
    cell.terrain = "lava"
    try:
        obs, _ = B.View(c).observe(u)
        sc = B.schema(c.data)
        mi = {n: i for i, n in enumerate(sc["map"])}
        ui = {n: i for i, n in enumerate(sc["unit"])}
        assert obs["map"][mi["terrain_dps"], B.R, B.R] > 0
        assert obs["map"][mi["danger"], B.R, B.R] > 0
        assert obs["units"][0, ui["on_danger"]] == 1
    finally:
        cell.terrain = old


def test_delayed_projectile_is_on_map():
    """Снаряд в полёте виден как delay_own/delay_foe — сеть может уклониться до прилёта."""
    from sim import battle_obs as B
    run, c = fight()
    hero = c.heroes(PLAYER)[0]
    foe = c.alive(ENEMY)[0]
    c.delayed.append({"left": 0.4, "total": 0.4, "caster": hero,
                      "effects": [{"type": "damage", "amount": 10, "radius": 1}],
                      "center": foe.cell, "tunit": foe, "name": "тест"})
    v = B.View(c)
    mi = {n: i for i, n in enumerate(B.schema(c.data)["map"])}
    x, y = foe.cell
    assert v.side[PLAYER][mi["delay_own"], y + B.R, x + B.R] > 0


def test_move_mask_needs_path_around_units():
    """Шаг в клетку за союзником закрыт, если обойти нельзя: маска учитывает юнитов на пути, а не только цель."""
    from sim import battle_obs as B
    run, c = fight()
    u, ally = c.heroes(PLAYER)[:2]
    line = None
    for y in range(c.grid.h):
        for x in range(c.grid.w - 2):
            pts = [(x, y), (x + 1, y), (x + 2, y)]
            cells = [c.grid.get(p) for p in pts]
            if all(cell is not None and cell.passable for cell in cells) and not any(
                    v.alive and v not in (u, ally) and v.cell in pts for v in c.units):
                line = pts
                break
        if line:
            break
    assert line is not None
    start, mid, goal = line
    changed = []
    for yy in range(max(0, start[1] - 2), min(c.grid.h, start[1] + 3)):
        for xx in range(max(0, start[0] - 1), min(c.grid.w, start[0] + 4)):
            p = (xx, yy)
            if p in line:
                continue
            cell = c.grid.get(p)
            if cell is not None and cell.passable:
                cell.passable = False
                changed.append(cell)
    old_u, old_ally = u.cell, ally.cell
    u.cell, ally.cell = start, mid
    try:
        obs, cands = B.View(c).observe(u)
        assert not obs["cmask"][B.T_MOVE, cands["cells"].index(goal)]       # за союзником, обхода нет
        assert not obs["cmask"][B.T_MOVE, cands["cells"].index(mid)]        # в союзника нельзя
        mi = {n: i for i, n in enumerate(B.schema(c.data)["map"])}
        assert not obs["map"][mi["free"], mid[1] + B.R, mid[0] + B.R]       # слой «свободно» знает про юнита
        assert obs["map"][mi["free"], goal[1] + B.R, goal[0] + B.R]         # цель свободна, но пути нет
    finally:
        for cell in changed:
            cell.passable = True
        u.cell, ally.cell = old_u, old_ally


def test_lab_default_is_heroes_vs_autopilot():
    """По умолчанию лаборатория учит только героев: враги — правила, сеть врагов не обучается."""
    from sim import nn_lab as LAB
    assert LAB.CONFIG["opponents"] == {"rules": 1.0, "latest": 0.0, "past": 0.0}
    assert LAB.CONFIG["learn_heroes"] and not LAB.CONFIG["learn_enemies"]


def test_lab_panel_obs_refreshes_without_decision():
    """Панель «что видит сеть» получает свежие маски чаще, чем сеть принимает решения."""
    from sim import battle_obs as B
    run, c = fight()
    ctl = NN.Controller(c, factory_for(run, c, NN.Store("_unused")), teams=(PLAYER,), learn=False)
    ctl.keep_obs = True
    c.controllers.append(ctl)
    c.step()
    assert set(ctl.last_obs) == set(ctl.state) and ctl.mask_t >= 0
    assert ctl.last_obs[next(iter(ctl.last_obs))][0]["cmask"].shape[0] == B.N_TYPES


def test_event_wakes_on_danger_and_old_cast():
    """Опасность под ногами и каст, начавшийся до прошлого решения, будят сеть вне общего тика."""
    run, c = fight()
    u = c.heroes(PLAYER)[0]
    foe = c.alive(ENEMY)[0]
    ctl = NN.Controller(c, factory_for(run, c, NN.Store("_unused")))
    st = ctl.state[u]
    u.order = {"type": "attack", "target": foe}
    st["hp"], st["ready"] = u.hp, NN.Controller._ready(u)
    cell = c.grid.get(u.cell)
    old = cell.terrain
    cell.terrain = "lava"
    try:
        st["danger"] = False
        assert ctl._event(u, st, 0.1)
        st["danger"] = True
        assert not ctl._event(u, st, 0.1)
    finally:
        cell.terrain = old
    st["danger"] = False
    foe.cast = {"skill": "fireball", "left": 0.1, "total": 1.0, "target": u}
    st["cast"] = None
    assert ctl._event(u, st, 0.5)                       # каст начался раньше прошлого решения — всё равно видим
    assert not ctl._event(u, st, 0.5)                   # второй раз о том же касте не кричим
    foe.cast = None
    u.order = None                                      # без приказа не будим сеть каждый кадр: только переход
    st["idle"] = False
    assert ctl._event(u, st, 0.05)
    assert not ctl._event(u, st, 0.05)


def test_new_features_keep_old_weights():
    """Новый признак: веса старых переносятся по именам, у нового — ноль (поведение сети не меняется)."""
    from sim import battle_obs as B
    from sim import entity_net as E
    torch = __import__("torch")
    run, c = fight()
    names = B.names(B.schema(c.data))
    net = E.make_net({k: len(v) for k, v in names.items()})
    new = {k: list(v) for k, v in names.items()}
    new["unit"] = new["unit"][:5] + ["новый признак"] + new["unit"][5:]
    fresh = E.make_net({k: len(v) for k, v in new.items()})
    st = E.adapt(net.state_dict(), names, new, fresh.state_dict())
    w_old, w_new = net.state_dict()["unit_in.weight"], st["unit_in.weight"]
    assert torch.equal(w_new[:, 5], torch.zeros_like(w_new[:, 5]))
    assert torch.equal(w_new[:, 6], w_old[:, 5]) and torch.equal(w_new[:, 0], w_old[:, 0])
    fresh.load_state_dict(st)


def test_controller_learns_and_saves(tmp_path):
    run, c = fight()
    store = NN.Store(str(tmp_path))
    ctl = NN.Controller(c, factory_for(run, c, store))
    c.controllers.append(ctl)
    assert not [ai for ai in c.ais]                                   # правила обеих команд молчат
    assert set(ctl.agents) >= set(c.heroes(PLAYER))
    before = {k: v.clone() for k, v in store.hero(run.heroes[0]).net.state_dict().items()}
    for _ in range(int(25 / c.dt)):
        c.step()
    extra = c.spawn_enemy("slime", next(p for p, cell in c.grid.cells.items() if cell.passable and c.is_free(p)))
    c.step()
    assert extra in ctl.agents                                        # подмога сразу под сетью
    c.result = c.result or "defeat"
    res = ctl.finish()
    assert res and all(v is not None for v in res.values())
    ag = store.hero(run.heroes[0])
    after = ag.net.state_dict()
    assert any(not (before[k] == after[k]).all() for k in before)    # сеть изменилась
    assert ag.stats["battles"] == 1
    store.save("heroes", run.heroes[0].uid, ag)
    again = NN.Store(str(tmp_path)).hero(run.heroes[0])
    assert again.stats["battles"] == 1


def test_teacher_mode_records_examples(tmp_path):
    run, c = fight()
    store = NN.Store(str(tmp_path))
    ctl = NN.Controller(c, factory_for(run, c, store), teacher=True)
    c.controllers.append(ctl)
    for _ in range(int(10 / c.dt)):
        c.step()
    assert sum(len(st["traj"]) for st in ctl.state.values()) > 10
    ctl.finish()
    assert all(not a.buf for a in set(ctl.agents.values()))


def test_manual_order_becomes_example(tmp_path):
    run, c = fight()
    store = NN.Store(str(tmp_path))
    ctl = NN.Controller(c, factory_for(run, c, store))
    c.controllers.append(ctl)
    u = c.heroes(PLAYER)[0]
    before = {v.id: v.order for v in c.units}
    c.order_attack(u, c.alive(ENEMY)[-1])
    NN.mark_manual(c, before)
    assert u.order.get("manual")
    ctl.state[u]["t"] = -1e9
    c.step()
    ctl.state[u]["t"] = -1e9
    c.step()
    assert ctl.state[u]["pending"] is not None and ctl.state[u]["pending"][5] == 1.0 or         any(b[7] == 1.0 for b in ctl.state[u]["traj"])                # записан пример (demo)
    assert u.order and u.order.get("manual")                          # сеть не перебила приказ


def test_school_fallback_and_blend(tmp_path):
    store = NN.Store(str(tmp_path))
    run, c = fight()
    h = X.Hero({"uid": "z", "name": "Я", "cls": "mage", "skills": []})
    sc = store.school("mage")
    sc.ensure(c.data)
    ag = store.hero(h)
    ag.ensure(c.data)
    k = "unit_in.weight"
    old = sc.net.state_dict()[k].clone()
    assert (old == ag.net.state_dict()[k]).all()                       # новичок — копия школы
    assert store.school("warrior") is sc                               # одна школа на все классы
    with __import__("torch").no_grad():
        for p in ag.net.parameters():
            p.add_(1.0)
    store.blend_school("mage", ag, 0.5)
    new = store.school("mage").net.state_dict()[k]
    assert abs(float((new - old).mean()) - 0.5) < 1e-4                # школа сдвинулась к герою на половину
    assert os.path.exists(os.path.join(str(tmp_path), "school", "hero.pt"))


def test_minions_walk_and_scale_from_necro():
    h = X.Hero({"uid": "n", "name": "Н", "cls": "necro", "skills": []})
    run = X.Expedition(ED, [h], seed=2)
    for _ in range(8):
        run.gain_xp(run.heroes[0], run.xp_next(run.heroes[0]))
    nid = run.available()[0]
    run.enter(nid)
    c = Combat(run.data, run.nodes[nid]["encounter"], squad=run.combat_squad(), enemy_scale=run.enemy_scale())
    nec = c.heroes()[0]
    u = c.summon(nec, {"unit": "skeleton_minion", "duration": 30, "limit": 3}, (nec.cell[0] + 1, nec.cell[1]))
    assert u.max_hp >= int(nec.max_hp * 0.3) and u.atk_damage >= nec.atk_damage
    start = u.cell
    for _ in range(int(8 / c.dt)):
        c.step()
    assert u.cell != start or u.tally["dealt"] > 0                    # пошёл к врагу сам


def test_bard_autopilot_plays_melodies():
    from sim.combat import PLAYER as P
    h = [X.Hero({"uid": "b", "name": "Б", "cls": "bard", "skills": []}),
         X.Hero({"uid": "w", "name": "В", "cls": "warrior", "skills": []})]
    run = X.Expedition(ED, h, seed=2)
    for hh in run.heroes:
        for _ in range(6):
            run.gain_xp(hh, run.xp_next(hh))
    nid = run.available()[0]
    run.enter(nid)
    c = Combat(run.data, run.nodes[nid]["encounter"], squad=run.combat_squad(), enemy_scale=run.enemy_scale(),
               ai_teams=(ENEMY, P))
    mel = 0
    while not c.result and c.time < 60:
        c.step()
        mel += sum(1 for e in c.events if e.get("t") == "melody")
        c.events.clear()
    assert mel >= 1


def test_lab_scenario_equips_heroes_by_act():
    """Лабораторные герои получают вещи как в походе: 2 слота в первом акте, 3 во втором, 4 в третьем.
    Снаряжение детерминировано seed сценария; gear="none" оставляет старые «голые» бои для сравнения."""
    from sim import nn_lab as LAB
    for seed in (5, 6, 7):
        sc = LAB.scenario(ED, seed)
        run, _, _ = LAB.prepare(ED, sc)
        want = len(LAB.LAB_GEAR[sc["act"]])
        assert all(len(h.gear) == want for h in run.heroes)
        assert all(set(h.gear) == {slot for slot, _ in LAB.LAB_GEAR[sc["act"]]} for h in run.heroes)
    sc = LAB.scenario(ED, 5, gear="none")
    run, _, _ = LAB.prepare(ED, sc)
    assert all(not h.gear for h in run.heroes)


def test_lab_battle_and_learner_step(tmp_path):
    """Лаборатория: герои-сети против автопилота → пачка PPO (с упаковкой карты) → шаг ученика; веса уходят бойцам."""
    from sim import nn_lab as LAB
    torch = __import__("torch")
    tr = LAB.Trainer(str(tmp_path), {"workers": 1, "device": "cpu", "batch": 64}, fresh=True)
    sc = LAB.scenario(tr.ed, 5)
    agents = tr.showcase_agents()
    run, c, ctl = LAB.play(tr.ed, sc, agents, dict(LAB.CONFIG, max_time=40))
    assert any(ai.team == ENEMY for ai in c.ais) and all(u.team == PLAYER for u in ctl.agents)
    batches, rewards, cls_r, en_r, parts = LAB.battle_report(run, c, ctl, agents, LAB.CONFIG)
    assert "team" in parts[NN.HERO_KEY] and "win" in parts[NN.HERO_KEY] or "death" in parts[NN.HERO_KEY]
    assert set(batches) == {NN.HERO_KEY} and set(cls_r) == set(sc["squad"])
    b = batches[NN.HERO_KEY]
    assert b["obs"]["map"].dtype == np.uint8 and len(b["obs"]["units"]) == len(b["adv"]) > 0
    before = tr.agents[NN.HERO_KEY].net.state_dict()["unit_in.weight"].clone()
    enemy_before = tr.agents[NN.ENEMY_KEY].net.state_dict()["unit_in.weight"].clone()
    tr.pending[NN.HERO_KEY] = [b]
    tr._update(NN.HERO_KEY)
    assert not torch.equal(tr.agents[NN.HERO_KEY].net.state_dict()["unit_in.weight"], before)   # сеть героев сдвинулась
    assert torch.equal(tr.agents[NN.ENEMY_KEY].net.state_dict()["unit_in.weight"], enemy_before)  # враги не учатся
    tr.publish_weights()
    from sim import np_net as NP
    got, extra = NP.load(LAB.weights_path(tr.wdir, tr.version))
    assert np.allclose(got[NN.HERO_KEY]["net"]["unit_in.weight"],
                       tr.agents[NN.HERO_KEY].net.state_dict()["unit_in.weight"].cpu().numpy())
    assert extra["reward"]["name"] == tr.cfg["reward"]


def test_support_credit_and_team_reward():
    """Заслуги поддержки: поглощённый щитом урон — тому, кто поставил щит; контроль и баффы — источнику.
    Командный дух: доля τ награды — средняя по команде; затухание подсказок к концу обучения."""
    from sim import rewards as RW
    run, c = fight(("guardian", "priest", "archer"))
    a, b = c.heroes(PLAYER)[:2]
    foe = c.alive(ENEMY)[0]
    c.apply_effects(b, [{"type": "shield", "amount": 50, "duration": 5}], a.cell, a)
    assert a.shield_src is b
    c._hit(foe, a, {"type": "damage", "amount": 30, "kind": "melee"})
    assert b.tally["shielded"] > 0                                   # щит сработал — заслуга жреца
    c.apply_effects(a, [{"type": "stun", "duration": 2, "radius": 0}], foe.cell, foe)
    assert a.tally["cc"] > 0
    c.apply_effects(b, [{"type": "buff", "stat": "armor", "value": 3, "duration": 4}], a.cell, a)
    assert b.tally["buffs"] == 1
    r0, r1 = RW.resolve("командный", 0), RW.resolve("командный", 10 ** 6)
    assert r0["scale"] == 1.0 and r1["scale"] < 0.2 and r1["tau"] > r0["tau"]
    assert RW.resolve("победа")["w"] == {}
    ctl = NN.Controller(c, factory_for(run, c, NN.Store("_unused")), reward=dict(RW.resolve("командный"), tau=1.0))
    c.controllers.append(ctl)
    for _ in range(int(6 / c.dt)):
        c.step()
    c.result = "victory"
    raw = {}                                                          # (юнит, шаг) → номер отрезка 0.5 с
    for u, st in ctl.state.items():
        if u.team == PLAYER:
            for i, step in enumerate(st["traj"]):
                if isinstance(step[5], dict) and not step[5]["p"]:
                    raw[(u, i)] = step[5]["k"]
    ctl.collect()
    final = {}
    for u, ag in ctl.agents.items():
        if u.team == PLAYER:
            tr = ag.buf[0]                                            # у каждого героя своя сеть — одна траектория
            for i, step in enumerate(tr):
                if (u, i) in raw:
                    final.setdefault(raw[(u, i)], set()).add(round(step[5], 4))
    assert final and all(len(v) == 1 for v in final.values())       # τ = 1: в одном отрезке у всех одна награда


def test_effective_damage_and_objective_potential():
    """v2: overkill не считается, урон нормирован HP цели; потенциал цели боя входит в Φ команды."""
    from sim import rewards as RW
    run, c = fight()
    u = c.heroes(PLAYER)[0]
    foe = [x for x in c.alive(ENEMY) if not x.obj][0]
    foe.hp, foe.shield = 1, 0
    c.damage(foe, 100, u, kind="melee")
    assert u.tally["dealt_eff"] <= 1.0 + 1e-6
    assert 0.0 < u.tally["dealt_frac"] <= 1.0 + 1e-6

    c.objective = {"type": "hold", "cells": [[1, 1]], "time": 10.0}
    c.hold = 0.0
    rw = RW.resolve("команда")
    p0 = RW.potential(c, PLAYER, rw)
    c.hold = 10.0
    assert RW.potential(c, PLAYER, rw) - p0 == pytest.approx(rw["obj"])


def test_dead_hero_gets_terminal_win():
    """Победа/поражение получают все герои, включая павших: она добавляется в последний переход."""
    from sim import rewards as RW
    run, c = fight()
    store = NN.Store("_unused")
    ctl = NN.Controller(c, factory_for(run, c, store))
    c.controllers.append(ctl)
    for _ in range(int(3 / c.dt)):
        c.step()
    u = c.heroes(PLAYER)[0]
    foe = [x for x in c.alive(ENEMY) if not x.obj][0]
    c.damage(u, 9999, foe, kind="melee")
    c.step()
    c.result = "victory"
    ctl.collect()
    assert not ctl.state[u]["alive"]
    assert ctl.state[u]["parts"]["win"] == pytest.approx(RW.resolve()["win"])


def test_reward_preset_switch_only_before_first_battle(tmp_path):
    """Пресет награды меняется до первого боя; на ходу это запрещено, чтобы не ломать критика."""
    from sim import nn_lab as LAB
    tr = LAB.Trainer(str(tmp_path), {"workers": 1, "device": "cpu", "batch": 64}, fresh=True)
    assert tr.set_reward("урон")
    tr.battles = 1
    assert not tr.set_reward("роли")
    assert tr.cfg["reward"] == "урон"


def test_dagger_records_autopilot_labels_while_net_plays(tmp_path):
    """DAgger: сеть ведёт бой, но те же состояния получают метку автопилота и уходят в примеры."""
    run, c = fight()
    store = NN.Store(str(tmp_path))
    ctl = NN.Controller(c, factory_for(run, c, store), dagger=True)
    c.controllers.append(ctl)
    for _ in range(int(5 / c.dt)):
        c.step()
    assert sum(len(st["demos"]) for st in ctl.state.values()) > 0
    c.result = "defeat"
    ctl.collect()
    assert any(b[7] > 0.5 for ag in set(ctl.agents.values()) for tr in ag.buf for b in tr)


def test_numpy_net_matches_torch():
    """Сеть бойцов на numpy считает то же, что torch (бойцам не нужен torch: ~0.3 ГБ вместо ~1.1 на процесс)."""
    from sim import battle_obs as B
    from sim import entity_net as E
    from sim import np_net as NP
    torch = __import__("torch")
    run, c = fight()
    for _ in range(30):
        c.step()
    names = B.names(B.schema(c.data))
    net = E.make_net({k: len(v) for k, v in names.items()}).eval()
    v = B.View(c)
    obs = [v.observe(u)[0] for u in c.units if u.alive and not u.obj][:5]
    with torch.no_grad():
        ref = [t.numpy() for t in net(E.collate(obs))]
    P = {k: w.numpy() for k, w in net.state_dict().items()}
    ob = NP.collate(obs)
    got = NP.forward(P, net.arch, ob)
    for r, g, m in zip(ref, got, (ob["tmask"], ob["umask"], ob["cmask"], None)):
        assert np.abs(r - g if m is None else (r - g)[m]).max() < 1e-3
    new = {k: list(x) for k, x in names.items()}
    new["glob"] = new["glob"] + ["новый"]
    P2 = NP.adapt(P, names, new)
    assert P2["glob_in.weight"].shape[1] == len(new["glob"]) and not P2["glob_in.weight"][:, -1].any()


def test_battle_clone_is_exact():
    """Копия боя для планировщика идёт кадр в кадр с оригиналом и не трогает его (выстрелы в полёте — данными,
    а не замыканиями на исходный бой)."""
    from sim import planner as PL
    from sim.ai import TeamAI
    run, c = fight(("archer", "mage", "warrior"))
    c.ais.append(TeamAI(c, PLAYER))
    c.autocaster.force = True
    for _ in range(40):
        c.step()
    d = PL.clone(c)
    assert d.data is c.data and not d.controllers
    for _ in range(80):
        c.step()
        d.step()
    assert [(u.hp, u.cell) for u in c.units] == [(u.hp, u.cell) for u in d.units]


def test_planner_teacher_records_examples():
    """Учитель-планировщик: автопилот + поправки по копиям боя; ходы — примеры для сети."""
    run, c = fight()
    store = NN.Store("_unused")
    ctl = NN.Controller(c, factory_for(run, c, store), teams=(PLAYER,))
    ctl.use_planner({"k": 2, "horizon": 0.5})
    c.controllers.append(ctl)
    for _ in range(int(3 / c.dt)):
        c.step()
    assert ctl.planned > 0
    assert any(b[7] == 1.0 for st in ctl.state.values() for b in st["traj"])
