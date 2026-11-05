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

    def relayout(self):
        """Окно изменилось: костёр по центру, фон перерисовать; подклассы пересчитывают кнопки."""
        self.camp.relayout()

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
        if prof.mode == "story":
            self.has_progress = bool(prof.done or prof.expeditions)
        elif prof.mode in ("expedition", "solo"):
            self.has_progress = bool(prof.runs or prof.run_state or prof.upgrades)
        self.relayout()

    def relayout(self):
        super().relayout()
        prof = self.app.profile
        x = T.content_ox() + 110
        self.buttons = []
        y = 290
        if getattr(self.app, "launcher", "legacy") == "main":      # main.py: только Экспедиция и Одиночка
            other = story = None
            exped = ("expedition", "Экспедиция: поход отряда") if prof.mode != "expedition" else \
                ("solo", "Одиночка: один герой")
        else:
            other = ("mode", "Основная игра") if prof.mode != "base" else ("mode", "Режим героев (статы)")
            story = ("story", "Сюжет: новое начало") if prof.mode != "story" else None
            exped = ("expedition", "Экспедиция: поход отряда") if prof.mode != "expedition" else None
        for key, label in tuple(x for x in (("continue", "Продолжить" if self.has_progress else "Начать"),
                                            ("new", "Новая игра"), exped, story, other, ("settings", "Настройки"),
                                            ("quit", "Выход")) if x):
            if key == "new" and not self.has_progress:
                continue
            self.buttons.append((pygame.Rect(x, y, 300, 50), key, label))
            y += 62
        self.panel_rect = pygame.Rect(T.content_ox() + 85, 270, 350, 20 + 62 * len(self.buttons))

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
        elif key == "mode":
            self.app.switch_mode("base" if self.app.profile.mode != "base" else "stats")
            self.app.to_title()
        elif key == "story":
            self.app.switch_mode("story")
            self.app.to_title()
        elif key == "expedition":
            self.app.switch_mode("expedition")
            self.app.to_title()
        elif key == "solo":
            self.app.switch_mode("solo")
            self.app.to_title()
        elif key == "settings":
            self.app.switch(SettingsScene(self.app, back=self.app.to_title))
        elif key == "quit":
            self.app.quit = True

    def draw_ui(self, surf):
        title = self.app.data.config.get("title", "Хроники янтаря")
        T.text(surf, title, (T.SCREEN_W // 2, 130), 64, GOLD, True, center=True, shadow=True)
        sub = {"stats": "РЕЖИМ ГЕРОЕВ: уровни, атрибуты, скейлы навыков",
               "story": "СЮЖЕТ: отряд собирается в пути · обучение механикам",
               "expedition": "ЭКСПЕДИЦИЯ: таверна · главы из трёх актов · отряд, события, снаряжение",
               "solo": "ОДИНОЧКА: один герой · те же главы · камера за героем, шесть навыков"}.get(
            self.app.profile.mode, "тактический бой · вылазки · герои")
        T.text(surf, sub, (T.SCREEN_W // 2, 192), 20,
               (150, 200, 255) if self.app.profile.mode == "stats" else (220, 210, 190), center=True, shadow=True)
        self.panel(surf, self.panel_rect)
        for r, key, label in self.buttons:
            accent = (255, 120, 100) if key == "new" and self.confirm_new else GOLD
            W.button(surf, r, label, self.mouse, accent=accent)
        prof = self.app.profile
        if self.has_progress:
            if prof.mode == "expedition":
                info = (f"Слава {prof.glory} · походов {prof.runs} · побед {prof.wins}"
                        + (" · поход не окончен" if prof.run_state else ""))
            else:
                info = (f"Янтарь {prof.amber} · регионов захвачено {len(prof.captured)} · "
                        f"героев {len(prof.unlocked)} из {len(self.app.data.classes)}")
            T.text(surf, info, (T.content_ox() + 260, 300 + 62 * len(self.buttons)), 15, (200, 200, 210),
                   center=True, shadow=True)
        self.draw_toast(surf, T.SCREEN_H - 40)
        T.text(surf, "Enter — продолжить · Esc — выход", (T.SCREEN_W // 2, T.SCREEN_H - 18), 13, T.TEXT_DIM,
               center=True)


class MainTitleScene(TitleScene):
    """Главный экран main.py: фон плавно сменяет иллюстрации глав (медленный наезд камеры), слева — меню в стиле
    «янтарь и тёмное дерево», внизу — что ждёт в таверне (слава, трофеи, ветераны) и какая глава на фоне."""

    SHOW = 7.0                    # сек на картинку
    FADE = 1.6                    # сек перехода

    def __init__(self, app):
        from ui.vfx import VfxWorld
        self._vfx = VfxWorld()
        self.t = 0.0
        self.slides = self._slides(app)
        self._cache = {}
        super().__init__(app)

    @property
    def vfx(self):
        return self._vfx

    @staticmethod
    def _slides(app):
        """Иллюстрации актов всех глав по порядку: (id картинки, подпись)."""
        from sim import expedition as X
        xd = app.profile.xd
        out = []
        for cid, meta in sorted(xd.get("chapters", {}).items(), key=lambda kv: kv[1].get("order", 0)):
            for i, a in enumerate(X.chapter_view(xd, cid)["acts"]):
                out.append((a.get("art", f"act_{i}"), f"{meta['name']} · {a['name']}"))
        return out or [("tavern", "")]

    def update(self, dt):
        self.t += dt
        if self.toast:
            self.toast = (self.toast[0], self.toast[1] - dt) if self.toast[1] > dt else None

    def relayout(self):
        prof = self.app.profile
        x, y = 70, 300
        self.buttons = []
        items = [("continue", "Продолжить" if self.has_progress else "Начать")]   # отряд или одиночка — в таверне
        if self.has_progress:
            items.append(("new", "Новая игра"))
        items += [("settings", "Настройки"), ("quit", "Выход")]
        for key, label in items:
            self.buttons.append((pygame.Rect(x, y, 340, 50), key, label))
            y += 60
        self.panel_rect = pygame.Rect(x - 24, 280, 388, 20 + 60 * len(self.buttons))

    def _image(self, iid, size):
        key = (iid, size)
        if key not in self._cache:
            from ui import illustrations as IL
            self._cache[key] = IL.get(iid, "act", size, hd=True)
            if len(self._cache) > 6:
                self._cache.pop(next(iter(self._cache)))
        return self._cache[key]

    def _slide(self, surf, i, alpha, phase):
        """Картинка i на весь экран с наездом (phase 0..1 — время показа); alpha — прозрачность."""
        iid, _ = self.slides[i % len(self.slides)]
        w = T.SCREEN_W
        h = max(T.SCREEN_H, w * 2 // 3)
        z = 1.06
        img = self._image(iid, (int(w * z), int(h * z)))
        dx = (img.get_width() - w) * (0.15 + 0.7 * phase)        # камера медленно едет вбок
        dy = (img.get_height() - T.SCREEN_H) * (0.6 - 0.3 * phase)
        if alpha >= 255:
            surf.blit(img, (-dx, -dy))
        else:
            tmp = img.copy()
            tmp.set_alpha(alpha)
            surf.blit(tmp, (-dx, -dy))

    def _backdrop(self, surf):
        n = len(self.slides)
        period = self.SHOW
        k = int(self.t // period)
        local = self.t - k * period
        self._slide(surf, k, 255, min(1.0, (local + self.FADE) / (period + self.FADE)))
        if local > period - self.FADE and n > 1:       # следующая проступает поверх
            a = int(255 * (local - (period - self.FADE)) / self.FADE)
            self._slide(surf, k + 1, a, (local - (period - self.FADE)) / (period + self.FADE))
        shade = pygame.Surface((T.SCREEN_W, T.SCREEN_H), pygame.SRCALPHA)
        for x in range(0, T.SCREEN_W, 8):                # тёмный край слева под меню, справа светлее
            a = int(190 * max(0.0, 1 - x / (T.SCREEN_W * 0.62)) + 40)
            shade.fill((10, 7, 5, a), (x, 0, 8, T.SCREEN_H))
        surf.blit(shade, (0, 0))
        band = pygame.Surface((T.SCREEN_W, 120), pygame.SRCALPHA)
        band.fill((8, 6, 4, 150))
        surf.blit(band, (0, T.SCREEN_H - 120))
        self.caption = self.slides[k % n][1]

    def draw_layers(self, world, ui, units=None):
        self._backdrop(world)
        if units is not None:
            units.fill((0, 0, 0, 0))
        self.draw_ui(ui)

    def draw(self, surf):
        self._backdrop(surf)
        self.draw_ui(surf)

    def draw_ui(self, surf):
        prof = self.app.profile
        title = self.app.data.config.get("title", "Хроники янтаря")
        T.text(surf, title, (70, 120), 72, (255, 196, 96), True, shadow=True)
        sub = "Таверна, главы из трёх актов, события и снаряжение — отрядом или в одиночку"
        T.text(surf, sub, (74, 206), 18, (230, 214, 180), shadow=True)
        pygame.draw.line(surf, T.AMBER, (74, 240), (520, 240), 2)
        T.frame(surf, self.panel_rect, 210, accent=T.AMBER_DIM)
        for r, key, label in self.buttons:
            hot = r.collidepoint(self.mouse)
            main = key == "continue"
            accent = (255, 120, 100) if key == "new" and self.confirm_new else (T.AMBER if main or hot else T.AMBER_DIM)
            T.frame(surf, r, 235, accent=accent, corners=main, corner=T.AMBER,
                    fill=T.mix(T.PANEL, T.AMBER, 0.22 if hot else (0.1 if main else 0.0)))
            T.text(surf, ("›  " if hot else "") + label, (r.x + 20, r.y + 14), 19 if main else 18,
                   (255, 236, 200) if hot or main else T.TEXT, True)
        # что ждёт в таверне
        chips = []
        if hasattr(prof, "glory"):
            chips.append((f"Слава {prof.glory}", (255, 196, 96)))
            for k, t in prof.xd.get("trophies", {}).items():
                if prof.trophies.get(k):
                    chips.append((f"{t['name']} {prof.trophies[k]}", tuple(t["color"])))
            vets = sum(1 for h in prof.roster if getattr(h, "vet", None))   # все ветераны таверны, обоих режимов
            if vets:
                chips.append((f"Ветеранов в таверне: {vets}", (150, 220, 170)))
            if getattr(prof, "wins", 0):
                chips.append((f"Побед: {prof.wins}", T.TEXT))
            if prof.run_state:
                chips.append(("Поход не окончен — продолжить", (150, 200, 255)))
        x = 46
        for label, col in chips:
            w = T.font(15, True).size(label)[0] + 22
            r = pygame.Rect(x, T.SCREEN_H - 92, w, 30)
            T.frame(surf, r, 220, accent=col, corners=False, radius=6)
            T.text(surf, label, (r.x + 11, r.y + 6), 15, col, True)
            x += w + 8
        cap = getattr(self, "caption", "")
        if cap:
            T.text(surf, cap, (T.SCREEN_W - 30 - T.font(15).size(cap)[0], T.SCREEN_H - 86), 15, (230, 214, 180),
                   shadow=True)
        self.draw_toast(surf, T.SCREEN_H - 130)
        T.text(surf, "Enter — продолжить · Esc — выход · F11 — полный экран", (46, T.SCREEN_H - 40), 13,
               T.TEXT_DIM)


class SettingsScene(CampBackdrop):
    def __init__(self, app, back):
        super().__init__(app)
        self.back_fn = back
        self.relayout()

    def relayout(self):
        super().relayout()
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
                    if key == "window":
                        from ui import display
                        if display.CURRENT:
                            display.CURRENT.apply()
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
            pygame.draw.rect(surf, (70, 52, 34) if hot else (46, 35, 26), r, border_radius=8)
            pygame.draw.rect(surf, GOLD if hot else T.PANEL_EDGE, r, 2, border_radius=8)
            T.text(surf, name, (r.x + 16, r.y + 12), 18, T.TEXT, True)
            val = S.label(key)
            T.text(surf, val, (r.right - 16 - T.font(18, True).size(val)[0], r.y + 12), 18, GOLD, True)
        W.button(surf, self.back, "Готово (Esc)", self.mouse, accent=GOLD)
        T.text(surf, "Клик по строке меняет значение. Сохраняется сразу.", (T.SCREEN_W // 2, T.SCREEN_H - 30), 14,
               T.TEXT_DIM, center=True)
