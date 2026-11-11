"""Мета экспедиции: трофеи глав, постройки таверны (слава + трофеи), обеты тяжести, ветераны и зал славы,
общая таверна у Экспедиции и Одиночки."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_expedition import ED, X  # noqa: E402
from sim.combat import Combat  # noqa: E402

XD = ED.expedition


def profile(tmp_path=None, **kw):
    prof = X.ExpeditionProfile(ED, str(tmp_path / "p.json") if tmp_path else None, **kw)
    return prof


def test_boss_gives_chapter_trophies_kept_after_defeat():
    prof = profile()
    run = prof.start([h.uid for h in prof.roster[:2]], seed=1)
    boss = next(n for n in run.nodes.values() if n["type"] == "boss")
    run.node = boss["id"]
    boss["encounter"] = run.boss_encounter()
    c = Combat(run.data, boss["encounter"], squad=run.combat_squad(), enemy_scale=run.enemy_scale())
    c.result = "victory"
    run.finish_battle(c)
    assert run.trophies == {"amber": 1}
    run.result = "defeat"
    prof.finish(run)
    assert prof.trophies == {"amber": 1} and len(prof.fallen) == 2


def test_buildings_cost_glory_and_trophies_and_work(tmp_path):
    prof = profile(tmp_path)
    assert not prof.build("altar")                                   # нет ни славы, ни янтаря
    prof.glory, prof.trophies = 5000, {"amber": 9, "ember": 9}
    for bid in ("smithy", "altar", "library", "yard", "infirmary"):
        assert prof.build(bid)
    assert prof.glory < 5000 and prof.trophies["amber"] < 9
    again = profile(tmp_path)
    assert again.building_level("altar") == 1
    run = prof.start([h.uid for h in prof.roster[:2]], seed=2)
    assert all(h.gear.get("weapon") or any(i["slot"] == "weapon" for i in run.bag) for h in run.heroes)
    assert all(h.level >= 2 for h in run.heroes)                    # двор: +1 уровень
    assert run.start_offers and len(run.start_offers) == 2          # алтарь: дар 1 из 2
    assert run.cfg["post_battle_heal"] > XD["config"]["post_battle_heal"]   # лазарет
    h = run.heroes[0]
    h.sp, h.pick_offer = 1, None
    first = run.pick_cards(h)
    assert len(first) == 2 and run.rerolls_left() == 2                # выбор из двух, библиотека — перебросы
    assert run.reroll_cards(h) and run.rerolls_left() == 1 and len(run.pick_cards(h)) == 2


def test_veterans_return_stronger_and_fallen_go_to_hall():
    prof = profile()
    picked = [h.uid for h in prof.roster[:2]]
    run = prof.start(picked, seed=5)
    for h in run.heroes:
        for _ in range(6):
            run.gain_xp(h, run.xp_next(h))
    sid = run.heroes[0].skills[0]
    if sid in ED.branches:
        run.heroes[0].branches[sid] = ("A", 2)
    run.result = "victory"
    end = prof.finish(run)
    vets = [h for h in prof.roster if h.vet]
    assert len(vets) == 2 and set(end["veterans"]) == {h.name for h in run.heroes}
    v = next(h for h in vets if h.uid == run.heroes[0].uid)
    assert v.rank == run.heroes[0].rank + 1 and v.level == int(XD["tavern"]["ranks"][str(v.rank)]["level"])
    assert not v.gear and v.vet["wins"] == 1
    if sid in ED.branches:
        assert v.branches == {sid: ("A", 1)}
    run2 = prof.start([v.uid], seed=6) if prof.solo else prof.start([v.uid, prof.roster[-1].uid], seed=6)
    run2.result = "defeat"
    prof.finish(run2)
    assert any(f["name"] == v.name for f in prof.fallen) and v.uid not in [h.uid for h in prof.roster]


def test_tavern_is_shared_between_squad_and_solo(tmp_path):
    prof = profile(tmp_path)
    prof.glory = 77
    prof.save()
    solo = profile(tmp_path, solo=True)
    assert solo.glory == 77 and solo.solo and not any(h.solo for h in solo.roster)
    run = solo.start([solo.roster[0].uid], seed=7)
    assert run.solo and run.heroes[0].solo
    run.result = "victory"
    solo.finish(run)
    squad = profile(tmp_path)
    vet = next(h for h in squad.roster if h.vet)
    assert vet.vet["solo"] and vet not in squad.hall()               # ветеран-одиночка в отряд не идёт
    assert len(squad.hall()) == squad.hall_size()                    # зал отряда при этом полный
    try:
        squad.start([vet.uid, squad.hall()[0].uid], seed=8)
        assert False, "одиночку не берут в отряд"
    except ValueError:
        pass
    back = profile(tmp_path, solo=True)
    assert vet.uid in [h.uid for h in back.hall()]                   # в одиночке он ждёт — с теми же навыками
    run = back.start([vet.uid], seed=9)
    assert run.heroes[0].skills == next(h for h in squad.roster if h.uid == vet.uid).skills
    sq = profile(tmp_path)                                           # ветеран отряда может пойти и в одиночку
    r = sq.start([h.uid for h in sq.hall()[:2]], seed=10)
    r.result = "victory"
    sq.finish(r)
    svet = next(h for h in profile(tmp_path, solo=True).hall() if h.vet and not h.vet["solo"])
    assert svet


def test_gifts_are_plenty_two_choices_and_all_build():
    """Даров хватает на весь поход одиночки: у каждого класса ≥ 22 подходящих; выбор — из 2; каждый дар собирается."""
    gifts = XD["gifts"]
    assert len(gifts) >= 60
    for cls in ED.classes:
        h = X.Hero({"uid": "a", "name": "А", "cls": cls, "skills": []})
        run = X.Expedition(ED, [h], seed=1)
        ok = [g for g in gifts if run.gift_ok(run.heroes[0], g) and not gifts[g].get("thread")]
        assert len(ok) >= 22, (cls, len(ok))
        for gid in ok:
            hh = X.Hero(run.heroes[0].to_dict())
            hh.gifts = [gid]
            assert run.proto(hh)["hp"] > 0
        assert len(run.reward_offers("boss")) == 2
    run.heroes[0].gifts = ["fire_soul"]
    assert not run.gift_ok(run.heroes[0], "frost_soul")              # одна «душа» на героя


def test_new_items_roll_and_describe():
    it = XD["items"]
    assert len(it["bases"]) >= 20 and len(it["uniques"]) >= 70
    run = X.Expedition(ED, [X.Hero({"uid": "a", "name": "А", "cls": "warrior", "skills": []})], seed=2)
    for uid, u in it["uniques"].items():
        if u.get("class") or u.get("masterpiece"):
            continue
        item = X.make_item(run.xd, run.rng, 1, "unique", unique=uid, uid="x")
        assert X.item_lines(run.xd, item)
        run.heroes[0].gear = {item["slot"]: item}
        assert run.proto(run.heroes[0])["hp"] > 0


def test_gift_detail_shows_numbers_and_gives_gift(tmp_path):
    import test_expedition_ui as U
    from game import expedition_scenes as XS
    app = U.new_app(tmp_path)
    XS.start_run(app, [h.uid for h in app.profile.roster[:2]])
    run = app.exp
    run.node = run.available()[0]
    rs = XS.RewardScene(app, {}, [{"type": "gift", "id": "glass_cannon"}, {"type": "gift", "id": "iron_will"}],
                        then=lambda: None)
    app.switch(rs)
    U.click(app, ("pick", 0))
    det = app.scene
    assert type(det).__name__ == "GiftDetailScene"
    p0, p1, m0, m1 = det._protos(det.hero_i)
    assert p1["hp"] < p0["hp"] and p1["attack"]["damage"] > p0["attack"]["damage"] and m1["dealt"] > m0["dealt"]
    det.update(1 / 30)
    U.frame(app)
    det.key(__import__("pygame").K_RETURN)
    assert "glass_cannon" in run.heroes[det.hero_i].gifts


def test_pick_scene_two_cards_with_demo(tmp_path):
    """Выбор улучшения: две карты, клик — демонстрация навыка («станет» / «сейчас»), повторный клик — взять."""
    import test_expedition_ui as U
    from game import expedition_scenes as XS
    app = U.new_app(tmp_path)
    XS.start_run(app, [h.uid for h in app.profile.hall()[:2]])
    run = app.exp
    h = run.heroes[0]
    for o in run.heroes:                                   # выбор только у этого героя (лучник ждал бы колчан)
        o.sp, o.pick_offer = 0, None
        o.quivers = ["fire", "frost", "bleed"][:run.quivers_due(o)]
    h.sp, h.pick_offer = 1, None
    for s in h.skills:
        h.ranks[s] = 3
    done = []
    sc = XS.PickScene(app, then=lambda: done.append(1), only=h)
    app.switch(sc)
    cards = run.pick_cards(h)
    assert len(cards) == 2
    sc.update(1 / 30)
    assert sc.preview.proto and sc.preview.sid == cards[0].get("skill", sc.preview.sid)
    U.click(app, ("card", 1))
    assert sc.sel == 1 and h.sp == 1                                   # первый клик — только выбор
    sc.update(1 / 30)
    sc.act(("view", False))
    sc.update(1 / 30)
    U.frame(app)
    before = (dict(h.branches), dict(h.ranks), list(h.skills), len(h.perks))
    U.click(app, ("card", 1))
    assert h.sp == 0 and (dict(h.branches), dict(h.ranks), list(h.skills), len(h.perks)) != before and done
