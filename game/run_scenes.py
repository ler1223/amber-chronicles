"""Экраны вылазки: карта, навыки, выбор (награда/предмет/отдых/торговец/трофей), конец вылазки."""
import math

import pygame

from sim.run import NODE_NAMES, RARITY_NAMES, SLOT_NAMES
from ui import theme as T
from ui import widgets as W
from ui.autocast_editor import AutocastEditor

BRANCH_COLOR = (255, 150, 90)
AMBER = (255, 170, 60)
RUNE_COLOR = (255, 200, 120)
RELIC_COLOR = (240, 140, 90)

NODE_COLORS = {"battle": (200, 85, 70), "elite": (230, 150, 40), "boss": (170, 70, 210), "guard": (220, 110, 60),
               "rest": (80, 185, 105), "shop": (225, 200, 80)}
NODE_LETTERS = {"battle": "Б", "elite": "Э", "boss": "!", "guard": "С", "rest": "О", "shop": "Т"}


class Option:
    def __init__(self, title, lines, on_pick, accent=(90, 180, 255), enabled=True, header=None, badge=None):
        self.title, self.lines, self.on_pick = title, lines, on_pick
        self.accent, self.enabled, self.header, self.badge = accent, enabled, header, badge


class ChoiceScene:
    """Экран выбора одной из карточек. Внизу — отряд, чтобы было видно, кому что нужно.
    skip — (надпись, callback): кнопка, Esc и Enter; alt — (надпись, callback): дополнительная кнопка."""

    def __init__(self, app, title, subtitle, options, skip=None, alt=None):
        self.app = app
        self.title, self.subtitle = title, subtitle
        self.options = options
        self.skip = skip
        self.alt = alt
        self.mouse = (0, 0)
        self.rects = []
        self.skip_rect = None
        self.alt_rect = None

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.mouse = ev.pos
            for r, opt in self.rects:
                if r.collidepoint(ev.pos) and opt.enabled:
                    opt.on_pick()
                    return
            if self.skip and self.skip_rect and self.skip_rect.collidepoint(ev.pos):
                self.skip[1]()
            elif self.alt and self.alt_rect and self.alt_rect.collidepoint(ev.pos):
                self.alt[1]()
        elif ev.type == pygame.KEYDOWN:
            i = ev.key - pygame.K_1
            if 0 <= i < len(self.options) and self.options[i].enabled:
                self.options[i].on_pick()
            elif ev.key in (pygame.K_ESCAPE, pygame.K_RETURN) and self.skip:
                self.skip[1]()

    def update(self, dt):
        pass

    def draw(self, surf):
        surf.fill(T.BG)
        run = self.app.run
        T.text(surf, self.title, (T.SCREEN_W // 2, 54), 34, T.TEXT, True, center=True)
        if self.subtitle:
            T.text(surf, self.subtitle, (T.SCREEN_W // 2, 96), 18, T.TEXT_DIM, center=True)
        if run:
            gold = f"Золото: {run.gold}"
            T.text(surf, gold, (T.SCREEN_W - 30 - T.font(20, True).size(gold)[0], 20), 20, W.GOLD, True)
        n = len(self.options)
        cw, gap = min(260, (T.SCREEN_W - 80 - (n - 1) * 20) // max(1, n)), 20
        x0 = (T.SCREEN_W - (n * cw + (n - 1) * gap)) // 2
        self.rects = []
        for i, opt in enumerate(self.options):
            r = pygame.Rect(x0 + i * (cw + gap), 130, cw, 230)
            self.rects.append((r, opt))
            W.card(surf, r, opt.title, opt.lines, self.mouse, opt.accent, opt.enabled, opt.header, opt.badge)
            T.text(surf, str(i + 1), (r.centerx, r.bottom + 14), 15, T.TEXT_DIM, center=True)
        buttons = [b for b in (self.skip, self.alt) if b]
        x = T.SCREEN_W // 2 - (len(buttons) * 240 - 20) // 2
        self.skip_rect = self.alt_rect = None
        for b in buttons:
            r = pygame.Rect(x, 404, 220, 44)
            W.button(surf, r, b[0], self.mouse)
            if b is self.skip:
                self.skip_rect = r
            else:
                self.alt_rect = r
            x += 240
        if run:
            draw_squad_row(surf, run, self.mouse, 470)


def draw_squad_row(surf, run, mouse, y, highlight=None):
    rects = []
    w = (T.SCREEN_W - 48 - 3 * 16) // 4
    for i, m in enumerate(run.squad):
        r = pygame.Rect(24 + i * (w + 16), y, w, T.SCREEN_H - y - 20)
        slots = W.member_card(surf, r, run, m, mouse, highlight is m)
        rects.append((r, slots, m))
    return rects


def hero_name(run, m):
    return run.data.classes[m.cls]["name"] + (f" · {run.data.paths[m.path]['name']}" if m.path else "")


# ---------- карта ----------

class MapScene:
    def __init__(self, app):
        self.app = app
        self.mouse = (0, 0)
        self.picked_item = None      # предмет из сумки, который надеваем
        self.node_pos = {}
        self.member_rects = []
        self.bag_rects = []
        self.relic_rects = []
        self.clock = 0.0
        self._layout()

    def _layout(self):
        nodes = self.app.run.nodes
        layers = max(n["layer"] for n in nodes.values()) + 1
        x0, x1, y0, y1 = 90, T.SCREEN_W - 90, 105, 365
        for n in nodes.values():
            x = x0 + (x1 - x0) * n["layer"] / max(1, layers - 1)
            y = y0 + (y1 - y0) * (n["idx"] + 0.5) / n["count"]
            self.node_pos[n["id"]] = (x, y)

    def node_at(self, pos):
        for nid, p in self.node_pos.items():
            if math.dist(p, pos) <= 28:
                return nid
        return None

    def handle(self, ev):
        run = self.app.run
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            self.mouse = ev.pos
            if ev.button == 3:
                self.picked_item = None
                return
            nid = self.node_at(ev.pos)
            if nid and nid in run.available():
                self.app.enter_node(nid)
                return
            for r, item in self.bag_rects:
                if r.collidepoint(ev.pos):
                    self.picked_item = None if self.picked_item == item else item
                    return
            for r, slots, m in self.member_rects:
                if self.picked_item and r.collidepoint(ev.pos):
                    run.equip(m, self.picked_item)
                    self.picked_item = None
                    return
                for slot, sr in slots.items():
                    if sr.collidepoint(ev.pos) and m.items.get(slot):
                        run.unequip(m, slot)
                        return
                if r.collidepoint(ev.pos):
                    self.app.switch(SkillsScene(self.app, m))
                    return
        elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.picked_item = None

    def update(self, dt):
        self.clock += dt

    def draw(self, surf):
        run = self.app.run
        surf.fill(T.BG)
        title = f"Вылазка: {run.region['name']}" if run.region else "Вылазка: Болото"
        w = T.text(surf, title, (24, 16), 28, T.TEXT, True).w
        extra = f"   ·   перебросов наград: {run.rerolls}" if run.rerolls else ""
        T.text(surf, f"угроза {run.threat}   ·   побед: {run.battles_won}   ·   сид {run.seed}{extra}",
               (24 + w + 20, 26), 15, T.TEXT_DIM)
        gold = f"Золото: {run.gold}"
        T.text(surf, gold, (T.SCREEN_W - 30 - T.font(22, True).size(gold)[0], 18), 22, W.GOLD, True)
        T.text(surf, "Выберите узел (подсвечены). Клик по герою — навыки и автокаст. Предметы: клик по предмету "
                     "в сумке, затем по герою; клик по слоту — снять.", (24, 62), 14, T.TEXT_DIM)

        avail = set(run.available())
        visited = set(run.path)
        for n in run.nodes.values():
            for nxt in n["next"]:
                a, b = self.node_pos[n["id"]], self.node_pos[nxt]
                on_path = n["id"] in visited and nxt in visited
                from_here = n["id"] == run.node and nxt in avail
                col = (230, 230, 230) if on_path else (120, 200, 255) if from_here else (60, 64, 76)
                pygame.draw.line(surf, col, a, b, 4 if on_path or from_here else 2)
        hover = self.node_at(self.mouse)
        for n in run.nodes.values():
            x, y = self.node_pos[n["id"]]
            col = NODE_COLORS[n["type"]]
            r = 30 if n["type"] in ("boss", "guard") else 24
            if n["id"] in avail:
                pulse = 4 + 3 * math.sin(self.clock * 5)
                pygame.draw.circle(surf, (120, 200, 255), (x, y), r + 6 + pulse, 3)
            dim = n["id"] not in avail and n["id"] not in visited
            pygame.draw.circle(surf, T.mix(col, (20, 20, 24), 0.55) if dim else col, (x, y), r)
            if n["id"] == run.node:
                pygame.draw.circle(surf, (255, 255, 255), (x, y), r + 3, 3)
            elif n["id"] in visited:
                pygame.draw.circle(surf, (200, 200, 200), (x, y), r, 2)
            T.text(surf, NODE_LETTERS[n["type"]], (x, y), 20, (255, 255, 255), True, center=True, shadow=True)
            T.text(surf, NODE_NAMES[n["type"]], (x, y + r + 12), 13, T.TEXT_DIM if dim else T.TEXT, center=True)

        # реликвии
        y = 398
        T.text(surf, "Реликвии:", (24, y), 16, T.TEXT_DIM, True)
        self.relic_rects = []
        x = 112
        if not run.relics:
            T.text(surf, "нет — их дают элита и торговец", (x, y + 1), 15, T.TEXT_DIM)
        for rid in run.relics:
            name = run.data.relics[rid]["name"]
            rw = T.font(14, True).size(name)[0] + 20
            r = pygame.Rect(x, y - 3, rw, 26)
            pygame.draw.rect(surf, (54, 40, 32), r, border_radius=6)
            pygame.draw.rect(surf, RELIC_COLOR, r, 1, border_radius=6)
            T.text(surf, name, (r.x + 10, r.y + 4), 14, RELIC_COLOR, True)
            self.relic_rects.append((r, rid))
            x += rw + 8

        # сумка
        y = 434
        T.text(surf, "Сумка:", (24, y), 16, T.TEXT_DIM, True)
        self.bag_rects = []
        x = 112
        if not run.inventory:
            T.text(surf, "пусто", (x, y + 1), 15, T.TEXT_DIM)
        for item in run.inventory:
            name = run.data.items[item]["name"]
            iw = T.font(14, True).size(name)[0] + 20
            r = pygame.Rect(x, y - 3, iw, 26)
            sel = self.picked_item == item
            col = W.item_color(run.data, item)
            pygame.draw.rect(surf, (80, 70, 30) if sel else (44, 42, 36), r, border_radius=6)
            pygame.draw.rect(surf, col, r, 2 if sel else 1, border_radius=6)
            T.text(surf, name, (r.x + 10, r.y + 4), 14, col, True)
            self.bag_rects.append((r, item))
            x += iw + 8
        self.member_rects = draw_squad_row(surf, run, self.mouse, 470)

        if hover:
            self._node_tooltip(surf, run.nodes[hover])
        else:
            tip = next((self.app.data.relics[rid]["desc"] for r, rid in self.relic_rects if r.collidepoint(self.mouse)),
                       None)
            item = self.picked_item or next((i for r, i in self.bag_rects if r.collidepoint(self.mouse)), None)
            if item:
                it = run.data.items[item]
                tip = f"{SLOT_NAMES[it['slot']]}, {RARITY_NAMES[it['rarity']]}: {it['desc']}" + \
                      (" — кликните по герою" if self.picked_item else "")
            if tip:
                T.text(surf, tip, (24, 82), 14, T.TEXT)

    def _node_tooltip(self, surf, n):
        data = self.app.data
        lines = [(NODE_NAMES[n["type"]], NODE_COLORS[n["type"]])]
        if n["encounter"] is not None:
            enc = data.encounters[n["encounter"]]
            lines.append((enc["name"], T.TEXT))
            counts = {}
            for e in enc["enemies"]:
                name = data.enemies[e["type"]]["name"]
                counts[name] = counts.get(name, 0) + 1
            for name, k in counts.items():
                lines.append((f"{name} ×{k}" if k > 1 else name, T.TEXT_DIM))
            if n["type"] == "elite":
                lines.append(("Награда: реликвия, редкий предмет или руна", AMBER))
        elif n["type"] == "rest":
            lines.append(("Лечение отряда или тренировка героя", T.TEXT_DIM))
        elif n["type"] == "shop":
            lines.append(("Предметы, руна, реликвия и лекарь", T.TEXT_DIM))
        w = max(T.font(14).size(s)[0] for s, _ in lines) + 20
        x, y = self.node_pos[n["id"]]
        box = pygame.Rect(min(x + 34, T.SCREEN_W - w - 10), y - 20, w, len(lines) * 19 + 12)
        pygame.draw.rect(surf, (12, 14, 18), box, border_radius=6)
        pygame.draw.rect(surf, T.PANEL_EDGE, box, 1, border_radius=6)
        for i, (s, col) in enumerate(lines):
            T.text(surf, s, (box.x + 10, box.y + 6 + i * 19), 14, col, i == 0)


class SkillsScene:
    """Навыки героя в вылазке: форма (ветка с подготовки), руны и настройка автокаста."""

    ROW_H = 128

    def __init__(self, app, member):
        self.app = app
        self.m = member
        self.mouse = (0, 0)
        self.settings = app.run.autocast_for(member)   # тот же словарь, что уйдёт в бой
        proto = app.run.proto(member)
        self.proto = proto
        self.editors = [(sid, AutocastEditor(proto["skill_defs"][sid], self.settings[sid], app.data.tags))
                        for sid in proto["skills"]]
        self.back = pygame.Rect(T.SCREEN_W // 2 - 110, T.SCREEN_H - 62, 220, 44)

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.back.collidepoint(ev.pos):
                self._leave()
                return
            for _, ed in self.editors:
                if ed.click(ev.pos):
                    return
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_RETURN):
            self._leave()

    def _leave(self):
        self.app.profile.remember_autocast(self.app.run)
        self.app.switch(MapScene(self.app))

    def update(self, dt):
        pass

    def draw(self, surf):
        m, p = self.m, self.proto
        surf.fill(T.BG)
        T.text(surf, f"{hero_name(self.app.run, m)} · ур. {m.level} — навыки и автокаст", (24, 18), 28, T.TEXT, True)
        T.text(surf, "Ветки выбираются на подготовке перед вылазкой, руны — награды вылазки. Автокаст применяет "
                     "навык сам, когда выполнены условия; ручной приказ главнее.", (24, 58), 14, T.TEXT_DIM)
        y = 90
        for i, (sid, ed) in enumerate(self.editors):
            sk = p["skill_defs"][sid]
            row = pygame.Rect(24, y, T.SCREEN_W - 48, self.ROW_H - 8)
            pygame.draw.rect(surf, T.PANEL, row, border_radius=10)
            x = row.x + 14
            T.text(surf, "QWERT"[i], (x, row.y + 10), 22, T.SELECT, True)
            T.text(surf, sk["name"], (x + 28, row.y + 10), 19, T.TEXT, True)
            info = [f"AP {sk['ap']}"]
            if sk["cast"]:
                info.append(f"каст {sk['cast']:g}с")
            if sk["range"]:
                info.append(f"дал. {sk['range']}")
            if sk["cooldown"]:
                info.append(f"кд {sk['cooldown']:g}с")
            T.text(surf, " · ".join(info), (x + 28, row.y + 36), 14, T.AP_COLOR)
            for j, line in enumerate(T.wrap(sk["desc"], 14, 420)[:3]):
                T.text(surf, line, (x + 28, row.y + 56 + j * 17), 14, T.TEXT)
            self._form_info(surf, sid, sk, pygame.Rect(row.x + 480, row.y + 10, 300, row.h - 20))
            ed.draw(surf, pygame.Rect(row.right - 360, row.y + (row.h - ed.height()) // 2, 350, ed.height()),
                    self.mouse)
            y += self.ROW_H
        W.button(surf, self.back, "Назад (Esc)", self.mouse)

    def _form_info(self, surf, sid, sk, rect):
        data = self.app.data
        y = rect.y
        br = data.branches.get(sid)
        if sk.get("branch") and br:
            b, tier = sk["branch"]
            T.text(surf, f"Ветка {b}: {br[b]['name']} {tier}/2", (rect.x, y), 14, BRANCH_COLOR, True)
        elif br:
            T.text(surf, "Без ветки (выбирается на подготовке)", (rect.x, y), 13, T.TEXT_DIM)
        else:
            T.text(surf, "Навык от таланта или предмета", (rect.x, y), 13, T.TEXT_DIM)
        y += 22
        for rid in sk.get("runes", []):
            r = data.runes[rid]
            T.text(surf, f"{r['name']}: {r['desc']}", (rect.x, y), 13, RUNE_COLOR)
            y += 17


# ---------- фабрики экранов выбора ----------

def item_option(data, iid, on_pick, enabled=True, badge=None):
    it = data.items[iid]
    return Option(it["name"], [(it["desc"], T.TEXT)], on_pick, W.item_color(data, iid), enabled,
                  header=f"{SLOT_NAMES[it['slot']]} · {RARITY_NAMES[it['rarity']]}", badge=badge)


def offer_option(app, offer, on_pick, enabled=True, badge=None):
    """Карточка награды или товара: предмет, руна, реликвия, лечение, золото."""
    run, data = app.run, app.data
    t = offer["type"]
    if t == "item":
        return item_option(data, offer["item"], on_pick, enabled, badge)
    if t == "rune":
        m = run.squad[offer["member"]]
        rune = data.runes[offer["rune"]]
        sk = run.proto(m)["skill_defs"][offer["skill"]]
        return Option(rune["name"], [(f"→ {sk['name']}", RUNE_COLOR), (rune["desc"], T.TEXT)], on_pick, RUNE_COLOR,
                      enabled, header=f"Руна · {hero_name(run, m)}", badge=badge)
    if t == "relic":
        rel = data.relics[offer["relic"]]
        return Option(rel["name"], [(rel["desc"], T.TEXT), ("Действует до конца вылазки", T.TEXT_DIM)], on_pick,
                      RELIC_COLOR, enabled, header="Реликвия отряда", badge=badge)
    if t == "heal":
        return Option(f"Лечение +{int(offer['pct'] * 100)}%", [("Всему отряду от макс. HP", T.TEXT)], on_pick,
                      T.HEAL, enabled, header="Отдых", badge=badge)
    return Option(f"+{offer['amount']} золота", [("Пригодится у торговца", T.TEXT)], on_pick, W.GOLD, enabled,
                  header="Золото", badge=badge)


def reward_scene(app, summary, options=None):
    run = app.run
    parts = [f"+{summary['gold']} золота", f"+{summary['xp']} опыта"]
    if summary["level_ups"]:
        names = ", ".join(dict.fromkeys(hero_name(run, m) for m in summary["level_ups"]))
        parts.append(f"новый уровень (статы): {names}")
    if summary["fallen"]:
        parts.append("павшие встают с 1 HP")
    options = options or run.reward_options()
    cards = []
    for r in options:
        def pick(r=r):
            item = run.apply_reward(r)
            if item:
                app.switch(assign_item_scene(app, item, app.continue_run))
            else:
                app.continue_run()
        cards.append(offer_option(app, r, pick))

    def reroll():
        new = run.reroll()
        if new:
            app.switch(reward_scene(app, summary, new))
    alt = (f"Перебросить ({run.rerolls})", reroll) if run.rerolls else None
    return ChoiceScene(app, "Победа!", " · ".join(parts), cards, alt=alt)


def assign_item_scene(app, item_id, then):
    run, data = app.run, app.data
    slot = data.items[item_id]["slot"]

    def give(m):
        run.inventory.append(item_id)
        run.equip(m, item_id)
        then()

    def to_bag():
        run.inventory.append(item_id)
        then()

    options = []
    for m in run.squad:
        old = m.items.get(slot)
        now = f"Сейчас: {data.items[old]['name']} (уйдёт в сумку)" if old else f"Слот «{SLOT_NAMES[slot]}» свободен"
        lines = [(now, T.TEXT_DIM)]
        options.append(Option(hero_name(run, m), lines, lambda m=m: give(m), tuple(data.classes[m.cls]["color"]),
                              header=f"ур. {m.level}"))
    item = data.items[item_id]
    return ChoiceScene(app, f"Кому отдать: {item['name']}?", f"{SLOT_NAMES[slot]}: {item['desc']}", options,
                       skip=("В сумку", to_bag))


def rest_scene(app):
    run = app.run
    pct = run.cfg["rest_heal"]

    def heal():
        run.heal_all(pct)
        app.continue_run()

    def train():
        options = []
        for m in run.squad:
            ok = m.level < run.cfg["max_level"]

            def pick(m=m):
                run.level_up(m)
                app.continue_run()
            options.append(Option(hero_name(run, m), [(f"ур. {m.level} → {m.level + 1}" if ok else "макс. уровень",
                                                       T.TEXT)], pick, tuple(run.data.classes[m.cls]["color"]), ok))
        app.switch(ChoiceScene(app, "Тренировка", "Кто получит уровень (+HP, +урон, +сила навыков)?", options))

    can_train = any(m.level < run.cfg["max_level"] for m in run.squad)
    return ChoiceScene(app, "Привал", "Костёр в сухом месте. Одно дело до рассвета.", [
        Option(f"Отдых: +{int(pct * 100)}% HP", [("Весь отряд лечится от макс. HP", T.TEXT)], heal, T.HEAL,
               header="Лечение"),
        Option("Тренировка", [("Один герой получает уровень: +HP, +урон, +сила навыков", T.TEXT)], train,
               (170, 140, 255), can_train, header="Уровень"),
    ])


def shop_scene(app):
    run = app.run
    options = []
    for offer in run.shop_stock:
        def buy(offer=offer):
            ok, item = run.buy(offer)
            if not ok:
                return
            if item:
                app.switch(assign_item_scene(app, item, lambda: app.switch(shop_scene(app))))
            else:
                app.switch(shop_scene(app))
        options.append(offer_option(app, offer, buy, run.gold >= offer["price"], f"{offer['price']} з."))
    h = run.cfg["shop_heal"]

    def heal():
        if run.buy_heal():
            app.switch(shop_scene(app))
    options.append(Option(f"Лекарь +{int(h['pct'] * 100)}%", [("Лечит весь отряд", T.TEXT)], heal, T.HEAL,
                          run.gold >= run.heal_price(), header="Услуга", badge=f"{run.heal_price()} з."))
    return ChoiceScene(app, "Торговец", "Кожаный навес у тропы. Выбирайте, пока не стемнело.", options,
                       skip=("Уйти", app.continue_run))


def trophy_scene(app, summary, then):
    """После победы над стражем: один трофей навсегда уходит в арсенал."""
    data = app.data

    def take(iid):
        app.profile.add_trophy(iid)
        summary["trophy"] = iid
        then()
    options = [item_option(data, iid, lambda iid=iid: take(iid)) for iid in summary["trophies"]]
    return ChoiceScene(app, "Трофей стража", "Выберите предмет — он навсегда попадёт в арсенал лагеря", options,
                       skip=("Без трофея", then))


class RunEndScene:
    """Итог вылазки: захват региона, янтарь, мастерство, трофей. summary — из Profile.finish_run."""

    def __init__(self, app, summary=None):
        self.app = app
        self.summary = summary or {}
        self.mouse = (0, 0)

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        if (ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_SPACE)) or \
                (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1):
            self.app.to_hub()

    def update(self, dt):
        pass

    def draw(self, surf):
        run, data = self.app.run, self.app.data
        surf.fill(T.BG)
        win = run.result == "victory"
        T.text(surf, "ВЫЛАЗКА ПРОЙДЕНА" if win else "ОТРЯД РАЗБИТ", (T.SCREEN_W // 2, 90), 52,
               (120, 230, 120) if win else (240, 90, 80), True, center=True, shadow=True)
        sm = self.summary
        T.text(surf, f"Побед в боях: {run.battles_won}   ·   пройдено узлов: {len(run.path)}",
               (T.SCREEN_W // 2, 146), 20, T.TEXT, center=True)
        y = 178
        if "amber" in sm:
            T.text(surf, f"+{sm['amber']} янтаря   (всего {self.app.profile.amber})", (T.SCREEN_W // 2, y), 22,
                   AMBER, True, center=True)
            y += 32
        if "mastery_xp" in sm:
            ups = [f"{data.classes[c]['name']} → {after}" for c, (before, after) in sm["mastery"].items()
                   if after > before]
            line = f"Мастерство: +{sm['mastery_xp']} опыта каждому герою"
            if ups:
                line += " · новый уровень: " + ", ".join(ups) + " (новые очки на подготовке)"
            T.text(surf, line, (T.SCREEN_W // 2, y), 17, W.XP, True, center=True)
            y += 28
        if sm.get("captured"):
            b = sm["bonus"]   # у логова босса бонуса нет
            text = f"Регион захвачен: {run.region['name']}"
            if b:
                text += f" — бонус «{b['name']}»: {b['desc']}"
            T.text(surf, text, (T.SCREEN_W // 2, y), 17, (120, 230, 120), True, center=True)
            y += 28
        if sm.get("trophy"):
            T.text(surf, f"Трофей в арсенале: {data.items[sm['trophy']]['name']}", (T.SCREEN_W // 2, y), 17,
                   W.item_color(data, sm["trophy"]), True, center=True)
            y += 28
        prof = self.app.profile
        if sm.get("biome_done"):
            diff = data.config["difficulties"][prof.difficulty]["name"]
            T.text(surf, f"Босс повержен — глава «{prof.biome['name']}» пройдена ({diff.lower()})!",
                   (T.SCREEN_W // 2, y), 20, (200, 150, 255), True, center=True)
            y += 28
        for cid, d in sm.get("opened", []):
            what = (f"Открыта новая глава: {data.biomes[cid]['name']}" if d == "normal" else
                    f"Открыта сложность «{data.config['difficulties'][d]['name']}» для главы «{data.biomes[cid]['name']}»")
            T.text(surf, what, (T.SCREEN_W // 2, y), 18, (255, 200, 120), True, center=True)
            y += 26
        T.text(surf, "Enter или клик — в лагерь", (T.SCREEN_W // 2, y + 8), 18, T.TEXT_DIM, center=True)
        draw_squad_row(surf, run, self.mouse, 380)
