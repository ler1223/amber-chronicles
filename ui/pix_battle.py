"""Пилот пиксельного стиля в бою (art_style.md, раздел 9.1): огонь и лёд — навыки, атаки, статусы, клетки, реакции.

BattleView спрашивает пилот в нужных местах: если он нарисовал своё, старый эффект не играется. Переключатель —
настройка fx_style (F9 в бою) — сравнение стилей на одном и том же бою (ui/fxlab — остальные стили).
"""
import math

import numpy as np
import pygame

from ui import projection as P
from ui import theme as T
from ui import pixmesh as M
from ui.pix_spells import Spells
from ui.pixsim import BOUNCE, DIE
from ui.pixfire import FireField, IceField
from ui.pixfx import FPS, PixFx, family
from ui.settings import SETTINGS

FIRE_LIGHT = (255, 140, 50)
ICE_LIGHT = (140, 200, 255)
FIRE_REACTIONS = {"melt", "steam", "freeze", "blaze", "shatter", "overload", "toxic"}
AREA_EFFECTS = {"damage", "hazard", "cell_tag", "status"}     # навык бьёт по площади — след на каждой клетке


class PixelPilot:
    def __init__(self, view):
        self.view = view
        self.fx = PixFx()
        self.glow = None           # слой свечения (размер экрана), только с OpenGL
        self.glow_used = False     # в этом кадре свечение собирается
        self.glow_dirty = False    # на слой что-то легло (иначе его не нужно ни чистить, ни отдавать видеокарте)
        self.time = 0.0            # игровое время: на паузе пламя замирает вместе с боем
        self.burning = set()       # клетки, горевшие в прошлом кадре
        self.burning_units = set()  # юниты, горевшие в прошлом кадре
        self.fire = FireField()    # горящие клетки — единая горящая поверхность
        self.ice = IceField(seed=8)  # ледяные клетки — единая ледяная корка
        self.icy = set()           # клетки, покрытые льдом в прошлом кадре
        self._masks = {}           # картинка фигурки → точки контура и тела (для огоньков по модели)
        self._acc = {}
        self._tongues = []         # языки пламени на клетках: [x, y, осталось жить, фаза покачивания]
        self._unit_src = {}        # юнит → корни огоньков на модельке: [доля x, доля y, осталось жить]
        self._born, self._wall_hp, self._wall_cache, self._wall_rects = {}, {}, {}, {}
        self._breaks = []          # раскалывающиеся куски ледяной стены
        self._deto = []            # детонации Вспышки этого кадра — взрываются одной поверхностью
        self._wall_key, self._wall_map = None, {}
        self.spells = Spells(self)  # живые частицы: снаряды-кометы и удары (эталон: огненный шар, метеор, лёд)

    @property
    def on(self):
        return SETTINGS.get("fx_style", "pixel") == "pixel"

    def toggle(self):
        self.fx.clear()
        self.spells.clear()
        self.fire.clear()
        self._tongues.clear()
        return self.on

    def reset(self):
        self.burning, self.burning_units, self.icy = set(), set(), set()   # «уже горело» — только в этом бою
        self._breaks.clear()
        self._wall_rects.clear()
        self._born.clear()
        self._wall_hp.clear()
        self._wall_key = None
        self.fx.clear()
        self.spells.clear()
        self.fire.clear()
        self._tongues.clear()
        if self.on:
            self.fx.lib.warm()

    def update(self, dt):
        if dt > 0:
            self.time += dt
            self.fx.update(dt)
            self.spells.update(dt)
            if self.on and self.view.combat is not None:
                self._burn(dt, self.view.combat)

    def _rate(self, key, per_sec, dt):
        a = self._acc.get(key, 0.0) + per_sec * dt
        n = int(a)
        self._acc[key] = a - n
        return n

    def _burn(self, dt, c):
        """Огонь живёт: поле жара под горящими клетками, языки пламени по всей площади, огоньки по фигуркам."""
        S = self.spells
        cells = [pos for pos, cell in c.grid.cells.items() if cell.hazard == "fire" and not S.held(pos)]
        self.fire.update(dt, cells, c.grid.w, c.grid.h)
        frozen = [pos for pos, cell in c.grid.cells.items() if cell.hazard == "ice" and not S.held(pos)]
        self.ice.update(dt, frozen, c.grid.w, c.grid.h)
        self.icy = set(frozen)
        self._cell_tongues(dt, len(cells))
        n = self._rate("sparks", 1.5 * len(cells), dt)
        pts = self.fire.sample(n, S.rng) if n else None
        if pts is not None:                    # редкие искры улетают высоко
            S.ps.spawn(n, (pts[0], pts[1], np.full(n, 0.1)), (0, 0, 1.2), life=1.1, temp=0.85, cool=0.6, buoy=0.6,
                       drag=1.0, pal="fire", smoke=None, spread=0.35)
        rects = {u.id: r for r, u in self.view.sprite_rects}
        for u in c.alive():
            if "fire" not in u.statuses or S.unit_held(u) or u.id not in rects:
                continue
            k = self._rate(("u", u.id), 28, dt)
            if k:
                self._unit_flames(u, rects[u.id], k, dt)

    def _cell_tongues(self, dt, ncells):
        """Пламя на клетках — отдельные языки, как у настоящего огня: у каждого свой корень, живёт пару секунд,
        покачивается; поток жара из корня: у основания жёлтый и широкий, к кончику тоньше, краснеет, коптит."""
        S = self.spells
        t = self._tongues
        for g in t:
            g[2] -= dt
        t[:] = [g for g in t if g[2] > 0]
        want = int(7 * ncells)
        if len(t) < want:
            pts = self.fire.sample(want - len(t), S.rng)
            if pts is not None:
                for x, y in zip(*pts):
                    t.append([float(x), float(y), float(S.rng.uniform(0.8, 2.4)), float(S.rng.uniform(0, 6.3))])
        if not t:
            return
        n = self._rate("tongues", 30 * len(t), dt)
        if not n:
            return
        i = S.rng.integers(0, len(t), n)
        arr = np.array(t)[i]
        sway = np.sin(self.time * 7 + arr[:, 3]) * 0.25
        life = np.minimum(1.0, arr[:, 2] * 2)        # гаснущий язык ниже и тусклее
        S.ps.spawn(n, (arr[:, 0], arr[:, 1], np.full(n, 0.02)), (sway, np.zeros(n), 0.7 * life), life=0.6 * life,
                   temp=S.rng.uniform(0.8, 0.97, n) * (0.7 + 0.3 * life), cool=1.6, buoy=3.0, drag=3.5, size=2.4,
                   grow=-3.2, tall=0.8, pal="fire", smoke="dust", smoke_at=0.12, jitter=0.07, life_var=0.25)

    def _mask(self, img):
        """Точки контура и тела картинки, доли ширины и высоты (кэш по картинке)."""
        m = self._masks.get(id(img))
        if m is None or m[0] is not img:
            if len(self._masks) > 300:
                self._masks.clear()
            mask = pygame.mask.from_surface(img)
            w, h = img.get_size()
            edge = np.array(mask.outline() or [(w // 2, h // 2)], float) / (w, h)
            a = pygame.surfarray.array_alpha(img)
            xs, ys = np.nonzero(a > 0)
            body = np.stack([xs, ys], 1) / (w, h) if len(xs) else edge
            m = self._masks[id(img)] = (img, edge, body)
        return m[1], m[2]

    def _unit_flames(self, u, rect, k, dt):
        """Мелкие огоньки по модельке: 4–5 маленьких языков с корнями на контуре и на теле (живут ~1 сек и
        переползают); из каждого корня — короткий поток жара вверх. Корни — в долях картинки, поэтому огонь
        едет вместе с фигуркой."""
        view, S = self.view, self.spells
        edge, body = self._mask(view.sprite_of(u, view.anim(u).facing < 0))
        src = self._unit_src.setdefault(u.id, [])
        for g in src:
            g[2] -= dt
        src[:] = [g for g in src if g[2] > 0]
        while len(src) < 5:
            pt = edge[S.rng.integers(len(edge))] if S.rng.random() < 0.6 else body[S.rng.integers(len(body))]
            if pt[1] < 0.12:                   # не с макушки: огонь лижет тело, а не висит над головой
                continue
            src.append([float(pt[0]), float(pt[1]), float(S.rng.uniform(0.6, 1.4))])
        pts = np.array(src)[S.rng.integers(0, len(src), k), :2]
        sx = rect.x + pts[:, 0] * rect.w
        sy = rect.y + pts[:, 1] * rect.h
        gx, gy = view.ground_pos(u)
        fx, fy, _ = P.project(gx, gy)
        hpx = max(1.0, fy - P.project(gx, gy, 1.0)[1])
        wpx = max(1.0, P.project(gx + 1, gy)[0] - fx)
        S.ps.spawn(k, (gx + (sx - fx) / wpx, np.full(k, gy + 0.08), np.maximum(0.02, (fy - sy) / hpx)), (0, 0, 0.45),
                   life=0.34, temp=S.rng.uniform(0.78, 0.95, k), cool=1.3, buoy=2.2, drag=3.5, size=1.5, grow=-2.0,
                   tall=0.6, pal="fire", smoke="dust", smoke_at=0.12, jitter=0.02, life_var=0.3)

    def _flat(self, p):
        """Экранная точка земли → точка плоской карты (или None за краем)."""
        g = P.unproject(*p)
        return P.ground_to_flat(*g) if g is not None else None

    def _stamp(self, name, p, scale=1.0, alpha=180):
        f = self._flat(p)
        if f is not None:
            img = self.fx.ground_img(name, self.fx.var(), scale)
            img.set_alpha(alpha)
            self.view.marks.stamp_surface(img, *f)
            img.set_alpha(255)

    def _frost(self, p, ttl=5.0, delay=0.0):
        """Иней на земле: тает за несколько секунд (подпалина остаётся, лёд — нет)."""
        f = self._flat(p)
        if f is not None:
            self.fx.add("frost", f, ground=True, ttl=ttl, fade=1.5, alpha=190, delay=delay)

    def _stamp_g(self, name, g, scale=1.0, alpha=180):
        """След по точке земли в клетках (а не по экранной точке)."""
        img = self.fx.ground_img(name, self.fx.var(), scale)
        img.set_alpha(alpha)
        self.view.marks.stamp_surface(img, *P.ground_to_flat(*g))
        img.set_alpha(255)

    def _follow(self, at, color, radius, dur):
        """Свет летит вместе со снарядом (at() — точка x, y, z)."""
        V = self.view.vfx
        start = V.time

        def pos():
            x, y, _ = P.project(*at())
            return x, y
        V.add_light({"radius": radius, "intensity": 0.9, "color": "tag", "fadein": 0.0}, pos, color,
                    alive=lambda: V.time - start < dur)

    def _light(self, pos, color, radius, intensity=1.2, life=0.5):
        self.view.vfx.add_light({"radius": radius, "intensity": intensity, "life": life, "color": "tag",
                                 "fadein": 0.02}, pos, color)

    def _at(self, name, ground, lift=0.0, delay=0.0, scale=1.0, anchor="center", **kw):
        """Эффект над точкой земли: lift — доля высоты кадра над землёй (0.5 — центр кадра на земле)."""
        n = self.fx.lib.get(name)[0][0].get_height()
        g = P.unproject(*ground)
        k = (P.scale_at(g[1]) if g is not None else 1.0) * scale
        y = ground[1] - (n * 2 * k * lift if anchor == "center" else 0)
        return self.fx.add(name, (ground[0], y), delay=delay, depth=ground[1], scale=scale, anchor=anchor, **kw)

    # ---------- навыки и атаки ----------

    def attack(self, e, a, b):
        """Дальняя атака огнём или льдом: пиксельный снаряд. Возвращает время полёта или None."""
        if not self.on or e["kind"] == "melee" or e.get("tag") not in ("fire", "ice"):
            return None
        fire = e["tag"] == "fire"
        S = self.spells
        dst = e["dst"]
        src = S.hand(e["src"], self.view.ground_pos(dst))
        hit = S.contact(src, dst)
        S.hold_units([dst], 3.0)                 # тег стихии виден на цели по прилёте

        def land(p, d):
            S.release(dst.cell)
            if fire:
                S.fire_hit_unit(p, d, scale=0.6)
            else:
                S.ice_hit_unit(p, d, dst, scale=0.6)
        return S.comet(src, hit, "fire" if fire else "ice", land, speed=11 if fire else 13,
                       scale=1.1 if fire else 1.3)

    def _follow_light(self, fx, color, radius):
        V = self.view.vfx
        start = V.time
        V.add_light({"radius": radius, "intensity": 0.9, "color": "tag", "fadein": 0.0}, fx.point, color,
                    alive=lambda: V.time - start < fx.ttl)

    def skill(self, u, sk, spec, ctx, color, far, radius, tier, sid=None):
        """Навык огня или льда: свой снаряд и удар. Возвращает время до удара или None (не стихия пилота)."""
        fam = family(sk)
        if not self.on or fam is None:
            return None
        V = self.view.vfx
        tr = spec.get("travel") if far else None
        impact = spec.get("impact") or ""
        hit = (lambda: self.impact(fam, impact, ctx, radius, tier, sk))
        if sid == "ice_wall":                    # стена растёт сама (draw_object), удара нет
            return 0.0
        if sid == "flashpoint":                  # взрывается пожар (detonate), у мага — только искра в руке
            S = self.spells
            gx, gy = self.view.ground_pos(u)
            S.ps.spawn(16, (gx + 0.2, gy, 0.6), (0, 0, 1.5), life=0.35, temp=1.0, cool=2.0, drag=2.0, pal="fire",
                       smoke=None, spread=1.4, streak=0.03)
            return 0.0
        if sid == "blizzard" and not tr:         # пилот льда по образцу огненного шара
            return self._blizzard(u, ctx, radius, tier)
        if not tr:
            hit()
            return spec.get("delay", 0.0)
        ref = self._reference(u, tr, ctx, fam, radius, tier)
        if ref is not None:
            return ref + spec.get("delay", 0.0)
        if tr.get("prop"):           # бомба: моделька летит по-старому, взрыв — пиксельный
            d = self.view._launch(dict(spec, impact=None), ctx, ctx["caster"], ctx["target"], color)
        else:
            a, b = ctx["caster"], ctx["target"]
            if tr.get("to") == "ground":
                b = ctx["target_ground"]
            sky = tr.get("from") == "sky"
            if sky:
                off = tr.get("sky", [-140, -560])
                a = (b[0] + off[0], b[1] + off[1])
            fire = fam == "fire"
            big = sky or radius >= 2
            fx = self.fx.projectile(("orb_big" if big else "orb") if fire else "shard", a, b,
                                    speed=650 if fire else 900, arc=0 if sky else min(40, tr.get("arc", 0)),
                                    dur=tr.get("time"), scale=1.0 + 0.14 * tier + (0.4 if big and not fire else 0),
                                    trail="ember" if fire else None, orient=not fire)
            self._follow_light(fx, FIRE_LIGHT if fire else ICE_LIGHT, 110 if big else 80)
            d = fx.ttl + spec.get("delay", 0.0)
        V.after(d, hit)
        return d

    def _blizzard(self, u, ctx, radius, tier):
        """Буран: туча собралась при касте (cast_area), теперь с неба рушится шквал ледяных осколков; клетки и
        цели замерзают, когда он долетел (ui/pix_spells.py: squall, ice_hit_area)."""
        S = self.spells
        g = P.unproject(*ctx["target_ground"]) if ctx.get("target_ground") else None
        if g is None:
            return None
        area = self._area(ctx)
        cells = {pos for _, pos in area} | {(int(g[0]), int(g[1]))}
        S.hold_cells(cells, 3.0, "ice")
        S.hold_units([w for w in self.view.combat.units if w.cell in cells], 3.0)
        s = 1.0 + 0.14 * tier
        return S.squall(g[0], g[1], area, radius, s)      # без снаряда: шквал с неба (туча собралась при касте)

    def _area(self, ctx, skip=None):
        """Клетки площади навыка: [(центр клетки на земле, клетка)], кроме skip."""
        out = []
        for p in ctx.get("cells") or []:
            g = P.unproject(*p) if p else None
            if g is None:
                continue
            pos = (int(g[0]), int(g[1]))
            if pos != skip:
                out.append(((pos[0] + 0.5, pos[1] + 0.5), pos))
        return out

    def _reference(self, u, tr, ctx, fam, radius, tier):
        """Эталонные снаряды на живых частицах: огненный шар (комета → удар о цель, брызги поджигают клетки),
        метеор (падает с неба → удар в землю), ледяной снаряд (осколок → раскол, лёд растёт по земле).
        Возвращает время до удара или None — навык ещё на старом пиксельном пилоте."""
        if tr.get("prop"):
            return None
        S = self.spells
        tgt = ctx.get("target_unit")
        g = P.unproject(*ctx["target_ground"]) if ctx.get("target_ground") else None
        if g is None:
            return None
        if tgt is None and tr.get("from") != "sky":     # навык по клетке, а на клетке кто-то стоит — бьёт в него
            center = (int(g[0]), int(g[1]))
            tgt = next((w for w in self.view.combat.units if w.alive and w.cell == center and w is not u
                        and not w.obj), None)
        s = 1.0 + 0.14 * tier
        cells = {pos for _, pos in self._area(ctx)} | {(int(g[0]), int(g[1]))}
        if fam == "fire":                                # клетки и юниты площади загорятся, когда долетит
            S.hold_cells(cells, 3.0)
        # статус и заморозку симуляция ставит при касте — на фигурке они появятся по прилёте
        S.hold_units([w for w in self.view.combat.units if w.cell in cells or w is tgt], 3.0)
        if tr.get("from") == "sky":                      # метеор: падает сверху-сзади по крутой прямой
            b = (g[0], g[1], 0.0)
            a = (g[0] - 1.4, g[1] - 2.2, 7.5)
            area = self._area(ctx)
            return S.comet(a, b, "fire_big", lambda p, d: S.fire_hit_ground(p, d, area, big=True, radius=radius),
                           speed=15, scale=(1.8 + 0.2 * radius) * s)
        dart = (tr.get("speed", 0) or 0) >= 1400        # «огненные дротики» — быстрые и мелкие
        aim = self.view.ground_pos(tgt) if tgt is not None else g
        a = S.hand(u, aim)
        if fam == "fire":
            if tgt is not None:
                b = S.contact(a, tgt)
                area = self._area(ctx, skip=tgt.cell) if radius else ()
                cell = tgt.cell

                def hit(p, d):
                    S.release(cell)                      # цель и клетка под ней вспыхивают в момент удара
                    S.fire_hit_unit(p, d, area, s * (0.7 if dart else 1.0), radius)
                S.muzzle(a, b, "fire", s)
                return S.comet(a, b, "fire", hit, speed=13 if dart else 7,
                               scale=(1.0 if dart else 1.7 + 0.3 * radius) * s)
            area = self._area(ctx, skip=(int(g[0]), int(g[1]))) if radius else ()
            S.muzzle(a, (g[0], g[1], 0.0), "fire", s)
            return S.comet(a, (g[0], g[1], 0.0), "fire", lambda p, d: S.fire_hit_ground(p, d, area, radius=radius),
                           speed=7, scale=(1.7 + 0.3 * radius) * s)
        area = self._area(ctx) if radius else ()
        if tgt is not None:
            b = S.contact(a, tgt)

            def hit(p, d):
                S.release(tgt.cell)
                S.ice_hit_unit(p, d, tgt, s, radius)
                if area:
                    S.ice_hit_ground((p[0], p[1], 0.0), d, area)
            S.muzzle(a, b, "ice", s)
            return S.comet(a, b, "ice", hit, speed=12, scale=1.8 * s)
        return S.comet(a, (g[0], g[1], 0.0), "ice", lambda p, d: S.ice_hit_ground(p, d, area), speed=12,
                       scale=1.8 * s)

    def impact(self, fam, impact, ctx, radius, tier, sk=None):
        V, X = self.view.vfx, self.fx
        g = ctx.get("target_ground") or ctx.get("target")
        pts = ctx.get("cells") or [g]
        tgt = ctx.get("target_unit")
        sz = 1.0 + 0.14 * tier
        if sk and not any(e.get("type") in AREA_EFFECTS for e in sk.get("effects", [])):
            # стена, каток, раздуть, вспышка: виден сам результат (стена, лёд, пламя клеток) — тут только всплеск
            if fam == "fire":
                self._at("blast_s", g, lift=0.3, scale=sz)
            self._light((g[0], g[1] - 16), FIRE_LIGHT if fam == "fire" else ICE_LIGHT, 100, 0.9, 0.4)
            return
        if fam == "fire":
            meteor = "meteor" in impact
            name = "blast_l" if (meteor or radius >= 1) else "blast_m"
            self._at(name, g, lift=0.3, scale=sz * (1.35 if meteor or radius >= 2 else 1.0))
            for p in pts:
                d = math.dist(p, g)
                if d > 4:
                    self._at("blast_s", p, lift=0.3, delay=0.05 + d / 1600)
                if d <= 4 or X.rng.random() < 0.5:
                    self._stamp("scorch", p, 1.0 if d <= 4 else 0.7, 200 if d <= 4 else 140)
            if meteor or radius >= 2:
                self._stamp("scorch_big", g)
                self._at("smoke", g, lift=0.6, delay=0.35, scale=1.4)
            if "shrapnel" in impact:
                self._at("shatter", g, lift=0.4, scale=1.2)
            self._light((g[0], g[1] - 20), FIRE_LIGHT, 130 + 60 * radius, 1.4, 0.55)
            V.screen_fx(shake=3 + 3 * radius + (6 if meteor else 0), flash=0.12 if meteor else 0.0,
                        color=FIRE_LIGHT)
            return
        # лёд
        if "prison" in impact and tgt is not None:
            self.prison(tgt, 1.6)
        if radius == 0 and tgt is not None:
            p = self.view.feet_pos(tgt)
            self._at("bloom_s", p, lift=0.9, scale=sz * 1.3)
            self._at("chip", p, lift=1.0, delay=0.1)
        else:                                    # одна снежинка на заклинание, шипы — не по клеткам, один иней
            c = P.unproject(*g)
            if c is not None:
                self._ice_area(c[0], c[1], radius + 0.5, sz)
        self._light((g[0], g[1] - 16), ICE_LIGHT, 110 + 50 * radius, 0.9, 0.6)
        V.screen_fx(shake=2 + 2 * radius)

    def _ice_area(self, x, y, R, s=1.0, spikes=True):
        """Лёд по площади (кроме Бурана): одна большая снежинка в центре, шипы в случайных местах площади,
        один морозный след."""
        S = self.spells
        S.big_snowflake(x, y, R)
        if spikes:
            S._ice_spikes(x, y, R, s)
        from ui.pixmarks import scar
        m = scar(x, y, R, S.terrain_at, (0.0, 0.0), (), seed=int(x * 31 + y * 17), crater=0.0, style="frost")
        if m is not None:
            self.fx.add_surface(m[0], m[1], ttl=6.0, fade=2.0)
        S._mist((x, y, 0.1), int(20 * R))

    def own_release(self, sid):
        """Старый эффект выпуска навыка не нужен: эти навыки целиком нарисованы пилотом."""
        return self.on and sid in ("flashpoint", "blizzard")

    def cast_area(self, u, sid, sk, alive):
        """Каст по площади: Буран — над целью сгущается туча. True — нарисовано."""
        if not self.on or sid != "blizzard" or sk.get("target") != "cell" or u.cast is None:
            return False
        tgt = u.cast.get("target")
        if not isinstance(tgt, tuple):
            return False
        self.spells.storm_cloud(tgt[0] + 0.5, tgt[1] + 0.5, sk.get("radius", 1) + 0.5, alive)
        return True

    def cast_orb(self, u, sk, head, alive, tier):
        """Копящаяся сила над головой при касте огня или льда. True — нарисовано (старая сфера не нужна)."""
        fam = family(sk)
        if not self.on or fam is None:
            return False
        feet = (lambda: self.view.feet_pos(u))
        if fam == "fire":
            self.fx.add("orb_big", head, alive=alive, scale=1 + 0.15 * tier, depth=lambda: feet()[1] + 1)
            return True
        S = self.spells                          # лёд: холод стягивается к руке — крупинки инея и дымка

        def step(dt):
            if not alive():
                return False
            gx, gy = self.view.ground_pos(u)
            k = S.rng.poisson(40 * dt) + 1
            a = S.rng.uniform(0, math.tau, k)
            r = S.rng.uniform(0.35, 0.6, k)
            S.ps.spawn(k, (gx + np.cos(a) * r, gy + np.sin(a) * r * 0.6, S.rng.uniform(0.4, 1.2, k)),
                       (-np.cos(a) * r * 2.2, -np.sin(a) * r * 1.3, np.full(k, 0.5)), life=0.42,
                       temp=S.rng.uniform(0.6, 1.0, k), drag=0.5, pal="ice", smoke=None, life_var=0.1)
            return True
        S.emitters.append(step)
        return True

    def prison(self, u, ttl):
        """Ледяная глыба вокруг цели (Ледяная тюрьма, заморозка реакцией)."""
        view = self.view
        self.fx.add("crust", lambda: view.feet_pos(u), ttl=ttl, alive=lambda: u.alive, anchor="bottom",
                    depth=lambda: view.feet_pos(u)[1] + 1, scale=1.1, alpha=215)

    # ---------- события ----------

    def event(self, e):
        """Пиксельный вид события. True — старый эффект этого события не играть."""
        if not self.on:
            return False
        t = e["t"]
        view = self.view
        if t == "damage":
            tag = e.get("tag")
            if tag not in ("fire", "ice"):
                return False
            if e["kind"] in ("dot", "hazard"):
                return tag == "fire"         # горение видно пламенем на фигурке — искры не нужны
            if e["kind"] in ("melee", "ranged", "spell"):
                self.spells.sparks(self.spells.unit_point(e["unit"]), tag == "fire")
                return True
            return False
        if t == "status" and e["tag"] in ("fire", "ice"):
            p = view.feet_pos(e["unit"])
            if e["tag"] == "fire":
                if not self.spells.unit_held(e["unit"]):
                    self.spells.catch_fire(e["unit"])
            return True                          # лёд на юните виден коркой на ногах — снежинки нет
        if t == "reaction":
            return self._reaction(e)
        if t == "detonate":
            if not self._deto:
                view.vfx.after(0.001, self._flash_point)
            pos = e["pos"]
            torch = next((u for u in view.combat.units if u.alive and not u.obj and u.cell == pos
                          and "fire" in u.statuses), None)
            self._deto.append((pos, e.get("src"), torch))     # клетка пожара или горящий враг
            return True
        if t == "mine":
            gp = T.cell_feet(e["pos"])
            self._at("blast_s", gp, lift=0.3, scale=1.3)
            self._stamp("scorch", gp)
            self._light((gp[0], gp[1] - 16), FIRE_LIGHT, 110, 1.2, 0.4)
            return True
        if t == "object_break" and e["unit"].obj.get("id") == "ice_wall":
            self.wall_break(e["unit"])
            return True
        if t == "object_break":
            eff = e.get("fx") or {}
            if not eff.get("damage") or eff.get("tag") not in (None, "fire"):
                return False
            u = e["unit"]
            gp = T.cell_feet(u.cell)
            r = eff.get("radius", 0)
            self._at("blast_l" if r >= 1 else "blast_m", gp, lift=0.3)
            for p in view._cells_around(u.cell, r) if r else []:
                cp = T.cell_feet(p)
                self._stamp("scorch", cp)
                if p != u.cell:
                    self._at("blast_s", cp, lift=0.3, delay=0.06 + math.dist(cp, gp) / 1500)
            self._stamp("scorch_big", gp)
            self._at("smoke", gp, lift=0.6, delay=0.3, scale=1.3)
            self._light((gp[0], gp[1] - 20), FIRE_LIGHT, 170 + 50 * r, 1.6, 0.6)
            view.vfx.screen_fx(shake=8 + 2 * r)
            return True
        if t == "cell_reaction" and e["tag"] in ("fire", "ice"):
            gp = T.cell_feet(e["pos"])
            if e["tag"] == "fire":
                self._at("blast_s", gp, lift=0.3)
            else:                                # вода замёрзла: наледь (IceField) и пар, без снежинки
                g = P.unproject(*gp)
                if g is not None:
                    self.spells._steam((g[0], g[1], 0.05), 6)
            return True
        if t == "terrain" and e["terrain"] == "ice_floor" and e["cells"]:
            xs = [p[0] + 0.5 for p in e["cells"]]
            ys = [p[1] + 0.5 for p in e["cells"]]
            cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
            R = max(math.hypot(x - cx, y - cy) for x, y in zip(xs, ys)) + 0.5
            self._ice_area(cx, cy, R, 1.0, spikes=False)       # каток: одна снежинка и иней, без шипов
            return True
        if t == "terrain" and e["terrain"] in ("lava", "ice_floor"):
            for i, p in enumerate(e["cells"]):
                gp = T.cell_feet(p)
                if e["terrain"] == "lava":
                    self._at("flame_pillar", gp, anchor="bottom", delay=0.05 * i)
                    self._stamp("scorch", gp)
                else:
                    self._at("bloom_s", gp, lift=0.3, delay=0.04 * i)
                    self._frost(gp, 3.0)
            return True
        if t == "shatter":
            self._at("shatter", view.feet_pos(e["unit"]), lift=0.8, scale=1.3)
            view.vfx.screen_fx(shake=4)
            return True
        if t == "wall":
            return False                       # стена растёт сама (draw_object), подпись остаётся
        if t == "frost_armor":
            self._at("bloom_s", view.feet_pos(e["unit"]), lift=0.9)
            return True
        return False

    def _reaction(self, e):
        tags = set(e["tags"])
        if e.get("friendly"):                 # теги погасили друг друга (святая вода по горящему) — пар
            if tags & {"fire", "ice"}:
                self._at("steam", self.view.feet_pos(e["unit"]), lift=0.9)
            return False
        rid = e["id"]
        if rid not in FIRE_REACTIONS:
            return False
        p = self.view.feet_pos(e["unit"])
        if rid == "melt":
            self._at("steam", p, lift=1.0, scale=1.2)
            self._at("spark", p, lift=0.9, scale=1.3)
        elif rid == "steam":
            self._at("steam", p, lift=0.9, scale=1.6)
            self._at("steam", (p[0] + 20, p[1]), lift=0.9, delay=0.12)
            self._at("steam", (p[0] - 20, p[1]), lift=0.9, delay=0.2)
        elif rid == "freeze":
            self._at("bloom_m", p, lift=0.5)
        elif rid == "blaze":
            self._at("flame_pillar", p, anchor="bottom", scale=1.3)
            self._at("blast_s", p, lift=0.5, delay=0.1)
            self._light((p[0], p[1] - 30), FIRE_LIGHT, 150, 1.5, 0.7)
        elif rid == "shatter":
            self._at("shatter", p, lift=0.8, scale=1.5)
        elif rid == "overload":
            self._at("blast_m", p, lift=0.4)
        elif rid == "toxic":
            self._at("blast_s", p, lift=0.5)
            self._at("smoke", p, lift=0.7, delay=0.15)
        self.view.vfx.screen_fx(shake=5)
        return True

    def arena(self, kind, pts):
        """Событие поля: извержение — взрывы с подпалинами, лавина — ледяные шипы. True — нарисовано."""
        if not self.on or kind not in ("eruption", "avalanche"):
            return False
        for i, p in enumerate(pts):
            if kind == "eruption":
                self._at("flame_pillar", p, anchor="bottom", delay=0.03 * i)
                self._at("blast_m", p, lift=0.3, delay=0.03 * i + 0.1)
                self._stamp("scorch", p)
            else:
                self._at("spikes_big", p, anchor="bottom", delay=0.04 * i)
                self._frost(p)
        if pts:
            self._light((pts[0][0], pts[0][1] - 20), FIRE_LIGHT if kind == "eruption" else ICE_LIGHT, 160, 1.2, 0.6)
        self.view.vfx.screen_fx(shake=6)
        return True

    # ---------- Вспышка: взрывается вся горящая поверхность ----------

    def _flash_point(self):
        """Все детонации этого кадра — одна Вспышка: цепная волна от мага наружу, каждая горящая клетка выбрасывает
        стену пламени всей своей площадью, от края пятна — ударная волна; горящие враги рвутся изнутри; в конце —
        одна выжженная земля по форме пожара."""
        items, self._deto = self._deto, []
        if not items:
            return
        S, V = self.spells, self.view.vfx
        src = items[0][1]
        sx, sy = (src.cell[0] + 0.5, src.cell[1] + 0.5) if src is not None else (items[0][0][0] + 0.5,
                                                                               items[0][0][1] + 0.5)
        # одна позиция может прийти дважды: как клетка пожара и как горящий враг на ней
        surface = {}
        for p, _, torch in items:
            surface.setdefault(p, [False, None])
            if torch is None or p in self.burning:
                surface[p][0] = True
            if torch is not None:
                surface[p][1] = torch
        cells = {p for p, (surf, _) in surface.items() if surf}
        last = 0.0
        for p in sorted(surface, key=lambda q: math.hypot(q[0] + 0.5 - sx, q[1] + 0.5 - sy)):
            d = 0.05 + math.hypot(p[0] + 0.5 - sx, p[1] + 0.5 - sy) * 0.055
            last = max(last, d)
            surf, torch = surface[p]
            V.after(d, lambda p=p, surf=surf, torch=torch: self._erupt(p, cells, torch, surf))
        if cells:
            def scar():
                from ui.pixmarks import area_scar
                m = area_scar(sorted(cells), S.terrain_at, seed=len(cells) * 7 + int(sx * 13))
                if m is not None:
                    img, (fx, fy) = m
                    self.view.marks.stamp_surface(img, fx, fy)
            V.after(last + 0.15, scar)
            n = len(cells)
            V.after(0.05, lambda: V.screen_fx(shake=4 + min(10, n * 0.8), hitstop=0.05, flash=0.08,
                                              color=FIRE_LIGHT))

    def _erupt(self, p, cells, unit, surface):
        S = self.spells
        cx, cy = p
        if surface:
            n = 70                                    # вспышка по всей площади клетки — у самой земли
            S.ps.spawn(n, (cx + S.rng.random(n), cy + S.rng.random(n), S.rng.uniform(0.02, 0.3, n)), life=0.09,
                       temp=1.0, cool=0.0, size=2.0, pal="fire", smoke=None, life_var=0.2)

            def wall(dt, f):                          # стена пламени бьёт вверх из всей площади
                k = int(dt * 1000 * (1 - 0.6 * f)) + 1
                S.ps.spawn(k, (cx + S.rng.random(k), cy + S.rng.random(k), np.full(k, 0.05)),
                           (0, 0, S.rng.uniform(3.5, 6.5, k)), life=0.6, temp=S.rng.uniform(0.9, 1.0, k), cool=1.5,
                           buoy=1.4, drag=2.2, size=1.6, grow=-0.8, tall=2.0, pal="fire", smoke="dust", smoke_at=0.2,
                           jitter=0.04)
            S.emitter(0.32, wall)
            for (dx, dy) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (cx + dx, cy + dy) in cells:
                    continue                          # внутренняя граница — волны нет, пятно одно
                k = 22                                # ударная волна от края пятна наружу
                t = S.rng.random(k)
                ex = cx + 0.5 + dx * 0.5 + (t - 0.5) * (dy != 0)
                ey = cy + 0.5 + dy * 0.5 + (t - 0.5) * (dx != 0)
                S.ps.spawn(k, (ex, ey, np.full(k, 0.05)), (dx * 4.5, dy * 4.5, np.full(k, 0.4)), life=0.3,
                           temp=0.85, cool=2.6, drag=5.0, size=1.2, pal="fire", smoke=None, spread=0.6)
                S.ps.spawn(k // 2, (ex[::2], ey[::2], np.full(k // 2, 0.05)), (dx * 5, dy * 5, np.full(k // 2, 0.3)), life=0.7,
                           temp=0.0, drag=3.5, size=1.4, grow=1.2, alpha=0.6, pal="dust", smoke="dust", smoke_at=1.0,
                           spread=0.4)
            S._smoke((cx + 0.5, cy + 0.5, 0.6), 6, life=1.6, buoy=1.2)
            self._light(P.project(cx + 0.5, cy + 0.5, 0.3)[:2], FIRE_LIGHT, 140, 1.5, 0.35)
        if unit is not None:                          # горящий враг рвётся изнутри
            S._burst(S.unit_point(unit), (0.0, 0.0, 1.0), 0.9)

    # ---------- ледяная стена: обрыв ледника ----------

    def _walls(self):
        """Живые ледяные стены → отрезки (ось, клетки); для каждой глыбы — её отрезок. Пересчёт раз в кадр."""
        c = self.view.combat
        key = (self.time, len(c.units), sum(u.alive for u in c.units if u.obj))
        if self._wall_key == key:
            return self._wall_map
        self._wall_key = key
        units = {u.cell: u for u in c.units if u.alive and u.obj and u.obj.get("id") == "ice_wall"}
        m = {}
        for axis, run in M.runs(list(units)):
            side = 1 if run[0][0] + 0.5 >= P.CX else -1          # стена вглубь поля — лицом к центру доски
            variant = (run[0][0] * 7 + run[0][1] * 3 + len(run)) % 3
            lead = run[-1] if axis == "y" else run[0]            # рисуется вместе с ближней к камере глыбой
            for i, p in enumerate(run):
                m[units[p].id] = (axis, run, i, side, variant, units[lead].id, [units[q] for q in run])
        self._wall_map = m
        return m

    def _wall_grow(self, u):
        """Рост из земли за 0.4 сек, в последние 1.2 сек срока — тает и оседает."""
        born = self._born.setdefault(u.id, self.time)
        g = min(1.0, (self.time - born) / 0.4)
        g = g * g * (3 - 2 * g)
        if u.life is not None:
            g *= min(1.0, max(0.0, u.life / 1.2))
        return g

    def draw_object(self, surf, u):
        """Объект поля в пиксельном виде. Возвращает прямоугольник (для клика) или None — рисует старый вид."""
        if not self.on or not u.obj or u.obj.get("id") != "ice_wall":
            return None
        w = self._walls().get(u.id)
        if w is None:
            return None
        axis, run, i, side, variant, lead, units = w
        self._wall_events(u, axis, run, i)
        if u.id != lead:                         # стену целиком рисует ближняя глыба — эта только кликается
            r = self._wall_rects.get(tuple(run))
            return r.copy() if r is not None else pygame.Rect(0, 0, 0, 0)
        g = min(self._wall_grow(w) for w in units)
        sink = M.data()["height"] * 1.05 * (1 - g)
        key = (tuple(run), variant, side, round(sink * 30), P.view_key())
        hit = self._wall_cache.get(key)
        if hit is None:
            if len(self._wall_cache) > 120:
                self._wall_cache.clear()
            hit = self._wall_cache[key] = M.wall(axis, run, variant, side, sink)
        if hit is None:
            return pygame.Rect(0, 0, 0, 0)
        img, (x, y) = hit
        if any(self.view.anim(q).hit > 0 for q in units):        # удар: стена вздрагивает
            x += math.sin(self.view.clock * 90) * 1.5
        surf.blit(img, (round(x), round(y)))
        r = pygame.Rect(round(x), round(y), img.get_width(), img.get_height())
        self._wall_rects[tuple(run)] = r
        return r

    def _wall_events(self, u, axis, run, i):
        """Рождение: трещина вдоль линии и выброс снега; урон — откалываются куски."""
        S = self.spells
        cx, cy = run[i][0] + 0.5, run[i][1] + 0.5
        if u.id not in self._born:
            self._born[u.id] = self.time
            ax = (1.0, 0.0) if axis == "x" else (0.0, 1.0)
            n = 40
            t = S.rng.uniform(-0.5, 0.5, n)
            S.ps.spawn(n, (cx + ax[0] * t, cy + ax[1] * t, np.full(n, 0.05)), (0, 0, 2.5), life=0.9,
                       temp=S.rng.uniform(0.6, 1.0, n), grav=7.0, drag=1.0, pal="ice", smoke=None, spread=1.2,
                       land=DIE)
            S.ps.spawn(24, (cx, cy, 0.1), (0, 0, 0.4), life=1.4, temp=0.0, buoy=0.3, drag=2.0, size=1.6, grow=1.4,
                       alpha=0.7, pal="steam", smoke="steam", smoke_at=1.0, spread=0.8, jitter=0.25)
            self.view.vfx.screen_fx(shake=2.5)
        hp = self._wall_hp.get(u.id, u.hp)
        if u.hp < hp:                            # откололось: куски льда и крошка с фасада
            k = 10 + int((hp - u.hp) / max(1, u.max_hp) * 30)
            front = (0.0, 0.32) if axis == "x" else (0.32 if cx >= P.CX else -0.32, 0.0)
            S.ps.spawn(k, (cx + S.rng.uniform(-0.4, 0.4), cy + front[1], S.rng.uniform(0.4, 1.1)),
                       (front[0] * 4, front[1] * 4, 1.0), life=1.4, temp=S.rng.uniform(0.45, 0.95, k), grav=9.0,
                       bounce=0.35, size=1.0, pal="ice", smoke=None, spread=1.2, land=BOUNCE)
        self._wall_hp[u.id] = u.hp

    def wall_break(self, u):
        """Стену разбили: кусок раскалывается на глыбы — они падают и раскатываются (раскол из Blender), тают;
        оседает облако снежной пыли."""
        S = self.spells
        if u.life is not None and u.life <= 0.05:     # срок вышел: стена уже осела и растаяла — лужа и пар
            S._steam((u.cell[0] + 0.5, u.cell[1] + 0.5, 0.05), 14)
            return
        w = self._wall_map.get(u.id)
        axis, side, variant = (w[0], w[3], w[4]) if w else ("y", 1 if u.cell[0] + 0.5 >= P.CX else -1, 0)
        self._breaks.append([u.cell, axis, side, variant, self.time])
        x, y = u.cell[0] + 0.5, u.cell[1] + 0.5
        n = 24
        a = S.rng.uniform(0, math.tau, n)
        sp = S.rng.uniform(1.0, 3.0, n)
        S.ps.spawn(n, (x, y, S.rng.uniform(0.2, 1.2, n)), (np.cos(a) * sp, np.sin(a) * sp, S.rng.uniform(0.5, 3, n)),
                   life=1.4, temp=S.rng.uniform(0.4, 1.0, n), grav=9.0, bounce=0.3, pal="ice", smoke=None,
                   land=BOUNCE)
        S.ps.spawn(36, (x, y, 0.5), (0, 0, 0.2), life=1.8, temp=0.0, grav=0.2, drag=2.0, size=1.8, grow=1.5,
                   alpha=0.7, pal="steam", smoke="steam", smoke_at=1.0, spread=0.9, jitter=0.35)
        self.view.vfx.screen_fx(shake=5, hitstop=0.04)

    def _break_items(self):
        """Раскалывающиеся куски стены: кадр по траекториям Blender, после — глыбы лежат и тают (0.8 сек)."""
        out = []
        frames, fps = M.break_frames()
        keep = []
        for b in self._breaks:
            cell, axis, side, variant, t0 = b
            age = self.time - t0
            if age > frames / fps + 0.8:
                continue
            keep.append(b)
            f = min(frames - 1, int(age * fps))
            fade = max(0.0, 1 - max(0.0, age - frames / fps) / 0.8)
            out.append((P.project(cell[0] + 0.5, cell[1] + 0.9)[1], 1, "pix",
                        (self._draw_break, (cell, axis, side, variant, f, fade))))
        self._breaks = keep
        return out

    def _draw_break(self, surf, cell, axis, side, variant, f, fade):
        key = ("break", cell, axis, side, variant, f, P.view_key())
        hit = self._wall_cache.get(key)
        if hit is None:
            hit = self._wall_cache[key] = M.wall_break(axis, cell, side, variant, f)
        if hit is None:
            return
        img, (x, y) = hit
        if fade < 1:
            img.set_alpha(int(255 * fade * self._dim()))
            surf.blit(img, (round(x), round(y)))
            img.set_alpha(255)
        else:
            surf.blit(img, (round(x), round(y)))

    # ---------- кадр ----------

    def begin_frame(self, gl):
        """Перед рисованием мира: свечение — только с OpenGL; очищаем, если в прошлом кадре на нём что-то было."""
        self.glow_used = bool(gl and self.on)
        if not self.glow_used:
            return
        if self.glow is None or self.glow.get_size() != (T.SCREEN_W, T.SCREEN_H):
            self.glow = pygame.Surface((T.SCREEN_W, T.SCREEN_H), pygame.SRCALPHA)
        elif self.glow_dirty:
            self.glow.fill((0, 0, 0, 0))
        self.glow_dirty = False

    def glow_layer(self):
        return self.glow if self.glow_used and self.glow_dirty else None

    def _glow(self):
        if not self.glow_used:
            return None
        self.glow_dirty = True
        return self.glow

    def _dim(self):
        return 1.0 - 0.45 * self.view.vfx.screen.calm   # пауза: эффекты прозрачнее, поле видно

    def ground(self, flat, c):
        """Плоская карта: горящая поверхность, иней на ледяных клетках, наземные экземпляры."""
        if not self.on:
            return
        self.ice.draw(flat)                    # ледяные клетки — одна корка, а не иней на каждой клетке
        self.fire.draw(flat)
        self.fx.draw_ground(flat)

    def world_items(self, c):
        """Что встаёт в общий порядок глубины с юнитами: пламя горящих клеток и воздушные экземпляры."""
        if not self.on:
            return []
        items = []
        self.burning = {pos for pos, cell in c.grid.cells.items() if cell.hazard == "fire"}
        self.burning_units = {u.id for u in c.units if "fire" in u.statuses and not self.spells.unit_held(u)}
        for fx in self.fx.air():
            items.append((fx.ground_y(), 2, "pix", (self._draw_fx, (fx,))))
        items += self._break_items()
        if self.spells.ps.prepare(self._dim()):
            for y, part in self.spells.ps.buckets():
                items.append((y, 2, "pix", (self._draw_parts, (part,))))
        return items

    def _draw_parts(self, surf, part):
        self.spells.ps.draw(surf, self._glow(), part)

    def _draw_fx(self, surf, fx):
        self.fx.draw(surf, self._glow(), fx, self._dim())

    def _flamelets(self, surf, glow, u, rect, k, dim):
        """Огоньки по модельке: маленькие язычки пламени на корнях с контура и тела, ползут и мерцают."""
        n = self.fx.lib.count("flamelet")
        for i, (nx, ny, left) in enumerate(self._unit_src.get(u.id, ())):
            grow = min(1.0, left * 2.5)        # корень гаснет — язычок опадает
            frame = (int(self.time * FPS) + i * 3 + u.id) % n
            self.fx.blit(surf, glow, "flamelet", u.id + i, frame, rect.x + nx * rect.w, rect.y + ny * rect.h + 3,
                         k * (0.75 + 0.35 * grow), "bottom", int(240 * dim))

    def on_unit(self, surf, u, rect, look, k):
        """Поверх фигурки: корка на ногах у охлаждённого, глыба у вмороженного (огонь — частицы, см. _burn).
        True — заморозку нарисовали здесь (старый полупрозрачный блок не нужен)."""
        if not self.on:
            return False
        dim = self._dim()
        glow = self._glow()
        if "fire" in u.statuses and not self.spells.unit_held(u):
            self._flamelets(surf, glow, u, rect, k, dim)
        if self.spells.unit_held(u):           # лёд ещё летит: ни глыбы, ни корки
            return look == "freeze"
        if look == "freeze":
            self.fx.blit(surf, glow, "crust", u.id, (int(self.time * FPS) // 2) % 6, rect.centerx, rect.bottom + 4,
                         max(k, rect.h * 1.08 / 68), "bottom", int(215 * dim))
            return True
        if "ice" in u.statuses:            # охлаждён: лёд по колено
            old = surf.get_clip()
            clip = pygame.Rect(rect.x - 20, rect.bottom - rect.h * 0.38, rect.w + 40, rect.h * 0.38 + 8)
            surf.set_clip(clip)
            self.fx.blit(surf, None, "crust", u.id, 0, rect.centerx, rect.bottom + 4, max(k, rect.h / 68), "bottom",
                         int(165 * dim))
            surf.set_clip(old)
        return False
