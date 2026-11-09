"""Экраны экспедиции (sim/expedition.py): таверна, карта акта, лист героя, события, награды, лагерь, торговец.

Все экраны — stage (вёрстка 1280×800). Поход сохраняется после каждого шага: из любого экрана можно выйти
в таверну и вернуться («Продолжить поход»), бой при этом начнётся заново, а исход броска события — нет.
"""
import math

import pygame

from game.battle_scene import BattleScene
from sim import story_meta
from sim import expedition as X
from sim import stats
from ui import theme as T
from ui import widgets as W
from ui.battle_view import fit
from ui.sprites import SpriteBank

GOLD = (240, 200, 80)
GLORY = (255, 190, 110)
BLESS = (150, 230, 170)
CURSE = (230, 110, 120)
SP = (120, 200, 255)
NODE_COLORS = {"battle": (200, 85, 70), "elite": (230, 150, 40), "boss": (170, 70, 210), "event": (80, 150, 230),
               "camp": (80, 185, 105), "shop": (225, 200, 80), "anvil": (150, 170, 190), "ash": (110, 104, 100)}
NODE_LETTERS = {"battle": "Б", "elite": "Э", "boss": "!", "event": "?", "camp": "Л", "shop": "Т", "anvil": "Н",
                "ash": "·"}
NODE_NAMES = {"battle": "Бой", "elite": "Элита", "boss": "Босс акта", "event": "Событие", "camp": "Лагерь",
              "shop": "Торговец", "anvil": "Наковальня", "ash": "Пепелище"}
HEAT = (255, 120, 50)
RESULT_NAMES = {"crit": ("Критический успех!", (255, 220, 100)), "success": ("Успех", (130, 230, 140)),
                "fail": ("Провал", (240, 130, 110)), "fumble": ("Критический провал!", (255, 80, 80))}
ATTR_NAMES = {"str": "Сила", "agi": "Ловкость", "int": "Интеллект"}
_SPRITES = SpriteBank()


_ICONS = {}


def icon(name, size=32):
    """Иконка assets/icons/<name>.png (вещь — item_<база> / unique_<id>, дар — gift_<id>) или None."""
    key = (name, size)
    if key not in _ICONS:
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icons",
                            f"{name}.png")
        img = None
        if os.path.exists(path):
            try:
                img = pygame.transform.scale(pygame.image.load(path), (size, size))
            except pygame.error:
                img = None
        _ICONS[key] = img
    return _ICONS[key]


def item_icon(item, size=32):
    """Иконка вещи; у уникальной без своей картинки — иконка её базы."""
    img = icon(f"unique_{item['unique']}", size) if item.get("unique") else None
    return img or icon(f"item_{item['base']}", size)


def tint_of(data, cls):
    """Цвета худа героя — по цвету его класса (ui/theme.hero_tint)."""
    return T.hero_tint(data.classes[cls]["color"])


def scene_party(surf, run, ground=0.94, x0=30, mouse=None, k=None, step=None):
    """Отряд на полноэкранной иллюстрации (по умолчанию в её масштабе: пиксель спрайта = пиксель сцены 192×128),
    с табличками: имя, полоса HP, рана. Возвращает [(прямоугольник фигурки, индекс героя)]."""
    img_h = T.SCREEN_W * 2 // 3
    k = k or T.SCREEN_W / 192 / 2
    g = (T.SCREEN_H - img_h) // 2 + int(img_h * ground)
    step = step or int(56 * k)
    rects = party_in_scene(surf, run.data, run.heroes, g, x0, step, k=k, dark=0.85)
    for (r, i) in rects:
        h = run.heroes[i]
        hot = mouse is not None and r.collidepoint(mouse)
        mx, hp = run.max_hp(h), run.hp_of(h)
        w = min(150, step - 10)
        tag = pygame.Rect(r.centerx - w // 2, r.y - 10, w, 40)
        tn = tint_of(run.data, h.cls)
        box = pygame.Surface(tag.size, pygame.SRCALPHA)
        pygame.draw.rect(box, (*T.mix((14, 12, 10), tn["accent"], 0.12), 220), box.get_rect(), border_radius=6)
        pygame.draw.rect(box, (*(tn["accent"] if hot else tn["dim"]), 255), box.get_rect(), 2 if hot else 1,
                         border_radius=6)
        pygame.draw.rect(box, (*tn["accent"], 255), (0, 6, 3, tag.h - 12), border_radius=2)
        surf.blit(box, tag)
        T.text(surf, h.name + (" · ранен" if h.wounded else ""), (tag.x + 8, tag.y + 3), 14,
               CURSE if h.wounded else T.TEXT, True)
        W.bar(surf, pygame.Rect(tag.x + 8, tag.y + 23, w - 16, 9), hp / mx, T.mix((230, 60, 50), (90, 220, 90), hp / mx))
    return rects


def party_in_scene(surf, data, heroes, ground, x0, step, k=1.25, dark=0.82):
    """Отряд текущего похода на переднем плане иллюстрации: картинки рисуются без героев (подходят к любому
    составу), фигурки ставит игра — на линию земли ground, слева направо, с тенью и чуть притушенные под свет
    сцены. Возвращает [(прямоугольник фигурки, индекс)]."""
    x = x0
    out = []
    for i, h in enumerate(heroes):
        img = hero_sprite(data, h.cls, k)
        if dark < 1:
            img = img.copy()
            v = int(255 * dark)
            img.fill((v, v, v, 255), special_flags=pygame.BLEND_RGBA_MULT)
        w = img.get_width()
        sh = pygame.Surface((int(w * 0.8), 12), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 120), sh.get_rect())
        surf.blit(sh, (x + w * 0.1, ground - 7))
        surf.blit(img, (x, ground - img.get_height()))
        out.append((pygame.Rect(x + w // 5, ground - img.get_height() * 4 // 5, w * 3 // 5, img.get_height() * 4 // 5),
                    i))
        x += step
    return out


def rarity_color(xd, item):
    return tuple(xd["items"]["rarities"][item["rarity"]]["color"])


def hero_sprite(data, cls, k=1.0):
    c = data.classes[cls]
    img = _SPRITES.get([cls], cls, tuple(c["color"]), look=c.get("look"))
    if k != 1:
        img = pygame.transform.scale(img, (int(img.get_width() * k), int(img.get_height() * k)))
    return img


# ---------- переходы между экранами (вызываются из App) ----------

def to_tavern(app):
    app.exp = None
    app.switch(TavernScene(app))


def save(app):
    if app.exp is not None:
        app.profile.save(app.exp)


def start_run(app, uids, tier=0, chapter="swamp"):
    seed = None if app.seed is None else app.seed + app.profile.runs
    app.exp = app.profile.start(uids, seed, tier=tier, chapter=chapter)
    offers = getattr(app.exp, "start_offers", None)
    if offers:                                   # алтарь таверны: дар на выбор ещё до первого шага
        app.switch(RewardScene(app, {}, [{"type": "gift", "id": g} for g in offers],
                               then=lambda: app.switch(ActScene(app)), title="Дар алтаря"))
    else:
        app.switch(ActScene(app))


def resume(app):
    """Продолжить сохранённый поход с того места, где из него вышли."""
    run = app.profile.resume()
    if run is None:
        to_tavern(app)
        return
    app.exp = run
    st = run.stage or {}
    kind = st.get("kind")
    if kind in ("battle", "elite", "boss"):
        battle(app)
    elif kind == "event" and (st.get("gift") or st.get("battle")):
        event_next(app, st["event"], st.get("step"), st.get("battle"), st.get("gift"))
    elif kind == "event" and st.get("step"):
        app.switch(EventScene(app, st["event"], st["step"]))
    elif kind == "reward" and st.get("offers") is not None:
        app.switch(RewardScene(app, st.get("summary") or {"result": "victory"}, st["offers"], st.get("bonus")))
    elif kind == "camp":
        app.switch(CampScene(app))
    elif kind == "shop":
        app.switch(ShopScene(app))
    elif kind == "act":
        app.switch(ActScene(app))
    else:
        to_map(app)


def to_map(app):
    run = app.exp
    run.stage = None
    save(app)
    app.switch(MapScene(app))


def enter(app, nid):
    run = app.exp
    n = run.enter(nid)
    t = n["type"]
    if t in ("battle", "elite", "boss"):
        save(app)
        battle(app)
    elif t == "event":
        run.start_event(n["event"])
        save(app)
        app.switch(EventScene(app, n["event"], "start"))
    elif t == "camp":
        save(app)
        app.switch(CampScene(app))
    elif t == "shop":
        save(app)
        app.switch(ShopScene(app))
    elif t == "anvil":
        save(app)
        app.switch(AnvilScene(app))
    elif t == "ash":                          # сгоревший узел: пусто, в пепле — немного руды
        if run.forge_on():
            run.add_mat("ore", 1)
        run.news = (run.news or []) + ["Пепелище: лава выжгла всё. В золе — руда +1" if run.forge_on() else
                                       "Пепелище: лава выжгла всё"]
        to_map(app)


def battle(app):
    run = app.exp
    n = run.nodes[run.node]
    app.switch(BattleScene(run.data, n["encounter"], autoplay=app.autoplay, squad=run.combat_squad(),
                           formation=run.formation, on_finish=lambda c, f: battle_done(app, c, f),
                           enemy_scale=run.enemy_scale(), difficulty=run.difficulty, cheats=app.profile.sandbox,
                           simple=True, solo=getattr(run, "solo", False), **neural_args(app)))


def neural_args(app):
    """Режим обучения (learn.py): бой ведут нейросети героев и врагов, после боя они учатся."""
    nl = getattr(app, "neural", None)
    if nl is None:
        return {}
    run = app.exp
    return {"neural": lambda c: nl.controller(run, c), "neural_done": lambda ctl: nl.after_battle(run, ctl)}


def battle_done(app, combat, formation):
    run = app.exp
    summary = run.finish_battle(combat, formation)
    if summary["result"] != "victory":
        finish(app)
        return
    kind = run.node_kind(run.nodes[run.node])
    offers = run.reward_offers(kind)
    bonus = run.bonus_item(kind) if kind in ("elite", "boss") else None
    if bonus:
        run.bag.append(bonus)
    run.stage = {"node": run.node, "kind": "reward", "offers": offers, "bonus": bonus,
                 "summary": {"result": "victory", "kind": kind, "xp": summary["xp"], "gold": summary["gold"],
                             "ups": sorted({h.name for h in summary["level_ups"]}),
                             "fallen": [h.name for h in summary["fallen"]], "extra": summary["extra"],
                             "act_done": summary.get("act_done"),
                             "learned": [f"{hn}: «{sn}» — ранг {r}" for hn, sn, r in summary.get("learned", [])],
                             "stats": summary.get("stats")}}
    save(app)
    reward = lambda: app.switch(RewardScene(app, run.stage["summary"], offers, bonus))
    if any(h.sp > 0 for h in run.heroes):          # ключевой уровень — сначала карты улучшения, прямо после боя
        app.switch(PickScene(app, then=reward, summary=run.stage["summary"]))
    else:
        reward()


def after_reward(app, summary):
    run = app.exp
    if run.result == "victory":
        finish(app)
    elif summary.get("act_done") is not None:
        run.next_act()
        run.stage = {"kind": "act"}
        save(app)
        app.switch(ActScene(app))
    else:
        to_map(app)


def finish(app):
    if getattr(app, "neural", None) is not None:
        app.neural.after_run(app.exp)              # опыт героев — в школы их классов
    end = app.profile.finish(app.exp)
    app.switch(EndScene(app, end))


# ---------- общий каркас экрана ----------

class XScene:
    stage = True

    def __init__(self, app):
        self.app = app
        self.mouse = (0, 0)
        self.hits = []          # (rect, action, tip)
        self.toast = None
        self.clock = 0.0

    @property
    def run(self):
        return self.app.exp

    @property
    def xd(self):
        """Данные похода: в походе — глазами его главы (свои акты, события, проклятия), в таверне — общие."""
        return self.app.exp.xd if getattr(self.app, "exp", None) else self.app.profile.xd

    def say(self, text):
        self.toast = (text, 2.4)

    def update(self, dt):
        self.clock += dt
        if self.toast:
            self.toast = (self.toast[0], self.toast[1] - dt) if self.toast[1] > dt else None

    def hit(self, rect, action=None, tip=None):
        self.hits.append((rect, action, tip))

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            self.mouse = ev.pos
            for r, action, _ in reversed(self.hits):
                if action is not None and r.collidepoint(ev.pos):
                    if isinstance(action, tuple) and action[0] == "levelup" and len(action) == 2:
                        h = self.run.heroes[action[1]]      # плашка «выбор улучшения» на карточке героя
                        self.app.switch(PickScene(self.app, then=lambda: self.app.switch(self), only=h))
                        return
                    self.act(action, ev.button)
                    return
        elif ev.type == pygame.KEYDOWN:
            self.key(ev.key)

    def act(self, action, button=1):
        pass

    def key(self, k):
        pass

    def button(self, surf, rect, label, action, enabled=True, accent=(90, 180, 255), tip=None):
        W.button(surf, rect, label, self.mouse, enabled, accent)
        self.hit(rect, action if enabled else None, tip)

    def tip_lines(self):
        for r, _, tip in reversed(self.hits):
            if tip and r.collidepoint(self.mouse):
                return [tip] if isinstance(tip, str) else tip
        return None

    def draw_tip(self, surf):
        lines = self.tip_lines()
        if not lines:
            return
        rows = []
        for ln in lines:
            s, col = (ln, T.TEXT) if isinstance(ln, str) else ln
            rows += [(x, col) for x in T.wrap(s, 14, 380)]
        w = max(T.font(14).size(s)[0] for s, _ in rows) + 20
        h = len(rows) * 18 + 12
        x = min(self.mouse[0] + 16, T.SCREEN_W - w - 8)
        y = min(self.mouse[1] + 18, T.SCREEN_H - h - 8)
        box = pygame.Rect(x, y, w, h)
        pygame.draw.rect(surf, (12, 14, 18), box, border_radius=6)
        pygame.draw.rect(surf, T.PANEL_EDGE, box, 1, border_radius=6)
        for i, (s, col) in enumerate(rows):
            T.text(surf, s, (box.x + 10, box.y + 6 + i * 18), 14, col, i == 0)

    def draw_toast(self, surf, y=None):
        if self.toast:
            T.text(surf, self.toast[0], (T.SCREEN_W // 2, y or T.SCREEN_H - 36), 17, (255, 190, 130), True,
                   center=True, shadow=True)

    def backdrop(self, surf, iid, mood="act", dim=170):
        """Иллюстрация на весь экран, притушенная, чтобы поверх читался интерфейс."""
        from ui import illustrations as IL
        img = IL.get(iid, mood, (T.SCREEN_W, T.SCREEN_W * 2 // 3), hd=True)
        surf.blit(img, (0, (T.SCREEN_H - img.get_height()) // 2))
        shade = pygame.Surface((T.SCREEN_W, T.SCREEN_H), pygame.SRCALPHA)
        shade.fill((6, 8, 10, dim))
        surf.blit(shade, (0, 0))

    def header(self, surf, title, sub=None):
        T.text(surf, title, (24, 14), 28, T.TEXT, True)
        if sub:
            T.text(surf, sub, (26, 52), 15, T.TEXT_DIM)
        if self.run:
            g = f"Золото: {self.run.gold}"
            T.text(surf, g, (T.SCREEN_W - 26 - T.font(22, True).size(g)[0], 16), 22, GOLD, True)

    def item_tip(self, item):
        xd = self.xd
        col = rarity_color(xd, item)
        rar = xd["items"]["rarities"][item["rarity"]]["name"]
        lines = [(X.item_name(item), col), (f"{xd['items']['slots'][item['slot']]} · {rar} · тир {item['tier']}",
                                            T.TEXT_DIM)]
        lines += [(s, T.TEXT) for s in X.item_lines(xd, item)]
        return lines

    def draw_party(self, surf, y, action_prefix="hero", h=150):
        """Отряд внизу: портрет, имя, уровень, HP, опыт, очки навыков, рана."""
        run = self.run
        n = len(run.heroes)
        w = min(300, (T.SCREEN_W - 48 - (n - 1) * 14) // max(1, n))
        x0 = (T.SCREEN_W - (n * w + (n - 1) * 14)) // 2
        data = run.data
        for i, hero in enumerate(run.heroes):
            r = pygame.Rect(x0 + i * (w + 14), y, w, h)
            hot = r.collidepoint(self.mouse)
            tn = tint_of(data, hero.cls)              # карточка — в цвете класса героя
            T.frame(surf, r, 240, accent=CURSE if hero.wounded else (tn["accent"] if hot else tn["dim"]),
                    fill=tn["hot"] if hot else tn["fill"], corner=tn["accent"], radius=10)
            img = hero_sprite(data, hero.cls)
            surf.blit(img, (r.x + 8, r.y + 8))
            x = r.x + 84
            T.text(surf, hero.name, (x, r.y + 8), 19, T.TEXT, True)
            T.text(surf, f"{data.classes[hero.cls]['name']} · ур. {hero.level}", (x, r.y + 32), 14, T.TEXT_DIM)
            mx = run.max_hp(hero)
            hp = run.hp_of(hero)
            W.bar(surf, pygame.Rect(x, r.y + 56, w - 96, 10), hp / mx, T.mix((230, 60, 50), (90, 220, 90), hp / mx))
            T.text(surf, f"{hp}/{mx}", (x, r.y + 68), 13, T.TEXT)
            W.bar(surf, pygame.Rect(x, r.y + 88, w - 96, 5), hero.xp / max(1, run.xp_next(hero)), W.XP)
            yy = r.y + 100
            chip = None
            if hero.sp:                               # невыбранные карты улучшения — клик открывает выбор
                label = "Выбрать улучшение" + (f" ×{hero.sp}" if hero.sp > 1 else "")
                chip = pygame.Rect(x - 2, yy - 2, T.font(13, True).size(label)[0] + 12, 19)
                pulse = 0.5 + 0.5 * math.sin(self.clock * 4)
                pygame.draw.rect(surf, T.mix((30, 50, 70), SP, 0.25 + 0.2 * pulse), chip, border_radius=5)
                pygame.draw.rect(surf, SP, chip, 1, border_radius=5)
                T.text(surf, label, (chip.x + 6, chip.y + 2), 13, (230, 245, 255), True)
                yy += 21
            if hero.wounded:
                T.text(surf, "ранен — до лагеря", (x, yy), 13, CURSE, True)
                yy += 17
            for gid in hero.gifts[:2]:
                T.text(surf, "дар: " + self.xd["gifts"][gid]["name"], (x, yy), 13, BLESS, True)
                yy += 17
            for pk in hero.perks[:max(0, 3 - len(hero.gifts[:2]))]:   # последствия событий
                if yy + 15 > r.bottom:
                    break
                T.text(surf, pk["name"], (x, yy), 13, T.AMBER, True)
                yy += 17
            tip = getattr(self, "party_tip", None)
            tip = tip(hero) if tip else [hero.name, "Клик — лист героя: навыки, снаряжение"]
            tip = list(tip) + [(f"{pk['name']}: {pk['desc']}" if pk.get("desc") else pk["name"], T.AMBER)
                               for pk in hero.perks]
            hl = getattr(self, "party_highlight", None)
            if hl and hl(hero):
                pygame.draw.rect(surf, GOLD, r, 3, border_radius=10)
            self.hit(r, (action_prefix, i), tip)
            if chip:
                self.hit(chip, ("levelup", i), [(f"{hero.name}: карты улучшения", SP),
                                                "Ветки навыков и мастерство — клик, чтобы выбрать"])

    def draw_buffs(self, surf, x, y):
        """Проклятия отряда — значками с подсказкой (дары — у героев)."""
        run = self.run
        for cid in run.curses:
            c = self.xd["curses"][cid]
            w = T.font(13, True).size(c["name"])[0] + 16
            r = pygame.Rect(x, y, w, 24)
            pygame.draw.rect(surf, (58, 30, 34), r, border_radius=6)
            pygame.draw.rect(surf, CURSE, r, 1, border_radius=6)
            T.text(surf, c["name"], (r.x + 8, r.y + 4), 13, CURSE, True)
            self.hit(r, None, [(c["name"], CURSE), c["desc"], "Снять: лагерь-торговец или событие"])
            x += w + 6
        cons = run.consequences()
        if cons:                                   # последствия выборов: репутация, засады, гости, финальный бой
            label = f"Последствия: {len(cons)}"
            w = T.font(13, True).size(label)[0] + 16
            r = pygame.Rect(x, y, w, 24)
            pygame.draw.rect(surf, T.PANEL_DARK, r, border_radius=6)
            pygame.draw.rect(surf, T.AMBER, r, 1, border_radius=6)
            T.text(surf, label, (r.x + 8, r.y + 4), 13, T.AMBER, True)
            self.hit(r, None, [("Последствия ваших выборов", T.AMBER)] +
                     [(s, BLESS if good else CURSE) for s, good in cons])
            x += w + 6
        return x


# ---------- таверна ----------

class TavernScene(XScene):
    def __init__(self, app):
        super().__init__(app)
        self.picked = []
        prof = app.profile
        self.chapter = next((c for c, _, ok in reversed(prof.chapters()) if ok), "swamp")             if hasattr(prof, "chapters") else "swamp"                  # глава похода — последняя открытая
        self.tier = prof.tier_open_of(self.chapter) if hasattr(prof, "tier_open_of") else             getattr(prof, "tier_open", 0)                              # сложность — высшая открытая

    def act(self, action, button=1):
        prof = self.app.profile
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "recruit":
            uid = action[1]
            if uid in self.picked:
                self.picked.remove(uid)
            elif len(self.picked) < self.squad_cfg()["squad_start"]:
                self.picked.append(uid)
            elif self.squad_cfg()["squad_start"] == 1:        # одиночка: клик по другому — замена
                self.picked = [uid]
            else:
                self.say("В поход берут не больше трёх героев — остальные присоединятся в пути")
        elif kind == "go":
            start_run(self.app, self.picked, self.tier, self.chapter)
        elif kind == "tier":
            if action[1] <= prof.tier_open_of(self.chapter):
                self.tier = action[1]
            else:
                self.say("Откроется победой на предыдущей сложности")
        elif kind == "chapter":
            if prof.chapter_open(action[1]):
                self.chapter = action[1]
                self.tier = min(self.tier, prof.tier_open_of(self.chapter))
            else:
                self.say("Глава откроется победой в предыдущей")
        elif kind == "chapters":
            self.app.switch(ChapterScene(self.app, self))
        elif kind == "resume":
            resume(self.app)
        elif kind == "abandon":
            prof.abandon()
            self.say("Поход брошен. Слава за него не начислена")
        elif kind == "upgrades":
            self.app.switch(UpgradeScene(self.app))
        elif kind == "vows":
            self.app.switch(VowsScene(self.app))
        elif kind == "hall":
            self.app.switch(HallScene(self.app))
        elif kind == "party_mode":                 # общая таверна: в поход отрядом или одним героем
            prof.solo = action[1]
            prof.mode = "solo" if prof.solo else "expedition"
            seen = {h.uid for h in prof.hall()}
            self.picked = [u for u in self.picked if u in seen][:1 if prof.solo else 3]
            from game.app import remember_mode
            if getattr(self.app, "_base_path", None):
                remember_mode(prof.mode, self.app._base_path)
            prof.save()
        elif kind == "reroll":
            if prof.reroll():
                self.picked = []
            else:
                self.say("Не хватает славы")
        elif kind == "menu":
            self.app.to_title()

    def squad_cfg(self):
        prof = self.app.profile
        return prof.squad_cfg() if hasattr(prof, "squad_cfg") else self.xd["config"]

    def key(self, k):
        cfg = self.squad_cfg()
        if k == pygame.K_SPACE:
            if self.app.profile.run_state:
                resume(self.app)
            elif cfg["squad_min"] <= len(self.picked) <= cfg["squad_start"]:
                start_run(self.app, self.picked, self.tier, self.chapter)
        elif k == pygame.K_u:
            self.app.switch(UpgradeScene(self.app))
        elif k == pygame.K_v:
            self.app.switch(VowsScene(self.app))
        elif k == pygame.K_ESCAPE:
            self.app.to_title()

    def draw(self, surf):
        prof = self.app.profile
        self.hits = []
        surf.fill((20, 16, 14))
        self.backdrop(surf, "tavern", "tavern", dim=120 if prof.run_state else 40)
        band = pygame.Surface((T.SCREEN_W, 80), pygame.SRCALPHA)
        band.fill((10, 8, 6, 170))
        surf.blit(band, (0, 0))
        T.text(surf, self.xd["tavern"]["name"], (24, 14), 30, GLORY, True, shadow=True)
        solo = getattr(prof, "solo", False)
        T.text(surf, "Одиночка: выберите одного героя — он пройдёт главу сам. Наведите — подробности." if solo else
               "Выберите 2–3 героев для похода, наведите — подробности.", (26, 54), 15, (220, 210, 190), shadow=True)
        g = f"Слава: {prof.glory}"
        T.text(surf, g, (T.SCREEN_W - 26 - T.font(22, True).size(g)[0], 18), 22, GLORY, True)
        if prof.run_state:
            self._draw_resume(surf)
        else:
            self._draw_roster(surf)
            self._draw_tiers(surf)
        y = T.SCREEN_H - 66
        cfg = self.squad_cfg()
        if not prof.run_state:
            ok = cfg["squad_min"] <= len(self.picked) <= cfg["squad_start"]
            self.button(surf, pygame.Rect(T.SCREEN_W - 300, y, 270, 46), f"В поход ({len(self.picked)})  Пробел",
                        "go", ok, GOLD)
            cost = self.xd["tavern"]["reroll_cost"]
            self.button(surf, pygame.Rect(564, y, 176, 46), f"Новые лица · {cost}", "reroll",
                        prof.glory >= cost, (170, 160, 210), f"Все новички в зале сменятся ({cost} славы); ветераны "
                                                             f"остаются")
        self.button(surf, pygame.Rect(30, y, 190, 46), "Стройка (U)", "upgrades", True, GLORY,
                    "Постройки таверны за славу и трофеи глав")
        vk = prof.vow_glory() if hasattr(prof, "vow_glory") else 1.0
        self.button(surf, pygame.Rect(228, y, 170, 46), f"Обеты ×{vk:.2f}" if vk > 1 else "Обеты (V)", "vows", True,
                    (230, 110, 120), "Обеты тяжести: поход труднее — славы больше")
        self.button(surf, pygame.Rect(406, y, 150, 46), "Зал славы", "hall", True, (170, 160, 210),
                    "Павшие герои и ветераны таверны")
        self.button(surf, pygame.Rect(T.SCREEN_W - 300 - 230, y, 210, 46), "Меню (Esc)", "menu", True)
        self.draw_tip(surf)
        self.draw_toast(surf, T.SCREEN_H - 90)

    def _draw_tiers(self, surf):
        """Сложность похода: Странник / Ветеран / Легенда (следующая — победой на предыдущей)."""
        prof = self.app.profile
        tiers = self.xd["config"]["tiers"]
        w, x0, y = 182, T.SCREEN_W - 26 - 3 * 182 - 12, 90
        chs = prof.chapters()
        if len(chs) > 1:                       # глава похода — карточка с картинкой; клик — экран выбора главы
            meta = self.xd["chapters"][self.chapter]
            col = tuple(meta.get("color", GLORY))
            r = pygame.Rect(x0, y, 3 * w + 12, 58)
            hot = r.collidepoint(self.mouse)
            T.frame(surf, r, 235, accent=col if hot else T.mix(col, (0, 0, 0), 0.3), corner=col)
            from ui import illustrations as IL
            thumb = IL.get(meta.get("art", "act_0"), "act", (78, 52))
            surf.blit(thumb, (r.x + 4, r.y + 3))
            pygame.draw.rect(surf, col, (r.x + 4, r.y + 3, 78, 52), 1)
            T.text(surf, "Глава похода", (r.x + 92, r.y + 6), 12, T.TEXT_DIM, True)
            T.text(surf, meta["name"], (r.x + 92, r.y + 22), 20, col, True)
            T.text(surf, "сменить" if hot else "клик — сменить", (r.right - 110, r.y + 24), 13, T.TEXT_DIM)
            self.hit(r, "chapters", [(meta["name"], col), meta.get("desc", ""), "Клик — выбор главы"])
            y += 80
        T.text(surf, "Сложность похода", (x0, y - 2), 14, (220, 210, 190), True, shadow=True)
        for i, t in enumerate(tiers):
            r = pygame.Rect(x0 + i * (w + 6), y + 18, w, 44)
            open_ = i <= prof.tier_open_of(self.chapter)
            col = (120, 220, 140) if i == 0 else (240, 180, 80) if i == 1 else (240, 100, 90)
            label = ("» " if i == self.tier else "") + t["name"] + ("" if open_ else " · закрыто")
            tip = [(t["name"], col), (t["desc"], T.TEXT), (f"Слава ×{t['glory']:g}", GLORY)]
            if not open_:
                tip.append(("Откроется победой на предыдущей сложности", CURSE))
            self.button(surf, r, label, ("tier", i), open_, col if i == self.tier else T.mix(col, (0, 0, 0), 0.4), tip)
        if hasattr(prof, "squad_cfg"):           # общая таверна: отряд или одиночка
            y += 70
            T.text(surf, "Поход", (x0, y - 2), 14, (220, 210, 190), True, shadow=True)
            mw = (3 * w + 12 - 6) // 2
            for i, (solo, label, tip) in enumerate(((False, "Отряд (2–3 героя)", "Экспедиция: поход отряда"),
                                                    (True, "Одиночка (1 герой)", "Один герой, камера за ним, 6 "
                                                                                 "навыков, врагов меньше"))):
                on = bool(prof.solo) == solo
                r = pygame.Rect(x0 + i * (mw + 6), y + 18, mw, 40)
                col = (150, 200, 255) if solo else GLORY
                self.button(surf, r, ("» " if on else "") + label, ("party_mode", solo), True,
                            col if on else T.mix(col, (0, 0, 0), 0.45), tip)

    def _draw_resume(self, surf):
        st = self.app.profile.run_state
        r = pygame.Rect(240, 160, 800, 380)
        pygame.draw.rect(surf, (34, 30, 28), r, border_radius=14)
        pygame.draw.rect(surf, GLORY, r, 2, border_radius=14)
        acts = X.chapter_view(self.xd, st.get("chapter", "swamp"))["acts"]
        act = acts[min(st.get("act", 0), len(acts) - 1)]["name"]
        T.text(surf, "Отряд в походе", (r.centerx, r.y + 30), 28, T.TEXT, True, center=True)
        T.text(surf, act, (r.centerx, r.y + 68), 18, GLORY, True, center=True)
        x = r.x + 60
        for h in st.get("heroes", []):
            img = hero_sprite(self.app.profile.data, h["cls"], 1.5)
            surf.blit(img, (x, r.y + 110))
            T.text(surf, h["name"], (x + img.get_width() // 2, r.y + 220), 16, T.TEXT, True, center=True)
            T.text(surf, f"ур. {h['level']}", (x + img.get_width() // 2, r.y + 242), 14, T.TEXT_DIM, center=True)
            x += 175
        self.button(surf, pygame.Rect(r.centerx - 290, r.bottom - 80, 300, 50), "Продолжить поход (Пробел)",
                    "resume", True, GOLD)
        self.button(surf, pygame.Rect(r.centerx + 30, r.bottom - 80, 260, 50), "Бросить поход", "abandon", True,
                    CURSE, "Поход закончится без славы, герои не вернутся")

    # места в зале таверны (иллюстрация tavern): доля ширины, линия земли (доля высоты картинки), смотрит влево
    SPOTS = [(0.10, 0.86, False), (0.35, 0.85, True), (0.57, 0.87, True), (0.22, 0.71, False),
             (0.46, 0.69, False), (0.64, 0.71, True), (0.03, 0.70, False), (0.33, 0.65, True),
             (0.53, 0.63, False), (0.76, 0.66, True)]

    def _draw_roster(self, surf):
        """Герои стоят по залу таверны; клик — в отряд / из отряда, наведение — всё о герое."""
        prof = self.app.profile
        data = prof.data
        img_h = T.SCREEN_W * 2 // 3
        top = (T.SCREEN_H - img_h) // 2
        px = T.SCREEN_W / 192                       # пикселей экрана на пиксель картинки
        placed = []
        for i, h in enumerate(prof.hall()[:len(self.SPOTS)]):
            sx, gy, flip = self.SPOTS[i]
            depth = 0.62 + 0.26 * (gy - 0.62) / 0.24      # дальше от зрителя — мельче
            img = hero_sprite(data, h.cls, px / 2 * depth)
            if flip:
                img = pygame.transform.flip(img, True, False)
            x = int(sx * T.SCREEN_W - img.get_width() / 2)
            placed.append((gy, h, img, x, int(top + gy * img_h)))
        placed.sort(key=lambda p: p[0])
        hover = None
        for gy, h, img, x, ground in placed:          # спереди стоящий перекрывает дальнего
            w = img.get_width()
            if pygame.Rect(x + w // 5, ground - img.get_height(), w * 3 // 5, img.get_height()).collidepoint(
                    self.mouse):
                hover = (h, img, x, ground)
        for gy, h, img, x, ground in placed:
            on = h.uid in self.picked
            hot = hover is not None and hover[0] is h
            w = img.get_width()
            sh = pygame.Surface((int(w * 0.7), max(8, w // 10)), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (*GOLD, 150) if on else (0, 0, 0, 120), sh.get_rect())
            if on:
                pygame.draw.ellipse(sh, (*GOLD, 255), sh.get_rect(), 3)
            surf.blit(sh, (x + w * 0.15, ground - sh.get_height() * 0.6))
            if hot:
                m = pygame.mask.from_surface(img)
                outline = m.to_surface(setcolor=(255, 240, 200, 255), unsetcolor=(0, 0, 0, 0))
                for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
                    surf.blit(outline, (x + dx, ground - img.get_height() + dy))
            dimg = img
            if not on and not hot:
                dimg = img.copy()
                dimg.fill((205, 195, 185, 255), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(dimg, (x, ground - img.get_height()))
            self.hit(pygame.Rect(x + w // 5, ground - img.get_height(), w * 3 // 5, img.get_height()),
                     ("recruit", h.uid))
            if on or hot:
                tw = T.font(16, True).size(h.name)[0] + 16
                tr = pygame.Rect(x + w // 2 - tw // 2, ground - img.get_height() * 5 // 6 - 30, tw, 24)
                tn = tint_of(prof.data, h.cls)
                pygame.draw.rect(surf, T.mix((20, 16, 12), tn["accent"], 0.15), tr, border_radius=6)
                pygame.draw.rect(surf, tn["accent"] if on else tn["dim"], tr, 2 if on else 1, border_radius=6)
                T.text(surf, h.name, tr.center, 16, tn["accent"] if on else T.TEXT, True, center=True)
        names = [h.name for h in prof.hall() if h.uid in self.picked]
        solo = getattr(prof, "solo", False)
        msg = (("Идёт в поход: " if solo else "В отряде: ") + ", ".join(names)) if names else \
            ("Кликните по герою в зале, чтобы выбрать его" if solo else "Кликните по героям в зале, чтобы взять их в поход")
        T.text(surf, msg, (T.SCREEN_W - 26 - T.font(16, True).size(msg)[0], 54), 16, GOLD if names else T.TEXT, True,
               shadow=True)
        if hover:
            self._draw_info(surf, *hover)

    def _draw_info(self, surf, h, img, x, ground):
        """Карточка героя при наведении: класс, ранг, черта, навыки, доктрина, вещь."""
        data, xd = self.app.profile.data, self.xd
        rk = xd["tavern"]["ranks"][str(h.rank)]
        tr = xd["tavern"]["traits"][h.trait]
        rows = [(h.name, T.TEXT, 22, True),
                (f"{data.classes[h.cls]['name']} · {rk['name']} (ранг {h.rank}) · ур. {h.level}", GLORY, 15, True),
                None, (f"{tr['name']}: {tr['desc']}", (220, 200, 160), 14, False),
                None, ("Навыки", T.TEXT_DIM, 13, True)]
        if h.vet:                                  # ветеран таверны: сколько походов и где
            names = ", ".join(xd["chapters"].get(c, {}).get("name", c) for c in h.vet.get("chapters", []))
            rows.insert(2, (f"Ветеран{'-одиночка' if h.vet.get('solo') else ''}: побед {h.vet.get('wins', 0)}"
                            + (f" ({names})" if names else ""), (150, 220, 170), 14, True))
        ult = story_meta.ult_of(data, h.cls)
        for k, sid in enumerate(h.skills):
            sk = data.skills[sid]
            key = "QWER"[k] if k < 4 else "·"
            if sid == ult:
                rows.append((f"{key} · ультимейт {sk['name']} — {sk.get('desc', '')}", GOLD, 13, False))
            else:
                rows.append((f"{key} · {sk['name']} — {sk.get('desc', '')}", T.TEXT, 13, False))
        if h.doctrine:
            pd = data.paths[h.doctrine]
            rows += [None, (f"Доктрина «{pd['name']}»: {pd['passive'].get('desc', '')}", (200, 170, 255), 13, False)]
        for item in h.gear.values():
            rows += [None, (X.item_name(item), rarity_color(xd, item), 14, True)]
            rows += [(ln, T.TEXT, 13, False) for ln in X.item_lines(xd, item)]
        w = 420
        lines = []
        for row in rows:
            if row is None:
                lines.append(None)
                continue
            text, col, size, bold = row
            lines += [(ln, col, size, bold) for ln in T.wrap(text, size, w - 28, bold)]
        hgt = 20 + sum(8 if ln is None else ln[2] + 5 for ln in lines)
        bx = x + img.get_width() * 3 // 4 + 10
        if bx + w > T.SCREEN_W - 10:
            bx = x + img.get_width() // 4 - w - 10
        by = max(80, min(ground - img.get_height(), T.SCREEN_H - 120 - hgt))
        box = pygame.Surface((w, hgt), pygame.SRCALPHA)
        pygame.draw.rect(box, (16, 13, 11, 240), box.get_rect(), border_radius=10)
        tn = tint_of(data, h.cls)
        pygame.draw.rect(box, (*(tn["accent"] if h.uid in self.picked else tn["dim"]), 255), box.get_rect(), 2,
                         border_radius=10)
        surf.blit(box, (bx, by))
        y = by + 12
        for ln in lines:
            if ln is None:
                y += 8
                continue
            T.text(surf, ln[0], (bx + 14, y), ln[2], ln[1], ln[3])
            y += ln[2] + 5
        hint = "клик — убрать из отряда" if h.uid in self.picked else "клик — взять в поход"
        T.text(surf, hint, (bx + w - 14 - T.font(12).size(hint)[0], by + 14), 12, T.TEXT_DIM)


def cost_chips(scene, surf, prof, cost, x, y):
    """Цена: слава и трофеи глав чипами; нехватка — красным."""
    xd = prof.xd
    for k, v in cost.items():
        have = prof.glory if k == "glory" else prof.trophies.get(k, 0)
        name = "Слава" if k == "glory" else xd["trophies"][k]["name"]
        col = GLORY if k == "glory" else tuple(xd["trophies"][k]["color"])
        label = f"{name} {v}"
        w = T.font(14, True).size(label)[0] + 16
        r = pygame.Rect(x, y, w, 24)
        pygame.draw.rect(surf, T.PANEL_DARK, r, border_radius=6)
        pygame.draw.rect(surf, col if have >= v else CURSE, r, 1, border_radius=6)
        T.text(surf, label, (r.x + 8, r.y + 4), 14, col if have >= v else CURSE, True)
        x += w + 6
    return x


class UpgradeScene(XScene):
    """Стройка таверны: улучшения за славу и постройки за славу и трофеи глав (общие у Экспедиции и Одиночки)."""

    def act(self, action, button=1):
        prof = self.app.profile
        if action == "back":
            to_tavern(self.app)
        elif action[0] == "buy":
            if not prof.buy_upgrade(action[1]):
                self.say("Не хватает славы")
        elif action[0] == "build":
            if not prof.build(action[1]):
                self.say("Не хватает славы или трофеев глав")

    def key(self, k):
        if k in (pygame.K_ESCAPE, pygame.K_u):
            to_tavern(self.app)

    def draw(self, surf):
        prof = self.app.profile
        if not prof.xd.get("buildings"):
            return self._draw_old(surf)
        self.hits = []
        surf.fill((20, 16, 14))
        self.backdrop(surf, "tavern", "tavern", dim=200)
        self.header(surf, "Стройка таверны", "Слава — за бои и акты (даже в проигранном походе), трофеи глав — за "
                                             "боссов. Таверна общая у Экспедиции и Одиночки.")
        x = T.SCREEN_W - 26
        chips = [("glory", prof.glory)] + [(k, prof.trophies.get(k, 0)) for k in prof.xd["trophies"]]
        for k, v in reversed(chips):
            name = "Слава" if k == "glory" else prof.xd["trophies"][k]["name"]
            col = GLORY if k == "glory" else tuple(prof.xd["trophies"][k]["color"])
            label = f"{name}: {v}"
            w = T.font(16, True).size(label)[0] + 18
            x -= w
            r = pygame.Rect(x, 16, w, 28)
            pygame.draw.rect(surf, T.PANEL_DARK, r, border_radius=7)
            pygame.draw.rect(surf, col, r, 1, border_radius=7)
            T.text(surf, label, (r.x + 9, r.y + 5), 16, col, True)
            if k != "glory":
                self.hit(r, None, [(name, col), prof.xd["trophies"][k]["desc"]])
            x -= 8
        items = []
        for uid, up in self.xd["tavern"]["upgrades"].items():
            lv, top = prof.level(uid), len(up["costs"])
            cost = prof.upgrade_cost(uid)
            items.append((up["name"], up["desc"], lv, top, self._value_text(uid, lv),
                          self._value_text(uid, lv + 1) if cost is not None else None,
                          {"glory": cost} if cost is not None else None, ("buy", uid)))
        for bid, b in self.xd["buildings"].items():
            lv, top = prof.building_level(bid), len(b["levels"])
            items.append((b["name"], b["desc"], lv, top, b["levels"][lv - 1]["text"] if lv else "не построено",
                          b["levels"][lv]["text"] if lv < top else None, prof.building_cost(bid), ("build", bid)))
        cw, ch = (T.SCREEN_W - 72) // 3, 150
        for i, (name, desc, lv, top, now, nxt, cost, action) in enumerate(items):
            r = pygame.Rect(24 + (i % 3) * (cw + 12), 92 + (i // 3) * (ch + 10), cw, ch)
            done = nxt is None
            T.frame(surf, r, 235, accent=GLORY if lv else T.PANEL_EDGE, corner=GLORY if lv else T.PANEL_EDGE)
            T.text(surf, name, (r.x + 14, r.y + 10), 18, T.TEXT, True)
            for k in range(top):
                pygame.draw.circle(surf, GLORY if k < lv else (70, 62, 54), (r.right - 20 - (top - 1 - k) * 16, r.y + 20), 6)
            T.text(surf, fit(desc, 13, r.w - 28), (r.x + 14, r.y + 34), 13, T.TEXT_DIM)
            T.text(surf, fit("Сейчас: " + now, 14, r.w - 28), (r.x + 14, r.y + 56), 14, T.TEXT)
            if not done:
                T.text(surf, fit("Дальше: " + nxt, 14, r.w - 28), (r.x + 14, r.y + 78), 14, BLESS)
                cost_chips(self, surf, prof, cost, r.x + 14, r.y + 106)
                ok = prof.can_pay(cost) if action[0] == "build" else prof.glory >= cost["glory"]
                b = pygame.Rect(r.right - 120, r.y + 104, 106, 32)
                self.button(surf, b, "Построить" if action[0] == "build" else "Купить", action, ok, GLORY)
            else:
                T.text(surf, "построено полностью", (r.x + 14, r.y + 110), 14, GLORY, True)
        self.button(surf, pygame.Rect(30, T.SCREEN_H - 66, 220, 46), "Назад (Esc)", "back")
        self.draw_tip(surf)
        self.draw_toast(surf)

    def _draw_old(self, surf):
        prof = self.app.profile
        self.hits = []
        surf.fill((20, 16, 14))
        T.text(surf, "Улучшения таверны", (24, 14), 30, GLORY, True)
        T.text(surf, "Слава даётся за бои, элиту, боссов и пройденные акты — даже если поход проигран.", (26, 54),
               15, T.TEXT_DIM)
        g = f"Слава: {prof.glory}"
        T.text(surf, g, (T.SCREEN_W - 26 - T.font(22, True).size(g)[0], 18), 22, GLORY, True)
        y = 100
        for uid, up in self.xd["tavern"]["upgrades"].items():
            r = pygame.Rect(60, y, T.SCREEN_W - 120, 110)
            pygame.draw.rect(surf, (36, 32, 30), r, border_radius=10)
            pygame.draw.rect(surf, T.PANEL_EDGE, r, 1, border_radius=10)
            lv, top = prof.level(uid), len(up["costs"])
            T.text(surf, up["name"], (r.x + 20, r.y + 14), 22, T.TEXT, True)
            T.text(surf, f"ступень {lv}/{top}", (r.x + 20 + T.font(22, True).size(up['name'])[0] + 16, r.y + 20), 15,
                   GLORY)
            T.text(surf, up["desc"], (r.x + 20, r.y + 46), 15, T.TEXT_DIM)
            T.text(surf, "Сейчас: " + self._value_text(uid, lv), (r.x + 20, r.y + 72), 15, T.TEXT)
            cost = prof.upgrade_cost(uid)
            if cost is not None:
                T.text(surf, "Дальше: " + self._value_text(uid, lv + 1), (r.x + 460, r.y + 72), 15, BLESS)
                self.button(surf, pygame.Rect(r.right - 230, r.y + 30, 200, 48), f"Купить: {cost}", ("buy", uid),
                            prof.glory >= cost, GLORY)
            y += 124
        self.button(surf, pygame.Rect(30, T.SCREEN_H - 66, 220, 46), "Назад (Esc)", "back")
        self.draw_toast(surf)

    def _value_text(self, uid, lv):
        up = self.xd["tavern"]["upgrades"][uid]
        v = up["values"][min(lv, len(up["values"]) - 1)]
        if uid == "hall":
            return f"героев в зале: {v}"
        if uid == "renown":
            return f"ветераны {v['2']}%, герои {v['3']}%"
        if uid == "provisions":
            return f"+{v} золота в начале похода"
        if uid == "guests":
            classes = []
            for k in range(1, lv + 1):
                classes += up["values"][min(k, len(up["values"]) - 1)]
            data = self.app.profile.data
            return ", ".join(data.classes[c]["name"] for c in classes) or "только 8 основных классов"
        return str(v)


class VowsScene(XScene):
    """Обеты тяжести: поход труднее (враги сильнее, лечения меньше…) — славы больше. Действуют с первой победы."""

    def act(self, action, button=1):
        prof = self.app.profile
        if action == "back":
            to_tavern(self.app)
        elif action[0] in ("vow+", "vow-") and prof.vows_open():
            vid = action[1]
            prof.set_vow(vid, prof.vows.get(vid, 0) + (1 if action[0] == "vow+" else -1))
        elif action == "clear":
            prof.vows = {}
            prof.save()

    def key(self, k):
        if k in (pygame.K_ESCAPE, pygame.K_v):
            to_tavern(self.app)

    def draw(self, surf):
        prof = self.app.profile
        self.hits = []
        surf.fill((18, 12, 12))
        self.backdrop(surf, "tavern", "tavern", dim=215)
        self.header(surf, "Обеты тяжести", "Перед походом можно дать обеты: поход станет труднее, слава — больше. "
                                           "Действуют вместе со сложностью.")
        k = prof.vow_glory()
        T.text(surf, f"Слава похода ×{k:.2f}", (T.SCREEN_W - 260, 20), 22, (230, 110, 120), True)
        if not prof.vows_open():
            T.text(surf, "Обеты откроются после первой победы в любой главе.", (T.SCREEN_W // 2, 300), 22, CURSE, True,
                   center=True, shadow=True)
        y = 96
        for vid, v in self.xd["vows"].items():
            r = pygame.Rect(60, y, T.SCREEN_W - 120, 70)
            rank = prof.vows.get(vid, 0)
            col = (230, 110, 120) if rank else T.PANEL_EDGE
            T.frame(surf, r, 235, accent=col, corner=col)
            T.text(surf, v["name"], (r.x + 16, r.y + 10), 19, T.TEXT if prof.vows_open() else T.TEXT_DIM, True)
            T.text(surf, f"{v['desc']} · за ступень: {v['text']}, слава +{v['glory'] * 100:.0f}%", (r.x + 16, r.y + 40),
                   14, T.TEXT_DIM)
            for i in range(v["ranks"]):
                pygame.draw.circle(surf, (230, 110, 120) if i < rank else (70, 50, 50), (r.right - 210 + i * 22, r.centery), 8)
            ok = prof.vows_open()
            self.button(surf, pygame.Rect(r.right - 120, r.y + 17, 46, 36), "−", ("vow-", vid), ok and rank > 0,
                        (230, 110, 120))
            self.button(surf, pygame.Rect(r.right - 66, r.y + 17, 46, 36), "+", ("vow+", vid), ok and rank < v["ranks"],
                        (230, 110, 120))
            y += 80
        self.button(surf, pygame.Rect(30, T.SCREEN_H - 66, 220, 46), "Назад (Esc)", "back")
        self.button(surf, pygame.Rect(270, T.SCREEN_H - 66, 220, 46), "Снять все обеты", "clear", bool(prof.vows),
                    (170, 160, 210))
        self.draw_tip(surf)


class HallScene(XScene):
    """Зал славы: павшие герои (и брошенные походы); ветераны, что ждут в таверне."""

    def act(self, action, button=1):
        to_tavern(self.app)

    def key(self, k):
        if k in (pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_RETURN):
            to_tavern(self.app)

    def draw(self, surf):
        prof = self.app.profile
        data, xd = prof.data, prof.xd
        self.hits = []
        surf.fill((14, 12, 16))
        self.backdrop(surf, "defeat", "act", dim=210)
        self.header(surf, "Зал славы", "Имена тех, кто не вернулся. Справа — ветераны, что ждут в таверне.")
        y = 92
        if not prof.fallen:
            T.text(surf, "Пока никто не пал.", (60, y + 10), 18, T.TEXT_DIM)
        for f in list(reversed(prof.fallen))[:13]:
            img = hero_sprite(data, f["cls"], 0.6)
            surf.blit(pygame.transform.grayscale(img), (40, y))
            ch = xd["chapters"].get(f["chapter"], {}).get("name", f["chapter"])
            T.text(surf, f"{f['name']} · {data.classes[f['cls']]['name']} · ур. {f['level']}", (90, y + 4), 16,
                   T.TEXT, True)
            T.text(surf, f"{ch}, акт {f['act']} · {f['reason']}" + (" · в одиночку" if f.get("solo") else "")
                   + (f" · побед до того: {f['wins']}" if f.get("wins") else ""), (90, y + 24), 13, T.TEXT_DIM)
            y += 46
        vets = [h for h in prof.roster if h.vet]
        x = T.SCREEN_W // 2 + 40
        T.text(surf, "Ветераны таверны", (x, 92), 18, (150, 220, 170), True)
        y = 122
        for h in vets[:12]:
            img = hero_sprite(data, h.cls, 0.6)
            surf.blit(img, (x, y))
            rk = xd["tavern"]["ranks"][str(h.rank)]["name"]
            T.text(surf, f"{h.name} · {data.classes[h.cls]['name']} · {rk}", (x + 50, y + 4), 16, T.TEXT, True)
            T.text(surf, f"побед {h.vet.get('wins', 0)} · старт с ур. {h.level}"
                   + (" · только в одиночке" if h.vet.get("solo") else ""), (x + 50, y + 24), 13, T.TEXT_DIM)
            y += 46
        if not vets:
            T.text(surf, "Победите — и выжившие вернутся сюда ветеранами.", (x, 122), 15, T.TEXT_DIM)
        self.button(surf, pygame.Rect(30, T.SCREEN_H - 66, 220, 46), "Назад (Esc)", "back")
        self.draw_tip(surf)


# ---------- акт ----------

class ActScene(XScene):
    """Заставка акта."""

    def key(self, k):
        if k in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE):
            to_map(self.app)

    def act(self, action, button=1):
        to_map(self.app)

    def draw(self, surf):
        self.hits = []
        surf.fill((10, 14, 12))
        a = self.run.act_def
        self.backdrop(surf, a.get("art", f"act_{self.run.act}"), "act", dim=95)
        img_h = T.SCREEN_W * 2 // 3                  # герои в масштабе картинки: пиксель спрайта = пиксель сцены
        k = T.SCREEN_W / 192 / 2
        party_in_scene(surf, self.run.data, self.run.heroes, (T.SCREEN_H - img_h) // 2 + int(img_h * 0.95),
                       30, int(56 * k), k=k, dark=0.8)
        band = pygame.Surface((T.SCREEN_W, 300), pygame.SRCALPHA)
        band.fill((6, 8, 10, 170))
        surf.blit(band, (0, 240))
        T.text(surf, a["name"], (T.SCREEN_W // 2, 280), 44, GLORY, True, center=True, shadow=True)
        y = 350
        for line in T.wrap(a.get("intro", ""), 20, 820):
            T.text(surf, line, (T.SCREEN_W // 2, y), 20, (220, 220, 210), center=True, shadow=True)
            y += 28
        diff = self.run.data.config["difficulties"][self.run.difficulty]["name"]
        T.text(surf, f"Сложность боёв: {diff} · поход: {self.run.tier_def['name']}", (T.SCREEN_W // 2, y + 20), 16,
               T.TEXT_DIM, center=True)
        r = pygame.Rect(T.SCREEN_W - 300, T.SCREEN_H - 84, 260, 50)
        self.button(surf, r, "В путь (Пробел)", "go", True, GOLD)


# ---------- выбор главы ----------

class ChapterScene(XScene):
    """Выбор главы похода: карточки с картинкой акта, описанием, механиками, типичными врагами и боссом.
    Закрытая глава видна, но не выбирается (откроется победой в предыдущей)."""

    def __init__(self, app, tavern):
        super().__init__(app)
        self.tavern = tavern

    def act(self, action, button=1):
        if action[0] == "pick":
            self.tavern.act(("chapter", action[1]))
            if self.tavern.chapter == action[1]:
                self.app.switch(self.tavern)
            else:
                self.say("Глава откроется победой в предыдущей")
        elif action == "back":
            self.app.switch(self.tavern)

    def key(self, k):
        chs = self.app.profile.chapters()
        if k == pygame.K_ESCAPE:
            self.act("back")
        elif pygame.K_1 <= k <= pygame.K_9 and k - pygame.K_1 < len(chs):
            self.act(("pick", chs[k - pygame.K_1][0]))

    def _enemy(self, surf, eid, x, ground, ok, boss=False, glow=None):
        """Враг главы на земле картинки, лицом к отряду (влево). Возвращает ширину."""
        e = self.app.profile.data.enemies.get(eid)
        if not e:
            return 0
        spr = _SPRITES.get([eid, e.get("sprite_fallback")], e.get("role", "melee"), tuple(e["color"]), boss)
        spr = pygame.transform.flip(spr, True, False)
        if not ok:
            spr = pygame.transform.grayscale(spr)
        w, h = spr.get_size()
        sh = pygame.Surface((w * 3 // 4 + (20 if glow else 0), 12 if glow else 9), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (*glow, 110) if glow else (0, 0, 0, 140), sh.get_rect())
        surf.blit(sh, (x + w // 2 - sh.get_width() // 2, ground - sh.get_height() // 2))
        surf.blit(spr, (x, ground - h))
        self.hit(pygame.Rect(x, ground - h, w, h), None, [(e["name"], glow or T.TEXT), "Босс главы" if boss else
                                                           "Враг главы"])
        return w

    def draw(self, surf):
        prof, xd = self.app.profile, self.app.profile.xd
        self.hits = []
        surf.fill(T.BG)
        self.backdrop(surf, "tavern", "tavern", dim=205)
        T.text(surf, "Куда идёт отряд?", (T.SCREEN_W // 2, 40), 34, GLORY, True, center=True, shadow=True)
        chs = prof.chapters()
        n = len(chs)
        cw = min(600, (T.SCREEN_W - 60 - (n - 1) * 24) // n)
        x0 = (T.SCREEN_W - (n * cw + (n - 1) * 24)) // 2
        from ui import illustrations as IL
        for i, (cid, name, ok) in enumerate(chs):
            meta = xd["chapters"][cid]
            col = tuple(meta.get("color", GLORY))
            r = pygame.Rect(x0 + i * (cw + 24), 84, cw, 652)
            on = cid == self.tavern.chapter
            hot = ok and r.collidepoint(self.mouse)
            T.frame(surf, r, 240, accent=col if (on or hot) else T.mix(col, (0, 0, 0), 0.45), corner=col,
                    fill=T.mix(T.PANEL, col, 0.12 if hot else 0.05))
            iw = cw - 24
            full = iw * 2 // 3
            ih = full - 60                                 # верх картинки (небо, своды) срезан — больше места тексту
            img = IL.get(meta.get("art", "act_0"), "act", (iw, full), hd=True).subsurface((0, 40, iw, ih))
            if not ok:
                img = pygame.transform.grayscale(img)
            surf.blit(img, (r.x + 12, r.y + 12))
            pygame.draw.rect(surf, col if ok else T.TEXT_DIM, (r.x + 12, r.y + 12, iw, ih), 2)
            ground = r.y + 12 + ih - 12                    # враги стоят на земле картинки, босс справа — крупнее
            gx = r.x + 26
            for eid in meta.get("enemies", []):
                gx += self._enemy(surf, eid, gx, ground, ok) - 6
            b = xd and prof.data.enemies.get(meta.get("boss"))
            if b:
                spr_w = _SPRITES.get([meta["boss"], b.get("sprite_fallback")], b.get("role", "melee"),
                                     tuple(b["color"]), True).get_width()
                self._enemy(surf, meta["boss"], r.x + 12 + iw - spr_w - 12, ground, ok, True, col)
            y = r.y + 24 + ih
            T.text(surf, f"{i + 1}. {name}", (r.x + 16, y), 26, col if ok else T.TEXT_DIM, True)
            y += 36
            for ln in T.wrap(meta.get("desc", ""), 15, cw - 32)[:3]:
                T.text(surf, ln, (r.x + 16, y), 15, T.TEXT)
                y += 19
            y += 8
            for m in meta.get("mechanics", []):
                pygame.draw.polygon(surf, col, [(r.x + 20, y + 3), (r.x + 25, y + 8), (r.x + 20, y + 13),
                                                (r.x + 15, y + 8)])
                lines = T.wrap(m, 14, cw - 48)[:2]
                for k, ln in enumerate(lines):
                    T.text(surf, ln, (r.x + 32, y + k * 17), 14, T.TEXT_DIM)
                y += 17 * len(lines) + 6
            y += 6
            acts = X.chapter_view(xd, cid)["acts"]
            path = " → ".join(a["name"].split(". ", 1)[-1] for a in acts)
            for k, ln in enumerate(T.wrap("Путь: " + path, 14, cw - 32)[:2]):
                T.text(surf, ln, (r.x + 16, y + k * 18), 14, T.TEXT if ok else T.TEXT_DIM, k == 0)
            b = prof.data.enemies.get(meta.get("boss"))
            if b:
                T.text(surf, f"В конце пути: {b['name']}", (r.x + 16, y + 42), 14, col, True)
            tiers = xd["config"]["tiers"]
            if ok:
                status = (f"Открыто сложностей: {prof.tier_open_of(cid) + 1} из {len(tiers)} · "
                          f"побед: {prof.chapter_wins.get(cid, 0)}")
            else:
                status = f"Закрыто — откроется победой в главе «{xd['chapters'][meta['unlock']]['name']}»"
            T.text(surf, status, (r.x + 16, r.bottom - 32), 14, BLESS if ok else CURSE, True)
            if on:
                T.text(surf, "выбрана", (r.right - 86, r.bottom - 32), 14, col, True)
            self.hit(r, ("pick", cid), [(name, col), "Клик — выбрать главу" if ok else "Глава ещё закрыта"])
        self.button(surf, pygame.Rect(T.SCREEN_W // 2 - 110, T.SCREEN_H - 54, 220, 42), "Назад (Esc)", "back")
        self.draw_tip(surf)
        self.draw_toast(surf, T.SCREEN_H - 74)


# ---------- карта ----------

class MapScene(XScene):
    def __init__(self, app):
        super().__init__(app)
        self.node_pos = {}
        self._layout()
        news = getattr(self.run, "news", None)
        if news:                              # извержение на последнем шаге — сразу видно
            self.say(" · ".join(news))
            self.run.news = []

    def relayout(self):
        self._layout()

    def _layout(self):
        nodes = self.run.nodes
        layers = max(n["layer"] for n in nodes.values()) + 1
        x0, x1, y0, y1 = 100, T.SCREEN_W - 100, 150, 465
        for n in nodes.values():
            x = x0 + (x1 - x0) * n["layer"] / max(1, layers - 1)
            y = y0 + (y1 - y0) * (n["idx"] + 0.5) / n["count"]
            self.node_pos[n["id"]] = (x, y)

    def node_at(self, pos):
        for nid, p in self.node_pos.items():
            if math.dist(p, pos) <= 26:
                return nid
        return None

    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            nid = self.node_at(ev.pos)
            if nid and nid in self.run.available():
                enter(self.app, nid)
                return
        super().handle(ev)

    def act(self, action, button=1):
        if action[0] == "hero":
            self.app.switch(HeroScene(self.app, action[1], back=lambda: self.app.switch(MapScene(self.app))))
        elif action == "tavern":
            save(self.app)
            to_tavern(self.app)

    def key(self, k):
        if k == pygame.K_h:
            self.act(("hero", 0))
        elif k == pygame.K_ESCAPE:
            self.act("tavern")
        elif pygame.K_1 <= k <= pygame.K_4 and k - pygame.K_1 < len(self.run.heroes):
            self.act(("hero", k - pygame.K_1))

    def draw(self, surf):
        run = self.run
        self.hits = []
        if len(self.node_pos) != len(run.nodes):
            self._layout()
        surf.fill(T.BG)
        self.backdrop(surf, run.act_def.get("art", f"act_{run.act}"), "act", dim=200)
        self.header(surf, run.act_def["name"], f"Сложность: {run.data.config['difficulties'][run.difficulty]['name']}"
                    f"  ·  выберите узел (подсвечены)  ·  1–4 / H — лист героя  ·  Esc — в таверну (сохранено)")
        x = self.draw_buffs(surf, 26, 78)
        if run.bag:
            msg = f"В сумке вещей: {len(run.bag)} — наденьте в листе героя"
            T.text(surf, msg, (max(x + 12, 26), 82), 14, GOLD, True)
        if run.heat_on():
            self._draw_heat(surf)
        if run.forge_on():
            draw_mats(self, surf, run, T.SCREEN_W - 26, 52, right=True)
        from ui import map_art as MA
        avail = set(run.available())
        visited = set(run.path)
        board = pygame.Rect(40, 110, T.SCREEN_W - 80, 418)        # карта — на доске тёмного дерева
        T.frame(surf, board, 150, accent=T.AMBER_DIM)
        rad = {nid: (30 if n["type"] == "boss" else 25 if n["type"] == "elite" else 22) for nid, n in run.nodes.items()}
        for n in run.nodes.values():
            for nxt in n["next"]:
                if nxt not in self.node_pos:
                    continue
                if n["id"] in visited and nxt in visited:
                    state = "done"
                elif n["id"] == run.node and nxt in avail:
                    state = "open"
                else:
                    state = "future"
                MA.draw_trail(surf, self.node_pos[n["id"]], self.node_pos[nxt], state, self.clock,
                              rad[n["id"]], rad[nxt])
        hover = self.node_at(self.mouse)
        for n in run.nodes.values():
            x, y = self.node_pos[n["id"]]
            nid = n["id"]
            state = ("here" if nid == run.node else "open" if nid in avail else "done" if nid in visited else "future")
            col = NODE_COLORS[n["type"]]
            r = MA.draw_node(surf, (x, y), n["type"], col, state, self.clock, n.get("thread"),
                             molten=n.get("molten"), lava=nid in run.lava_next)
            if nid == hover and state != "future":
                pygame.draw.circle(surf, (255, 240, 200), (x, y), r + 5, 2)
            label = n.get("label") or NODE_NAMES[n["type"]]
            MA.ribbon(surf, label, (x, y + r + 5), GLORY if n.get("thread") else col, bool(n.get("thread")),
                      dim=state == "future")
        if run.node in self.node_pos and run.heroes:           # отряд стоит на текущем узле
            x, y = self.node_pos[run.node]
            img = hero_sprite(run.data, run.heroes[0].cls, 0.7)
            bob = int(2 * math.sin(self.clock * 3))
            fx, fy = x - rad[run.node] - 10, y + 8                 # стоит слева от медальона, на тропе
            sh = pygame.Surface((30, 8), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (0, 0, 0, 130), sh.get_rect())
            surf.blit(sh, (fx - 15, fy - 4))
            surf.blit(img, (fx - img.get_width() // 2, fy - img.get_height() + 2 + bob))
        self.draw_party(surf, T.SCREEN_H - 230, h=150)
        self.button(surf, pygame.Rect(T.SCREEN_W - 260, T.SCREEN_H - 66, 236, 44), "В таверну (Esc)", "tavern", True,
                    (170, 160, 210), "Поход сохранён — продолжить можно из таверны")
        if hover:
            self._node_tip(surf, run.nodes[hover])
        else:
            self.draw_tip(surf)

    def _draw_heat(self, surf):
        """Жар кузни: шкала с порогами извержений; на пороге лава зальёт отмеченные узлы."""
        run = self.run
        hc = run.heat_cfg()
        r = pygame.Rect(T.SCREEN_W - 420, 84, 300, 14)
        T.text(surf, f"Жар {run.heat}/{hc['max']}", (r.x - 96, r.y - 3), 15, HEAT, True, shadow=True)
        pygame.draw.rect(surf, (30, 16, 10), r.inflate(4, 4), border_radius=6)
        fill = r.copy()
        fill.w = int(r.w * run.heat / hc["max"])
        glow = 0.5 + 0.5 * math.sin(self.clock * 5)
        pygame.draw.rect(surf, T.mix((200, 80, 30), (255, 200, 90), glow * run.heat / hc["max"]), fill, border_radius=5)
        for t in hc["thresholds"]:
            tx = r.x + int(r.w * t / hc["max"])
            pygame.draw.line(surf, (255, 230, 180) if run.heat < t else (90, 40, 20), (tx, r.y - 3), (tx, r.bottom + 3), 2)
        nxt = next((t for t in hc["thresholds"] if run.heat < t), None)
        tip = [("Жар кузни", HEAT), f"Каждый шаг +{hc['step']}, каждый бой +{hc['battle']}.",
               "На пороге — извержение: отмеченные узлы зальёт лава (бои станут огненными — сильнее, но больше руды "
               "и золота; остальное сгорит).",
               "На пределе — большое извержение: сгорят все лагеря, лавки и наковальни впереди, отряд получит ожоги.",
               "Чем выше Жар, тем чаще опасности в боях. Остудить — лагерь и события."]
        if nxt:
            tip.append((f"До извержения: {nxt - run.heat}", CURSE))
        self.hit(pygame.Rect(r.x - 100, r.y - 6, r.w + 104, 24), None, tip)

    def _node_tip(self, surf, n):
        data = self.run.data
        lines = [(n.get("label") or NODE_NAMES[n["type"]], NODE_COLORS[n["type"]])]
        if n.get("molten"):
            lines.append(("Огненный бой: залит лавой — враги крепче, опасностей больше; руда ×2, металл, золото ×1.5",
                          HEAT))
        if n["id"] in self.run.lava_next:
            lines.append(("Лава подступает: следующее извержение зальёт этот узел", HEAT))
        enc = n["encounter"] if n["type"] != "boss" else self.run.boss_encounter()
        if n["type"] in ("battle", "elite", "boss") and enc is not None:
            e = data.encounters[enc]
            lines.append((e["name"], T.TEXT))
            counts = {}
            for x in e["enemies"]:
                name = data.enemies[x["type"]]["name"]
                counts[name] = counts.get(name, 0) + 1
            lines += [(f"{k} ×{v}" if v > 1 else k, T.TEXT_DIM) for k, v in counts.items()]
            sc = self.run.enemy_scale(n)
            lines.append((f"сила врагов: здоровье ×{sc['hp']:.1f}, урон ×{sc['damage']:.1f}", (240, 160, 120)))
            if n["type"] == "elite":
                lines.append(("Награда: благословение на выбор + редкая вещь", GLORY))
            if n["type"] == "boss":
                lines.append(("Награда: сильное благословение + вещь; следующий акт", GLORY))
        elif n["type"] == "event":
            lines.append(("Неизвестно, что ждёт впереди", T.TEXT_DIM) if not n.get("thread") else
                         ("Продолжение сюжетной нити", GLORY))
        elif n["type"] == "camp":
            lines.append(("Отдых (лечение, раны) или тренировка; можно сбросить ветки навыков", T.TEXT_DIM))
        elif n["type"] == "shop":
            lines.append(("Вещи, лекарь, снятие проклятий; продажа лишнего", T.TEXT_DIM))
        elif n["type"] == "anvil":
            lines.append(("Выковать вещь из руды, перековать, переплавить; шедевры", T.TEXT_DIM))
        elif n["type"] == "ash":
            lines.append(("Сгорело в извержении — здесь ничего нет", T.TEXT_DIM))
        w = max(T.font(14).size(s)[0] for s, _ in lines) + 20
        x, y = self.node_pos[n["id"]]
        box = pygame.Rect(min(x + 32, T.SCREEN_W - w - 10), max(10, y - 20), w, len(lines) * 19 + 12)
        pygame.draw.rect(surf, (12, 14, 18), box, border_radius=6)
        pygame.draw.rect(surf, T.PANEL_EDGE, box, 1, border_radius=6)
        for i, (s, col) in enumerate(lines):
            T.text(surf, s, (box.x + 10, box.y + 6 + i * 19), 14, col, i == 0)


# ---------- лист героя ----------

class HeroScene(XScene):
    """Навыки (ранги и ветки — только в походе), снаряжение и сумка. В лагере — сброс очков навыков."""

    def __init__(self, app, idx, back, respec=False):
        super().__init__(app)
        self.idx = idx
        self.back = back
        self.respec = respec

    @property
    def hero(self):
        return self.run.heroes[min(self.idx, len(self.run.heroes) - 1)]

    def act(self, action, button=1):
        run, h = self.run, self.hero
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "tab":
            self.idx = action[1]
        elif kind == "branch":
            sid, b = action[1], action[2]
            nxt = run.branch_next(h, sid, b)
            if nxt and not run.take_branch(h, sid, b):
                self.say(f"Ступень ветки: выбор улучшения и ранг навыка {nxt[1]}+")
            h.pick_offer = None
        elif kind == "levelup":
            self.app.switch(PickScene(self.app, then=lambda: self.app.switch(self), only=h))
        elif kind == "equip":
            if not run.equip(h, action[1]):
                item = next((i for i in run.bag if i["uid"] == action[1]), None)
                cls = self.xd["items"]["uniques"].get((item or {}).get("unique") or "", {}).get("class")
                if cls:
                    self.say(f"Эта вещь — только для класса «{run.data.classes[cls]['name']}»")
        elif kind == "unequip":
            run.unequip(h, action[1])
        elif kind == "respec":
            run.respec(h)
        elif kind == "back":
            save(self.app)
            self.back()

    def key(self, k):
        if k in (pygame.K_ESCAPE, pygame.K_h):
            self.act("back")
        elif pygame.K_1 <= k <= pygame.K_4 and k - pygame.K_1 < len(self.run.heroes):
            self.idx = k - pygame.K_1
        elif k == pygame.K_TAB:
            self.idx = (self.idx + 1) % len(self.run.heroes)

    def draw(self, surf):
        run, h, data, xd = self.run, self.hero, self.run.data, self.xd
        self.hits = []
        surf.fill(T.BG)
        self.header(surf, "Отряд", "Ранги и ветки навыков действуют только в этом походе. Вещи — клик по вещи "
                                   "в сумке (надеть) или в слоте (снять).")
        x = 24
        for i, hh in enumerate(run.heroes):
            r = pygame.Rect(x, 80, 200, 34)
            on = i == self.idx
            tn = tint_of(data, hh.cls)               # вкладка — в цвете класса героя
            pygame.draw.rect(surf, tn["hot"] if on else tn["fill"], r, border_radius=8)
            pygame.draw.rect(surf, tn["accent"] if on else tn["dim"], r, 2 if on else 1, border_radius=8)
            T.text(surf, f"{i + 1}. {hh.name}" + (f"  ({hh.sp})" if hh.sp else ""), (r.x + 12, r.y + 7), 16,
                   T.TEXT if on else T.TEXT_DIM, True)
            self.hit(r, ("tab", i))
            x += 210
        p = run.proto(h, party=False)          # чистые числа: прокачка и вещи, без проклятий отряда и боя
        # портрет и статы
        left = pygame.Rect(24, 128, 330, 600)
        pygame.draw.rect(surf, T.PANEL, left, border_radius=10)
        img = hero_sprite(data, h.cls, 2.0)
        surf.blit(img, (left.x + 10, left.y + 6))
        tx = left.x + img.get_width() + 18
        T.text(surf, h.name, (tx, left.y + 14), 22, T.TEXT, True)
        T.text(surf, data.classes[h.cls]["name"], (tx, left.y + 42), 15, T.TEXT_DIM)
        T.text(surf, f"{xd['tavern']['ranks'][str(h.rank)]['name']} · ранг {h.rank}", (tx, left.y + 62), 14, GLORY,
               True)
        tr = xd["tavern"]["traits"][h.trait]
        trr = pygame.Rect(tx, left.y + 84, 150, 20)
        T.text(surf, tr["name"], (trr.x, trr.y), 15, (220, 200, 160), True)
        self.hit(trr, None, [tr["name"], tr["desc"]])
        y = left.y + img.get_height() + 14
        mx = run.max_hp(h)
        rows = [("Уровень", f"{h.level}  (опыт {h.xp}/{run.xp_next(h)})"),
                ("Здоровье", f"{run.hp_of(h)} / {mx}"),
                ("Атака", self._atk(p)),
                ("Темп / дальн.", f"раз в {p['attack']['cooldown']:.2f} с · {p['attack']['range']} кл."),
                ("Сила навыков", f"×{p['power']:.2f}"),
                ("Крит / уклонение", f"{p['crit'] * 100:.0f}% (×{p['crit_mult']:.2f}) / {p['dodge'] * 100:.0f}%"),
                ("Броня / AP", f"{p['armor']:.1f} / {p['ap_max']}")]
        for k, v in rows:
            T.text(surf, k, (left.x + 14, y), 14, T.TEXT_DIM)
            T.text(surf, v, (left.x + 140, y), 14, T.TEXT, True)
            y += 22
        if h.wounded:
            T.text(surf, f"Ранен: −{(1 - xd['config']['wound_mult']) * 100:.0f}% до лагеря", (left.x + 14, y), 14,
                   CURSE, True)
            y += 22
        at = stats.attrs(data, h.cls, h.rpg)
        y += 6
        for a in stats.ATTRS:
            T.text(surf, ATTR_NAMES[a], (left.x + 14, y), 14, T.TEXT_DIM)
            T.text(surf, f"{at[a]:.0f}", (left.x + 140, y), 14, tuple(data.stats_mode["attrs"][a]["color"]), True)
            y += 20
        T.text(surf, "Атрибуты растут с уровнем сами (основной — быстрее).", (left.x + 14, y + 4), 12, T.TEXT_DIM)
        if h.doctrine:
            pd = data.paths[h.doctrine]
            dr = pygame.Rect(left.x + 14, y + 26, 300, 18)
            T.text(surf, "Доктрина: " + pd["name"], (dr.x, dr.y), 14, (200, 170, 255), True)
            self.hit(dr, None, [pd["name"], pd["passive"].get("desc", "")])
        self._draw_skills(surf, p)
        self._draw_gear(surf)
        if getattr(self.app, "neural", None) is not None:       # режим обучения: опыт сети героя
            from game.learn_mode import draw_progress
            draw_progress(surf, pygame.Rect(24, T.SCREEN_H - 200, 330, 128), self.app.neural.agent(h).stats,
                          title="Сеть героя")
        self.button(surf, pygame.Rect(T.SCREEN_W - 230, T.SCREEN_H - 62, 206, 44), "Назад (Esc)", "back")
        if self.respec:
            self.button(surf, pygame.Rect(T.SCREEN_W - 470, T.SCREEN_H - 62, 226, 44), "Сбросить ветки", "respec",
                        h.sp_spent(xd) > 0, SP, "Лагерь: взятые ветки вернутся выборами улучшений, "
                                                "ранги навыков (от применения) останутся")
        if h.sp:
            self.button(surf, pygame.Rect(24, T.SCREEN_H - 62, 300, 44), f"Выбрать улучшение ({h.sp})", "levelup",
                        True, SP, "Карты улучшения навыков: ветки и мастерство")
        self.draw_tip(surf)
        self.draw_toast(surf, T.SCREEN_H - 80)

    @staticmethod
    def _atk(p):
        """Атака: обычная и с критом (скейл основного атрибута уже учтён)."""
        base = p["attack"]["damage"] * (p.get("scale") or {}).get("basic", 1.0)
        return f"{base:.0f} (крит {base * p['crit_mult']:.0f})"

    def _draw_skills(self, surf, p):
        run, h, data = self.run, self.hero, self.run.data
        hc = self.xd["config"]["hero"]
        box = pygame.Rect(368, 128, 560, 600)
        pygame.draw.rect(surf, T.PANEL, box, border_radius=10)
        T.text(surf, "Навыки", (box.x + 14, box.y + 10), 18, T.TEXT, True)
        if h.sp:
            T.text(surf, f"выборов: {h.sp}", (box.right - 120, box.y + 12), 16, SP, True)
        y = box.y + 38
        rh = min(132, (box.bottom - y - 6) // max(1, len(h.skills)) - 6)       # 3 навыка + ультимейт — карточки ниже
        ult = story_meta.ult_of(data, h.cls)
        for k_, sid in enumerate(h.skills):
            sk = p["skill_defs"].get(sid, data.skills[sid])
            r = pygame.Rect(box.x + 10, y, box.w - 20, rh)
            is_ult = sid == ult
            pygame.draw.rect(surf, (58, 48, 34) if is_ult else (50, 38, 28), r, border_radius=8)
            if is_ult:
                pygame.draw.rect(surf, GOLD, r, 1, border_radius=8)
            key = "QWER"[k_] if k_ < 4 else ""
            T.text(surf, key, (r.x + 10, r.y + 7), 17, GOLD if is_ult else T.SELECT, True)
            locked = is_ult and not X.ult_open(data, h)
            T.text(surf, sk["name"] + ("  · ультимейт" if is_ult else ""), (r.x + 30, r.y + 8), 17,
                   T.TEXT_DIM if locked else T.TEXT, True)
            if locked:
                lv = story_meta.skill_level(data, h.cls, sid)
                T.text(surf, f"откроется на {lv} уровне", (r.x + 260, r.y + 30), 13, (230, 150, 110), True)
            T.text(surf, f"AP {sk['ap']} · перезарядка {sk['cooldown']:.1f} с", (r.x + 12, r.y + 30), 13, T.TEXT_DIM)
            vals = stats.skill_values(p, sk)
            vx = r.x + 12 + T.font(13).size(f"AP {sk['ap']} · перезарядка {sk['cooldown']:.1f} с")[0] + 14
            for what, v, c in vals[:2]:
                txt = f"{what} {v}" + (f" · крит {c}" if c else "")
                col = (255, 170, 120) if what == "урон" else (130, 230, 160)
                T.text(surf, txt, (vx, r.y + 29), 14, col, True)
                vx += T.font(14, True).size(txt)[0] + 14
            rank = h.rank_of(sid)                          # ранг растёт сам от применения навыка в боях
            for k in range(hc["max_rank"]):
                pygame.draw.circle(surf, GOLD if k < rank else (70, 70, 80), (r.right - 150 + k * 18, r.y + 18), 6)
            pr = run.rank_progress(h, sid)
            bar = pygame.Rect(r.right - 158, r.y + 30, 96, 6)
            if pr:
                W.bar(surf, bar, min(1.0, pr[0] / max(1, pr[1])), GOLD)
                T.text(surf, f"{pr[0]}/{pr[1]}", (bar.right + 6, bar.y - 5), 12, T.TEXT_DIM)
            else:
                T.text(surf, "мастер", (bar.x, bar.y - 5), 12, GOLD, True)
            self.hit(pygame.Rect(r.right - 160, r.y + 8, 150, 34), None,
                     [f"Ранг {rank} из {hc['max_rank']}", "Растёт сам: применяйте навык в бою" +
                      (f" — ещё {pr[1] - pr[0]} до ранга {rank + 1}" if pr else ""),
                      f"Ранг: +{hc['rank_amount'] * 100:.0f}% урона/лечения, −{hc['rank_cooldown'] * 100:.0f}% перезарядки"])
            for i, line in enumerate(T.wrap(sk.get("desc", ""), 13, r.w - 24)[:2 if rh >= 124 else 1]):
                T.text(surf, line, (r.x + 12, r.y + 50 + i * 16), 13, T.TEXT)
            if sid in data.branches:
                cur = h.branches.get(sid)
                bx = r.x + 12
                for b in ("A", "B"):
                    br = data.branches[sid][b]
                    tier = cur[1] if cur and cur[0] == b else 0
                    nxt = run.branch_next(h, sid, b)
                    label = f"{b}: {br['name']}" + (f" {tier}/{len(br['tiers'])}" if tier else "")
                    tip = [(f"Ветка {b}: {br['name']}", (255, 150, 90))]
                    for k, t in enumerate(br["tiers"][:len(hc["branch_cost"])]):
                        tip.append((f"{k + 1}. {t['name']}: {t['desc']}", T.TEXT if k < tier else T.TEXT_DIM))
                    if nxt:
                        tip.append((f"Следующая ступень: выбор улучшения, ранг навыка {nxt[1]}+", SP))
                    elif cur and cur[0] != b:
                        tip.append(("Взята другая ветка (сброс — в лагере)", CURSE))
                    ok = bool(nxt) and h.sp >= nxt[0] and rank >= nxt[1]
                    bw = (r.w - 34) // 2
                    rr = pygame.Rect(bx, r.bottom - 36, bw, 30)
                    accent = (255, 150, 90) if tier else (120, 130, 150)
                    W.button(surf, rr, label if T.font(18, True).size(label)[0] < bw - 10 else label[:22] + "…",
                             self.mouse, ok or bool(tier), accent)
                    self.hit(rr, ("branch", sid, b) if ok else None, tip)
                    bx += bw + 10
            y += rh + 6

    def _draw_gear(self, surf):
        run, h, xd = self.run, self.hero, self.xd
        box = pygame.Rect(942, 128, T.SCREEN_W - 966, 600)
        pygame.draw.rect(surf, T.PANEL, box, border_radius=10)
        T.text(surf, "Снаряжение", (box.x + 12, box.y + 10), 18, T.TEXT, True)
        y = box.y + 40
        for slot in X.SLOTS:
            r = pygame.Rect(box.x + 10, y, box.w - 20, 46)
            item = h.gear.get(slot)
            pygame.draw.rect(surf, (50, 38, 28), r, border_radius=6)
            T.text(surf, xd["items"]["slots"][slot], (r.x + 10, r.y + 4), 12, T.TEXT_DIM)
            if item:
                pygame.draw.rect(surf, rarity_color(xd, item), r, 1, border_radius=6)
                ic = item_icon(item, 32)
                if ic:
                    surf.blit(ic, (r.right - 40, r.y + 7))
                T.text(surf, X.item_name(item), (r.x + 10, r.y + 22), 14, rarity_color(xd, item), True)
                self.hit(r, ("unequip", slot), self.item_tip(item) + [("клик — снять в сумку", T.TEXT_DIM)])
            else:
                T.text(surf, "пусто", (r.x + 10, r.y + 22), 14, T.TEXT_DIM)
            y += 52
        y += 8
        T.text(surf, f"Сумка ({len(run.bag)})", (box.x + 12, y), 16, T.TEXT, True)
        y += 24
        for item in run.bag[:12]:
            r = pygame.Rect(box.x + 10, y, box.w - 20, 24)
            hot = r.collidepoint(self.mouse)
            pygame.draw.rect(surf, (70, 52, 34) if hot else (46, 35, 26), r, border_radius=5)
            ic = item_icon(item, 20)
            if ic:
                surf.blit(ic, (r.right - 24, r.y + 2))
            T.text(surf, X.item_name(item), (r.x + 8, r.y + 4), 13, rarity_color(xd, item), True)
            old = h.gear.get(item["slot"])
            tip = self.item_tip(item) + [("клик — надеть", T.TEXT_DIM)]
            if old:
                tip.append((f"вместо: {X.item_name(old)}", T.TEXT_DIM))
            self.hit(r, ("equip", item["uid"]), tip)
            y += 27
        if len(run.bag) > 12:
            T.text(surf, f"и ещё {len(run.bag) - 12}", (box.x + 12, y), 13, T.TEXT_DIM)


# ---------- событие ----------

class EventScene(XScene):
    """Событие: иллюстрация и текст, варианты → (кто бросает → кубик d20 в 3D) → исход → следующий шаг / конец.
    Исход броска считается и сохраняется сразу при выборе героя: выход и возврат не перебросят кубик —
    кубик лишь показывает уже выпавшее число."""

    def __init__(self, app, eid, step):
        super().__init__(app)
        self.eid = eid
        self.step = step
        self.phase = "choose"           # choose | pick | roll | result
        self.option = None
        self.roll = None
        self.roller = None
        self.out = None                 # исход: {"text", "lines", "next", "battle", "gift"}
        self.die = None
        self.landed_t = 0.0

    @property
    def ev(self):
        return self.run.event(self.eid)

    def act(self, action, button=1):
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "opt":
            opt = self.ev["steps"][self.step]["options"][action[1]]
            self.option = opt
            if "check" in opt:                # бросает тот, у кого лучший шанс — без выбора
                self.act(("roller", self.run.heroes.index(self.run.best_roller(opt["check"]))))
            else:
                self._resolve(opt, None, None)
        elif kind == "roller":
            hero = self.run.heroes[action[1]]
            r = self.run.roll(hero, self.option["check"])
            self.roll, self.roller = r, hero
            self._resolve(self.run.outcome(self.option, r["result"]), hero, r)
            from ui.dice import Die
            self.die = Die(150, seed=r["d20"] * 31 + len(self.run.path))
            self.phase = "roll"
        elif kind == "die":
            self._die_click()
        elif kind == "cancel":
            self.phase = "choose"
            self.option = None
        elif kind == "next":
            self._continue()

    def _die_click(self):
        d = self.die
        if d.state == "idle":
            d.roll(self.roll["d20"])
        elif d.state == "rolling":
            d.t = d.ROLL_TIME                           # нетерпеливым — сразу итог
        elif self.landed_t > 0.35:
            self.phase = "result"

    def skip_roll(self):
        """Сразу к итогу (тесты, повторный клик)."""
        if self.phase == "roll":
            self.phase = "result"

    def key(self, k):
        if self.phase == "roll" and k in (pygame.K_SPACE, pygame.K_RETURN):
            self._die_click()
        elif self.phase == "result" and k in (pygame.K_SPACE, pygame.K_RETURN):
            self._continue()
        elif self.phase == "pick" and k == pygame.K_ESCAPE:
            self.act("cancel")
        elif self.phase == "choose" and pygame.K_1 <= k <= pygame.K_9:
            i = k - pygame.K_1
            opts = self.ev["steps"][self.step]["options"]
            if i < len(opts) and self.run.option_ok(opts[i]):
                self.act(("opt", i))
        elif self.phase == "pick" and pygame.K_1 <= k <= pygame.K_4 and k - pygame.K_1 < len(self.run.heroes):
            self.act(("roller", k - pygame.K_1))

    def handle(self, ev):
        if self.phase == "roll" and ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self._die_click()
            return
        super().handle(ev)

    def _resolve(self, o, hero, r):
        """Исход применяется сразу и сохраняется."""
        run = self.run
        text = run.fill(o.get("text") or self.option.get("result") or "", hero, self.ev)
        lines = run.apply_ops(o.get("do", []), hero)
        fight = next((x["battle"] for x in lines if isinstance(x, dict) and "battle" in x), None)
        gift = next((x["gift"] for x in lines if isinstance(x, dict) and "gift" in x), None)
        lines = [x for x in lines if isinstance(x, str)]
        nxt = None if fight else o.get("next")
        if not text and not lines and not fight and not gift and not hero:
            if nxt:                                   # молча к следующему шагу
                run.stage = {"node": run.node, "kind": "event", "event": self.eid, "step": nxt}
                save(self.app)
                self.app.switch(EventScene(self.app, self.eid, nxt))
            else:                                     # «пройти мимо»
                to_map(self.app)
            return
        self.out = {"text": text, "lines": lines, "next": nxt, "battle": fight, "gift": gift}
        run.stage = {"node": run.node, "kind": "event", "event": self.eid, "step": nxt, "battle": fight,
                     "gift": gift}
        save(self.app)
        self.phase = "result"

    def _continue(self):
        event_next(self.app, self.eid, self.out["next"], self.out["battle"], self.out["gift"])

    def update(self, dt):
        super().update(dt)
        if self.die:
            self.die.update(dt)
            self.landed_t = self.landed_t + dt if self.die.done else 0.0

    # ---------- рисование ----------
    # Иллюстрация на весь экран (исходник без сжатия), отряд стоит на её переднем плане слева внизу. Название и текст —
    # сверху на мягком затемнении, варианты — прозрачным текстом справа внизу: наведение подсвечивает строку.

    OPT_X = 600

    def draw(self, surf):
        run = self.run
        self.hits = []
        surf.fill((8, 10, 12))
        ev = self.ev
        st = ev["steps"][self.step]
        thread = ev.get("kind") == "thread"
        from ui import illustrations as IL
        step_id = f"{self.eid}.{self.step}"
        img = IL.get(step_id if IL.has(step_id) else self.eid, ev.get("kind", "short"),
                     (T.SCREEN_W, T.SCREEN_W * 2 // 3), hd=True)
        surf.blit(img, (0, (T.SCREEN_H - img.get_height()) // 2))
        scene_party(surf, run, mouse=self.mouse, k=2.5, step=128)
        kind = {"thread": "СЮЖЕТНАЯ НИТЬ", "companion": "СПУТНИКИ", "scene": "СЦЕНА", "short": "ВСТРЕЧА"}.get(
            ev.get("kind"), "")
        text = self.out["text"] if self.phase == "result" else run.fill(st["text"], None, ev)
        title = T.wrap(ev["title"], 34, 900, True)
        body = T.wrap(text, 19, 820)
        extra = 0
        if self.phase == "result":                   # исход: строка броска и что изменилось
            extra = (32 if self.roll else 0) + sum(len(T.wrap("• " + ln, 17, 820)) * 24 for ln in self.out["lines"])                 + (24 if self.out.get("gift") else 0) + 10
        w = max([T.font(34, True).size(x)[0] for x in title] + [T.font(19).size(x)[0] for x in body] + [380]) + 48
        self._plate(surf, pygame.Rect(22, 12, min(w, 900), 34 + 42 * len(title) + 26 * len(body) + extra + 14))
        T.text(surf, kind, (40, 18), 13, GLORY if thread else (170, 190, 210), True, shadow=True)
        y = 38
        for line in title:
            T.text(surf, line, (40, y), 34, (250, 244, 230), True, shadow=True)
            y += 42
        for line in body:
            T.text(surf, line, (42, y), 19, (236, 232, 222), shadow=True)
            y += 26
        if self.phase == "result":
            self._draw_result(surf, 42, y + 10, 820)
        elif self.phase in ("choose", "roll"):
            self._draw_options(surf, st, enabled=self.phase == "choose")
        elif self.phase == "pick":
            self._draw_pick(surf)
        if self.phase == "roll":
            self._draw_roll(surf)
        else:
            self.draw_tip(surf)

    def _plate(self, surf, r, alpha=175):
        """Тёмная полупрозрачная подложка под текст: читается на любой картинке."""
        box = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(box, (6, 8, 12, alpha), box.get_rect(), border_radius=10)
        surf.blit(box, r)

    def _shade(self, surf, y, h, top=True):
        """Мягкое затемнение края картинки под текст (без рамок — текст лежит прямо на сцене)."""
        g = pygame.Surface((T.SCREEN_W, h), pygame.SRCALPHA)
        for i in range(h):
            t = (1 - i / h) if top else i / h
            g.fill((6, 8, 10, int(205 * t ** 1.4)), (0, i, T.SCREEN_W, 1))
        surf.blit(g, (0, y))

    def _option_info(self, opt):
        run = self.run
        notes = []
        req = opt.get("requires") or {}
        if "class_any" in req:
            notes.append("нужен: " + " / ".join(run.data.classes[c]["name"] for c in req["class_any"]))
        if "gold" in req:
            notes.append(f"{req['gold']} золота")
        if "pay" in req:
            k = run.trade_mult()
            notes.append(f"{run.pay_price(req['pay'])} золота" + (f" (жабы: ×{k:.2f})" if k != 1 else ""))
        if "items_at_least" in req:
            notes.append("нужна вещь")
        for k, v in req.get("mat_at_least", {}).items():       # руда и металлы кузни
            m = run.xd.get("mats", {}).get(k, {"name": k})
            notes.append(f"{m['name']}: {v} (есть {run.mat(k)})")
        if "heat_at_least" in req:
            notes.append(f"Жар от {req['heat_at_least']}")
        if "heat_below" in req:
            notes.append(f"Жар ниже {req['heat_below']}")
        if req.get("flag_at_least", {}).get("forged"):
            notes.append("нужна своя ковка")
        names = {"toads": "жабы", "village": "Камышинка", "hunters": "охотники", "rivals": "Ржавые"}
        names.update({k: v.lower() for k, v in run.xd.get("factions", {}).items()})
        for f, v in req.get("rep_at_least", {}).items():
            notes.append(f"{names.get(f, f)}: репутация от {v:+d}")
        for f, v in req.get("rep_below", {}).items():
            notes.append(f"{names.get(f, f)}: репутация ниже {v:+d}")
        if "check" in opt:
            chk = opt["check"]
            best = run.best_roller(chk)
            notes.append(f"d20 · {ATTR_NAMES[chk['attr']]}, сложность {run.dc(chk)} · бросает {best.name} "
                         f"({run.chance(best, chk) * 100:.0f}%)")
            if chk.get("classes"):
                notes.append("легче: " + ", ".join(run.data.classes[c]["name"] for c in chk["classes"]))
        return " · ".join(notes)

    def _text_option(self, surf, y, label, info, action, ok=True, accent=GOLD):
        """Вариант — строка текста прямо на картинке; под курсором — цветом и стрелкой."""
        w = T.SCREEN_W - self.OPT_X - 30
        r = pygame.Rect(self.OPT_X - 24, y - 4, w + 24, 46 if info else 30)
        hot = ok and r.collidepoint(self.mouse)
        col = accent if hot else ((246, 240, 228) if ok else (150, 150, 155))
        T.text(surf, ("›  " if hot else "") + label, (self.OPT_X - (18 if hot else 0), y), 20, col, True, shadow=True)
        if info:
            T.text(surf, info, (self.OPT_X + 22, y + 25), 13, (230, 214, 160) if ok else (140, 140, 145), shadow=True)
        self.hit(r, action if ok else None)

    def _options_top(self, n, with_info=True):
        return T.SCREEN_H - 34 - n * (52 if with_info else 36)

    def _options_plate(self, surf, top, bottom):
        self._plate(surf, pygame.Rect(self.OPT_X - 34, top - 14, T.SCREEN_W - self.OPT_X + 34 - 18, bottom - top + 18))

    def _draw_options(self, surf, st, enabled=True):
        opts = st["options"]
        y = self._options_top(len(opts))
        self._options_plate(surf, y, y + 52 * len(opts) - 6)
        for i, opt in enumerate(opts):
            ok = self.run.option_ok(opt)
            info = self._option_info(opt)
            label = f"{i + 1}. {self.run.fill(opt['text'], None, self.ev)}"
            self._text_option(surf, y, label, fit(info, 13, T.SCREEN_W - self.OPT_X - 60), ("opt", i), ok and enabled)
            y += 52

    def _draw_pick(self, surf):
        run = self.run
        chk = self.option["check"]
        n = len(run.heroes) + 1
        y = self._options_top(n) - 34
        self._options_plate(surf, y, y + 34 + 52 * n - 16)
        T.text(surf, f"Кто попробует?  {ATTR_NAMES[chk['attr']]}, сложность {run.dc(chk)}", (self.OPT_X, y), 18,
               GLORY, True, shadow=True)
        y += 34
        for i, h in enumerate(run.heroes):
            ch = run.chance(h, chk)
            self._text_option(surf, y, f"{i + 1}. {h.name} — {run.data.classes[h.cls]['name']}",
                              f"бонус {run.check_bonus(h, chk):+d} · шанс {ch * 100:.0f}%", ("roller", i))
            y += 52
        self._text_option(surf, y, "Назад (Esc)", None, "cancel", accent=(170, 190, 220))

    def _draw_result(self, surf, x, y, w):
        if self.roll:
            name, col = RESULT_NAMES[self.roll["result"]]
            r = self.roll
            T.text(surf, f"{name}  ({r['d20']} {r['bonus']:+d} = {r['total']} / {r['dc']})", (x, y), 21, col, True,
                   shadow=True)
            y += 32
        for line in self.out["lines"]:
            bad = any(s_ in line for s_ in ("теряет", "Проклятие", "ранен", "покидает")) or "−" in line
            for ln in T.wrap("• " + line, 17, w):
                T.text(surf, ln, (x + 6, y), 17, CURSE if bad else BLESS, True, shadow=True)
                y += 24
        if self.out.get("gift"):
            T.text(surf, "• Дар: выберите, кому он достанется", (x + 6, y), 17, GLORY, True, shadow=True)
        label = "В бой!  (Пробел)" if self.out["battle"] else "Дальше  (Пробел)"
        self._options_plate(surf, T.SCREEN_H - 70, T.SCREEN_H - 40)
        self._text_option(surf, T.SCREEN_H - 70, label, None, "next")

    def _draw_roll(self, surf):
        """Кубик по центру поверх сцены, как в BG3: сложность сверху, бонус снизу."""
        shade = pygame.Surface((T.SCREEN_W, T.SCREEN_H), pygame.SRCALPHA)
        shade.fill((4, 6, 10, 200))
        surf.blit(shade, (0, 0))
        run, r, d = self.run, self.roll, self.die
        chk = self.option["check"]
        cx, cy = T.SCREEN_W // 2, 330
        T.text(surf, ATTR_NAMES[chk["attr"]].upper(), (cx, 120), 18, (170, 180, 200), True, center=True)
        T.text(surf, f"Сложность {r['dc']}", (cx, 158), 40, T.TEXT, True, center=True, shadow=True)
        name, col = RESULT_NAMES[r["result"]]
        tint = col if d.done else None
        d.draw(surf, (cx, cy), tint)
        T.text(surf, f"{self.roller.name}:  d20 {r['bonus']:+d}", (cx, cy + 165), 20, T.TEXT, True, center=True)
        if d.state == "idle":
            pulse = 160 + int(80 * math.sin(self.clock * 4))
            T.text(surf, "Нажмите на кубик, чтобы бросить", (cx, cy + 200), 18, (pulse, pulse, 255), True,
                   center=True)
        elif d.done:
            T.text(surf, f"{r['d20']} {r['bonus']:+d} = {r['total']}", (cx, cy + 200), 26, T.TEXT, True, center=True)
            T.text(surf, name, (cx, cy + 240), 34, col, True, center=True, shadow=True)
            if self.landed_t > 0.35:
                T.text(surf, "клик — дальше", (cx, cy + 278), 14, T.TEXT_DIM, center=True)

def event_next(app, eid, nxt, fight, gift):
    """После исхода события: сперва дар (выбор героя), потом бой, следующий шаг или карта."""
    run = app.exp
    if gift:
        def then():
            run.stage = {"node": run.node, "kind": "event", "event": eid, "step": nxt, "battle": fight}
            save(app)
            event_next(app, eid, nxt, fight, None)
        app.switch(RewardScene(app, None, [{"type": "gift", "id": g} for g in gift], then=then, title="Дар"))
        return
    if fight:
        run.battle_from_event(fight)
        save(app)
        battle(app)
    elif nxt:
        app.switch(EventScene(app, eid, nxt))
    else:
        to_map(app)


# ---------- награда ----------

class RewardScene(XScene):
    """Награда на выбор. Дар: сначала карточка дара, потом герой, который его получит (подходящие подсвечены).
    then — куда дальше (по умолчанию — обычный путь после боя); так же выбирается дар из события."""

    def __init__(self, app, summary, offers, bonus=None, then=None, title=None):
        super().__init__(app)
        self.summary = summary or {}
        self.offers = offers
        self.bonus = bonus
        self.then = then
        self.title = title
        self.gift = None                 # индекс выбранного дара — ждём героя

    def act(self, action, button=1):
        if action[0] == "pick":
            o = self.offers[action[1]]
            if o["type"] == "gift":               # дар: сначала подробно — описание, демонстрация, цифры
                self.app.switch(GiftDetailScene(self.app, self, action[1]))
                return
            self.run.apply_offer(o)
            self._done()
        elif action == "skip":
            self._done()
        elif action == "stats":
            self.app.switch(StatsScene(self.app, self.summary["stats"], back=lambda: self.app.switch(self)))
        elif action[0] == "hero":
            if self.gift is not None:
                self._give(action[1])
            else:
                self.app.switch(HeroScene(self.app, action[1], back=lambda: self.app.switch(self)))

    def take_gift(self, offer_i, hero_i):
        """Из окна подробностей: дар offer_i — герою hero_i."""
        self.gift = offer_i
        self._give(hero_i)

    def _give(self, i):
        o, h = self.offers[self.gift], self.run.heroes[i]
        if self.run.apply_offer(o, h):
            self._done()
        else:
            self.say("Этому герою дар не подходит")

    def party_highlight(self, hero):
        return self.gift is not None and self.run.gift_ok(hero, self.offers[self.gift]["id"])

    def party_tip(self, hero):
        if self.gift is None:
            return [hero.name, "Клик — лист героя: навыки, снаряжение"]
        g = self.xd["gifts"][self.offers[self.gift]["id"]]
        ok = self.run.gift_ok(hero, self.offers[self.gift]["id"])
        return [(f"{hero.name}: {g['name']}", BLESS if ok else CURSE),
                "Клик — отдать дар" if ok else "Дар не подходит этому герою"]

    def _done(self):
        if self.then:
            self.then()
            return
        self.run.stage = None
        after_reward(self.app, self.summary)

    def key(self, k):
        if k == pygame.K_TAB and self.summary.get("stats"):
            self.act("stats")
            return
        if self.gift is not None:
            if pygame.K_1 <= k <= pygame.K_4 and k - pygame.K_1 < len(self.run.heroes):
                self._give(k - pygame.K_1)
            elif k == pygame.K_ESCAPE:
                self.gift = None
            return
        if pygame.K_1 <= k <= pygame.K_3 and k - pygame.K_1 < len(self.offers):
            self.act(("pick", k - pygame.K_1))
        elif k == pygame.K_ESCAPE:
            self._done()

    def _offer_card(self, o):
        xd = self.xd
        if o["type"] == "item":
            it = o["item"]
            rar = xd["items"]["rarities"][it["rarity"]]["name"]
            lines = [(f"{xd['items']['slots'][it['slot']]} · {rar} · тир {it['tier']}", T.TEXT_DIM)]
            lines += [(s, T.TEXT) for s in X.item_lines(xd, it)]
            return X.item_name(it), lines, rarity_color(xd, it)
        if o["type"] == "gift":
            g = xd["gifts"][o["id"]]
            data = self.run.data
            who = [h.name for h in self.run.heroes if self.run.gift_ok(h, o["id"])]
            if g.get("any"):
                req = "любой герой"
            else:
                req = ", ".join([data.classes[c]["name"] for c in g.get("classes", []) if c in data.classes]
                                + [{"melee": "ближний бой", "ranged": "дальний бой", "caster": "маги",
                                    "support": "поддержка"}.get(r, r) for r in g.get("roles", [])])
            return g["name"], [(g["desc"], T.TEXT), (f"Для: {req}", T.TEXT_DIM),
                               ("Подходит: " + (", ".join(who) or "никому"), BLESS),
                               ("Личный дар — до конца похода", GLORY),
                               ("Клик — подробно и демонстрация", T.TEXT_DIM)], BLESS
        if o["type"] == "gold":
            return f"{o['amount']} золота", [("Торговцы и меняла будут рады", T.TEXT_DIM)], GOLD
        if o["type"] == "heal":
            return "Перевязка", [(f"Отряд лечится на {o['pct'] * 100:.0f}%", T.TEXT)], (90, 220, 120)
        return "Урок мастерства", [(f"+{o['amount']} выбор улучшения навыков каждому герою", T.TEXT)], SP

    def draw(self, surf):
        s = self.summary
        self.hits = []
        surf.fill(T.BG)
        kind = s.get("kind", "battle")
        title = self.title or {"boss": "Босс повержен!", "elite": "Элита разбита"}.get(kind, "Победа")
        self.header(surf, title)
        y = 58
        parts = [f"золото +{s.get('gold', 0)}", f"опыт +{s.get('xp', 0)}"] if s.get("xp") else []
        if s.get("ups"):
            parts.append("новый уровень: " + ", ".join(s["ups"]))
        T.text(surf, " · ".join(parts), (26, y), 16, T.TEXT)
        y += 22
        if s.get("fallen"):
            T.text(surf, "Ранены до лагеря: " + ", ".join(s["fallen"]), (26, y), 15, CURSE)
            y += 20
        for line in s.get("extra", []):
            if isinstance(line, str):
                T.text(surf, "• " + line, (26, y), 15, BLESS)
                y += 20
        if s.get("learned"):                          # ранги от применения навыков
            T.text(surf, "Навыки окрепли: " + "; ".join(s["learned"]), (26, y), 15, GOLD)
            y += 20
        if self.bonus:
            T.text(surf, f"Трофей в сумку: {X.item_name(self.bonus)}", (26, y), 16, rarity_color(self.xd, self.bonus),
                   True)
            self.hit(pygame.Rect(26, y, 500, 20), None, self.item_tip(self.bonus))
            y += 22
        if self.gift is not None:
            g = self.xd["gifts"][self.offers[self.gift]["id"]]
            msg = f"Кому достанется «{g['name']}»? Клик по герою внизу (1–4) · Esc — другой дар"
        else:
            gifts = self.offers and all(o["type"] == "gift" for o in self.offers)
            msg = ("Выберите дар — клик по карточке: подробности и демонстрация" if gifts else
                   "Выберите награду (1–3):") if self.offers else ""
        T.text(surf, msg, (T.SCREEN_W // 2, 170), 20, GLORY, True, center=True)
        n = len(self.offers)
        cw, gap = 300, 24
        x0 = (T.SCREEN_W - (n * cw + (n - 1) * gap)) // 2
        for i, o in enumerate(self.offers):
            r = pygame.Rect(x0 + i * (cw + gap), 196, cw, 300)
            title_, lines, accent = self._offer_card(o)
            W.card(surf, r, title_, lines, self.mouse, accent, self.gift is None or self.gift == i)
            ic = item_icon(o["item"], 48) if o["type"] == "item" else icon(f"gift_{o['id']}", 48) \
                if o["type"] == "gift" else None
            if ic:
                surf.blit(ic, (r.right - 58, r.bottom - 58))
            if self.gift == i:
                pygame.draw.rect(surf, GOLD, r, 3, border_radius=10)
            T.text(surf, str(i + 1), (r.centerx, r.bottom + 14), 15, T.TEXT_DIM, center=True)
            self.hit(r, ("pick", i))
        self.button(surf, pygame.Rect(T.SCREEN_W // 2 - 110, 528, 220, 40), "Пропустить (Esc)", "skip")
        stats_strip(self, surf, s.get("stats"))
        self.draw_party(surf, T.SCREEN_H - 200, h=150)
        self.draw_tip(surf)


def stats_strip(scene, surf, st):
    """Коротко о бое на экране наград: время, кто больше всех нанёс; кнопка — подробная статистика (Tab)."""
    if not st:
        return
    best = max(st["rows"], key=lambda r: r["dealt"], default=None)
    msg = f"Бой {st['time']:.0f} с · убито {st['killed']} из {st['foes']}"
    if best and best["dealt"]:
        msg += f" · больше всех урона: {best['name']} ({best['dealt']})"
    T.text(surf, msg, (T.SCREEN_W - 26 - T.font(14).size(msg)[0], 60), 14, T.TEXT_DIM)
    scene.button(surf, pygame.Rect(T.SCREEN_W - 236, 84, 210, 34), "Статистика боя (Tab)", "stats", True, SP,
                 "Урон, полученный урон, лечение, убийства и навыки каждого героя")


def gift_rule_lines(xd, g):
    """Строки «что делает» дара: статы, особые свойства, срабатывания — для окна подробностей."""
    names = {"hp": "здоровья", "atk_damage": "урона атак", "power": "силы навыков", "armor": "брони",
             "lifesteal": "вампиризма", "ap_max": "AP", "atk_range": "дальности атак"}
    out = []
    for m in g.get("mods", []):
        if "stat" in m and m["stat"] in names:
            if "mult" in m:
                out.append(f"{(m['mult'] - 1) * 100:+.0f}% {names[m['stat']]}")
            elif "add" in m:
                v = m["add"] * 100 if m["stat"] == "lifesteal" else m["add"]
                out.append(f"{v:+g}{'%' if m['stat'] == 'lifesteal' else ''} {names[m['stat']]}")
        elif m.get("stat") == "atk_cooldown":
            out.append(f"атаки быстрее на {(1 - m['mult']) * 100:.0f}%")
        elif m.get("stat") == "ap_regen":
            out.append(f"AP быстрее на {(1 - m['mult']) * 100:.0f}%")
        elif "attack_tag" in m:
            out.append(f"атаки — стихия «{xd.get('tag_names', {}).get(m['attack_tag'], m['attack_tag'])}»")
        elif "skill" in m:
            if "cooldown_mult" in m:
                out.append(f"перезарядка навыков −{(1 - m['cooldown_mult']) * 100:.0f}%")
            if "amount_mult" in m:
                out.append(f"сила лечения и щитов навыков +{(m['amount_mult'] - 1) * 100:.0f}%")
            if "radius_add" in m:
                out.append(f"области навыков +{m['radius_add']} клетка")
        elif "passive" in m:
            out.append(f"пассивка класса: {m['passive']} {m['add']:+g}")
    for k, v in g.get("extra", {}).items():
        out.append({"crit": f"+{v * 100:.0f}% шанса крита", "dodge": f"+{v * 100:.0f}% уклонения",
                    "crit_mult": f"+{v * 100:.0f}% силы крита"}.get(k, f"{k} +{v}"))
    for tg, k in g.get("dmg_vs", {}).items():
        out.append(f"+{(k - 1) * 100:.0f}% урона по {dict(wet='мокрым', burning='горящим', cold='замёрзшим').get(tg, tg)}")
    if g.get("reaction_mult"):
        out.append(f"+{(g['reaction_mult'] - 1) * 100:.0f}% урона реакций")
    if g.get("rules"):
        out.append("срабатывание: " + g["desc"])
    return out


class GiftDetailScene(XScene):
    """Дар крупно: полное описание, для кого, демонстрация (герой с даром на манекенах) и цифры героя до и после,
    урон за 10 сек без дара и с ним. Enter — взять (выбранному герою), Esc — назад к выбору."""

    stage = False                 # окно боя превью рисует видеокарта, как лист героя
    PREVIEW = None

    def __init__(self, app, reward, offer_i):
        super().__init__(app)
        from ui.gift_preview import GiftPreview
        self.reward, self.offer_i = reward, offer_i
        self.gid = reward.offers[offer_i]["id"]
        self.g = self.xd["gifts"][self.gid]
        self.fit = [i for i, h in enumerate(self.run.heroes) if self.run.gift_ok(h, self.gid)]
        self.hero_i = self.fit[0] if self.fit else 0
        self.preview = GiftPreview(self.run.data, self._prect(), zoom=64)
        self.cache = {}
        self._show()

    def _prect(self):
        return pygame.Rect(T.SCREEN_W - 24 - 700, 96, 700, 420)

    def relayout(self):
        if hasattr(self, "preview"):
            self.preview.rect = self._prect()

    def _protos(self, i):
        """Прототип героя без дара и с даром, замер за 10 сек — один раз на героя."""
        if i not in self.cache:
            from ui.gift_preview import measure
            run = self.run
            h = run.heroes[i]
            with_g = X.Hero(h.to_dict())
            with_g.gifts = list(h.gifts) + [self.gid]
            p0, p1 = run.proto(h), run.proto(with_g)
            self.cache[i] = (p0, p1, measure(run.data, h.cls, p0), measure(run.data, h.cls, p1))
        return self.cache[i]

    def _show(self):
        h = self.run.heroes[self.hero_i]
        _, p1, _, _ = self._protos(self.hero_i)
        self.preview.show_hero(h.cls, p1, f"{h.name} с даром")

    def act(self, action, button=1):
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "hero":
            if action[1] in self.fit:
                self.hero_i = action[1]
                self._show()
        elif kind == "take":
            self.app.switch(self.reward)
            self.reward.take_gift(self.offer_i, self.hero_i)
        elif kind == "back":
            self.app.switch(self.reward)

    def key(self, k):
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE) and self.fit:
            self.act("take")
        elif k == pygame.K_ESCAPE:
            self.act("back")
        elif pygame.K_1 <= k <= pygame.K_4:
            self.act(("hero", k - pygame.K_1))

    def update(self, dt):
        super().update(dt)
        self.preview.update(dt)

    @property
    def vfx(self):
        return self.preview.vfx

    def plane(self):
        return self.preview.plane()

    def gpu_particles(self):
        return self.preview.gpu_particles()

    def draw_layers(self, world, ui, units):
        world.fill(T.BG)
        units.fill((0, 0, 0, 0))
        self._draw_panel(ui)
        ui.fill((0, 0, 0, 0), self.preview.rect)
        self.preview.draw_layers(world, units, ui)
        self._draw_frame(ui)

    def draw(self, surf):
        self.preview.draw_cpu(surf)
        layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        self._draw_panel(layer)
        layer.fill((0, 0, 0, 0), self.preview.rect)
        surf.blit(layer, (0, 0))
        self.preview._draw_overlay(surf)
        self._draw_frame(surf)

    def _draw_frame(self, surf):
        r = self.preview.rect
        pygame.draw.rect(surf, BLESS, r.inflate(4, 4), 2, border_radius=6)
        h = self.run.heroes[self.hero_i]
        T.text(surf, f"Демонстрация: {h.name} с даром бьёт манекенов", (r.x + 10, r.y + 8), 14, T.TEXT, True,
               shadow=True)

    def _draw_panel(self, surf):
        run, g = self.run, self.g
        self.hits = []
        surf.fill(T.BG)
        left = pygame.Rect(24, 24, T.SCREEN_W - 24 - 700 - 24 - 24, T.SCREEN_H - 110)
        T.frame(surf, left, 245, accent=BLESS, corner=BLESS)
        ic = icon(f"gift_{self.gid}", 64)
        x, y = left.x + 16, left.y + 14
        if ic:
            surf.blit(ic, (x, y))
        tx = x + (76 if ic else 0)
        T.text(surf, g["name"], (tx, y + 2), 26, BLESS, True)
        who = "любой герой" if g.get("any") else ", ".join(
            [run.data.classes[c]["name"] for c in g.get("classes", []) if c in run.data.classes] +
            [{"melee": "ближний бой", "ranged": "дальний бой", "caster": "маги", "support": "поддержка"}.get(r, r)
             for r in g.get("roles", [])])
        T.text(surf, f"Для: {who}" + ("  ·  меняет игру" if g.get("keystone") else ""), (tx, y + 36), 14,
               GLORY if g.get("keystone") else T.TEXT_DIM, True)
        y += 80
        for ln in T.wrap(g["desc"], 16, left.w - 32):
            T.text(surf, ln, (x, y), 16, T.TEXT)
            y += 21
        y += 4
        for ln in gift_rule_lines(self.xd, g):
            for k, part in enumerate(T.wrap("• " + ln, 14, left.w - 32)):
                T.text(surf, part, (x, y), 14, T.TEXT_DIM)
                y += 18
        y += 10
        T.text(surf, "Кому:", (x, y + 6), 15, T.TEXT_DIM, True)
        bx = x + 60
        for i, h in enumerate(run.heroes):
            ok = i in self.fit
            w = T.font(15, True).size(h.name)[0] + 24
            r = pygame.Rect(bx, y, w, 32)
            tn = tint_of(run.data, h.cls)
            on = i == self.hero_i
            pygame.draw.rect(surf, tn["hot"] if on else tn["fill"], r, border_radius=7)
            pygame.draw.rect(surf, tn["accent"] if on else (tn["dim"] if ok else T.PANEL_EDGE), r, 2 if on else 1,
                             border_radius=7)
            T.text(surf, h.name, (r.x + 12, r.y + 7), 15, T.TEXT if ok else T.TEXT_DIM, True)
            self.hit(r, ("hero", i) if ok else None, [h.name, "Подходит" if ok else "Этому герою дар не подходит"])
            bx += w + 8
        y += 46
        p0, p1, m0, m1 = self._protos(self.hero_i)
        rows = [("Здоровье", p0["hp"], p1["hp"], "{:.0f}"),
                ("Урон атаки", p0["attack"]["damage"], p1["attack"]["damage"], "{:.0f}"),
                ("Атак в секунду", 1 / max(0.05, p0["attack"]["cooldown"]), 1 / max(0.05, p1["attack"]["cooldown"]),
                 "{:.2f}"),
                ("Сила навыков", p0.get("power", 1.0) * 100, p1.get("power", 1.0) * 100, "{:.0f}%"),
                ("Броня", p0.get("armor", 0), p1.get("armor", 0), "{:.1f}"),
                ("Крит", p0.get("crit", 0) * 100, p1.get("crit", 0) * 100, "{:.0f}%"),
                ("Уклонение", p0.get("dodge", 0) * 100, p1.get("dodge", 0) * 100, "{:.0f}%"),
                ("Вампиризм", p0.get("lifesteal", 0) * 100, p1.get("lifesteal", 0) * 100, "{:.0f}%")]
        T.text(surf, "Было → станет", (x, y), 15, T.TEXT_DIM, True)
        y += 22
        for name, a, b, fmt in rows:
            if abs(a - b) < 1e-6 and name not in ("Здоровье", "Урон атаки"):
                continue
            col = BLESS if b > a + 1e-6 else (CURSE if b < a - 1e-6 else T.TEXT)
            T.text(surf, name, (x, y), 15, T.TEXT)
            T.text(surf, f"{fmt.format(a)}  →  {fmt.format(b)}", (x + 170, y), 15, col, True)
            y += 20
        # замер на манекенах
        r = self.preview.rect
        y2 = r.bottom + 14
        T.text(surf, "За 10 сек боя с манекенами: без дара → с даром", (r.x, y2), 15, T.TEXT_DIM, True)
        y2 += 24
        for key, name, good in (("dealt", "Урон", True), ("taken", "Получено урона", False), ("healed", "Лечение", True),
                                ("absorbed", "Поглощено щитом", True)):
            a, b = m0[key], m1[key]
            if not a and not b:
                continue
            pct = f" ({(b - a) / a * 100:+.0f}%)" if a else ""
            better = (b > a) == good
            col = T.TEXT if a == b else (BLESS if better else CURSE)
            T.text(surf, f"{name}: {a} → {b}{pct}", (r.x, y2), 16, col, True)
            y2 += 22
        self.button(surf, pygame.Rect(T.SCREEN_W - 24 - 260, T.SCREEN_H - 64, 260, 46), "Взять дар (Enter)", "take",
                    bool(self.fit), BLESS)
        self.button(surf, pygame.Rect(T.SCREEN_W - 24 - 260 - 270, T.SCREEN_H - 64, 250, 46), "Другой дар (Esc)",
                    "back", True, (170, 160, 210))
        self.draw_tip(surf)


class StatsScene(XScene):
    """Статистика боя: по героям (и гостям) — урон, получено, поглощено щитом, лечение, убийства, навыки."""

    BARS = [("dealt", "Урон", (255, 140, 90)), ("taken", "Получено", (230, 90, 90)),
            ("absorbed", "Щитом", (150, 200, 255)), ("healed", "Лечение", (110, 220, 130))]

    def __init__(self, app, stats, back):
        super().__init__(app)
        self.stats, self.back = stats, back

    def act(self, action, button=1):
        if action == "back":
            self.back()

    def key(self, k):
        if k in (pygame.K_ESCAPE, pygame.K_TAB, pygame.K_RETURN, pygame.K_SPACE):
            self.back()

    def draw(self, surf):
        st = self.stats
        self.hits = []
        surf.fill(T.BG)
        res = {"victory": "Победа", "defeat": "Поражение"}.get(st.get("result"), "Бой")
        self.header(surf, f"Статистика боя — {res}",
                    f"{st['time']:.1f} с · убито врагов {st['killed']} из {st['foes']}")
        rows = st["rows"]
        top = {k: max([r[k] for r in rows] + [1]) for k, _, _ in self.BARS}
        mvp = max(rows, key=lambda r: r["dealt"] + r["healed"] * 0.8 + r["kills"] * 30, default=None)
        h = min(150, (T.SCREEN_H - 170) // max(1, len(rows)) - 10)
        y = 96
        data = self.run.data if self.run else self.app.profile.data
        for r in rows:
            box = pygame.Rect(24, y, T.SCREEN_W - 48, h)
            cls = r["cls"]
            tn = tint_of(data, cls) if cls in data.classes else {"accent": T.AMBER, "fill": T.PANEL}
            T.frame(surf, box, 235, accent=tn["accent"], corner=tn["accent"], fill=tn["fill"])
            if cls in data.classes:
                img = hero_sprite(data, cls, 1.2)
            else:
                e = data.enemies.get(cls, {})
                img = _SPRITES.get([cls, e.get("sprite_fallback")], e.get("role", "melee"),
                                   tuple(e.get("color", (200, 200, 200))))
            if not r["alive"]:
                img = pygame.transform.grayscale(img)
            surf.blit(img, (box.x + 14, box.y + h // 2 - img.get_height() // 2))
            T.text(surf, r["name"] + (" (гость)" if r["guest"] else ""), (box.x + 110, box.y + 10), 20,
                   tn["accent"], True)
            T.text(surf, ("жив" if r["alive"] else "пал") + f" · HP {max(0, r['hp'])}/{r['max_hp']}"
                   + f" · убийств {r['kills']}", (box.x + 110, box.y + 36), 14, T.TEXT_DIM if r["alive"] else CURSE)
            if r is mvp and len(rows) > 1:
                T.text(surf, "лучший в бою", (box.right - 130, box.y + 10), 15, GOLD, True)
            bx, by = box.x + 110, box.y + 60
            bw = (box.w - 130 - 3 * 16) // 4
            for i, (key, label, col) in enumerate(self.BARS):
                rr = pygame.Rect(bx + i * (bw + 16), by + 18, bw, 12)
                T.text(surf, f"{label}: {r[key]}", (rr.x, by), 14, col, True)
                pygame.draw.rect(surf, (20, 16, 12), rr, border_radius=4)
                fill = rr.copy()
                fill.w = int(rr.w * r[key] / top[key])
                pygame.draw.rect(surf, col, fill, border_radius=4)
            uses = [f"{r['skill_names'].get(sid, sid)} ×{n}" for sid, n in list(r["uses"].items())[:5]]
            if uses and h > 100:
                T.text(surf, fit("Навыки: " + ", ".join(uses), 14, box.w - 130), (bx, by + 42), 14, T.TEXT)
            y += h + 10
        self.button(surf, pygame.Rect(T.SCREEN_W // 2 - 110, T.SCREEN_H - 56, 220, 42), "Назад (Esc)", "back")
        self.draw_tip(surf)


class PickScene(XScene):
    """Карты улучшения на ключевом уровне: две карты (ветки навыков, мастерство, новый навык). Клик по карте —
    выбрать и посмотреть демонстрацию навыка (как будет после улучшения; «Сейчас / Станет» — сравнить) и цифры
    «было → станет»; повторный клик, «Взять» или Enter — взять. Сразу после боя — по очереди всем героям с выбором;
    с карточки героя — только ему. «Позже» — выбор остаётся на карточке героя. Библиотека таверны — перебросы."""

    stage = False                 # окно демонстрации рисует видеокарта, как в листе героя

    def __init__(self, app, then, summary=None, only=None):
        super().__init__(app)
        from ui.skill_preview import SkillPreview
        self.then = then
        self.summary = summary
        self.only = only
        self.sel = 0
        self.after = True         # демонстрация: «станет» (True) или «сейчас»
        self.shown = None
        self.preview = SkillPreview(self.run.data, self._prect(), zoom=62)

    def _prect(self):
        return pygame.Rect(T.SCREEN_W - 24 - 640, 92, 640, 330)

    def relayout(self):
        if hasattr(self, "preview"):
            self.preview.rect = self._prect()

    @property
    def hero(self):
        hs = [self.only] if self.only else self.run.heroes
        return next((h for h in hs if h.sp > 0), None)

    def _card(self):
        h = self.hero
        cards = self.run.pick_cards(h) if h else []
        if not cards:
            return None, None
        self.sel = min(self.sel, len(cards) - 1)
        return h, cards[self.sel]

    def _protos(self, h, card):
        run = self.run
        return run.proto(h, party=False), run.proto(run.card_hero(h, card), party=False)

    def _sync(self):
        """Демонстрация — под выбранную карту (навык после улучшения или как сейчас)."""
        h, card = self._card()
        if h is None:
            return
        key = (h.uid, h.level, h.sp, self.sel, self.after, repr(card))
        if key == self.shown:
            return
        self.shown = key
        sid = card.get("skill") or next((s for s in h.skills), None)
        p0, p1 = self._protos(h, card)
        proto = p1 if (self.after or card["type"] == "learn") else p0
        if sid in proto["skill_defs"]:
            self.preview.show_proto(h.cls, proto, sid, self.run.data.skills[sid]["name"])

    def _take(self):
        h, card = self._card()
        if h is None:
            return
        self.run.take_card(h, self.sel)
        self.sel, self.after, self.shown = 0, True, None
        save(self.app)
        if self.hero is None:
            self.then()

    def act(self, action, button=1):
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "card":
            if self.sel == action[1]:
                self._take()               # повторный клик по выбранной — взять
            else:
                self.sel, self.after = action[1], True
        elif kind == "take":
            self._take()
        elif kind == "view":
            self.after = action[1]
        elif kind == "reroll":
            h = self.hero
            if h and self.run.reroll_cards(h):
                self.sel, self.shown = 0, None
                save(self.app)
            else:
                self.say("Перебросов нет — их даёт библиотека таверны")
        elif kind == "later":
            save(self.app)
            self.then()
        elif kind == "stats" and self.summary and self.summary.get("stats"):
            self.app.switch(StatsScene(self.app, self.summary["stats"], back=lambda: self.app.switch(self)))

    def key(self, k):
        h = self.hero
        if k == pygame.K_TAB:
            self.act("stats")
        elif h and pygame.K_1 <= k <= pygame.K_2:
            self.sel, self.after = k - pygame.K_1, True
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._take()
        elif k == pygame.K_v:
            self.after = not self.after
        elif k == pygame.K_r:
            self.act("reroll")
        elif k == pygame.K_ESCAPE:
            self.act("later")

    def party_highlight(self, hero):
        return hero is self.hero

    # ---------- демонстрация (как в листе героя: окно-дырка в интерфейсе) ----------

    def update(self, dt):
        super().update(dt)
        if self.hero is None:
            return
        self._sync()
        self.preview.update(dt)

    @property
    def vfx(self):
        return self.preview.vfx

    def plane(self):
        return self.preview.plane() if self.preview.proto else None

    def gpu_particles(self):
        return self.preview.gpu_particles()

    def draw_layers(self, world, ui, units):
        world.fill(T.BG)
        units.fill((0, 0, 0, 0))
        self._draw_panel(ui)
        if self.hero is not None and self.preview.proto:
            ui.fill((0, 0, 0, 0), self.preview.rect)
            self.preview.draw_layers(world, units, ui)
            self._draw_frame(ui)

    def draw(self, surf):
        if self.hero is not None and self.preview.proto:
            self.preview.draw_cpu(surf)
            layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            self._draw_panel(layer)
            layer.fill((0, 0, 0, 0), self.preview.rect)
            surf.blit(layer, (0, 0))
            self.preview._draw_overlay(surf)
            self._draw_frame(surf)
        else:
            self._draw_panel(surf)

    def _draw_frame(self, surf):
        r = self.preview.rect
        h, card = self._card()
        pygame.draw.rect(surf, GOLD, r.inflate(4, 4), 2, border_radius=6)
        if card:
            sid = card.get("skill")
            name = self.run.data.skills[sid]["name"] if sid else ""
            when = "станет" if (self.after or card["type"] == "learn") else "сейчас"
            T.text(surf, f"Демонстрация: {name} — {when}", (r.x + 10, r.y + 8), 14, T.TEXT, True, shadow=True)

    def _draw_panel(self, surf):
        run, h = self.run, self.hero
        self.hits = []
        surf.fill(T.BG)
        if h is None:
            self.then()
            return
        s = self.summary or {}
        title = {"boss": "Босс повержен!", "elite": "Элита разбита"}.get(s.get("kind"), "Победа") if s else \
            "Улучшение навыков"
        self.header(surf, title)
        if s.get("xp"):
            parts = [f"золото +{s.get('gold', 0)}", f"опыт +{s.get('xp', 0)}"]
            if s.get("ups"):
                parts.append("новый уровень: " + ", ".join(s["ups"]))
            T.text(surf, " · ".join(parts), (26, 58), 15, T.TEXT)
        tn = tint_of(run.data, h.cls)
        img = hero_sprite(run.data, h.cls, 1.1)
        surf.blit(img, (24, 84))
        T.text(surf, h.name, (24 + img.get_width() + 12, 88), 24, tn["accent"], True)
        T.text(surf, f"{run.data.classes[h.cls]['name']} · ур. {h.level} — выберите улучшение"
               + (f" (ещё {h.sp - 1})" if h.sp > 1 else ""), (24 + img.get_width() + 12, 118), 15, T.TEXT)
        cards = run.pick_cards(h)
        left_w = T.SCREEN_W - 24 - 640 - 24 - 24
        y = 160
        for i, c in enumerate(cards):
            r = pygame.Rect(24, y, left_w, 150)
            head, lines = run.card_text(h, c)
            accent = {"branch": (255, 150, 90), "rank": GOLD, "learn": SP}.get(c["type"], BLESS)
            kind = {"branch": "Ветка навыка", "rank": "Мастерство", "learn": "Новый навык"}.get(c["type"], "Закалка")
            on = i == self.sel
            T.frame(surf, r, 240, accent=accent if on else T.mix(accent, (0, 0, 0), 0.5), corner=accent,
                    fill=T.mix(T.PANEL, accent, 0.16 if on else 0.04))
            T.text(surf, f"{i + 1}. {kind}", (r.x + 14, r.y + 8), 13, accent, True)
            T.text(surf, fit(head, 18, r.w - 28), (r.x + 14, r.y + 26), 18, T.TEXT, True)
            yy = r.y + 52
            for k, ln in enumerate(lines):
                col = T.TEXT_DIM if k == 0 or ln.startswith("Сейчас:") else (BLESS if ln.startswith("Станет:") else T.TEXT)
                for part in T.wrap(ln, 13, r.w - 28)[:2]:
                    if yy > r.bottom - 18:
                        break
                    T.text(surf, part, (r.x + 14, yy), 13, col)
                    yy += 16
            if on:
                T.text(surf, "выбрано — клик ещё раз: взять", (r.right - 210, r.y + 8), 12, accent, True)
            self.hit(r, ("card", i), [head, "Клик — показать; ещё клик — взять"])
            y += 160
        # переключатель и цифры под демонстрацией
        pr = self._prect()
        h_, card = self._card()
        if card:
            bx = pr.x
            for on, label in ((False, "Сейчас (V)"), (True, "Станет (V)")):
                b = pygame.Rect(bx, pr.bottom + 10, 150, 30)
                ok = not (card["type"] == "learn" and not on)
                W.button(surf, b, ("» " if self.after == on else "") + label, self.mouse, ok,
                         GOLD if self.after == on else (120, 110, 100))
                self.hit(b, ("view", on) if ok else None)
                bx += 158
            p0, p1 = self._protos(h, card)
            rows = []
            sid = card.get("skill")
            if sid and sid not in p1["skill_defs"]:
                sid = None
            if sid:
                sk0 = p0["skill_defs"].get(sid)
                sk1 = p1["skill_defs"][sid]
                v0 = {w: v for w, v, _ in stats.skill_values(p0, sk0)} if sk0 else {}
                v1 = {w: v for w, v, _ in stats.skill_values(p1, sk1)}
                for w in v1:
                    rows.append((w.capitalize(), v0.get(w, 0), v1[w], "{:.0f}"))
                rows.append(("Перезарядка, с", sk0["cooldown"] if sk0 else 0, sk1["cooldown"], "{:.1f}"))
                rows.append(("AP", sk0["ap"] if sk0 else 0, sk1["ap"], "{:.0f}"))
            else:
                rows += [("Здоровье", p0["hp"], p1["hp"], "{:.0f}"),
                         ("Урон атаки", p0["attack"]["damage"], p1["attack"]["damage"], "{:.0f}"),
                         ("Сила навыков", p0.get("power", 1) * 100, p1.get("power", 1) * 100, "{:.0f}%")]
            yy = pr.bottom + 50
            for name, a, b, fmt in rows:
                lower_better = name.startswith("Перезарядка") or name == "AP"
                col = T.TEXT if abs(a - b) < 1e-6 else (BLESS if (b < a) == lower_better else CURSE)
                T.text(surf, name, (pr.x, yy), 15, T.TEXT)
                T.text(surf, f"{fmt.format(a)}  →  {fmt.format(b)}", (pr.x + 170, yy), 15, col, True)
                yy += 20
            if sid:                                  # описание — того вида, что сейчас в демонстрации
                proto = p1 if (self.after or card["type"] == "learn") else p0
                desc = proto["skill_defs"].get(sid, {}).get("desc") or ""
                for k, part in enumerate(T.wrap(desc, 13, pr.w - 340)[:5]):
                    T.text(surf, part, (pr.x + 330, pr.bottom + 50 + 18 * k), 13, T.TEXT_DIM)
        by = T.SCREEN_H - 248
        self.button(surf, pygame.Rect(24, by, 200, 40), "Взять (Enter)", "take", bool(card), GOLD)
        left = run.rerolls_left()
        self.button(surf, pygame.Rect(234, by, 200, 40), f"Перебросить (R) · {max(0, left)}", "reroll", left > 0,
                    (150, 200, 255), "Перебросы карт даёт библиотека таверны")
        self.button(surf, pygame.Rect(444, by, 150, 40), "Позже (Esc)", "later", True, (170, 160, 210),
                    "Выбор останется на карточке героя")
        st = s.get("stats")
        if st:
            self.button(surf, pygame.Rect(604, by, 170, 40), "Статистика (Tab)", "stats", True, SP)
        self.draw_party(surf, T.SCREEN_H - 196, h=150)
        self.draw_tip(surf)
        self.draw_toast(surf, T.SCREEN_H - 214)


# ---------- лагерь ----------

class CampScene(XScene):
    def act(self, action, button=1):
        run = self.run
        if action == "rest":
            run.camp_rest()
            to_map(self.app)
        elif action == "train":
            run.camp_train()
            to_map(self.app)
        elif action == "cool":
            run.camp_cool()
            to_map(self.app)
        elif action == "neural":                   # режим обучения: фоновые бои без графики
            from game.learn_mode import TrainScene
            self.app.switch(TrainScene(self.app, back=lambda: to_map(self.app), battles=20))
        elif action[0] == "hero":
            self.app.switch(HeroScene(self.app, action[1], back=lambda: self.app.switch(CampScene(self.app)),
                                      respec=True))

    def key(self, k):
        if k == pygame.K_1:
            self.act("rest")
        elif k == pygame.K_2:
            self.act("train")
        elif k == pygame.K_3 and self.run.heat_on():
            self.act("cool")
        elif k == pygame.K_4 and getattr(self.app, "neural", None) is not None:
            self.act("neural")

    def draw(self, surf):
        run = self.run
        self.hits = []
        surf.fill((14, 18, 14))
        self.backdrop(surf, "camp", "act", dim=70)
        band = pygame.Surface((T.SCREEN_W, 80), pygame.SRCALPHA)
        band.fill((8, 8, 10, 170))
        surf.blit(band, (0, 0))
        for r, i in scene_party(surf, run, mouse=self.mouse):
            self.hit(r, ("hero", i), [run.heroes[i].name, "Клик — лист героя (в лагере — сброс навыков)"])
        self.header(surf, "Лагерь", "Костёр и пара часов покоя. Выберите одно. В листе героя здесь можно "
                                    "сбросить очки навыков.")
        wounded = [h.name for h in run.heroes if h.wounded]
        opts = [("rest", "Отдых", [(f"Отряд лечится на {run.cfg['camp_heal'] * 100:.0f}%", T.TEXT),
                                  ("Раны заживают" + (": " + ", ".join(wounded) if wounded else ""), BLESS)],
                 (90, 220, 120)),
                ("train", "Тренировка", [("+1 выбор улучшения навыков каждому", SP), ("+половина уровня опыта", W.XP)], SP)]
        if run.heat_on():
            opts.append(("cool", "Остудить кузню", [(f"Жар −{run.heat_cfg().get('camp_cool', 30)}", HEAT),
                                                   (f"сейчас {run.heat}", T.TEXT_DIM),
                                                   ("Залить водой ближние горны: извержение откладывается", T.TEXT)],
                         HEAT))
        if getattr(self.app, "neural", None) is not None:
            opts.append(("neural", "Тренировка сети", [("20 быстрых боёв без графики", (150, 200, 255)),
                                                     ("сети героев и врагов учатся", T.TEXT),
                                                     ("лагерь при этом тратится", T.TEXT_DIM)], (150, 200, 255)))
        x0 = T.SCREEN_W - len(opts) * 290 - 40
        for i, (key, title, lines, accent) in enumerate(opts):
            r = pygame.Rect(x0 + i * 290, 110, 270, 170)
            W.card(surf, r, f"{i + 1}. {title}", lines, self.mouse, accent)
            self.hit(r, key)
        self.draw_tip(surf)


# ---------- наковальня (глава с ковкой) ----------

def draw_mats(scene, surf, run, x, y, right=False):
    """Руда и металлы отряда: значок и число (с подсказкой)."""
    items = list(run.xd["mats"].items())
    w = 78
    x0 = x - len(items) * w if right else x
    for i, (k, m) in enumerate(items):
        r = pygame.Rect(x0 + i * w, y, w - 6, 24)
        pygame.draw.rect(surf, T.PANEL_DARK, r, border_radius=6)
        pygame.draw.rect(surf, tuple(m["color"]), r, 1, border_radius=6)
        ic = icon(f"mat_{k}", 20)
        if ic:
            surf.blit(ic, (r.x + 3, r.y + 2))
        else:
            pygame.draw.polygon(surf, tuple(m["color"]), [(r.x + 12, r.y + 4), (r.x + 20, r.y + 12), (r.x + 12, r.y + 20),
                                                         (r.x + 4, r.y + 12)])
        T.text(surf, str(run.mat(k)), (r.x + 28, r.y + 3), 15, T.TEXT, True)
        scene.hit(r, None, [(m["name"], tuple(m["color"])), m["desc"]])


class AnvilScene(XScene):
    """Наковальня: выковать вещь (слот → база наковальни, 1–3 свойства из предложенных, закалка), перековать
    (тир +1), переплавить лишнее в руду, шедевр главы. Предложение наковальни фиксировано на узел."""

    def __init__(self, app):
        super().__init__(app)
        self.slot = "weapon"
        self.picks = []
        self.temper = False

    @property
    def node(self):
        return self.run.nodes[self.run.node]

    def act(self, action, button=1):
        run = self.run
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "slot":
            self.slot = action[1]
        elif kind == "prop":
            i = action[1]
            if i in self.picks:
                self.picks.remove(i)
            elif len(self.picks) < 3:
                self.picks.append(i)
            else:
                self.say("Не больше трёх свойств")
        elif kind == "temper":
            self.temper = not self.temper
        elif kind == "forge":
            item = run.forge_item(self.node, self.slot, self.picks, self.temper)
            if item:
                self.say(f"Выковано: {X.item_name(item)} — в сумке")
                self.picks, self.temper = [], False
                save(self.app)
            else:
                self.say("Не хватает металла")
        elif kind == "reforge":
            item = next((i for i in run.all_items() if i["uid"] == action[1]), None)
            if item and run.reforge(item):
                self.say(f"Перековано: {X.item_name(item)}")
                save(self.app)
            else:
                self.say("Не хватает металла")
        elif kind == "smelt":
            item = next((i for i in run.bag if i["uid"] == action[1]), None)
            if item:
                n = run.smelt(item)
                self.say(f"Переплавлено: руда +{n}")
                save(self.app)
        elif kind == "master":
            item = run.forge_masterpiece(action[1])
            self.say(f"Шедевр выкован: {X.item_name(item)}!" if item else "Не хватает металла")
            if item:
                save(self.app)
        elif kind == "leave":
            to_map(self.app)
        elif kind == "hero":
            self.app.switch(HeroScene(self.app, action[1], back=lambda: self.app.switch(self)))

    def key(self, k):
        if k == pygame.K_ESCAPE:
            self.act("leave")

    def _mini(self, surf, r, label, action, ok, accent, tip=None, left=False):
        """Небольшая кнопка с мелким шрифтом (строки списка)."""
        hot = ok and r.collidepoint(self.mouse)
        pygame.draw.rect(surf, (70, 50, 32) if hot else (44, 34, 26), r, border_radius=6)
        pygame.draw.rect(surf, accent if ok else T.PANEL_EDGE, r, 2 if hot else 1, border_radius=6)
        col = T.TEXT if ok else T.TEXT_DIM
        if left:
            T.text(surf, label, (r.x + 10, r.y + 7), 13, col, True)
        else:
            T.text(surf, label, r.center, 13, col, True, center=True)
        self.hit(r, action if ok else None, tip)

    def draw(self, surf):
        run, xd = self.run, self.xd
        self.hits = []
        surf.fill(T.BG)
        self.backdrop(surf, "anvil", "thread", dim=185)
        self.header(surf, "Наковальня", "Своя вещь из руды: база и 1–3 свойства на выбор. Перековка, переплавка, "
                                        "шедевры. Esc — уйти")
        draw_mats(self, surf, run, T.SCREEN_W - 26, 52, right=True)
        off = run.anvil_offer(self.node)
        # ---- выковать ----
        left = pygame.Rect(24, 92, 600, 490)
        T.frame(surf, left, 230, accent=HEAT)
        T.text(surf, "Выковать вещь", (left.x + 14, left.y + 10), 19, HEAT, True)
        x = left.x + 14
        for slot in X.SLOTS:
            r = pygame.Rect(x, left.y + 40, 140, 30)
            on = slot == self.slot
            base = xd["items"]["bases"][off["bases"][slot]]["name"]
            W.button(surf, r, f"{xd['items']['slots'][slot]}", self.mouse, True, HEAT if on else (120, 110, 100))
            self.hit(r, ("slot", slot), [f"{xd['items']['slots'][slot]}: {base}"])
            x += 146
        base_item = {"base": off["bases"][self.slot], "tier": run.item_tier(), "affixes": []}
        y = left.y + 80
        for ln in X.base_text(xd, base_item):
            T.text(surf, f"База «{xd['items']['bases'][off['bases'][self.slot]]['name']}»: {ln}", (left.x + 14, y), 14,
                   T.TEXT_DIM)
            y += 18
        y += 6
        for i, p in enumerate(off["props"]):
            r = pygame.Rect(left.x + 10, y, left.w - 20, 34)
            on = i in self.picks
            pygame.draw.rect(surf, (70, 44, 26) if on else (44, 34, 26), r, border_radius=6)
            pygame.draw.rect(surf, HEAT if on else T.PANEL_EDGE, r, 2 if on else 1, border_radius=6)
            box = pygame.Rect(r.x + 8, r.y + 9, 16, 16)
            pygame.draw.rect(surf, HEAT if on else (90, 80, 70), box, 0 if on else 2, border_radius=3)
            txt = X.affix_text(xd, p, run.item_tier())
            T.text(surf, fit(txt, 14, r.w - 190), (r.x + 34, r.y + 8), 14, T.TEXT if on else T.TEXT_DIM, on)
            cost = run.prop_cost(p)
            T.text(surf, run.mats_line(cost), (r.right - 150, r.y + 9), 13, GOLD if run.can_pay(cost) else CURSE)
            self.hit(r, ("prop", i), [txt, "Свойство-срабатывание" if p["kind"] == "proc" else "Свойство-стат",
                                      "Цена: " + run.mats_line(cost)])
            y += 38
        props = [off["props"][i] for i in self.picks]
        cost = run.forge_cost(props) if props else run.forge_cfg()["cost_base"]
        if self.temper:
            cost = dict(cost, emberheart=cost.get("emberheart", 0) + 1)
        rar = {0: "—", 1: "обычная", 2: "редкая", 3: "эпическая"}[len(props)]
        y += 6
        tr = pygame.Rect(left.x + 14, y, 280, 28)
        W.button(surf, tr, ("[x] " if self.temper else "[ ] ") + "Закалка сердцем углей", self.mouse, run.mat("emberheart") > 0
                 or self.temper, (255, 140, 60))
        self.hit(tr, "temper", ["Закалка: тир вещи +1", "Стоит 1 сердце углей"])
        T.text(surf, f"Вещь: {rar} · свойств {len(props)}/3", (left.x + 310, y + 5), 15, T.TEXT, True)
        y += 36
        ok = bool(props) and run.can_pay(cost)
        fr = pygame.Rect(left.x + 14, y, 300, 40)
        self.button(surf, fr, "Выковать", "forge", ok, HEAT, "Цена: " + run.mats_line(cost))
        T.text(surf, "Цена: " + run.mats_line(cost), (fr.right + 14, fr.y + 11), 14, GOLD if ok else CURSE)
        # ---- перековать / переплавить ----
        right = pygame.Rect(640, 92, T.SCREEN_W - 664, 300)
        T.frame(surf, right, 230)
        T.text(surf, "Перековать (тир +1) · переплавить сумку", (right.x + 14, right.y + 10), 17, T.TEXT, True)
        y = right.y + 38
        rc = run.mats_line(run.forge_cfg()["cost_upgrade"])
        for item in run.all_items()[:7]:
            r = pygame.Rect(right.x + 10, y, right.w - 20, 30)
            T.text(surf, fit(X.item_name(item), 14, right.w - 250), (r.x + 4, r.y + 6), 14, rarity_color(xd, item), True)
            b = pygame.Rect(r.right - 224, r.y + 2, 110, 26)
            can = run.can_pay(run.reforge_cost(item)) and item["tier"] < 3
            self._mini(surf, b, "перековать", ("reforge", item["uid"]), can, HEAT,
                       self.item_tip(item) + [("Перековать: " + rc, GOLD)])
            if item in run.bag:
                b2 = pygame.Rect(r.right - 108, r.y + 2, 104, 26)
                self._mini(surf, b2, f"в руду +{run.smelt_value(item)}", ("smelt", item["uid"]), True, (190, 150, 110),
                           ["Переплавить: вещь исчезнет", f"Руда +{run.smelt_value(item)}"])
            y += 34
        # ---- шедевры ----
        mp = pygame.Rect(640, 404, T.SCREEN_W - 664, 178)
        T.frame(surf, mp, 230, accent=(150, 200, 255))
        mc = run.forge_cfg()["cost_masterpiece"]
        T.text(surf, "Шедевр: " + run.mats_line(mc), (mp.x + 14, mp.y + 10), 16, (150, 200, 255), True)
        y = mp.y + 36
        can = run.can_pay(mc)
        for uid in run.masterpieces()[:4]:
            u = xd["items"]["uniques"][uid]
            r = pygame.Rect(mp.x + 10, y, mp.w - 20, 30)
            self._mini(surf, r, fit(f"{u['name']} — {u['desc']}", 13, r.w - 20), ("master", uid), can, (150, 200, 255),
                       [(u["name"], (255, 170, 60)), u["desc"], "Цена: " + run.mats_line(mc)], left=True)
            y += 34
        if run.forge_on() and not run.masterpieces():
            T.text(surf, "Все шедевры уже у отряда", (mp.x + 14, y + 4), 14, T.TEXT_DIM)
        self.button(surf, pygame.Rect(T.SCREEN_W - 166, T.SCREEN_H - 64, 150, 44), "Уйти (Esc)", "leave")
        self.draw_party(surf, T.SCREEN_H - 180, h=150)
        self.draw_tip(surf)
        self.draw_toast(surf, T.SCREEN_H - 200)


# ---------- торговец ----------

class ShopScene(XScene):
    def act(self, action, button=1):
        run = self.run
        kind = action[0] if isinstance(action, tuple) else action
        if kind == "buy":
            if not run.buy(run.node, action[1]):
                self.say("Не хватает золота")
        elif kind == "sell":
            got = run.sell(action[1])
            self.say(f"Продано за {got}")
        elif kind == "heal":
            if not run.buy_heal():
                self.say("Не хватает золота")
        elif kind == "uncurse":
            if not run.buy_uncurse():
                self.say("Не хватает золота")
        elif kind == "hero":
            self.app.switch(HeroScene(self.app, action[1], back=lambda: self.app.switch(ShopScene(self.app))))
        elif kind == "leave":
            to_map(self.app)

    def key(self, k):
        if k == pygame.K_ESCAPE:
            to_map(self.app)

    def draw(self, surf):
        run, xd = self.run, self.xd
        self.hits = []
        surf.fill((20, 18, 12))
        self.backdrop(surf, "shop", "act", dim=80)
        band = pygame.Surface((T.SCREEN_W, 80), pygame.SRCALPHA)
        band.fill((8, 8, 10, 170))
        surf.blit(band, (0, 0))
        self.header(surf, "Торговец", "Болотный торговец: лодка, фонарь и сундук с добром. ПКМ по вещи в сумке "
                                      "справа — продать.")
        stock = run.nodes[run.node].get("stock", [])
        for i, o in enumerate(stock):
            r = pygame.Rect(26 + i * 232, 90, 220, 262)
            if o is None:
                pygame.draw.rect(surf, (30, 30, 30), r, border_radius=10)
                T.text(surf, "продано", r.center, 16, T.TEXT_DIM, center=True)
                continue
            it = o["item"]
            rar = xd["items"]["rarities"][it["rarity"]]["name"]
            lines = [(f"{xd['items']['slots'][it['slot']]} · {rar}", T.TEXT_DIM)]
            lines += [(s, T.TEXT) for s in X.item_lines(xd, it)]
            W.card(surf, r, X.item_name(it), lines, self.mouse, rarity_color(xd, it), run.gold >= o["price"],
                   badge=f"{o['price']}")
            ic = item_icon(it, 48)
            if ic:
                surf.blit(ic, (r.x + 12, r.bottom - 58))
            self.hit(r, ("buy", i))
        sx = 26 + 4 * 232 + 10
        box = pygame.Rect(sx, 90, T.SCREEN_W - sx - 24, 262)
        pygame.draw.rect(surf, T.PANEL, box, border_radius=10)
        T.text(surf, "Сумка — ПКМ продать", (box.x + 10, box.y + 8), 15, T.TEXT, True)
        y = box.y + 32
        for item in run.bag[:9]:
            r = pygame.Rect(box.x + 8, y, box.w - 16, 26)
            pygame.draw.rect(surf, (46, 35, 26), r, border_radius=5)
            T.text(surf, X.item_name(item), (r.x + 8, r.y + 5), 13, rarity_color(xd, item), True)
            self.hit(r, ("sell", item["uid"]), self.item_tip(item) + [(f"ПКМ — продать за "
                                                                        f"{X.item_price(xd, item) // 3}", GOLD)])
            y += 29
        self.button(surf, pygame.Rect(26, 366, 300, 46), f"Лекарь: +{run.cfg['shop']['heal_pct'] * 100:.0f}% HP — "
                    f"{run.heal_price()}", "heal", run.gold >= run.heal_price(), (90, 220, 120))
        self.button(surf, pygame.Rect(346, 366, 330, 46), f"Снять проклятие — {run.curse_price()}", "uncurse",
                    bool(run.curses) and run.gold >= run.curse_price(), CURSE)
        self.button(surf, pygame.Rect(T.SCREEN_W - 250, 366, 226, 46), "Уйти (Esc)", "leave")
        for r, k in scene_party(surf, run, mouse=self.mouse):
            self.hit(r, ("hero", k), [run.heroes[k].name, "Клик — лист героя: надеть купленное"])
        self.draw_tip(surf)
        self.draw_toast(surf, 440)

    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
            for r, action, _ in self.hits:
                if isinstance(action, tuple) and action[0] == "sell" and r.collidepoint(ev.pos):
                    self.act(action)
                    return
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for r, action, _ in self.hits:
                if isinstance(action, tuple) and action[0] == "sell" and r.collidepoint(ev.pos):
                    return                                # левая кнопка по сумке ничего не продаёт
        super().handle(ev)


# ---------- итоги ----------

class EndScene(XScene):
    def __init__(self, app, end):
        super().__init__(app)
        self.end = end

    def act(self, action, button=1):
        to_tavern(self.app)

    def key(self, k):
        if k in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE):
            to_tavern(self.app)

    def draw(self, surf):
        e = self.end
        self.hits = []
        surf.fill((12, 12, 14))
        win = e["result"] == "victory"
        self.backdrop(surf, "victory" if win else "defeat", "thread" if win else "act", dim=70)
        band = pygame.Surface((T.SCREEN_W, 230), pygame.SRCALPHA)
        band.fill((8, 8, 10, 160))
        surf.blit(band, (0, 140))
        cv = X.chapter_view(self.app.profile.xd, e.get("chapter", "swamp"))
        title = {"swamp": "Болото покорено!", "forge": "Кузни остыли!"}.get(e.get("chapter", "swamp"), "Глава пройдена!")
        T.text(surf, title if win else "Поход окончен", (T.SCREEN_W // 2, 180), 48,
               GLORY if win else CURSE, True, center=True, shadow=True)
        acts = cv["acts"]
        T.text(surf, f"Дошли до: {acts[min(e['act'], len(acts) - 1)]['name']}", (T.SCREEN_W // 2, 250), 20, T.TEXT,
               center=True)
        c = e["counts"]
        T.text(surf, f"Боёв {c.get('battle', 0)} · элиты {c.get('elite', 0)} · боссов {c.get('boss', 0)} · "
                     f"событий {c.get('event', 0)}", (T.SCREEN_W // 2, 286), 17, T.TEXT_DIM, center=True)
        T.text(surf, f"Слава: +{e['glory']}", (T.SCREEN_W // 2, 340), 30, GLORY, True, center=True)
        extra = []
        trophies = self.app.profile.xd.get("trophies", {})
        for k, v in (e.get("trophies") or {}).items():
            extra.append(f"{trophies.get(k, {}).get('name', k)} +{v}")
        if e.get("veterans"):
            extra.append("в таверну ветеранами: " + ", ".join(e["veterans"]))
        elif e["result"] != "victory":
            extra.append("павшие — в зал славы")
        if extra:
            T.text(surf, " · ".join(extra), (T.SCREEN_W // 2, 376), 17, BLESS if win else T.TEXT_DIM, True,
                   center=True, shadow=True)
        img_h = T.SCREEN_W * 2 // 3                  # отряд на земле сцены, в её масштабе
        k = T.SCREEN_W / 192 / 2
        ground = (T.SCREEN_H - img_h) // 2 + int(img_h * 0.95)
        data = self.app.profile.data
        x = 30
        for name, cls, lvl in e["heroes"]:
            img = hero_sprite(data, cls, k)
            if not win:
                img = img.copy()
                img.fill((150, 150, 165, 255), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(img, (x, ground - img.get_height()))
            T.text(surf, f"{name} · ур. {lvl}", (x + img.get_width() // 2, ground - img.get_height() + 18), 15,
                   T.TEXT, True, center=True, shadow=True)
            x += int(56 * k)
        self.button(surf, pygame.Rect(T.SCREEN_W - 320, T.SCREEN_H - 84, 280, 50), "В таверну (Пробел)", "go", True,
                    GOLD)
