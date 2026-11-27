"""Боевые спрайты фей вокруг эльфа."""

import math

import pygame

from . import skin as SK
from .elf_ui import FAE_THRESHOLD, GREATER_THRESHOLD


class FaeFlight:
    MOTION = .52
    DISSOLVE = .09
    WAVE = .46
    SLOTS = ((10, -17), (26, -9), (10, 0), (26, 9), (10, 17))

    def __init__(self, count):
        self.t = 0.0
        self.arrivals = [-self.MOTION] * count
        self.departures = []
        self.waves = []
        self.feet = None
        self.trail = pygame.Vector2()

    def set_count(self, count):
        before = len(self.arrivals)
        if count < before:
            self.departures.extend((slot, self.t, self.arrivals[slot]) for slot in range(count, before))
            del self.arrivals[count:]
        elif count > before:
            self.arrivals.extend([self.t] * (count - before))
            for threshold in (FAE_THRESHOLD, GREATER_THRESHOLD):
                if before < threshold <= count:
                    start = max(self.t, self.waves[-1][0] + self.WAVE if self.waves else self.t)
                    self.waves.append((start, threshold))

    def update(self, dt, feet):
        self.t += dt
        feet = pygame.Vector2(feet)
        if self.feet is not None:
            self.trail += self.feet - feet
            if self.trail.length_squared() > 13 ** 2:
                self.trail.scale_to_length(13)
            self.trail *= math.exp(-11 * dt)
        self.feet = feet
        self.departures = [(i, when, born) for i, when, born in self.departures if self.t - when < self.DISSOLVE]
        self.waves = [(start, threshold) for start, threshold in self.waves if self.t - start < self.WAVE]

    def _position(self, slot, rect, age):
        side = -1 if slot % 2 == 0 else 1
        gap, lift = self.SLOTS[slot // 2]
        scale = max(.88, min(1.35, rect.h / 60))
        phase = self.t * (3.4 + .13 * slot) + slot * 1.8
        drift = max(0.0, 1 - age / self.MOTION) ** 2
        x = rect.centerx + side * (rect.w / 2 + (gap + 24 * drift + 2 * math.sin(phase)) * scale)
        bob = 1.8 * math.sin(self.t * 3.2 + side) + .8 * math.cos(phase)
        y = rect.top + .63 * rect.h + (lift + 14 * drift + bob) * scale
        return x + self.trail.x * .55, y + self.trail.y * .75

    @staticmethod
    def _frame(sk, index, height, facing, flash):
        def make():
            art = sk.art(f"fae_flight_{index}")
            if art is None:
                return None
            width = max(1, round(art.get_width() * height / art.get_height()))
            img = pygame.transform.scale(art, (width, height))
            if facing < 0:
                img = pygame.transform.flip(img, True, False)
            if flash:
                img.fill((245, 250, 223), special_flags=pygame.BLEND_RGB_MAX)
            return img

        return SK._remember(("fae-flight", sk.id, index, height, facing, flash), make)

    def draw(self, surf, sk, rect, facing):
        native, scale, point = SK.ctx(surf)
        height = max(1, round(max(12, min(18, .23 * rect.h)) * scale))
        for slot, born in enumerate(self.arrivals):
            flash = self.t - born < .20 or any(0 <= self.t - start - slot * .032 < .13 and slot < threshold
                                               for start, threshold in self.waves)
            self._draw_one(native, point, sk, slot, rect, born, height, facing, flash)
        for slot, when, born in self.departures:
            progress = (self.t - when) / self.DISSOLVE
            self._draw_one(native, point, sk, slot, rect, born, height, facing, True, progress)

    @staticmethod
    def _halo(sk, size, flash):
        def make():
            halo = pygame.Surface((size, size), pygame.SRCALPHA)
            color = SK.lighter(sk.p["accent"], .44)
            radius = size / 2
            for yy in range(size):
                for xx in range(size):
                    distance = math.hypot(xx + .5 - radius, yy + .5 - radius) / radius
                    if distance < 1:
                        falloff = (1 - distance) ** 1.5
                        ring = math.exp(-((distance - .74) / .12) ** 2)
                        alpha = round((125 if flash else 92) * falloff + (52 if flash else 30) * ring)
                        halo.set_at((xx, yy), (*color, alpha))
            return halo

        return SK._remember(("fae-halo", sk.id, size, flash), make)

    def _draw_one(self, native, point, sk, slot, rect, born, height, facing, flash, fade=0.0):
        index = int(self.t * 13 + slot * 1.7) % 4
        art = self._frame(sk, index, height, facing, flash)
        if art is None:
            return
        age = self.t - born
        x, y = self._position(slot, rect, age)
        opacity = (1 - fade) * min(1.0, .75 + age / self.MOTION)
        halo = self._halo(sk, round(height * (2.0 if flash else 1.8)), flash)
        halo.set_alpha(round(255 * opacity * (.86 + .14 * math.sin(self.t * 4 + slot))))
        px, py = point((x, y - fade * 8))
        native.blit(halo, halo.get_rect(center=(px + facing * height * .12, py)))
        if age < self.MOTION or fade:
            art = art.copy()
            art.set_alpha(round(255 * opacity))
        native.blit(art, art.get_rect(center=(px, py)))
