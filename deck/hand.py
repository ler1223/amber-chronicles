"""Рука карт «Спуска» с живым откликом (как в Balatro): веер, покачивание, плавный подъём и наклон к мыши, тень,
перетаскивание с креном от скорости, добор из колоды и полёт в сброс / к цели.

Карты — спрайты с пружинами: положение, угол и масштаб тянутся к целям (layout), скорость даёт инерцию.
Лицо карты рисуется один раз на состояние (кэш) и поворачивается/масштабируется каждый кадр.
"""
import math

import pygame

from .cardface import title_style

SPRING = 210.0          # жёсткость пружины положения
DAMP = 20.0             # затухание
ASPRING = 260.0
ADAMP = 22.0
FLIP_T = 0.32           # переворот на 180° (ПКМ): время ровного разворота


def ease(t):
    """Плавный разгон и торможение без перелёта (кубическая)."""
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


class Sprite:
    def __init__(self, card, pos):
        self.card = card
        self.x, self.y = pos
        self.vx = self.vy = 0.0
        self.a, self.va = -18.0, 0.0
        self.s = 0.55
        self.tx, self.ty, self.ta, self.ts = self.x, self.y, 0.0, 1.0
        self.alpha = 255
        self.fly = None          # (куда, сколько осталось, всего, гаснуть ли)
        self.order = 0
        self.tilt = (0.0, 0.0)   # наклон для объёма рамки (слои сдвигаются по глубине), −1…1
        self.age = 0.0           # сколько живёт в руке: только что взятая — рубашкой вверх
        self.back_only = False   # всегда рубашкой (полёт части в стопку)
        self.f = 0.0             # поворот переворота (0 — основное сверху, 180 — простое), отдельно от пружины
        self.f0 = self.ft = 0.0
        self.fp = 1.0            # ход переворота 0..1

    def flip_bump(self):
        """Середина переворота: карта чуть приподнята и крупнее."""
        if self.fp >= 1.0:
            return 1.0, 0.0
        k = math.sin(math.pi * self.fp)
        return 1.0 + 0.08 * k, -16.0 * k


class HandView:
    def __init__(self, card_size, draw_pos, discard_pos):
        self.cw, self.ch = card_size
        self.draw_pos = draw_pos
        self.discard_pos = discard_pos
        self.sprites = {}        # uid карты -> спрайт в руке
        self.flying = []         # улетают: в сброс, к цели
        self.hover = None        # uid карты под мышью
        self.drag = None         # uid перетаскиваемой
        self.grab = (0, 0)
        self.lifted = None       # uid карты, поднятой над рукой (прицел стрелкой)
        self.t = 0.0
        self.cache = {}
        self.face = None         # функция: (карта, состояние) -> Surface лица
        self.flipped = set()     # uid карт, повёрнутых простым применением вверх (ПКМ)
        self.face_tilt = None    # функция: (карта, состояние, наклон) -> лицо с объёмом
        self.glow = None         # функция: (карта, состояние) -> светиться ли (условие выполнено, как в CZN)
        self.back = None         # рубашка героя — у карты, только что взятой из колоды
        self.mouse = (0, 0)
        self.zoom = 1.4          # увеличение карты под мышью
        self.sink = False        # цель выбирают на поле — рука уходит вниз, нижние клетки видны

    # ---------- состав руки ----------

    def sync(self, hand):
        uids = [c.uid for c in hand]
        self.flipped &= set(uids)                            # ушла из руки — вернётся прямой
        for uid in list(self.sprites):
            if uid not in uids:
                sp = self.sprites.pop(uid)
                sp.fly = (self.discard_pos, 0.32, 0.32, True)
                self.flying.append(sp)
        for i, c in enumerate(hand):
            if c.uid not in self.sprites:
                sp = Sprite(c, self.draw_pos)
                sp.order = i
                self.sprites[c.uid] = sp
            self.sprites[c.uid].card = c

    def flip(self, uid):
        """ПКМ: повернуть карту на 180° — сверху окажется простое применение (или снова основное)."""
        if uid in self.flipped:
            self.flipped.discard(uid)
        else:
            self.flipped.add(uid)
        sp = self.sprites.get(uid)
        if sp is not None:                                   # ровный разворот с разгоном и торможением
            sp.f0, sp.ft, sp.fp = sp.f, (180.0 if uid in self.flipped else 0.0), 0.0

    def mode(self, uid):
        return "alt" if uid in self.flipped else "main"

    def played(self, card, to_pos):
        """Карта сыграна: летит к цели и гаснет (а не в сброс)."""
        sp = self.sprites.pop(card.uid, None)
        if sp is not None:
            sp.fly = (to_pos, 0.26, 0.26, True)
            sp.ts = 0.55
            self.flying.append(sp)

    # ---------- раскладка ----------

    def layout(self, hand, area, mouse):
        """Цели спрайтов: веер по дуге; под мышью — выше, крупнее, прямее; соседи расступаются."""
        n = len(hand)
        if not n:
            return
        cx = area.centerx
        base = area.bottom - self.ch * 0.5 - 16            # в покое карта видна целиком, с простым внизу
        step = min(self.cw * 0.86, (area.w - self.cw) / max(1, n - 1)) if n > 1 else 0
        mid = (n - 1) / 2
        hov = next((i for i, c in enumerate(hand) if c.uid == self.hover), None)
        for i, c in enumerate(hand):
            sp = self.sprites.get(c.uid)
            if sp is None or c.uid == self.drag:
                continue
            if getattr(sp, "merge_hold", False):              # оружие ждёт конца слияния
                sp.tx, sp.ty, sp.ts = sp.x, sp.y, sp.s
                continue
            k = i - mid
            x = cx + k * step
            if hov is not None and i != hov:                  # соседи расступаются
                x += 46 * (1 if i > hov else -1) * max(0.0, 1 - abs(i - hov) * 0.35)
            y = base + (k * k) * 2.2
            a = -k * 3.6
            s = 1.0
            sway = self.t * 1.4 + i * 0.9                     # покачивание, как дыхание
            y += math.sin(sway) * 2.2
            a += math.sin(sway * 0.8) * 1.1
            if self.sink and c.uid != self.hover:              # выбирают цель на поле: видны только верхушки
                y += self.ch * 0.6
                if c.uid == self.lifted:                       # выбранная — чуть выше остальных, ровно
                    y -= 26
                    a = 0.0
            elif c.uid == self.hover or c.uid == self.lifted:
                s = self.zoom
                y = area.bottom - self.ch * s * 0.5 - 6           # поднятая — целиком и крупно
                a = 0.0                                       # к мыши карта поворачивается в 3D (рисование)
            sp.tx, sp.ty, sp.ta, sp.ts = x, y, a, s
            sp.order = i + (100 if c.uid in (self.hover, self.lifted) else 0)

    def update(self, dt, mouse):
        self.t += dt
        self.mouse = mouse
        for uid, sp in self.sprites.items():            # наклон: к мыши у карты под ней, от скорости — у взятой
            sp.age += dt
            if uid == self.drag:
                goal = (max(-1.0, min(1.0, -sp.vx / 900)), max(-1.0, min(1.0, -sp.vy / 900)))
            elif uid in (self.hover, self.lifted):
                w, h = self.cw * sp.s / 2, self.ch * sp.s / 2
                goal = (max(-1.0, min(1.0, (mouse[0] - sp.x) / w)), max(-1.0, min(1.0, (mouse[1] - sp.y) / h)))
            else:
                goal = (0.0, 0.0)
            if uid in self.flipped:                       # повёрнута на 180 — наклон в другую сторону
                goal = (-goal[0], -goal[1])
            k = min(1.0, dt * 10)
            sp.tilt = (sp.tilt[0] + (goal[0] - sp.tilt[0]) * k, sp.tilt[1] + (goal[1] - sp.tilt[1]) * k)
        if self.drag in self.sprites:                         # тянется за мышью с инерцией и креном
            sp = self.sprites[self.drag]
            sp.tx, sp.ty = mouse[0] - self.grab[0], mouse[1] - self.grab[1]
            sp.ta = max(-20.0, min(20.0, -sp.vx * 0.035))
            sp.ts = 1.1
            sp.order = 200
        for sp in list(self.sprites.values()) + self.flying:
            if sp.fly:
                to, left, total, fade = sp.fly
                left -= dt
                sp.tx, sp.ty = to
                sp.ta = sp.a + 40 * dt * (1 if to[0] > sp.x else -1)
                if fade:
                    sp.alpha = int(255 * max(0.0, left / total))
                sp.fly = (to, left, total, fade)
            ax = SPRING * (sp.tx - sp.x) - DAMP * sp.vx
            ay = SPRING * (sp.ty - sp.y) - DAMP * sp.vy
            sp.vx += ax * dt
            sp.vy += ay * dt
            sp.x += sp.vx * dt
            sp.y += sp.vy * dt
            aa = ASPRING * (sp.ta - sp.a) - ADAMP * sp.va
            sp.va += aa * dt
            sp.a += sp.va * dt
            sp.s += (sp.ts - sp.s) * min(1.0, dt * 14)
            if sp.fp < 1.0:
                sp.fp = min(1.0, sp.fp + dt / FLIP_T)
                sp.f = sp.f0 + (sp.ft - sp.f0) * ease(sp.fp)
            else:
                sp.f = sp.ft
        self.flying = [sp for sp in self.flying if sp.fly and sp.fly[1] > 0]

    # ---------- мышь ----------

    def rect_of(self, sp):
        w, h = self.cw * sp.s, self.ch * sp.s
        return pygame.Rect(int(sp.x - w / 2), int(sp.y - h / 2), int(w), int(h))

    def hit(self, mouse, exclude=None):
        """Карта под мышью — верхняя по порядку отрисовки."""
        best = None
        for uid, sp in self.sprites.items():
            if uid != exclude and self.rect_of(sp).collidepoint(mouse) and (best is None or sp.order >= best[1]):
                best = (uid, sp.order)
        return best[0] if best else None

    def start_drag(self, uid, mouse):
        sp = self.sprites.get(uid)
        if sp is None:
            return
        self.drag = uid
        self.grab = (mouse[0] - sp.x, mouse[1] - sp.y)

    def top_of(self, uid):
        sp = self.sprites.get(uid)
        if sp is None:
            return None
        return (sp.x, sp.y - self.ch * sp.s * 0.5)

    # ---------- отрисовка ----------

    def draw(self, surf, state_of):
        """state_of(карта) -> ключ состояния лица (доступность, выбор) — лицо перерисовывается при смене."""
        items = sorted(self.sprites.values(), key=lambda sp: sp.order) + self.flying
        for sp in items:
            st = state_of(sp.card)
            zoom = self.zoom if sp.s > 1.15 else 1.0                       # лицо — под размер: в покое или крупно
            key = (title_style(), sp.card.uid, sp.card.tier, sp.card.uses, sp.card.ready, sp.card.insight_misses,
                   sp.card.lvl, sp.card.spirit_rank, st, zoom, sp.card.preview_key())
            face = self.cache.get(key)
            tilted = self.face_tilt is not None and abs(sp.tilt[0]) + abs(sp.tilt[1]) > 0.05
            if self.back is not None and (sp.back_only or (sp.age < 0.22 and not sp.fly)):  # рубашкой
                face = self.back
            elif tilted:                                                        # объём: слои по наклону
                face = self.face_tilt(sp.card, st, sp.tilt, zoom)
            elif face is None:
                face = self.face(sp.card, st, zoom)
                self.cache[key] = face
                if len(self.cache) > 120:
                    self.cache.clear()
                    from . import gfx
                    gfx._rot.clear()
                    self.cache[key] = face
            glowing = self.glow is not None and self.glow(sp.card, st) and not sp.fly
            bump, dy = sp.flip_bump()
            s_ = sp.s * bump
            a = sp.a + sp.f
            x, y = sp.x, sp.y + dy
            lift = max(0.0, s_ - 1.0) * 6 + (1.0 if sp.card.uid == self.drag else 0.0) - dy * 0.05
            off = 6 + lift * 10
            if hasattr(surf, "blit_hd"):                    # окно в родном разрешении: сразу из лица
                surf.blit_hd(self.shadow(), (x + off * 0.6, y + off), a, s_, alpha=int(110 * sp.alpha / 255))
                if glowing:                                 # условие выполнено — мягкий ореол вокруг карты
                    pulse = 0.5 + 0.5 * math.sin(self.t * 3.2 + sp.order)
                    surf.blit_hd(self.halo(), (x, y), a, s_, alpha=int((185 + 70 * pulse) * sp.alpha / 255))
                if tilted and hasattr(surf, "blit_card3d"):           # карта поворачивается вся, в 3D
                    surf.blit_card3d(face, (x, y), a, s_ * self.cw / face.get_width(), sp.tilt, alpha=sp.alpha)
                else:
                    surf.blit_hd(face, (x, y), a, s_ * self.cw / face.get_width(), alpha=sp.alpha)
                continue
            img = pygame.transform.rotozoom(face, a, s_ * self.cw / face.get_width())
            if sp.alpha < 255:
                img.set_alpha(sp.alpha)
            sh = pygame.transform.rotozoom(self.shadow(), a, s_)   # тень: дальше, когда карта поднята
            sh.set_alpha(int(110 * sp.alpha / 255))
            surf.blit(sh, (x - sh.get_width() / 2 + off * 0.6, y - sh.get_height() / 2 + off))
            surf.blit(img, (x - img.get_width() / 2, y - img.get_height() / 2))

    def halo(self):
        """Ореол карты: тёплое свечение, мягко гаснущее наружу (размер — карта + поля)."""
        s = self.cache.get("halo")
        if s is None:
            m = 34
            s = pygame.Surface((self.cw + 2 * m, self.ch + 2 * m), pygame.SRCALPHA)
            for k in range(m, 0, -1):
                a = int(235 * (1 - k / m) ** 1.3)
                r = pygame.Rect(m - k, m - k, self.cw + 2 * k, self.ch + 2 * k)
                pygame.draw.rect(s, (255, 206, 100, a), r, 2, border_radius=12 + k)
            pygame.draw.rect(s, (255, 240, 180, 255), pygame.Rect(m - 3, m - 3, self.cw + 6, self.ch + 6), 3,
                             border_radius=13)
            self.cache["halo"] = s
        return s

    def shadow(self):
        s = self.cache.get("shadow")
        if s is None:
            s = pygame.Surface((self.cw, self.ch), pygame.SRCALPHA)
            pygame.draw.rect(s, (0, 0, 0, 255), s.get_rect(), border_radius=10)
            self.cache["shadow"] = s
        return s


def arrow(surf, a, b, color, t=0.0):
    """Стрелка прицела от карты к цели: изогнутая цепочка шевронов, бегущих к цели, и наконечник."""
    ax, ay = a
    bx, by = b
    cx, cy = (ax + bx) / 2, min(ay, by) - abs(bx - ax) * 0.25 - 60
    pts = []
    n = 22
    for i in range(n + 1):
        u = i / n
        x = (1 - u) ** 2 * ax + 2 * (1 - u) * u * cx + u * u * bx
        y = (1 - u) ** 2 * ay + 2 * (1 - u) * u * cy + u * u * by
        pts.append((x, y))
    phase = (t * 3) % 1.0
    for i in range(1, n):
        u = i / n
        if (u * 6 - phase) % 1.0 > 0.55:
            continue
        r = 3 + 4 * u
        pygame.draw.circle(surf, (20, 14, 8), pts[i], r + 2)
        pygame.draw.circle(surf, color, pts[i], r)
    dx, dy = pts[-1][0] - pts[-3][0], pts[-1][1] - pts[-3][1]
    d = math.hypot(dx, dy) or 1
    dx, dy = dx / d, dy / d
    tip = pts[-1]
    left = (tip[0] - dx * 22 - dy * 13, tip[1] - dy * 22 + dx * 13)
    right = (tip[0] - dx * 22 + dy * 13, tip[1] - dy * 22 - dx * 13)
    pygame.draw.polygon(surf, (20, 14, 8), [(tip[0] + dx * 3, tip[1] + dy * 3), left, right])
    pygame.draw.polygon(surf, color, [tip, left, right])
