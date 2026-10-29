"""Лагерь-хаб — центр между вылазками: костёр с отрядом, переходы к карте биома, отряду и расстановке,
подготовке героев, улучшениям лагеря. Экран отряда — game/squad_scene.py."""
import pygame

from game.title_scene import GOLD, CampBackdrop
from sim import meta
from ui import theme as T
from ui import widgets as W

AMBER = (255, 170, 60)
ROLE = {"melee": "ближний бой", "ranged": "дальний бой", "caster": "маг", "support": "поддержка"}


class HubScene(CampBackdrop):
    def __init__(self, app):
        super().__init__(app)
        self.camp.set_heroes(app.profile.squad)
        x, y = T.SCREEN_W - 360, 120
        self.buttons = []
        for key, label, hot in (("map", "В поход: карта главы", "M"), ("roster", "Отряд и расстановка", "O"),
                                ("heroes", "Подготовка героев", "H"), ("camp", "Улучшения лагеря", "L"),
                                ("menu", "Главное меню", "Esc")):
            self.buttons.append((pygame.Rect(x, y, 330, 52), key, f"{label}  ({hot})"))
            y += 64
        self.keys = {pygame.K_m: "map", pygame.K_RETURN: "map", pygame.K_o: "roster", pygame.K_h: "heroes",
                     pygame.K_l: "camp", pygame.K_ESCAPE: "menu"}

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.mouse = ev.pos
            for r, key, _ in self.buttons:
                if r.collidepoint(ev.pos):
                    self.act(key)
                    return
        elif ev.type == pygame.KEYDOWN and ev.key in self.keys:
            self.act(self.keys[ev.key])

    def act(self, key):
        from game.meta_scenes import CampScene, HeroesScene
        app = self.app
        if key == "map":
            app.to_world()
        elif key == "roster":
            from game.squad_scene import SquadScene
            app.switch(SquadScene(app))
        elif key == "heroes":
            app.switch(HeroesScene(app))
        elif key == "camp":
            app.switch(CampScene(app))
        elif key == "menu":
            app.to_title()

    def draw_ui(self, surf):
        prof, data = self.app.profile, self.app.data
        T.text(surf, "Лагерь", (28, 18), 40, GOLD, True, shadow=True)
        amber = f"Янтарь: {prof.amber}"
        T.text(surf, amber, (T.SCREEN_W - 30 - T.font(24, True).size(amber)[0], 24), 24, AMBER, True, shadow=True)
        diff = data.config["difficulties"][prof.difficulty]["name"]
        done = " · пройдена" if prof.biome_done else ""
        info = (f"Глава {prof.biome.get('order', 0) + 1}: {prof.biome['name']} ({diff.lower()}) · захвачено регионов "
                f"{len(prof.regular_captured())}{done} · вылазок {prof.expeditions}")
        T.text(surf, info, (30, 70), 16, (210, 210, 220), shadow=True)
        self.panel(surf, pygame.Rect(T.SCREEN_W - 376, 104, 362, 64 * len(self.buttons) + 16))
        free = sum(meta.points_free(data, prof.heroes[c]) for c in prof.squad)
        for r, key, label in self.buttons:
            text = label + (f" · очков {free}" if key == "heroes" and free else "")
            W.button(surf, r, text, self.mouse, accent=GOLD if key == "map" else (170, 160, 210))
        # отряд — карточки внизу
        y = T.SCREEN_H - 112
        self.panel(surf, pygame.Rect(16, y - 12, 4 * 222 + 12, 104), 150)
        for i, cls in enumerate(prof.squad):
            h = prof.heroes[cls]
            r = pygame.Rect(24 + i * 222, y, 210, 80)
            c = data.classes[cls]
            pygame.draw.rect(surf, (36, 38, 46), r, border_radius=8)
            pygame.draw.rect(surf, tuple(c["color"]), r, 2, border_radius=8)
            T.text(surf, c["name"] + (f" · {data.paths[h['path']]['name']}" if h["path"] else ""), (r.x + 10, r.y + 6),
                   15, T.TEXT, True)
            T.text(surf, f"мастерство {prof.mastery(cls)} · {ROLE.get(c['role'], c['role'])}", (r.x + 10, r.y + 28),
                   13, T.TEXT_DIM)
            pts = meta.points_free(data, h)
            if pts:
                T.text(surf, f"свободных очков: {pts}", (r.x + 10, r.y + 48), 13, (170, 140, 255), True)
        T.text(surf, "Отряд в вылазке", (24, y - 32), 15, (220, 220, 230), True, shadow=True)
        self.draw_toast(surf, T.SCREEN_H - 140)


def __getattr__(name):
    """Старое имя экрана отряда — теперь это экран расстановки (game/squad_scene.py)."""
    if name == "RosterScene":
        from game.squad_scene import SquadScene
        return SquadScene
    raise AttributeError(name)
