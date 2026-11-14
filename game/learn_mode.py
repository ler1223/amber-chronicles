"""Режим обучения (learn.py): копия экспедиции, где героями и врагами управляют нейросети (sim/neural.py).

Learner — связь сетей с походом: у героя своя сеть (сохраняется по его uid, ветеран уносит её в следующий поход),
новый герой начинает с «школы класса», у врагов — сеть на вид врага. После каждого боя сети учатся на его опыте
и сохраняются; после похода опыт героев вливается в школу класса.
TrainScene — фоновая тренировка в лагере: N быстрых боёв без графики (бои текущего акта, тот же отряд).
draw_mind — панель «что думает сеть» в бою, draw_progress — график награды героя.
"""
import os
import random
import threading

import pygame

from sim import neural as NN
from sim.combat import Combat, ENEMY, PLAYER
from ui import theme as T

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULTS = os.path.join(ROOT, "data", "neural")


class Learner:
    def __init__(self, root):
        self.store = NN.Store(root, DEFAULTS)
        self.lock = threading.Lock()
        self.last = {}                # uid героя / вид врага → награда последнего боя

    # ---------- бой похода ----------

    def factory(self, run, combat):
        heroes_u = combat.heroes(PLAYER)

        def make(u):
            if u.team == PLAYER:
                if u in heroes_u and heroes_u.index(u) < len(run.heroes):
                    return self.store.hero(run.heroes[heroes_u.index(u)])
                return None                        # гости и призванные — правилами
            return self.store.enemy(u.proto_id)
        return make

    def controller(self, run, combat):
        ctl = NN.Controller(combat, self.factory(run, combat))
        combat.controllers.append(ctl)
        return ctl

    def after_battle(self, run, ctl):
        """Бой окончен: обучение и сохранение сетей героев и врагов."""
        with self.lock:
            res = ctl.finish()
            for u, ag in ctl.agents.items():
                kind = "heroes" if u.team == PLAYER else "enemies"
                self.store.save(kind, ag.key, ag)
            for ag, total in res.items():
                if total is not None:
                    self.last[ag.key] = total
            return res

    def after_run(self, run):
        """Поход окончен: опыт героев — в общую школу героев."""
        with self.lock:
            for h in run.heroes:
                if self.store.has("heroes", h.uid):
                    self.store.blend_school(h.cls, self.store.hero(h), 0.25)

    def agent(self, h):
        return self.store.hero(h)

    # ---------- тренировка ----------

    def train(self, run, n, progress=None, stop=None):
        """n быстрых боёв: бои текущего акта, тот же отряд и сила врагов; сети героев и врагов учатся."""
        rng = random.Random(f"{run.seed}:train:{len(run.path)}:{self.agent(run.heroes[0]).stats.get('battles', 0)}")
        nodes = [v for v in run.nodes.values() if v["type"] in ("battle", "elite") and v["encounter"] is not None]
        wins = 0
        for k in range(n):
            if stop is not None and stop():
                break
            node = rng.choice(nodes)
            c = Combat(run.data, node["encounter"], seed=rng.randrange(10 ** 6), squad=run.combat_squad(),
                       enemy_scale=run.enemy_scale(node), ai_teams=(ENEMY,))
            ctl = self.controller(run, c)
            while not c.result and c.time < 150:
                c.step()
            c.result = c.result or "defeat"
            self.after_battle(run, ctl)
            wins += c.result == "victory"
            if progress:
                progress(k + 1, wins)
        return wins


# ---------- экраны ----------

def draw_progress(surf, rect, stats, color=(150, 220, 170), title="Опыт сети"):
    """График награды за бой (последние 60 боёв) и сглаженная линия."""
    T.frame(surf, rect, 230, accent=T.mix(color, (0, 0, 0), 0.3), corners=False)
    rw = stats.get("rewards", [])
    T.text(surf, f"{title}: боёв {stats.get('battles', 0)}, побед {stats.get('wins', 0)}", (rect.x + 8, rect.y + 5),
           13, color, True)
    if len(rw) < 2:
        T.text(surf, "мало боёв для графика", (rect.x + 8, rect.y + 26), 12, T.TEXT_DIM)
        return
    lo, hi = min(rw + [0]), max(rw + [0.1])
    box = pygame.Rect(rect.x + 8, rect.y + 24, rect.w - 16, rect.h - 32)
    zero = box.bottom - (0 - lo) / (hi - lo) * box.h
    pygame.draw.line(surf, (70, 60, 50), (box.x, zero), (box.right, zero))
    pts = [(box.x + i * box.w / (len(rw) - 1), box.bottom - (v - lo) / (hi - lo) * box.h) for i, v in enumerate(rw)]
    pygame.draw.lines(surf, T.mix(color, (0, 0, 0), 0.5), False, pts, 1)
    sm, acc = [], None
    for v in rw:
        acc = v if acc is None else acc * 0.8 + v * 0.2
        sm.append(acc)
    pts = [(box.x + i * box.w / (len(sm) - 1), box.bottom - (v - lo) / (hi - lo) * box.h) for i, v in enumerate(sm)]
    pygame.draw.lines(surf, color, False, pts, 2)


def draw_mind(surf, ctl, u, x=16, y=96):
    """Что думает сеть выбранного юнита: три самых вероятных хода (тип и цель) и оценка положения."""
    th = ctl.thinking.get(u) if ctl else None
    r = pygame.Rect(x, y, 300, 104)
    T.frame(surf, r, 220, accent=(150, 200, 255), corners=False)
    if u is None or th is None:
        T.text(surf, "Нейросеть: выберите героя", (r.x + 10, r.y + 8), 13, (150, 200, 255), True)
        return
    ag = ctl.agents.get(u)
    T.text(surf, f"Сеть {u.name}: оценка {th['v']:+.2f} · боёв {ag.stats.get('battles', 0) if ag else 0}",
           (r.x + 10, r.y + 6), 13, (150, 200, 255), True)
    for k, (p, name) in enumerate(th["top"]):
        yy = r.y + 28 + k * 24
        pygame.draw.rect(surf, (30, 26, 22), (r.x + 10, yy + 14, 280, 5))
        pygame.draw.rect(surf, (150, 200, 255), (r.x + 10, yy + 14, int(280 * min(1.0, p)), 5))
        T.text(surf, f"{p * 100:4.0f}%  {name}", (r.x + 10, yy - 2), 13, T.TEXT)
    if ctl.state.get(u, {}).get("net_order") is not u.order and u.order and u.order.get("manual"):
        T.text(surf, "ваш приказ — сеть учится на нём", (r.x + 10, r.bottom - 14), 11, (255, 210, 120), True)


class TrainScene:
    """Фоновая тренировка: бои идут в отдельном потоке, экран показывает прогресс и графики героев."""
    stage = True

    def __init__(self, app, back, battles=20):
        from game.expedition_scenes import XScene
        self.base = XScene(app)
        self.app, self.back, self.n = app, back, battles
        self.done, self.wins, self.stop = 0, 0, False
        self.error = None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            self.app.neural.train(self.app.exp, self.n, progress=self._progress, stop=lambda: self.stop)
        except Exception as exc:              # noqa: BLE001 — показать на экране, не ронять игру
            self.error = repr(exc)
        self.done = max(self.done, self.n if not self.stop else self.done)

    def _progress(self, k, wins):
        self.done, self.wins = k, wins

    @property
    def finished(self):
        return not self.thread.is_alive()

    def update(self, dt):
        pass

    def relayout(self):
        pass

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_RETURN):
            if self.finished:
                self.back()
            else:
                self.stop = True
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 3) and self.finished:
            self.back()

    def draw(self, surf):
        run = self.app.exp
        surf.fill(T.BG)
        T.text(surf, "Тренировка сети", (24, 14), 30, (150, 200, 255), True)
        T.text(surf, "Быстрые бои без графики: бои этого акта, тот же отряд. Сети героев и врагов учатся на каждом.",
               (26, 54), 15, T.TEXT_DIM)
        bar = pygame.Rect(24, 96, T.SCREEN_W - 48, 22)
        pygame.draw.rect(surf, (30, 26, 22), bar, border_radius=6)
        pygame.draw.rect(surf, (150, 200, 255), (bar.x, bar.y, int(bar.w * self.done / max(1, self.n)), bar.h),
                         border_radius=6)
        T.text(surf, f"боёв {self.done}/{self.n} · побед {self.wins}", (bar.x + 10, bar.y + 3), 15, T.BG, True)
        y = 140
        for h in run.heroes:
            ag = self.app.neural.agent(h)
            draw_progress(surf, pygame.Rect(24, y, T.SCREEN_W - 48, 150), ag.stats,
                          title=f"{h.name} ({run.data.classes[h.cls]['name']})")
            y += 162
        msg = ("Готово — любая клавиша" if self.finished else "Esc — остановить после текущего боя")
        if self.error:
            msg = "Ошибка тренировки: " + self.error
        T.text(surf, msg, (T.SCREEN_W // 2, T.SCREEN_H - 30), 16, (255, 210, 120), True, center=True)
