"""Independent art planes for the camp and shop."""

import math
from functools import lru_cache
from pathlib import Path

import pygame

from ui import illustrations as IL

ART = Path(IL.DIR) / "parallax"

# Each tuple gives the sprite's horizontal offset, ground line and maximum size at 800px tall.
CAMP = (("tent", -72, 523, 560, 390),
        ("supplies", -341, 590, 250, 170),
        ("tripod", 296, 621, 260, 273),
        ("fire", 4, 632, 274, 218))
SHOP = (("merchant_full", 0, 725, 435, 653),
        ("bottles", -160, 653, 243, 178),
        ("barrel", 325, 614, 238, 197),
        ("chest", 94, 690, 408, 288))
GROUND_DEPTH = 21


@lru_cache(maxsize=30)
def _art(chapter, name):
    return pygame.image.load(str(ART / chapter / f"{name}.png"))


@lru_cache(maxsize=8)
def has_layers(chapter):
    return (ART / chapter / "base.png").is_file()


@lru_cache(maxsize=40)
def _fitted(chapter, name, bounds, cover=False):
    art = _art(chapter, name)
    fit = max if cover else min
    k = fit(bounds[0] / art.get_width(), bounds[1] / art.get_height())
    return pygame.transform.smoothscale(art, (round(art.get_width() * k), round(art.get_height() * k)))


@lru_cache(maxsize=16)
def _terrain(biome, name, size):
    return pygame.transform.smoothscale(_art("common", f"{biome}_{name}"), size)


def chest_image(variant, state, width):
    return _fitted("chests", f"{variant}_{state}", (width, 500))


def shop_offers_left(width):
    return max(342, round(width * .29))


@lru_cache(maxsize=16)
def _pool(size, color):
    glow = pygame.Surface((96, 48), pygame.SRCALPHA)
    for i in range(24, 0, -1):
        rect = pygame.Rect(0, 0, i * 4, i * 2)
        rect.center = (48, 24)
        pygame.draw.ellipse(glow, (*color[:3], round(color[3] * (1 - i / 24) ** 1.7)), rect)
    return pygame.transform.smoothscale(glow, size)


class Scenery:
    def __init__(self):
        self.t = 0.0
        self.motion = pygame.Vector2()
        self.goal = pygame.Vector2()
        self.angle = 0.0
        self.velocity = 0.0
        self.hot = False
        self.prop_rect = None
        self.fire_rect = None
        self.fire_hot = False
        self.fire_impulse = 0.0
        self.ground_offset = pygame.Vector2()

    def update(self, dt):
        dt = min(dt, .05)
        self.t += dt
        self.motion += (self.goal - self.motion) * (1 - math.exp(-7 * dt))
        aim = math.sin(self.t * 2.4) * (2.5 if self.hot else .7) + self.motion.x
        self.velocity += ((aim - self.angle) * 39 - self.velocity * 5) * dt
        self.angle = max(-9, min(9, self.angle + self.velocity * dt))
        self.fire_impulse = max(0, self.fire_impulse - dt)

    def touch(self, pos):
        if self.prop_rect and self.prop_rect.collidepoint(pos):
            self.velocity += 28 if self.angle <= 0 else -28
            return True
        if self.fire_rect and self.fire_rect.collidepoint(pos):
            self.fire_impulse = .85
            return True
        return False

    def shift(self, depth):
        return self.motion.elementwise() * (-depth, -depth * .65)

    def draw(self, surf, iid, mouse, *, bare=False):
        native = getattr(surf, "native", surf)
        view = surf.get_rect()
        size = native.get_size()
        sx = getattr(surf, "S", 1)
        ox, oy = getattr(surf, "ox", 0), getattr(surf, "oy", 0)
        pointer = pygame.Vector2(mouse if mouse != (0, 0) else view.center)
        self.goal.update(max(-1, min(1, (pointer.x - view.centerx) * 2 / view.w)),
                         max(-1, min(1, (pointer.y - view.centery) * 2 / view.h)))
        self.prop_rect = self.fire_rect = None
        k = size[1] / 800
        center_x = size[0] / 2
        base = _fitted(iid, "base", (size[0] + round(24*k), size[1] + round(24*k)), cover=True)
        native.blit(base, base.get_rect(center=pygame.Vector2(native.get_rect().center) + self.shift(8)*k))
        biome = iid.split("_", 1)[1]
        span = max(size[0] + round(72*k), round(1950*k))
        bank = _terrain(biome, "bank", (span, round(178*k)))
        bank_origin = pygame.Vector2(center_x, 304*k) + self.shift(14)*k
        native.blit(bank, bank.get_rect(midtop=bank_origin))
        ground = _terrain(biome, "ground", (span, round(475*k)))
        # Use the same integer translation for the ground, props, lights and hit areas.
        translation = self.shift(GROUND_DEPTH)*k
        translation.update(round(translation.x), round(translation.y))
        self.ground_offset = translation / sx
        native.blit(ground, ground.get_rect(midtop=pygame.Vector2(center_x, 363*k) + translation))
        if not bare:
            self.draw_props(native, iid, mouse, center_x, k, translation, sx, ox, oy)

        slide = self.shift(33)*k
        bounds = (round(420*k), round(230*k))
        left = _fitted("common", f"{biome}_left", bounds)
        right = _fitted("common", f"{biome}_right", bounds)
        y = size[1] + 61*k + slide.y
        native.blit(left, left.get_rect(bottomleft=(-49*k + slide.x, y)))
        native.blit(right, right.get_rect(bottomright=(size[0] + 49*k + slide.x, y)))

    def draw_props(self, native, iid, mouse, center_x, k, translation, sx, ox, oy):
        camp = iid.startswith("camp_")
        locations = {}
        for name, dx, baseline, width, height in CAMP if camp else SHOP:
            sprite = _fitted("common" if name == "tripod" else iid, name, (round(width*k), round(height*k)))
            x = center_x * .40 if name == "merchant_full" else center_x + dx*k
            foot = pygame.Vector2(x, baseline*k) + translation
            rect = sprite.get_rect(midbottom=foot)
            locations[name] = rect
            shadow = _pool((max(1, round(rect.w * .94)), round(44*k)), (5, 7, 10, 146))
            native.blit(shadow, shadow.get_rect(center=(rect.centerx, rect.bottom - 12*k)))
            if name == "fire":
                glow = _pool((round(380*k), round(124*k)), (203, 91, 21, 94))
                native.blit(glow, glow.get_rect(center=(rect.centerx, rect.bottom - 40*k)))
            native.blit(sprite, rect)

        def logical(rect):
            return pygame.Rect((rect.x - ox) / sx, (rect.y - oy) / sx, rect.w / sx, rect.h / sx)

        if camp:
            tripod = locations["tripod"]
            pivot = pygame.Vector2(tripod.x + tripod.w * .55, tripod.y + tripod.h * .53)
            pot = _fitted("common", "pot", (round(102*k), round(116*k)))
            self.prop_rect = logical(self.swing(native, pot, pivot))
            fire = locations["fire"]
            origin = (fire.centerx, fire.bottom - fire.h * .34)
            self.fire_rect = logical(pygame.Rect(origin[0] - fire.w * .42, origin[1] - 34*k, fire.w * .84, 93*k))
            self.fire_hot = self.fire_rect.collidepoint(mouse)
            self.embers(native, origin, k)
        else:
            merchant = locations["merchant_full"]
            fx, fy = (.955, .106) if iid == "shop_swamp" else (.121, .146)
            lamp = _fitted(iid, "lantern", (round(67*k), round(119*k)))
            pivot = pygame.Vector2(merchant.x + fx*merchant.w, merchant.y + fy*merchant.h)
            self.prop_rect = logical(self.swing(native, lamp, pivot))
        self.hot = self.prop_rect.collidepoint(mouse)


    def swing(self, surf, sprite, pivot):
        rotated = pygame.transform.rotozoom(sprite, self.angle, 1)
        offset = pygame.Vector2(0, sprite.get_height() / 2).rotate(-self.angle)
        box = rotated.get_rect(center=pivot + offset)
        surf.blit(rotated, box)
        return box

    def embers(self, surf, center, k):
        lift = max(.25 if self.fire_hot else 0, self.fire_impulse)
        for i in range(17 + round(24 * lift)):
            t = (self.t * (.58 + i % 5 * .085) + i * .618) % 1
            x = center[0] + (math.sin(i * 2.39) * 25 + t * (math.sin(i) * 40 + self.motion.x * 9)) * k
            y = center[1] - (15 + t * (36 + i % 4 * 15 + 43 * lift)) * k
            color = (255, 202, 100) if t < .25 else (222, 103, 46) if t < .69 else (101, 54, 39)
            side = max(1, round(k * (2.5 - t * 1.5)))
            pygame.draw.rect(surf, color, (round(x), round(y), side, side))
