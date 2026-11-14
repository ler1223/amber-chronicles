"""Таверна из комнат (квиз 2026-11-11): полоса комнат 1–6; «Сборы» — глава, ступень, формат, автокаст, отряд,
лист героя по ПКМ; Двор, Мастерская, Стройка, Зал славы (кладбище и книга)."""
import pygame

from tests.test_expedition_ui import click, frame, key, new_app


def test_rooms_strip_switches_rooms(tmp_path):
    from game import tavern_rooms as R
    app = new_app(tmp_path)
    assert isinstance(app.scene, R.HallRoom)
    for i, (rid, *_rest) in enumerate(R.ROOMS):
        key(app, pygame.K_1 + i)
        assert isinstance(app.scene, R.ROOM_CLASSES[rid])
        frame(app)
    click(app, ("room", "hall"))
    assert isinstance(app.scene, R.HallRoom)


def test_chapter_and_muster_are_separate_rooms(tmp_path):
    from game import tavern_rooms as R
    from ui import settings
    app = new_app(tmp_path)
    key(app, pygame.K_9)
    sc = app.scene
    assert isinstance(sc, R.ChapterRoom)
    frame(app)
    click(app, ("party_mode", True))
    assert app.profile.solo
    click(app, ("autocast", "off"))
    assert settings.SETTINGS["autocast_start"] == "off"
    click(app, ("party_mode", False))
    sc.act(("tier", 5))
    assert sc.tier == 0                                    # закрытая ступень не выбирается
    app.profile.tier_open = 3
    click(app, ("tier", 3))
    assert sc.tier == 3
    sc.act(("chapter", "forge"))
    assert sc.chapter == "swamp"                           # глава закрыта
    app.profile.chapter_wins = {"swamp": 1}
    click(app, ("chapter", "forge"))
    assert sc.chapter == "forge" and sc.tier == 0
    key(app, pygame.K_2)
    assert isinstance(app.scene, R.MusterRoom)
    key(app, pygame.K_1)
    key(app, pygame.K_9)
    assert app.scene.chapter == "forge"                    # выбор — общий для комнат


def test_muster_hero_sheet_right_click(tmp_path):
    from game.expedition_scenes import TavernHeroScene
    app = new_app(tmp_path)
    key(app, pygame.K_2)
    mus = app.scene
    frame(app)
    uid = app.profile.hall()[1].uid
    mus.act(("recruit", uid), 3)
    sc = app.scene
    assert isinstance(sc, TavernHeroScene) and sc.heroes[sc.idx].uid == uid
    assert app.exp is None                                 # просмотр не начинает поход
    frame(app)
    key(app, pygame.K_RETURN)                              # взять в поход прямо из листа
    assert uid in mus.picked
    key(app, pygame.K_RIGHT)
    frame(app)
    key(app, pygame.K_ESCAPE)
    assert app.scene is mus


def test_hall_click_opens_sheet_and_shows_resume(tmp_path):
    from game import tavern_rooms as R
    from game.expedition_scenes import TavernHeroScene
    app = new_app(tmp_path)
    frame(app)
    uid = app.profile.hall()[0].uid
    click(app, ("hero", uid))
    assert isinstance(app.scene, TavernHeroScene)
    key(app, pygame.K_ESCAPE)
    assert isinstance(app.scene, R.HallRoom)


def test_endless_muster_opens_skill_picker(tmp_path):
    from game import tavern_rooms as R
    from sim import story_meta
    app = new_app(tmp_path)
    app.switch_mode("solo")
    app.to_hub()
    key(app, pygame.K_2)
    assert isinstance(app.scene, R.MusterRoom)
    h = app.profile.hall()[0]
    h.level = 10
    frame(app)
    click(app, ("endless_skill", h.uid))
    assert isinstance(app.scene.overlay, R.EndlessSkillOverlay)
    ov = app.scene.overlay
    assert len(ov.regular()) >= len(story_meta.one_skill_choices(app.profile.data, h.cls, h.level, h))
    assert ov.ults()
    old = h.endless_skill
    choices = story_meta.one_skill_choices(app.profile.data, h.cls, h.level, h)
    sid = next(s for s in choices if s != old)
    click(app, ("pick", sid))
    assert h.endless_skill == sid


def test_muster_chest_equips_artifact(tmp_path):
    from game import tavern_rooms as R
    app = new_app(tmp_path)
    prof = app.profile
    prof.glory, prof.mats = 9999, {m: 50 for m in prof.xd["materials"]}
    prof.buildings["ws_forge"] = 1
    art = prof.craft("ws_forge", "belt", "militia", 1.0)
    key(app, pygame.K_2)
    h = prof.hall()[0]
    click(app, ("slot", h.uid))
    assert isinstance(app.scene.overlay, R.ChestOverlay)
    click(app, ("art", art["uid"]))
    assert art["uid"] in h.arts
    click(app, ("off", art["uid"]))
    assert not h.arts
    key(app, pygame.K_ESCAPE)
    assert app.scene.overlay is None


def test_fame_cemetery_and_book(tmp_path):
    from game import tavern_rooms as R
    app = new_app(tmp_path)
    prof = app.profile
    prof.fallen = [{"name": f"Павший {i}", "cls": "warrior", "level": 5, "chapter": "swamp", "act": 1,
                    "reason": "погиб в бою", "solo": False, "wins": 0, "titles": [],
                    "chronicle": [{"kind": "death", "text": "Погиб", "run": 1, "chapter": "swamp"}], "feats": {}}
                   for i in range(5)]
    key(app, pygame.K_6)
    assert isinstance(app.scene, R.FameRoom)
    frame(app)
    click(app, "cemetery")
    cem = app.scene
    assert isinstance(cem, R.CemeteryScene)
    cem.cam = float(cem.gx(2))
    frame(app)
    assert cem.nearest() == 2
    key(app, pygame.K_l)                                   # летопись павшего — книга на его странице
    book = app.scene
    assert isinstance(book, R.BookScene)
    kind, page = book.pages[book.idx]
    assert kind == "fallen" and page is prof.fallen[2]
    frame(app)
    key(app, pygame.K_RIGHT)
    assert book.idx == min(len(book.pages) - 1, book.pages.index((kind, page)) + 1)
    key(app, pygame.K_ESCAPE)
    assert app.scene is cem
    key(app, pygame.K_ESCAPE)
    assert isinstance(app.scene, R.FameRoom)


def test_chest_scrolls_and_gem_viewer_rotates(tmp_path):
    """Сундук с множеством камней — полоса прокрутки (колесо, перетаскивание); витрина — вращение мышью."""
    from game import tavern_rooms as R
    app = new_app(tmp_path)
    prof = app.profile
    prof.glory, prof.mats = 99999, {m: 999 for m in prof.xd["materials"]}
    prof.buildings["ws_jewel"] = 1
    for i in range(30):
        prof.add_rough("ruby")
        prof.cut_gem("ruby", 1.0)
    key(app, pygame.K_3)
    room = app.scene
    room.overlay = R.ChestOverlay(room)
    click(app, ("tab", "gems"))
    frame(app)
    assert "chest_gems" in room.scroll_regs
    area, track = room.scroll_regs["chest_gems"][:2]
    room.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=area.center, rel=(0, 0), buttons=(0, 0, 0)))
    room.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-2))
    reg = room.scroll_regs["chest_gems"]
    assert room.scroll_pos["chest_gems"] == min(2, reg[2] - reg[3])      # прокрутка — до последнего пикселя
    room.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(track.centerx, track.bottom - 2), button=1))
    room.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(track.centerx, track.bottom - 2), button=1))
    frame(app)
    assert room.scroll_pos["chest_gems"] == room.scroll_regs["chest_gems"][2] - room.scroll_regs["chest_gems"][3]
    gem = prof.gems[-1]
    click(app, ("gem_view", gem["uid"]))                   # последний камень виден после прокрутки
    viewer = room.overlay
    assert isinstance(viewer, R.GemViewer)
    m0 = viewer.insp.m
    c = viewer.view_rect().center
    room.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=c, button=1))
    room.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(c[0] + 60, c[1] + 40), rel=(60, 40), buttons=(1, 0, 0)))
    room.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(c[0] + 60, c[1] + 40), button=1))
    assert viewer.insp.m != m0
    frame(app)
    key(app, pygame.K_ESCAPE)
    assert isinstance(room.overlay, R.ChestOverlay)        # витрина закрылась — назад в сундук


def test_bag_scrolls_in_hero_sheet(tmp_path):
    from game import expedition_scenes as XS
    from sim import expedition as X
    app = new_app(tmp_path)
    XS.start_run(app, [h.uid for h in app.profile.roster[:2]])
    run = app.exp
    for _ in range(30):
        run.bag.append(run.new_item())
    app.switch(XS.HeroScene(app, 0, back=lambda: None))
    frame(app)
    assert "bag" in app.scene.scroll_regs
    area = app.scene.scroll_regs["bag"][0]
    app.scene.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=area.center, rel=(0, 0), buttons=(0, 0, 0)))
    app.scene.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-3))
    for _ in range(30):                                   # плавная прокрутка — доезжает за доли секунды
        frame(app)
    shown = [a[1] for _, a, _ in app.scene.hits if isinstance(a, tuple) and a[0] == "equip"]
    assert shown and shown[0] == run.bag[3]["uid"]
    assert X


def test_wide_window_mouse_hits_stage_scene(tmp_path):
    """Широкое окно (21:9): сцена-колонка 1280 по центру — клик по кнопке попадает в неё, а не мимо;
    поля — рамки, а не копия сцены."""
    import main
    from ui import theme as T, present, layout as L
    from game import workshop_games as G, workshop_scenes as WS
    app = new_app(tmp_path)
    g = G.JewelCut(1)
    app.switch(WS.MiniGameScene(app, g, "Огранка", lambda q: None, lambda: None))
    old = (T.SCREEN_W, T.SCREEN_H)
    T.SCREEN_W, T.SCREEN_H = 1911, 800
    try:
        assert not app.scene.stage                    # огранка — на весь широкий холст, не колонкой
        frame(app)
        r = g.choice_rects[2]
        assert app.scene.area().w > 1800
        main.dispatch(app.scene, pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=r.center, button=1))
        assert g.phase == "cut" and g.cut is G.CUTS[2]
        ox = L.content_ox(1911)
        bg = present.side_frames(1911, 800)
        assert bg.get_at((ox + 600, 400))[:3] == (16, 12, 9) and bg.get_at((20, 400))[:3] != (16, 12, 9)
    finally:
        T.SCREEN_W, T.SCREEN_H = old
