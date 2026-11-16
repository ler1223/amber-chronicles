"""Прототип «Грань»: полноэкранная мастерская с вкладками.

Три вкладки:
  Клиенты   — выбрать заказ и перейти к работе.
  Закупка   — купить отдельный камень или лот.
  Мастерская — выбрать камень, огранить его или продать готовый.
"""
from __future__ import annotations

import math
import os
import random

import pygame

from game.workshop_games import JewelCut
from game import jewel_view as JV
from sim import gems as GM
from . import ui as U
from .model import Workshop

W, H = 1280, 800
TAB_Y = 78
CONTENT_Y = 142


def gem_color(w, gem):
    gd = GM.gem_def(w.xd, gem["id"])
    return GM.tint(tuple(gd.get("color", (120, 160, 220))), gem.get("col", 0.5))


def rough_color(w, rough):
    gd = GM.gem_def(w.xd, rough["id"])
    return GM.tint(tuple(gd.get("color", (120, 160, 220))), rough.get("col", 0.5))


def status_ru(status):
    return {"ok": "Принято", "discount": "Со скидкой", "wrong": "Не тот камень",
            "reject": "Отказ", "refused": "Отказ", "skipped": "Пропущен"}.get(status, status)


def sprite(name, w, h=None):
    img = JV.spr(name, w, h or w)
    return img


class Scene:
    def __init__(self, app):
        self.app = app
        self.mouse = (0, 0)
        self.hits = []

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.mouse = ev.pos
            for r, action in self.hits:
                if r.collidepoint(ev.pos) and action is not None:
                    self.act(action)
                    return

    def update(self, dt):
        pass

    def draw(self, surf):
        pass

    def act(self, action):
        pass

    def hit(self, r, action):
        self.hits.append((pygame.Rect(r), action))

    def button(self, surf, r, label, action, enabled=True, accent=U.GOLD, small=False):
        U.button(surf, r, label, self.mouse, enabled, accent, small)
        self.hit(r, action if enabled else None)


class HubScene(Scene):
    """Главный экран с тремя вкладками."""

    def __init__(self, app, tab="supply", client=None):
        super().__init__(app)
        self.tab = tab
        self.client = client
        self.selected = None          # ("rough", rough) / ("gem", gem)
        self._fix_client()

    def _fix_client(self):
        w = self.app.workshop
        rem = w.remaining_clients()
        if self.client is not None and self.client in rem:
            return
        self.client = rem[0] if rem else None

    def _header(self, surf):
        w = self.app.workshop
        U.text(surf, "ГРАНЬ", (24, 18), 30, U.GOLD, True)
        U.text(surf, f"День {w.day}", (178, 26), 18, U.TEXT, True)
        U.text(surf, f"Золото: {w.money}", (W - 310, 20), 20, U.GOLD, True)
        U.text(surf, f"Репутация: {w.reputation}", (W - 310, 46), 15, U.GREEN)
        if w.debt:
            U.text(surf, f"Долг: {w.debt}", (W - 310, 66), 15, U.RED)
        tabs = (("clients", "Клиенты", "npc_jeweler"),
                ("supply", "Закупка", "facet_lap"),
                ("workshop", "Мастерская", "facet_loupe"))
        x = 24
        for key, label, icon in tabs:
            r = pygame.Rect(x, TAB_Y, 184, 42)
            active = self.tab == key
            U.panel(surf, r, U.PANEL_HI if active else U.PANEL, U.GOLD if active else U.EDGE, 2, 8)
            ic = sprite(icon, 30)
            if ic:
                surf.blit(ic, (r.x + 8, r.y + 6))
            U.text(surf, label, (r.x + 44, r.y + 10), 17, U.TEXT if active else U.DIM, True)
            self.hit(r, ("tab", key))
            x += 196

    def act(self, action):
        w = self.app.workshop
        if isinstance(action, tuple) and action[0] == "tab":
            self.tab = action[1]
            self.selected = None
            self._fix_client()
            return
        if self.tab == "supply":
            if isinstance(action, tuple) and action[0] == "stock":
                if w.buy_stock(action[1]):
                    self.app.save()
            elif isinstance(action, tuple) and action[0] == "lot":
                if w.buy_lot(action[1]):
                    self.app.save()
        elif self.tab == "clients":
            if isinstance(action, tuple) and action[0] == "client":
                self.client = w.clients[action[1]]
                self.selected = None
            elif action == "to_workshop":
                if self.client:
                    self.tab = "workshop"
                    self.selected = None
            elif action == "skip":
                if self.client:
                    w.skip_client(self.client)
                    self.app.save()
                    self._fix_client()
            elif action == "day":
                self.app.switch(DayEndScene(self.app))
        elif self.tab == "workshop":
            if isinstance(action, tuple) and action[0] == "pick_rough":
                self.selected = ("rough", action[1])
            elif isinstance(action, tuple) and action[0] == "pick_gem":
                self.selected = ("gem", action[1])
            elif action == "back_clients":
                self.tab = "clients"
                self._fix_client()
            elif action == "cut" and self.selected and self.selected[0] == "rough" and self.client:
                rough = self.selected[1]
                w.inventory.remove(rough)
                self.app.switch(CutScene(self.app, rough, self.client))
            elif action == "sell" and self.selected and self.selected[0] == "gem" and self.client:
                gem = self.selected[1]
                status, offer = w.evaluate(self.client, gem)
                self.app.switch(ResultScene(self.app, self.client, gem, status, offer))

    # ---------- закупка ----------

    def _draw_supply(self, surf):
        w = self.app.workshop
        U.text(surf, "Закупка", (24, CONTENT_Y), 24, U.TEXT, True)
        U.text(surf, "Поставщик: отдельные камни · лоты: дешевле, но менее предсказуемы",
               (180, CONTENT_Y + 5), 14, U.DIM)
        for i, item in enumerate(w.stock):
            col, row = i % 3, i // 3
            r = pygame.Rect(24 + col * 410, 186 + row * 116, 390, 106)
            U.panel(surf, r)
            rough = item["rough"]
            JV.draw_rough(surf, rough, rough_color(w, rough), (r.x + 54, r.y + 54), 70,
                          t=self.app.clock * 0.4, xd=w.xd)
            U.text(surf, w.gem_name(rough["id"]), (r.x + 102, r.y + 8), 17, U.TEXT, True)
            U.text(surf, f"{rough['size']:.2f} ct · {GM.color_word(w.xd, rough['col'])}",
                   (r.x + 102, r.y + 31), 13, U.DIM)
            U.text(surf, U.fit(GM.describe(w.xd, rough, rough=True)[1], 12, 210),
                   (r.x + 102, r.y + 50), 12, U.TEXT)
            U.text(surf, f"{item['price']} з.", (r.x + 102, r.y + 70), 16, U.GOLD, True)
            self.button(surf, pygame.Rect(r.right - 94, r.bottom - 34, 82, 26), "Купить",
                        ("stock", i), w.money >= item["price"], small=True)
        U.text(surf, "Лоты", (24, 426), 20, U.TEXT, True)
        for i, lot in enumerate(w.lots):
            r = pygame.Rect(24 + i * 410, 458, 390, 98)
            U.panel(surf, r, U.PANEL, (110, 80, 50))
            U.text(surf, lot["label"], (r.x + 14, r.y + 10), 18, U.GOLD, True)
            U.text(surf, "камни из каравана · без полной проверки", (r.x + 14, r.y + 35), 13, U.DIM)
            U.text(surf, f"{lot['price']} з.", (r.x + 14, r.y + 62), 17, U.TEXT, True)
            self.button(surf, pygame.Rect(r.right - 94, r.bottom - 34, 82, 26), "Купить",
                        ("lot", i), w.money >= lot["price"], small=True)
        U.text(surf, f"В мастерской: {len(w.inventory)} · на витрине: {len(w.display)}",
               (24, 592), 14, U.DIM)
        self.button(surf, pygame.Rect(W - 250, 700, 226, 44), "К клиентам",
                    ("tab", "clients"), True, U.GREEN)

    # ---------- клиенты ----------

    def _draw_clients(self, surf):
        w = self.app.workshop
        rem = w.remaining_clients()
        U.text(surf, "Клиенты", (24, CONTENT_Y), 24, U.TEXT, True)
        U.text(surf, "Выберите заказ, затем перейдите в мастерскую", (196, CONTENT_Y + 5), 14, U.DIM)
        if not rem:
            U.text(surf, "Все клиенты на сегодня обслужены.", (24, 220), 20, U.DIM)
            self.button(surf, pygame.Rect(24, 280, 240, 44), "Завершить день", "day", True, U.GREEN)
            return
        for i, c in enumerate(w.clients):
            r = pygame.Rect(24, 184 + i * 94, 330, 82)
            sel = c is self.client
            U.panel(surf, r, U.PANEL_HI if sel else U.PANEL, U.GOLD if sel else U.EDGE)
            U.text(surf, c["name"], (r.x + 12, r.y + 9), 16, U.GOLD if sel else U.TEXT, True)
            U.text(surf, U.fit(c["desc"], 12, r.w - 24), (r.x + 12, r.y + 33), 12,
                   U.DIM if c["served"] else U.TEXT)
            U.text(surf, "Обслужен" if c["served"] else f"до {c['budget']} з.",
                   (r.x + 12, r.y + 56), 12, U.DIM)
            self.hit(r, ("client", i))

        c = self.client
        if c is None:
            return
        r = pygame.Rect(380, 184, 876, 360)
        U.panel(surf, r, U.PANEL, U.EDGE)
        portrait = sprite("npc_jeweler", 130, 170)
        if portrait:
            surf.blit(portrait, (r.x + 20, r.y + 28))
        else:
            U.panel(surf, pygame.Rect(r.x + 20, r.y + 28, 130, 170), U.PANEL_HI, U.EDGE)
        U.text(surf, c["name"], (r.x + 174, r.y + 22), 24, U.GOLD, True)
        U.text(surf, "Индивидуальный заказ" if c["kind"] == "custom" else "Покупатель витрины",
               (r.x + 174, r.y + 56), 14, U.BLUE)
        for k, ln in enumerate(U.wrap(c["desc"], 16, r.w - 210)):
            U.text(surf, ln, (r.x + 174, r.y + 86 + k * 22), 16, U.TEXT)
        U.text(surf, f"Бюджет клиента: до {c['budget']} з.", (r.x + 174, r.y + 164), 15, U.GOLD)
        self.button(surf, pygame.Rect(r.x + 174, r.bottom - 64, 260, 44),
                    "Гранить камень" if c["kind"] == "custom" else "Подобрать камень",
                    "to_workshop", True, U.GREEN)
        self.button(surf, pygame.Rect(r.x + 450, r.bottom - 64, 180, 44), "Пропустить",
                    "skip", True, U.RED, True)
        U.text(surf, "В мастерской можно выбрать камень и огранить его.", (r.x + 174, r.y + 206), 13, U.DIM)

    # ---------- мастерская ----------

    def _stone_card(self, surf, r, item, kind, selected):
        w = self.app.workshop
        U.panel(surf, r, U.PANEL_HI if selected else U.PANEL, U.GOLD if selected else U.EDGE)
        if kind == "rough":
            JV.draw_rough(surf, item, rough_color(w, item), (r.centerx, r.y + 42), 62,
                          t=self.app.clock * 0.35, xd=w.xd)
            name = w.gem_name(item["id"])
            line = f"{item['size']:.2f} ct"
        else:
            JV.draw_gem(surf, item, gem_color(w, item), (r.centerx, r.y + 42), 62,
                        t=self.app.clock * 0.4, xd=w.xd)
            name = w.gem_name(item["id"])
            line = f"{item['size']:.2f} ct · {item['value']} з."
        U.text(surf, U.fit(name, 12, r.w - 12), (r.x + 6, r.y + 80), 12, U.TEXT)
        U.text(surf, line, (r.x + 6, r.y + 98), 11, U.DIM)
        U.text(surf, "камни" if kind == "rough" else "витрина", (r.x + 6, r.y + 114), 10, U.DIM)

    def _draw_workshop(self, surf):
        w = self.app.workshop
        U.text(surf, "Мастерская", (24, CONTENT_Y), 24, U.TEXT, True)
        c = self.client
        if c:
            r = pygame.Rect(24, 180, 1232, 72)
            U.panel(surf, r, U.PANEL, U.EDGE)
            U.text(surf, f"Заказ: {c['name']}", (r.x + 14, r.y + 8), 16, U.GOLD, True)
            U.text(surf, U.fit(c["desc"], 14, r.w - 28), (r.x + 14, r.y + 32), 14, U.TEXT)
        else:
            U.text(surf, "Нет активного клиента — выберите заказ во вкладке «Клиенты».",
                   (24, 188), 15, U.DIM)

        U.text(surf, "Сырьё", (24, 266), 17, U.TEXT, True)
        for i, rough in enumerate(w.inventory[:8]):
            r = pygame.Rect(24 + (i % 4) * 154, 294 + (i // 4) * 148, 144, 134)
            sel = self.selected == ("rough", rough)
            self._stone_card(surf, r, rough, "rough", sel)
            self.hit(r, ("pick_rough", rough))
        if not w.inventory:
            U.text(surf, "Пусто — купите камни во вкладке «Закупка».", (24, 306), 14, U.DIM)

        U.text(surf, "Витрина", (656, 266), 17, U.TEXT, True)
        for i, gem in enumerate(w.display[:8]):
            r = pygame.Rect(656 + (i % 4) * 154, 294 + (i // 4) * 148, 144, 134)
            sel = self.selected == ("gem", gem)
            self._stone_card(surf, r, gem, "gem", sel)
            self.hit(r, ("pick_gem", gem))
        if not w.display:
            U.text(surf, "Пусто — готовые камни появятся здесь.", (656, 306), 14, U.DIM)

        r = pygame.Rect(24, 590, 1232, 90)
        U.panel(surf, r, U.PANEL, U.EDGE)
        if self.selected:
            kind, item = self.selected
            U.text(surf, "Выбрано:", (r.x + 14, r.y + 12), 14, U.DIM)
            if kind == "rough":
                U.text(surf, f"{w.gem_name(item['id'])} · {item['size']:.2f} ct",
                       (r.x + 84, r.y + 10), 17, U.TEXT, True)
                if c:
                    self.button(surf, pygame.Rect(r.right - 230, r.y + 24, 200, 42), "Гранить",
                                "cut", True, U.GREEN)
            else:
                U.text(surf, f"{w.gem_name(item['id'])} · {item['size']:.2f} ct · "
                             f"качество {item['q']:.2f}",
                       (r.x + 84, r.y + 10), 17, U.TEXT, True)
                if c and c["kind"] == "walkin":
                    self.button(surf, pygame.Rect(r.right - 230, r.y + 24, 200, 42), "Продать",
                                "sell", True, U.GREEN)
        else:
            U.text(surf, "Выберите камень или готовый камень на витрине.", (r.x + 14, r.y + 32), 15, U.DIM)
        self.button(surf, pygame.Rect(24, 710, 200, 38), "К клиентам", "back_clients", True, U.BLUE)

    def draw(self, surf):
        self.hits = []
        surf.fill(U.BG)
        self._header(surf)
        if self.tab == "supply":
            self._draw_supply(surf)
        elif self.tab == "clients":
            self._draw_clients(surf)
        else:
            self._draw_workshop(surf)


class CutScene(Scene):
    """Полноценный станок из основной игры."""

    def __init__(self, app, rough, client):
        super().__init__(app)
        w = app.workshop
        known = [client["cut"]] if client.get("cut") in w.known_cuts else w.known_cuts
        self.client = client
        self.rough = rough
        self.cutter = JewelCut(seed=app.seed, rough=rough, known=known, xd=w.xd,
                               lenses=tuple(w.lenses), disks=tuple(w.disks),
                               autofocus=w.autofocus)
        self.rect = pygame.Rect(80, 140, 1120, 520)
        self.gem = None
        self.done_t = 0.0

    def act(self, action):
        if action == "back":
            self.app.workshop.inventory.append(self.rough)
            self.app.switch(HubScene(self.app, tab="workshop"))

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                if self.cutter.can_abort():
                    self.act("back")
                return
            if ev.key == pygame.K_SPACE:
                self.cutter.press()
                return
            self.cutter.key(ev.key)
            return
        if ev.type == pygame.KEYUP and ev.key == pygame.K_SPACE:
            self.cutter.release()
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.cutter.pointer(ev, self.rect):
                return
            self.cutter.click(ev.pos)
            return
        if ev.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP):
            self.cutter.pointer(ev, self.rect)
            return
        if ev.type == pygame.MOUSEWHEEL:
            self.cutter.wheel(ev.y)

    def update(self, dt):
        self.cutter.update(dt)
        if self.cutter.done and self.gem is None:
            self.gem = self.app.workshop.finish_gem(self.rough, self.cutter)
            self.done_t = 0.8
        if self.gem is not None:
            self.done_t -= dt
            if self.done_t <= 0:
                self.app.switch(ResultScene(self.app, self.client, self.gem, None, 0))

    def draw(self, surf):
        surf.fill(U.BG)
        w = self.app.workshop
        U.text(surf, "ОГРАНКА", (24, 18), 28, U.GOLD, True)
        U.text(surf, f"{w.gem_name(self.rough['id'])} · {self.rough['size']:.2f} ct · {self.client['name']}",
               (24, 54), 15, U.TEXT)
        self.cutter.draw(surf, self.rect)
        U.text(surf, "1–9 — огранка · W/S — угол · A/D — индекс · Пробел — к диску · Enter — грань · F — перевернуть",
               (80, 682), 12, U.DIM)
        if self.gem is not None:
            U.text(surf, "Камень готов", (W // 2, 110), 24, U.GREEN, True, True)


class ResultScene(Scene):
    def __init__(self, app, client, gem, status, offer):
        super().__init__(app)
        self.client = client
        self.gem = gem
        self.status = status
        self.offer = offer
        if status is None:
            self.status, self.offer = app.workshop.evaluate(client, gem)

    def _next_scene(self):
        if self.app.workshop.all_clients_done():
            self.app.switch(DayEndScene(self.app))
        else:
            self.app.switch(HubScene(self.app, tab="clients"))

    def act(self, action):
        w = self.app.workshop
        if action == "sell":
            if w.sell(self.client, self.gem, self.offer, self.status):
                self.app.save()
                self._next_scene()
        elif action == "haggle":
            self.offer = w.haggle(self.client, self.offer)
        elif action == "refuse":
            w.refuse(self.client, self.gem)
            self.app.save()
            self._next_scene()

    def draw(self, surf):
        self.hits = []
        w = self.app.workshop
        surf.fill(U.BG)
        U.text(surf, "РЕЗУЛЬТАТ", (24, 18), 28, U.GOLD, True)
        U.text(surf, self.client["name"], (24, 58), 17, U.TEXT)
        r = pygame.Rect(24, 100, 470, 420)
        U.panel(surf, r, U.PANEL, U.EDGE)
        JV.draw_gem(surf, self.gem, gem_color(w, self.gem), (r.centerx, r.y + 170), 190,
                    t=self.app.clock * 0.5, xd=w.xd)
        U.text(surf, w.gem_name(self.gem["id"]), (r.x + 20, r.y + 290), 22, U.TEXT, True)
        U.text(surf, f"{self.gem['size']:.2f} ct · качество {self.gem['q']:.2f}",
               (r.x + 20, r.y + 322), 15, U.DIM)
        U.text(surf, f"Огранка: {w.cut_name(self.gem['cut'])}", (r.x + 20, r.y + 346), 14, U.TEXT)
        U.text(surf, f"Оценка: {self.gem['value']} з.", (r.x + 20, r.y + 370), 16, U.GOLD, True)
        r2 = pygame.Rect(520, 100, 736, 420)
        U.panel(surf, r2, U.PANEL, U.EDGE)
        U.text(surf, "Клиент", (r2.x + 18, r2.y + 16), 18, U.GOLD, True)
        U.text(surf, self.client["desc"], (r2.x + 18, r2.y + 48), 15, U.TEXT)
        U.text(surf, f"Вердикт: {status_ru(self.status)}", (r2.x + 18, r2.y + 96), 20,
               U.GREEN if self.status in ("ok", "discount") else U.RED, True)
        if self.offer:
            U.text(surf, f"Предложение: {self.offer} з.", (r2.x + 18, r2.y + 130), 20, U.GOLD, True)
        else:
            U.text(surf, "Клиент не готов платить за этот камень.", (r2.x + 18, r2.y + 130), 15, U.DIM)
        if self.status in ("ok", "discount") and not self.client.get("haggle_used"):
            self.button(surf, pygame.Rect(r2.x + 18, r2.bottom - 120, 210, 40), "Поторговаться",
                        "haggle", True, U.BLUE)
        if self.status in ("ok", "discount") and self.offer:
            self.button(surf, pygame.Rect(r2.x + 244, r2.bottom - 120, 210, 40),
                        f"Продать за {self.offer}", "sell", True, U.GREEN)
        self.button(surf, pygame.Rect(r2.x + 470, r2.bottom - 120, 210, 40), "Оставить / отказ",
                    "refuse", True, U.RED)


class DayEndScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.report = app.workshop.end_day()
        app.save()

    def act(self, action):
        w = self.app.workshop
        if action == "next":
            w.new_day()
            self.app.save()
            self.app.switch(HubScene(self.app, tab="supply"))
        elif isinstance(action, tuple) and action[0] == "upgrade":
            if w.buy_upgrade(action[1]):
                self.app.save()

    def draw(self, surf):
        self.hits = []
        w = self.app.workshop
        surf.fill(U.BG)
        U.text(surf, "ВЕЧЕР", (24, 18), 28, U.GOLD, True)
        U.text(surf, f"День {w.day} завершён", (24, 58), 17, U.TEXT)
        r = pygame.Rect(24, 100, 500, 300)
        U.panel(surf, r, U.PANEL, U.EDGE)
        rep = self.report
        U.text(surf, f"Аренда: {rep['rent']} з.", (r.x + 18, r.y + 18), 18, U.TEXT, True)
        U.text(surf, f"Оплачено: {rep['paid']} з.", (r.x + 18, r.y + 50), 15, U.DIM)
        if rep["debt_added"]:
            U.text(surf, f"В долг: {rep['debt_added']} з.", (r.x + 18, r.y + 74), 16, U.RED, True)
        U.text(surf, f"Золото: {w.money}", (r.x + 18, r.y + 110), 18, U.GOLD, True)
        U.text(surf, f"Репутация: {w.reputation}", (r.x + 18, r.y + 138), 16, U.GREEN, True)
        if w.debt:
            U.text(surf, f"Общий долг: {w.debt} з.", (r.x + 18, r.y + 166), 16, U.RED, True)
        U.text(surf, "Улучшения", (24, 430), 20, U.TEXT, True)
        opts = w.upgrade_options()
        for i, o in enumerate(opts[:4]):
            r = pygame.Rect(24 + (i % 2) * 610, 466 + (i // 2) * 110, 590, 98)
            U.panel(surf, r, U.PANEL, U.EDGE)
            U.text(surf, o["name"], (r.x + 14, r.y + 10), 17, U.GOLD, True)
            U.text(surf, U.fit(o["desc"], 13, r.w - 28), (r.x + 14, r.y + 36), 13, U.TEXT)
            U.text(surf, f"{o['price']} з.", (r.x + 14, r.y + 66), 15, U.GOLD, True)
            self.button(surf, pygame.Rect(r.right - 120, r.bottom - 34, 104, 26), "Купить",
                        ("upgrade", o["key"]), w.money >= o["price"], small=True)
        self.button(surf, pygame.Rect(W - 280, 720, 256, 44), "Следующий день",
                    "next", True, U.GREEN)


class WorkshopApp:
    def __init__(self, seed=None, fullscreen=True):
        pygame.init()
        pygame.display.set_caption("Грань — ювелирная мастерская")
        self.canvas = pygame.Surface((W, H))
        self.screen = None
        self.fullscreen = bool(fullscreen)
        self.scale = 1.0
        self.offset = (0, 0)
        self._set_display()
        self.clock_obj = pygame.time.Clock()
        self.seed = seed
        self.workshop = Workshop.load() if seed is None else Workshop(seed)
        self.scene = HubScene(self, tab="supply")
        self.running = True
        self.clock_t = 0.0

    @property
    def clock(self):
        return self.clock_t

    def _set_display(self):
        flags = pygame.FULLSCREEN if self.fullscreen else pygame.RESIZABLE
        size = (0, 0) if self.fullscreen else (W, H)
        try:
            self.screen = pygame.display.set_mode(size, flags)
        except pygame.error:
            self.fullscreen = False
            self.screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
        self._update_view()

    def _update_view(self):
        sw, sh = self.screen.get_size()
        self.scale = max(0.1, min(sw / W, sh / H))
        dw, dh = int(W * self.scale), int(H * self.scale)
        self.offset = ((sw - dw) // 2, (sh - dh) // 2)

    def _to_logical(self, pos):
        return (int((pos[0] - self.offset[0]) / self.scale),
                int((pos[1] - self.offset[1]) / self.scale))

    def _map_event(self, ev):
        if ev.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            d = dict(ev.dict)
            d["pos"] = self._to_logical(ev.pos)
            return pygame.event.Event(ev.type, d)
        return ev

    def _present(self):
        self.screen.fill((0, 0, 0))
        dw, dh = int(W * self.scale), int(H * self.scale)
        img = pygame.transform.smoothscale(self.canvas, (dw, dh))
        self.screen.blit(img, self.offset)
        pygame.display.flip()

    def switch(self, scene):
        self.scene = scene

    def save(self):
        self.workshop.save()

    def run(self):
        while self.running:
            dt = self.clock_obj.tick(60) / 1000.0
            self.clock_t += dt
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                    continue
                if ev.type == pygame.KEYDOWN and (
                        ev.key == pygame.K_F11 or
                        (ev.key == pygame.K_RETURN and ev.mod & pygame.KMOD_ALT)):
                    self.fullscreen = not self.fullscreen
                    self._set_display()
                    continue
                if ev.type in (pygame.VIDEORESIZE, pygame.WINDOWRESIZED, pygame.WINDOWSIZECHANGED):
                    self._update_view()
                    continue
                self.scene.handle(self._map_event(ev))
            self.scene.update(dt)
            self.scene.draw(self.canvas)
            self._present()
        self.save()
        pygame.quit()
