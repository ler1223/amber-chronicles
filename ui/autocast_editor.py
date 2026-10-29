"""Редактор автокаста одного навыка: вкл/выкл и до двух условий (тип < >, значение − +).

Меняет словарь настройки на месте — тот же объект живёт в юните (бой) и в бойце забега.
"""
import pygame

from sim import autocast as AC
from ui import theme as T

ON = (110, 220, 130)
ROW = 28


def _cycle_value(c, delta):
    vals = AC.CONDS[c["type"]]["values"]
    if not vals:
        return
    i = vals.index(c["value"]) if c.get("value") in vals else 0
    if c["type"] == "target_has_tag":
        c["value"] = vals[(i + delta) % len(vals)]
    else:
        c["value"] = vals[max(0, min(len(vals) - 1, i + delta))]


def _default_value(t):
    vals = AC.CONDS[t]["values"]
    if not vals:
        return None
    return vals[0] if t in ("target_has_tag", "enemies_adjacent", "enemies_in_area") else vals[len(vals) // 2]


def adjust_first_value(setting, delta):
    """Колесо мыши над карточкой навыка: крутит значение первого условия."""
    if setting["conds"]:
        _cycle_value(setting["conds"][0], delta)


class AutocastEditor:
    def __init__(self, sk, setting, tags):
        self.sk = sk
        self.st = setting
        self.tags = tags
        self.types = [None] + AC.allowed_conds(sk)
        self.hits = []

    @staticmethod
    def height():
        return 12 + ROW * 3

    def _set_type(self, i, delta):
        conds = self.st["conds"]
        cur = conds[i]["type"] if i < len(conds) else None
        used = {c["type"] for j, c in enumerate(conds) if j != i}
        opts = [t for t in self.types if t is None or t not in used]
        t = opts[(opts.index(cur) + delta) % len(opts)] if cur in opts else opts[delta % len(opts)]
        if t is None:
            if i < len(conds):
                conds.pop(i)
        else:
            c = {"type": t, "value": _default_value(t)}
            if i < len(conds):
                conds[i] = c
            else:
                conds.append(c)

    def click(self, pos):
        for r, action in self.hits:
            if r.collidepoint(pos):
                kind, i = action
                if kind == "toggle":
                    self.st["on"] = not self.st["on"]
                elif kind == "type":
                    self._set_type(i[0], i[1])
                elif kind == "value" and i[0] < len(self.st["conds"]):
                    _cycle_value(self.st["conds"][i[0]], i[1])
                return True
        return False

    def _btn(self, surf, rect, label, mouse, action, enabled=True):
        hot = enabled and rect.collidepoint(mouse)
        pygame.draw.rect(surf, (70, 74, 90) if hot else (48, 52, 64), rect, border_radius=5)
        T.text(surf, label, rect.center, 14, T.TEXT if enabled else T.TEXT_DIM, True, center=True)
        if enabled:
            self.hits.append((rect, action))

    def draw(self, surf, rect, mouse):
        self.hits = []
        pygame.draw.rect(surf, (22, 24, 30), rect, border_radius=8)
        pygame.draw.rect(surf, ON if self.st["on"] else T.PANEL_EDGE, rect, 2, border_radius=8)
        x, y = rect.x + 8, rect.y + 6
        tog = pygame.Rect(x, y, 118, ROW - 4)
        pygame.draw.rect(surf, (40, 90, 54) if self.st["on"] else (52, 52, 58), tog, border_radius=5)
        T.text(surf, "АВТО: вкл" if self.st["on"] else "АВТО: выкл", tog.center, 14,
               (200, 255, 210) if self.st["on"] else T.TEXT_DIM, True, center=True)
        self.hits.append((tog, ("toggle", None)))
        T.text(surf, "через «И»; пусто — всегда", (x + 128, y + 4), 12, T.TEXT_DIM)
        conds = self.st["conds"]
        for i in range(AC.MAX_CONDS):
            y += ROW
            active = i <= len(conds)  # второе условие доступно после первого
            c = conds[i] if i < len(conds) else None
            T.text(surf, f"{i + 1}.", (x, y + 4), 14, T.TEXT_DIM if not active else T.TEXT, True)
            self._btn(surf, pygame.Rect(x + 20, y, 22, ROW - 4), "<", mouse, ("type", (i, -1)), active)
            label = AC.cond_label(c, self.tags) if c else "— нет условия —"
            box = pygame.Rect(x + 46, y, rect.w - 46 - 8 - 26 - 60, ROW - 4)
            pygame.draw.rect(surf, (34, 36, 46), box, border_radius=5)
            T.text(surf, label, box.center, 13, T.TEXT if c else T.TEXT_DIM, bool(c), center=True)
            self._btn(surf, pygame.Rect(box.right + 4, y, 22, ROW - 4), ">", mouse, ("type", (i, 1)), active)
            has_val = c is not None and AC.CONDS[c["type"]]["values"] is not None
            vx = rect.right - 8 - 56
            self._btn(surf, pygame.Rect(vx, y, 26, ROW - 4), "−", mouse, ("value", (i, -1)), has_val)
            self._btn(surf, pygame.Rect(vx + 30, y, 26, ROW - 4), "+", mouse, ("value", (i, 1)), has_val)
