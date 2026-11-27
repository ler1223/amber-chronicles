"""Three Elven wind spells, drawn on the same pixel grid as Expedition magic."""

import math
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pygame

from ui import pixfx


@lru_cache(maxsize=1)
def _gust_frames():
    atlas = Path(__file__).resolve().parents[1] / "assets/vfx/flipbooks/elf_gust"
    meta = json.loads(atlas.with_suffix(".json").read_text(encoding="utf-8"))
    sheet = pygame.image.load(atlas.with_suffix(".png"))
    w, h = meta["frame"]
    frames = [sheet.subsurface((i % meta["cols"] * w, i // meta["cols"] * h, w, h))
              for i in range(meta["frames"])]
    visible = [i for i, frame in enumerate(frames) if frame.get_bounding_rect(min_alpha=24)]
    frames = frames[visible[0]:visible[-1] + 1]
    rects = [rect for frame in frames if (rect := frame.get_bounding_rect(min_alpha=16))]
    bounds = rects[0].unionall(rects[1:]).inflate(4, 4).clip(frames[0].get_rect())
    cropped = [frame.subsurface(bounds).copy() for frame in frames]
    for frame in cropped:
        # Lift the sunlit dust above the dark grass while preserving the baked density.
        frame.fill((48, 46, 33), special_flags=pygame.BLEND_RGB_ADD)
    return cropped


@lru_cache(maxsize=768)
def _plume(index, width, height, angle):
    # Reduce the lit volume to the spell pixel grid before rotating and enlarging it.
    cloud = pygame.transform.smoothscale(_gust_frames()[index], (width, height))
    return pygame.transform.rotate(cloud, angle)


def _dust(tile, center, direction, phase, width, height):
    frames = _gust_frames()
    index = min(len(frames) - 1, int(phase * len(frames)))
    angle = round(-math.degrees(math.atan2(direction.y, direction.x)) / 10) * 10
    cloud = _plume(index, width, height, angle)
    tile.blit(cloud, cloud.get_rect(center=center))


@dataclass
class Wind:
    kind: str
    start: float
    life: float
    origin: tuple
    target: tuple
    depth: float
    cells: tuple

    def draw(self, surf, time, scale, offset):
        age = time - self.start
        if not 0 <= age < self.life:
            return
        step = pixfx.PX * self.depth
        delta = (pygame.Vector2(self.target) - self.origin) / step
        p = min(1, int(age * pixfx.FPS) / max(1, self.life * pixfx.FPS - 1))
        pad = 24
        bounds = [pygame.Vector2(), delta]
        if self.kind == "swarm":
            bounds.extend((pygame.Vector2(cell) - self.origin) / step for cell in self.cells)
        left = math.floor(min(v.x for v in bounds)) - pad
        top = math.floor(min(v.y for v in bounds)) - pad
        w = math.ceil(max(v.x for v in bounds)) + pad - left
        h = math.ceil(max(v.y for v in bounds)) + pad - top
        tile = pygame.Surface((w, h), pygame.SRCALPHA)
        origin = pygame.Vector2(-left, -top)
        if self.kind == "slipstream":
            direction = delta.normalize() if delta.length_squared() else pygame.Vector2(1, 0)
            normal = pygame.Vector2(-direction.y, direction.x)
            flight = age / self.life
            head = origin + delta * flight
            _dust(tile, head - direction * 12, direction, .16 + .46 * p, 25, 9)
            for delay, side in ((0, 3), (.14, -2)):
                t = flight - delay
                if t >= 0:
                    center = origin + delta * (.74 * t) + normal * side
                    _dust(tile, center, direction, .13 + .84 * t, 35, 10)
        elif self.kind == "swarm":
            from deck import skin
            from deck.elf_flight import FaeFlight
            sk = skin.use("elf")
            elapsed = age / self.life
            travel = 1 - (1 - elapsed) ** 2.6
            for i, cell in enumerate(self.cells):
                ray = (pygame.Vector2(cell) - self.origin) / step
                if ray.length_squared() < 1:
                    continue
                turn = (.38 + .09 * math.sin(i * 2.4)) * (1 - travel)
                point = origin + ray.rotate_rad(turn) * travel
                point.y -= 4 + 5 * math.sin(travel * math.pi)
                frame = FaeFlight._frame(sk, (int(age * pixfx.FPS) + i) % 4, 9, 1 if ray.x >= 0 else -1, False)
                wake = origin + ray.rotate_rad(turn) * (.90 * travel)
                _dust(tile, wake, ray, min(.98, .15 + elapsed * .8), 30, 12)
                if elapsed >= .52:
                    recoil = (elapsed - .52) / .48
                    dust = origin + ray + ray.normalize() * (4 * recoil)
                    _dust(tile, dust, ray, recoil, 32, 16)
                if frame:
                    tile.blit(frame, frame.get_rect(center=point))
        elif self.kind == "root":
            end = min(1, age / self.life * 1.65)
            points = []
            count = max(2, math.ceil(delta.length() / 2))
            for i in range(max(2, round(end * count) + 1)):
                t = min(end, i / count)
                bend = math.sin(t * 18) * math.sin(t * math.pi) * 2.6
                point = origin + delta * t + (0, bend)
                points.append(point)
            pygame.draw.lines(tile, (58, 42, 41), False, points, 4)
            pygame.draw.lines(tile, (177, 111, 66), False, points, 2)
            for i in range(3, len(points), 5):
                base = points[i]
                side = 1 if i % 2 else -1
                leaf = base + (4 * side, -5)
                pygame.draw.polygon(tile, (72, 140, 86), [base, base + (side, -4), leaf, base + (3 * side, -1)])
                pygame.draw.line(tile, (183, 206, 106), base, leaf)
                if i % 3 == 0:
                    pygame.draw.circle(tile, (174, 83, 125), leaf, 2)
                    tile.set_at((round(leaf.x), round(leaf.y - 1)), (249, 195, 164))
            rise = min(1, max(0, (age / self.life - .52) * 5))
            if rise:
                base = origin + delta
                tip = base + (4 * rise, -19 * rise)
                pygame.draw.polygon(tile, (59, 94, 54), [base - (5, 0), tip, base + (4, 0)])
                pygame.draw.polygon(tile, (220, 238, 145), [base - (2, 1), tip, base + (1, -3)])
        elif self.kind == "ground_drift":
            direction = delta.normalize() if delta.length_squared() else pygame.Vector2(1, 0)
            _dust(tile, origin + delta * (1 - (1 - age / self.life) ** 2), direction,
                  .16 + .75 * p, 44, 17)
        else:
            _dust(tile, origin + delta, delta, p, 38, 22)
        out = pygame.transform.scale(tile, (max(1, round(w * step * scale)), max(1, round(h * step * scale))))
        surf.blit(out, ((self.origin[0] + left * step) * scale + offset[0],
                        (self.origin[1] + top * step) * scale + offset[1]))


def play(view, kind, ctx):
    world = view.vfx
    depth = max(.82, min(1.25, ctx["scale"]))
    start, end = ctx["caster_ground"], ctx["target_ground"]
    def add(name, a, b, life, delay=0):
        world.cues.append(Wind(name, world.time + delay, life, a, b, depth, tuple(ctx["cells"])))

    if kind == "moon":
        a, b = ctx["caster"], ctx["target"]
        duration = max(.26, min(.80, math.dist(a, b) / 850))
        prop = "arrow_ice"
        world.prop(prop, *a, scale=36 * depth / view.props[prop].get_width(),
                   path=(a, b, duration, 0), orient=True, life=duration, opaque=True)
        add("slipstream", a, b, duration)
        add("gust", a, b, .62, duration)
        return duration
    if kind == "swarm":
        add("swarm", start, start, .48)
        return .25
    add("root", start, end, .64)
    return .41
