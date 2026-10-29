"""Графика: спрайты (PNG и заглушки), эффекты (частицы, модельки, ленты, шейдерные эффекты, свет, следы),
камера, выбор юнита кликом по спрайту."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from game.battle_scene import BattleScene  # noqa: E402
from sim.build import skill_in_branch  # noqa: E402
from sim.data import GameData  # noqa: E402
from ui import projection as P  # noqa: E402
from ui import theme as T  # noqa: E402
from ui.marks import MarkLayer  # noqa: E402
from ui.props import build_prop_atlas, load_props  # noqa: E402
from ui.sprites import SpriteBank  # noqa: E402
from ui.vfx import VfxWorld  # noqa: E402
from ui.vfx_textures import TOTAL, make_textures  # noqa: E402

pygame.init()
SCREEN = pygame.display.set_mode((T.SCREEN_W, T.SCREEN_H))
DATA = GameData()
PROPS = load_props()
PROP_INDEX = {n: i for i, n in enumerate(PROPS)}


def test_sprite_png_overrides_placeholder_and_scales(tmp_path):
    img = pygame.Surface((32, 32), pygame.SRCALPHA)
    img.fill((200, 10, 10, 255), (12, 4, 8, 28))
    pygame.image.save(img, str(tmp_path / "warrior.png"))
    bank = SpriteBank(str(tmp_path))
    war = bank.get(["berserker", "warrior"], "warrior", (1, 2, 3))
    assert war.get_size() == (64, 64) and war.get_at((32, 40))[:3] == (200, 10, 10)
    boss = bank.get(["warrior"], "warrior", (1, 2, 3), boss=True)
    assert boss.get_height() == 96
    flash = bank.get(["warrior"], "warrior", (1, 2, 3), flash=True)
    assert flash.get_at((32, 40))[:3] == (255, 255, 255) and flash.get_at((0, 0))[3] == 0
    slime = bank.get(["slime"], "slime", (90, 160, 120))           # файла нет — заглушка
    assert slime.get_height() == 64 and slime.get_bounding_rect().h > 20


def test_every_effect_plays_and_draws_on_cpu():
    v = VfxWorld(props=PROP_INDEX)
    ctx = {"caster": (200, 300), "caster_ground": (200, 330), "target": (500, 280), "target_ground": (500, 310),
           "cells": [(500, 310), (588, 310)], "color": (255, 120, 40), "dir": -5.0, "tier": 2}
    for name in v.effects:
        v.play(name, ctx)
    for _ in range(30):
        v.update(1 / 60)
    assert v.n > 300 and v.decals and v.props and v.sfx and v.ribbons and v.lights and v.marks
    import numpy as np
    groups = v.batches(np.zeros((TOTAL, 4), np.float32))
    assert all(g.shape[1] == 14 for g in groups.values()) and sum(len(g) for g in groups.values()) >= v.n
    assert len(v.sfx_rows()["distort"]) and len(v.ribbon_verts()["add"])
    assert len(v.light_rows((0, 0, 1, 1))) == len(v.lights)
    v.draw_cpu(SCREEN, make_textures(), {}, props=PROPS)
    for _ in range(400):
        v.update(1 / 60)
    assert not v.busy()
    v.update(0)                       # пауза — ничего не меняется


def test_vfx_library_references_exist():
    v = VfxWorld()
    lib = v.lib
    effects = set(v.effects)

    def check_spec(where, spec):
        for key in ("impact", "release", "line_fx"):
            assert not spec.get(key) or spec[key] in effects, (where, key)
        for key, val in spec.get("by_tag", {}).items():
            assert val in effects, (where, key)
        tr = spec.get("travel")
        if tr:
            heads = [] if not tr.get("head") else ([tr["head"]] if isinstance(tr["head"], str) else tr["head"])
            assert all(h in v.presets for h in heads) and (not tr.get("trail") or tr["trail"] in v.presets), where
            check_refs(where, tr)

    def check_refs(where, d):
        for key, pool in (("sfx", lib["sfx"]), ("ribbon", lib["ribbons"]), ("light", lib["lights"])):
            val = d.get(key)
            names = [] if not val else ([val] if isinstance(val, str) else [x for x in val if isinstance(x, str)])
            assert all(n in pool for n in names), (where, key, names)
        assert not d.get("prop") or d["prop"] in PROP_INDEX, (where, d["prop"])

    for name, layers in v.effects.items():
        for layer in layers:
            assert "fx" not in layer or layer["fx"] in v.presets, (name, layer)
            assert "line" not in layer or layer["line"] in v.presets, (name, layer)
            assert "play" not in layer or layer["play"] in effects, (name, layer)
            check_refs(name, layer)
            for key in ("projectile", "attach"):
                if key in layer:
                    check_refs(name, layer[key])
                    assert not layer[key].get("impact") or layer[key]["impact"] in effects, (name, layer)
            if "arc" in layer:
                assert layer["arc"].get("ribbon", "slash") in lib["ribbons"], name
            if "streak" in layer:
                assert layer["streak"]["ribbon"] in lib["ribbons"], name
            if "props" in layer:
                names = layer["props"]["name"]
                assert all(n in PROP_INDEX for n in ([names] if isinstance(names, str) else names)), name
            if "mark" in layer:
                m = layer["mark"] if isinstance(layer["mark"], str) else layer["mark"]["name"]
                assert m in MarkLayer((10, 10)).tex, (name, m)
    for sid, spec in lib["skills"].items():
        assert sid.startswith("_") or sid in DATA.skills, sid
        check_spec(sid, spec)
        for b, over in spec.get("branches", {}).items():
            assert b in DATA.branches[sid], (sid, b)
            check_spec(f"{sid}.{b}", dict(spec, **over))
    for key, spec in list(lib["attacks"].items()) + list(lib["defaults"].items()):
        check_spec(key, spec)
    assert all(a in lib["attacks"] for a in lib["unit_attacks"].values())
    for key, cast in lib["casts"].items():
        assert key.split(".")[0] in DATA.skills or key == "default", key
        assert not cast.get("orb") or cast["orb"] in lib["sfx"], key


def test_branch_gets_own_look_and_tier_scale():
    s = BattleScene(DATA, 0)
    base, _ = s.view.skill_spec("fireball", DATA.skills["fireball"])
    meteor, tier = s.view.skill_spec("fireball", skill_in_branch(DATA, "fireball", "A", 2))
    assert tier == 2 and meteor["impact"] == "meteor_impact" and base["impact"] == "fire_explosion"
    assert meteor["travel"]["from"] == "sky"


def test_hitstop_freezes_battle_time_in_real_time():
    s = BattleScene(DATA, 0)
    s.phase, s.paused = "battle", False
    t0 = s.combat.time
    s.view.vfx.screen_fx(hitstop=0.1)
    s.update(1 / 30)
    assert s.combat.time == t0              # стоп-кадр: бой стоит
    for _ in range(6):
        s.update(1 / 30)
    assert s.combat.time > t0               # прошло 0.1 с реального времени — бой пошёл


def test_marks_stamp_and_reset():
    s = BattleScene(DATA, 0)
    v = s.view
    v.vfx.mark("scorch", 500, 300, 80)
    v.vfx.mark("prop:arrow", 520, 300, 0, 20)
    v.update(1 / 60, 1 / 60)
    fx, fy = P.screen_to_flat(500, 300)              # след лежит на плоской карте земли
    assert v.marks.count == 2 and v.marks.surf.get_at((int(fx), int(fy)))[3] > 100
    v.reset(s.combat)
    assert v.marks.count == 0 and v.marks.surf.get_bounding_rect().w == 0


def test_prop_atlas_and_flight():
    atlas, uvs, dims, index = build_prop_atlas(PROPS)
    assert atlas.shape == (512, 512, 4) and set(index) == set(PROPS)
    assert dims[index["arrow"]][0] > dims[index["arrow"]][1]          # стрела длинная и смотрит вправо
    v = VfxWorld(props=PROP_INDEX)
    hit = []
    dur = v.projectile((100, 300), (500, 300), 1000, None, None, (255, 255, 255), arc=40, prop="arrow",
                       on_hit=lambda: hit.append(1), stick=True)
    assert abs(dur - 0.4) < 1e-6 and len(v.props) == 1
    for _ in range(30):
        v.update(1 / 60)
    assert hit == [1] and not v.props and v.marks and v.marks[0][0] == "prop:arrow"


def test_projectile_delays_damage_numbers():
    s = BattleScene(DATA, 0)
    archer, foe = s.combat.units[1], s.combat.units[4]
    view = s.view
    view.consume([{"t": "attack", "src": archer, "dst": foe, "kind": "ranged", "tag": None},
                  {"t": "damage", "unit": foe, "amount": 9, "absorbed": 0, "kind": "ranged", "tag": None,
                   "cover": False, "blocked": None}])
    assert not [f for f in view.fx if f.kind == "text"]           # снаряд ещё летит
    for _ in range(40):
        view.update(1 / 60, 1 / 60)
    assert any(f.kind == "text" and f.s == "-9" for f in view.fx)


def test_gl_full_frame_with_all_layers():
    try:
        from ui.gl_renderer import GLRenderer
        gl = GLRenderer((T.SCREEN_W, T.SCREEN_H), window=False)
    except Exception:
        import pytest
        pytest.skip("нет OpenGL")
    s = BattleScene(DATA, 0)
    v = s.view
    tgt = s.combat.units[4]
    for name in ("meteor_impact", "judgment_beam", "volley_rain", "crush", "net_wrap"):
        v.vfx.play(name, v._ctx(s.combat.units[2], tgt, cells=v._cells_around(tgt.cell, 1), color=(255, 160, 80)))
    for _ in range(12):
        v.update(1 / 60, 1 / 60)
    world, ui = pygame.Surface((T.SCREEN_W, T.SCREEN_H)), pygame.Surface((T.SCREEN_W, T.SCREEN_H), pygame.SRCALPHA)
    units = pygame.Surface((T.SCREEN_W, T.SCREEN_H), pygame.SRCALPHA)
    s.draw_layers(world, ui, units)
    gl.render(world, v.vfx, ui, units)
    img = gl.read()
    assert img.get_size() == (T.SCREEN_W, T.SCREEN_H)


def test_gl_frames_do_not_stick():
    """Регрессия: вспышка первого кадра не должна оставаться в bloom следующих кадров."""
    try:
        from ui.gl_renderer import GLRenderer
        gl = GLRenderer((T.SCREEN_W, T.SCREEN_H), window=False)
    except Exception:
        import pytest
        pytest.skip("нет OpenGL")
    world = pygame.Surface((T.SCREEN_W, T.SCREEN_H))
    world.fill((40, 60, 40))
    v = VfxWorld()
    v.emit("flare", 300, 300)
    v.update(1 / 60)
    gl.render(world, v, None)
    assert gl.read().get_at((300, 300))[:3] == (255, 255, 255)
    gl.render(world, VfxWorld(), None)
    assert gl.read().get_at((300, 300))[:3] == (40, 60, 40)


def test_battle_draws_and_clicks_sprite():
    s = BattleScene(DATA, 0)
    s.update(1 / 60)
    s.draw(SCREEN)
    archer = s.combat.alive()[1]
    rect = next(r for r, u in s.view.sprite_rects if u is archer)
    head = (rect.centerx, rect.y + 6)                 # голова может заходить на клетку выше
    assert s.cell_at(*head) == archer.cell
    s.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))   # в бой
    s.paused = False
    for _ in range(240):
        s.update(1 / 30)
    s.draw(SCREEN)
    assert s.view.vfx.n or s.combat.time > 5
