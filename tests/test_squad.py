"""Экран «Отряд» (расстановка, замена, составы) и превью навыков в подготовке героя."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from game.app import App  # noqa: E402
from game.squad_scene import SquadScene, tile_rect  # noqa: E402
from sim.build import class_skills  # noqa: E402
from sim.data import GameData  # noqa: E402
from sim.profile import Profile  # noqa: E402
from ui import projection as P  # noqa: E402
from ui import theme as T  # noqa: E402

DATA = GameData()
pygame.init()
SCREEN = pygame.display.set_mode((T.SCREEN_W, T.SCREEN_H))


def test_place_swap_replace_remove_and_presets(tmp_path):
    prof = Profile(DATA, str(tmp_path / "p.json"), sandbox=True)
    cells = prof.formation_cells()
    assert set(cells) == set(prof.squad) and len(set(cells.values())) == 4
    war, arch = prof.squad[0], prof.squad[1]
    assert prof.place(war, cells[arch])[0]                   # на своего — меняются местами
    assert prof.formation_cells()[arch] == cells[war]
    ok, msg = prof.place("ram", (2, 5))                      # отряд полон, клетка пустая
    assert not ok and msg
    assert prof.place("ram", prof.formation_cells()[arch])[0]  # на занятую — замена
    assert "ram" in prof.squad and arch not in prof.squad
    prof.save_preset(0)
    assert prof.remove_from_squad("ram")[0] and "ram" not in prof.squad
    assert prof.load_preset(0)[0] and "ram" in prof.squad
    again = Profile(DATA, str(tmp_path / "p.json"), sandbox=True)
    assert again.formation_cells() == prof.formation_cells() and again.presets[0]


def test_formation_goes_to_the_first_battle(tmp_path):
    prof = Profile(DATA, str(tmp_path / "p.json"), sandbox=True)
    prof.place(prof.squad[0], (1, 0))
    run = prof.start_run(prof.available()[0])
    assert run.formation[0] == [1, 0]


def test_drag_from_roster_to_board():
    prof = Profile(DATA, None, sandbox=True)
    app = App(DATA, 1, profile=prof, start="hub")
    s = SquadScene(app)
    app.scene = s
    s.draw(SCREEN)
    target = prof.formation_cells()[prof.squad[0]]
    r = next(r for r, c in s.portraits if c == "necro")
    s.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=r.center, button=1))
    s.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=tile_rect(target).center))
    s.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=tile_rect(target).center, button=1))
    assert "necro" in prof.squad and prof.formation_cells()["necro"] == target
    # с поля в ростер — убрать
    s.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=tile_rect(target).center, button=1))
    s.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(600, 650), button=1))
    assert "necro" not in prof.squad
    s.draw(SCREEN)


def test_every_skill_previews():
    """Каждый навык каждого героя (и навыки путей) проигрывается в превью без ошибок и применяется."""
    from ui.skill_preview import SkillPreview
    pv = SkillPreview(DATA, pygame.Rect(588, 154, 668, 380))
    seen = 0
    for cls in DATA.classes:
        paths = [None] + [p for p, d in DATA.paths.items() if d["class"] == cls]
        done = set()
        for path in paths:
            for sid in class_skills(DATA, cls, path):
                if sid in done:
                    continue
                done.add(sid)
                pv.show(cls, path, {}, sid)
                for _ in range(150):                       # 2.5 сек при 60 кадрах — как в игре
                    pv.update(1 / 60)
                log = " ".join(t for t, _ in pv.view.log)
                assert DATA.skills[sid]["name"] in log, (cls, sid)   # навык действительно применён
                seen += 1
        pv.draw_cpu(SCREEN)
    P.reset()
    assert seen >= 60


def test_preview_runs_at_real_frame_rates():
    """При 60 и 144 кадрах в секунду навык применяется в первом же цикле (шаг боя длиннее кадра)."""
    from ui.skill_preview import CYCLE, SkillPreview
    pv = SkillPreview(DATA, pygame.Rect(588, 154, 668, 380))
    for fps in (60, 144):
        pv.show("mage", None, {}, "fireball")
        applied = []
        for _ in range(int(CYCLE * fps) - 2):
            pv.update(1 / fps)
            applied.append(pv.caster.cooldowns.get("fireball", 0) > 0 or pv.caster.ap < pv.caster.ap_max)
        assert any(applied), fps
        assert pv.c.time > CYCLE * 0.8                     # бой шёл всё время цикла
    P.reset()


def test_heroes_unlock_by_chapter(tmp_path):
    prof = Profile(DATA, str(tmp_path / "p.json"))
    assert prof.hero_available("ram") and prof.hero_available("shaman")          # глава 1 открыта сразу
    assert not prof.hero_available("binder") and "главе 9" in prof.hero_lock_reason("binder")
    prof.amber = 9999
    assert not prof.unlock_hero("binder")
    assert {h["cls"] for _, h in prof.new_heroes()} == {"ram", "shaman"}
    prof.mark_seen(["ram", "shaman"])
    assert not prof.new_heroes()
    prof._state("swamp", "normal")["done"] = True                                 # глава 2 открыта
    assert {h["cls"] for _, h in prof.new_heroes()} == {"cryo", "geomancer"}
    assert all(h["cls"] in DATA.classes and h["skill"] in DATA.skills for hs in DATA.hero_unlocks.values() for h in hs)
    assert len(DATA.hero_chapter) == len([c for c in DATA.classes if DATA.classes[c].get("unlock", 0)])


def test_view_only_hero_cannot_be_changed():
    from game.meta_scenes import HeroesScene
    prof = Profile(DATA, None)
    app = App(DATA, 1, profile=prof, start="hub")
    s = HeroesScene(app, "binder", "skills")
    assert s.view_only and "binder" in s.roster()
    sid = DATA.classes["binder"]["skills"][0]
    s.act(("branch", sid, "A", 1))
    assert prof.heroes["binder"]["branches"] == {} and s.pv == (sid, "A", 1) and s.toast
    for _ in range(40):
        s.update(1 / 60)
    s.draw(SCREEN)
    P.reset()


def test_heroes_layout_reflows_on_wide():
    from game.meta_scenes import HeroesScene
    prof = Profile(DATA, None, sandbox=True)
    app = App(DATA, 1, profile=prof, start="hub")
    T.SCREEN_W, T.SCREEN_H = 1911, 800
    s = HeroesScene(app, "warrior", "overview")
    assert not getattr(s, "stage", False)
    surf = pygame.Surface((1911, 800))
    s.draw(surf)
    assert s.left_rect == pygame.Rect(24, 154, 652, 552)
    assert s.right_rect.right == 1887

    tab = next(r for r, a, _ in s.hits if a == ("window", "skills"))
    s.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=tab.center, button=1))
    s.update(1 / 60)
    s.draw(surf)
    assert s.window == "skills"
    assert s.preview_rect == pygame.Rect(822, 154, 1065, 380)
    assert s.info_rect.right == 1887

    show = next(r for r, a, _ in s.hits if a and a[0] == "show")
    sid = next(a[1] for _, a, _ in s.hits if a and a[0] == "show")
    s.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=show.center, button=1))
    assert s.pv and s.pv[0] == sid

    T.SCREEN_W = 1280
    s.relayout()
    assert s.left_rect == pygame.Rect(24, 154, 548, 552)
    assert s.preview_rect == pygame.Rect(588, 154, 668, 380)


def test_big_board_battle_and_formation_scaling():
    from sim.combat import Combat
    i = next(i for i, e in enumerate(DATA.encounters) if len(e["map"][0]) == 14)
    c = Combat(DATA, i, player_positions=[[0, 0], [2, 5], [1, 2], [0, 4]])
    hs = c.heroes()
    assert c.grid.w == 14 and c.grid.h == 8
    assert hs[0].cell == (0, 0) and hs[1].cell == (2, 7)              # ряды 0..5 растянуты на 0..7
    P.set_board(14, 8)
    a = P.project(0, 7.99)[0]
    b = P.project(14, 7.99)[0]
    assert b - a <= P.MAX_NEAR_W + 1 and P.scale_at(4) < 1.0      # влезает, фигурки мельче
    P.reset()
