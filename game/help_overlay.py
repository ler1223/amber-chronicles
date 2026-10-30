"""Справка-обучение поверх окна: страницы по одной, каждая может переключить вкладку окна, о которой рассказывает.
Пробел / клик — дальше, Backspace — назад, Esc — закрыть."""
import pygame

from ui import theme as T

GOLD = (255, 205, 110)

HERO_PAGES = [
    {"window": "overview", "title": "Окно героя",
     "text": ["Здесь готовят героя к бою. Слева — отряд: переключение кликом, клавишами 1–9 или Tab.",
              "Сверху — вкладки (F1–F4): обзор и путь, способности, таланты и снаряжение, характеристики.",
              "Всё, что выбрано здесь, сохраняется и действует в каждом бою."]},
    {"window": "overview", "title": "Обзор и путь",
     "text": ["Обзор: здоровье, броня, атака (урон, дальность, скорость), AP и личная шкала героя.",
              "AP — синие пипсы под героем в бою: копятся со временем и тратятся на навыки.",
              "Путь — специализация героя: меняет набор навыков и пассивное умение. Выбирается здесь же."]},
    {"window": "skills", "title": "Способности",
     "text": ["У героя три навыка (в бою — Q, W, E). У навыка: цена в AP, перезарядка, время каста, дальность.",
              "Каждый навык улучшается по одной из двух веток — A или B, у ветки две ступени. Ветки меняют сам навык:",
              "площадь, эффект, иногда — способ применения. Цена — очки подготовки.",
              "Справа — живой пример навыка на манекенах. ПКМ по ступени — посмотреть её, не покупая. Пробел — повтор."]},
    {"window": "talents", "title": "Таланты и снаряжение",
     "text": ["Таланты — постоянные усиления героя за очки подготовки. Очки даёт мастерство: оно растёт за бои.",
              "Снаряжение — предметы из арсенала лагеря (торговец и трофеи вылазок). У каждого предмета свой слот.",
              "Один предмет носит один герой; снять и переложить можно в любой момент."]},
    {"window": "stats", "title": "Характеристики",
     "text": ["Уровень героя растёт от опыта за бои — навсегда. Каждый уровень сам немного усиливает героя",
              "и даёт свободные очки атрибутов. Распределите их здесь:",
              "  Сила — здоровье, урон ближних навыков и столкновений.",
              "  Ловкость — скорость атак, броня, крит, уклонение, урон стрел.",
              "  Интеллект — урон заклинаний и реакций, лечение и щиты, восстановление AP.",
              "Навык усиливается от своего атрибута: удар — Силой, выстрел — Ловкостью, магия и лечение — Интеллектом."]},
    {"window": "stats", "title": "Совет",
     "text": ["Перед вылазкой потратьте свободные очки (их число видно на кнопке «Подготовка героев» в лагере).",
              "Воину и Стражу — Сила, Лучнице и Ассасину — Ловкость, магам и Жрецу — Интеллект.",
              "В бою Ctrl + клавиша навыка включает автокаст: навык применяется сам, когда условие выполнено.",
              "Справка всегда под кнопкой «Справка (I)»."]},
]


class HelpOverlay:
    def __init__(self, pages, on_page=None, on_close=None):
        self.pages = pages
        self.i = 0
        self.on_page = on_page
        self.on_close = on_close
        self.open = True
        self._show()

    def _show(self):
        if self.on_page:
            self.on_page(self.pages[self.i])

    def close(self):
        self.open = False
        if self.on_close:
            self.on_close()

    def step(self, d):
        self.i += d
        if self.i >= len(self.pages):
            self.close()
            return
        self.i = max(0, self.i)
        self._show()

    def handle(self, ev):
        """True — событие съедено справкой."""
        if not self.open:
            return False
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_SPACE, pygame.K_RIGHT):
                self.step(1)
            elif ev.key in (pygame.K_BACKSPACE, pygame.K_LEFT):
                self.step(-1)
            elif ev.key == pygame.K_ESCAPE:
                self.close()
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN:
            self.step(1 if ev.button == 1 else -1)
            return True
        return ev.type in (pygame.MOUSEBUTTONUP, pygame.KEYUP)

    def draw(self, surf):
        if not self.open:
            return
        pg = self.pages[self.i]
        w = 820
        lines = [ln for t in pg["text"] for ln in T.wrap(t, 17, w - 48)]
        h = 92 + 25 * len(lines)
        r = pygame.Rect((T.SCREEN_W - w) // 2, T.SCREEN_H - h - 96, w, h)
        box = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(box, (14, 17, 26, 238), box.get_rect(), border_radius=12)
        pygame.draw.rect(box, (*GOLD, 200), box.get_rect(), 2, border_radius=12)
        surf.blit(box, r)
        T.text(surf, pg["title"], (r.x + 24, r.y + 16), 22, GOLD, True)
        T.text(surf, f"Справка · {self.i + 1}/{len(self.pages)}", (r.right - 150, r.y + 20), 14, T.TEXT_DIM)
        for k, ln in enumerate(lines):
            T.text(surf, ln, (r.x + 24, r.y + 54 + 25 * k), 17, (236, 232, 222))
        T.text(surf, "Пробел — дальше · Backspace — назад · Esc — закрыть", (r.x + 24, r.bottom - 28), 14,
               (255, 230, 160))
