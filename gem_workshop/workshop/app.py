"""Прототип «Грань»: бесконечная мастерская, заказы и огранка камней."""
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


def gem_color(w, gem):
    gd = GM.gem_def(w.xd, gem["id"])
    return GM.tint(tuple(gd.get("color", (120, 160, 220))), gem.get("col", 0.5))


def rough_color(w, rough):
    gd = GM.gem_def(w.xd, rough["id"])
    return GM.tint(tuple(gd.get("color", (120, 160, 220))), rough.get("col", 0.5))


def status_ru(status):
    return {"ok": "Принято", "discount": "Со скидкой", "wrong": "Не тот камень",
            "reject": "Отказ", "refused": "Отказ", "skipped": "Пропущен"}.get(status, status)


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


class MarketScene(Scene):
    """Утро: заказы дня, поставщик и лоты."""

    def __init__(self, app):
        super().__init__(app)
        self.stock_rects = []
        self.lot_rects = []

    def draw(self, surf):
        self.hits = []
        w = self.app.workshop
        surf.fill(U.BG)
        U.text(surf, "ГРАНЬ", (24, 18), 30, U.GOLD, True)
        U.text(surf, f"День {w.day}", (176, 26), 18, U.TEXT, True)
        U.text(surf, f"Золото: {w.money}", (W - 300, 20), 20, U.GOLD, True)
        U.text(surf, f"Репутация: {w.reputation}", (W - 300, 46), 15, U.GREEN)
        if w.debt:
            U.text(surf, f"Долг: {w.debt}", (W - 300, 66), 15, U.RED)
        U.text(surf, "Сегодняшние клиенты", (24, 66), 18, U.TEXT, True)
        for i, c in enumerate(w.clients):
            r = pygame.Rect(24 + i * 410, 92, 390, 76)
            U.panel(surf, r, U.PANEL, U.EDGE)
            U.text(surf, c["name"], (r.x + 12, r.y + 8), 16, U.GOLD, True)
            U.text(surf, U.fit(c["desc"], 13, r.w - 24), (r.x + 12, r.y + 31), 13, U.TEXT)
            U.text(surf, f"Бюджет до {c['budget']}", (r.x + 12, r.y + 52), 12, U.DIM)
        U.text(surf, "Поставщик", (24, 184), 18, U.TEXT, True)
        for i, item in enumerate(w.stock):
            col = i % 3
            row = i // 3
            r = pygame.Rect(24 + col * 410, 210 + row * 112, 390, 102)
            U.panel(surf, r)
            rough = item["rough"]
            JV.draw_rough(surf, rough, rough_color(w, rough), (r.x + 48, r.y + 52), 58,
                          t=self.app.clock * 0.4, xd=w.xd)
            U.text(surf, w.gem_name(rough["id"]), (r.x + 92, r.y + 8), 16, U.TEXT, True)
            U.text(surf, f"{rough['size']:.2f} ct · {GM.color_word(w.xd, rough['col'])}",
                   (r.x + 92, r.y + 30), 13, U.DIM)
            U.text(surf, U.fit(GM.describe(w.xd, rough, rough=True)[1], 12, 180),
                   (r.x + 92, r.y + 48), 12, U.TEXT)
            U.text(surf, f"{item['price']} з.", (r.x + 92, r.y + 68), 15, U.GOLD, True)
            self.button(surf, pygame.Rect(r.right - 92, r.bottom - 32, 80, 24), "Купить",
                        ("stock", i), w.money >= item["price"], small=True)
        U.text(surf, "Лоты", (24, 438), 18, U.TEXT, True)
        U.text(surf, "дешевле, но состав менее предсказуем", (100, 442), 13, U.DIM)
        for i, lot in enumerate(w.lots):
            r = pygame.Rect(24 + i * 410, 466, 390, 92)
            U.panel(surf, r, U.PANEL, (110, 80, 50))
            U.text(surf, lot["label"], (r.x + 12, r.y + 8), 17, U.GOLD, True)
            U.text(surf, "камни из каравана · без полной проверки", (r.x + 12, r.y + 32), 13, U.DIM)
            U.text(surf, f"{lot['price']} з.", (r.x + 12, r.y + 57), 16, U.TEXT, True)
            self.button(surf, pygame.Rect(r.right - 92, r.bottom - 32, 80, 24), "Купить",
                        ("lot", i), w.money >= lot["price"], small=True)
        U.text(surf, f"В мастерской: {len(w.inventory)} камней · на витрине: {len(w.display)}",
               (24, 610), 14, U.DIM)
        self.button(surf, pygame.Rect(W - 250, 700, 226, 46), "Открыть мастерскую",
                    "start", True, U.GREEN)
        self.button(surf, pygame.Rect(24, 700, 160, 46), "Сохранить", "save", True, U.BLUE)

    def act(self, action):
        w = self.app.workshop
        if action == "save":
            self.app.save()
        elif action == "start":
            self.app.switch(ShopScene(self.app))
        elif isinstance(action, tuple) and action[0] == "stock":
            if w.buy_stock(action[1]):
                self.app.save()
        elif isinstance(action, tuple) and action[0] == "lot":
            if w.buy_lot(action[1]):
                self.app.save()


class ShopScene(Scene):
    """День: клиенты, инвентарь и витрина."""

    def __init__(self, app):
        super().__init__(app)
        self.ci = 0
        self.selected = None          # ("rough", rough) / ("gem", gem)
        self._fix_client()

    def _fix_client(self):
        w = self.app.workshop
        rem = w.remaining_clients()
        if not rem:
            self.ci = -1
            return
        if not (0 <= self.ci < len(w.clients)) or w.clients[self.ci]["served"]:
            self.ci = w.clients.index(rem[0])

    @property
    def client(self):
        w = self.app.workshop
        if 0 <= self.ci < len(w.clients):
            return w.clients[self.ci]
        return None

    def act(self, action):
        w = self.app.workshop
        if action == "back":
            self.app.switch(MarketScene(self.app))
        elif action == "skip":
            c = self.client
            if c:
                w.skip_client(c)
                self.app.save()
                self._after_client()
        elif isinstance(action, tuple) and action[0] == "client":
            self.ci = action[1]
            self.selected = None
        elif isinstance(action, tuple) and action[0] == "pick_rough":
            self.selected = ("rough", action[1])
        elif isinstance(action, tuple) and action[0] == "pick_gem":
            self.selected = ("gem", action[1])
        elif action == "cut":
            if self.selected and self.selected[0] == "rough" and self.client:
                rough = self.selected[1]
                w.inventory.remove(rough)
                self.app.switch(CutScene(self.app, rough, self.client))
        elif action == "sell":
            if self.selected and self.selected[0] == "gem" and self.client:
                gem = self.selected[1]
                status, offer = w.evaluate(self.client, gem)
                self.app.switch(ResultScene(self.app, self.client, gem, status, offer))
        elif action == "day":
            self._after_client()

    def _after_client(self):
        self._fix_client()
        if self.client is None:
            self.app.switch(DayEndScene(self.app))
        else:
            self.selected = None

    def draw(self, surf):
        self.hits = []
        w = self.app.workshop
        surf.fill(U.BG)
        U.text(surf, "МАСТЕРСКАЯ", (24, 18), 28, U.GOLD, True)
        U.text(surf, f"День {w.day} · золото {w.money} · репутация {w.reputation}",
               (24, 54), 15, U.TEXT)
        if w.debt:
            U.text(surf, f"Долг поставщику: {w.debt}", (24, 74), 14, U.RED)
        U.text(surf, "Клиенты", (24, 96), 17, U.TEXT, True)
        for i, c in enumerate(w.clients):
            r = pygame.Rect(24 + i * 300, 122, 280, 76)
            sel = i == self.ci
            U.panel(surf, r, U.PANEL_HI if sel else U.PANEL, U.GOLD if sel else U.EDGE)
            U.text(surf, c["name"], (r.x + 10, r.y + 8), 15, U.GOLD if sel else U.TEXT, True)
            U.text(surf, status_ru(c["status"]) if c["served"] else U.fit(c["desc"], 12, r.w - 20),
                   (r.x + 10, r.y + 30), 12, U.DIM if c["served"] else U.TEXT)
            self.hit(r, ("client", i))

        c = self.client
        if c is None:
            U.text(surf, "Все клиенты обслужены.", (24, 220), 20, U.DIM)
        else:
            r = pygame.Rect(24, 220, 600, 150)
            U.panel(surf, r, U.PANEL, U.EDGE)
            U.text(surf, c["name"], (r.x + 12, r.y + 10), 20, U.GOLD, True)
            U.text(surf, c["desc"], (r.x + 12, r.y + 40), 14, U.TEXT)
            U.text(surf, f"Бюджет: до {c['budget']} · ", (r.x + 12, r.y + 65), 13, U.DIM)
            U.text(surf, "Заказ" if c["kind"] == "custom" else "Покупатель витрины",
                   (r.x + 12, r.y + 88), 13, U.BLUE)

        U.text(surf, "Камни в мастерской", (24, 390), 16, U.TEXT, True)
        for i, rough in enumerate(w.inventory[:8]):
            r = pygame.Rect(24 + (i % 4) * 148, 416 + (i // 4) * 104, 138, 94)
            sel = self.selected == ("rough", rough)
            U.panel(surf, r, U.PANEL_HI if sel else U.PANEL, U.GOLD if sel else U.EDGE)
            JV.draw_rough(surf, rough, rough_color(w, rough), (r.centerx, r.y + 38), 38,
                          t=self.app.clock * 0.35, xd=w.xd)
            U.text(surf, U.fit(w.gem_name(rough["id"]), 12, 126), (r.x + 6, r.y + 64), 12, U.TEXT)
            U.text(surf, f"{rough['size']:.2f} ct", (r.x + 6, r.y + 80), 11, U.DIM)
            self.hit(r, ("pick_rough", rough))
        U.text(surf, "Витрина", (24, 626), 16, U.TEXT, True)
        for i, gem in enumerate(w.display[:5]):
            r = pygame.Rect(24 + i * 148, 652, 138, 94)
            sel = self.selected == ("gem", gem)
            U.panel(surf, r, U.PANEL_HI if sel else U.PANEL, U.GOLD if sel else U.EDGE)
            JV.draw_gem(surf, gem, gem_color(w, gem), (r.centerx, r.y + 38), 38,
                        t=self.app.clock * 0.4, xd=w.xd)
            U.text(surf, U.fit(w.gem_name(gem["id"]), 12, 126), (r.x + 6, r.y + 64), 12, U.TEXT)
            U.text(surf, f"{gem['size']:.2f} ct · {gem['value']} з.", (r.x + 6, r.y + 80), 11, U.DIM)
            self.hit(r, ("pick_gem", gem))

        # правая панель выбранного
        r = pygame.Rect(720, 220, 536, 440)
        U.panel(surf, r, U.PANEL, U.EDGE)
        if c is not None:
            U.text(surf, "Заказ", (r.x + 16, r.y + 14), 17, U.GOLD, True)
            for k, ln in enumerate(U.wrap(c["desc"], 14, r.w - 32)):
                U.text(surf, ln, (r.x + 16, r.y + 44 + k * 20), 14, U.TEXT)
        if self.selected:
            kind, item = self.selected
            U.text(surf, "Выбрано", (r.x + 16, r.y + 116), 16, U.GOLD, True)
            if kind == "rough":
                rough = item
                JV.draw_rough(surf, rough, rough_color(w, rough), (r.x + 100, r.y + 220), 120,
                              t=self.app.clock * 0.4, xd=w.xd)
                U.text(surf, w.gem_name(rough["id"]), (r.x + 180, r.y + 150), 20, U.TEXT, True)
                U.text(surf, f"{rough['size']:.2f} ct · {GM.color_word(w.xd, rough['col'])}",
                       (r.x + 180, r.y + 180), 14, U.DIM)
                for k, ln in enumerate(GM.describe(w.xd, rough, rough=True)):
                    U.text(surf, U.fit(ln, 13, r.w - 210), (r.x + 180, r.y + 206 + k * 18), 13, U.TEXT)
                self.button(surf, pygame.Rect(r.x + 300, r.bottom - 66, 210, 42), "Гранить",
                            "cut", True, U.GREEN)
            else:
                gem = item
                JV.draw_gem(surf, gem, gem_color(w, gem), (r.x + 100, r.y + 220), 120,
                            t=self.app.clock * 0.4, xd=w.xd)
                U.text(surf, w.gem_name(gem["id"]), (r.x + 180, r.y + 150), 20, U.TEXT, True)
                U.text(surf, f"{gem['size']:.2f} ct · качество {gem['q']:.2f}",
                       (r.x + 180, r.y + 180), 14, U.DIM)
                U.text(surf, f"Огранка: {w.cut_name(gem['cut'])}", (r.x + 180, r.y + 202), 14, U.TEXT)
                U.text(surf, f"Оценка: {gem['value']} з.", (r.x + 180, r.y + 224), 15, U.GOLD, True)
                self.button(surf, pygame.Rect(r.x + 300, r.bottom - 66, 210, 42), "Предложить",
                            "sell", True, U.GREEN)
        self.button(surf, pygame.Rect(24, 740, 160, 38), "В поставку", "back", True, U.BLUE)
        if c is None:
            self.button(surf, pygame.Rect(198, 740, 190, 38), "Завершить день", "day", True, U.GREEN)
        else:
            self.button(surf, pygame.Rect(198, 740, 190, 38), "Пропустить клиента", "skip",
                        True, U.RED, True)


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
            self.app.switch(ShopScene(self.app))

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
            self.app.switch(ShopScene(self.app))

    def act(self, action):
        w = self.app.workshop
        if action == "sell":
            if w.sell(self.client, self.gem, self.offer, self.status):
                self.app.save()
                self._next_scene()
        elif action == "haggle":
            self.offer = w.haggle(self.client, self.offer)
            self.status = "ok" if self.status == "ok" else self.status
        elif action == "refuse":
            w.refuse(self.client, self.gem)
            self.app.save()
            self._next_scene()
        elif action == "keep":
            if self.gem not in w.display:
                w.add_display(self.gem)
            self.client["served"] = True
            self.client["status"] = "refused"
            w.reputation = max(-20, w.reputation - 1)
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
        if action == "save":
            self.app.save()
        elif action == "next":
            w.new_day()
            self.app.save()
            self.app.switch(MarketScene(self.app))
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
        self.button(surf, pygame.Rect(24, 720, 160, 44), "Сохранить", "save", True, U.BLUE)

    def act(self, action):
        w = self.app.workshop
        if action == "save":
            self.app.save()
        elif action == "next":
            w.new_day()
            self.app.save()
            self.app.switch(MarketScene(self.app))
        elif isinstance(action, tuple) and action[0] == "upgrade":
            if w.buy_upgrade(action[1]):
                self.app.save()


class WorkshopApp:
    def __init__(self, seed=None):
        pygame.init()
        pygame.display.set_caption("Грань — ювелирная мастерская")
        self.screen = pygame.display.set_mode((W, H))
        self.clock_obj = pygame.time.Clock()
        self.seed = seed
        self.workshop = Workshop.load() if seed is None else Workshop(seed)
        self.scene = MarketScene(self)
        self.running = True
        self.clock_t = 0.0

    @property
    def clock(self):
        return self.clock_t

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
                else:
                    self.scene.handle(ev)
            self.scene.update(dt)
            self.scene.draw(self.screen)
            pygame.display.flip()
        self.save()
        pygame.quit()
