"""Поручения и экономика (квиз 2026-11-11): золото — единая валюта вне похода (бывшая «слава» ×5); найм новичков
рангом выше — за золото; общежитие для выкупленных ветеранов (места — постройкой); доска поручений (2 одновременно,
растёт постройкой): герои уходят на N походов, приносят золото/материалы/трофеи, гибель — только на опасных."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.data import GameData  # noqa: E402
from sim import expedition as X  # noqa: E402

DATA = GameData()
ED = X.expedition_data(DATA)
XD = ED.expedition


def prof_with(tmp_path=None, gold=5000, **builds):
    p = X.ExpeditionProfile(ED, str(tmp_path / "exp.json") if tmp_path else None)
    p.glory = gold
    p.buildings.update(builds)
    return p


def run_once(prof, n=2, win=True):
    """Короткий поход: старт и сразу итог (победа/поражение)."""
    free = [h for h in prof.hall() if prof.ready(h) and not h.vet and prof.hire_cost(h) == 0][:n]
    run = prof.start([h.uid for h in free], seed=3)
    run.result = "victory" if win else "defeat"
    return run, prof.finish(run)


def test_old_save_glory_becomes_gold_once(tmp_path):
    path = tmp_path / "exp.json"
    p = prof_with(tmp_path)
    p.save()
    d = json.loads(path.read_text(encoding="utf-8"))
    d.pop("econ")
    d["glory"] = 40
    path.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    again = X.ExpeditionProfile(ED, str(path))
    assert again.glory == 200                       # слава ×5 → золото
    again.save()
    assert X.ExpeditionProfile(ED, str(path)).glory == 200       # и только один раз


def test_new_tavern_has_treasury_and_run_gold_goes_to_it():
    p = X.ExpeditionProfile(ED)
    assert p.glory == XD["tavern"]["start_treasury"]
    p.glory = 0
    free = [h for h in p.hall() if p.hire_cost(h) == 0][:2]
    run = p.start([h.uid for h in free], seed=1)
    run.gold = 100
    run.result = "defeat"
    out = p.finish(run)
    assert out["glory"] == run.glory() + int(100 * XD["config"]["treasury_share"])
    assert p.glory == out["glory"]


def test_hire_cost_for_higher_ranks():
    p = prof_with(gold=0)
    h = p.hall()[0]
    h.rank = 2
    assert p.hire_cost(h) == XD["tavern"]["hire_cost"]["2"] > 0
    others = [x for x in p.hall()[1:] if p.hire_cost(x) == 0][:1]
    try:
        p.start([h.uid] + [x.uid for x in others], seed=1)
        assert False, "без золота дорогого новичка не нанять"
    except ValueError:
        pass
    p.glory = 100
    p.start([h.uid] + [x.uid for x in others], seed=1)
    assert p.glory == 100 - XD["tavern"]["hire_cost"]["2"]


def test_dorm_keeps_bought_veteran_others_leave():
    p = prof_with(dorm=1)
    assert p.dorm_slots() == XD["buildings"]["dorm"]["levels"][0]["value"]
    run, out = run_once(p)
    vets = [h for h in p.roster if h.vet]
    assert len(vets) == 2 and out["veterans"]
    keep, gone = vets
    cost = p.dorm_cost(keep)
    g0 = p.glory
    assert p.keep_in_dorm(keep) and keep.dorm and p.glory == g0 - cost
    assert keep in p.recruitable() and keep not in p.hall()     # жилец — не в зале, но в поход берётся
    run_once(p)                                     # следующий поход: невыкупленный ветеран уходит
    uids = {h.uid for h in p.roster}
    assert keep.uid in uids and gone.uid not in uids
    assert any(d["uid"] == gone.uid for d in p.away)     # ушёл странствовать — может вернуться
    assert p.release(keep) and not keep.dorm


def test_dorm_is_limited_by_building():
    p = prof_with(dorm=0)
    run_once(p)
    a, b = [h for h in p.roster if h.vet][:2]
    assert p.dorm_slots() == XD["tavern"]["dorm_base"] == 1
    assert p.keep_in_dorm(a) and not p.keep_in_dorm(b)    # без постройки — одно место
    p.buildings["dorm"] = 1
    assert p.keep_in_dorm(b)


def test_contract_board_send_and_resolve(tmp_path):
    p = prof_with(tmp_path, board=1)
    assert p.board_slots() == XD["buildings"]["board"]["levels"][0]["value"] and len(p.offers) == XD["contracts"]["offers"]
    offer = next(o for o in p.offers if XD["contracts"]["templates"][o["id"]]["heroes"] == 1)
    t = XD["contracts"]["templates"][offer["id"]]
    h = p.hall()[-1]
    assert p.send(offer, [h.uid])
    assert h.task and h not in p.hall() and not p.ready(h)
    assert offer not in p.offers
    again = X.ExpeditionProfile(ED, p.path)                   # поручение сохраняется
    assert next(x for x in again.roster if x.uid == h.uid).task["id"] == offer["id"]
    for _ in range(t["runs"]):
        _, out = run_once(p)
    news = out["news"]
    assert news and news[0]["name"] == t["name"] and news[0]["result"] in ("success", "partial", "fail")
    if any(x.uid == h.uid for x in p.roster):
        assert not h.task and h.chronicle and h.chronicle[-1]["text"].startswith("Поручение")


def test_board_slots_limit_and_heroes_count():
    p = prof_with()
    assert p.board_slots() == XD["contracts"]["base_slots"] == 2
    p.offers = [{"id": "courier", "key": f"c{i}"} for i in range(3)] + [{"id": "old_tooth", "key": "ot"}]
    free = p.hall()
    assert not p.send(p.offers[-1], [free[0].uid])          # «Старый Зуб» — нужны двое
    assert p.send(p.offers[0], [free[0].uid])
    assert p.send(p.offers[0], [free[1].uid])
    assert not p.send(p.offers[0], [free[2].uid])            # 2 места на доске
    p.buildings["board"] = 1
    assert p.send(p.offers[0], [free[2].uid])


def test_contract_chance_rewards_fitting_heroes():
    p = prof_with()
    fit_cls = XD["contracts"]["templates"]["militia"]["fit"]["classes"][0]
    h = p.hall()[0]
    base = p.contract_chance("courier", [h])
    h2 = X.Hero(dict(h.to_dict(), cls=fit_cls, rank=1))
    h.rank = 1
    assert p.contract_chance("militia", [h2]) == round(XD["contracts"]["chance"]["low"] + XD["contracts"]["chance"]["fit"], 2)
    assert base <= XD["contracts"]["chance"]["max"]


def test_resolve_outcomes_reward_wound_and_death():
    """Исходы развязки: успех — награда целиком; провал — рана (пропуск похода); на опасных — может убить."""
    p = prof_with(gold=0)
    h1, h2 = p.hall()[:2]
    for h, cid, chance in ((h1, "courier", 1.0), (h2, "old_tooth", -1.0)):
        h.task = {"id": cid, "key": cid, "left": 1, "chance": chance, "with": [h.uid]}
    news = {n["name"]: n for n in p.tick_tasks()}
    ok = news[XD["contracts"]["templates"]["courier"]["name"]]
    assert ok["result"] == "success" and ok["reward"]["gold"] > 0 and p.glory == ok["reward"]["gold"]
    bad = news[XD["contracts"]["templates"]["old_tooth"]["name"]]
    assert bad["result"] in ("fail", "partial")
    if bad["result"] == "fail":
        assert bad["hurt"] or bad["dead"]
        if bad["dead"]:
            assert h2 not in p.roster and p.fallen[-1]["name"] == h2.name
        else:
            assert h2.rest == 1 and not p.ready(h2)
    assert h1.feats.get("tasks") == 1


def test_low_risk_contracts_never_kill():
    p = prof_with()
    for i in range(30):
        h = p.hall()[0]
        h.task = {"id": "courier", "key": f"k{i}", "left": 1, "chance": -1.0, "with": [h.uid]}
        p.runs += 1
        news = p.tick_tasks()
        assert not news[0]["dead"]
        h.rest = 0


def test_materials_and_trophies_from_rewards():
    p = prof_with()
    import random
    got = p._task_reward(XD["contracts"]["templates"]["gem_vein"], random.Random(1), 1.0)
    assert got["mats"] and all(p.mats[k] == v for k, v in got["mats"].items())
    assert p.trophies.get("ember") == 1
    n0 = len(p.roster)
    got = p._task_reward(XD["contracts"]["templates"]["militia"], random.Random(1), 1.0)
    assert len(p.roster) == n0 + 1 and p.roster[0].name == got["recruit"] and p.roster[0].rank == 2


def test_busy_heroes_survive_reroll_and_roster_roll():
    p = prof_with(board=1, dorm=1)
    h = p.hall()[0]
    p.offers = [{"id": "courier", "key": "c"}]
    assert p.send(p.offers[0], [h.uid])
    assert p.reroll()
    assert h in p.roster and h.task


def test_board_and_dorm_screens(tmp_path):
    """Двор (4): доска поручений внизу (заказ, герой, отправить); у входа — ветеран, поселить в общежитие;
    этажи — колесом."""
    import pygame
    from tests.test_expedition_ui import new_app, frame, key, click
    from game import tavern_rooms as R
    app = new_app(tmp_path)
    prof = app.profile
    prof.glory = 2000
    run_once(prof)
    key(app, pygame.K_4)
    yard = app.scene
    assert isinstance(yard, R.YardRoom)
    frame(app)
    click(app, "board")
    assert isinstance(yard.overlay, R.BoardOverlay)
    o = next(o for o in prof.offers if XD["contracts"]["templates"][o["id"]]["heroes"] == 1)
    click(app, ("offer", o["key"]))
    click(app, ("send_hero", yard.overlay.free_heroes()[0].uid))
    key(app, pygame.K_RETURN)
    assert len(prof.tasks()) == 1
    key(app, pygame.K_ESCAPE)
    assert yard.overlay is None
    vet = next(h for h in prof.roster if h.vet and not h.task)
    frame(app)
    click(app, ("vet", vet.uid))
    assert isinstance(yard.overlay, R.HeroPopup)
    click(app, "keep")
    assert vet.dorm and yard.overlay is None
    yard.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=3))
    for _ in range(20):
        frame(app)
    assert yard.cam > 100                           # колесо — выше, к этажам общежития
    frame(app)
    click(app, ("lodger", vet.uid))
    click(app, "release")
    assert not vet.dorm


def test_lodgers_do_not_take_hall_places():
    """Жильцы общежития живут отдельно: зал полон гостями, жильцы — сверх него, но в поход их берут."""
    p = prof_with(dorm=3)
    run_once(p)
    vets = [h for h in p.roster if h.vet]
    for v in vets:
        assert p.keep_in_dorm(v)
    p.roll_roster(keep=True)
    assert len(p.hall()) == p.hall_size() and not any(h.dorm for h in p.hall())
    assert set(h.uid for h in vets) <= set(h.uid for h in p.recruitable())
    run = p.start([vets[0].uid, p.hall()[0].uid], seed=1)
    assert any(h.uid == vets[0].uid for h in run.heroes)
