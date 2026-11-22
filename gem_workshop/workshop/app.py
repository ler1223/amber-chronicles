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
from ui import illustrations as IL
from . import ui as U
from . import optics as OPT
from . import surface as SURF
from . import marks as MK
from . import apprentice as AP
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

    def __init__(self, app, tab="hub", client=None):
        super().__init__(app)
        self.tab = tab
        self.client = client
        self.selected = None          # ("rough", rough) / ("gem", gem)
        self.page = 0                 # страница сырья в мастерской
        self._fix_client()

    def _fix_client(self):
        w = self.app.workshop
        rem = w.remaining_clients()
        if self.client is not None and self.client in rem:
            return
        self.client = rem[0] if rem else None

    def _header(self, surf):
        w = self.app.workshop
        if self.tab == "hub":
            U.text(surf, "ГРАНЬ", (24, 18), 30, U.GOLD, True)
            U.text(surf, f"День {w.day}", (178, 26), 18, U.TEXT, True)
        else:
            self.button(surf, pygame.Rect(24, 18, 92, 34), "Назад", ("tab", "hub"), True, U.BLUE, True)
            title = {"clients": "Клиенты", "supply": "Закупка", "workshop": "Мастерская"}.get(self.tab, "")
            U.text(surf, title, (132, 20), 28, U.GOLD, True)
        U.text(surf, f"Золото: {w.money}", (W - 310, 20), 20, U.GOLD, True)
        U.text(surf, f"Репутация: {w.reputation}", (W - 310, 46), 15, U.GREEN)
        if w.debt:
            U.text(surf, f"Долг: {w.debt}", (W - 310, 66), 15, U.RED)

    def _dock(self, surf):
        tabs = (("clients", "Клиенты", "npc_jeweler"),
                ("supply", "Закупка", "barrel_big"),
                ("workshop", "Мастерская", "facet_loupe"))
        x = 24
        for key, label, icon in tabs:
            r = pygame.Rect(x, 724, 200, 54)
            active = self.tab == key
            U.panel(surf, r, U.PANEL_HI if active else U.PANEL, U.GOLD if active else U.EDGE, 2, 9)
            ic = sprite(icon, 34)
            if ic:
                surf.blit(ic, (r.x + 10, r.y + 10))
            U.text(surf, label, (r.x + 54, r.y + 16), 17, U.TEXT if active else U.DIM, True)
            self.hit(r, ("tab", key))
            x += 212

    def _draw_hub(self, surf):
        w = self.app.workshop
        bg = IL.get("ws_bench_jewel", "tavern", (W, H), hd=True)
        surf.blit(bg, (0, 0))
        shade = pygame.Surface((W, H), pygame.SRCALPHA)
        shade.fill((8, 6, 4, 165))
        surf.blit(shade, (0, 0))
        U.text(surf, "Мастерская «Грань»", (24, 68), 22, U.TEXT, True)
        U.text(surf, "Выберите, чем заняться сегодня", (24, 98), 14, U.DIM)
        stations = (
            ("clients", "Клиенты", "npc_jeweler", "Заказы, витрина и торг", len(w.remaining_clients())),
            ("supply", "Закупка", "barrel_big", "Мешочки с сырьём", len(w.lots)),
            ("workshop", "Мастерская", "facet_loupe", "Сырьё, огранка и витрина", len(w.inventory)),
        )
        for i, (key, label, icon, desc, count) in enumerate(stations):
            r = pygame.Rect(60 + i * 400, 250, 360, 330)
            hot = r.collidepoint(self.mouse)
            U.panel(surf, r, U.PANEL_HI if hot else U.PANEL, U.GOLD if hot else U.EDGE, 2, 12)
            img = sprite(icon, 130, 150 if key == "clients" else 130)
            if img:
                surf.blit(img, (r.centerx - img.get_width() // 2, r.y + 24))
            U.text(surf, label, (r.centerx, r.y + 190), 25, U.GOLD, True, True)
            U.text(surf, desc, (r.centerx, r.y + 226), 14, U.TEXT, False, True)
            U.text(surf, f"{count}", (r.centerx, r.y + 262), 28, U.GREEN, True, True)
            self.hit(r, ("tab", key))
        self._draw_master(surf, pygame.Rect(60, 596, 1160, 116))

    def _draw_master(self, surf, r):
        """Мастер: урок дня в ученичестве; потом — шкаф с его образцами."""
        w = self.app.workshop
        les = w.lesson()
        if les is None and w.retired_note and not w.samples:
            return
        U.panel(surf, r, (38, 30, 24), U.GOLD if les else U.EDGE, 2, 10)
        portrait = sprite("npc_jeweler", 70, 92)
        if portrait:
            surf.blit(portrait, (r.x + 12, r.y + 12))
        x = r.x + 96
        if les is not None:
            U.text(surf, f"Мастер · {les['title']}", (x, r.y + 10), 17, U.GOLD, True)
            for k, ln in enumerate(U.wrap(les["text"], 13, r.w - 400)[:4]):
                U.text(surf, ln, (x, r.y + 36 + k * 18), 13, U.TEXT)
            if les["stones"] and not w.lesson_given:
                self.button(surf, pygame.Rect(r.right - 280, r.y + 16, 260, 38), "Взять камни мастера",
                            "lesson", True, U.GREEN, True)
            elif les["stones"]:
                U.text(surf, "Камни у вас в мастерской", (r.right - 280, r.y + 26), 13, U.DIM)
        elif not w.retired_note:
            U.text(surf, "Мастер ушёл на покой", (x, r.y + 10), 17, U.GOLD, True)
            for k, ln in enumerate(U.wrap(AP.RETIRE_TEXT, 13, r.w - 400)[:4]):
                U.text(surf, ln, (x, r.y + 36 + k * 18), 13, U.TEXT)
            self.button(surf, pygame.Rect(r.right - 280, r.y + 16, 260, 38), "Понятно", "retired_ok",
                        True, U.BLUE, True)
        else:
            U.text(surf, "Шкаф мастера", (x, r.y + 10), 17, U.GOLD, True)
            U.text(surf, "Его учебные камни с ответами: сравните с ними то, что видите в новом сырье.",
                   (x, r.y + 38), 13, U.TEXT)
        if w.samples:
            self.button(surf, pygame.Rect(r.right - 280, r.y + 64, 260, 38), f"Образцы мастера ({len(w.samples)})",
                        "samples", True, U.BLUE, True)

    def act(self, action):
        w = self.app.workshop
        if isinstance(action, tuple) and action[0] == "tab":
            self.tab = action[1]
            self.selected = None
            self._fix_client()
            return
        if action == "lesson":
            if w.take_lesson_stones():
                self.app.save()
            self.tab = "workshop"
            return
        if action == "retired_ok":
            w.retired_note = True
            self.app.save()
            return
        if action == "samples" and w.samples:
            self.app.switch(InspectScene(self.app, w.samples, 0, "sample", -1,
                                         back=lambda: self.app.switch(HubScene(self.app, tab="hub"))))
            return
        if self.tab == "supply":
            if isinstance(action, tuple) and action[0] == "stock":
                if w.buy_stock(action[1]):
                    self.app.save()
            elif isinstance(action, tuple) and action[0] == "lot":
                if w.buy_lot(action[1]):
                    self.app.save()
            elif isinstance(action, tuple) and action[0] == "inspect_stock":
                i = action[1]
                if 0 <= i < len(w.stock):
                    item = w.stock[i]
                    self.app.switch(InspectScene(self.app, [item["rough"]], item["price"], "stock", i))
            elif isinstance(action, tuple) and action[0] == "inspect_lot":
                i = action[1]
                if 0 <= i < len(w.lots):
                    lot = w.lots[i]
                    self.app.switch(InspectScene(self.app, lot["stones"], lot["price"], "lot", i))
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
            elif isinstance(action, tuple) and action[0] == "page":
                self.page = max(0, self.page + action[1])
            elif action == "scrap" and self.selected and self.selected[0] == "rough":
                got = w.sell_scrap(self.selected[1])
                if got:
                    self.app.save()
                self.selected = None
            elif isinstance(action, tuple) and action[0] == "inspect_rough":
                rough = action[1]
                self.app.switch(InspectScene(self.app, [rough], w.rough_market_value(rough), "rough", -1,
                                             back=lambda: self.app.switch(HubScene(self.app, tab="workshop"))))
            elif isinstance(action, tuple) and action[0] == "inspect_gem":
                gem = action[1]
                self.app.switch(InspectScene(self.app, [gem], gem.get("value", 0), "gem", -1,
                                             back=lambda: self.app.switch(HubScene(self.app, tab="workshop"))))

    def key(self, k):
        if k == pygame.K_ESCAPE and self.tab != "hub":
            self.tab = "hub"
            self.selected = None
        elif k in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.tab = ("clients", "supply", "workshop")[k - pygame.K_1]
            self.selected = None
            self._fix_client()

    # ---------- закупка ----------

    def _draw_supply(self, surf):
        w = self.app.workshop
        U.text(surf, "Мешочки с сырьём", (24, CONTENT_Y), 20, U.TEXT, True)
        U.text(surf, "Продают только партией: высыпьте на стол, осмотрите каждый кусок — и решайте. "
                     "Цена — по виду; что внутри, продавец не знает.", (24, CONTENT_Y + 26), 13, U.DIM)
        for i, lot in enumerate(w.lots):
            r = pygame.Rect(24 + (i % 2) * 622, 190 + (i // 2) * 262, 610, 250)
            U.panel(surf, r, U.PANEL, (110, 80, 50))
            U.text(surf, lot["label"], (r.x + 16, r.y + 12), 18, U.GOLD, True)
            U.text(surf, lot.get("desc", f"{len(lot['stones'])} кусков"), (r.x + 16, r.y + 38), 13, U.DIM)
            for k, st in enumerate(lot["stones"][:8]):
                cell = pygame.Rect(r.x + 14 + k * 73, r.y + 64, 68, 108)
                pygame.draw.rect(surf, (20, 17, 15), cell, border_radius=6)
                surf.blit(JV.rough_thumb(st, rough_color(w, st), 64, w.xd), (cell.x + 2, cell.y + 4))
                U.text(surf, U.fit(w.gem_name(st["id"]), 11, 66), (cell.x + 3, cell.y + 70), 11, U.TEXT)
                U.text(surf, f"{st['size']:.2f} ct", (cell.x + 3, cell.y + 86), 10, U.DIM)
            U.text(surf, f"{lot['price']} з.", (r.x + 16, r.bottom - 52), 22, U.GOLD, True)
            self.button(surf, pygame.Rect(r.right - 400, r.bottom - 50, 210, 36), "Высыпать на стол",
                        ("inspect_lot", i), True, U.BLUE, True)
            self.button(surf, pygame.Rect(r.right - 180, r.bottom - 50, 164, 36), "Купить партию",
                        ("lot", i), w.money >= lot["price"], small=True)
        if not w.lots:
            U.text(surf, "Сегодня мешочков больше нет — приходите завтра.", (24, 220), 16, U.DIM)
        U.text(surf, f"В мастерской: {len(w.inventory)} кусков · на витрине: {len(w.display)}",
               (W - 420, CONTENT_Y + 4), 14, U.DIM)

    # ---------- клиенты ----------

    def _draw_clients(self, surf):
        w = self.app.workshop
        rem = w.remaining_clients()
        U.text(surf, "Выберите заказ, затем перейдите в мастерскую", (24, CONTENT_Y), 14, U.DIM)
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
            line = f"{item['size']:.2f} ct · {GM.shape_name(item)}"
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
        c = self.client
        if c:
            r = pygame.Rect(24, 180, 1232, 72)
            U.panel(surf, r, U.PANEL, U.EDGE)
            U.text(surf, f"Заказ: {c['name']}", (r.x + 14, r.y + 8), 16, U.GOLD, True)
            U.text(surf, U.fit(c["desc"], 14, r.w - 28), (r.x + 14, r.y + 32), 14, U.TEXT)
        else:
            U.text(surf, "Нет активного клиента — выберите заказ во вкладке «Клиенты».",
                   (24, 188), 15, U.DIM)

        pages = max(1, (len(w.inventory) + 7) // 8)
        self.page = min(self.page, pages - 1)
        U.text(surf, f"Сырьё · {len(w.inventory)}", (24, 266), 17, U.TEXT, True)
        if pages > 1:
            self.button(surf, pygame.Rect(470, 262, 40, 26), "‹", ("page", -1), self.page > 0, U.BLUE, True)
            U.text(surf, f"{self.page + 1}/{pages}", (518, 266), 14, U.DIM)
            self.button(surf, pygame.Rect(566, 262, 40, 26), "›", ("page", 1), self.page < pages - 1, U.BLUE, True)
        for i, rough in enumerate(w.inventory[self.page * 8:self.page * 8 + 8]):
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
                self.button(surf, pygame.Rect(r.right - 444, r.y + 24, 200, 42), "Осмотр",
                            ("inspect_rough", item), True, U.BLUE)
                cost = f"куплен за ≈{item['cost']} з. · " if item.get("cost") else ""
                U.text(surf, U.fit(cost + MK.summary(item), 13, 470), (r.x + 84, r.y + 40), 13, U.DIM)
                U.text(surf, "в осмотре — метки и окошко", (r.x + 84, r.y + 60), 12, U.DIM)
                self.button(surf, pygame.Rect(r.right - 664, r.y + 24, 200, 42),
                            f"Скупщику · {w.scrap_price(item)} з.", "scrap", True, U.RED, True)
                if c:
                    self.button(surf, pygame.Rect(r.right - 230, r.y + 24, 200, 42), "Гранить",
                                "cut", True, U.GREEN)
            else:
                U.text(surf, f"{w.gem_name(item['id'])} · {item['size']:.2f} ct · "
                             f"качество {item['q']:.2f}",
                       (r.x + 84, r.y + 10), 17, U.TEXT, True)
                self.button(surf, pygame.Rect(r.right - 444, r.y + 24, 200, 42), "Осмотр",
                            ("inspect_gem", item), True, U.BLUE)
                if c and c["kind"] == "walkin":
                    self.button(surf, pygame.Rect(r.right - 230, r.y + 24, 200, 42), "Продать",
                                "sell", True, U.GREEN)
        else:
            U.text(surf, "Выберите камень или готовый камень на витрине.", (r.x + 14, r.y + 32), 15, U.DIM)

    def draw(self, surf):
        self.hits = []
        surf.fill(U.BG)
        if self.tab == "hub":
            self._draw_hub(surf)
        else:
            surf.fill(U.BG)
            self._header(surf)
            if self.tab == "supply":
                self._draw_supply(surf)
            elif self.tab == "clients":
                self._draw_clients(surf)
            else:
                self._draw_workshop(surf)
        self._header(surf) if self.tab == "hub" else None
        self._dock(surf)


class InspectScene(Scene):
    """Осмотр камня: вращение мышью, колесо — приближение, фонарик.

    У сырья — метки игрока (ПКМ: прогноз «что тут внутри») и, у своего камня, окошко:
    маленькая полированная площадка, сквозь которую нутро видно без корки.
    Правды о включениях в тексте нет — её показывает только сам камень."""

    def __init__(self, app, stones, price, kind, index, back=None):
        super().__init__(app)
        self.stones = list(stones)
        self.i = 0
        self.price = int(price)
        self.base_price = int(price)
        self.kind = kind
        self.index = index
        self.back = back
        self.can_buy = kind in ("stock", "lot")
        self.insp = JV.Inspector()
        self.flash_on = False
        self.flash_xy = (0.5, 0.5)
        self.flash_mode = "back"        # back | front | grazing
        self.tool = None                # тип метки или "window"
        self.note = ""
        self.owned = kind == "rough"    # свой камень: можно открыть окошко
        self.show_truth = False         # «Ответ мастера» — у учебных камней и образцов

    @property
    def stone(self):
        return self.stones[self.i]

    def view_rect(self):
        return pygame.Rect(24, 104, 750, 560)

    def act(self, action):
        w = self.app.workshop
        if action == "back":
            if self.back:
                self.back()
            else:
                self.app.switch(HubScene(self.app, tab="supply"))
        elif action == "buy" and self.can_buy:
            ok = w.buy_stock(self.index) if self.kind == "stock" else w.buy_lot(self.index)
            if ok:
                self.app.save()
                self.app.switch(HubScene(self.app, tab="supply"))
        elif action == "flash":
            self.flash_on = not self.flash_on
        elif isinstance(action, tuple) and action[0] == "mode":
            self.flash_mode = action[1]
        elif action == "truth":
            self.show_truth = not self.show_truth
        elif isinstance(action, tuple) and action[0] == "tool":
            self.tool = None if self.tool == action[1] else action[1]
        elif isinstance(action, tuple) and action[0] == "pick":
            if action[1] != self.i:
                self.i = action[1]
                self.insp = JV.Inspector()
                self.flash_xy = (0.5, 0.5)
                self.note = ""
        elif isinstance(action, tuple) and action[0] == "step":
            self.i = (self.i + action[1]) % max(1, len(self.stones))
            self.insp = JV.Inspector()
            self.flash_xy = (0.5, 0.5)

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.act("back")
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_f:
            self.flash_on = not self.flash_on
            return
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_LEFT, pygame.K_RIGHT) and len(self.stones) > 1:
            self.act(("pick", (self.i + (1 if ev.key == pygame.K_RIGHT else -1)) % len(self.stones)))
            return
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.flash_mode = {pygame.K_1: "back", pygame.K_2: "front", pygame.K_3: "grazing"}[ev.key]
            self.flash_on = True
            return
        if ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and ev.button not in (1, 3):
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3 and self.view_rect().collidepoint(ev.pos):
            self._right_click(ev.pos)
            return
        if ev.type == pygame.MOUSEMOTION and self.flash_on:
            r = self.view_rect()
            self.flash_xy = (max(0.0, min(1.0, (ev.pos[0] - r.x) / max(1, r.w))),
                             max(0.0, min(1.0, (ev.pos[1] - r.y) / max(1, r.h))))
        if self.insp.pointer(ev, self.view_rect()):
            return
        super().handle(ev)

    def update(self, dt):
        self.insp.update(dt)

    # ---------- метки и окошко ----------

    def _is_rough(self):
        return "q" not in self.stone

    def _geom(self):
        faces = JV.stone_faces(self.stone)
        return faces, JV.mm_per_unit(self.stone, faces, self.app.workshop.xd)

    def _save(self):
        if hasattr(self.app, "save"):
            self.app.save()

    def _right_click(self, pos):
        self.mouse = pos
        if not self._is_rough():
            return
        stone = self.stone
        faces, mm = self._geom()
        view = self.view_rect()
        if self.tool == "saw":
            if not self.owned:
                return
            plane = MK.saw_plane(self.insp, view, faces, mm, pos)
            pieces = MK.saw_split(stone, plane) if plane else None
            if not pieces:
                self.note = "Так не распилить: один из кусков выходит слишком маленьким."
                return
            self.app.workshop.saw(stone, pieces)
            self.stones[self.i:self.i + 1] = pieces
            self.price = int(self.app.workshop.rough_market_value(self.stone))
            self.note = (f"Распилено: {pieces[0]['size']:.2f} + {pieces[1]['size']:.2f} ct. "
                         f"Куски на столе снизу.")
            self.tool = None
            self._save()
            return
        if self.tool == "window":
            if not self.owned:
                return
            if MK.window_count(stone) >= MK.MAX_WINDOWS:
                self.note = "Больше окошек не открыть — камень и так теряет массу."
                return
            ray = MK.pick(self.insp, view, faces, mm, pos)
            if ray is None:
                return
            loss = MK.add_window(stone, ray)
            self.price = int(self.app.workshop.rough_market_value(stone))
            self.note = f"Окошко открыто: −{loss * 100:.1f}% массы. Посмотрите сквозь него с фонариком."
            if MK.window_count(stone) >= MK.MAX_WINDOWS:
                self.tool = None
            self._save()
            return
        m = MK.mark_at(self.insp, view, mm, stone, pos)
        if m is not None:
            stone["marks"].remove(m)
            self.note = "Метка убрана."
            self._save()
            return
        if self.tool is None:
            self.note = "Выберите тип метки справа, затем ПКМ по камню."
            return
        ray = MK.pick(self.insp, view, faces, mm, pos)
        if ray is None:
            return
        MK.add_mark(stone, self.tool, ray)
        self.note = f"Метка: {MK.KIND[self.tool][0].lower()}. Это прогноз — проверит сам камень."
        self._save()

    def _draw_marks(self, surf, mm):
        view = self.view_rect()
        clip = surf.get_clip()
        surf.set_clip(view)
        for m in self.stone.get("marks") or []:
            label, short, col = MK.KIND.get(m["k"], (m["k"], "?", (200, 200, 200)))
            a = MK.project(self.insp, view, mm, m["a"])
            b = MK.project(self.insp, view, mm, m["b"])
            if math.hypot(a[0] - b[0], a[1] - b[1]) > 6:      # повернули — видно, что метка — луч взгляда
                JV.dashed(surf, a, b, tuple(v // 2 for v in col), 1, 12)
            pos = MK.project(self.insp, view, mm, MK.mid(m))
            JV._mark_icon(surf, (int(pos[0]), int(pos[1])), short, col)
        surf.set_clip(clip)

    def _has_answer(self):
        return bool(self.stone.get("lesson") or self.stone.get("sample"))

    def _draw_truth(self, surf, mm):
        """Ответ мастера: настоящие включения поверх камня."""
        view = self.view_rect()
        scale = MK.view_scale(view, self.insp.zoom, mm)
        names = GM.cfg(self.app.workshop.xd)["incl_kinds"]
        clip = surf.get_clip()
        surf.set_clip(view)
        for inc in JV.rough_incl(self.stone):
            if inc["k"] == "silk":
                U.text(surf, "шёлк — по всему камню", (view.x + 14, view.y + 12), 14, (180, 210, 255), True)
                continue
            x, y = MK.project(self.insp, view, mm, inc["p"])
            rr = max(5, int(inc["r"] * scale))
            col = MK.KIND.get(MK.CATEGORY_KIND.get(inc["k"], ""), ("", "", (240, 240, 240)))[2]
            pygame.draw.circle(surf, col, (int(x), int(y)), rr, 2)
            U.text(surf, names.get(inc["k"], {}).get("name", inc["k"]), (int(x + rr + 4), int(y - 8)), 13, col, True,
                   shadow=True)
        surf.set_clip(clip)

    def _draw_mark_panel(self, surf, r, y):
        """Палитра меток и окошко. → новая y."""
        U.text(surf, "Метки — ваш прогноз", (r.x + 18, y), 14, U.GOLD, True)
        U.text(surf, "ПКМ — поставить · ПКМ по метке — убрать", (r.x + 200, y + 3), 11, U.DIM)
        y += 22
        for i, (k, label, short, col) in enumerate(MK.KINDS):
            br = pygame.Rect(r.x + 18 + (i % 4) * 106, y + (i // 4) * 28, 102, 24)
            self.button(surf, br, label, ("tool", k), True, col if self.tool == k else U.EDGE, True)
        y += 58
        if self.owned:
            left = MK.MAX_WINDOWS - MK.window_count(self.stone)
            self.button(surf, pygame.Rect(r.x + 18, y, 170, 26), f"Окошко (ещё {left})", ("tool", "window"),
                        left > 0, U.GOLD if self.tool == "window" else U.BLUE, True)
            self.button(surf, pygame.Rect(r.x + 196, y, 110, 26), "Пила", ("tool", "saw"),
                        True, U.GOLD if self.tool == "saw" else U.BLUE, True)
            hint = {"window": "ПКМ — сошлифовать площадку", "saw": "ПКМ — пилить"}.get(self.tool, "")
            U.text(surf, hint, (r.x + 314, y + 7), 11, U.DIM)
            y += 32
        U.text(surf, U.fit(MK.summary(self.stone), 13, r.w - 36), (r.x + 18, y), 13, U.TEXT)
        y += 20
        if self.note:
            for part in U.wrap(self.note, 12, r.w - 36)[:2]:
                U.text(surf, part, (r.x + 18, y), 12, U.GREEN)
                y += 16
        if self._has_answer():
            self.button(surf, pygame.Rect(r.x + 18, y + 2, 200, 26),
                        "Скрыть ответ" if self.show_truth else "Ответ мастера", "truth", True, U.GOLD, True)
            y += 34
            if self.show_truth:
                rev = MK.review(self.stone, self.app.workshop.xd)
                if rev and rev["marked"]:
                    U.text(surf, f"ваши метки: верно {rev['hits']} · ошибок {rev['misses']}", (r.x + 18, y), 13,
                           U.GOLD)
                    y += 18
                    for _, txt, col in rev["items"][:5]:
                        U.text(surf, U.fit(txt, 12, r.w - 36), (r.x + 18, y), 12, col)
                        y += 16
                else:
                    U.text(surf, "меток нет — сравните ответ с тем, что видите", (r.x + 18, y), 12, U.DIM)
                    y += 16
        return y + 8

    def _surface_for(self, rough):
        return SURF.for_stone(self.stone, rough=rough, cleaned=True)

    def _light_for(self, faces, mm):
        """Фонарик в мировых координатах, затем перевод в оси камня.

        Положение луча берётся из курсора, а не из экранного пятна: при
        повороте камня луч остаётся мировым и меняет то, что освещает.
        """
        view = self.view_rect()
        far = max((math.sqrt(p[0] * p[0] + p[1] * p[1] + p[2] * p[2])
                   for f in faces for p in f["pts"]), default=100.0)
        px_mm = min(view.w, view.h) / 12.0 * self.insp.zoom
        scale = max(1e-4, px_mm * mm)
        cx = view.x + self.flash_xy[0] * view.w
        cy = view.y + self.flash_xy[1] * view.h
        wx = (cx - view.centerx) / scale
        wy = (cy - view.centery) / scale
        z = far * 3.6 + 60.0
        back_z = far * 1.10 + 8.0
        mode = self.flash_mode
        # Матовая корка глушит свет, сквозь блестящие грани он проходит почти весь:
        # сила фонарика — по облику поверхности, а не по «сырьё/огранка».
        matte = "q" not in self.stone and JV.rough_style(self.stone) == "pebble"
        if mode == "back":
            # Фонарик прислонён к задней грани: свет входит в камень
            # локально, преломляется и идёт внутрь, а не светит издалека.
            pos = (wx * 0.30, wy * 0.30, -back_z)
            target = (wx * 0.08, wy * 0.08, 0.0)
            cone = 32.0
            intensity = 1.3 if matte else 0.40
            env = 1.15 if matte else 1.02
        elif mode == "grazing":
            pos = (wx - far * 1.55, wy - far * 0.55, z * 0.55)
            target = (wx, wy, 0.0)
            cone, intensity, env = 14.0, (1.6 if matte else 0.9), 0.82
        else:
            pos = (wx, wy, z)
            target = (wx, wy, 0.0)
            cone, intensity, env = 10.0, (1.8 if matte else 0.8), 0.90
        dx, dy, dz = target[0] - pos[0], target[1] - pos[1], target[2] - pos[2]
        ln = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        direction = (dx / ln, dy / ln, dz / ln)
        # Мир → камень. Направление — без переноса, только поворот.
        p_obj = self.insp.to_stone(pos)
        d_obj = self.insp.to_stone(direction)
        return {
            "on": bool(self.flash_on),
            "pos": p_obj,
            "dir": d_obj,
            "color": (1.0, 0.95, 0.88),         # нейтрально-белый, как осветитель геммолога
            "intensity": intensity,
            "cone": cone,
            "soft": 0.018,
            "ref": back_z if mode == "back" else z,
        }, env

    def _draw_flashlight(self, surf):
        """Только прицел луча. Сам свет рисует трассировщик, а не этот спрайт."""
        r = self.view_rect()
        cx = int(r.x + self.flash_xy[0] * r.w)
        cy = int(r.y + self.flash_xy[1] * r.h)
        pygame.draw.circle(surf, (235, 205, 145), (cx, cy), 12, 1)
        pygame.draw.circle(surf, (120, 95, 60), (cx, cy), 3, 1)
        mode = {"back": "сзади", "front": "прямой", "grazing": "боковой"}.get(self.flash_mode, self.flash_mode)
        U.text(surf, mode, (cx + 16, cy - 7), 11, U.DIM)

    def draw(self, surf):
        self.hits = []
        w = self.app.workshop
        surf.fill(U.BG)
        rough = "q" not in self.stone
        title = {"lot": "НА СТОЛЕ", "sample": "ОБРАЗЦЫ МАСТЕРА"}.get(self.kind, "ОСМОТР" if rough else "ОСМОТР КАМНЯ")
        U.text(surf, title, (24, 18), 28, U.GOLD, True)
        if self.kind == "lot":
            U.text(surf, f"{len(self.stones)} кусков · {self.i + 1}-й: {w.gem_name(self.stone['id'])}, "
                         f"{self.stone['size']:.2f} ct · клик по столу или стрелки",
                   (240, 26), 15, U.DIM)
        else:
            U.text(surf, f"{w.gem_name(self.stone['id'])} · {self.stone['size']:.2f} ct",
                   (340, 26), 15, U.DIM)
        faces = JV.stone_faces(self.stone)
        profile = OPT.profile(self.stone["id"])
        color = rough_color(w, self.stone) if rough else gem_color(w, self.stone)
        # Включения передаются всегда: их видимость теперь решает свет,
        # а не переключатель «показать/скрыть» в интерфейсе.
        incl = JV.rough_incl(self.stone) if rough else self.stone.get("incl")
        cfield = JV.gem_cfield(self.stone, faces) if rough else JV.gem_cfield(self.stone)
        absorb = OPT.absorption(self.stone["id"], color)
        transparency = profile["transparency"]
        surface = self._surface_for(rough)
        surface["pleo"] = OPT.pleo_value(self.stone["id"])
        # Двупреломление дорого в два прохода; у сырья оно всё равно
        # маскируется коркой и рассеянием, поэтому включаем его для огранки.
        surface["biref"] = 0.0 if rough else OPT.biref_value(self.stone["id"])
        # У сырья ось кристалла — ось его призмы: по ней идут штриховка, зоны и шёлк.
        caxis = JV.ROUGH_CAXIS if rough else self.stone.get("axis")
        surface["opaxis"] = caxis or (0.0, 0.0, 1.0)
        if rough:
            surface.update(JV.rough_look(self.stone))       # скругление, налёт, порода
        light, env = self._light_for(faces, JV.mm_per_unit(self.stone, faces, w.xd))
        mm = JV.mm_per_unit(self.stone, faces, w.xd)
        flash = (self.flash_xy[0], self.flash_xy[1], 1.0 if self.flash_on else 0.0)
        self.insp.draw(surf, self.view_rect(), faces, color, self.app.clock,
                       mm=mm, incl=incl, cfield=cfield,
                       star=0.0 if rough else self.stone.get("star", 0.0),
                       axis=caxis,
                       ior=profile["ior"], absorb=absorb,
                       transparency=transparency, flash=flash,
                       light=light, surface=surface, env=env)
        if rough:
            self._draw_marks(surf, mm)
            if self.show_truth and self._has_answer():
                self._draw_truth(surf, mm)
            if self.tool == "saw" and self.view_rect().collidepoint(self.mouse):
                v = self.view_rect()               # пила идёт вертикально через курсор
                JV.dashed(surf, (self.mouse[0], v.y + 8), (self.mouse[0], v.bottom - 8), (240, 120, 90), 2, 30)
        if self.flash_on:
            self._draw_flashlight(surf)
        r = pygame.Rect(800, 104, 456, 560)
        U.panel(surf, r, U.PANEL, U.EDGE)
        U.text(surf, w.gem_name(self.stone["id"]), (r.x + 18, r.y + 16), 23, U.GOLD, True)
        form_line = f" · {GM.shape_name(self.stone)}" if rough else ""
        U.text(surf, f"{self.stone['size']:.2f} карат · {GM.color_word(w.xd, self.stone['col'])}{form_line}",
               (r.x + 18, r.y + 50), 14, U.TEXT)
        y = r.y + 80
        if rough:
            # Только то, что видно снаружи. Что внутри — решает игрок по фонарику и окошку.
            y = self._draw_mark_panel(surf, r, y)
        else:
            desc = GM.describe(w.xd, self.stone, rough=rough)
            if not self.flash_on:
                desc = desc[:1] + ["Включения и чистота скрыты — включите фонарик."]
            for ln in desc:
                for part in U.wrap(ln, 14, r.w - 36):
                    U.text(surf, part, (r.x + 18, y), 14, U.TEXT if self.flash_on else U.DIM)
                    y += 20
            y += 6
        if not (rough and self.show_truth):          # с ответом мастера — место под разбор
            U.text(surf, "Оптика", (r.x + 18, y), 14, U.GOLD, True)
            y += 20
            for ln in OPT.optics_text(self.stone["id"]):
                for part in U.wrap(ln, 13, r.w - 36):
                    U.text(surf, part, (r.x + 18, y), 13, U.DIM)
                    y += 18
        if not rough:
            y += 6
            U.text(surf, "Поверхность", (r.x + 18, y), 14, U.GOLD, True)
            y += 20
            for ln in SURF.diagnosis(surface, rough):
                for part in U.wrap(ln, 12, r.w - 36):
                    U.text(surf, part, (r.x + 18, y), 12, U.DIM)
                    y += 16
        y += 6
        if self.kind == "sample":
            U.text(surf, "Образец мастера: ответ известен", (r.x + 18, y), 16, U.GOLD, True)
        else:
            label = "Цена партии" if self.kind == "lot" else ("Цена" if self.can_buy else "Оценка по виду")
            U.text(surf, f"{label}: {self.price} з.", (r.x + 18, y), 20, U.GOLD, True)
        if not rough:
            cl = self.stone.get("cl", 1.0)
            n_inc = len([i for i in (incl or []) if i.get("k") != "silk"])
            cl_loss = max(0.0, 1.0 - GM.k_clarity(w.xd, cl) / max(1e-6, GM.k_clarity(w.xd, 1.0)))
            U.text(surf, f"чистота: {GM.grade(w.xd, cl).lower()} · включения: {n_inc} · "
                         f"примеси −{cl_loss * 100:.0f}%",
                   (r.x + 18, y + 26), 11, U.DIM)
        U.text(surf, "Фонарик сзади — просвет и внутреннее преломление. F — включить.",
               (r.x + 18, r.bottom - 122), 12, U.GREEN if self.flash_on else U.GOLD)
        U.text(surf, "ЛКМ — вращать · колесо — приблизить" + (" · ПКМ — метка" if rough else ""),
               (r.x + 18, r.bottom - 106), 12, U.DIM)
        # Режимы света: сзади (основной), прямой, боковой.
        modes = (("back", "1 Сзади"), ("front", "2 Прямой"), ("grazing", "3 Боковой"))
        for k, (key, label) in enumerate(modes):
            self.button(surf, pygame.Rect(r.x + 18 + k * 146, r.bottom - 154, 140, 26), label,
                        ("mode", key), True,
                        U.GOLD if self.flash_mode == key else U.BLUE, True)
        self.button(surf, pygame.Rect(r.x + 18, r.bottom - 76, 190, 30), "Фонарик (F)",
                    "flash", True, U.GOLD if self.flash_on else U.BLUE, True)
        if self.can_buy:
            self.button(surf, pygame.Rect(r.x + 18, r.bottom - 38, 190, 26),
                        "Купить партию" if self.kind == "lot" else "Купить",
                        "buy", w.money >= self.price, U.GREEN, True)
            self.button(surf, pygame.Rect(r.x + 224, r.bottom - 38, 190, 26), "Назад",
                        "back", True, U.BLUE, True)
        else:
            self.button(surf, pygame.Rect(r.x + 18, r.bottom - 38, 190, 26), "Назад",
                        "back", True, U.BLUE, True)
        if len(self.stones) > 1:
            # стол: весь мешочек перед глазами, клик — взять кусок под лупу
            for k, st in enumerate(self.stones[:9]):
                cell = pygame.Rect(24 + k * 84, 676, 80, 112)
                sel = k == self.i
                U.panel(surf, cell, U.PANEL_HI if sel else (30, 25, 21), U.GOLD if sel else U.EDGE, 2 if sel else 1, 6)
                surf.blit(JV.rough_thumb(st, rough_color(w, st), 72, w.xd), (cell.x + 4, cell.y + 2))
                U.text(surf, U.fit(w.gem_name(st["id"]), 11, 74), (cell.x + 4, cell.y + 74), 11, U.TEXT)
                mk = len(st.get("marks") or [])
                U.text(surf, f"{st['size']:.2f} ct" + (f" · м{mk}" if mk else ""), (cell.x + 4, cell.y + 92), 10, U.DIM)
                self.hit(cell, ("pick", k))


class CutScene(Scene):
    """Полноэкранный станок из основной игры.

    Повторяет поведение MiniGameScene: станок занимает почти весь экран,
    Esc до начала работы возвращает камень, Esc после начала завершает его.
    """

    def __init__(self, app, rough, client):
        super().__init__(app)
        w = app.workshop
        known = [client["cut"]] if client.get("cut") in w.known_cuts else w.known_cuts
        self.client = client
        self.rough = rough
        self.game = JewelCut(seed=app.seed, rough=rough, known=known, xd=w.xd,
                             lenses=tuple(w.lenses), disks=tuple(w.disks),
                             autofocus=w.autofocus)
        gd = GM.gem_def(w.xd, rough["id"])
        self.game.color = GM.tint(tuple(gd.get("color", (120, 160, 220))), rough.get("col", 0.5))
        self.rect = pygame.Rect(16, 62, W - 32, H - 96)
        self.finished = False

    def area(self):
        return self.rect

    def finish(self):
        if self.finished:
            return
        self.finished = True
        w = self.app.workshop
        rev = MK.review(self.rough, w.xd)          # метки против того, что оказалось внутри
        gem = w.finish_gem(self.rough, self.game)
        if rev:
            gem["review"] = {"score": round(rev["score"], 2), "hits": rev["hits"], "misses": rev["misses"]}
        if getattr(self.game, "grind_stats", None):
            gem["grind"] = self.game.grind_stats
        self.app.switch(ResultScene(self.app, self.client, gem, None, 0, review=rev, rough=self.rough))

    def stop_early(self):
        g = self.game
        if g.done:
            return
        if hasattr(g, "can_abort") and g.can_abort():
            self.app.workshop.inventory.append(self.rough)
            self.app.switch(HubScene(self.app, tab="workshop"))
            return
        if hasattr(g, "stop"):
            g.stop()
            return

    def act(self, action):
        if action == "take":
            self.finish()

    def handle(self, ev):
        if ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and ev.button not in (1, 2, 3):
            return
        g = self.game
        if hasattr(g, "pointer") and g.pointer(ev, self.rect):
            if ev.type == pygame.MOUSEMOTION:
                self.mouse = ev.pos
            return
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.stop_early()
                return
            if g.done and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.finish()
                return
            if ev.key == pygame.K_SPACE:
                g.press()
                return
            if hasattr(g, "key") and g.key(ev.key):
                return
        elif ev.type == pygame.KEYUP and ev.key == pygame.K_SPACE:
            g.release()
            return
        elif ev.type == pygame.MOUSEWHEEL:
            if hasattr(g, "wheel"):
                g.wheel(ev.y)
            return
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (4, 5):
            return
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3 and not g.done and hasattr(g, "key"):
            g.key(pygame.K_RETURN)
            return
        elif ev.type == pygame.MOUSEMOTION:
            g.mouse(ev.pos, self.rect)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and not g.done and self.rect.collidepoint(ev.pos):
            if hasattr(g, "click") and g.click(ev.pos):
                return
            if getattr(g, "click_press", True):
                g.press()
            return
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and not g.done:
            if getattr(g, "click_press", True):
                g.release()

    def update(self, dt):
        self.game.update(dt)

    def draw(self, surf):
        self.hits = []
        surf.fill((14, 12, 10))
        g = self.game
        U.text(surf, f"Огранка: {self.app.workshop.gem_name(self.rough['id'])} · "
                     f"{self.rough['size']:.2f} кар.", (W // 2, 18), 22, U.GOLD, True, True, True)
        U.text(surf, f"{g.title}: {g.hint}", (W // 2, 42), 13, U.TEXT, False, True)
        U.panel(surf, self.rect, (25, 21, 18), U.EDGE, 1, 4)
        g.draw(surf, self.rect)
        if getattr(g, "phase", "cut") not in ("choose", "plan", "grind"):
            q = g.quality
            U.text(surf, f"Качество: {q * 100:.0f}%", (W // 2, self.rect.bottom + 8), 16,
                   U.GOLD if q >= 1.0 else U.TEXT, True, True)
        if g.done:
            self.button(surf, pygame.Rect(W // 2 - 140, H - 58, 280, 44), "Готово (Enter)",
                        "take", True, U.GREEN)
        else:
            free = hasattr(g, "can_abort") and g.can_abort()
            U.text(surf, "Esc — отмена (камень не тронут)" if free else
                   "Esc — завершить работу", (W // 2, H - 34), 13, U.DIM, False, True)


class ResultScene(Scene):
    def __init__(self, app, client, gem, status, offer, review=None, rough=None):
        super().__init__(app)
        self.review = review
        self.rough = rough              # исходный кусок — для «до и после»
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
        elif action == "inspect":
            self.app.switch(InspectScene(self.app, [self.gem], self.gem.get("value", 0), "gem", -1,
                                         back=lambda: self.app.switch(self)))

    def draw(self, surf):
        self.hits = []
        w = self.app.workshop
        surf.fill(U.BG)
        U.text(surf, "РЕЗУЛЬТАТ", (24, 18), 28, U.GOLD, True)
        U.text(surf, self.client["name"], (24, 58), 17, U.TEXT)
        r = pygame.Rect(24, 100, 470, 420)
        U.panel(surf, r, U.PANEL, U.EDGE)
        y0 = r.y + 236
        if self.rough:
            # до и после: невзрачный кусок → готовый камень
            JV.draw_rough(surf, self.rough, rough_color(w, self.rough), (r.x + 115, r.y + 128), 170,
                          t=self.app.clock * 0.3, xd=w.xd)
            JV.draw_gem(surf, self.gem, gem_color(w, self.gem), (r.x + 350, r.y + 128), 170,
                        t=self.app.clock * 0.5, xd=w.xd)
            ax, ay = r.x + 222, r.y + 128
            pygame.draw.line(surf, U.GOLD, (ax, ay), (ax + 26, ay), 3)
            pygame.draw.polygon(surf, U.GOLD, [(ax + 34, ay), (ax + 24, ay - 7), (ax + 24, ay + 7)])
            U.text(surf, "было", (r.x + 98, r.y + 16), 14, U.DIM)
            U.text(surf, "стало", (r.x + 330, r.y + 16), 14, U.GOLD)
            ct0 = self.rough.get("size0", self.rough["size"])
            cost = self.rough.get("cost")
            U.text(surf, f"кусок {ct0:.2f} ct" + (f" · куплен за ≈{cost} з." if cost else ""),
                   (r.x + 20, y0), 14, U.DIM)
            yld = self.gem["size"] / max(0.01, ct0) * 100
            U.text(surf, f"камень {self.gem['size']:.2f} ct · выход {yld:.0f}%", (r.x + 20, y0 + 20), 14, U.TEXT)
            gs = self.gem.get("grind") or {}
            if gs.get("overcut", 0) > 0.005 or gs.get("chips"):
                U.text(surf, f"обдирка: за контур {gs.get('overcut', 0) * 100:.0f}% · сколов {gs.get('chips', 0)}",
                       (r.x + 20, y0 + 40), 12, U.RED)
        else:
            JV.draw_gem(surf, self.gem, gem_color(w, self.gem), (r.centerx, r.y + 120), 190,
                        t=self.app.clock * 0.5, xd=w.xd)
        y1 = y0 + 62
        U.text(surf, w.gem_name(self.gem["id"]), (r.x + 20, y1), 22, U.TEXT, True)
        U.text(surf, f"качество {self.gem['q']:.2f} · огранка: {w.cut_name(self.gem['cut'])}",
               (r.x + 20, y1 + 32), 14, U.TEXT)
        U.text(surf, SURF.short_line(SURF.for_stone(self.gem)), (r.x + 20, y1 + 54), 13, U.DIM)
        U.text(surf, f"Оценка: {self.gem['value']} з.", (r.x + 20, y1 + 76), 18, U.GOLD, True)
        r2 = pygame.Rect(520, 100, 736, 420)
        U.panel(surf, r2, U.PANEL, U.EDGE)
        U.text(surf, "Клиент", (r2.x + 18, r2.y + 16), 18, U.GOLD, True)
        self.button(surf, pygame.Rect(r2.right - 150, r2.y + 12, 132, 28), "Осмотр",
                    "inspect", True, U.BLUE, True)
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
        if self.review:
            self._draw_review(surf, pygame.Rect(24, 536, 1232, 240))

    def _draw_review(self, surf, r):
        """Разбор: метки, поставленные до огранки, против того, что оказалось внутри."""
        rev = self.review
        U.panel(surf, r, U.PANEL, U.EDGE)
        U.text(surf, "Разбор: что вы прочитали в сырье", (r.x + 18, r.y + 12), 18, U.GOLD, True)
        if rev["marked"]:
            U.text(surf, f"верно {rev['hits']} · ошибок и пропусков {rev['misses']} · "
                         f"точность {rev['score'] * 100:.0f}%", (r.x + 380, r.y + 16), 14, U.TEXT)
        else:
            U.text(surf, "меток не было — вот что было внутри", (r.x + 380, r.y + 16), 14, U.DIM)
        items = rev["items"] or [("hit", "внутри чисто — и меток нет", U.GREEN)]
        for i, (_, txt, col) in enumerate(items[:16]):
            x = r.x + 18 + (i // 8) * 600
            y = r.y + 46 + (i % 8) * 23
            U.text(surf, U.fit(txt, 14, 580), (x, y), 14, col)
        if len(items) > 16:
            U.text(surf, f"… и ещё {len(items) - 16}", (r.right - 140, r.bottom - 24), 12, U.DIM)


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
            self.app.switch(HubScene(self.app, tab="hub"))
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
        if rep["rent"] == 0 and w.apprentice_day:
            U.text(surf, "Аренду сегодня заплатил мастер", (r.x + 18, r.y + 18), 18, U.GREEN, True)
        else:
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
        self.scene = HubScene(self, tab="hub")
        self.running = True
        self.clock_t = 0.0
        self.fade = 0.0

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
        self.fade = 0.8

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
            if self.fade > 0:
                self.fade = max(0.0, self.fade - dt * 4.0)
                veil = pygame.Surface((W, H), pygame.SRCALPHA)
                veil.fill((0, 0, 0, int(210 * self.fade)))
                self.canvas.blit(veil, (0, 0))
            self._present()
        self.save()
        pygame.quit()
