"""Сцены сюжета (sim/story.py): диалоги с портретами, лагерь, торговец, переходы между боями цепочки.

Поток вылазки: вступление (диалог) → бой 1 (реплики перед боем, обучение) → передышка → бой 2 … → итог
(янтарь, трофей на выбор) → эпилог (диалог) → лагерь.
"""
import pygame

from game.title_scene import GOLD, CampBackdrop
from ui import theme as T
from ui import widgets as W
from ui.sprites import DRAWERS, SpriteBank

AMBER = (255, 190, 90)
_BANK = SpriteBank()


def portrait(data, story, who, size=128):
    """Портрет говорящего: фигурка героя или врага (из спрайтов игры), увеличенная без сглаживания."""
    ch = story["characters"].get(who, {})
    key = ch.get("sprite", who)
    proto = data.classes.get(key) or data.enemies.get(key)
    if proto is None:
        return None
    look = proto.get("look")
    kind = key if key in DRAWERS or look else proto.get("role", "melee")
    img = _BANK.get([proto.get("path"), key], kind, tuple(proto.get("color", (200, 200, 200))),
                    bool(proto.get("boss")), False, False, look)
    k = size / max(img.get_size())
    return pygame.transform.scale(img, (int(img.get_width() * k), int(img.get_height() * k)))


class DialogScene(CampBackdrop):
    """Реплики по одной: Enter / Пробел / клик — дальше, Esc — пропустить сцену. then() — после последней."""

    def __init__(self, app, lines, then, title=None):
        super().__init__(app)
        self.lines = [ln for ln in lines if ln.get("text")]
        self.then = then
        self.title = title
        self.i = 0
        self.age = 0.0
        self.story = app.profile.story
        self._por = {}
        if not self.lines:
            then()

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1) or \
                (ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE):
            self.next()
        elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.i = len(self.lines) - 1
            self.age = 999.0                      # пропуск — сразу, без допечатывания
            self.next()

    def next(self):
        line = self.lines[self.i] if self.i < len(self.lines) else None
        if line and self.age * 60 < len(line["text"]):        # текст ещё печатается — сначала показать целиком
            self.age = 999.0
            return
        self.i += 1
        self.age = 0.0
        if self.i >= len(self.lines):
            self.then()

    def update(self, dt):
        super().update(dt)
        self.age += dt

    def draw_ui(self, surf):
        if self.title:
            T.text(surf, self.title, (T.SCREEN_W // 2, 60), 34, GOLD, True, center=True, shadow=True)
        if self.i >= len(self.lines):
            return
        line = self.lines[self.i]
        who = line.get("who", "narrator")
        ch = self.story["characters"].get(who, {"name": who, "color": (220, 220, 220)})
        r = pygame.Rect(60, T.SCREEN_H - 230, T.SCREEN_W - 120, 190)
        self.panel(surf, r, 215)
        x = r.x + 24
        if who != "narrator":
            if who not in self._por:
                self._por[who] = portrait(self.app.profile.data, self.story, who)
            por = self._por[who]
            if por is not None:
                pr = por.get_rect(midbottom=(r.x + 100, r.bottom - 16))
                surf.blit(por, pr)
                x = r.x + 200
            T.text(surf, ch["name"], (x, r.y + 18), 22, tuple(ch["color"]), True, shadow=True)
        shown = line["text"][:int(self.age * 60)]
        for k, ln in enumerate(T.wrap(shown, 20, r.right - x - 30)):
            T.text(surf, ln, (x, r.y + (56 if who != "narrator" else 30) + 28 * k), 20,
                   (225, 222, 210) if who != "narrator" else (205, 200, 185))
        T.text(surf, f"{self.i + 1}/{len(self.lines)}   Пробел — дальше · Esc — пропустить",
               (r.right - 330, r.bottom - 26), 13, T.TEXT_DIM)


class StoryHub(CampBackdrop):
    """Лагерь сюжета: в путь (следующая вылазка), отряд, подготовка героев, торговец, кузница, меню."""

    def __init__(self, app):
        super().__init__(app)
        prof = app.profile
        self.camp.set_heroes(prof.squad)
        self.exp = prof.current()
        x, y = T.SCREEN_W - 380, 130
        self.buttons = []
        go = f"В путь: {self.exp['name']}" if self.exp else "Продолжение следует…"
        from sim import stats
        free = sum(stats.points_free(app.data, prof.heroes[c]["rpg"]) for c in prof.unlocked)
        heroes = "Подготовка героев  (H)" + (f" · очков {free}" if free else "")
        for key, label in (("go", go), ("roster", "Отряд и расстановка  (O)"), ("heroes", heroes),
                           ("shop", "Торговец  (T)"), ("forge", "Кузница: улучшения лагеря  (K)"),
                           ("menu", "Главное меню  (Esc)")):
            self.buttons.append((pygame.Rect(x, y, 350, 52), key, label))
            y += 62
        self.keys = {pygame.K_RETURN: "go", pygame.K_o: "roster", pygame.K_h: "heroes", pygame.K_t: "shop",
                     pygame.K_k: "forge", pygame.K_ESCAPE: "menu"}

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for r, key, _ in self.buttons:
                if r.collidepoint(ev.pos):
                    self.act(key)
                    return
        elif ev.type == pygame.KEYDOWN and ev.key in self.keys:
            self.act(self.keys[ev.key])

    def act(self, key):
        app = self.app
        if key == "go":
            if self.exp:
                app.story_go()
        elif key == "roster":
            from game.squad_scene import SquadScene
            app.switch(SquadScene(app))
        elif key == "heroes":
            from game.meta_scenes import HeroesScene
            app.switch(HeroesScene(app))
        elif key == "shop":
            app.switch(StoryShop(app))
        elif key == "forge":
            from game.meta_scenes import CampScene
            app.switch(CampScene(app))
        elif key == "menu":
            app.to_title()

    def draw_ui(self, surf):
        prof = self.app.profile
        T.text(surf, "Лагерь", (28, 18), 40, GOLD, True, shadow=True)
        amber = f"Янтарь: {prof.amber}"
        T.text(surf, amber, (T.SCREEN_W - 30 - T.font(24, True).size(amber)[0], 24), 24, AMBER, True, shadow=True)
        if self.exp:
            T.text(surf, self.exp["chapter_name"], (30, 74), 22, (225, 215, 190), True, shadow=True)
            n = len(self.exp["battles"])
            join = self.exp.get("join")
            sub = f"Следующая вылазка: «{self.exp['name']}» — {n} боя подряд, враги ур. {self.exp.get('level', 1)}"
            if join:
                sub += f" · присоединится {prof.character(join)['name']}"
            T.text(surf, sub, (30, 106), 17, (200, 196, 185), shadow=True)
        self.panel(surf, pygame.Rect(T.SCREEN_W - 396, 114, 382, 62 * len(self.buttons) + 16))
        for r, key, label in self.buttons:
            W.button(surf, r, label, self.mouse, enabled=key != "go" or self.exp is not None,
                     accent=GOLD if key == "go" else (170, 160, 210))
        y = T.SCREEN_H - 120
        self.panel(surf, pygame.Rect(16, y - 12, 6 * 150 + 12, 100), 150)
        for i, c in enumerate(prof.squad):
            lvl = prof.level(c)
            T.text(surf, prof.character(c)["name"], (28 + i * 150, y), 17, tuple(prof.character(c)["color"]), True)
            T.text(surf, f"{self.app.data.classes[c]['name']} · ур. {lvl}", (28 + i * 150, y + 24), 14, T.TEXT_DIM)
        T.text(surf, f"В отряде {len(prof.squad)} из {prof.squad_size()} · союзников {len(prof.unlocked)}",
               (28, y + 56), 14, T.TEXT_DIM)
        self.draw_toast(surf, T.SCREEN_H - 150)


class StoryShop(CampBackdrop):
    """Торговец: предметы за янтарь — навсегда в арсенал; надеть — в «Подготовке героев»."""

    def __init__(self, app):
        super().__init__(app)
        self.rects = []
        self.back = pygame.Rect(T.SCREEN_W // 2 - 110, T.SCREEN_H - 64, 220, 46)

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.back.collidepoint(ev.pos):
                self.app.to_hub()
                return
            for r, iid in self.rects:
                if r.collidepoint(ev.pos):
                    if self.app.profile.buy(iid):
                        self.say(f"Куплено: {self.app.data.items[iid]['name']} — в арсенале")
                    else:
                        self.say("Не хватает янтаря")
                    return
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_RETURN):
            self.app.to_hub()

    def draw_ui(self, surf):
        prof = self.app.profile
        T.text(surf, "Торговец", (28, 18), 40, GOLD, True, shadow=True)
        amber = f"Янтарь: {prof.amber}"
        T.text(surf, amber, (T.SCREEN_W - 30 - T.font(24, True).size(amber)[0], 24), 24, AMBER, True, shadow=True)
        T.text(surf, "Купленное остаётся в арсенале навсегда. Надеть — «Подготовка героев».", (30, 76), 16,
               T.TEXT_DIM, shadow=True)
        self.rects = []
        stock = prof.shop_stock()[:15]
        for k, (iid, it) in enumerate(stock):
            r = pygame.Rect(30 + (k % 3) * 410, 110 + (k // 3) * 112, 396, 100)
            self.rects.append((r, iid))
            self.panel(surf, r, 200 if r.collidepoint(self.mouse) else 160)
            price = it.get("price", 50)
            T.text(surf, it["name"], (r.x + 14, r.y + 10), 18, (255, 225, 160) if it["rarity"] != "common"
                   else (230, 228, 220), True)
            T.text(surf, f"{price}", (r.right - 60, r.y + 10), 18, AMBER if prof.amber >= price else (200, 90, 80),
                   True)
            for j, ln in enumerate(T.wrap(it.get("desc", ""), 14, r.w - 28)[:3]):
                T.text(surf, ln, (r.x + 14, r.y + 38 + 18 * j), 14, T.TEXT_DIM)
        if not stock:
            T.text(surf, "Всё раскуплено. Загляните после следующей главы.", (30, 120), 18, T.TEXT_DIM)
        W.button(surf, self.back, "Назад в лагерь", self.mouse)
        self.draw_toast(surf, T.SCREEN_H - 90)


class BetweenScene(CampBackdrop):
    """Передышка между боями цепочки: отряд подлечен, следующий бой — по кнопке."""

    def __init__(self, app, summary, then):
        super().__init__(app)
        self.summary, self.then = summary, then
        self.btn = pygame.Rect(T.SCREEN_W // 2 - 140, T.SCREEN_H - 120, 280, 54)

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.btn.collidepoint(ev.pos)) or \
                (ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE):
            self.then()

    def draw_ui(self, surf):
        run = self.app.run
        n = len(run.nodes)
        T.text(surf, f"Бой {run.battles_won} из {n} выигран", (T.SCREEN_W // 2, 70), 34, GOLD, True, center=True,
               shadow=True)
        T.text(surf, "Короткая передышка: раны перевязаны, можно перестроиться перед следующим боем.",
               (T.SCREEN_W // 2, 116), 17, (210, 205, 190), center=True, shadow=True)
        r = pygame.Rect(T.SCREEN_W // 2 - 380, 160, 760, 64 + 34 * len(run.squad))
        self.panel(surf, r)
        prof = self.app.profile
        for i, m in enumerate(run.squad):
            y = r.y + 24 + 34 * i
            mx = run.max_hp(m)
            T.text(surf, f"{prof.character(m.cls)['name']} ({self.app.data.classes[m.cls]['name']}) · ур. {m.level}",
                   (r.x + 24, y), 17, tuple(prof.character(m.cls)["color"]), True)
            w = 260
            pygame.draw.rect(surf, (30, 30, 34), (r.right - w - 30, y + 4, w, 14), border_radius=4)
            pygame.draw.rect(surf, (110, 210, 120), (r.right - w - 30, y + 4, int(w * m.hp / max(1, mx)), 14),
                             border_radius=4)
            T.text(surf, f"{m.hp}/{mx}", (r.right - w - 110, y), 15, T.TEXT_DIM)
        W.button(surf, self.btn, "Следующий бой  (Пробел)", self.mouse, accent=GOLD)
