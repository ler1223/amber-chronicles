"""Артефакты и мини-игры мастерских: значок и подсказка артефакта, экран мини-игры (качество работы).
Сами мастерская, сундук и сборы — комнаты таверны (game/tavern_rooms.py)."""
import math

import pygame

from game import expedition_scenes as E
from game.expedition_scenes import XScene, BLESS, CURSE, GLORY, GOLD
from sim import artifacts as A
from ui import theme as T

WORKSHOPS = ("ws_forge", "ws_jewel", "ws_leather", "ws_alchemy")
WS_COLORS = {"ws_forge": (255, 150, 80), "ws_jewel": (120, 190, 255), "ws_leather": (210, 160, 100),
             "ws_alchemy": (140, 230, 140)}


def rar_color(xd, rarity):
    return tuple(xd["artifacts"]["rarities"][rarity]["color"])


def draw_art_icon(surf, r, xd, art, dim=False):
    """Значок артефакта: рамка цвета редкости и силуэт вида (наручи, пояс, кольцо, амулет, талисман)."""
    col = rar_color(xd, art["rarity"])
    if dim:
        col = T.mix(col, (40, 40, 40), 0.55)
    pygame.draw.rect(surf, T.mix((22, 18, 15), col, 0.18), r, border_radius=8)
    pygame.draw.rect(surf, col, r, 2, border_radius=8)
    img = E.icon(f"art_{art['kind']}_{art['rarity']}", int(min(r.w, r.h) - 8))   # лист A1 промптов
    if img is not None:
        if dim:
            img = img.copy()
            img.fill((120, 120, 120, 255), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(img, img.get_rect(center=r.center))
    else:
        _draw_art_shape(surf, r, art, col)
    if art.get("level"):
        T.text(surf, f"+{art['level']}", (r.right - 4 - T.font(12, True).size(f"+{art['level']}")[0], r.y + 2), 12,
               (255, 240, 200), True)


def _draw_art_shape(surf, r, art, col):
    """Заглушка, пока нет картинки: силуэт вида."""
    cx, cy, s = r.centerx, r.centery, min(r.w, r.h) / 2 - 6
    metal = T.mix((200, 190, 170), col, 0.35)
    k = art["kind"]
    if k == "bracers":
        for dx in (-s * 0.45, s * 0.45):
            pygame.draw.rect(surf, metal, (cx + dx - s * 0.3, cy - s * 0.6, s * 0.6, s * 1.2), border_radius=4)
            pygame.draw.line(surf, col, (cx + dx - s * 0.3, cy), (cx + dx + s * 0.3, cy), 2)
    elif k == "belt":
        pygame.draw.rect(surf, (130, 90, 55), (cx - s, cy - s * 0.25, 2 * s, s * 0.5), border_radius=3)
        pygame.draw.rect(surf, metal, (cx - s * 0.3, cy - s * 0.4, s * 0.6, s * 0.8), 3, border_radius=3)
    elif k == "ring":
        pygame.draw.circle(surf, metal, (cx, cy + s * 0.15), s * 0.6, 4)
        pygame.draw.polygon(surf, col, [(cx, cy - s * 0.85), (cx - s * 0.25, cy - s * 0.5), (cx + s * 0.25, cy - s * 0.5)])
    elif k == "amulet":
        pygame.draw.arc(surf, metal, (cx - s * 0.7, cy - s, s * 1.4, s * 1.4), math.pi * 1.1, math.pi * 1.9, 2)
        pygame.draw.circle(surf, col, (cx, cy + s * 0.35), s * 0.4)
        pygame.draw.circle(surf, metal, (cx, cy + s * 0.35), s * 0.4, 2)
    else:
        pygame.draw.polygon(surf, (225, 215, 190), [(cx, cy - s), (cx + s * 0.35, cy + s * 0.2), (cx, cy + s),
                                                   (cx - s * 0.35, cy + s * 0.2)])
        pygame.draw.circle(surf, col, (cx, cy), s * 0.2)


def art_tip(prof, art):
    """Подсказка артефакта: имя, редкость и качество, статы, сет и его бонусы, кто носит."""
    xd = prof.xd
    a = xd["artifacts"]
    s = a["sets"][art["set"]]
    rows = [(A.art_name(xd, art), rar_color(xd, art["rarity"])),
            (f"{a['rarities'][art['rarity']]['name']} · {A.quality_word(art['q'])} ({art['q'] * 100:.0f}%)", T.TEXT_DIM)]
    rows += [(ln, T.TEXT) for ln in A.art_lines(xd, art)]
    rows.append((f"Сет «{s['name']}»:", GLORY))
    rows += [(f"  {n} вещи: {b['text']}", BLESS) for n, b in sorted(s["bonus"].items())]
    owner = prof.art_owner(art["uid"])
    if prof.art_locked(art["uid"]):
        rows.append(("в походе — не снять", CURSE))
    elif owner:
        rows.append((f"носит {owner.name}", T.TEXT_DIM))
    return rows


class MiniGameScene(XScene):
    """Мини-игра мастерской. Esc — закончить досрочно (оставшееся засчитается как промах)."""

    @property
    def stage(self):
        """Широкая игра (огранка) рисуется на весь холст окна, остальные — в колонке 1280×800."""
        return not getattr(self.game, "wide", False)

    def __init__(self, app, game, title, on_done, back):
        super().__init__(app)
        self.game = game
        self.title = title
        self.on_done = on_done
        self.back = back
        self.finished = False

    def finish(self):
        if self.finished:
            return
        self.finished = True
        self.on_done(self.game.quality)
        self.back()

    def stop_early(self):
        g = self.game
        if g.done:
            return
        if hasattr(g, "can_abort") and g.can_abort():   # работа ещё не начата — выйти без потерь
            self.finished = True
            self.back()
            return
        if hasattr(g, "stop"):
            g.stop()
            return
        if hasattr(g, "STRIKES"):
            g.scores += [0.0] * (g.STRIKES - len(g.scores))
        elif hasattr(g, "FACETS"):
            g.scores += [0.0] * (g.FACETS - len(g.scores))
        else:
            g.total += max(0.0, g.DURATION - g.t)        # недоваренное время — мимо
        g.done = True

    def update(self, dt):
        super().update(dt)
        self.game.update(dt)

    def act(self, action, button=1):
        if action == "take":
            self.finish()

    def handle(self, ev):
        g = self.game
        if hasattr(g, "pointer") and g.pointer(ev, self.area()):
            if ev.type == pygame.MOUSEMOTION:
                self.mouse = ev.pos
            return
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.stop_early()
                return
            if g.done and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.finish()
                return
            if ev.key == pygame.K_SPACE:
                g.press()
                return
            if hasattr(g, "key") and g.key(ev.key):
                return
        elif ev.type == pygame.KEYUP and ev.key == pygame.K_SPACE:
            g.release()
            return
        elif ev.type == pygame.MOUSEWHEEL:
            if hasattr(g, "wheel"):
                g.wheel(ev.y)
            return
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (4, 5):
            return
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3 and not g.done and hasattr(g, "key"):
            g.key(pygame.K_RETURN)
            return
        elif ev.type == pygame.MOUSEMOTION:
            g.mouse(ev.pos, self.area())
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and not g.done and self.area().collidepoint(ev.pos):
            if hasattr(g, "click") and g.click(ev.pos):
                return
            if getattr(g, "click_press", True):           # огранка: ЛКМ не опускает камень (только Пробел)
                g.press()
            return
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and not g.done:
            if getattr(g, "click_press", True):
                g.release()
        super().handle(ev)

    def area(self):
        if getattr(self.game, "wide", False):          # поле — почти весь экран
            return pygame.Rect(16, 62, T.SCREEN_W - 32, T.SCREEN_H - 62 - 34)
        w, h = getattr(self.game, "area_size", (840, 360))
        return pygame.Rect(T.SCREEN_W // 2 - w // 2, 110, w, h)

    def draw(self, surf):
        self.hits = []
        surf.fill((14, 12, 10))
        self.backdrop(surf, "tavern", "tavern", dim=225)
        g = self.game
        wide = getattr(g, "wide", False)
        if wide:                                        # широкая игра: шапка и низ — тонкие, поле — максимум
            T.text(surf, self.title, (T.SCREEN_W // 2, 20), 24, GLORY, True, center=True, shadow=True)
            T.text(surf, f"{g.title}: {g.hint}", (T.SCREEN_W // 2, 46), 14, T.TEXT, center=True)
        else:
            T.text(surf, self.title, (T.SCREEN_W // 2, 30), 28, GLORY, True, center=True, shadow=True)
            T.text(surf, f"{g.title}: {g.hint}", (T.SCREEN_W // 2, 72), 15, T.TEXT, center=True)
        r = self.area()
        T.frame(surf, r, 235, accent=T.PANEL_EDGE)
        g.draw(surf, r)
        q = g.quality
        if getattr(g, "phase", "cut") not in ("choose", "plan"):        # огранка: качество — когда пошла работа
            T.text(surf, f"Качество сейчас: {q * 100:.0f}% — {A.quality_word(q)}",
                   (T.SCREEN_W // 2 - (200 if wide else 0), r.bottom + (17 if wide else 20)),
                   16 if wide else 18, GOLD if q >= 1.0 else T.TEXT, True, center=True)
        if g.done:
            self.button(surf, pygame.Rect(T.SCREEN_W // 2 - 140, T.SCREEN_H - 120, 280, 50), "Забрать (Enter)", "take",
                        True, GOLD)
        else:
            free = hasattr(g, "can_abort") and g.can_abort()
            T.text(surf, "Esc — выйти без потерь (работа не начата)" if free else
                   "Esc — закончить досрочно (остаток — как промах)",
                   (T.SCREEN_W // 2 + (220 if wide else 0), T.SCREEN_H - (17 if wide else 90)), 14,
                   T.TEXT_DIM, center=True)
        self.draw_tip(surf)
