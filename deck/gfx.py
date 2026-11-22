"""Вывод «Спуска» в родном разрешении экрана.

Сцены рисуют в логических координатах 1280×800, как и раньше, но на «холст» (Canvas) — он не хранит пиксели
сам, а пересчитывает всё в настоящее окно: координаты ×S со сдвигом (поле по центру), текст рисуется заново
шрифтом ×S (не растягивается), панели темы и примитивы pygame.draw — тоже в полном разрешении, карты — из
своего лица высокого разрешения. Поле боя с пиксельными фигурками рисуется в обычный логический кадр и
растягивается целиком (пиксель-арт от этого не портится).

Использование: with native(canvas): scene.draw(canvas) — на время кадра подменяются pygame.draw.*, T.text,
T.frame (для чужих, обычных поверхностей всё работает как было). Мышь — to_logical(pos).
"""
import contextlib
import math

import pygame

from ui import theme as T

LW, LH = 1280, 800
_rot = {}


class Canvas(pygame.Surface):
    """Логический холст 1280×800 поверх настоящего окна native: S — масштаб, (ox, oy) — сдвиг."""

    BUDGET = 3                         # сглаженных перерисовок карт за кадр (остальные — дёшево, до остановки)

    def __init__(self, native):
        super().__init__((1, 1), pygame.SRCALPHA)
        self.native = native
        self.LW, self.LH = LW, LH
        w, h = native.get_size()
        self.S = min(w / self.LW, h / self.LH)
        self.ox = (w - self.LW * self.S) / 2
        self.oy = (h - self.LH * self.S) / 2
        self.pixel = False             # мир с пиксельными фигурками: всё увеличивать ближайшими пикселями
        self._tick, self._turns = -1, 0  # дорогие повороты карт за кадр (blit_hd)
        self._pxtick, self._seen, self._seen_new = -1, set(), set()
        self._px = {}                  # готовые увеличения: (id картинки, размер) → (картинка, увеличенная)

    def set_layout(self, lw, lh):
        """Сменить логическую ширину сцены (широкий экран) и заново вписать её в окно."""
        self.LW, self.LH = max(1, int(lw)), max(1, int(lh))
        w, h = self.native.get_size()
        self.S = min(w / self.LW, h / self.LH)
        self.ox = (w - self.LW * self.S) / 2
        self.oy = (h - self.LH * self.S) / 2

    def reset_layout(self):
        self.set_layout(LW, LH)

    # --- пересчёт ---
    def pt(self, p):
        return (self.ox + p[0] * self.S, self.oy + p[1] * self.S)

    def rect(self, r):
        r = pygame.Rect(r)
        x, y = self.pt(r.topleft)
        return pygame.Rect(round(x), round(y), max(1, round(r.w * self.S)), max(1, round(r.h * self.S)))

    def n(self, v):
        return v * self.S

    def w(self, v):
        return 0 if not v else max(1, round(v * self.S))

    def content(self):
        return self.rect((0, 0, self.LW, self.LH))

    # --- поверхность ---
    def get_size(self):
        return (self.LW, self.LH)

    def get_width(self):
        return self.LW

    def get_height(self):
        return self.LH

    def get_rect(self, **kw):
        return pygame.Rect(0, 0, self.LW, self.LH)

    def blit_world(self, src):
        """Кадр поля 1280×800 — растянуть целиком (быстро; пиксель-арт остаётся пиксельным)."""
        r = self.content()
        self.native.blit(pygame.transform.scale(src, r.size), r.topleft)

    def blit(self, src, dest, area=None, special_flags=0):
        if area is not None:
            src = src.subsurface(area)
        pos = dest.topleft if isinstance(dest, pygame.Rect) else dest
        w, h = src.get_size()
        tw, th = max(1, round(w * self.S)), max(1, round(h * self.S))
        if self.pixel:                                # мир: пиксель-арт ×S ближайшими, повторы — из кэша
            key = (id(src), tw, th)
            hit = self._px.get(key)
            if hit is None or hit[0] is not src:
                tick = pygame.time.get_ticks()
                if tick != self._pxtick:                # кадр сменился: что видели в прошлом — «знакомое»
                    self._pxtick, self._seen, self._seen_new = tick, self._seen_new, set()
                img = pygame.transform.scale(src, (tw, th))
                self._seen_new.add(key)
                if key in self._seen:                   # встречается кадр за кадром — запомнить; разовые
                    if len(self._px) > 1500:            # (дыхание фигурки) кэш не забивают
                        self._px.clear()
                    self._px[key] = (src, img)
                hit = (src, img)
            x, y = self.pt(pos)
            return self.native.blit(hit[1], (round(x), round(y)), special_flags=special_flags)
        small = max(w, h) <= 96                       # пиксельные значки — без размытия
        img = pygame.transform.scale(src, (tw, th)) if small else pygame.transform.smoothscale(
            src.convert_alpha() if src.get_bitsize() != 32 else src, (tw, th))
        x, y = self.pt(pos)
        return self.native.blit(img, (round(x), round(y)), special_flags=special_flags)

    def blit_card3d(self, img, center, angle=0.0, scale=1.0, tilt=(0.0, 0.0), alpha=255):
        """Карта, повёрнутая в 3D (как настоящая): tilt (x, y) −1…1 — край под мышью уходит вглубь, с перспективой
        и светом; angle — ещё и поворот в плоскости. Рисуется прямо в родное разрешение."""
        tx, ty = tilt
        if abs(tx) + abs(ty) < 0.02:
            return self.blit_hd(img, center, angle, scale, alpha)
        q = 20                                               # шаг наклона в кэше — 1/20 (≈1.2°)
        key = (id(img), round(tx * q), round(ty * q), round(angle * 2), round(scale * self.S, 3))
        hit = _warps.get(key)
        if hit is not None and hit[0] is img:
            out = hit[1]
        else:
            out, _ = warp_card(img, (0, 0), angle, scale * self.S, round(tx * q) / q, round(ty * q) / q)
            if len(_warps) > 120:
                _warps.clear()
            _warps[key] = (img, out)
        if out is None:
            return None
        x, y = self.pt(center)
        pos = (round(x - out.get_width() / 2), round(y - out.get_height() / 2))
        if alpha < 255:
            out = out.copy()
            out.set_alpha(alpha)
        self.native.blit(out, pos)
        return out

    def blit_hd(self, img, center, angle=0.0, scale=1.0, alpha=255):
        """Картинка высокого разрешения (лицо карты): масштаб scale — в логических единицах, без промежуточного
        уменьшения — сразу в родное разрешение. Готовые масштабы и повороты — из кэша (шаг 1% и 1°); новых
        дорогих (сглаженных) — не больше BUDGET за кадр: сверх него карта в движении рисуется дёшево, а чисто —
        как только остановится (тогда её размер и угол уже в кэше)."""
        k = round(scale * self.S, 2)
        key = (id(img), float(round(angle)), k)
        out = _rot.get(key)
        if out is None or out[0] is not img:
            tick = pygame.time.get_ticks()
            if tick != self._tick:                          # новый кадр — бюджет заново
                self._tick, self._turns = tick, 0
            size = (max(1, round(img.get_width() * k)), max(1, round(img.get_height() * k)))
            if self._turns >= self.BUDGET:                  # в движении — дёшево и без запоминания
                cheap = pygame.transform.scale(img, size)
                res = pygame.transform.rotate(cheap, key[1]) if key[1] else cheap
            else:
                self._turns += 1
                res = pygame.transform.rotozoom(img, key[1], k) if key[1] else pygame.transform.smoothscale(img, size)
                if len(_rot) > 400:
                    _rot.clear()
                _rot[key] = (img, res)
            out = (img, res)
        out = out[1]
        if alpha < 255:
            out = out.copy()
            out.set_alpha(alpha)
        x, y = self.pt(center)
        self.native.blit(out, (round(x - out.get_width() / 2), round(y - out.get_height() / 2)))
        return out

    def fill(self, color, rect=None, special_flags=0):
        return self.native.fill(color, self.rect(rect) if rect is not None else None, special_flags)   # фон — на всё окно

    def set_clip(self, rect=None):
        self.native.set_clip(self.rect(rect) if rect is not None else None)

    def get_clip(self):
        return pygame.Rect(0, 0, self.LW, self.LH)

    def copy(self):
        return self.native.copy()


MAX_TILT = 24.0          # наибольший поворот карты в 3D, градусов


STRIP = 6                # ширина полосы перспективы, пикселей
_warps = {}              # готовые повороты: (лицо, наклон, угол, масштаб) → картинка


def warp_card(img, center, angle, k, tx, ty):
    """Перспективный поворот карты из полос (быстро, средствами SDL): строки растягиваются по ширине (наклон
    вверх-вниз), столбцы — по высоте (наклон влево-вправо); пиксели ближайшие — пиксель-арт не размывается.
    Уходящая сторона темнее. center — пиксели окна, k — масштаб, angle — ещё поворот в плоскости.
    Возвращает (Surface, левый верхний угол)."""
    w, h = img.get_size()
    ax, ay = math.radians(MAX_TILT) * tx, math.radians(MAX_TILT) * ty
    f = 1.9 * h                                             # фокусное расстояние — заметная, но мягкая перспектива
    # проход 1 — строки: наклон вокруг горизонтальной оси
    def py(yc):
        return f / (f + yc * math.sin(ay))
    top = (-h / 2) * math.cos(ay) * py(-h / 2) * k
    bot = (h / 2) * math.cos(ay) * py(h / 2) * k
    rw = int(math.ceil(w * k * max(py(-h / 2), py(h / 2)))) + 2
    rh = int(math.ceil(bot - top)) + 2
    rows = pygame.Surface((rw, rh), pygame.SRCALPHA)
    for y0 in range(0, h, STRIP):
        y1 = min(h, y0 + STRIP)
        a = (y0 - h / 2) * math.cos(ay) * py(y0 - h / 2) * k - top
        b = (y1 - h / 2) * math.cos(ay) * py(y1 - h / 2) * k - top
        dh = max(1, round(b) - round(a))
        dw = max(1, round(w * k * py((y0 + y1) / 2 - h / 2)))
        rows.blit(pygame.transform.scale(img.subsurface((0, y0, w, y1 - y0)), (dw, dh)), ((rw - dw) // 2, round(a)))
    # проход 2 — столбцы: наклон вокруг вертикальной оси
    def px(xc):
        return f / (f + xc / max(k, 1e-3) * math.sin(ax))
    left = (-rw / 2) * math.cos(ax) * px(-rw / 2)
    right = (rw / 2) * math.cos(ax) * px(rw / 2)
    ow = int(math.ceil(right - left)) + 2
    oh = int(math.ceil(rh * max(px(-rw / 2), px(rw / 2)))) + 2
    out = pygame.Surface((ow, oh), pygame.SRCALPHA)
    for x0 in range(0, rw, STRIP):
        x1 = min(rw, x0 + STRIP)
        a = (x0 - rw / 2) * math.cos(ax) * px(x0 - rw / 2) - left
        b = (x1 - rw / 2) * math.cos(ax) * px(x1 - rw / 2) - left
        dw = max(1, round(b) - round(a))
        dh = max(1, round(rh * px((x0 + x1) / 2 - rw / 2)))
        out.blit(pygame.transform.scale(rows.subsurface((x0, 0, x1 - x0, rh)), (dw, dh)), (round(a), (oh - dh) // 2))
    # свет: уходящая сторона темнее
    sh = pygame.Surface((2, 2))
    for (cx, cy), (sx, sy) in zip(((0, 0), (1, 0), (0, 1), (1, 1)), ((-1, -1), (1, -1), (-1, 1), (1, 1))):
        c = int(max(0.6, min(1.0, 0.94 - 0.2 * (tx * sx + ty * sy))) * 255)
        sh.set_at((cx, cy), (c, c, c))
    out.blit(pygame.transform.smoothscale(sh, (ow, oh)), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    if abs(angle) > 0.3:                                    # ещё и поворот в плоскости (тянут, веер)
        out = pygame.transform.rotate(out, angle)
    return out, (round(center[0] - out.get_width() / 2), round(center[1] - out.get_height() / 2))


class FaceCanvas(Canvas):
    """Холст для лица карты: логические координаты лица (512×768) — в настоящую поверхность нужного размера.
    Текст пишется сразу кеглем ×S (чётко, с хинтингом), а не уменьшается из большого лица."""

    def __init__(self, native, lw, lh):
        pygame.Surface.__init__(self, (1, 1), pygame.SRCALPHA)
        self.native = native
        self.LW, self.LH = lw, lh
        self.S = native.get_width() / lw
        self.ox = self.oy = 0.0
        self.pixel = False
        self._px = {}
        self._tick, self._turns = -1, 0
        self._pxtick, self._seen, self._seen_new = -1, set(), set()

    def get_size(self):
        return (self.LW, self.LH)

    def get_width(self):
        return self.LW

    def get_height(self):
        return self.LH

    def get_rect(self, **kw):
        return pygame.Rect(0, 0, self.LW, self.LH)

    def content(self):
        return self.native.get_rect()

    def blit(self, src, dest, area=None, special_flags=0):
        if area is not None:
            src = src.subsurface(area)
        pos = dest.topleft if isinstance(dest, pygame.Rect) else dest
        w, h = src.get_size()
        tw, th = max(1, round(w * self.S)), max(1, round(h * self.S))
        img = pygame.transform.smoothscale(src.convert_alpha() if src.get_bitsize() != 32 else src, (tw, th))             if (tw, th) != (w, h) else src
        return self.native.blit(img, (round(pos[0] * self.S), round(pos[1] * self.S)), special_flags=special_flags)


def is_canvas(s):
    return isinstance(s, Canvas)


# ---------- подмена рисования на время кадра ----------

_orig = {}


def _rect_kw(c, kw):
    out = dict(kw)
    for k in ("border_radius", "border_top_left_radius", "border_top_right_radius", "border_bottom_left_radius",
              "border_bottom_right_radius"):
        if k in out and out[k] > 0:
            out[k] = max(1, round(out[k] * c.S))
    return out


def _d_rect(surf, color, rect, width=0, *a, **kw):
    if not is_canvas(surf):
        return _orig["rect"](surf, color, rect, width, *a, **kw)
    c = surf
    if a:                                           # border_radius позиционно
        a = tuple(max(1, round(v * c.S)) if v > 0 else v for v in a)
    return _orig["rect"](c.native, color, c.rect(rect), c.w(width), *a, **_rect_kw(c, kw))


def _d_circle(surf, color, center, radius, width=0, *a, **kw):
    if not is_canvas(surf):
        return _orig["circle"](surf, color, center, radius, width, *a, **kw)
    c = surf
    return _orig["circle"](c.native, color, c.pt(center), max(1, radius * c.S), c.w(width), *a, **kw)


def _d_line(surf, color, a, b, width=1):
    if not is_canvas(surf):
        return _orig["line"](surf, color, a, b, width)
    c = surf
    return _orig["line"](c.native, color, c.pt(a), c.pt(b), c.w(width) or 1)


def _d_lines(surf, color, closed, points, width=1):
    if not is_canvas(surf):
        return _orig["lines"](surf, color, closed, points, width)
    c = surf
    return _orig["lines"](c.native, color, closed, [c.pt(p) for p in points], c.w(width) or 1)


def _d_polygon(surf, color, points, width=0):
    if not is_canvas(surf):
        return _orig["polygon"](surf, color, points, width)
    c = surf
    return _orig["polygon"](c.native, color, [c.pt(p) for p in points], c.w(width))


def _d_ellipse(surf, color, rect, width=0):
    if not is_canvas(surf):
        return _orig["ellipse"](surf, color, rect, width)
    c = surf
    return _orig["ellipse"](c.native, color, c.rect(rect), c.w(width))


def _d_aaline(surf, color, a, b, *rest):
    if not is_canvas(surf):
        return _orig["aaline"](surf, color, a, b, *rest)
    c = surf
    return _orig["aaline"](c.native, color, c.pt(a), c.pt(b), *rest)


def _t_text(surf, s, pos, size=16, color=T.TEXT, bold=False, center=False, shadow=False):
    """Текст на холсте: место — по логическим размерам, рисунок — шрифтом ×S (чётко)."""
    if not is_canvas(surf):
        return _orig["text"](surf, s, pos, size, color, bold, center, shadow)
    c = surf
    lr = T.render(s, size, color, bold).get_rect()
    if center:
        lr.center = pos
    else:
        lr.topleft = pos
    ns = max(6, round(size * c.S))
    img = T.render(s, ns, color, bold)
    nr = img.get_rect()
    if center:
        nr.center = c.pt(lr.center)
    else:
        nr.midleft = c.pt(lr.midleft)
    if shadow:
        c.native.blit(T.render(s, ns, (0, 0, 0), bold), nr.move(max(1, round(c.S)), max(1, round(c.S))))
    c.native.blit(img, nr)
    return lr


def _t_frame(surf, rect, alpha=238, accent=None, corners=True, radius=7, fill=None, corner=None):
    if not is_canvas(surf):
        return _orig["frame"](surf, rect, alpha, accent, corners, radius, fill, corner)
    c = surf
    _orig["frame"](c.native, c.rect(rect), alpha, accent, corners, max(1, round(radius * c.S)), fill, corner)
    return pygame.Rect(rect)


@contextlib.contextmanager
def native(canvas):
    """На время кадра: рисование на холст — в родное разрешение. Вложенный вызов (лицо карты собирается посреди
    кадра) ничего не меняет — внешний сам вернёт всё на место."""
    d = pygame.draw
    if _orig and d.rect is _d_rect:
        yield canvas
        return
    if not _orig:
        _orig.update(rect=d.rect, circle=d.circle, line=d.line, lines=d.lines, polygon=d.polygon,
                     ellipse=d.ellipse, aaline=d.aaline, text=T.text, frame=T.frame)
    d.rect, d.circle, d.line, d.lines, d.polygon, d.ellipse, d.aaline = (
        _d_rect, _d_circle, _d_line, _d_lines, _d_polygon, _d_ellipse, _d_aaline)
    T.text, T.frame = _t_text, _t_frame
    try:
        yield canvas
    finally:
        d.rect, d.circle, d.line, d.lines, d.polygon, d.ellipse, d.aaline = (
            _orig["rect"], _orig["circle"], _orig["line"], _orig["lines"], _orig["polygon"], _orig["ellipse"],
            _orig["aaline"])
        T.text, T.frame = _orig["text"], _orig["frame"]


def to_logical(canvas, pos):
    return ((pos[0] - canvas.ox) / canvas.S, (pos[1] - canvas.oy) / canvas.S)
