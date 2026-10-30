"""Живые пиксельные частицы в мире поля (art_style.md, «физика → пиксель»).

Каждая частица живёт в координатах поля: (x, y) — клетки на земле, z — высота в клетках. Физика: гравитация,
плавучесть (тёплое всплывает, холодное оседает), сопротивление воздуха, остывание, удар о землю (погаснуть,
отскочить, остановиться). Рисуется квадратом в пиксельной сетке (пиксель эффекта = 2 экранных × глубина),
цвет — по температуре из палитры стихии с упорядоченным дизерингом; остывшая — дымом/паром своей палитры.
Приземление частицы с меткой (tag) возвращается из update — так брызги огня поджигают клетку там, где упали.
"""
import numpy as np

from ui import projection as P
from ui.pixfx_sim import BAYER, PAL

PALS = ["fire", "ice", "dust", "steam", "scorch", "water", "storm", "poison"]
PAL_ID = {n: i for i, n in enumerate(PALS)}
PAL_RGB = np.array([PAL[n] for n in PALS], np.uint8)          # [палитра, 6, 3]
GLOW_PALS = {PAL_ID["fire"], PAL_ID["ice"], PAL_ID["storm"]}
PX = 2

# что делает частица на земле
DIE, BOUNCE, STICK = 0, 1, 2
FIELDS = ("x", "y", "z", "vx", "vy", "vz", "age", "life", "temp", "cool", "buoy", "drag", "grav", "bounce", "size",
          "grow", "alpha", "smoke_at", "streak", "tall")
INTS = ("pal", "smoke", "land", "tag")


def project_many(x, y, z):
    """P.project для массивов: экранные x, y и масштаб глубины."""
    t = y - P.CY
    zc = np.maximum(P.DIST - t * P.COS - z * P.SIN, 0.05)
    yc = -t * P.SIN + z * P.COS
    return (P.CENTER_SCREEN[0] + P.FOCAL * (x - P.CX) / zc, P.CENTER_SCREEN[1] - P.FOCAL * yc / zc,
            P.DIST / zc * P.PX_PER_CELL / P.BASE_PX)


class Particles:
    CAP = 6000

    def __init__(self, seed=5):
        self.rng = np.random.default_rng(seed)
        self.n = 0
        for f in FIELDS:
            setattr(self, f, np.zeros(self.CAP, np.float32))
        for f in INTS:
            setattr(self, f, np.zeros(self.CAP, np.int16))
        self._frame = None

    def clear(self):
        self.n = 0

    def spawn(self, count, pos, vel=(0, 0, 0), life=1.0, temp=1.0, cool=1.0, buoy=0.0, drag=0.0, grav=0.0,
              bounce=0.3, size=1.0, grow=0.0, alpha=1.0, pal="fire", smoke="dust", smoke_at=0.2, land=DIE, tag=0,
              spread=0.0, jitter=0.0, life_var=0.3, streak=0.0, tall=0.0):
        """count частиц из точки pos (x, y, z клеток). vel — общая скорость (клетки/с), spread — разброс скорости
        во все стороны, jitter — разброс места. Любой параметр может быть массивом длины count.
        streak — искра рисуется штрихом: путь за streak секунд назад; tall — язык пламени вытягивается вверх,
        пока поднимается (длина ~ tall × скорость подъёма)."""
        k = min(int(count), self.CAP - self.n)
        if k <= 0:
            return slice(0, 0)
        if k < count:                          # лимит частиц: массивы параметров урезаем вместе с числом
            def cut(v):
                if isinstance(v, (tuple, list)):
                    return type(v)(cut(x) for x in v)
                a = np.asarray(v)
                return a[:k] if a.ndim and len(a) == count else v
            pos, vel = cut(pos), cut(vel)
            life, temp, cool, buoy, drag, grav, bounce, size, grow, alpha, smoke_at, tag, streak, tall = (
                cut(v) for v in (life, temp, cool, buoy, drag, grav, bounce, size, grow, alpha, smoke_at, tag,
                                 streak, tall))
        s = slice(self.n, self.n + k)
        r = self.rng
        for i, f in enumerate(("x", "y", "z")):
            getattr(self, f)[s] = np.asarray(pos[i], np.float32) + (r.normal(0, jitter, k) if jitter else 0)
        for i, f in enumerate(("vx", "vy", "vz")):
            getattr(self, f)[s] = np.asarray(vel[i], np.float32) + (r.normal(0, spread, k) if spread else 0)
        self.z[s] = np.maximum(self.z[s], 0.0)
        self.age[s] = 0.0
        self.life[s] = np.asarray(life, np.float32) * (1 + r.uniform(-life_var, life_var, k))
        for f, v in (("temp", temp), ("cool", cool), ("buoy", buoy), ("drag", drag), ("grav", grav),
                     ("bounce", bounce), ("size", size), ("grow", grow), ("alpha", alpha), ("smoke_at", smoke_at),
                     ("streak", streak), ("tall", tall)):
            getattr(self, f)[s] = v
        self.pal[s] = PAL_ID[pal]
        self.smoke[s] = PAL_ID[smoke] if smoke else -1
        self.land[s] = land
        self.tag[s] = tag
        self.n += k
        return s

    def update(self, dt):
        """Шаг физики. Возвращает [(tag, x, y)] — частицы с меткой, которые только что коснулись земли."""
        n = self.n
        if not n or dt <= 0:
            return []
        s = slice(0, n)
        x, y, z, vx, vy, vz = self.x[s], self.y[s], self.z[s], self.vx[s], self.vy[s], self.vz[s]
        vz += (self.buoy[s] - self.grav[s]) * dt
        k = np.exp(-self.drag[s] * dt)
        vx *= k
        vy *= k
        vz *= k
        x += vx * dt
        y += vy * dt
        z += vz * dt
        self.age[s] += dt
        self.temp[s] = np.maximum(0.0, self.temp[s] - self.cool[s] * dt)
        self.size[s] += self.grow[s] * dt
        landed = []
        hit = (z <= 0) & (vz < 0)
        if hit.any():
            tagged = hit & (self.tag[s] > 0)
            for i in np.nonzero(tagged)[0]:
                landed.append((int(self.tag[i]), float(x[i]), float(y[i])))
            self.tag[s][tagged] = 0
            z[hit] = 0.0
            land = self.land[s]
            die = hit & (land == DIE)
            self.age[s][die] = self.life[s][die]
            bo = hit & (land == BOUNCE)
            vz[bo] = -vz[bo] * self.bounce[s][bo]
            vx[bo] *= 0.55
            vy[bo] *= 0.55
            rest = hit & ((land == STICK) | (bo & (np.abs(vz) < 0.6)))
            vx[rest] = vy[rest] = vz[rest] = 0.0
            self.grav[s][rest] = 0.0
            self.buoy[s][rest] = 0.0
        alive = self.age[s] < self.life[s]
        if not alive.all():
            idx = np.nonzero(alive)[0]
            m = len(idx)
            for f in FIELDS + INTS:
                a = getattr(self, f)
                a[:m] = a[:n][idx]
            self.n = m
        return landed

    # ---------- отрисовка ----------

    def prepare(self, dim=1.0):
        """Экранные квадраты на этот кадр: (x, y, сторона, цвет, светится, глубина) для живых частиц."""
        n = self.n
        self._frame = None
        if not n:
            return 0
        s = slice(0, n)
        sx, sy, k = project_many(self.x[s], self.y[s], self.z[s])
        _, gy, _ = project_many(self.x[s], self.y[s], np.zeros(n, np.float32))
        side = np.maximum(1, np.round(PX * k * self.size[s])).astype(int)
        qx = np.floor(sx / side).astype(int)
        qy = np.floor(sy / side).astype(int)
        th = BAYER[qy % 4, qx % 4]
        left = 1 - self.age[s] / np.maximum(self.life[s], 1e-3)
        temp = self.temp[s]
        smoke = (temp < self.smoke_at[s]) & (self.smoke[s] >= 0)
        hot_i = np.clip((temp * 6 + th - 0.5).astype(int), 0, 5)
        smoke_i = np.clip((1 + left * 2 + th - 0.5).astype(int), 0, 3)
        pal = np.where(smoke, self.smoke[s], self.pal[s])
        idx = np.where(smoke, smoke_i, hot_i)
        # прозрачность — дизерингом: остывший дым редеет к концу жизни, горячее держится
        a = self.alpha[s] * np.where(smoke, left * 1.4, np.minimum(1.0, left * 3)) * dim
        show = a > th * 0.95
        glow = ~smoke & (idx >= 5) & np.isin(self.pal[s], list(GLOW_PALS))     # светится только белое ядро
        cols = PAL_RGB[np.maximum(pal, 0), idx]
        keep = np.nonzero(show)[0]
        # язык пламени: столбик из нескольких пикселей над точкой, пока жар поднимается
        tall = np.round(self.tall[s] * np.clip(self.vz[s], 0, 1.5) * ~smoke).astype(int)
        st = self.streak[s]
        x0, y0, _ = project_many(self.x[s] - self.vx[s] * st, self.y[s] - self.vy[s] * st, self.z[s] - self.vz[s] * st)
        self._frame = (qx[keep] * side[keep], qy[keep] * side[keep], side[keep], cols[keep], glow[keep], gy[keep],
                       tall[keep], st[keep] > 0, x0[keep], y0[keep])
        return len(keep)

    def buckets(self, step=24):
        """Группы частиц по глубине (экранная y точки земли под ними) — встают в общий порядок с юнитами."""
        if self._frame is None:
            return []
        gy = self._frame[5]
        key = (gy // step).astype(int)
        out = []
        order = np.argsort(key, kind="stable")
        keys = key[order]
        cuts = np.nonzero(np.diff(keys))[0] + 1
        for part in np.split(order, cuts):
            if len(part):
                out.append((float(keys[part[0]] * step + step - 1), part))
        return out

    def draw(self, surf, glow, part):
        x, y, side, cols, gl, _, tall, streak, x0, y0 = self._frame
        fill = surf.fill
        for i in part:
            c, w = tuple(cols[i]), int(side[i])
            if streak[i]:                      # штрих: пиксели вдоль пути искры (в той же сетке)
                ax, ay, bx, by = float(x0[i]), float(y0[i]), float(x[i]), float(y[i])
                n = max(1, int(max(abs(bx - ax), abs(by - ay)) / w))
                for j in range(n + 1):
                    t = j / n
                    r = (int((ax + (bx - ax) * t) // w * w), int((ay + (by - ay) * t) // w * w), w, w)
                    fill(c, r)
                    if glow is not None and gl[i]:
                        glow.fill(c, r)
                continue
            h = w * (1 + int(tall[i]))
            r = (int(x[i]), int(y[i]) - h + w, w, h)
            fill(c, r)
            if glow is not None and gl[i]:
                glow.fill(c, r)
