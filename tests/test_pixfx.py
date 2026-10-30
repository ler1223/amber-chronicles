"""Пилот пиксельного стиля (art_style.md): огонь и лёд — запекание, стихия навыка, навыки в превью, бой, F9."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pygame  # noqa: E402

from game.battle_scene import BattleScene  # noqa: E402
from sim.build import build_proto  # noqa: E402
from sim.data import GameData  # noqa: E402
from ui import theme as T  # noqa: E402
from ui.pixfx import RECIPES, VARIANTS, Lib, family  # noqa: E402
from ui.settings import SETTINGS  # noqa: E402
from ui.skill_preview import SkillPreview  # noqa: E402

pygame.init()
SCREEN = pygame.display.set_mode((T.SCREEN_W, T.SCREEN_H))
DATA = GameData()
CASES = [("mage", None, "fireball", None), ("mage", None, "fireball", ("A", 2)), ("mage", None, "fireball", ("B", 2)),
         ("mage", None, "flashpoint", None), ("mage", None, "fan_flames", None),
         ("mage", "igniter", "cinder_field", None), ("cryo", None, "ice_wall", None), ("cryo", None, "rink", None),
         ("cryo", "stormfrost", "blizzard", None), ("cryo", "stormfrost", "blizzard", ("B", 2)),
         ("cryo", None, "shatter", None), ("geomancer", "lavalord", "lava_vent", None)]


def test_every_recipe_bakes_pixel_frames_with_glow():
    lib = Lib()
    for name in RECIPES:
        for v in range(VARIANTS):
            frames = lib.get(name, v)
            assert frames, name
            img, _ = frames[0]
            assert img.get_bitsize() == 32
        big = lib.img(name, 0, 0, 2.6)
        w, h = lib.get(name)[0][0].get_size()
        assert big.get_size() == (round(w * 2.5), round(h * 2.5))     # ступени 0.25 — пиксель остаётся квадратным
    assert any(g is not None for _, g in lib.get("blast_m"))           # белое ядро взрыва светится


def test_family_reads_effects_not_names():
    sk = DATA.skills
    assert family(sk["fireball"]) == "fire" and family(sk["flashpoint"]) == "fire"
    assert family(sk["ice_wall"]) == "ice" and family(sk["blizzard"]) == "ice" and family(sk["rink"]) == "ice"
    assert family(sk["holy_water"]) is None and family(sk["coat"]) is None and family(sk["purify"]) is None


def _play(case, pixel):
    SETTINGS["fx_style"] = "pixel" if pixel else "old"
    cls, path, sid, br = case
    pv = SkillPreview(DATA, pygame.Rect(300, 160, 680, 420))
    pv.show(cls, path, {sid: br} if br else {}, sid)
    seen = 0
    for i in range(80):
        pv.update(1 / 30)
        seen = max(seen, len(pv.view.pix.fx.items) + pv.view.pix.spells.ps.n)   # запечённые + живые частицы
        if i % 10 == 0:
            pv.draw_cpu(SCREEN)
            units = pygame.Surface(SCREEN.get_size(), pygame.SRCALPHA)
            pv.draw_layers(SCREEN, units, SCREEN)
    return seen


def test_fire_and_ice_skills_play_pixel_effects_and_switch_off():
    try:
        for case in CASES:
            assert _play(case, True) > 0, case
        assert _play(CASES[0], False) == 0
    finally:
        SETTINGS["fx_style"] = "pixel"


def test_battle_with_fire_and_ice_draws_and_f9_toggles():
    SETTINGS["fx_style"] = "pixel"
    i = next(i for i, e in enumerate(DATA.encounters) if e["id"] == "forge_2")
    squad = [{"cls": c, "proto": build_proto(DATA, c)} for c in ("mage", "cryo", "alchemist", "warrior")]
    s = BattleScene(DATA, i, autoplay=True, squad=squad)
    s.paused = False
    units = pygame.Surface(SCREEN.get_size(), pygame.SRCALPHA)
    ui = pygame.Surface(SCREEN.get_size(), pygame.SRCALPHA)
    drew = False
    for n in range(360):
        s.update(1 / 30)
        if n % 15 == 0:
            s.draw(SCREEN)
            s.draw_layers(SCREEN, ui, units)
            drew = drew or s.glow_layer() is not None
    assert drew                                     # горящие клетки и взрывы дали свечение
    try:
        s.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F9, mod=0, unicode=""))
        assert SETTINGS["fx_style"] == "flipbook" and not s.view.pix.pixel.fx.items
        for _ in range(30):
            s.update(1 / 30)
        s.draw_layers(SCREEN, ui, units)
        assert s.glow_layer() is None
    finally:
        SETTINGS["fx_style"] = "pixel"


def test_particles_fall_land_and_report_tag():
    from ui.pixsim import BOUNCE, STICK, Particles
    ps = Particles()
    ps.spawn(1, (3.0, 2.0, 1.0), (1.0, 0.0, 0.0), life=5, grav=9.0, land=STICK, tag=7, life_var=0)
    ps.spawn(1, (3.0, 2.0, 1.0), life=5, grav=9.0, land=BOUNCE, bounce=0.5, life_var=0)
    ps.spawn(1, (3.0, 2.0, 0.1), life=5, buoy=2.0, life_var=0)        # тёплое всплывает
    landed = []
    for _ in range(60):
        landed += ps.update(1 / 30)
    assert landed and landed[0][0] == 7 and 3.3 < landed[0][1] < 3.6    # упала с разлётом по x, метка — один раз
    assert len(landed) == 1
    assert ps.z[0] == 0 and ps.vx[0] == 0                            # прилипла к земле
    assert ps.z[2] > 1.0
    assert ps.prepare() > 0 and ps.buckets()


def test_fireball_hits_target_then_droplets_ignite_neighbours():
    SETTINGS["fx_style"] = "pixel"
    pv = SkillPreview(DATA, pygame.Rect(300, 160, 680, 420))
    pv.show("mage", None, {}, "fireball")
    pv.caster.attack_timer = pv.caster.atk_cd = 999.0
    S = pv.view.pix.spells
    surf = pygame.Surface(SCREEN.get_size(), pygame.SRCALPHA)
    held_before_hit = False
    for i in range(235):                               # до перезапуска превью (4.2 сек)
        pv.update(1 / 60)
        pv.draw_layers(SCREEN, surf, SCREEN)
        main = pv.foes[0]
        if "fire" in main.statuses and S.unit_held(main):
            held_before_hit = True                     # статус уже есть, но пламя ждёт снаряд
    assert held_before_hit
    assert not S.hold and not S.unit_hold              # всё долетело: клетки и цели отпущены
    assert pv.view.marks.count > 0                     # подпалины там, где упали капли


def test_burning_cells_merge_into_one_surface():
    from ui.pixfire import RES, FireField
    ff = FireField()
    ff.update(1.0, [(2, 2), (3, 2)], 10, 6)
    x0, y0 = ff.box[0], ff.box[1]
    row = ff.cover[(2 - y0) * RES + RES // 2]
    seam = (3 - x0) * RES                              # граница между двумя горящими клетками
    centre = row[seam - RES // 2]
    assert row[seam - 2:seam + 2].min() >= centre * 0.97 and centre > 0.5   # шва нет: одна горящая плоскость
    assert ff.cover[0, 0] < 0.05                       # вокруг не горит
    xs, ys = ff.sample(200, np.random.default_rng(1))
    assert ((xs >= 1.6) & (xs <= 4.4) & (ys >= 1.6) & (ys <= 3.4)).all()     # край рваный, но у клеток


def test_one_scar_per_impact_and_none_on_water():
    from ui.pixmarks import scar

    def land(kind):
        return lambda xs, ys: np.where(xs < 3.0, kind, "grass").astype("U10")
    m = scar(3.5, 2.5, 1.5, land("grass"), (1.0, 0.0), [(4.5, 2.5), (2.5, 3.5)], seed=1)
    assert m is not None                                # один кусок на весь удар
    assert scar(3.5, 2.5, 1.0, lambda xs, ys: np.full(len(xs), "water", "U10")) is None
    half = scar(3.0, 2.5, 1.5, land("water"), seed=2)[0]
    a = pygame.surfarray.array_alpha(half)
    w = a.shape[0]
    assert a[: w // 2 - 4].max() == 0 and a[w // 2 + 4:].max() > 0    # на воде (слева) следа нет


def test_surface_field_never_spills_outside_cells():
    from ui.pixfire import IceField
    for seed in range(6):
        f = IceField(seed=seed)
        f.update(1.0, [(5, 2), (6, 2), (5, 3), (6, 3)], 10, 6)
        a = pygame.surfarray.array_alpha(f.img[0])          # [x, y] в пикселях плоской карты
        cell = a.shape[0] // (f.box[2] - f.box[0])
        assert a[:cell // 3].max() == 0 and a[-cell // 3:].max() == 0      # дальше трети клетки от края — пусто


def test_ground_surface_keeps_transparency_between_frames():
    from ui.pixfx import PixFx
    X = PixFx()
    a = np.zeros((8, 8, 4), np.uint8)
    a[0, 0] = [255, 255, 255, 255]
    img = pygame.image.frombuffer(a.tobytes(), (8, 8), "RGBA").copy()
    X.add_surface(img, (40, 40), ttl=5.0, fade=1.0)
    flat = pygame.Surface((80, 80))
    for age in (0.1, 4.5, 4.6):                          # и до, и во время таяния
        X.items[0].age = age
        X.draw_ground(flat)
    assert (pygame.surfarray.array_alpha(img) > 0).mean() < 0.05
    flat.fill((0, 0, 0))
    X.draw_ground(flat)
    assert pygame.surfarray.pixels3d(flat)[40, 40].max() == 0     # прозрачное осталось прозрачным


def test_ice_wall_cells_join_into_runs_and_render():
    from ui import pixmesh as M
    from ui import projection as P
    P.reset()
    runs = M.runs([(2, 1), (2, 2), (2, 3), (5, 4), (6, 4), (7, 4)])
    assert ("y", [(2, 1), (2, 2), (2, 3)]) in runs and ("x", [(5, 4), (6, 4), (7, 4)]) in runs
    for axis, run in runs:
        img, _ = M.wall(axis, run, 0, -1)
        a = pygame.surfarray.array_alpha(img)
        assert 0.2 < (a > 0).mean() < 0.95                    # модель из Blender нарисована, вокруг пусто
    assert M.wall("x", [(5, 4)], 0, 1, sink=10) is None        # ушла под землю — не видно
    frames, fps = M.break_frames()
    assert frames >= 20 and M.wall_break("x", (5, 4), 1, 0, frames - 1) is not None


def test_flashpoint_burns_surface_as_one_scar():
    from ui.pixmarks import area_scar
    grass = lambda xs, ys: np.full(len(xs), "grass", "U10")   # noqa: E731
    m = area_scar([(3, 2), (4, 2), (4, 3)], grass, seed=1)
    assert m is not None
    a = pygame.surfarray.array_alpha(m[0])
    assert 0.15 < (a > 0).mean() < 0.9                       # пятно по форме пожара, а не весь прямоугольник




def test_lab_styles_play_skills_and_render_on_gpu():
    """Стили лаборатории (флипбуки, шейдеры, меши, симуляция): навыки дают команды кадра, видеокарта их рисует."""
    from ui.fxlab import LOOKS
    from ui.present import Presenter
    pres = Presenter(SCREEN, True, window=False)

    class Adapter:
        def __init__(self, pv):
            self.pv = pv

        def draw_layers(self, world, ui, units):
            self.pv.draw_layers(world, units, ui)

        def plane(self):
            return self.pv.plane()

        def glow_layer(self):
            return self.pv.view.glow_layer()

        def lab_frame(self):
            return self.pv.view.lab_frame()

        @property
        def vfx(self):
            return self.pv.vfx
    try:
        for style in LOOKS:
            SETTINGS["fx_style"] = style
            for cls, path, sid, br in (("mage", None, "fireball", None), ("mage", None, "fireball", ("A", 2)),
                                       ("cryo", "stormfrost", "blizzard", None), ("cryo", None, "ice_wall", None)):
                pv = SkillPreview(DATA, pygame.Rect(300, 160, 680, 420), loop=False)
                pv.show(cls, path, {sid: br} if br else {}, sid)
                cmds = 0
                for i in range(300):                      # метеор кастуется 3 сек
                    pv.update(1 / 60 * 1.5)
                    if i % 20 == 0:
                        pres.frame(Adapter(pv))
                        fr = pv.view.lab_frame()
                        cmds = max(cmds, sum(len(v) for v in fr.layers.values()) if fr else 0)
                walls = [u for u in pv.c.units if u.obj and u.obj.get("id") == "ice_wall" and u.alive]
                assert cmds > 0 or walls, (style, sid)
    finally:
        SETTINGS["fx_style"] = "pixel"


def test_particle_cap_cuts_array_params():
    from ui.pixsim import Particles
    ps = Particles()
    ps.spawn(ps.CAP - 10, (0.0, 0.0, 0.0), life=5, life_var=0)
    n = 50
    rng = np.random.default_rng(0)
    ps.spawn(n, (rng.random(n), rng.random(n), np.zeros(n)), (rng.random(n), np.zeros(n), 0.5), life=0.6,
             temp=rng.random(n), size=2.0, life_var=0.2)              # массивы длины n, а места — на 10
    assert ps.n == ps.CAP
