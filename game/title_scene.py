"""Титульное меню и настройки. Фон — живой костёр (ui/campfire.py), общий с лагерем."""
import pygame

from ui import settings as S
from ui import theme as T
from ui import widgets as W

GOLD = (255, 200, 110)


class CampBackdrop:
    """Экран с костром на фоне: эффекты кладёт видеокарта (draw_layers) или CPU (draw)."""

    def __init__(self, app):
        self.app = app
        self.camp = app.campfire()
        self.mouse = (0, 0)
        self.toast = None

    @property
    def vfx(self):
        return self.camp.vfx

    def update(self, dt):
        self.camp.update(dt)
        if self.toast:
            self.toast = (self.toast[0], self.toast[1] - dt) if self.toast[1] > dt else None

    def say(self, text):
        self.toast = (text, 2.5)

    def draw(self, surf):
        self.camp.draw_cpu(surf)
        self.draw_ui(surf)

    def draw_layers(self, world, ui, units=None):
        self.camp.draw_ground(world)
        if units is None:
            self.camp.draw_units(world)
        else:
            units.fill((0, 0, 0, 0))
            self.camp.draw_units(units)
        self.draw_ui(ui)

    def panel(self, surf, rect, alpha=170):
        shade = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(shade, (14, 16, 22, alpha), shade.get_rect(), border_radius=12)
        pygame.draw.rect(shade, (*T.PANEL_EDGE, 200), shade.get_rect(), 1, border_radius=12)
        surf.blit(shade, rect)

    def draw_toast(self, surf, y):
        if self.toast:
            T.text(surf, self.toast[0], (T.SCREEN_W // 2, y), 16, (255, 160, 130), True, center=True, shadow=True)


class TitleScene(CampBackdrop):
    def __init__(self, app):
        super().__init__(app)
        prof = app.profile
        self.camp.set_heroes(prof.squad)
        self.has_progress = bool(prof.expeditions or prof.amber or prof.captured or len(prof.unlocked) > 4)
        self.confirm_new = False
        x = 110
        self.buttons = []
        y = 290
        for key, label in (("continue", "Продолжить" if self.has_progress else "Начать"),
                           ("new", "Новая игра"), ("settings", "Настройки"), ("quit", "Выход")):
            if key == "new" and not self.has_progress:
                continue
            self.buttons.append((pygame.Rect(x, y, 300, 50), key, label))
            y += 62

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.mouse = ev.pos
            for r, key, _ in self.buttons:
                if r.collidepoint(ev.pos):
                    self.act(key)
                    return
        elif ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.act("continue")
            elif ev.key == pygame.K_ESCAPE:
                self.act("quit")

    def act(self, key):
        self.camp.poke()
        if key == "continue":
            self.app.to_hub()
        elif key == "new":
            if not self.confirm_new:
                self.confirm_new = True
                self.say("Нажмите «Новая игра» ещё раз: весь прогресс (регионы, янтарь, герои) будет удалён")
                return
            self.app.new_game()
            self.app.to_hub()
        elif key == "settings":
            self.app.switch(SettingsScene(self.app, back=self.app.to_title))
        elif key == "quit":
            self.app.quit = True

    def draw_ui(self, surf):
        title = self.app.data.config.get("title", "Хроники янтаря")
        T.text(surf, title, (T.SCREEN_W // 2, 130), 64, GOLD, True, center=True, shadow=True)
        T.text(surf, "тактический бой · вылазки · герои", (T.SCREEN_W // 2, 192), 20, (220, 210, 190), center=True,
               shadow=True)
        self.panel(surf, pygame.Rect(85, 270, 350, 20 + 62 * len(self.buttons)))
        for r, key, label in self.buttons:
            accent = (255, 120, 100) if key == "new" and self.confirm_new else GOLD
            W.button(surf, r, label, self.mouse, accent=accent)
        prof = self.app.profile
        if self.has_progress:
            info = (f"Янтарь {prof.amber} · регионов захвачено {len(prof.captured)} · "
                    f"героев {len(prof.unlocked)} из {len(self.app.data.classes)}")
            T.text(surf, info, (260, 300 + 62 * len(self.buttons)), 15, (200, 200, 210), center=True,
                   shadow=True)
        self.draw_toast(surf, T.SCREEN_H - 40)
        T.text(surf, "Enter — продолжить · Esc — выход", (T.SCREEN_W // 2, T.SCREEN_H - 18), 13, T.TEXT_DIM,
               center=True)


class SettingsScene(CampBackdrop):
    def __init__(self, app, back):
        super().__init__(app)
        self.back_fn = back
        self.rows = []
        y = 230
        for key, name, _, _ in S.OPTIONS:
            self.rows.append((pygame.Rect(T.SCREEN_W // 2 - 260, y, 520, 48), key, name))
            y += 58
        self.back = pygame.Rect(T.SCREEN_W // 2 - 110, y + 16, 220, 46)

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.mouse = ev.pos
            if self.back.collidepoint(ev.pos):
                self.back_fn()
                return
            for r, key, _ in self.rows:
                if r.collidepoint(ev.pos):
                    S.cycle(key)
                    S.save()
                    if key in ("shake", "flash", "hitstop", "zoom"):   # сразу показать, как это выглядит
                        self.camp.poke()
                        self.vfx.screen_fx(shake=8, flash=0.2, hitstop=0.08, zoom=1.04, center=self.camp.fire,
                                           aberration=0.5)
                    return
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_RETURN):
            self.back_fn()

    def draw_ui(self, surf):
        T.text(surf, "Настройки", (T.SCREEN_W // 2, 150), 44, GOLD, True, center=True, shadow=True)
        self.panel(surf, pygame.Rect(T.SCREEN_W // 2 - 290, 210, 580, 60 * len(self.rows) + 100))
        for r, key, name in self.rows:
            hot = r.collidepoint(self.mouse)
            pygame.draw.rect(surf, (52, 56, 68) if hot else (36, 38, 46), r, border_radius=8)
            pygame.draw.rect(surf, GOLD if hot else T.PANEL_EDGE, r, 2, border_radius=8)
            T.text(surf, name, (r.x + 16, r.y + 12), 18, T.TEXT, True)
            val = S.label(key)
            T.text(surf, val, (r.right - 16 - T.font(18, True).size(val)[0], r.y + 12), 18, GOLD, True)
        W.button(surf, self.back, "Готово (Esc)", self.mouse, accent=GOLD)
        T.text(surf, "Клик по строке меняет значение. Сохраняется сразу.", (T.SCREEN_W // 2, T.SCREEN_H - 30), 14,
               T.TEXT_DIM, center=True)
