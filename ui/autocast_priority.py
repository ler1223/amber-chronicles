"""Приоритет автокаста героя: навыки списком, перетаскиванием меняется порядок (выше — применяется раньше).

Между соседними навыками — резерв AP: сколько AP навык ниже обязан оставить под навыки выше (по умолчанию 0).
Резерв навыка — сумма резервов от верха списка до него (sim/autocast.py reserve_before). Клик по «авто» — вкл/выкл,
−/+ и колесо над резервом — меняют его. Один и тот же виджет — в листе героя (между боями) и в бою (P, на паузе).

Данные меняются на месте: order (список), reserve (словарь), autocast (настройки навыков)."""
import pygame

from sim import autocast as AC
from ui import theme as T

ROW_H, GAP_H = 38, 24
GOLD = (240, 200, 110)


class PriorityPanel:
    def __init__(self, tags=None):
        self.tags = tags
        self.rect = pygame.Rect(0, 0, 420, 400)
        self.defs, self.autocast, self.order, self.reserve = {}, {}, [], {}
        self.drag = None              # (индекс навыка, смещение мыши по y)
        self.mouse = (0, 0)
        self.hits = []

    def set_source(self, skill_defs, autocast, order, reserve):
        self.defs, self.autocast, self.order, self.reserve = skill_defs, autocast, order, reserve

    def height(self):
        n = len(self.order)
        return 62 + n * ROW_H + max(0, n - 1) * GAP_H + 52

    def _row_y(self, i):
        return self.rect.y + 62 + i * (ROW_H + GAP_H)

    def _row_at(self, y):
        """Куда лечь перетаскиваемому навыку: индекс по высоте курсора."""
        rel = y - self.rect.y - 62 + GAP_H // 2
        return max(0, min(len(self.order) - 1, int(rel // (ROW_H + GAP_H))))

    # ---------- ввод ----------

    def handle(self, ev):
        """True — событие обработано панелью."""
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
            return self.drag is not None
        if ev.type == pygame.MOUSEWHEEL:
            for r, act in self.hits:
                if act[0] == "gap" and r.collidepoint(self.mouse):
                    self._bump(act[1], 1 if ev.y > 0 else -1)
                    return True
            return self.rect.collidepoint(self.mouse)
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.mouse = ev.pos
            for r, act in reversed(self.hits):
                if not r.collidepoint(ev.pos):
                    continue
                if act[0] == "toggle":
                    st = self.autocast.get(act[1])
                    if st is not None:
                        st["on"] = not st["on"]
                elif act[0] == "minus":
                    self._bump(act[1], -1)
                elif act[0] == "plus":
                    self._bump(act[1], 1)
                elif act[0] == "row":
                    i = self.order.index(act[1])
                    self.drag = (i, ev.pos[1] - self._row_y(i))
                return True
            return self.rect.collidepoint(ev.pos)
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.drag is not None:
            i, _ = self.drag
            self.drag = None
            j = self._row_at(ev.pos[1])
            if j != i:
                sid = self.order.pop(i)
                self.order.insert(j, sid)
            return True
        return False

    def _bump(self, sid, d):
        v = max(0, min(12, self.reserve.get(sid, 0) + d))
        if v:
            self.reserve[sid] = v
        else:
            self.reserve.pop(sid, None)

    # ---------- кадр ----------

    def draw(self, surf, title="Приоритет автокаста"):
        r = self.rect
        self.hits = []
        T.frame(surf, r, 245, accent=GOLD, corner=GOLD)
        T.text(surf, title, (r.x + 14, r.y + 10), 18, GOLD, True)
        T.text(surf, "Выше — применяется раньше; перетаскивайте мышью.", (r.x + 14, r.y + 34), 12, T.TEXT_DIM)
        drag_i = self.drag[0] if self.drag else None
        for i, sid in enumerate(self.order):
            y = self._row_y(i)
            if i > 0:                                    # резерв AP между навыком выше и этим
                g = pygame.Rect(r.x + 60, y - GAP_H + 2, r.w - 120, GAP_H - 4)
                n = self.reserve.get(sid, 0)
                hot = g.collidepoint(self.mouse)
                pygame.draw.rect(surf, (40, 32, 24) if not hot else (60, 46, 32), g, border_radius=5)
                lab = f"резерв {n} AP под навыки выше" if n else "без резерва (0 AP)"
                T.text(surf, lab, g.center, 12, T.AP_COLOR if n else T.TEXT_DIM, bool(n), center=True)
                m = pygame.Rect(g.x + 2, g.y + 1, 22, g.h - 2)
                p = pygame.Rect(g.right - 24, g.y + 1, 22, g.h - 2)
                for b, s in ((m, "−"), (p, "+")):
                    pygame.draw.rect(surf, (70, 56, 40), b, border_radius=4)
                    T.text(surf, s, b.center, 15, T.TEXT, True, center=True)
                self.hits += [(g, ("gap", sid)), (m, ("minus", sid)), (p, ("plus", sid))]
            if i == drag_i:
                continue
            self._row(surf, sid, i, pygame.Rect(r.x + 10, y, r.w - 20, ROW_H))
        if drag_i is not None:                           # перетаскиваемый — под курсором, место — подсветкой
            j = self._row_at(self.mouse[1])
            pygame.draw.rect(surf, GOLD, pygame.Rect(r.x + 10, self._row_y(j) - 3, r.w - 20, 3))
            sid = self.order[drag_i]
            self._row(surf, sid, drag_i, pygame.Rect(r.x + 10, self.mouse[1] - self.drag[1], r.w - 20, ROW_H), True)
        note = "Резерв: навык ниже применится, только если после него останется столько AP под навыки выше."
        for k, ln in enumerate(T.wrap(note, 12, r.w - 28)[:2]):
            T.text(surf, ln, (r.x + 14, r.bottom - 40 + k * 15), 12, T.TEXT_DIM)

    def _row(self, surf, sid, i, rr, lifted=False):
        sk = self.defs.get(sid, {})
        st = self.autocast.get(sid)
        if not lifted:
            self.hits.append((rr, ("row", sid)))         # переключатель «авто» добавится позже — он главнее
        pygame.draw.rect(surf, (78, 60, 40) if lifted else (52, 40, 30), rr, border_radius=7)
        pygame.draw.rect(surf, GOLD if lifted else T.PANEL_EDGE, rr, 2 if lifted else 1, border_radius=7)
        T.text(surf, f"{i + 1}", (rr.x + 10, rr.y + 10), 16, GOLD, True)
        name = sk.get("name", sid) + ("  · кнопка" if sk.get("mech") else "  · ульт" if sk.get("ult") else "")
        T.text(surf, name, (rr.x + 34, rr.y + 4), 15, T.TEXT, True)
        cond = AC.setting_label(st, self.tags) if st else "без автокаста"
        T.text(surf, f"{sk.get('ap', 0)} AP · {cond}", (rr.x + 34, rr.y + 21), 11, T.TEXT_DIM)
        if st is not None:
            tg = pygame.Rect(rr.right - 74, rr.y + 7, 66, rr.h - 14)
            on = st["on"]
            pygame.draw.rect(surf, (36, 90, 52) if on else (60, 44, 34), tg, border_radius=6)
            T.text(surf, "авто вкл" if on else "авто выкл", tg.center, 12, (200, 255, 210) if on else T.TEXT_DIM, on,
                   center=True)
            if not lifted:
                self.hits.append((tg, ("toggle", sid)))
