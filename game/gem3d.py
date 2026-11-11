"""Самоцвет в 3D для огранки: выпуклый многогранник (грани — плоскости), срез плоскостью, объём и отрисовка
с эффектами камня — блики (отражение ламп, Френель), преломление с дисперсией («огонь»: свой показатель для
красного, зелёного, синего), полное внутреннее отражение от нижних граней. Грань: {"pts", "n", "kind"}, kind —
rough (сырой камень, матовый), frost (свежесточенная, белёсая), polish (полированная, играет светом),
girdle (рундист, матовый поясок)."""
import math
import random

import pygame


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    ln = math.sqrt(dot(a, a)) or 1.0
    return (a[0] / ln, a[1] / ln, a[2] / ln)


def box(r, z0, z1):
    """Заготовка — брусок: |x|, |y| ≤ r, z0 ≤ z ≤ z1 (ось z — к калетте, вниз от короны)."""
    v = [(-r, -r, z0), (r, -r, z0), (r, r, z0), (-r, r, z0), (-r, -r, z1), (r, -r, z1), (r, r, z1), (-r, r, z1)]
    quads = (((0, 3, 2, 1), (0, 0, -1)), ((4, 5, 6, 7), (0, 0, 1)), ((0, 1, 5, 4), (0, -1, 0)),
             ((2, 3, 7, 6), (0, 1, 0)), ((1, 2, 6, 5), (1, 0, 0)), ((0, 4, 7, 3), (-1, 0, 0)))
    return [{"pts": [v[i] for i in q], "n": n, "kind": "rough"} for q, n in quads]


def clip(faces, n, h, kind="frost", eps=1e-7):
    """Срез: остаётся часть p·n ≤ h; на месте среза — новая грань kind."""
    out, cap = [], []
    for f in faces:
        pts = f["pts"]
        new = []
        k = len(pts)
        for i in range(k):
            a, b = pts[i], pts[(i + 1) % k]
            da, db = dot(a, n) - h, dot(b, n) - h
            if da <= eps:
                new.append(a)
            if abs(da) <= eps:
                cap.append(a)
            if (da < -eps and db > eps) or (da > eps and db < -eps):
                p = add(a, mul(sub(b, a), da / (da - db)))
                new.append(p)
                cap.append(p)
        if len(new) >= 3:
            out.append(dict(f, pts=new))
    uniq = []
    for p in cap:
        if all(dot(sub(p, q), sub(p, q)) > 1e-8 for q in uniq):
            uniq.append(p)
    if len(uniq) >= 3:
        c = mul(sum_v(uniq), 1 / len(uniq))
        u = norm(sub(uniq[0], c))
        w = cross(n, u)
        uniq.sort(key=lambda p: math.atan2(dot(sub(p, c), w), dot(sub(p, c), u)))
        out = [f for f in out if not (abs(dot(f["n"], n) - 1) < 1e-6 and abs(dot(f["pts"][0], n) - h) < 1e-4)]
        out.append({"pts": uniq, "n": n, "kind": kind})
    return out


def sum_v(pts):
    x = y = z = 0.0
    for p in pts:
        x += p[0]
        y += p[1]
        z += p[2]
    return (x, y, z)


def face_area(f):
    pts = f["pts"]
    s = (0.0, 0.0, 0.0)
    for i in range(len(pts)):
        s = add(s, cross(pts[i], pts[(i + 1) % len(pts)]))
    return abs(dot(s, f["n"])) / 2


def volume(faces):
    return sum(face_area(f) * dot(f["n"], f["pts"][0]) for f in faces if f["pts"]) / 3


def extent(faces, n):
    return max((dot(p, n) for f in faces for p in f["pts"]), default=0.0)


def polished(faces):
    """Свежие (матовые) грани — в полировку."""
    return [dict(f, kind="polish") if f["kind"] == "frost" else f for f in faces]


# ---------- свет и шейдинг ----------

LAMPS = (((-0.55, -0.75, 0.38), (255, 230, 190), 8, 1.3), ((0.65, -0.55, 0.5), (200, 220, 255), 10, 1.1),
         ((0.0, -0.15, 1.0), (255, 255, 255), 30, 1.6), ((-0.75, 0.2, 0.6), (255, 200, 140), 6, 0.7),
         ((0.3, 0.85, 0.4), (150, 140, 130), 3, 0.5))


def env(d, t=0.0):
    """Студия огранщика: мягкий фон (светлее сверху), тёплая лампа, холодное окно, блик, отсвет диска снизу."""
    up = max(0.0, -d[1])
    r = g = b = 26.0 + 50.0 * up
    wob = 0.12 * math.sin(t * 0.7)
    for (lx, ly, lz), col, k, gain in LAMPS:
        L = norm((lx + wob, ly, lz))
        v = gain * max(0.0, dot(d, L)) ** k
        r += col[0] * v
        g += col[1] * v
        b += col[2] * v
    return (r, g, b)


def reflect(d, n):
    return sub(d, mul(n, 2 * dot(d, n)))


def refract(d, n, eta):
    c = -dot(d, n)
    k = 1 - eta * eta * (1 - c * c)
    if k < 0:
        return reflect(d, n)
    return norm(add(mul(d, eta), mul(n, eta * c - math.sqrt(k))))


IOR = (2.38, 2.42, 2.47)                     # дисперсия: красный, зелёный, синий («огонь» камня)


def shade(f, N, world_normals, kinds, color, t, seed):
    """Цвет грани. N — нормаль в мире (к зрителю +z), world_normals/kinds — все грани (для внутреннего отражения)."""
    view = (0.0, 0.0, -1.0)
    diff = max(0.0, dot(N, norm((-0.5, -0.7, 0.5))))
    kind = f["kind"]
    if kind == "rough":                       # сырой камень: тусклый, матовый
        k = 0.45 + 0.55 * diff
        return tuple(int(min(255, (c * 0.55 + 60) * k)) for c in color)
    if kind in ("frost", "girdle"):           # свежесточенная грань / рундист: белёсая, матовая
        k = 0.45 + 0.55 * diff
        base = tuple(c * 0.4 + 150 for c in color)
        return tuple(int(min(255, c * k)) for c in base)
    cosv = max(0.0, N[2])
    fres = 0.05 + 0.95 * (1 - cosv) ** 5
    refl = env(reflect(view, N), t)
    out = []
    for ch in range(3):                       # преломление и полное внутреннее отражение от нижних граней
        T = refract(view, N, 1 / IOR[ch])
        best, bi = -2.0, -1
        for i, nb in enumerate(world_normals):
            d = dot(T, nb)
            if d > best:
                best, bi = d, i
        nb = world_normals[bi]
        if kinds[bi] == "polish":
            T2 = reflect(T, nb)
            T3 = reflect(T2, world_normals[(bi + 3) % len(world_normals)])
            lit = env(T2, t)[ch] * 0.7 + env(T3, t)[ch] * 0.5
        else:                                  # низ не огранён — свет уходит, камень мутный
            lit = 60.0
        tint = 0.2 + 0.8 * color[ch] / 255     # тело камня — свой цвет, на гранях — вспышки
        body = 18 + lit * tint * 1.25 + (lit - 120) * 0.35 * (lit > 200)
        out.append(body * (1 - fres) + refl[ch] * fres * 1.6)
    return tuple(int(max(0, min(255, v))) for v in out)


def render(surf, faces, to_world, center, scale, color, t=0.0, sparkle=True):
    """Отрисовка: to_world(p) → (X, Y, Z) (Z — к зрителю); отсечение задних граней, шейдинг, кромки, искры."""
    if not faces:
        return
    wn = []
    for f in faces:
        a = to_world((0.0, 0.0, 0.0))
        b = to_world(f["n"])
        wn.append(norm(sub(b, a)))
    kinds = [f["kind"] for f in faces]
    cx, cy = center
    sparks = []
    for i, f in enumerate(faces):
        N = wn[i]
        if N[2] <= 0.0:
            continue
        pts3 = [to_world(p) for p in f["pts"]]
        pts = [(cx + p[0] * scale, cy + p[1] * scale) for p in pts3]
        col = shade(f, N, wn, kinds, color, t, i)
        pygame.draw.polygon(surf, col, pts)
        if f["kind"] == "frost":               # следы шлифовки — мелкая штриховка
            rng = random.Random(i * 7919 + len(f["pts"]))
            c0 = mul(sum_v(pts3), 1 / len(pts3))
            for _ in range(min(14, 2 + int(face_area(f) * scale * scale / 900))):
                p = rng.choice(pts3)
                q = add(c0, mul(sub(p, c0), rng.uniform(0.1, 0.85)))
                x, y = cx + q[0] * scale, cy + q[1] * scale
                pygame.draw.line(surf, (235, 235, 240), (x - 3, y), (x + 3, y), 1)
        edge = tuple(min(255, c + 50) for c in col) if f["kind"] == "polish" else tuple(max(0, c - 40) for c in col)
        pygame.draw.polygon(surf, edge, pts, 1)
        if sparkle and f["kind"] == "polish" and sum(col) > 600:
            sparks.append((max(pts, key=lambda p: p[1] * 0.3 - p[0]), sum(col)))
    for (x, y), v in sparks[:6]:               # звёздочки-искры на самых ярких гранях
        k = 3 + int(4 * (0.5 + 0.5 * math.sin(t * 6 + x)))
        pygame.draw.line(surf, (255, 255, 255), (x - k, y), (x + k, y), 1)
        pygame.draw.line(surf, (255, 255, 255), (x, y - k), (x, y + k), 1)


# ---------- заготовка самоцвета ----------

GIRDLE = 0.03                                  # полутолщина рундиста (доля радиуса)


def make_stone(rng, R):
    """Сырой камень: рундист (поясок из 16 граней) уже выточен, верх и низ — неровные сколы с запасом."""
    faces = box(R * 1.3, -0.62 * R, 1.12 * R)
    for k in range(16):
        a = math.tau * k / 16
        faces = clip(faces, (math.cos(a), math.sin(a), 0.0), R, "girdle")
    for side, depth in ((1, 1.02), (-1, 0.48)):
        for _ in range(7):                      # сколы: неровная форма, но не глубже нужного
            th = math.radians(rng.uniform(18, 55))
            a = rng.uniform(0, math.tau)
            n = (math.sin(th) * math.cos(a), math.sin(th) * math.sin(a), side * math.cos(th))
            off = R * (math.sin(th) * 1.0 + math.cos(th) * depth * rng.uniform(1.02, 1.12))
            faces = clip(faces, n, off, "rough")
    return faces


def planes(faces):
    """Форма камня для сохранения: [[nx, ny, nz, отступ, вид]]."""
    return [[round(f["n"][0], 5), round(f["n"][1], 5), round(f["n"][2], 5), round(dot(f["n"], f["pts"][0]), 4),
             f["kind"]] for f in faces if f["pts"]]


def from_planes(pl, R=100.0):
    """Камень обратно из плоскостей (пересечение полупространств)."""
    faces = box(R * 3, -R * 3, R * 3)
    for nx, ny, nz, off, kind in pl:
        faces = clip(faces, (nx, ny, nz), off, kind)
    return faces
