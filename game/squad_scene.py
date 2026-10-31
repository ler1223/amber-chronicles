"""Экран «Отряд»: поле расстановки (зона высадки 3×6) и ростер. Героев перетаскивают мышью: из ростера на поле —
в отряд (на занятую клетку — заменить), по полю — переставить, с поля в ростер — убрать. Справа — выбранный герой
и «Связки отряда»: кому что нужно (data/synergy.json). Три сохранённых состава. Расстановка уходит в первый бой
вылазки."""
import math

import pygame

from game.meta_scenes import MetaScene
from game.title_scene import GOLD
from ui import theme as T
from ui import widgets as W
from ui.sprites import SpriteBank

AMBER = (255, 170, 60)
ROLE = {"melee": "ближний бой", "ranged": "дальний бой", "caster": "маг", "support": "поддержка"}
FILTERS = [("all", "Все"), ("melee", "Ближний бой"), ("ranged", "Дальний бой"), ("caster", "Маги"),
           ("support", "Поддержка")]
OK, MISS = (120, 220, 130), (240, 110, 100)
DRAG = 8

BOARD = pygame.Rect(24, 64, 470, 452)
TILE_W, TILE_H = 120, 60
TILE_X, TILE_Y = 60, 116
INFO = pygame.Rect(510, 64, 746, 236)
SYN = pygame.Rect(510, 310, 746, 206)
ROSTER = pygame.Rect(24, 526, 1232, 194)


def tile_rect(cell):
    x, y = cell
    return pygame.Rect(TILE_X + x * (TILE_W + 8), TILE_Y + y * (TILE_H + 2), TILE_W, TILE_H)


class SquadScene(MetaScene):
    hint = ("Перетащите героя из ростера на поле — в отряд (на занятую клетку — заменить), по полю — переставить, "
            "с поля вниз — убрать. Клик — подробности. Герои бесплатны и открываются главами. Расстановка — стартовая "
            "в первом бою вылазки.")

    def __init__(self, app):
        super().__init__(app)
        self.sprites = SpriteBank()
        self.clock = 0.0
        self.filter = "all"
        self.selected = app.profile.squad[0]
        self.drag = None            # {"cls", "from": "board"|"roster", "start": pos}
        self.portraits = []         # (rect, cls)
        self.last_click = (None, 0.0)
        self._layout()

    def _layout(self):
        global INFO, SYN, ROSTER
        # поле расстановки фиксированное, информационные панели тянутся по ширине окна
        INFO = pygame.Rect(510, 64, max(300, T.SCREEN_W - 534), 236)
        SYN = pygame.Rect(510, 310, max(300, T.SCREEN_W - 534), 206)
        ROSTER = pygame.Rect(24, 526, max(600, T.SCREEN_W - 48), 194)

    def relayout(self):
        super().relayout()
        self._layout()

    # ---------- ввод ----------

    def update(self, dt):
        super().update(dt)
        self.clock += dt

    def _cell_at(self, pos):
        for x in range(3):
            for y in range(6):
                if tile_rect((x, y)).collidepoint(pos):
                    return (x, y)
        return None

    def _portrait_at(self, pos):
        return next((c for r, c in self.portraits if r.collidepoint(pos)), None)

    def handle(self, ev):
        prof = self.app.profile
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.mouse = ev.pos
            if self.back.collidepoint(ev.pos):
                self.go_back()
                return
            for r, action, _ in self.hits:
                if r.collidepoint(ev.pos) and action:
                    self.act(action)
                    return
            cell = self._cell_at(ev.pos)
            cls = prof.hero_at(cell) if cell else self._portrait_at(ev.pos)
            if cls:
                self.drag = {"cls": cls, "from": "board" if cell else "roster", "start": ev.pos}
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.drag:
            d, self.drag = self.drag, None
            moved = math.dist(ev.pos, d["start"]) > DRAG
            if not moved:
                self._click(d["cls"], d["from"])
                return
            cell = self._cell_at(ev.pos)
            if cell:
                ok, msg = prof.place(d["cls"], cell)
                if not ok:
                    self.say(msg)
                self.selected = d["cls"]
            elif d["from"] == "board" and (ROSTER.collidepoint(ev.pos) or not BOARD.collidepoint(ev.pos)):
                ok, msg = prof.remove_from_squad(d["cls"])
                if not ok and msg:
                    self.say(msg)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
            cls = self._portrait_at(ev.pos) or (prof.hero_at(self._cell_at(ev.pos)) if self._cell_at(ev.pos) else None)
            if cls:
                self.act(("toggle", cls))
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.go_back()

    def _click(self, cls, where):
        """Клик — выбрать; двойной клик по портрету — в отряд на свободную клетку."""
        cls_prev, t = self.last_click
        double = cls_prev == cls and self.clock - t < 0.4
        self.last_click = (cls, self.clock)
        self.selected = cls
        if double and where == "roster":
            self.act(("toggle", cls))

    def act(self, action):
        prof = self.app.profile
        kind = action[0]
        if kind == "filter":
            self.filter = action[1]
        elif kind == "prep":
            from game.meta_scenes import HeroesScene
            scene = HeroesScene(self.app, action[1], "skills")
            scene.on_back = lambda: self.app.switch(self)
            self.app.switch(scene)
        elif kind == "look":
            from game.meta_scenes import HeroesScene
            scene = HeroesScene(self.app, action[1], "skills")
            scene.on_back = lambda: self.app.switch(self)
            self.app.switch(scene)
        elif kind == "toggle":                 # в отряд / из отряда
            cls = action[1]
            self.selected = cls
            if cls not in prof.unlocked:
                self.say(prof.hero_lock_reason(cls) or "Герой ещё не открыт")
                return
            if cls in prof.squad:
                ok, msg = prof.remove_from_squad(cls)
            else:
                taken = set(prof.formation_cells().values())
                free = next((p for p in prof.DEFAULT_SPOTS + [(x, y) for x in range(3) for y in range(6)]
                             if p not in taken), None)
                ok, msg = prof.place(cls, free) if free else (False, "Нет свободных клеток")
            if not ok and msg:
                self.say(msg)
        elif kind == "preset_load":
            ok, msg = prof.load_preset(action[1])
            self.say(f"Состав {action[1] + 1} загружен" if ok else msg)
        elif kind == "preset_save":
            prof.save_preset(action[1])
            self.say(f"Текущий отряд сохранён как «Состав {action[1] + 1}»")

    # ---------- отрисовка ----------

    def draw(self, surf):
        prof = self.app.profile
        self.hits = []
        surf.fill(T.BG)
        T.text(surf, "Отряд", (24, 14), 30, T.TEXT, True)
        amber = f"Янтарь: {prof.amber}"
        T.text(surf, amber, (T.SCREEN_W - 30 - T.font(22, True).size(amber)[0], 18), 22, AMBER, True)
        self._draw_presets(surf)
        self._draw_board(surf)
        self._draw_info(surf)
        self._draw_synergy(surf)
        self._draw_roster(surf)
        if self.drag and math.dist(self.mouse, self.drag["start"]) > DRAG:
            img = self._sprite(self.drag["cls"], 1.5)
            surf.blit(img, (self.mouse[0] - img.get_width() / 2, self.mouse[1] - img.get_height() * 0.7))
        self.draw_footer(surf)

    def _sprite(self, cls, k=1.0, dim=False):
        c = self.app.data.classes[cls]
        img = self.sprites.get([cls], cls, tuple(c["color"]), look=c.get("look"))
        if k != 1:
            img = pygame.transform.scale(img, (int(img.get_width() * k), int(img.get_height() * k)))
        if dim:
            img = img.copy()
            img.fill((70, 70, 80, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return img

    def _draw_presets(self, surf):
        prof = self.app.profile
        x = 360
        for i in range(3):
            r = pygame.Rect(x, 16, 132, 34)
            has = prof.presets[i] is not None
            W.button(surf, r, f"Состав {i + 1}", self.mouse, has, accent=GOLD)
            self.hit(r, ("preset_load", i), "Загрузить сохранённый состав" if has else "Пусто — сохраните текущий")
            s = pygame.Rect(r.right + 4, 16, 34, 34)
            W.button(surf, s, "↓", self.mouse, accent=(170, 160, 210))
            self.hit(s, ("preset_save", i), f"Запомнить текущий отряд и расстановку как «Состав {i + 1}»")
            x += 182

    def _draw_board(self, surf):
        prof, data = self.app.profile, self.app.data
        pygame.draw.rect(surf, T.PANEL, BOARD, border_radius=10)
        T.text(surf, f"Расстановка · в отряде {len(prof.squad)} из {prof.squad_size()}", (BOARD.x + 14, BOARD.y + 10),
               17, GOLD, True)
        T.text(surf, "враги →", (BOARD.right - 86, BOARD.y + 14), 15, (240, 120, 110), True)
        cells = prof.formation_cells()
        drop = self._cell_at(self.mouse) if self.drag else None
        for x in range(3):
            for y in range(6):
                r = tile_rect((x, y))
                shade = 34 + x * 6 + ((x + y) % 2) * 4
                pygame.draw.rect(surf, (shade, shade + 6, shade), r, border_radius=6)
                pygame.draw.rect(surf, (120, 255, 140) if (x, y) == drop else (60, 70, 62), r,
                                 3 if (x, y) == drop else 1, border_radius=6)
        T.text(surf, "тыл", (TILE_X, TILE_Y + 6 * (TILE_H + 2) + 2), 12, T.TEXT_DIM)
        T.text(surf, "передний край", (TILE_X + 2 * (TILE_W + 8), TILE_Y + 6 * (TILE_H + 2) + 2), 12, T.TEXT_DIM)
        order = sorted(cells.items(), key=lambda kv: kv[1][1])
        for cls, cell in order:
            if self.drag and self.drag["cls"] == cls and math.dist(self.mouse, self.drag["start"]) > DRAG:
                continue
            r = tile_rect(cell)
            c = data.classes[cls]
            sel = cls == self.selected
            pygame.draw.ellipse(surf, T.SELECT if sel else GOLD, (r.centerx - 30, r.bottom - 16, 60, 14), 2)
            img = self._sprite(cls, 1.0)
            bob = 2 * math.sin(self.clock * 2 + cell[1])
            surf.blit(img, (r.centerx - img.get_width() / 2, r.bottom - img.get_height() - 6 - bob))
            T.text(surf, c["name"], (r.x + 4, r.y + 2), 11, T.TEXT, True, shadow=True)
            self.hit(r, None, f"{c['name']}: перетащите, чтобы переставить; вниз — убрать из отряда")

    def _draw_info(self, surf):
        prof, data = self.app.profile, self.app.data
        pygame.draw.rect(surf, T.PANEL, INFO, border_radius=10)
        cls = self.selected
        c = data.classes[cls]
        hired = cls in prof.unlocked
        img = self._sprite(cls, 2.0, dim=not hired)
        surf.blit(img, (INFO.x + 8, INFO.y + 8))
        x = INFO.x + 150
        T.text(surf, c["name"], (x, INFO.y + 10), 24, T.TEXT if hired else T.TEXT_DIM, True)
        sub = ROLE.get(c["role"], c["role"]) + (f" · мастерство {prof.mastery(cls)}" if hired else "")
        h = prof.heroes[cls]
        if hired and h["path"]:
            sub += f" · путь «{data.paths[h['path']]['name']}»"
        T.text(surf, sub, (x, INFO.y + 40), 14, T.TEXT_DIM)
        skills = ", ".join(data.skills[s]["name"] for s in c["skills"])
        g = c.get("gauge") or {}
        y = INFO.y + 62
        for line in T.wrap(c.get("about", ""), 13, INFO.right - x - 14)[:5]:
            T.text(surf, line, (x, y), 13, (200, 205, 220))
            y += 17
        T.text(surf, f"Навыки: {skills}", (x, y + 2), 13, (255, 180, 120))
        if g:
            T.text(surf, f"Шкала «{g['name']}»: {g['desc']}", (x, y + 20), 13, tuple(g.get("color", (200, 200, 200))))
        by = INFO.bottom - 44
        if not hired:
            T.text(surf, prof.hero_lock_reason(cls) or "Ещё не открыт", (x, by + 8), 14, (240, 150, 120), True)
            look = pygame.Rect(x + 300, by, 200, 34)
            W.button(surf, look, "Посмотреть навыки", self.mouse, accent=(170, 140, 255))
            self.hit(look, ("look", cls), "Превью навыков, ветки и пути — можно смотреть заранее")
        else:
            b = pygame.Rect(x, by, 160, 34)
            W.button(surf, b, "Убрать" if cls in prof.squad else "В отряд", self.mouse, accent=GOLD)
            self.hit(b, ("toggle", cls), None)
            p = pygame.Rect(b.right + 10, by, 220, 34)
            W.button(surf, p, "Подготовка и превью", self.mouse, accent=(170, 140, 255))
            self.hit(p, ("prep", cls), "Путь, ветки с превью навыков, таланты и снаряжение")

    def _synergy(self):
        """[(герой, нужда, кто закрывает)] и что даёт отряд."""
        data, prof = self.app.data, self.app.profile
        syn = data.synergy
        gives = {}
        for cls in prof.squad:
            for t in syn["classes"].get(cls, {}).get("gives", []):
                gives.setdefault(t, []).append(cls)
        rows = []
        for cls in prof.squad:
            for need in syn["classes"].get(cls, {}).get("needs", []):
                who = [c for t in need["any"] for c in gives.get(t, []) if c != cls]
                rows.append((cls, need, list(dict.fromkeys(who))))
        return rows, gives

    def _draw_synergy(self, surf):
        data = self.app.data
        pygame.draw.rect(surf, T.PANEL, SYN, border_radius=10)
        T.text(surf, "Связки отряда", (SYN.x + 14, SYN.y + 10), 17, (170, 200, 255), True)
        rows, gives = self._synergy()
        y = SYN.y + 38
        for cls, need, who in rows:
            ok = bool(who)
            pygame.draw.circle(surf, OK if ok else MISS, (SYN.x + 22, y + 8), 6)
            name = data.classes[cls]["name"]
            if ok:
                text = f"{name} — {need['text']}: есть {', '.join(data.classes[c]['name'] for c in who)}"
            else:
                text = f"{name} — {need['text']}: в отряде нет"
            for i, line in enumerate(T.wrap(text, 13, SYN.w - 50)[:2]):
                T.text(surf, line, (SYN.x + 36, y + i * 16), 13, (200, 230, 205) if ok else (250, 190, 180))
            y += 34 if len(T.wrap(text, 13, SYN.w - 50)) > 1 else 22
            if y > SYN.bottom - 40:
                break
        tags = data.synergy["tags"]
        have = ", ".join(tags[t] for t in tags if t in gives)
        for i, line in enumerate(T.wrap(f"Отряд: {have}", 12, SYN.w - 28)[:2]):
            T.text(surf, line, (SYN.x + 14, SYN.bottom - 36 + i * 15), 12, T.TEXT_DIM)

    def _draw_roster(self, surf):
        prof, data = self.app.profile, self.app.data
        pygame.draw.rect(surf, T.PANEL, ROSTER, border_radius=10)
        x = ROSTER.x + 12
        for fid, name in FILTERS:
            w = T.font(13, True).size(name)[0] + 20
            r = pygame.Rect(x, ROSTER.y + 8, w, 24)
            on = fid == self.filter
            pygame.draw.rect(surf, (60, 64, 78) if on else (36, 38, 46), r, border_radius=12)
            pygame.draw.rect(surf, GOLD if on else T.PANEL_EDGE, r, 1, border_radius=12)
            T.text(surf, name, r.center, 13, T.TEXT if on else T.TEXT_DIM, on, center=True)
            self.hit(r, ("filter", fid), None)
            x += w + 8
        T.text(surf, "ПКМ или двойной клик — в отряд/из отряда · перетащить на поле — на клетку",
               (x + 12, ROSTER.y + 12), 12, T.TEXT_DIM)
        heroes = [c for c in data.classes if self.filter == "all" or data.classes[c]["role"] == self.filter]
        self.portraits = []
        tw, th = 104, 74
        per_row = max(1, ROSTER.w // (tw + 6))       # шире окно — больше героев в ряду
        for i, cls in enumerate(heroes):
            r = pygame.Rect(ROSTER.x + 12 + (i % per_row) * (tw + 6), ROSTER.y + 40 + (i // per_row) * (th + 4), tw, th)
            self.portraits.append((r, cls))
            c = data.classes[cls]
            hired, in_squad = cls in prof.unlocked, cls in prof.squad
            hot = r.collidepoint(self.mouse) or cls == self.selected
            pygame.draw.rect(surf, (52, 56, 68) if hot else (36, 38, 46), r, border_radius=8)
            edge = GOLD if in_squad else (tuple(c["color"]) if hired else T.PANEL_EDGE)
            pygame.draw.rect(surf, edge, r, 3 if in_squad else 1, border_radius=8)
            img = self._sprite(cls, 0.85, dim=not hired)
            surf.blit(img, (r.centerx - img.get_width() / 2, r.y - 2))
            label = c["name"]
            size = 11
            while T.font(size, True).size(label)[0] > tw - 6 and size > 9:
                size -= 1
            T.text(surf, label, (r.centerx, r.bottom - 10), size, T.TEXT if hired else T.TEXT_DIM, True, center=True,
                   shadow=True)
            if not hired:
                cid = data.hero_chapter.get(cls)
                if cid:
                    T.text(surf, f"гл.{data.biomes[cid].get('order', 0) + 1}", (r.right - 34, r.y + 4), 11,
                           (240, 150, 120), True)
            elif in_squad:
                pygame.draw.circle(surf, GOLD, (r.right - 10, r.y + 10), 5)
            self.hit(r, None, f"{c['name']} — {ROLE.get(c['role'], c['role'])}"
                     + ("" if hired else f". {prof.hero_lock_reason(cls) or 'Ещё не открыт'}"))
