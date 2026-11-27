"""Плотные контуры заклинаний для рисования поверх поля в CPU-режиме."""

import math
from dataclasses import dataclass

import pygame


@dataclass
class Cue:
    kind: str
    start: float
    life: float
    pos: tuple
    color: tuple
    size: float
    path: object = None

    def draw(self, surf, time, scale, offset):
        age = time - self.start
        if not 0 <= age < self.life:
            return
        progress = age / self.life
        x, y = self.path(age) if self.path is not None else self.pos
        x, y = round(x * scale + offset[0]), round(y * scale + offset[1])
        size = self.size * scale
        ink = (25, 27, 39)
        tint = self.color
        light = tuple(round(c + (255 - c) * .58) for c in tint)
        if self.kind == "trail":
            tail = max(0, age - .13)
            points = [self.path(tail + (age - tail) * i / 5) for i in range(6)]
            points = [(round(px * scale + offset[0]), round(py * scale + offset[1])) for px, py in points]
            pygame.draw.lines(surf, ink, False, points, max(2, round(size)))
            pygame.draw.lines(surf, tint, False, points, max(1, round(size * .59)))
            pygame.draw.lines(surf, light, False, points, max(1, round(size * .29)))
        elif self.kind == "orb":
            radius = max(2, round(size * (.92 + .08 * math.sin(age * 24))))
            pygame.draw.circle(surf, ink, (x, y), radius + max(1, round(scale)))
            pygame.draw.circle(surf, tint, (x, y), radius)
            pygame.draw.circle(surf, light, (x, y), max(1, round(radius * .62)))
        elif self.kind == "ward":
            w = max(4, round(size * (1 + progress * .2)))
            h = max(5, round(w * 1.25))
            arc = pygame.Rect(x - w, y - h, 2 * w, 2 * h)
            border = max(2, round(3 * scale))
            pygame.draw.arc(surf, ink, arc, .19, math.pi - .19, border + 2)
            pygame.draw.arc(surf, light, arc.inflate(-2, -2), .19, math.pi - .19, border)
        elif self.kind == "ring":
            radius = max(3, round(size * (.44 + .60 * progress)))
            depth = max(3, round(radius * .56))
            ring = pygame.Rect(x - radius, y - depth, 2 * radius, 2 * depth)
            width = max(1, round(scale * (2.6 - progress * 1.6)))
            pygame.draw.ellipse(surf, ink, ring, width + 2)
            pygame.draw.ellipse(surf, light, ring.inflate(-2, -2), width)
        else:
            # Искры расходятся от точки попадания. В конце кадра остаются короткие штрихи.
            for i in range(6):
                angle = i * math.tau / 6 + .29
                dx, dy = math.cos(angle), math.sin(angle)
                far = size * (.52 + .65 * progress)
                near = far * (.33 + .51 * progress)
                a = round(x + dx * near), round(y + dy * near)
                b = round(x + dx * far), round(y + dy * far)
                pygame.draw.line(surf, ink, a, b, max(2, round(scale * 4)))
                pygame.draw.line(surf, light if progress < .65 else tint, a, b, max(1, round(scale * 2)))
