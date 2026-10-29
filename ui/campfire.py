"""Живой фон меню и лагеря: ночная поляна, костёр на частицах (пламя-флипбук, искры, дым, светлячки),
динамический свет огня и герои вокруг. Рисуется так же, как бой: земля, юниты, эффекты (OpenGL) или всё на CPU.
"""
import math
import random

import pygame

from ui import theme as T
from ui.props import load_props
from ui.sprites import SpriteBank
from ui.vfx import Light, VfxWorld, resolve_color
from ui.vfx_textures import make_textures

FIREFLIES = {"shape": "glow", "count": 1, "spawn": 260, "speed": [5, 20], "life": [3.0, 5.0], "size": [7, 3],
             "colors": [[220, 255, 150], [140, 220, 90]], "alpha": [0.9, 0], "fadein": 0.3, "hdr": 1.8,
             "drag": 0.2}
CAMP_SMOKE = {"shape": "fb_smoke", "blend": "alpha", "count": 1, "spawn": 10, "speed": [20, 40], "angle": -95,
              "spread": 20, "gravity": -10, "life": [2.0, 3.0], "size": [40, 160],
              "colors": [[70, 66, 72], [40, 38, 44]], "alpha": [0.35, 0.35], "rot": [0, 360], "spin": [5, 20]}


class Campfire:
    def __init__(self, data, fire=(640, 600), horizon=380):
        self.data = data
        self.fire = fire
        self.horizon = horizon
        self.props = load_props()
        self.vfx = VfxWorld(props={n: i for i, n in enumerate(self.props)})
        self.vfx.presets = dict(self.vfx.presets, fireflies=FIREFLIES, camp_smoke=CAMP_SMOKE)
        self.sprites = SpriteBank()
        self.clock = 0.0
        self.acc = {}
        self._bg = None
        self._cpu_tex = None
        self._cpu_cache = {}
        self.heroes = []                # [(id класса, цвет)] — сидят у костра
        self.rng = random.Random(4)
        self.burst = 0.0

    def set_heroes(self, classes):
        self.heroes = [(c, tuple(self.data.classes[c]["color"])) for c in classes]

    def _rate(self, key, per_sec, dt):
        a = self.acc.get(key, 0.0) + per_sec * dt
        n = int(a)
        self.acc[key] = a - n
        return n

    def poke(self):
        """Всплеск огня (нажали кнопку): сноп искр и вспышка."""
        x, y = self.fire
        self.vfx.emit("embers_bounce", x, y - 30, count=24)
        self.vfx.emit("fire_core", x, y - 30, scale=0.6)
        self.burst = 0.5

    def update(self, dt):
        self.clock += dt
        V = self.vfx
        x, y = self.fire
        for _ in range(self._rate("flame", 16, dt)):
            V.emit("flame_fb", x + self.rng.uniform(-18, 18), y - 30, scale=1.5)
        for _ in range(self._rate("ember", 7, dt)):
            V.emit("heat_embers", x, y - 30, scale=1.2)
        for _ in range(self._rate("smoke", 1.5, dt)):
            V.emit("camp_smoke", x, y - 90)
        for _ in range(self._rate("fly", 1.2, dt)):
            V.emit("fireflies", x + self.rng.uniform(-500, 500), self.horizon + self.rng.uniform(20, 300))
        self.burst = max(0.0, self.burst - dt)
        V.update(dt)
        V.real_update(dt)
        k = 1.3 + 0.25 * math.sin(self.clock * 11) * math.sin(self.clock * 4.3) + self.burst
        V.frame_lights = [Light((x, y - 20), resolve_color((255, 150, 60), None), 430, k, fadein=0),
                          Light((x, y - 60), resolve_color((255, 200, 120), None), 160, 0.8, fadein=0)]

    # ---------- рисование ----------

    def _background(self):
        if self._bg:
            return self._bg
        s = pygame.Surface((T.SCREEN_W, T.SCREEN_H))
        hz = self.horizon
        for yy in range(hz):                                  # небо: ночной градиент
            k = yy / hz
            s.fill(T.mix((10, 12, 26), (34, 30, 52), k), (0, yy, T.SCREEN_W, 1))
        rng = random.Random(9)
        for _ in range(140):                                  # звёзды
            sx, sy = rng.randrange(T.SCREEN_W), rng.randrange(int(hz * 0.85))
            c = rng.randint(120, 230)
            s.set_at((sx, sy), (c, c, min(255, c + 20)))
        pygame.draw.circle(s, (230, 230, 210), (760, 70), 26)   # луна
        pygame.draw.circle(s, T.mix((10, 12, 26), (34, 30, 52), 0.2), (772, 62), 24)
        for layer, (col, base, amp) in enumerate((((22, 30, 34), hz - 70, 60), ((16, 22, 24), hz - 30, 40))):
            pts = [(0, hz + 10)]                              # лес: два ряда силуэтов елей
            x = 0
            while x <= T.SCREEN_W + 40:
                h = amp * (0.6 + 0.4 * rng.random())
                pts += [(x, base), (x + 18, base - h), (x + 36, base)]
                x += 36
            pts += [(T.SCREEN_W, hz + 10)]
            pygame.draw.polygon(s, col, pts)
        for yy in range(hz, T.SCREEN_H):                      # поляна
            k = (yy - hz) / (T.SCREEN_H - hz)
            s.fill(T.mix((26, 34, 26), (40, 52, 36), k), (0, yy, T.SCREEN_W, 1))
        for _ in range(500):
            gx, gy = rng.randrange(T.SCREEN_W), rng.randrange(hz + 5, T.SCREEN_H)
            s.fill(T.mix((40, 56, 38), (70, 90, 60), rng.random()), (gx, gy, 2, 3))
        fx, fy = self.fire
        pygame.draw.ellipse(s, (30, 28, 24), (fx - 90, fy - 22, 180, 44))   # кострище
        for i in range(10):                                    # камни кругом
            a = i * math.tau / 10
            cx, cy = fx + math.cos(a) * 74, fy + math.sin(a) * 18
            pygame.draw.ellipse(s, (96, 94, 98), (cx - 12, cy - 7, 24, 14))
            pygame.draw.ellipse(s, (62, 60, 66), (cx - 12, cy - 7, 24, 14), 2)
        for dx, ang in ((-30, 0.35), (30, -0.35), (0, 0)):     # поленья
            log = pygame.Surface((90, 16), pygame.SRCALPHA)
            pygame.draw.rect(log, (110, 74, 44), (0, 2, 90, 12), border_radius=6)
            pygame.draw.rect(log, (70, 44, 26), (0, 2, 90, 12), 2, border_radius=6)
            pygame.draw.circle(log, (170, 120, 70), (84, 8), 5)
            log = pygame.transform.rotate(log, math.degrees(ang))
            s.blit(log, log.get_rect(center=(fx + dx, fy - 4)))
        self._bg = s
        return s

    def draw_ground(self, surf):
        surf.blit(self._background(), (0, 0))

    def hero_spots(self):
        """Места у костра: дуга за огнём и по бокам (огонь остаётся перед зрителем)."""
        fx, fy = self.fire
        n = len(self.heroes)
        out = []
        for i in range(n):
            a = math.radians(195 + 150 * (i + 0.5) / max(1, n))
            out.append((fx + math.cos(a) * 240, fy + 10 + math.sin(a) * 80))
        return out

    def draw_units(self, surf):
        fx, fy = self.fire
        spots = self.hero_spots()
        order = sorted(range(len(self.heroes)), key=lambda i: spots[i][1])
        for i in order:
            cls, col = self.heroes[i]
            x, y = spots[i]
            img = self.sprites.get([cls], cls, col)
            if x > fx:
                img = pygame.transform.flip(img, True, False)   # смотрят на огонь
            img = pygame.transform.scale(img, (img.get_width() * 3 // 2, img.get_height() * 3 // 2))
            breathe = math.sin(self.clock * 2 + i) * 1.5
            shadow = pygame.Rect(0, 0, 70, 18)
            shadow.center = (x, y)
            pygame.draw.ellipse(surf, (12, 14, 12), shadow)
            surf.blit(img, (x - img.get_width() / 2, y - img.get_height() + 6 + breathe))

    def draw_cpu(self, surf):
        self.draw_ground(surf)
        self.draw_units(surf)
        if self._cpu_tex is None:
            self._cpu_tex = make_textures()
        self.vfx.draw_cpu(surf, self._cpu_tex, self._cpu_cache, props=self.props)
