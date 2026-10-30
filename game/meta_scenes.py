"""Экраны меты между вылазками: подготовка героев (путь, ветки, таланты, снаряжение) и лагерь (янтарь)."""
import pygame

from sim import meta, stats
from sim.build import class_skills
from sim.run import RARITY_NAMES, SLOT_NAMES, Run
from ui import projection as P
from ui import theme as T
from ui import widgets as W

AMBER = (255, 170, 60)
BRANCH_COLOR = (255, 150, 90)
PATH_COLOR = (150, 200, 255)
TALENT_COLOR = (170, 140, 255)
BAD = (255, 120, 110)


class MetaScene:
    """Общее: кнопки как список (rect, действие, подсказка), подсказка и сообщение внизу, Esc — в лагерь."""

    def __init__(self, app):
        self.app = app
        self.mouse = (0, 0)
        self.hits = []
        self.toast = None          # (текст, осталось сек)
        self.back = pygame.Rect(T.SCREEN_W - 220, T.SCREEN_H - 66, 196, 44)
        self.on_back = None        # куда «Назад»: по умолчанию — в лагерь

    def go_back(self):
        (self.on_back or self.app.to_hub)()

    def handle(self, ev):
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
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.go_back()
            else:
                self.key(ev.key)

    def act(self, action):
        pass

    def key(self, k):
        pass

    def update(self, dt):
        if self.toast:
            self.toast = (self.toast[0], self.toast[1] - dt) if self.toast[1] > dt else None

    def say(self, text):
        self.toast = (text, 2.5)

    def hit(self, rect, action=None, tip=None):
        self.hits.append((rect, action, tip))

    def draw_footer(self, surf):
        box = pygame.Rect(24, T.SCREEN_H - 74, T.SCREEN_W - 270, 60)
        pygame.draw.rect(surf, T.PANEL, box, border_radius=8)
        tip = next((t for r, _, t in self.hits if t and r.collidepoint(self.mouse)), None)
        text, col = (self.toast[0], BAD) if self.toast else (tip, T.TEXT) if tip else (self.hint, T.TEXT_DIM)
        for i, line in enumerate(T.wrap(text, 14, box.w - 24)[:3]):
            T.text(surf, line, (box.x + 12, box.y + 6 + i * 17), 14, col)
        W.button(surf, self.back, "Назад (Esc)", self.mouse)

    hint = ""


# ---------- подготовка героев ----------

class HeroesScene(MetaScene):
    hint = ("Мастерство растёт за каждую вылазку и даёт очки. Очки тратятся на ступени веток (1 очко за ступень) "
            "и таланты; всё можно перераспределить перед любой вылазкой. Путь открывается на мастерстве "
            "{unlock}. 1–4 — герой.")

    WINDOWS = (("overview", "Обзор и путь"), ("skills", "Способности"), ("talents", "Таланты и снаряжение"))
    PREVIEW = pygame.Rect(588, 154, 668, 380)

    def __init__(self, app, cls=None, window="overview"):
        super().__init__(app)
        from ui.skill_preview import SkillPreview
        self.cls = cls or app.profile.squad[0]
        self.preview = None
        self.windows = self.WINDOWS + ((("stats", "Характеристики"),) if app.profile.uses_stats else ())
        self.window = window
        self.skill_preview = SkillPreview(app.data, self.PREVIEW)
        self.pv = None             # что показывает превью: (навык, ветка, ступень) — ветка None = основа
        self.pv_dirty = True
        self.hint = self.hint.format(unlock=meta.path_unlock_level(app.data))
        self.help = None
        self.help_btn = pygame.Rect(self.back.x - 176, self.back.y, 164, 44)
        if app.profile.mode == "story" and not getattr(app.profile, "help_seen", True):
            self.open_help()                      # сюжет: при первом заходе — обучение окну героя

    def open_help(self):
        from game.help_overlay import HERO_PAGES, HelpOverlay
        pages = [p for p in HERO_PAGES if any(p["window"] == w for w, _ in self.windows)]

        def done():
            prof = self.app.profile
            if hasattr(prof, "help_seen") and not prof.help_seen:
                prof.help_seen = True
                prof.save()
        self.help = HelpOverlay(pages, on_page=lambda pg: self.set_window(pg["window"]), on_close=done)

    # ---------- окна и превью навыка ----------

    def set_window(self, w):
        self.window = w
        if w != "skills":
            P.reset()
        self.pv_dirty = True

    def show_skill(self, sid, b=None, t=None):
        self.pv = (sid, b, t)
        self.pv_dirty = True

    def _sync_preview(self):
        data, hero = self.app.data, self.hero
        skills = class_skills(data, self.cls, hero["path"])
        if self.pv is None or self.pv[0] not in skills:
            self.pv = (skills[0], None, None)
        if not self.pv_dirty:
            return
        self.pv_dirty = False
        sid, b, t = self.pv
        branches = {sid: [b, t]} if b else {}
        name = data.skills[sid]["name"] + (f" · {data.branches[sid][b]['tiers'][t - 1]['name']}" if b else "")
        self.skill_preview.show(self.cls, hero["path"], branches, sid, name)

    def update(self, dt):
        super().update(dt)
        if self.window == "skills":
            self._sync_preview()
            self.skill_preview.update(dt)

    @property
    def vfx(self):
        return self.skill_preview.vfx

    def plane(self):
        return self.skill_preview.plane() if self.window == "skills" and self.skill_preview.proto else None

    def draw_layers(self, world, ui, units):
        """С OpenGL: интерфейс — непрозрачный слой с окном-дыркой, в которой виден бой превью."""
        world.fill(T.BG)
        units.fill((0, 0, 0, 0))
        self._draw_menu(ui)
        if self.window == "skills" and self.skill_preview.proto:
            ui.fill((0, 0, 0, 0), self.PREVIEW)
            self.skill_preview.draw_layers(world, units, ui)
            self._draw_preview_frame(ui)

    def draw(self, surf):
        """Без OpenGL: превью под интерфейсом, интерфейс с дыркой поверх."""
        if self.window == "skills" and self.skill_preview.proto:
            self.skill_preview.draw_cpu(surf)
            layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            self._draw_menu(layer)
            layer.fill((0, 0, 0, 0), self.PREVIEW)
            surf.blit(layer, (0, 0))
            self.skill_preview._draw_overlay(surf)
            self._draw_preview_frame(surf)
        else:
            self._draw_menu(surf)

    def _draw_preview_frame(self, surf):
        r = self.PREVIEW
        pygame.draw.rect(surf, BRANCH_COLOR, r.inflate(4, 4), 2, border_radius=6)
        title = self.skill_preview.title
        box = pygame.Rect(r.x + 8, r.y + 8, T.font(15, True).size(title)[0] + 16, 24)
        pygame.draw.rect(surf, (12, 14, 18), box, border_radius=6)
        T.text(surf, title, (box.x + 8, box.y + 3), 15, BRANCH_COLOR, True)
        k = min(1.0, self.skill_preview.t / 4.2)
        pygame.draw.rect(surf, (12, 14, 18), (r.x + 8, r.bottom - 12, r.w - 16, 4))
        pygame.draw.rect(surf, BRANCH_COLOR, (r.x + 8, r.bottom - 12, int((r.w - 16) * k), 4))

    def handle(self, ev):
        if self.help and self.help.handle(ev):
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.help_btn.collidepoint(ev.pos):
            self.open_help()
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_i:
            self.open_help()
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3 and self.window == "skills":
            for r, action, _ in self.hits:              # ПКМ по ступени — только показать
                if r.collidepoint(ev.pos) and action and action[0] in ("branch", "show"):
                    self.show_skill(*action[1:])
                    return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE and self.window == "skills":
            self.skill_preview.restart()
            return
        super().handle(ev)

    @property
    def hero(self):
        return self.app.profile.heroes[self.cls]

    def roster(self):
        """Все герои: сначала отряд, потом нанятые, потом остальные (их можно смотреть, но не настраивать)."""
        prof = self.app.profile
        hired = prof.squad + [c for c in prof.unlocked if c not in prof.squad]
        pool = prof.all_story_heroes() if prof.mode == "story" else self.app.data.classes   # сюжет — свои 8
        return hired + [c for c in pool if c not in hired]

    @property
    def view_only(self):
        return self.cls not in self.app.profile.unlocked

    def key(self, k):
        units = self.roster()
        if pygame.K_1 <= k < pygame.K_1 + min(9, len(units)):
            self.cls = units[k - pygame.K_1]
            self.preview = self.pv = None
            self.pv_dirty = True
        elif k == pygame.K_TAB:
            self.cls = units[(units.index(self.cls) + 1) % len(units)]
            self.preview = self.pv = None
            self.pv_dirty = True
        elif k in (pygame.K_F1, pygame.K_F2, pygame.K_F3, pygame.K_F4):
            i = (pygame.K_F1, pygame.K_F2, pygame.K_F3, pygame.K_F4).index(k)
            if i < len(self.windows):
                self.set_window(self.windows[i][0])

    def act(self, action):
        data, prof, hero = self.app.data, self.app.profile, self.hero
        kind = action[0]
        ok = True
        if kind == "window":
            self.set_window(action[1])
            return
        if kind == "show":
            self.show_skill(*action[1:])
            return
        if kind == "hero":
            self.cls = action[1]
            self.pv = None
            self.pv_dirty = True
            self.preview = None
            return
        if self.view_only and kind in ("path", "branch", "talent", "loadout", "attr", "attr_reset"):
            if kind == "branch":
                self.show_skill(*action[1:])
            why = prof.hero_lock_reason(self.cls) or "Герой ещё не открыт"
            self.say(f"{why} — пока можно только посмотреть")
            return
        elif kind == "path":
            ok = meta.set_path(data, self.cls, hero, action[1])
            if not ok:
                self.say(f"Путь откроется на мастерстве {meta.path_unlock_level(data)}")
        elif kind == "branch":
            ok = meta.click_branch(data, hero, *action[1:])
            self.show_skill(*action[1:])
            if not ok:
                self.say("Не хватает очков мастерства — снимите другую ступень или талант")
        elif kind == "talent":
            ok = meta.toggle_talent(data, self.cls, hero, action[1])
            if not ok:
                self.say("Не хватает очков мастерства")
        elif kind == "attr":
            ok = prof.add_point(self.cls, action[1], action[2])
            if not ok:
                self.say("Нет свободных очков атрибутов — они даются за уровень героя (3 за уровень)")
        elif kind == "attr_reset":
            prof.reset_points(self.cls)
            self.say("Очки атрибутов возвращены — распределите заново")
        elif kind == "loadout":
            ok = prof.toggle_loadout(self.cls, action[1])
            if not ok:
                owner = prof.loadout_owner(action[1])
                self.say(f"Предмет уже у героя «{data.classes[owner]['name']}»" if owner else
                         f"Мест в оружейной стойке: {prof.arsenal_slots()} — улучшите её в лагере")
        if ok:
            prof.save()
        self.preview = None
        self.pv_dirty = True

    def proto(self):
        """Герой как он выйдет в вылазку: с мастерством, лагерем и регионами (без случайной реликвии)."""
        if self.preview is None:
            prof = self.app.profile
            bonus = {k: v for k, v in prof.bonuses().items() if k != "start_relics"}
            h = prof.heroes[self.cls]
            build = {"cls": self.cls, "path": h["path"], "branches": h["branches"], "talents": h["talents"],
                     "mastery": prof.mastery(self.cls), "autocast": h["autocast"], "items": list(h["loadout"]),
                     "rpg": h["rpg"]}
            run = Run(self.app.data, 0, None, bonus, [build], mode=prof.mode)
            self.preview = run.proto(run.squad[0])
        return self.preview

    def _draw_menu(self, surf):
        data, prof, hero = self.app.data, self.app.profile, self.hero
        self.hits = []
        surf.fill(T.BG)
        T.text(surf, "Подготовка героев", (24, 14), 30, T.TEXT, True)
        free, total = meta.points_free(data, hero), meta.points_total(data, hero)
        pts = f"Очки мастерства: свободно {free} из {total}"
        if self.view_only:
            pts = f"Просмотр: {prof.hero_lock_reason(self.cls) or 'герой ещё не открыт'}"
        T.text(surf, pts, (T.SCREEN_W - 30 - T.font(20, True).size(pts)[0], 20), 20,
               TALENT_COLOR if free else T.TEXT_DIM, True)
        units = self.roster()
        rows = 1 if len(units) <= 11 else 2          # много героев — вкладки в два ряда
        per_row = -(-len(units) // rows)
        bw = min(176, (T.SCREEN_W - 48) // max(1, per_row) - 6)
        bh = 40 if rows == 1 else 24
        for i, cls in enumerate(units):
            r = pygame.Rect(24 + (i % per_row) * (bw + 6), (62 if rows == 1 else 58) + (i // per_row) * (bh + 4), bw, bh)
            sel = cls == self.cls
            pygame.draw.rect(surf, (52, 56, 68) if sel else T.PANEL, r, border_radius=8)
            edge = T.SELECT if sel else ((255, 200, 110) if cls in prof.squad else T.PANEL_EDGE)
            pygame.draw.rect(surf, edge, r, 2, border_radius=8)
            h = prof.heroes[cls]
            name = data.classes[cls]["name"]
            hired = cls in prof.unlocked
            if h["path"] and bw > 150:
                name += f" · {data.paths[h['path']]['name']}"
            if rows == 1:
                T.text(surf, f"{i + 1}. {name}" if i < 9 else name, (r.x + 8, r.y + 3), 14 if bw < 150 else 15,
                       T.TEXT, True)
                T.text(surf, f"мастер. {prof.mastery(cls)} · очков {meta.points_free(data, h)}", (r.x + 8, r.y + 21),
                       12, T.TEXT_DIM)
            else:
                label = data.classes[cls]["name"]
                while T.font(12, True).size(label)[0] > bw - 10 and len(label) > 3:
                    label = label[:-1]
                T.text(surf, label, (r.x + 5, r.y + 4), 12, T.TEXT if hired else T.TEXT_DIM, True)
            tip = f"{data.classes[cls]['name']}" + (" — в отряде" if cls in prof.squad else
                                                     " — не в отряде («Отряд»)" if hired else
                                                     f" — {prof.hero_lock_reason(cls) or 'ещё не открыт'}"
                                                     ", можно смотреть")
            self.hit(r, ("hero", cls), tip)
        for i, (wid, title) in enumerate(self.windows):
            r = pygame.Rect(24 + i * 250, 116, 240, 32)
            on = wid == self.window
            pygame.draw.rect(surf, (52, 56, 68) if on else T.PANEL, r, border_top_left_radius=8,
                             border_top_right_radius=8)
            pygame.draw.rect(surf, BRANCH_COLOR if on else T.PANEL_EDGE, r, 2, border_top_left_radius=8,
                             border_top_right_radius=8)
            T.text(surf, f"{title}  (F{i + 1})", r.center, 15, T.TEXT if on else T.TEXT_DIM, on, center=True)
            self.hit(r, ("window", wid), None)
        if self.window == "overview":
            self._draw_hero(surf, pygame.Rect(24, 154, 520, 552))
            self._draw_paths(surf, pygame.Rect(560, 154, 696, 552))
        elif self.window == "skills":
            self._draw_skills(surf, pygame.Rect(24, 154, 548, 552))
            self._draw_skill_info(surf, pygame.Rect(588, 544, 668, 162))
        elif self.window == "stats":
            self._draw_stats(surf, pygame.Rect(24, 154, 600, 552), pygame.Rect(640, 154, 616, 552))
        else:
            self._draw_talents(surf, pygame.Rect(24, 154, 600, 552), pygame.Rect(640, 154, 616, 552))
        self.draw_footer(surf)
        W.button(surf, self.help_btn, "Справка (I)", self.mouse, accent=(255, 205, 110))
        if self.help:
            self.help.draw(surf)

    def _draw_stats(self, surf, left, right):
        """Режим героев: уровень, опыт, атрибуты (+ очки), что они дают и как скейлятся навыки."""
        data, hero = self.app.data, self.hero
        rpg = hero["rpg"]
        der = stats.derive(data, self.cls, rpg)
        k = data.stats_mode
        p = self.proto()
        for r in (left, right):
            pygame.draw.rect(surf, T.PANEL, r, border_radius=10)
        x, y = left.x + 16, left.y + 12
        lvl, cap = rpg["level"], k["level_cap"]
        T.text(surf, f"Уровень {lvl}" + (" (максимум)" if lvl >= cap else ""), (x, y), 24, (150, 200, 255), True)
        if lvl < cap:
            need = stats.xp_to_next(data, lvl)
            W.bar(surf, pygame.Rect(x + 190, y + 10, left.w - 230, 10), rpg["xp"] / need, W.XP)
            T.text(surf, f"опыт {rpg['xp']}/{need}", (x + 190, y + 24), 12, T.TEXT_DIM)
        y += 52
        free = stats.points_free(data, rpg)
        T.text(surf, f"Свободных очков: {free}", (x, y), 17, TALENT_COLOR if free else T.TEXT_DIM, True)
        rb = pygame.Rect(left.right - 186, y - 4, 170, 28)
        W.button(surf, rb, "Сбросить очки", self.mouse, accent=(200, 160, 120))
        self.hit(rb, ("attr_reset",), "Вернуть все вложенные очки (бесплатно)")
        y += 36
        c = k["classes"][self.cls]
        for a in stats.ATTRS:
            ad = k["attrs"][a]
            r = pygame.Rect(x - 4, y, left.w - 24, 104)
            prim = a == c["primary"]
            pygame.draw.rect(surf, (36, 38, 46), r, border_radius=8)
            pygame.draw.rect(surf, tuple(ad["color"]) if prim else T.PANEL_EDGE, r, 2 if prim else 1,
                             border_radius=8)
            T.text(surf, ad["name"] + ("  · основной" if prim else ""), (r.x + 12, r.y + 8), 18, tuple(ad["color"]),
                   True)
            T.text(surf, f"{der['attrs'][a]:.0f}", (r.x + 230, r.y + 4), 26, T.TEXT, True)
            T.text(surf, f"старт {c['start'][a]} · +{c['gain'][a]:g} за уровень · вложено {rpg['points'][a]}",
                   (r.x + 12, r.y + 34), 13, T.TEXT_DIM)
            for i, line in enumerate(T.wrap(ad["desc"], 13, r.w - 150)[:2]):
                T.text(surf, line, (r.x + 12, r.y + 54 + i * 17), 13, (200, 205, 220))
            for j, n in enumerate((1, 5)):
                b = pygame.Rect(r.right - 120 + j * 58, r.y + 10, 52, 34)
                W.button(surf, b, f"+{n}", self.mouse, free >= n, accent=tuple(ad["color"]))
                self.hit(b, ("attr", a, n), f"Вложить {n} в «{ad['name']}»")
            y += 112
        # что получилось
        x, y = right.x + 16, right.y + 12
        T.text(surf, "Характеристики", (x, y), 20, T.TEXT, True)
        y += 34
        rows = [("Здоровье", f"{p['hp']}"), ("Броня", f"{p['armor']:g}"),
                ("Атака", f"{p['attack']['damage']} × {der['scale']['basic']:.2f} (от основного атрибута)"),
                ("Атака раз в", f"{p['attack']['cooldown']:.2f} с"), ("AP", f"{p['ap_max']}"),
                ("AP восстанавливается", f"1 за {p['ap_regen']:.2f} с"),
                ("Крит", f"{der['crit'] * 100:.1f}% (урон ×{der['crit_mult']:g})"),
                ("Уклонение", f"{der['dodge'] * 100:.1f}% от атак оружием")]
        for name, val in rows:
            T.text(surf, name, (x, y), 15, T.TEXT_DIM)
            T.text(surf, val, (x + 230, y), 15, T.TEXT, True)
            y += 24
        y += 12
        T.text(surf, "Скейлы навыков", (x, y), 18, BRANCH_COLOR, True)
        y += 28
        names = {"melee": "Ближние навыки (Сила)", "collision": "Столкновения (Сила)", "ranged": "Стрелы (Ловкость)",
                 "spell": "Заклинания (Интеллект)", "reaction": "Реакции стихий (Интеллект)",
                 "heal": "Лечение и щиты (Интеллект)"}
        for school, name in names.items():
            v = der["scale"].get(school, 1.0)
            T.text(surf, name, (x, y), 15, T.TEXT_DIM)
            T.text(surf, f"×{v:.2f}", (x + 300, y), 15, (150, 240, 160) if v > 1.001 else T.TEXT, True)
            y += 22
        y += 10
        for line in T.wrap("Прибавки считаются от стартовых атрибутов героя: на 1 уровне он такой же, как в основной "
                           "игре. Враги регионов тоже растут уровнями — ниже уровнем фармятся легко.", 13, right.w - 32):
            T.text(surf, line, (x, y), 13, T.TEXT_DIM)
            y += 17

    def _draw_skill_info(self, surf, rect):
        """Под превью: что именно показано — цена, дальность, описание ступени."""
        data = self.app.data
        pygame.draw.rect(surf, T.PANEL, rect, border_radius=10)
        if not self.skill_preview.proto:
            return
        sid, b, t = self.pv
        sk = self.skill_preview.proto["skill_defs"][sid]
        x, y = rect.x + 14, rect.y + 10
        T.text(surf, self.skill_preview.title, (x, y), 18, BRANCH_COLOR, True)
        bits = [f"AP {sk['ap']}"] + ([f"{sk['hp_cost']} HP"] if sk.get("hp_cost") else []) + \
            ([f"каст {sk['cast']:g}с"] if sk["cast"] else []) + ([f"дал. {sk['range']}"] if sk["range"] else []) + \
            ([f"радиус {sk['radius']}"] if sk.get("radius") else []) + ([f"кд {sk['cooldown']:g}с"] if sk["cooldown"] else [])
        T.text(surf, " · ".join(bits), (x, y + 26), 14, T.AP_COLOR)
        sc = self.proto().get("scale")
        if sc:                                    # режим героев: от чего растёт навык
            schools = []
            for e in sk["effects"] + [x for e in sk["effects"] if e["type"] == "delay" for x in e["effects"]]:
                if e["type"] in ("heal", "shield"):
                    schools.append("heal")
                elif e.get("amount") is not None:
                    schools.append(e.get("kind", "melee" if e["type"] == "push" else "spell"))
            attr = {"melee": "Сила", "collision": "Сила", "ranged": "Ловкость", "spell": "Интеллект",
                    "reaction": "Интеллект", "heal": "Интеллект"}
            parts = [f"{attr.get(s, '?')} ×{sc.get(s, 1.0):.2f}" for s in dict.fromkeys(schools) if s in attr]
            if parts:
                T.text(surf, "Скейл: " + ", ".join(parts), (x + 330, y + 26), 14, (150, 200, 255), True)
        y += 48
        text = sk["desc"]
        if b:
            text = f"{data.branches[sid][b]['tiers'][t - 1]['desc']} — {text}"
        for line in T.wrap(text, 14, rect.w - 28)[:4]:
            T.text(surf, line, (x, y), 14, T.TEXT)
            y += 18
        T.text(surf, "ЛКМ по ступени — взять и показать · ПКМ — только показать · Пробел — повторить",
               (x, rect.bottom - 22), 12, T.TEXT_DIM)

    def _draw_hero(self, surf, rect):
        data, prof, hero = self.app.data, self.app.profile, self.hero
        p = self.proto()
        pygame.draw.rect(surf, T.PANEL, rect, border_radius=10)
        x, y = rect.x + 14, rect.y + 12
        pygame.draw.circle(surf, tuple(p["color"]), (x + 20, y + 20), 20)
        T.text(surf, p["label"], (x + 20, y + 20), 20, (255, 255, 255), True, center=True, shadow=True)
        T.text(surf, data.classes[self.cls]["name"], (x + 50, y), 22, T.TEXT, True)
        lvl = prof.mastery(self.cls)
        T.text(surf, f"Мастерство {lvl}", (x + 50, y + 28), 15, W.XP, True)
        prog = meta.mastery_progress(data, hero["xp"])
        if prog:
            W.bar(surf, pygame.Rect(x + 170, y + 34, rect.w - 200, 8), prog[0] / prog[1], W.XP)
            T.text(surf, f"{prog[0]}/{prog[1]}", (rect.right - 70, y + 44), 12, T.TEXT_DIM)
        y += 64
        stat = data.config["mastery"]["stat_per_level"]
        g = p.get("gauge") or {"name": "PP", "desc": ""}
        lines = [f"HP {p['hp']} · броня {p['armor']} · атака {p['attack']['damage']}",
                 f"AP {p['ap_max']} · {g['name']} {p['pp_max']} · сила навыков ×{p['power']:.2f}",
                 f"Мастерство даёт +{round(stat * (lvl - 1) * 100)}% HP и урона"]
        for s in lines:
            T.text(surf, s, (x, y), 15, T.TEXT)
            y += 20
        for line in T.wrap(f"Шкала «{g['name']}»: {g['desc']}. Пассив «{p['passive']['name']}»: "
                           f"{p['passive']['desc']}", 14, rect.w - 28):
            T.text(surf, line, (x, y), 14, tuple(g.get("color", T.PP_COLOR)))
            y += 18
        y += 10
        for line in T.wrap(data.classes[self.cls].get("about", ""), 14, rect.w - 28):
            T.text(surf, line, (x, y), 14, (200, 205, 220))
            y += 18
        if not hasattr(self, "_sprites"):
            from ui.sprites import SpriteBank
            self._sprites = SpriteBank()
        c = data.classes[self.cls]
        img = self._sprites.get([self.cls], self.cls, tuple(c["color"]), look=c.get("look"))
        img = pygame.transform.scale(img, (img.get_width() * 3, img.get_height() * 3))
        pygame.draw.ellipse(surf, (24, 26, 32), (rect.centerx - 70, rect.bottom - 34, 140, 26))
        surf.blit(img, (rect.centerx - img.get_width() / 2, rect.bottom - img.get_height() - 18))

    def _draw_paths(self, surf, rect):
        data, prof, hero = self.app.data, self.app.profile, self.hero
        pygame.draw.rect(surf, T.PANEL, rect, border_radius=10)
        x, y = rect.x + 14, rect.y + 12
        lvl = prof.mastery(self.cls)
        T.text(surf, "Путь", (x, y), 17, PATH_COLOR, True)
        y += 30
        unlocked = lvl >= meta.path_unlock_level(data)
        base = data.classes[self.cls]
        options = [(None, f"Основа: {data.classes[self.cls]['name']}",
                    f"Навыки: {', '.join(data.skills[s]['name'] for s in base['skills'])}. "
                    f"Пассив «{base['passive']['name']}».")]
        for pid in meta.paths_for(data, self.cls):
            pd = data.paths[pid]
            options.append((pid, pd["name"], pd["desc"]))
        for pid, title, desc in options:
            r = pygame.Rect(x, y, rect.w - 28, 150)
            sel = hero["path"] == pid
            locked = pid is not None and not unlocked
            pygame.draw.rect(surf, (52, 56, 68) if sel else (36, 38, 46), r, border_radius=8)
            pygame.draw.rect(surf, PATH_COLOR if sel else T.PANEL_EDGE, r, 2, border_radius=8)
            T.text(surf, title + ("  (выбран)" if sel else ""), (r.x + 10, r.y + 6), 16,
                   T.TEXT_DIM if locked else T.TEXT, True)
            if pid:
                pa = data.paths[pid]["passive"]
                desc = f"{desc} Пассив «{pa['name']}»: {pa['desc']}."
            for i, line in enumerate(T.wrap(desc, 14, r.w - 20)[:6]):
                T.text(surf, line, (r.x + 10, r.y + 30 + i * 18), 14, T.TEXT_DIM if locked else (200, 205, 220))
            if locked:
                T.text(surf, f"мастерство {meta.path_unlock_level(data)}", (r.right - 110, r.y + 8), 13, BAD)
            tip = None
            if pid:
                pa = data.paths[pid]["passive"]
                tip = f"{data.paths[pid]['name']}: пассив «{pa['name']}» — {pa['desc']}. Ветки заменённого навыка " \
                      f"снимаются, очки возвращаются."
            self.hit(r, ("path", pid), tip)
            y += 160

    def _draw_skills(self, surf, rect):
        data, hero = self.app.data, self.hero
        pygame.draw.rect(surf, T.PANEL, rect, border_radius=10)
        T.text(surf, "Навыки и ветки", (rect.x + 14, rect.y + 10), 17, BRANCH_COLOR, True)
        p = self.proto()
        y = rect.y + 40
        free = meta.points_free(data, hero)
        for sid in class_skills(data, self.cls, hero["path"]):
            sk = p["skill_defs"][sid]
            base = data.skills[sid]
            title = base["name"] + (f" → {sk['name']}" if sk["name"] != base["name"] else "")
            shown = self.pv is not None and self.pv[0] == sid
            head = pygame.Rect(rect.x + 8, y - 2, rect.w - 16, 22)
            if shown and self.pv[1] is None:
                pygame.draw.rect(surf, (52, 56, 68), head, border_radius=5)
            T.text(surf, ("» " if shown else "") + title, (rect.x + 14, y), 16, BRANCH_COLOR if shown else T.TEXT, True)
            T.text(surf, f"AP {sk['ap']}", (rect.right - 60, y + 2), 13, T.AP_COLOR)
            self.hit(head, ("show", sid, None, None), f"{base['name']}: показать в превью")
            y += 22
            T.text(surf, T.wrap(sk["desc"], 13, rect.w - 28)[0], (rect.x + 14, y), 13, T.TEXT_DIM)
            y += 22
            br = data.branches.get(sid)
            cur = hero["branches"].get(sid)
            for col, b in enumerate(("A", "B")):
                bx = rect.x + 14 + col * (rect.w - 28) // 2
                bw = (rect.w - 28) // 2 - 8
                closed = cur is not None and cur[0] != b
                T.text(surf, f"{b}: {br[b]['name']}", (bx, y), 14, T.TEXT_DIM if closed else BRANCH_COLOR, True)
                for t, tier in enumerate(br[b]["tiers"], 1):
                    r = pygame.Rect(bx, y + 20 + (t - 1) * 40, bw, 36)
                    taken = cur is not None and cur[0] == b and cur[1] >= t
                    cost = t - (cur[1] if cur and cur[0] == b else 0)
                    affordable = taken or cost <= free + (cur[1] if cur and cur[0] != b else 0)
                    fill = T.mix(BRANCH_COLOR, (30, 30, 34), 0.55) if taken else (36, 38, 46)
                    pygame.draw.rect(surf, fill, r, border_radius=6)
                    edge = BRANCH_COLOR if taken else (T.PANEL_EDGE if affordable else (90, 50, 50))
                    if self.pv == (sid, b, t):
                        edge = (255, 255, 255)
                    pygame.draw.rect(surf, edge, r, 2 if taken or self.pv == (sid, b, t) else 1, border_radius=6)
                    T.text(surf, f"{t}. {tier['name']}", (r.x + 8, r.y + 3), 14,
                           T.TEXT if (taken or not closed) else T.TEXT_DIM, taken)
                    T.text(surf, "взята" if taken else f"{max(cost, 1)} очк.", (r.x + 8, r.y + 19), 12,
                           (150, 240, 160) if taken else T.TEXT_DIM)
                    tip = f"{tier['name']}: {tier['desc']}"
                    if closed and not taken:
                        tip += " Заменит другую ветку этого навыка."
                    self.hit(r, ("branch", sid, b, t), tip)
            y += 20 + 2 * 40 + 14

    def _draw_talents(self, surf, rect, gear=None):
        data, prof, hero = self.app.data, self.app.profile, self.hero
        pygame.draw.rect(surf, T.PANEL, rect, border_radius=10)
        x, y = rect.x + 14, rect.y + 10
        T.text(surf, "Таланты", (x, y), 17, TALENT_COLOR, True)
        y += 28
        free = meta.points_free(data, hero)
        for tid in meta.talent_options(data, self.cls, hero):
            t = data.talents[tid]
            r = pygame.Rect(x, y, rect.w - 28, 26)
            on = tid in hero["talents"]
            cost = meta.talent_cost(data, tid)
            pygame.draw.rect(surf, T.mix(TALENT_COLOR, (30, 30, 34), 0.6) if on else (36, 38, 46), r, border_radius=6)
            pygame.draw.rect(surf, TALENT_COLOR if on else (T.PANEL_EDGE if cost <= free else (90, 50, 50)), r, 1,
                             border_radius=6)
            T.text(surf, t["name"], (r.x + 8, r.y + 4), 14, T.TEXT, on)
            T.text(surf, "взят" if on else f"{cost} очк.", (r.right - 52, r.y + 5), 12,
                   (150, 240, 160) if on else T.TEXT_DIM)
            general = " (общий талант)" if t["class"] == "any" else ""
            self.hit(r, ("talent", tid), f"{t['name']}: {t['desc']}{general}")
            y += 30
        y += 10
        if gear is not None:                  # отдельная колонка снаряжения
            pygame.draw.rect(surf, T.PANEL, gear, border_radius=10)
            rect = gear
            x, y = gear.x + 14, gear.y + 10
        T.text(surf, f"Снаряжение из арсенала ({prof.loadout_count()}/{prof.arsenal_slots()})", (x, y), 16, W.GOLD,
               True)
        y += 26
        cols = 2 if gear is not None and len(prof.arsenal) > (rect.bottom - y) // 30 else 1
        col_w = (rect.w - 28 - (cols - 1) * 8) // cols
        top, col = y, 0
        if not prof.arsenal:
            for line in T.wrap("Арсенал пуст. Трофеи даёт победа над стражем региона.", 13, rect.w - 28):
                T.text(surf, line, (x, y), 13, T.TEXT_DIM)
                y += 17
        for iid in prof.arsenal:
            if y > rect.bottom - 30:
                if col + 1 >= cols:
                    break
                col, y = col + 1, top
            it = data.items[iid]
            r = pygame.Rect(x + col * (col_w + 8), y, col_w, 26)
            owner = prof.loadout_owner(iid)
            mine = owner == self.cls
            pygame.draw.rect(surf, (60, 56, 40) if mine else (36, 38, 46), r, border_radius=6)
            pygame.draw.rect(surf, W.item_color(data, iid) if mine else T.PANEL_EDGE, r, 1, border_radius=6)
            T.text(surf, it["name"], (r.x + 8, r.y + 4), 14, W.item_color(data, iid), mine)
            mark = "у героя" if mine else (data.classes[owner]["name"] if owner else SLOT_NAMES[it["slot"]].lower())
            T.text(surf, mark, (r.right - 8 - T.font(12).size(mark)[0], r.y + 5), 12, T.TEXT_DIM)
            self.hit(r, ("loadout", iid),
                     f"{it['name']} ({SLOT_NAMES[it['slot']]}, {RARITY_NAMES[it['rarity']]}): {it['desc']}. "
                     f"Клик — взять на вылазку или снять.")
            y += 30


# ---------- лагерь ----------

class CampScene(MetaScene):
    hint = "Янтарь даётся за вылазки. Улучшения лагеря действуют на все будущие вылазки."

    def act(self, action):
        if action[0] == "buy":
            if not self.app.profile.buy_upgrade(action[1]):
                cost = self.app.profile.camp_cost(action[1])
                self.say("Улучшение на максимуме" if cost is None else f"Не хватает янтаря: нужно {cost}")

    def draw(self, surf):
        data, prof = self.app.data, self.app.profile
        self.hits = []
        surf.fill(T.BG)
        T.text(surf, "Лагерь", (24, 14), 30, T.TEXT, True)
        amber = f"Янтарь: {prof.amber}"
        T.text(surf, amber, (T.SCREEN_W - 30 - T.font(22, True).size(amber)[0], 18), 22, AMBER, True)
        cw = (T.SCREEN_W - 48 - 2 * 16) // 3
        for gi, g in enumerate(data.camp["groups"]):
            x = 24 + gi * (cw + 16)
            y = 70
            T.text(surf, g["name"], (x, y), 18, AMBER, True)
            y += 30
            for uid, up in data.camp["upgrades"].items():
                if up["group"] != g["id"]:
                    continue
                r = pygame.Rect(x, y, cw, 104)
                lvl, cost = prof.camp_level(uid), prof.camp_cost(uid)
                can = cost is not None and prof.amber >= cost
                hot = r.collidepoint(self.mouse) and can
                pygame.draw.rect(surf, (52, 56, 68) if hot else T.PANEL, r, border_radius=10)
                pygame.draw.rect(surf, AMBER if can else T.PANEL_EDGE, r, 2, border_radius=10)
                T.text(surf, up["name"], (r.x + 12, r.y + 8), 17, T.TEXT, True)
                for i in range(len(up["costs"])):
                    pygame.draw.circle(surf, AMBER if i < lvl else (60, 62, 70),
                                       (r.right - 16 - (len(up["costs"]) - 1 - i) * 16, r.y + 18), 6)
                T.text(surf, up["desc"], (r.x + 12, r.y + 34), 14, (200, 205, 220))
                T.text(surf, f"уровень {lvl}/{len(up['costs'])}", (r.x + 12, r.y + 58), 13, T.TEXT_DIM)
                label = "максимум" if cost is None else f"улучшить: {cost} янтаря"
                T.text(surf, label, (r.x + 12, r.y + 78), 14,
                       T.TEXT_DIM if cost is None else (AMBER if can else BAD), True)
                self.hit(r, ("buy", uid))
                y += 114
        y = 590
        T.text(surf, f"Арсенал — трофеи стражей (на вылазку можно взять: {prof.arsenal_slots()})", (24, y), 18,
               W.GOLD, True)
        y += 30
        x = 24
        if not prof.arsenal:
            T.text(surf, "Пока пусто: после победы над стражем региона выберите трофей.", (x, y), 15, T.TEXT_DIM)
        for iid in prof.arsenal:
            it = data.items[iid]
            w = T.font(14, True).size(it["name"])[0] + 20
            if x + w > T.SCREEN_W - 24:
                x, y = 24, y + 32
            r = pygame.Rect(x, y, w, 26)
            pygame.draw.rect(surf, (36, 38, 46), r, border_radius=6)
            pygame.draw.rect(surf, W.item_color(data, iid), r, 1, border_radius=6)
            T.text(surf, it["name"], (r.x + 10, r.y + 4), 14, W.item_color(data, iid), True)
            owner = prof.loadout_owner(iid)
            self.hit(r, None, f"{it['name']} ({SLOT_NAMES[it['slot']]}, {RARITY_NAMES[it['rarity']]}): {it['desc']}"
                     + (f" — берёт {data.classes[owner]['name']}" if owner else " — раздаётся на экране героев"))
            x += w + 8
        self.draw_footer(surf)
