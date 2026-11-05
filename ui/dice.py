"""Кубик d20 в 3D, как в Baldur's Gate 3: настоящий икосаэдр с цифрами на гранях.

Пока ждёт броска — медленно вращается. Бросок: подлетает, кувыркается по инерции, замедляется и ложится выпавшей
гранью к зрителю (цифрой вверх). 20 — золотая вспышка и искры, 1 — красная трещина. Рисуется pygame-полигонами
(плоское освещение, порядок граней по глубине), без OpenGL.
"""
import itertools
import math
import random

import numpy as np
import pygame

from ui import theme as T

PHI = (1 + 5 ** 0.5) / 2
BODY = (74, 40, 120)
EDGE = (236, 196, 110)
DIGIT = (255, 226, 150)
LIGHT = np.array([-0.45, 0.55, 0.7])
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def _geometry():
    v = []
    for a, b in itertools.product((-1, 1), repeat=2):
        v += [(0, a, b * PHI), (a, b * PHI, 0), (b * PHI, 0, a)]
    v = np.array(v, float)
    faces = []
    for i, j, k in itertools.combinations(range(12), 3):
        if all(abs(np.linalg.norm(v[x] - v[y]) - 2) < 1e-6 for x, y in ((i, j), (j, k), (i, k))):
            n = np.cross(v[j] - v[i], v[k] - v[i])
            c = (v[i] + v[j] + v[k]) / 3
            faces.append((i, j, k) if np.dot(n, c) > 0 else (i, k, j))
    normals = []
    for f in faces:
        c = v[list(f)].mean(0)
        normals.append(c / np.linalg.norm(c))
    normals = np.array(normals)
    # цифры: противоположные грани в сумме 21, как у настоящего d20
    nums = [0] * 20
    order = sorted(range(20), key=lambda i: (-normals[i][2], math.atan2(normals[i][1], normals[i][0])))
    k = 1
    for i in order:
        if nums[i]:
            continue
        opp = int(np.argmin([np.dot(normals[i], normals[j]) for j in range(20)]))
        nums[i], nums[opp] = k, 21 - k
        k += 1
    return v, faces, normals, nums


VERTS, FACES, NORMALS, NUMS = _geometry()


def rot(axis, angle):
    axis = np.asarray(axis, float)
    axis = axis / (np.linalg.norm(axis) or 1)
    x, y, z = axis
    c, s = math.cos(angle), math.sin(angle)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def face_up(i):
    """«Верх» цифры на грани: к первой вершине грани."""
    f = FACES[i]
    c = VERTS[list(f)].mean(0)
    up = VERTS[f[0]] - c
    n = NORMALS[i]
    up = up - np.dot(up, n) * n
    return up / np.linalg.norm(up)


def landing(value, twist=0.0):
    """Поворот, при котором грань value смотрит на зрителя цифрой вверх."""
    i = NUMS.index(value)
    n, a = NORMALS[i], face_up(i)
    R = np.array([np.cross(a, n), a, n])
    return rot((0, 0, 1), twist) @ R


class Die:
    """Состояние кубика: idle (ждёт клика) → rolling → landed."""

    ROLL_TIME = 1.7

    def __init__(self, size=120, seed=None):
        self.size = size
        self.rng = random.Random(seed)
        self.R = rot((1, 1, 0), 0.6)
        self.state = "idle"
        self.t = 0.0
        self.value = None
        self.spin_axis = np.array([0.3, 1.0, 0.2])
        self.sparks = []
        self.glow = 0.0

    def roll(self, value):
        """Бросок к заданному числу (исход уже посчитан игрой)."""
        self.value = value
        self.state = "rolling"
        self.t = 0.0
        self.target = landing(value, self.rng.uniform(-0.25, 0.25))
        self.axis = np.array([self.rng.uniform(-1, 1), self.rng.uniform(-1, 1), self.rng.uniform(-0.4, 0.4)])
        self.turns = self.rng.uniform(5.5, 7.5) * math.pi

    @property
    def done(self):
        return self.state == "landed"

    def update(self, dt):
        if self.state == "idle":
            self.R = rot(self.spin_axis, dt * 0.9) @ self.R
        elif self.state == "rolling":
            self.t += dt
            k = min(1.0, self.t / self.ROLL_TIME)
            e = 1 - (1 - k) ** 3
            self.R = self.target @ rot(self.axis, self.turns * (1 - e))
            if k >= 1.0:
                self.state = "landed"
                self.R = self.target
                self._burst()
        else:
            self.glow = min(1.0, self.glow + dt * 2.5)
        for s in self.sparks:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[3] += 260 * dt
            s[4] -= dt
        self.sparks = [s for s in self.sparks if s[4] > 0]

    def _burst(self):
        if self.value in (1, 20):
            col = (255, 220, 110) if self.value == 20 else (255, 80, 70)
            for _ in range(70 if self.value == 20 else 40):
                a = self.rng.uniform(0, math.tau)
                sp = self.rng.uniform(120, 420)
                self.sparks.append([0.0, 0.0, math.cos(a) * sp, math.sin(a) * sp - 120, self.rng.uniform(0.5, 1.2), col])

    def offset(self):
        """Подлёт и подскоки при броске (смещение вверх в пикселях) и масштаб."""
        if self.state != "rolling":
            return 0.0, 1.0
        k = self.t / self.ROLL_TIME
        h = abs(math.sin(k * math.pi * 3.0)) * (1 - k) ** 1.5 * self.size * 1.1
        return h, 1.0 + 0.18 * (1 - k)

    def draw(self, surf, center, tint=None):
        """tint — цвет итога (успех/провал) для свечения после броска."""
        cx, cy = center
        lift, scale = self.offset()
        cy -= lift
        s = self.size * scale / PHI / 1.9
        if self.state == "landed" and tint:
            g = pygame.Surface((self.size * 4, self.size * 4), pygame.SRCALPHA)
            for r in range(10, 0, -1):
                a = int(14 * self.glow * (11 - r) / 10)
                pygame.draw.circle(g, (*tint, a), (self.size * 2, self.size * 2), int(self.size * (0.55 + r * 0.06)))
            surf.blit(g, (cx - self.size * 2, cy - self.size * 2))
        V = VERTS @ self.R.T
        persp = 6.0
        pts = [(cx + x * s * persp / (persp - z), cy - y * s * persp / (persp - z)) for x, y, z in V]
        N = NORMALS @ self.R.T
        order = sorted(range(20), key=lambda i: V[list(FACES[i])][:, 2].mean())
        crack = self.state == "landed" and self.value == 1
        for i in order:
            n = N[i]
            if n[2] <= 0:
                continue
            light = 0.32 + 0.68 * max(0.0, float(np.dot(n, LIGHT)))
            base = BODY
            if crack:
                base = T.mix(BODY, (150, 30, 30), 0.6 * self.glow)
            col = tuple(min(255, int(c * light + 40 * n[2] ** 8)) for c in base)
            poly = [pts[j] for j in FACES[i]]
            pygame.draw.polygon(surf, col, poly)
            pygame.draw.polygon(surf, T.mix(EDGE, (40, 30, 20), 0.55 - 0.45 * n[2]), poly, 2)
            if n[2] > 0.35:
                self._digit(surf, i, poly, n[2], s)
        if crack and self.glow > 0.2:
            front = max(range(20), key=lambda i: N[i][2])
            c = np.mean([pts[j] for j in FACES[front]], axis=0)
            for a in (0.3, 2.2, 4.1):
                x, y = c
                for k in range(4):
                    nx = x + math.cos(a + k * 0.6) * s * 0.35
                    ny = y + math.sin(a + k * 0.6) * s * 0.35
                    pygame.draw.line(surf, (255, 90, 70), (x, y), (nx, ny), 2)
                    x, y = nx, ny
        for x, y, _, _, life, col in self.sparks:
            r = max(1, int(3 * life))
            pygame.draw.circle(surf, col, (int(cx + x), int(cy + y)), r)

    def _digit(self, surf, i, poly, facing, s):
        num = str(NUMS[i])
        size = max(10, int(s * 0.62 * facing))
        img = T.render(num, size, DIGIT if not (self.state == "landed" and NUMS[i] == self.value) else (255, 255, 230),
                       True)
        up = face_up(i) @ self.R.T
        ang = math.degrees(math.atan2(up[0], up[1]))
        img = pygame.transform.rotate(img, ang)
        img.set_alpha(int(255 * min(1.0, (facing - 0.35) / 0.4)))
        c = np.mean(poly, axis=0)
        surf.blit(img, (c[0] - img.get_width() / 2, c[1] - img.get_height() / 2))
