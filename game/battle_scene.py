"""Сцена боя: расстановка, ввод игрока, пауза/скорость, связь симуляции и отрисовки.

Фазы: "deploy" — разведка и расстановка (время стоит), "battle" — бой.
"""
import math

import pygame

from sim import movement as MV
from sim.combat import ENEMY, PLAYER, Combat
from sim.grid import sign
from sim.unit import Unit
from ui import projection as P
from ui.autocast_editor import AutocastEditor, adjust_first_value
from ui.battle_view import BattleView

SKILL_KEYS = {pygame.K_q: 0, pygame.K_w: 1, pygame.K_e: 2, pygame.K_r: 3, pygame.K_t: 4}
SPEED_KEYS = {pygame.K_F1: 0, pygame.K_F2: 1, pygame.K_F3: 2}
DRAG_DIST = 12


class BattleScene:
    """Без on_finish — песочница: R/N/F5/F6 перезапускают и листают бои.
    С on_finish (бой забега) — переигровки нет, по Enter после боя вызывается on_finish(combat, расстановка)."""

    def __init__(self, data, encounter_index=0, autoplay=False, squad=None, formation=None, on_finish=None,
                 enemy_scale=None, scout_hp=False, fx=None, difficulty="normal", cheats=False, tutorial=None):
        self.data = data
        from game.tutorial import Tutorial
        self.tutorial = Tutorial(tutorial) if tutorial else None   # сюжет: подсказки, ждущие действий игрока
        self.cheats = cheats or not on_finish    # песочница и отдельный бой: F7 — всё готово, F8 — победа
        self.difficulty = difficulty
        self.fx = fx                  # боевые эффекты реликвий
        self.enemy_scale = enemy_scale
        self.scout_hp = scout_hp      # бонус «Сторожевая башня»: разведка видит HP и урон врагов
        self.cfg = data.config
        self.view = BattleView(data)
        self.autoplay = autoplay
        self.squad = squad
        self.on_finish = on_finish
        self.speed_idx = 1
        self.positions = {}  # индекс боя -> последняя расстановка игрока
        self.formation = formation
        self.start(encounter_index)

    @property
    def run_mode(self):
        return self.on_finish is not None

    def start(self, encounter_index):
        P.reset()                     # камера боя (подготовка героя могла смотреть в окно превью)
        self.encounter_index = encounter_index % len(self.data.encounters)
        teams = (PLAYER, ENEMY) if self.autoplay else (ENEMY,)
        self.combat = Combat(self.data, self.encounter_index, ai_teams=teams, squad=self.squad,
                             player_positions=self.positions.get(self.encounter_index) or self.formation,
                             enemy_scale=self.enemy_scale, fx=self.fx, difficulty=self.difficulty)
        self.view.reset(self.combat)
        self.phase = "battle" if self.autoplay else "deploy"
        self.paused = not self.autoplay
        self.slowmo = False
        self.acc = 0.0
        self.targeting = None
        self.hover_cell = None
        self.mouse = (0, 0)
        self.toast = None
        self.picked = None       # юнит, взятый для перестановки
        self.route = None        # маршрут, который игрок рисует правой кнопкой: [клетки]
        self.pick = None         # юнит под курсором (подсвечен кольцом)
        self.drag_start = None
        self.editor = None       # открытый редактор автокаста: {"unit", "idx", "editor", "rect"}
        squad = self.combat.fighters(PLAYER)
        self.selected = squad[0] if squad else None

    def finish(self):
        if self.run_mode and self.combat.result:
            self.on_finish(self.combat, self.positions.get(self.encounter_index))

    def begin_battle(self):
        self.positions[self.encounter_index] = self.combat.positions()
        self.phase = "battle"
        self.picked = None
        self.drag_start = None
        self.paused = True
        self.say("Бой начался. Space — снять паузу")

    @property
    def dragging(self):
        return (self.picked is not None and self.drag_start is not None
                and math.dist(self.mouse, self.drag_start) > DRAG_DIST)

    # ---------- время ----------

    @property
    def time_scale(self):
        if self.phase != "battle" or self.paused or self.combat.result:
            return 0.0
        s = self.cfg["speeds"][self.speed_idx]
        # стоп-кадр и замедление от эффектов (удар, большое заклинание)
        return s * (self.cfg["slowmo_factor"] if self.slowmo else 1.0) * self.view.vfx.screen.time_k()

    def update(self, real_dt):
        # пауза (и расстановка): эффекты экрана гаснут, свечение приглушено — видно поле и фигурки
        self.view.vfx.screen.calm_target = 1.0 if (self.paused or self.phase != "battle") else 0.0
        game_dt = min(real_dt, 0.1) * self.time_scale
        self.acc += game_dt
        steps = 0
        while self.acc >= self.combat.dt and steps < 12:
            self.combat.step()
            self.acc -= self.combat.dt
            steps += 1
        if self.tutorial:
            self.tutorial.observe(self.combat.events)
        self.view.consume(self.combat.events)
        self.combat.events.clear()
        if self.tutorial:
            self.tutorial.update(self, real_dt)
        self.view.update(game_dt, real_dt)
        if self.toast:
            self.toast = (self.toast[0], self.toast[1] - real_dt)
            if self.toast[1] <= 0:
                self.toast = None
        if self.selected and not self.selected.alive:
            self.selected = None
            self.targeting = None
        if self.combat.result:
            self.targeting = None

    def draw(self, surf):
        self.view.draw(surf, self)
        if self.tutorial:
            self.tutorial.draw(surf)

    def draw_layers(self, world, ui, units=None):
        """Для OpenGL: земля, юниты и интерфейс отдельными слоями, эффекты (self.vfx) кладёт видеокарта."""
        self.view.draw_layers(world, ui, self, units)
        if self.tutorial:
            self.tutorial.draw(ui)

    def plane(self):
        """Земля HD-2D для видеокарты: плоская карта и цвет дымки."""
        return self.view.plane()

    def glow_layer(self):
        return self.view.glow_layer()

    def lab_frame(self):
        return self.view.lab_frame()

    @property
    def vfx(self):
        return self.view.vfx

    def say(self, msg):
        self.toast = (msg, 1.8)

    # ---------- ввод ----------

    def pick_filter(self):
        """Кого можно выбрать сейчас: при прицеливании навыком — только подходящие цели."""
        u = self.selected
        if not self.targeting or not u:
            return None
        kind = u.skill_defs[self.targeting]["target"]
        if kind == "enemy":
            return lambda v: u.is_enemy(v) and (not v.obj or v.obj.get("source"))
        if kind == "ally":
            return lambda v: not u.is_enemy(v) and not v.obj
        return None

    def unit_target(self):
        """Прицел навыком по юниту (враг или союзник) — клетка «прилипает» к фигурке."""
        return bool(self.targeting and self.selected
                    and self.selected.skill_defs[self.targeting]["target"] in ("enemy", "ally"))

    def ground_cell(self, mx, my):
        """Клетка земли под курсором — фигурки не мешают (перемещение, маршрут, навыки по площади)."""
        wx, wy = self.view.uncam((mx, my))
        return P.screen_to_cell(wx, wy, self.combat.grid.w, self.combat.grid.h)

    def cell_at(self, mx, my):
        """Клетка под курсором. Прилипает к фигурке (юнит мог уже перейти на соседнюю клетку) только там, где
        цель — юнит: навык по врагу или союзнику и расстановка своих перед боем."""
        if self.unit_target() or self.phase == "deploy":
            u = self.view.pick_unit((mx, my), self.pick_filter())
            if u is not None:
                return u.cell
        return self.ground_cell(mx, my)

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
            self.hover_cell = self.ground_cell(*ev.pos) if self.picked else self.cell_at(*ev.pos)
            self.pick = (self.view.pick_unit(ev.pos, self.pick_filter()) if self.unit_target()
                         else self.view.pick_unit(ev.pos, reach=0)) if self.phase == "battle" else None
            if self.route is not None and getattr(ev, "buttons", (0, 0, 0))[2]:
                self._extend_route(self.hover_cell)
        elif ev.type == pygame.MOUSEWHEEL:
            self._autocast_wheel(ev.y)
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            self.mouse = ev.pos
            if ev.button in (4, 5) or self._autocast_click(ev.pos, ev.button):
                return
            if self.phase == "deploy":
                self._deploy_click(ev.pos, ev.button)
            elif ev.button == 3 and pygame.key.get_mods() & pygame.KMOD_SHIFT and self._waypoint(ev.pos):
                pass
            else:
                self._click(ev.pos, ev.button)
                self._start_route(ev.pos, ev.button)
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 3 and self.route is not None:
            self._finish_route()
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.phase == "deploy":
            self._deploy_release(ev.pos)
        elif ev.type == pygame.KEYDOWN:
            self._key(ev.key)

    # ---------- маршрут, выбранный игроком ----------

    def _start_route(self, pos, button):
        """ПКМ по пустой клетке — уже приказ «идти»; если повести мышью с зажатой кнопкой — рисуется маршрут."""
        u = self.selected
        cell = self.cell_at(*pos)
        if button != 3 or not u or cell is None or not u.order or u.order["type"] != "move":
            return
        self.route = [cell]

    def _extend_route(self, cell):
        if cell is None or not self.route or cell == self.route[-1]:
            return
        g = self.combat.grid
        cur = self.route[-1]
        while cur != cell:                       # быстрое движение мыши — клетки между ними тоже
            cur = (cur[0] + sign(cell[0] - cur[0]), cur[1] + sign(cell[1] - cur[1]))
            blocker = self.combat.unit_at(cur)
            if not g.passable(cur) or (blocker is not None and blocker.obj):
                return                           # стена или бочка — маршрут дальше не тянется
            if len(self.route) >= 2 and cur == self.route[-2]:
                self.route.pop()                 # повёл назад — стираем хвост
            else:
                self.route.append(cur)

    def _finish_route(self):
        route, self.route = self.route, None
        u = self.selected
        if not u or not route or len(route) < 2:
            return
        ok, msg = self.combat.order_path(u, route)
        if not ok:
            self.say(msg)

    def _waypoint(self, pos):
        """Shift+ПКМ — добавить точку к маршруту: путь продлевается от конца текущего приказа."""
        u, cell = self.selected, self.cell_at(*pos)
        if not u or cell is None or self.targeting or self.combat.unit_at(cell) not in (None, u):
            return False
        o = u.order or {}
        start = o.get("cells") if o.get("type") == "path" else ([o["cell"]] if o.get("type") == "move" else [])
        ok, msg = self.combat.order_path(u, list(start) + [cell])
        if not ok:
            self.say(msg)
        return True

    def route_preview(self):
        """Клетки рисуемого маршрута от героя и время на него."""
        u = self.selected
        if not u or not self.route:
            return None, 0.0
        cells = MV.fill_path(self.combat, u, self.route)
        if not cells:
            return None, 0.0
        return cells, MV.path_time(self.combat, u, cells)

    # ---------- автокаст ----------

    def toggle_autocast(self, idx):
        u = self.selected
        if u and idx < len(u.skills):
            st = u.autocast[u.skills[idx]]
            st["on"] = not st["on"]
            self.say(f"{u.skill_defs[u.skills[idx]]['name']}: автокаст {'вкл' if st['on'] else 'выкл'}")

    def _autocast_click(self, pos, button):
        """Клики по редактору и полоскам автокаста. True — клик обработан."""
        if self.editor:
            rect = self.editor.get("rect")
            if rect and rect.collidepoint(pos):
                self.editor["editor"].click(pos)
                return True
            self.editor = None
            return True
        for r, idx in self.view.auto_rects:
            if r.collidepoint(pos):
                if button == 3:
                    self.toggle_autocast(idx)
                else:
                    u = self.selected
                    sid = u.skills[idx]
                    self.targeting = None
                    self.editor = {"unit": u, "idx": idx, "rect": None,
                                   "editor": AutocastEditor(u.skill_defs[sid], u.autocast[sid], self.data.tags)}
                return True
        if button == 3:
            for r, idx in self.view.skill_rects:
                if r.collidepoint(pos):
                    self.toggle_autocast(idx)
                    return True
        return False

    def _autocast_wheel(self, dy):
        u = self.selected
        for r, idx in self.view.skill_rects:
            if r.collidepoint(self.mouse) and u:
                adjust_first_value(u.autocast[u.skills[idx]], 1 if dy > 0 else -1)
                return

    def _key(self, key):
        c = self.combat
        if key in SKILL_KEYS and pygame.key.get_mods() & pygame.KMOD_CTRL:
            self.toggle_autocast(SKILL_KEYS[key])
            return
        if key == pygame.K_ESCAPE and self.editor:
            self.editor = None
            return
        if c.result:
            if self.run_mode:
                if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    self.finish()
            elif key == pygame.K_r:
                self.start(self.encounter_index)
            elif key == pygame.K_n:
                self.start(self.encounter_index + 1)
            return
        if self.cheats and key == pygame.K_F7:
            for u in c.heroes(PLAYER):
                if u.alive:
                    u.ap, u.pp = u.ap_max, u.pp_max
                    u.cooldowns.clear()
            self.say("Отряд готов: полные AP, шкалы, без перезарядок")
            return
        if self.cheats and key == pygame.K_F8 and self.phase == "battle":
            c.win_now()
            return
        if key == pygame.K_F10 and self.tutorial:
            self.tutorial.skip()
            return
        if key == pygame.K_SPACE and self.tutorial and self.tutorial.wants_ack() and self.phase == "battle":
            self.tutorial.ack()
            return
        if key == pygame.K_F9:                      # пиксельный пилот огня и льда ↔ старые эффекты
            self.say("Эффекты огня и льда: " + self.view.pix.toggle())
            return
        if key == pygame.K_F5 and not self.run_mode:
            self.start(self.encounter_index)
        elif key == pygame.K_F6 and not self.run_mode:
            self.start(self.encounter_index + 1)
        elif key == pygame.K_TAB:
            squad = [u for u in c.fighters(PLAYER) if not u.summon]
            if squad:
                i = squad.index(self.selected) + 1 if self.selected in squad else 0
                self._select(squad[i % len(squad)])
        elif pygame.K_1 <= key <= pygame.K_4:
            squad = c.heroes(PLAYER)
            i = key - pygame.K_1
            if i < len(squad) and squad[i].alive:
                self._select(squad[i])
        elif self.phase == "deploy":
            if key == pygame.K_SPACE:                # старт боя — Пробел
                self.begin_battle()
            elif key == pygame.K_ESCAPE:
                self.picked = None
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER) and c.intermission > 0:
            c.call_wave()
            self.say("Волна вызвана")
        elif key == pygame.K_SPACE:
            self.paused = not self.paused
        elif key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
            self.slowmo = not self.slowmo
        elif key in SPEED_KEYS:
            self.speed_idx = SPEED_KEYS[key]
        elif key == pygame.K_ESCAPE:
            if self.targeting:
                self.targeting = None
            else:
                self.selected = None
        elif key in SKILL_KEYS:
            self._skill_key(SKILL_KEYS[key])

    def _select(self, u):
        self.selected = u
        self.targeting = None

    def _squad_click(self, pos):
        for r, u in self.view.squad_rects:
            if r.collidepoint(pos) and u.alive:
                self._select(u)
                return True
        return False

    # ---------- расстановка ----------

    def _deploy_click(self, pos, button):
        if button == 1 and self.view.start_button and self.view.start_button.collidepoint(pos):
            self.begin_battle()
            return
        if self._squad_click(pos):
            return
        if button == 3:
            self.picked = None
            return
        # героя берём с притяжением к фигурке; уже взятого ставим в клетку земли под курсором
        cell = self.ground_cell(*pos) if self.picked else self.cell_at(*pos)
        if cell is None or button != 1:
            return
        c = self.combat
        u = c.unit_at(cell)
        if u and u.team == PLAYER and not u.summon and not u.obj:
            if self.picked and self.picked is not u:
                c.redeploy(self.picked, cell)  # клик по своему — поменять местами
                self.picked = None
            elif self.picked is u:
                self.picked = None
            else:
                self.selected = self.picked = u
                self.drag_start = pos
            return
        if self.picked:
            if not c.redeploy(self.picked, cell):
                self.say("Ставить можно только в зелёной зоне")
            self.picked = None

    def _deploy_release(self, pos):
        if not self.picked or not self.drag_start:
            return
        dragged = self.dragging
        self.drag_start = None
        if not dragged:
            return  # это был клик: ждём второй клик по клетке
        cell = self.ground_cell(*pos)           # бросаем в клетку под курсором — фигурки рядом не мешают
        if cell and cell != self.picked.cell and not self.combat.redeploy(self.picked, cell):
            self.say("Ставить можно только в зелёной зоне")
        self.picked = None

    # ---------- бой ----------

    def _skill_key(self, idx):
        u = self.selected
        if not u or idx >= len(u.skills):
            return
        sid = u.skills[idx]
        if self.targeting == sid:
            self.targeting = None
            return
        if self.cfg["skills_only_in_pause"] and not self.paused:
            self.say("Навыки — только на паузе")
            return
        sk = u.skill_defs[sid]
        if sk["target"] == "self":
            ok, msg = self.combat.order_skill(u, sid, u)
            if ok and self.tutorial:
                self.tutorial.ordered(sid)
            if not ok:
                self.say(msg)
            return
        ok, msg = self.combat.check_skill(u, sid, u if sk["target"] != "enemy" else None)
        if not ok and msg in ("Не хватает AP", "Перезарядка"):
            self.say(msg)
            return
        self.targeting = sid

    def _click(self, pos, button):
        if self._squad_click(pos):
            return
        for r, foe in self.view.enemy_rects:            # строка в списке врагов — атаковать его
            if r.collidepoint(pos):
                if self.selected and foe.alive:
                    ok, msg = self.combat.order_attack(self.selected, foe)
                    if not ok:
                        self.say(msg)
                return
        for r, idx in self.view.skill_rects:
            if r.collidepoint(pos) and button == 1:
                self._skill_key(idx)
                return
        cell = self.cell_at(*pos)
        if cell is None or self.combat.result:
            return
        c = self.combat
        target_unit = c.unit_at(cell)

        if self.targeting:
            if button == 3:
                self.targeting = None
                return
            sk = self.selected.skill_defs[self.targeting]
            target = target_unit if sk["target"] in ("enemy", "ally") else cell
            if target is None:
                self.say("Нужна цель-юнит")
                return
            ok, msg = c.order_skill(self.selected, self.targeting, target)
            if ok and self.tutorial:
                self.tutorial.ordered(self.targeting)
            if ok:
                self.targeting = None
            else:
                self.say(msg)
            return

        if button == 1:                          # выбор своего — с притяжением к фигурке рядом с курсором
            mine = self.view.pick_unit(pos, lambda v: v.team == PLAYER and not v.summon and not v.obj)
            if mine is not None:
                self._select(mine)
                return
        u = self.selected
        if not u:
            return
        hit = self.view.pick_unit(pos, lambda v: u.is_enemy(v), reach=0)   # атака — курсор прямо на враге
        if hit is not None:
            target_unit = hit
        if isinstance(target_unit, Unit) and u.is_enemy(target_unit):
            ok, msg = c.order_attack(u, target_unit)
        elif target_unit is None:
            ok, msg = c.order_move(u, cell)
        else:
            return
        if not ok:
            self.say(msg)
