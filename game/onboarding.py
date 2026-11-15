"""Первый тур по таверне, кодекс и одноразовые подсказки.

Экран таверны остаётся живым: тур и кодекс — лёгкие оверлеи поверх комнат. Тур сам
переключает комнаты, кодекс открывается клавишей I или кнопкой в шапке.
"""
import pygame

from game.expedition_scenes import BLESS, CURSE, GLORY, GOLD
from ui import theme as T
from ui import widgets as W


TOUR_STEPS = [
    {"room": "hall", "title": "Добро пожаловать в таверну",
     "text": ["Это штаб отряда. Отсюда начинается каждый поход: герои, снаряжение, мастерские и главы.",
              "Комнаты внизу — просто переключатели. Тур проведёт по главным из них, а потом вы сможете ходить сами."]},
    {"room": "muster", "title": "Сборы",
     "text": ["Здесь собирают отряд: 2–3 героя на старте, их навыки и артефакты.",
              "Перед выходом проверьте снаряжение и выберите главу. Первый поход лучше начинать на обычной ступени."]},
    {"room": "workshop", "title": "Мастерские",
     "text": ["В мастерских куют артефакты, гранят камни, делают талисманы и зачаровывают вещи.",
              "Артефакты лежат в сундуке. Чем выше уровень мастерской, тем более редкие вещи доступны."]},
    {"room": "build", "title": "Стройка",
     "text": ["Стройка открывает новые возможности таверны: кузню, алтарь, библиотеку, двор, лазарет и мастерские.",
              "Ресурсы приходят из походов, поручений, сада и мастерских. Верхние уровни требуют гранёные камни."]},
    {"room": "market", "title": "Рынок",
     "text": ["На рынке покупают камни, семена и вещи у бродячих мастеров. Товар обновляется после каждого похода.",
              "Семена открывают новые растения в саду, а камни нужны для ювелирки и строительства."]},
    {"room": "chapters", "title": "Главы",
     "text": ["Глава — это поход из трёх актов. Победа над боссом открывает следующую главу и новые сложности.",
              "Не бойтесь проиграть: часть наград и опыт остаются, а таверна продолжает развиваться."]},
    {"room": "hall", "title": "Готово",
     "text": ["Тур закончен. Кодекс всегда открывается клавишей I, а подсказки будут появляться при первом входе в комнаты.",
              "Если забудете управление — откройте кодекс или справку в бою."]},
]

HINTS = {
    "hall": "Комнаты внизу, кодекс — I, меню — Esc. Начните со «Сборов».",
    "muster": "Соберите 2–3 героя, проверьте снаряжение и выберите главу.",
    "workshop": "Артефакты — в сундуке. Кузня, ювелирка, кожевня и алхимия открываются постройками.",
    "yard": "Поручения отправляют свободных героев за золотом, материалами и новобранцами.",
    "build": "Стройка требует золото, трофеи и ресурсы мастерских. Верхние уровни — гранёные камни.",
    "fame": "Зал славы хранит павших и летопись походов.",
    "market": "Товар обновляется после похода. Семена открывают растения, камни нужны для ювелирки.",
    "mine": "Шахта добывает ресурсы, пока игра открыта. Рабочие и глубину можно улучшать.",
    "chapters": "Победа над боссом открывает следующую главу и новую ступень сложности.",
    "polygon": "Полигон: проверьте героев и артефакты в тренировочном бою — без похода, наград и потерь.",
}


def start_tour(app):
    """Запустить первый тур только в основной игре и только один раз."""
    prof = getattr(app, "profile", None)
    if app.launcher != "main" or prof is None or prof.sandbox or prof.tutorial_done():
        return
    app.tour = {"i": 0, "steps": TOUR_STEPS}


def hint_for_room(scene):
    """Одноразовая подсказка для комнаты; в тестах и старых лаунчерах не шумит."""
    app = scene.app
    prof = app.profile
    if app.launcher != "main" or prof.sandbox or getattr(app, "tour", None):
        return None
    key = f"room:{scene.room}"
    if prof.hint_seen(key) or scene.room not in HINTS:
        return None
    prof.mark_hint(key)
    return HINTS[scene.room]


def draw_hint(scene, surf, text):
    """Небольшая карточка-подсказка над нижней панелью."""
    from game.tavern_rooms import strip_y
    r = pygame.Rect(18, strip_y() - 126, T.SCREEN_W - 36, 56)
    T.frame(surf, r, 238, accent=T.AMBER_DIM)
    T.text(surf, "Подсказка", (r.x + 16, r.y + 8), 14, GLORY, True)
    T.text(surf, text, (r.x + 16, r.y + 28), 14, T.TEXT)
    scene.btn(surf, pygame.Rect(r.right - 116, r.y + 12, 100, 32), "Понятно", "hint_close",
              True, primary=True)


class TourOverlay:
    """Пошаговый тур: следующая страница сама переключает комнату."""

    modal = True

    def __init__(self, scene):
        self.scene = scene
        self.app = scene.app
        self.tour = self.app.tour

    @property
    def step(self):
        return self.tour["steps"][self.tour["i"]]

    def next(self):
        if self.tour["i"] + 1 >= len(self.tour["steps"]):
            self.finish()
            return
        self.tour["i"] += 1
        self.scene.overlay = None
        from game.tavern_rooms import go
        go(self.app, self.step["room"])

    def finish(self):
        self.app.tour = None
        self.app.profile.finish_tutorial()
        self.scene.overlay = None
        self.scene.say("Тур завершён — кодекс открывается клавишей I")

    def act(self, action, button=1):
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "tour_next":
            self.next()
        elif kind == "tour_skip":
            self.finish()
        elif kind == "tour_codex":
            self.scene.overlay = CodexOverlay(self.scene, back=self)

    def key(self, k):
        if k in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
            self.next()
            return True
        if k == pygame.K_ESCAPE:
            self.finish()
            return True
        if k == pygame.K_i:
            self.scene.overlay = CodexOverlay(self.scene, back=self)
            return True
        return False

    def wheel(self, dy):
        pass

    def update(self, dt):
        pass

    def draw(self, surf):
        from game.tavern_rooms import strip_y
        shade = pygame.Surface((T.SCREEN_W, T.SCREEN_H), pygame.SRCALPHA)
        shade.fill((4, 3, 2, 145))
        surf.blit(shade, (0, 0))
        r = pygame.Rect(T.SCREEN_W // 2 - 440, strip_y() - 296, 880, 286)
        T.frame(surf, r, 250, accent=GOLD)
        T.text(surf, self.step["title"], (r.x + 24, r.y + 18), 26, GOLD, True)
        T.text(surf, f"Первый тур · {self.tour['i'] + 1}/{len(self.tour['steps'])}",
               (r.right - 190, r.y + 24), 14, T.TEXT_DIM)
        y = r.y + 62
        for line in self.step["text"]:
            for part in T.wrap(line, 16, r.w - 48):
                T.text(surf, part, (r.x + 24, y), 16, T.TEXT)
                y += 23
        last = self.tour["i"] + 1 >= len(self.tour["steps"])
        self.scene.btn(surf, pygame.Rect(r.x + 24, r.bottom - 56, 210, 38),
                       "Готово" if last else "Дальше (Space)", "tour_next", True, primary=True)
        self.scene.btn(surf, pygame.Rect(r.x + 246, r.bottom - 56, 150, 38),
                       "Кодекс (I)", "tour_codex", True)
        self.scene.btn(surf, pygame.Rect(r.right - 160, r.bottom - 56, 136, 38),
                       "Пропустить", "tour_skip", True)


class CodexOverlay:
    """Кодекс: основы, бой, классы, сеты, главы и экономика."""

    modal = True
    TABS = [("basics", "Основы"), ("combat", "Бой"), ("classes", "Классы"),
            ("sets", "Сеты"), ("chapters", "Главы"), ("economy", "Экономика")]

    def __init__(self, scene, back=None):
        self.scene = scene
        self.app = scene.app
        self.prof = scene.app.profile
        self.back = back
        self.tab = "basics"
        self.scroll = 0
        self.pages = self._build_pages()

    def _build_pages(self):
        prof = self.prof
        xd = prof.xd
        data = self.app.data
        pages = {}
        pages["basics"] = [
            ("Экспедиция", GLORY, True),
            ("Таверна → отряд → глава из трёх актов → награды → улучшения. Победа над боссом открывает следующую главу.", T.TEXT, False),
            ("Комнаты внизу: 1 Зал, 2 Сборы, 3 Мастер, 4 Двор, 5 Строй, 6 Слава, 7 Рынок, 8 Шахта, 9 Главы.", T.TEXT, False),
            ("I — кодекс, Esc — меню, колесо — прокрутка. В бою Space — пауза, Q/W/E/R — навыки, F4 — автопауза.", T.TEXT_DIM, False),
            ("Карточка врага открывается кликом по нему, карточка героя — кнопкой «Инфо» в панели отряда.", T.TEXT_DIM, False),
            ("Совет", GLORY, True),
            ("Сначала соберите отряд и проверьте снаряжение. Первый поход лучше начинать на обычной ступени.", BLESS, False),
        ]
        pages["combat"] = [("Стихии и статусы", GLORY, True)]
        for tag, td in data.tags.items():
            pages["combat"].append((f"{td.get('name', tag)}: {td.get('status', '')}", T.TEXT, False))
        pages["combat"].append(("Реакции", GLORY, True))
        for r in data.reactions.get("unit", []):
            a, b = r.get("tags", ["?", "?"])[:2]
            na = data.tags.get(a, {}).get("name", a)
            nb = data.tags.get(b, {}).get("name", b)
            pages["combat"].append((f"{na} + {nb} → {r.get('name', '')}: {r.get('desc', '')}", BLESS, False))
        pages["combat"].append(("Контроль и защита", GLORY, True))
        pages["combat"].append(("Оглушение, корни, заморозка, сон, капкан и стазис — это состояния. Очищение снимает стихии, контроль и дебаффы.", T.TEXT, False))
        pages["combat"].append(("Укрытие режет дальний урон: полное — на 50%, половина — на 25%.", T.TEXT_DIM, False))
        pages["classes"] = [("Классы отряда", GLORY, True)]
        roles = {"melee": "ближний бой", "ranged": "дальний бой", "caster": "магия", "support": "поддержка"}
        for cid, c in data.classes.items():
            role = roles.get(c.get("role"), c.get("role", ""))
            pages["classes"].append((f"{c.get('name', cid)} · {role}", BLESS, True))
            about = c.get("about", "")
            if about:
                pages["classes"].append((about, T.TEXT, False))
            pas = c.get("passive") or {}
            if pas.get("name"):
                pages["classes"].append((f"Пассивка: {pas['name']} — {pas.get('desc', '')}", T.TEXT_DIM, False))
        pages["sets"] = [("Сеты артефактов", GLORY, True)]
        for sid, s in xd["artifacts"]["sets"].items():
            pages["sets"].append((f"{s.get('name', sid)} · {xd['artifacts']['rarities'][s['rarity']]['name']}", BLESS, True))
            for n, b in sorted(s.get("bonus", {}).items()):
                pages["sets"].append((f"{n} предмета: {b.get('text', '')}", T.TEXT, False))
        pages["chapters"] = [("Главы", GLORY, True)]
        for cid, ch in sorted(xd.get("chapters", {}).items(), key=lambda kv: kv[1].get("order", 0)):
            pages["chapters"].append((ch.get("name", cid), BLESS, True))
            pages["chapters"].append((ch.get("desc", ""), T.TEXT, False))
            for m in ch.get("mechanics", []):
                pages["chapters"].append((f"• {m}", T.TEXT_DIM, False))
        pages["economy"] = [
            ("Экономика", GLORY, True),
            ("Золото таверны даётся за походы и поручения. Оно тратится на найм, стройку, мастерские, семена и рынок.", T.TEXT, False),
            ("Ресурсы", GLORY, True),
        ]
        for k, m in xd.get("materials", {}).items():
            if m.get("plant") or m.get("rare") or k in ("ore", "leather", "herbs", "gems", "coal"):
                pages["economy"].append((f"{m.get('name', k)}: {m.get('desc', 'материал')}", T.TEXT, False))
        pages["economy"].append(("Постройки", GLORY, True))
        for bid, b in xd.get("buildings", {}).items():
            pages["economy"].append((f"{b.get('name', bid)}: {b.get('desc', '')}", T.TEXT, False))
        pages["economy"].append(("Сад", GLORY, True))
        pages["economy"].append(("Семена покупаются у торговца на рынке и открывают растения навсегда. Растения нужны для улучшений, зачарований и строительства.", T.TEXT, False))
        return pages

    def close(self):
        self.scene.overlay = self.back if self.back is not None else None

    def act(self, action, button=1):
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "codex_close":
            self.close()
        elif kind == "codex_tab":
            self.tab = action[1]
            self.scroll = 0

    def key(self, k):
        if k in (pygame.K_ESCAPE, pygame.K_i):
            self.close()
            return True
        if k in (pygame.K_LEFT, pygame.K_RIGHT):
            ids = [x[0] for x in self.TABS]
            i = ids.index(self.tab)
            self.tab = ids[(i + (1 if k == pygame.K_RIGHT else -1)) % len(ids)]
            self.scroll = 0
            return True
        if k in (pygame.K_UP, pygame.K_DOWN, pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            step = 1 if k == pygame.K_DOWN else -1
            if k == pygame.K_PAGEUP:
                step = -8
            elif k == pygame.K_PAGEDOWN:
                step = 8
            self.scroll = max(0, self.scroll + step)
            return True
        return False

    def wheel(self, dy):
        self.scroll = max(0, self.scroll - dy)

    def update(self, dt):
        pass

    def draw(self, surf):
        from game.tavern_rooms import strip_y
        shade = pygame.Surface((T.SCREEN_W, T.SCREEN_H), pygame.SRCALPHA)
        shade.fill((4, 3, 2, 175))
        surf.blit(shade, (0, 0))
        r = pygame.Rect(28, 64, T.SCREEN_W - 56, strip_y() - 82)
        T.frame(surf, r, 252, accent=GOLD)
        T.text(surf, "Кодекс", (r.x + 20, r.y + 12), 28, GOLD, True)
        self.scene.btn(surf, pygame.Rect(r.right - 116, r.y + 10, 96, 32), "Закрыть", "codex_close", True)
        x = r.x + 20
        for tid, name in self.TABS:
            on = tid == self.tab
            tw = T.font(15, True).size(name)[0] + 28
            tr = pygame.Rect(x, r.y + 54, tw, 32)
            pygame.draw.rect(surf, (78, 55, 32) if on else (40, 30, 20), tr, border_radius=7)
            pygame.draw.rect(surf, T.AMBER if on else (88, 66, 42), tr, 1, border_radius=7)
            T.text(surf, name, tr.center, 15, T.TEXT if on else T.TEXT_DIM, True, center=True)
            self.scene.hit(tr, ("codex_tab", tid))
            x += tw + 5
        area = pygame.Rect(r.x + 20, r.y + 98, r.w - 40, r.h - 150)
        wrapped = []
        for text, col, bold in self.pages[self.tab]:
            for line in T.wrap(text, 16, area.w - 28):
                wrapped.append((line, col, bold))
        line_h = 21
        total = len(wrapped) * line_h
        max_scroll = max(0, (total - area.h) // line_h + 1)
        self.scroll = max(0, min(max_scroll, self.scroll))
        old = surf.get_clip()
        surf.set_clip(area)
        y = area.y - self.scroll * line_h
        for text, col, bold in wrapped:
            if area.y - line_h <= y <= area.bottom:
                T.text(surf, text, (area.x, y), 16, col, bold)
            y += line_h
        surf.set_clip(old)
        if max_scroll:
            bar = pygame.Rect(area.right - 8, area.y, 4, area.h)
            pygame.draw.rect(surf, (50, 40, 30), bar, border_radius=2)
            th = max(20, int(bar.h * area.h / total))
            top = bar.y + int((bar.h - th) * self.scroll / max_scroll)
            pygame.draw.rect(surf, T.AMBER_DIM, pygame.Rect(bar.x, top, bar.w, th), border_radius=2)
        T.text(surf, "I/Esc — закрыть · ←/→ — раздел · колесо — прокрутка", (r.x + 20, r.bottom - 30), 13,
               T.TEXT_DIM)
