"""Окно лаборатории обучения (lab.py): живой бой на свежих сетях, графики обучения, сравнение с автопилотом.

Обучение (sim/nn_lab.py) идёт всё время, пока открыто окно: процессы-бойцы играют бои, ученик на видеокарте
обновляет сети. Вкладки только показывают его:
  «Бой»       — показательный бой: герои — текущая сеть, враги — автопилот (каждый новый бой берёт свежие
                веса); щелчок по юниту — «что думает сеть», F1–F3 и +/− — скорость, Enter — следующий бой;
  «Графики»   — победы, награды, потери PPO, энтропия, скорость и загрузка процессора и видеокарты;
  «Автопилот» — контрольные серии: одни и те же бои героями-сетями и автопилотом.
P — пауза обучения, S — сохранить точку, U дважды — опубликовать сети в data/neural, E — контроль сейчас.
"""
import random
import time

import pygame

from sim import neural as NN
from sim import nn_lab as LAB
from sim import rewards as RW
from sim.combat import ENEMY, PLAYER
from ui import theme as T

TABS = (("battle", "Бой"), ("charts", "Графики"), ("eval", "Автопилот"))
BLUE = (150, 200, 255)
GREEN = (150, 220, 170)
RED = (240, 130, 110)
GOLD = (232, 170, 72)
VIOLET = (200, 160, 255)
GREY = (170, 160, 150)


class LabApp:
    """Держатель сцен лаборатории (как App у игры): scene, quit, relayout."""

    def __init__(self, data, trainer):
        from sim import expedition as X
        self.data = data
        self.ed = trainer.ed
        self.trainer = trainer
        self.quit = False
        self.tab = "battle"
        self.notice = None
        self.confirm_publish = 0.0
        self.show = Showcase(self)
        self.charts = ChartsScene(self)
        self.evals = EvalScene(self)

    @property
    def scene(self):
        return {"battle": self.show, "charts": self.charts, "eval": self.evals}[self.tab]

    def relayout(self):
        if self.show.b is not None:
            self.show.b.relayout()

    def say(self, msg, sec=3.0):
        self.notice = (msg, sec)

    def tick(self, dt):
        if hasattr(self.trainer, "poll"):            # ученик в другом процессе: свежая сводка
            self.trainer.poll()
        if self.notice:
            self.notice = (self.notice[0], self.notice[1] - dt)
            if self.notice[1] <= 0:
                self.notice = None
        self.confirm_publish = max(0.0, self.confirm_publish - dt)

    # общие клавиши и вкладки; True — событие съедено
    def common(self, ev):
        tr = self.trainer
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for key, r in tab_rects():
                if r.collidepoint(ev.pos):
                    self.tab = key
                    return True
        if ev.type != pygame.KEYDOWN:
            return False
        if ev.key == pygame.K_BACKQUOTE or (ev.key == pygame.K_TAB and ev.mod & pygame.KMOD_CTRL):
            keys = [k for k, _ in TABS]
            self.tab = keys[(keys.index(self.tab) + 1) % len(keys)]
            return True
        if ev.mod & pygame.KMOD_CTRL:
            return False
        if ev.key == pygame.K_p:
            tr.paused = not tr.paused
            self.say("Обучение на паузе (бои идут, опыт не копится)" if tr.paused else "Обучение продолжено")
            return True
        if ev.key == pygame.K_s:
            tr.save()
            self.say("Точка сохранена: save/lab/ckpt")
            return True
        if ev.key == pygame.K_r:
            names = list(RW.PRESETS)
            nxt = names[(names.index(tr.cfg["reward"]) + 1) % len(names)] if tr.cfg["reward"] in names else names[0]
            if tr.set_reward(nxt):
                self.say(f"Награда: «{nxt}» — {RW.PRESETS[nxt]['about']}", 5)
            else:
                self.say("Пресет на ходу не меняется: запустите новый прогон с --reward или --dir", 6)
            return True
        if ev.key == pygame.K_e:
            tr.start_eval()
            self.say("Контрольная серия запущена — смотрите вкладку «Автопилот»")
            return True
        if ev.key == pygame.K_u:
            if self.confirm_publish > 0:
                tr.publish()
                self.confirm_publish = 0
                self.say("Школа героев опубликована в data/neural: с неё начнут новые герои learn.py", 4)
            else:
                self.confirm_publish = 3.0
                self.say("U ещё раз — заменить школу героев игры (data/neural) сетью лаборатории", 3)
            return True
        return False


def tab_rects():
    x = T.SCREEN_W - 16
    out = []
    for key, name in reversed(TABS):
        w = T.font(15, True).size(name)[0] + 26
        x -= w
        out.append((key, pygame.Rect(x, 8, w, 28)))
        x -= 6
    return list(reversed(out))


def draw_tabs(surf, app):
    for key, r in tab_rects():
        on = app.tab == key
        T.frame(surf, r, 235 if on else 180, accent=BLUE if on else None, corners=False, radius=6)
        T.text(surf, dict(TABS)[key], r.center, 15, BLUE if on else T.TEXT_DIM, True, center=True)


def status_line(tr):
    el = max(1.0, tr.elapsed)
    dev = "видеокарта" if tr.device == "cuda" else "процессор"
    pause = " · ПАУЗА" if tr.paused else ""
    err = tr.errors if isinstance(tr.errors, int) else len(tr.errors)
    return (f"боёв {tr.battles} (учитель {tr.teacher_battles}) · {tr.battles_per_sec():.0f} боёв/с · "
            f"образцов {tr.samples / 1e6:.2f} млн ({tr.samples / el / 1000:.0f} тыс/с) · шагов PPO {tr.updates} · "
            f"ученик: {dev} · ЦП {tr.res['cpu']:.0f}% · ГП {tr.res['gpu']:.0f}% ({tr.res['gpu_mem']:.0f} МБ)"
            f" · бойцов {tr.alive}/{tr.workers} (по потоку на каждого)" + (f" · упавших боёв {err}" if err else "")
            + pause)


def draw_top(surf, app, title, second=None):
    """Шапка: заголовок, вкладки, строка состояния обучения (или своя вторая строка)."""
    tr = app.trainer
    bar = pygame.Rect(0, 0, T.SCREEN_W, 44)
    s = pygame.Surface(bar.size, pygame.SRCALPHA)
    s.fill((14, 12, 11, 235))
    surf.blit(s, bar)
    T.text(surf, title, (14, 4), 20, BLUE, True)
    if second is None:
        T.text(surf, status_line(tr), (14, 26), 12, T.TEXT_DIM)
    else:
        x = 14 + T.font(20, True).size(title)[0] + 14
        T.text(surf, short_status(tr), (x, 10), 12, T.TEXT_DIM)
        T.text(surf, second, (14, 26), 12, GOLD, True)
    draw_tabs(surf, app)


def short_status(tr):
    rw = tr.reward()
    return (f"боёв {tr.battles} · {tr.battles_per_sec():.0f}/с · шагов PPO {tr.updates} · ЦП {tr.res['cpu']:.0f}% · "
            f"ГП {tr.res['gpu']:.0f}% · награда «{rw['name']}» (подсказки ×{rw['scale']:.2f}, дух {rw['tau']:.0%})"
            + (" · ПАУЗА" if tr.paused else ""))


def draw_bottom(surf, app, hint):
    if app.notice:
        T.text(surf, app.notice[0], (T.SCREEN_W // 2, T.SCREEN_H - 52), 16, (255, 210, 120), True, center=True,
               shadow=True)
    T.text(surf, hint + "   ·   P пауза · S сохранить · R награда · E контроль · U опубликовать · ` вкладки",
           (T.SCREEN_W // 2, T.SCREEN_H - 18), 12, T.TEXT_DIM, center=True, shadow=True)


# ---------- вкладка «Бой» ----------

class Showcase:
    """Показательный бой на текущих весах. Обёртка над BattleScene: всё, чего нет здесь, — у боя."""

    def __init__(self, app):
        self.app = app
        self.b = None
        self.sc = None
        self.wait = 0.0
        self.speed = 1
        self.n = 0
        self.vision = True            # панель «что видит сеть» (V)
        self.new_battle()

    def __getattr__(self, name):                     # draw_layers, vfx, plane… — от сцены боя (для OpenGL)
        b = self.__dict__.get("b")
        if b is None:
            raise AttributeError(name)
        return getattr(b, name)

    def new_battle(self):
        from game.battle_scene import BattleScene
        app = self.app
        self.n += 1
        self.sc = LAB.scenario(app.ed, random.randrange(2 ** 31))
        run, node, enc = LAB.prepare(app.ed, self.sc)
        agents = app.trainer.showcase_agents()
        if agents is None:                           # ученик ещё не выложил веса — попробуем чуть позже
            self.wait = 2.0
            return
        self.version = app.trainer.version

        obs_mod, net_mod, _ = LAB.model_mods(app.trainer.cfg)

        def neural(c):
            ctl = NN.Controller(c, LAB.factory(c, agents), teams=(PLAYER,), learn=False,
                                obs=obs_mod, net=net_mod)
            ctl.keep_obs = True
            c.controllers.append(ctl)
            return ctl
        self.b = BattleScene(run.data, enc, autoplay=True, squad=run.combat_squad(), enemy_scale=run.enemy_scale(node),
                             simple=True, neural=neural)
        self.b.cfg = dict(self.b.cfg, speeds=[0.5, 1.0, 2.0, 4.0, 8.0])
        self.b.speed_idx = self.speed
        hs = self.b.combat.heroes(PLAYER)
        if hs:
            self.b.selected, self.b.selected_units = hs[0], [hs[0]]
        self.wait = 0.0

    def update(self, dt):
        self.app.tick(dt)
        self.b.update(dt)
        self.speed = self.b.speed_idx
        if self.b.selected is None:                  # выбранный пал — показываем мысли следующего
            hs = [u for u in self.b.combat.heroes(PLAYER) if u.alive]
            if hs:
                self.b.selected, self.b.selected_units = hs[0], [hs[0]]
        if self.b.combat.result or self.b.combat.time > LAB.CONFIG["max_time"]:
            self.wait += dt
            if self.wait > 3.0:
                self.new_battle()

    def handle(self, ev):
        if self.app.common(ev):
            return
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_RETURN:
                self.new_battle()
                return
            if ev.key == pygame.K_v:
                self.vision = not self.vision
                return
            if ev.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self.b.speed_idx = min(len(self.b.cfg["speeds"]) - 1, self.b.speed_idx + 1)
                return
            if ev.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.b.speed_idx = max(0, self.b.speed_idx - 1)
                return
            if ev.key == pygame.K_ESCAPE:
                self.app.quit = True
                return
        self.b.handle(ev)

    def _overlay(self, ui):
        app, sc = self.app, self.sc
        names = ", ".join(f"{app.ed.classes[c]['name']} {lv}" for c, lv in zip(sc["squad"], sc["levels"]))
        ch = (app.ed.expedition.get("chapters", {}).get(sc["chapter"]) or {}).get("name", sc["chapter"])
        kind = "босс" if sc["boss"] else "бой"
        c = self.b.combat
        res = {"victory": "победа сетей героев", "defeat": "победа сетей врагов"}.get(c.result, "")
        draw_top(ui, app, "Живой бой", f"№{self.n}: {ch}, акт {sc['act'] + 1}, {kind} · {names} · веса v{self.version}"
                                       f" · ×{self.b.cfg['speeds'][self.b.speed_idx]:g} · {c.time:.0f} с  {res}")
        if app.notice:
            T.text(ui, app.notice[0], (T.SCREEN_W // 2, 300), 16, (255, 210, 120), True, center=True, shadow=True)
        for i, s in enumerate(("щелчок по юниту — что думает сеть", "V — что видит сеть · F1–F3, +/− скорость",
                               "Space пауза · Enter новый бой · Esc выход", "P пауза · S сохранить · R награда",
                               "E контроль · U опубликовать · ` вкладки")):
            T.text(ui, s, (18, 208 + i * 15), 11, T.TEXT_DIM, shadow=True)
        if self.vision and self.b.ctl is not None:
            draw_vision(ui, self.b.ctl, self.b.selected, pygame.Rect(T.SCREEN_W - 352, 182, 340, 410))

    def draw(self, surf):
        self.b.draw(surf)
        self._overlay(surf)

    def draw_layers(self, world, ui, units=None):
        self.b.draw_layers(world, ui, units)
        self._overlay(ui)

    def _draw_mind(self, surf):
        pass


# ---------- что видит сеть ----------

VIS_LAYERS = (("hazard_foe", "опасно", RED), ("enemy", "враги", (255, 150, 120)), ("ally", "свои", GREEN),
              ("cast_foe", "чужие касты", VIOLET), ("zone_foe", "чужие зоны", GOLD),
              ("move_mask", "маска шага", GREY))
SHOW = (("hp_frac", "HP {:.0%}", 1), ("shield", "щит {:.0%}", 1), ("armor", "бр {:.0f}", 20),
        ("casting", "каст", 0), ("stun", "оглуш", 0), ("taunted", "насмешка", 0), ("hidden", "скрыт", 0),
        ("hp_loss_5s", "−{:.0%}/5с", 1), ("moving", "идёт", 0))


def draw_vision(surf, ctl, u, r):
    """Вход сети выбранного юнита: токены юнитов (главные признаки), навыки (готов / можно), слои карты side×side."""
    from sim import battle_obs as B
    obs_mod = getattr(ctl, "B", B)
    side = getattr(obs_mod, "SIDE", B.SIDE)
    R = getattr(obs_mod, "R", B.R)
    T_SKILL = getattr(obs_mod, "T_SKILL", B.T_SKILL)
    T.frame(surf, r, 228, accent=BLUE, corners=False, radius=6)
    got = ctl.last_obs.get(u) if u is not None else None
    if got is None:
        T.text(surf, "Что видит сеть: выберите героя", (r.x + 10, r.y + 8), 13, BLUE, True)
        return
    obs, cands = got
    sc = obs_mod.schema(ctl.c.data)
    ix = {n: i for i, n in enumerate(sc["unit"])}
    T.text(surf, f"Что видит сеть {u.name}: юнитов {len(cands['units'])}, признаков у каждого {len(sc['unit'])}",
           (r.x + 8, r.y + 5), 12, BLUE, True)
    y = r.y + 24
    for k, v in enumerate(cands["units"][:9]):
        row = obs["units"][k]
        who = "я" if row[ix["me"]] else "свой" if row[ix["ally"]] else "враг"
        col = BLUE if who == "я" else GREEN if who == "свой" else RED
        bits = []
        for name, fmt, scale in SHOW:
            val = float(row[ix[name]])
            if abs(val) > 1e-3:
                bits.append(fmt.format(val * scale) if "{" in fmt else fmt)
        for n in sc["unit"]:
            if (n.startswith("buff:") or n.startswith("status:")) and abs(float(row[ix[n]])) > 1e-3:
                bits.append(n.split(":", 1)[1])
        if row[ix["targets_me"]]:
            bits.append("бьёт меня")
        if row[ix["cast_on_me"]] or row[ix["cast_near_me"]]:
            bits.append("каст на меня")
        T.text(surf, f"{who}: {v.name}"[:22], (r.x + 8, y), 11, col, True)
        T.text(surf, " · ".join(bits)[:44], (r.x + 128, y), 11, T.TEXT_DIM)
        y += 14
    y += 4
    T.text(surf, "навыки:", (r.x + 8, y), 11, T.TEXT, True)
    si = {n: i for i, n in enumerate(sc["skill"])}
    x = r.x + 58
    for k, sid in enumerate(cands["skills"]):
        f = obs["skills"][k]
        ok = obs["tmask"][T_SKILL + k]
        name = u.skill_defs[sid]["name"][:12]
        col = GREEN if ok else (GOLD if f[si["ready"]] else GREY)
        w = T.font(11).size(name)[0] + 8
        if x + w > r.right - 6:
            y += 13
            x = r.x + 58
        T.text(surf, name, (x, y), 11, col)
        x += w
    y += 20
    cell = max(2, min(7, 96 // max(1, side)))       # 11×11 — по 7 px, полное 24×24 — по 4 px
    for j, (layer, label, col) in enumerate(VIS_LAYERS):
        gx = r.x + 8 + (j % 3) * 110
        gy = y + (j // 3) * 100
        T.text(surf, label, (gx, gy), 11, col)
        if layer == "move_mask":                    # маска шага: клетки, куда реально можно дойти в обход юнитов
            m = obs["cmask"][getattr(obs_mod, "T_MOVE", B.T_MOVE)].reshape(side, side)
        else:
            m = obs["map"][sc["map"].index(layer)]
        for yy in range(side):
            for xx in range(side):
                val = float(m[yy, xx])
                c = T.mix((26, 22, 20), col, max(0.0, min(1.0, val)))
                pygame.draw.rect(surf, c, (gx + xx * cell, gy + 14 + yy * cell, cell - 1, cell - 1))
        pygame.draw.rect(surf, BLUE, (gx + R * cell, gy + 14 + R * cell, cell - 1, cell - 1), 1)


# ---------- графики ----------

def chart(surf, rect, title, series, lo=None, hi=None, fmt="{:.2f}", note=None):
    """Линейный график: series — [(подпись, цвет, [(x, y)])]. Ось x — номер боя."""
    T.frame(surf, rect, 225, accent=T.mix(BLUE, (0, 0, 0), 0.45), corners=False, radius=6)
    T.text(surf, title, (rect.x + 8, rect.y + 5), 13, T.TEXT, True)
    labs = [(name + (f" {fmt.format(pts[-1][1])}" if pts else ""), col) for name, col, pts in series]
    room = rect.w - 24 - T.font(13, True).size(title)[0]
    wide = sum(T.font(11).size(lab)[0] + 12 for lab, _ in labs)
    top = 24
    if wide <= room:                                 # подписи — справа от заголовка
        lx = rect.right - 8
        for lab, col in reversed(labs):
            lx -= T.font(11).size(lab)[0]
            T.text(surf, lab, (lx, rect.y + 7), 11, col)
            lx -= 12
    else:                                            # не влезают — строками под заголовком
        lx, ly = rect.x + 8, rect.y + 22
        for lab, col in labs:
            w = T.font(11).size(lab)[0]
            if lx + w > rect.right - 8:
                lx, ly = rect.x + 8, ly + 13
            T.text(surf, lab, (lx, ly), 11, col)
            lx += w + 12
        top = ly - rect.y + 16
    box = pygame.Rect(rect.x + 42, rect.y + top, rect.w - 52, rect.h - top - 16)
    allp = [p for _, _, pts in series for p in pts]
    if len(allp) < 2:
        T.text(surf, note or "данные копятся…", (box.centerx, box.centery), 12, T.TEXT_DIM, center=True)
        return
    ys = [p[1] for p in allp]
    lo = min(ys) if lo is None else lo
    hi = max(ys) if hi is None else hi
    if hi - lo < 1e-6:
        hi = lo + 1.0
    x0 = min(p[0] for p in allp)
    x1 = max(max(p[0] for p in allp), x0 + 1)
    for k in range(3):
        yy = box.bottom - k * box.h / 2
        pygame.draw.line(surf, (48, 42, 36), (box.x, yy), (box.right, yy))
        T.text(surf, fmt.format(lo + (hi - lo) * k / 2), (box.x - 4 - T.font(10).size(fmt.format(lo + (hi - lo) * k / 2))[0],
                                                          yy - 7), 10, T.TEXT_DIM)
    T.text(surf, f"бой {int(x0)}", (box.x, box.bottom + 2), 10, T.TEXT_DIM)
    s = f"бой {int(x1)}"
    T.text(surf, s, (box.right - T.font(10).size(s)[0], box.bottom + 2), 10, T.TEXT_DIM)
    for _, col, pts in series:
        if len(pts) < 2:
            continue
        step = max(1, len(pts) // box.w)
        pp = pts[::step]
        xy = [(box.x + (x - x0) / (x1 - x0) * box.w,
               box.bottom - (min(hi, max(lo, y)) - lo) / (hi - lo) * box.h) for x, y in pp]
        pygame.draw.lines(surf, col, False, xy, 2)


def smooth(pts, k=0.15):
    out, acc = [], None
    for x, y in pts:
        acc = y if acc is None else acc * (1 - k) + y * k
        out.append((x, acc))
    return out


class ChartsScene:
    stage = False

    def __init__(self, app):
        self.app = app
        self.cls_scroll = 0

    def update(self, dt):
        self.app.tick(dt)

    def relayout(self):
        pass

    def handle(self, ev):
        if self.app.common(ev):
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.app.tab = "battle"

    def draw(self, surf):
        app, tr = self.app, self.app.trainer
        surf.fill(T.BG)
        draw_top(surf, app, "Лаборатория: графики обучения")
        h = dict(tr.history)
        W = T.SCREEN_W
        gap, top = 10, 54
        cw = (W - 24 - 2 * gap) // 3
        ch = 150
        cells = [
            ("Победы героев по соперникам (правила — мерка)", [
                ("против правил", GREEN, h.get("win_rules", [])), ("текущие враги", RED, h.get("win_latest", [])),
                ("прошлые", GOLD, h.get("win_past", [])),
                ("учитель-планировщик", VIOLET, h.get("win_planner", []))], 0, 1, "{:.0%}"),
            ("Награда за бой (на юнита)", [("герои", GREEN, h.get("hero_reward", [])),
                                           ("враги", RED, h.get("enemy_reward", []))], None, None, "{:.2f}"),
            ("Баланс матчей: сила врагов (×)", [("акт 1", GREEN, h.get("power:a0", [])),
                                                ("акт 2", GOLD, h.get("power:a1", [])),
                                                ("акт 3", RED, h.get("power:a2", [])),
                                                ("боссы", VIOLET, h.get("power:boss", []))], None, None, "{:.2f}"),
            ("Потери: ценность (сплошь — герои) и подражание", [
                ("ценность гер.", GREEN, smooth(h.get("loss_v:hero", []))),
                ("ценность вр.", RED, smooth(h.get("loss_v:enemy", []))),
                ("подражание", VIOLET, smooth(h.get("loss_bc:hero", [])))], 0, None, "{:.2f}"),
            ("Энтропия (тип + цель) и цель " + f"{tr.cfg.get('ent_target', 0):g}", [
                ("герои", GREEN, smooth(h.get("loss_ent:hero", []))),
                ("враги", RED, smooth(h.get("loss_ent:enemy", []))),
                ("премия×10 гер.", GOLD, [(x, y * 10) for x, y in h.get("loss_ent_coef:hero", [])])], 0, None,
             "{:.2f}"),
            ("KL и доля срезанных шагов (clip), герои", [("KL", BLUE, smooth(h.get("loss_kl:hero", []))),
                                                        ("clip", RED, smooth(h.get("loss_clip:hero", [])))], None,
             None, "{:.3f}"),
            ("Награда героев по компонентам (на героя за бой)", self._parts(h), None, None, "{:.2f}"),
            ("Загрузка всего ЦП и ГП, %", [("ЦП", GOLD, h.get("cpu", [])), ("ГП", BLUE, h.get("gpu", []))], 0, 100, "{:.0f}"),
        ]
        for i, (title, ser, lo, hi, fmt) in enumerate(cells):
            r = pygame.Rect(12 + (i % 3) * (cw + gap), top + (i // 3) * (ch + gap), cw, ch)
            chart(surf, r, title, ser, lo, hi, fmt)
        # таблица по классам — в последней ячейке и ниже
        r = pygame.Rect(12 + 2 * (cw + gap), top + 2 * (ch + gap), cw, ch)
        self._nets(surf, r)
        self._classes(surf, pygame.Rect(12, top + 3 * (ch + gap), W - 24, T.SCREEN_H - top - 3 * (ch + gap) - 30))
        draw_bottom(surf, app, "Esc — к бою")

    def _nets(self, surf, r):
        tr = self.app.trainer
        T.frame(surf, r, 225, accent=T.mix(BLUE, (0, 0, 0), 0.45), corners=False, radius=6)
        T.text(surf, "Сеть: школа героев (враги — автопилот)", (r.x + 8, r.y + 5), 13, T.TEXT, True)
        info = tr.net
        if not info:
            T.text(surf, "ученик запускается…", (r.x + 8, r.y + 26), 12, T.TEXT_DIM)
            return
        nm, a = info["names"], info["arch"]
        lines = [f"параметров {info['params']:,} · трансформер {a['layers']}×{a['d']}, "
                 f"{a['heads']} головы".replace(",", " "),
                 f"признаков: юнит {nm['unit']} · навык {nm['skill']} · карта {nm['map']}×"
                 f"{a.get('side', 11)}×{a.get('side', 11)} · общее {nm['glob']}",
                 f"видов {nm['kinds']} · навыков {nm['skills']} (свой вектор у каждого)",
                 f"пачка {tr.cfg['batch']} · эпох {tr.cfg['epochs']} · мини-пачка {tr.cfg['minibatch']}",
                 f"lr {tr.cfg['lr']:g} · clip {tr.cfg['clip']} · энтропия {tr.cfg['entropy']} · учитель "
                 f"{tr.cfg['teacher_share']:.0%}"]
        rw = tr.reward()
        lines.insert(0, f"награда «{rw['name']}» (R): подсказки ×{rw['scale']:.2f}, дух {rw['tau']:.0%}, "
                        f"победа {rw['win']:g}")
        shown = ((NN.HERO_KEY, "герои"), (NN.ENEMY_KEY, "враги")) if tr.cfg.get("learn_enemies") \
            else ((NN.HERO_KEY, "герои"),)
        for key, title in shown:
            st = tr.net_stats.get(key, {"updates": 0, "samples": 0})
            warm = (getattr(tr, "warm", None) or {}).get(key, 0)
            rs = (getattr(tr, "rscale", None) or {})
            rs = rs() if callable(rs) else rs
            ec = (getattr(tr, "ent_coef", None) or getattr(tr, "ent", None) or {}).get(key, 0)
            lines.append(f"{title}: шагов {st['updates']}, {st['samples'] / 1e6:.2f} млн · премия {ec:.3f} · "
                         f"норм. ×{rs.get(key, 1):.2f}" + (f" · разогрев критика ещё {warm}" if warm else ""))
        for i, s in enumerate(lines):
            T.text(surf, s, (r.x + 8, r.y + 26 + i * 15), 12, GOLD if i == 0 else T.TEXT_DIM if i < 6 else T.TEXT)

    PART_COLORS = (GREEN, BLUE, GOLD, VIOLET, RED, GREY, (120, 220, 220), (240, 180, 220))

    def _parts(self, h):
        """Ряды графика вклада: 6 самых весомых компонентов (по модулю за последние значения)."""
        rows = [(k[3:], v) for k, v in h.items() if k.startswith("rp:") and v]
        rows.sort(key=lambda kv: -abs(kv[1][-1][1]))
        return [(RW.NAMES.get(k, k), self.PART_COLORS[i % len(self.PART_COLORS)], v) for i, (k, v) in
                enumerate(rows[:6])]

    def _classes(self, surf, r):
        """По классам: награда (среднее за 200 боёв), доля побед отрядов с классом, шагов обучения."""
        tr, ed = self.app.trainer, self.app.ed
        T.frame(surf, r, 225, accent=T.mix(GREEN, (0, 0, 0), 0.45), corners=False, radius=6)
        T.text(surf, "Классы в общей школе: средняя награда героя за бой · победы отрядов с ним · боёв",
               (r.x + 8, r.y + 5), 13, T.TEXT, True)
        rows = []
        for cls in sorted(ed.classes):
            rw, wr, games = tr.classes.get(cls, (None, None, 0))
            rows.append((cls, rw, wr, {"updates": games}))
        cols = 3
        cw = (r.w - 16) // cols
        per = (len(rows) + cols - 1) // cols
        vals = [x[1] for x in rows if x[1] is not None]
        top = max(vals + [0.1])
        for i, (cls, rw, wr, st) in enumerate(rows):
            x = r.x + 8 + (i // per) * cw
            y = r.y + 26 + (i % per) * 18
            if y > r.bottom - 14:
                continue
            col = ed.classes[cls].get("color")
            col = tuple(col[:3]) if isinstance(col, (list, tuple)) else GREEN
            T.text(surf, ed.classes[cls]["name"], (x, y), 12, col, True)
            if rw is not None:
                bw = int(110 * max(0.0, rw) / top)
                pygame.draw.rect(surf, (34, 30, 26), (x + 120, y + 4, 110, 8))
                pygame.draw.rect(surf, GREEN, (x + 120, y + 4, bw, 8))
                T.text(surf, f"{rw:+.2f}", (x + 236, y), 12, T.TEXT)
            T.text(surf, f"{wr:.0%}" if wr is not None else "—", (x + 286, y), 12, T.TEXT_DIM)
            T.text(surf, str(st.get("updates", 0)), (x + 330, y), 12, T.TEXT_DIM)


# ---------- сравнение с автопилотом ----------

class EvalScene:
    stage = False

    def __init__(self, app):
        self.app = app

    def update(self, dt):
        self.app.tick(dt)

    def relayout(self):
        pass

    def handle(self, ev):
        if self.app.common(ev):
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.app.tab = "battle"

    def draw(self, surf):
        app, tr = self.app, self.app.trainer
        surf.fill(T.BG)
        draw_top(surf, app, "Лаборатория: сети против автопилота")
        W = T.SCREEN_W
        T.text(surf, f"Контрольная серия: {tr.cfg['eval_size']} одних и тех же боёв (сценарии с постоянными номерами). "
                     f"Каждый играется дважды: героями управляют сети (самый вероятный ход, без случайности) и "
                     f"автопилот игры.", (16, 54), 13, T.TEXT_DIM)
        T.text(surf, f"Враги в обоих случаях — правила игры, чтобы сравнение было честным. Серия — каждые "
                     f"{tr.cfg['eval_every']} боёв или по клавише E.", (16, 72), 13, T.TEXT_DIM)
        ev = tr.evals
        note = f"первая серия — после {tr.cfg['eval_every']} боёв (или нажмите E)"
        cw = (W - 34) // 2
        chart(surf, pygame.Rect(12, 96, cw, 300), "Доля побед в контрольной серии",
              [("сети", GREEN, [(e[0], e[1] / e[3]) for e in ev]), ("автопилот", GOLD, [(e[0], e[2] / e[3]) for e in ev])],
              0, 1, "{:.0%}", note=note)
        chart(surf, pygame.Rect(22 + cw, 96, cw, 300), "Здоровья у героев в конце (поражение — 0)",
              [("сети", GREEN, [(e[0], e[4]) for e in ev]), ("автопилот", GOLD, [(e[0], e[5]) for e in ev])],
              0, 1, "{:.0%}", note=note)
        r = pygame.Rect(12, 408, W - 24, T.SCREEN_H - 408 - 30)
        T.frame(surf, r, 225, accent=T.mix(GOLD, (0, 0, 0), 0.45), corners=False, radius=6)
        T.text(surf, "Серии", (r.x + 8, r.y + 5), 13, T.TEXT, True)
        done, total = tr.eval_progress
        if total:
            T.text(surf, f"идёт серия: готово {done}/{total}", (r.x + 80, r.y + 6), 12, BLUE, True)
        y = r.y + 28
        for a, nw, tw, n, nhp, thp in reversed(ev[-14:]):
            d = nw - tw
            col = GREEN if d > 0 else RED if d < 0 else T.TEXT_DIM
            T.text(surf, f"после боя {a}:", (r.x + 12, y), 13, T.TEXT_DIM)
            T.text(surf, f"сети {nw}/{n}", (r.x + 150, y), 13, GREEN, True)
            T.text(surf, f"автопилот {tw}/{n}", (r.x + 260, y), 13, GOLD, True)
            T.text(surf, f"{d:+d}", (r.x + 400, y), 13, col, True)
            T.text(surf, f"здоровья: сети {nhp:.0%} · автопилот {thp:.0%}", (r.x + 450, y), 13, T.TEXT_DIM)
            y += 18
        if not ev:
            T.text(surf, "Серий пока нет.", (r.x + 12, y), 13, T.TEXT_DIM)
        draw_bottom(surf, app, "Esc — к бою")
