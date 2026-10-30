"""Карта главы: выбор главы и сложности, регионы, захват, выбор следующей вылазки. Мета-прогресс — sim/profile.py."""
import math

import pygame

from sim import stats

from sim import meta
from ui import theme as T
from ui import widgets as W

AMBER = (255, 170, 60)
CAPTURED = (90, 200, 120)
BOSS = (170, 70, 210)
REGION_R = 34
MAP_RECT = pygame.Rect(24, 132, 840, 524)
PANEL_RECT = pygame.Rect(884, 132, 372, 524)
DIFF_COLORS = {"normal": (120, 200, 255), "heroic": (255, 190, 80), "nightmare": (240, 80, 90)}


class WorldScene:
    def __init__(self, app):
        self.app = app
        self.mouse = (0, 0)
        self.clock = 0.0
        self.tip = None
        self._layout()

    def _layout(self):
        prof = self.app.profile
        self.pos = {}
        for r in prof.biome["regions"]:
            fx, fy = r["pos"]
            self.pos[r["id"]] = (MAP_RECT.x + 50 + fx * (MAP_RECT.w - 100), MAP_RECT.y + 40 + fy * (MAP_RECT.h - 80))
        fresh = [rid for rid in prof.available() if rid not in prof.captured]
        self.selected = (fresh or prof.available() or [None])[0]
        self.go_rect = pygame.Rect(PANEL_RECT.x + 16, PANEL_RECT.bottom - 60, PANEL_RECT.w - 32, 44)
        self.heroes_rect = pygame.Rect(T.SCREEN_W - 520, 12, 150, 38)
        self.camp_rect = pygame.Rect(T.SCREEN_W - 360, 12, 150, 38)
        # полоска глав и вкладки сложности
        chapters = prof.chapters()
        cw = (MAP_RECT.w + 8) // len(chapters) - 8
        self.chapter_rects = [(pygame.Rect(24 + i * (cw + 8), 60, cw, 30), cid) for i, cid in enumerate(chapters)]
        order = self.app.data.config["difficulty_order"]
        self.diff_rects = [(pygame.Rect(PANEL_RECT.x + i * 126, 60, 118, 30), d) for i, d in enumerate(order)]

    def _pick_chapter(self, cid, diff=None):
        prof = self.app.profile
        if not prof.chapter_unlocked(cid):
            return
        if prof.set_chapter(cid, diff):
            self._layout()

    def region_at(self, p):
        for rid, c in self.pos.items():
            if math.dist(c, p) <= REGION_R + 4:
                return rid
        return None

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.mouse = ev.pos
            rid = self.region_at(ev.pos)
            if rid:
                if rid == self.selected and self.app.profile.lock_reason(rid) is None:
                    self.app.start_expedition(rid)   # повторный клик — в путь
                else:
                    self.selected = rid
            elif self.go_rect.collidepoint(ev.pos):
                self._go()
            elif self.heroes_rect.collidepoint(ev.pos):
                self._open("heroes")
            elif self.camp_rect.collidepoint(ev.pos):
                self._open("camp")
            else:
                for r, cid in self.chapter_rects:
                    if r.collidepoint(ev.pos):
                        self._pick_chapter(cid)
                for r, d in self.diff_rects:
                    if r.collidepoint(ev.pos) and self.app.profile.difficulty_unlocked(self.app.profile.biome_id, d):
                        self._pick_chapter(self.app.profile.biome_id, d)
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_RETURN:
                self._go()
            elif ev.key == pygame.K_ESCAPE:
                self.app.to_hub()
            elif ev.key == pygame.K_h:
                self._open("heroes")
            elif ev.key == pygame.K_l:
                self._open("camp")

    def _open(self, which):
        from game.meta_scenes import CampScene, HeroesScene
        self.app.switch(HeroesScene(self.app) if which == "heroes" else CampScene(self.app))

    def _go(self):
        if self.selected and self.app.profile.lock_reason(self.selected) is None:
            self.app.start_expedition(self.selected)

    def update(self, dt):
        self.clock += dt

    # ---------- отрисовка ----------

    def draw(self, surf):
        prof = self.app.profile
        surf.fill(T.BG)
        n = prof.biome.get("order", 0) + 1
        T.text(surf, f"Глава {n}: {prof.biome['name']}", (24, 14), 30, T.TEXT, True)
        amber = f"Янтарь: {prof.amber}"
        T.text(surf, amber, (T.SCREEN_W - 30 - T.font(22, True).size(amber)[0], 18), 22, AMBER, True)
        free = sum(meta.points_free(self.app.data, h) for h in prof.heroes.values())
        W.button(surf, self.heroes_rect, "Герои (H)" + (f" · {free}" if free else ""), self.mouse,
                 accent=(170, 140, 255))
        W.button(surf, self.camp_rect, "Лагерь (L)", self.mouse, accent=AMBER)
        self.tip = None
        self._draw_chapters(surf)
        T.text(surf, prof.biome["desc"], (24, 100), 14, T.TEXT_DIM)

        pygame.draw.rect(surf, (24, 30, 28), MAP_RECT, border_radius=12)
        pygame.draw.rect(surf, T.PANEL_EDGE, MAP_RECT, 1, border_radius=12)
        avail = set(prof.available())
        drawn = set()
        for r in prof.biome["regions"]:
            for link in r["links"]:
                key = frozenset((r["id"], link))
                if key in drawn:
                    continue
                drawn.add(key)
                both = r["id"] in prof.captured and link in prof.captured
                one = r["id"] in prof.captured or link in prof.captured
                col = CAPTURED if both else (110, 140, 170) if one else (55, 62, 70)
                pygame.draw.line(surf, col, self.pos[r["id"]], self.pos[link], 4 if one else 2)
        for r in prof.biome["regions"]:
            self._draw_region(surf, r, r["id"] in avail)
        self._draw_mechanics(surf)
        self._draw_panel(surf)
        self._draw_footer(surf)
        if self.tip:
            lines = T.wrap(self.tip, 14, 360)
            w = max(T.font(14).size(s)[0] for s in lines) + 16
            box = pygame.Rect(min(self.mouse[0] + 14, T.SCREEN_W - w - 8), self.mouse[1] + 18, w, len(lines) * 18 + 10)
            pygame.draw.rect(surf, (12, 14, 18), box, border_radius=6)
            pygame.draw.rect(surf, T.PANEL_EDGE, box, 1, border_radius=6)
            for i, s in enumerate(lines):
                T.text(surf, s, (box.x + 8, box.y + 5 + i * 18), 14, T.TEXT)

    def _draw_chapters(self, surf):
        prof, data = self.app.profile, self.app.data
        for r, cid in self.chapter_rects:
            b = data.biomes[cid]
            open_ = prof.chapter_unlocked(cid)
            sel = cid == prof.biome_id
            pygame.draw.rect(surf, (52, 56, 68) if sel else (34, 36, 44), r, border_radius=6)
            pygame.draw.rect(surf, T.SELECT if sel else (T.PANEL_EDGE if open_ else (50, 50, 56)), r, 2,
                             border_radius=6)
            label = f"{b.get('order', 0) + 1}. {b['name']}"
            T.text(surf, label if T.font(12, True).size(label)[0] < r.w - 22 else f"{b.get('order', 0) + 1}. "
                   f"{b['name'][:9]}…", (r.x + 6, r.y + 7), 12, T.TEXT if open_ else T.TEXT_DIM, True)
            done = [d for d in data.config["difficulty_order"] if prof.done(cid, d)]
            for i, d in enumerate(done):                       # точки: пройдена на сложности
                pygame.draw.circle(surf, DIFF_COLORS[d], (r.right - 8 - i * 7, r.y + 8), 3)
            if not open_:
                pygame.draw.line(surf, (90, 90, 96), (r.right - 14, r.bottom - 10), (r.right - 6, r.bottom - 10), 2)
            if r.collidepoint(self.mouse):
                self.tip = b["name"] + (": " + " · ".join(b.get("mechanics", [])) if open_ else
                                        " — откроется после победы над боссом предыдущей главы")
        for r, d in self.diff_rects:
            cfg = data.config["difficulties"][d]
            ok = prof.difficulty_unlocked(prof.biome_id, d)
            sel = d == prof.difficulty
            col = DIFF_COLORS[d]
            pygame.draw.rect(surf, T.mix(col, (0, 0, 0), 0.6) if sel else (34, 36, 44), r, border_radius=6)
            pygame.draw.rect(surf, col if ok else (60, 60, 66), r, 2, border_radius=6)
            mark = " ✓" if prof.done(prof.biome_id, d) else ""
            T.text(surf, cfg["name"] + mark, r.center, 14, T.TEXT if ok else T.TEXT_DIM, True, center=True)
            if r.collidepoint(self.mouse):
                adds = prof.biome.get("adds", {})
                pool = adds.get("heroic", []) + (adds.get("nightmare", []) if d == "nightmare" else [])
                names = ", ".join(dict.fromkeys(data.enemies[t]["name"] for t in pool))
                self.tip = (f"{cfg['name']}: враги HP ×{cfg['hp']:g}, урон ×{cfg['damage']:g}"
                            + (f", +{cfg['adds']} врага в бою ({names})" if cfg["adds"] else "")
                            + (f", модификаторы врагов: {cfg['affixes']}" if cfg["affixes"] else "")
                            + (", события поля чаще" if cfg["event_rate"] < 1 else "")
                            + f". Янтарь ×{cfg['amber']:g}, мастерство ×{cfg['xp']:g}"
                            + (", эпические трофеи чаще" if cfg["epic"] else "") + "."
                            + ("" if ok else " Откроется после победы над боссом главы на предыдущей сложности."))

    def _draw_mechanics(self, surf):
        mech = self.app.profile.biome.get("mechanics", [])
        if not mech:
            return
        y = MAP_RECT.bottom - 14 - 18 * len(mech) - 20
        T.text(surf, "Механики главы", (MAP_RECT.x + 16, y), 14, (255, 200, 120), True)
        for i, m in enumerate(mech):
            T.text(surf, "• " + m, (MAP_RECT.x + 16, y + 20 + i * 18), 13, (200, 205, 220))
        data, prof = self.app.data, self.app.profile
        heroes = [h["cls"] for h in data.hero_unlocks.get(prof.biome_id, [])]
        if heroes:                                # герои, которые открываются этой главой
            names = ", ".join(data.classes[c]["name"] + ("" if c in prof.unlocked else " (откроется)")
                              for c in heroes)
            T.text(surf, f"Герои главы: {names}", (MAP_RECT.x + 16, y - 22), 14, (170, 200, 255), True)

    def _draw_region(self, surf, r, available):
        prof = self.app.profile
        x, y = self.pos[r["id"]]
        captured = r["id"] in prof.captured
        base = BOSS if r.get("boss") else CAPTURED if captured else (190, 110, 70)
        col = base if available or captured else T.mix(base, (20, 22, 26), 0.6)
        rad = REGION_R + (6 if r.get("boss") else 0)
        if available and not captured:
            pulse = 4 + 3 * math.sin(self.clock * 4)
            pygame.draw.circle(surf, (120, 200, 255), (x, y), rad + 6 + pulse, 3)
        pygame.draw.circle(surf, col, (x, y), rad)
        if r["id"] == self.selected:
            pygame.draw.circle(surf, T.SELECT, (x, y), rad + 3, 3)
        elif captured:
            pygame.draw.circle(surf, (210, 255, 220), (x, y), rad, 2)
        mark = "!" if r.get("boss") else str(r["threat"])
        T.text(surf, mark, (x, y), 24, (255, 255, 255), True, center=True, shadow=True)
        # подложка, чтобы линии связей не перечёркивали подпись
        lw = T.font(15, True).size(r["name"])[0] + 12
        pygame.draw.rect(surf, (24, 30, 28), (x - lw / 2, y + rad + 3, lw, 40), border_radius=6)
        T.text(surf, r["name"], (x, y + rad + 14), 15, T.TEXT if available or captured else T.TEXT_DIM, True,
               center=True)
        sub = "захвачен" if captured else "босс" if r.get("boss") else f"угроза {r['threat']}"
        col = CAPTURED if captured else T.TEXT_DIM
        if prof.mode == "stats":                  # режим героев: уровень региона против уровня отряда
            lvl = prof.region_level(r["id"])
            sub = f"ур. {lvl}" + (" · взят" if captured else "")
            col = stats.level_color(lvl - prof.squad_level())
        T.text(surf, sub, (x, y + rad + 32), 13, col, True, center=True)

    def _draw_panel(self, surf):
        prof, data = self.app.profile, self.app.data
        pygame.draw.rect(surf, T.PANEL, PANEL_RECT, border_radius=12)
        pygame.draw.rect(surf, T.PANEL_EDGE, PANEL_RECT, 1, border_radius=12)
        if not self.selected:
            return
        if self.selected not in {r["id"] for r in prof.biome["regions"]}:
            return
        r = prof.region(self.selected)
        x, y, w = PANEL_RECT.x + 16, PANEL_RECT.y + 14, PANEL_RECT.w - 32
        T.text(surf, r["name"], (x, y), 24, T.TEXT, True)
        y += 34
        kind = "Логово босса" if r.get("boss") else f"Угроза {r['threat']}"
        if prof.mode == "stats":
            kind += f" · уровень врагов {prof.region_level(r['id'])} (отряд {prof.squad_level()})"
        T.text(surf, f"{kind}  ·  вылазка из {len(r['layers'])} шагов", (x, y), 15, T.TEXT_DIM)
        y += 22
        key = (r["id"], prof.biome_id, prof.difficulty)
        if getattr(self, "_scale", (None,))[0] != key:
            from sim.run import Run
            self._scale = (key, Run(data, 0, r, {}, None, prof.biome_id, prof.difficulty).enemy_scale())
        scale = self._scale[1]
        if scale["hp"] > 1.001:
            T.text(surf, f"Враги: HP +{round((scale['hp'] - 1) * 100)}%, урон +{round((scale['damage'] - 1) * 100)}%",
                   (x, y), 14, (255, 150, 120))
            y += 20
        y += 8
        enc = next(e for e in data.encounters if e["id"] == r["guard"])
        T.text(surf, f"{'Босс' if r.get('boss') else 'Страж'}: {enc['name']}", (x, y), 16, (230, 130, 80), True)
        y += 24
        counts = {}
        for e in enc["enemies"]:
            name = data.enemies[e["type"]]["name"]
            counts[name] = counts.get(name, 0) + 1
        for name, k in counts.items():
            T.text(surf, f"  {name}" + (f" ×{k}" if k > 1 else ""), (x, y), 14, T.TEXT)
            y += 19
        y += 12
        b = r.get("bonus")
        captured = r["id"] in prof.captured
        if b:
            T.text(surf, f"Бонус захвата: {b['name']}" + ("  (получен)" if captured else ""), (x, y), 16,
                   CAPTURED, True)
            y += 22
            for line in T.wrap(b["desc"], 14, w):
                T.text(surf, line, (x, y), 14, T.TEXT)
                y += 18
            y += 8
        c = prof.cfg
        reward = c["amber_boss"] if r.get("boss") else c["amber_capture"] + c["amber_per_threat"] * r["threat"]
        reward = int(round(reward * prof.reward_mult()))
        if captured:
            reward = int(reward * c["replay_mult"])
        per = int(round(c["amber_per_battle"] * prof.reward_mult()))
        T.text(surf, f"Янтарь: {reward} за победу + {per} за каждый бой", (x, y), 14, AMBER)
        y += 20
        if captured:
            T.text(surf, "Повторная зачистка: награда меньше, бонус уже есть", (x, y), 13, T.TEXT_DIM)
            y += 18
        reason = prof.lock_reason(r["id"])
        if reason:
            for line in T.wrap(reason, 14, w):
                T.text(surf, line, (x, self.go_rect.y - 26), 14, (255, 150, 120))
        W.button(surf, self.go_rect, "В вылазку (Enter)", self.mouse, reason is None)

    def _draw_footer(self, surf):
        prof = self.app.profile
        y = MAP_RECT.bottom + 16
        bonuses = prof.region_bonuses()
        T.text(surf, "Бонусы регионов:", (24, y), 16, T.TEXT_DIM, True)
        x = 24 + T.font(16, True).size("Бонусы регионов:")[0] + 12
        if not bonuses:
            T.text(surf, "пока нет — захватите регион, победив его стража", (x, y + 1), 15, T.TEXT_DIM)
        if len(bonuses) < 6:
            label = "   ·   ".join(f"{b['name']}: {b['desc']}" for b in bonuses)
        else:
            label = f"{len(bonuses)} бонусов: " + ", ".join(b["name"] for b in bonuses)
        for line in T.wrap(label, 14, T.SCREEN_W - x - 24)[:2]:
            T.text(surf, line, (x, y + 1), 14, CAPTURED)
            y += 19
        reg = len(prof.regular_captured())
        stats = (f"Захвачено регионов: {reg}   ·   вылазок: {prof.expeditions}   ·   успешных: {prof.victories}"
                 + ("   ·   глава пройдена на этой сложности" if prof.biome_done else ""))
        T.text(surf, stats, (24, T.SCREEN_H - 34), 14, T.TEXT_DIM)
        T.text(surf, "Клик по региону — выбрать, повторный клик или Enter — в вылазку. H — герои, L — улучшения "
                     "лагеря, Esc — в лагерь.", (24, T.SCREEN_H - 58), 14, T.TEXT_DIM)
