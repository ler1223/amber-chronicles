"""Обучение в бою (сюжет, data/story.json): шаги-подсказки, каждый ждёт действия игрока.

Шаг: {"text", "until", "pause"}. until:
  start — бой начат после расстановки;      pause / unpause — поставить / снять паузу;
  ack — прочитал: Пробел;
  select[:класс] — выбран герой;             order — приказ идти или атаковать;
  skill[:id] — навык приказан или применён;  time:N — N секунд боя;  win — победа.
pause: true — пока шаг не выполнен, бой стоит на паузе (приказы на паузе отдавать можно).
F10 — пропустить обучение.
"""
import pygame

from sim.combat import PLAYER
from ui import theme as T


class Tutorial:
    def __init__(self, steps):
        self.steps = list(steps or [])
        self.i = 0
        self.t0 = None
        self.seen_skills = set()
        self.flash = 0.0
        self.acked = False
        self.begun = -1

    @property
    def step(self):
        return self.steps[self.i] if self.i < len(self.steps) else None

    def skip(self):
        self.i = len(self.steps)

    def observe(self, events):
        for e in events:
            if e["t"] == "skill" and e.get("unit") is not None and e["unit"].team == PLAYER:
                self.seen_skills.add(e.get("skill"))

    def ordered(self, sid):
        self.seen_skills.add(sid)

    def wants_ack(self):
        return self.step is not None and self.step["until"] == "ack"

    def ack(self):
        self.acked = True

    def _begin(self, sc, st):
        """Начало шага: «выберите героя» — сначала снимаем выбор, чтобы игрок сделал это сам."""
        self.acked = False
        if st["until"].startswith("select"):
            sc.selected = None
            sc.targeting = None

    def _done(self, sc, st):
        kind, _, arg = st["until"].partition(":")
        c = sc.combat
        if kind == "ack":
            return self.acked
        if kind == "start":
            return sc.phase == "battle"
        if kind == "pause":
            return sc.phase == "battle" and sc.paused
        if kind == "unpause":
            return sc.phase == "battle" and not sc.paused
        if kind == "select":
            return sc.selected is not None and (not arg or sc.selected.proto_id == arg)
        if kind == "order":
            return any(u.order and u.order.get("type") in ("move", "path", "attack")
                       for u in c.units if u.team == PLAYER and u.alive)
        if kind == "skill":
            return (arg in self.seen_skills) if arg else bool(self.seen_skills)
        if kind == "time":
            if self.t0 is None:
                self.t0 = c.time
            return c.time - self.t0 >= float(arg)
        if kind == "win":
            return c.result == "victory"
        return True

    def update(self, sc, dt):
        self.flash = max(0.0, self.flash - dt)
        st = self.step
        if st is not None and self.begun != self.i:
            self.begun = self.i
            self._begin(sc, st)
        while st is not None and self._done(sc, st):
            self.i += 1
            self.t0 = None
            self.flash = 0.6
            st = self.step
            if st is not None:
                self.begun = self.i
                self._begin(sc, st)
        if st and st.get("pause") and sc.phase == "battle" and not sc.combat.result:
            sc.paused = True                  # приказы отдаются на паузе — бой ждёт игрока

    def draw(self, surf):
        st = self.step
        if st is None:
            return
        w = 640
        lines = T.wrap(st["text"], 17, w - 40)
        h = 46 + 24 * len(lines)
        r = pygame.Rect((T.SCREEN_W - 300) // 2 - w // 2 + 40, 70, w, h)
        box = pygame.Surface(r.size, pygame.SRCALPHA)
        glow = int(120 * self.flash / 0.6)
        pygame.draw.rect(box, (16, 20, 30, 225), box.get_rect(), border_radius=10)
        pygame.draw.rect(box, (255, 205, 110, 160 + glow // 2), box.get_rect(), 2, border_radius=10)
        surf.blit(box, r)
        T.text(surf, f"Обучение · {self.i + 1}/{len(self.steps)}", (r.x + 16, r.y + 8), 14, (255, 205, 110), True)
        T.text(surf, "Пробел — понятно" if st["until"] == "ack" else "F10 — пропустить", (r.right - 130, r.y + 9),
               12, (255, 230, 160) if st["until"] == "ack" else T.TEXT_DIM)
        for k, ln in enumerate(lines):
            T.text(surf, ln, (r.x + 16, r.y + 32 + 24 * k), 17, (240, 236, 225))

