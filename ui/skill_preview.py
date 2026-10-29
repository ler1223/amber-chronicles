"""Превью навыка в подготовке героя: маленький бой на манекенах, навык (с выбранной ступенью ветки) повторяется по
кругу — видно анимацию, снаряды, эффекты и что именно он делает.

Сцена готовится под навык: для «Вспышки» поле уже горит, для некроманта лежат трупы, для фитиля стоят бочки,
для «Реактива» на манекене висят теги, для дозора и капкана манекен сам заходит в зону и т.п.
Рисуется тем же BattleView, что и бой; камера проекции смотрит в окно превью (ui/projection.configure).
"""
import copy

from sim.build import build_proto
from sim.combat import Combat
from sim.teams import ENEMY
from ui import projection as P
from ui.battle_view import BattleView

CYCLE = 4.2          # сек на один показ навыка
CAST_AT = 0.45       # когда герой начинает применять навык
MAIN, SIDE, BACK = (6, 3), (6, 2), (7, 4)       # манекены
ALLY = (5, 2)
ZOOM = 70            # пикселей на клетку в окне превью


class PreviewScene:
    """Что BattleView спрашивает у сцены боя."""
    phase = "battle"
    hover_cell = None
    dragging = False
    targeting = None
    selected = None
    picked = None
    mouse = (0, 0)

    def __init__(self):
        self.combat = None


def flat_effects(sk):
    out = []
    for e in sk["effects"]:
        out.append(e)
        if e["type"] == "delay":
            out += e["effects"]
    return out


class SkillPreview:
    def __init__(self, data, rect):
        self.data = data
        self.rect = rect
        self.view = BattleView(data)
        self.scene = PreviewScene()
        enc = {"id": "preview", "name": "Тренировка", "kind": "normal", "chapter": "_preview",
               "map": ["." * 10 for _ in range(6)], "player_spawn": [[3, 3], [3, 1], [0, 0], [0, 5]],
               "deploy_max_x": 9,
               "enemies": [{"type": "slime", "pos": list(MAIN)}, {"type": "slime", "pos": list(SIDE)},
                           {"type": "slime", "pos": list(BACK)}]}
        self._data = copy.copy(data)
        self._data.encounters = [enc]
        self.proto = None
        self.sid = None
        self.t = 0.0
        self.cast_done = False
        self.title = ""

    # ---------- что показываем ----------

    def show(self, cls, path, branches, sid, title=""):
        """Герой cls на пути path со ступенями branches (только этого навыка) применяет навык sid."""
        self.proto = build_proto(self.data, cls, branches=branches, path=path)
        self.cls, self.sid, self.title = cls, sid, title
        self.restart()

    def restart(self):
        self.t, self.cast_done, self.acc = 0.0, False, 0.0
        sk = self.proto["skill_defs"][self.sid]
        ally = build_proto(self.data, "warrior")
        c = Combat(self._data, 0, seed=3, squad=[{"cls": self.cls, "proto": self.proto},
                                                  {"cls": "warrior", "proto": ally}])
        c.ais = []
        c.autocaster.update = lambda dt: None
        self.c = c
        self.scene.combat = c
        self.caster, self.ally = c.heroes()[0], c.heroes()[1]
        self.foes = c.fighters(ENEMY)
        for f in self.foes:                  # манекены: крепкие и не бьют в ответ
            f.max_hp = f.hp = 420
            f.atk_damage = 0
            f.atk_cd = f.attack_timer = 999.0
        self.caster.ap_max = max(self.caster.ap_max, sk["ap"])
        self.caster.ap = self.caster.ap_max
        self.caster.pp = self.caster.pp_max
        self.ally.autocast = {k: {"on": False, "conds": []} for k in self.ally.autocast}
        self._prepare(sk)
        self.view.reset(c)

    def _put(self, u, cell):
        u.cell = u.prev_cell = tuple(cell)

    def _prepare(self, sk):
        """Расставить сцену под навык."""
        c, me, ally, (main, side, _) = self.c, self.caster, self.ally, self.foes
        types = {e["type"] for e in flat_effects(sk)}
        melee = sk["range"] <= 1 or types & {"push", "toss"} and sk["target"] != "self"
        if melee or sk["target"] == "self" and sk.get("radius", 0) >= 1 and types & {"push", "damage", "corpse"}:
            self._put(me, (5, 3))
            self._put(ally, (4, 1))
        if "rush" in types:
            self._put(me, (2, 3))
        if "guard" in types:
            self._put(me, (2, 4))
        if types & {"extra_attack", "focus"} or "atk_tag" in {e.get("stat") for e in flat_effects(sk)}:
            self._put(ally, (5, 3))
            self._put(me, (3, 1))
        if types & {"heal", "delay", "life_transfer", "rewind"} and sk["target"] == "ally":
            ally.hp = ally.max_hp // 2
        if "detonate" in types or "spread_fire" in types:
            for p in (MAIN, SIDE, BACK, (7, 3)):
                cell = c.grid.get(p)
                cell.hazard, cell.hazard_time, cell.hazard_team = "fire", 6.0, None
            for f in (main, side):
                f.statuses["fire"] = 4.0
        if "corpse" in types:
            for p in ((6, 4), (5, 4), (7, 2)):
                c.corpses.append({"cell": p, "left": 14.0, "name": "манекен"})
        if "reagent" in types:
            for tag in ("water", "oil", "poison"):
                main.statuses[tag] = 4.0
        if "fuse" in types:
            for p in ((5, 2), (5, 4)):
                o = c.spawn_object("barrel_powder", p)
                o.owner = me
        if "shatter" in types:
            for p in ((5, 2), (5, 3), (5, 4)):
                o = c.spawn_object("ice_wall", p)
                o.owner, o.life = me, 10
        if types & {"merge", "life_transfer"}:
            ally.tethered_by, ally.tether_time = me, 15.0
        if "rewind" in types:
            if sk["target"] == "ally":
                ally.history = [(c.time - 3.0, (2, 1), ally.max_hp)]
                self._put(ally, (5, 3))
            else:
                main.history = [(c.time - 3.0, (9, 3), main.hp)]
        if "toss" in types:
            self._put(main, (6, 3))

    def _target(self, sk):
        kind = sk["target"]
        types = {e["type"] for e in flat_effects(sk)}
        if kind == "enemy":
            return self.foes[0]
        if kind == "ally":
            return self.ally
        if kind == "self":
            return self.caster
        if "toss" in types:
            return (8, 1)
        if "regroup" in types:
            return (4, 4)
        if "watch" in types or "trap" in types or "wall" in types:
            return (5, 3)
        if sk.get("free_cell") or "teleport" in types:
            return (5, 4)
        if "corpse" in types:
            return (6, 4)
        if "rush" in types:
            return MAIN
        return MAIN

    def _after_cast(self, sk):
        """Дозор и капкан: манекен сам идёт в зону."""
        types = {e["type"] for e in flat_effects(sk)}
        if types & {"watch", "trap"}:
            self.c.order_move(self.foes[0], (3, 3))

    # ---------- кадр ----------

    def update(self, dt):
        if self.proto is None:
            return
        P.configure(self.rect.center, ZOOM)
        self.t += dt
        c = self.c
        if self.t >= CAST_AT and not self.cast_done:
            self.cast_done = True
            sk = self.caster.skill_defs[self.sid]
            ok, _ = c.order_skill(self.caster, self.sid, self._target(sk))
            if ok:
                self.view.vfx.after(0.6 + sk.get("cast", 0), lambda sk=sk: self._after_cast(sk))
        self.acc += min(dt, 0.1)          # накопитель: при 60–144 кадрах в секунду шаг боя (0.05 с) длиннее кадра
        while self.acc >= c.dt:
            self.acc -= c.dt
            c.step()
        self.view.consume(c.events)
        c.events.clear()
        self.view.update(dt, dt)
        if self.t >= CYCLE:
            self.restart()

    def plane(self):
        return self.view.plane()

    @property
    def vfx(self):
        return self.view.vfx

    def draw_layers(self, world, units, ui):
        """С OpenGL: земля — плоская карта (плоскость кладёт видеокарта), фигурки — в units, надписи — в ui."""
        if self.proto is None:
            return
        P.configure(self.rect.center, ZOOM)
        v = self.view
        v.gl_camera = True
        v.draw_ground(world, self.scene, warp=False)
        units.fill((0, 0, 0, 0))
        v._draw_world(units, self.scene)
        self._draw_overlay(ui)

    def draw_cpu(self, surf):
        """Без OpenGL: всё на одну поверхность (её потом закроет интерфейс, кроме окна превью)."""
        if self.proto is None:
            return
        P.configure(self.rect.center, ZOOM)
        v = self.view
        v.gl_camera = False
        v.draw_ground(surf, self.scene, warp=True)
        v._draw_world(surf, self.scene)
        if v._cpu_tex is None:
            from ui.vfx_textures import make_textures
            v._cpu_tex = make_textures()
        v.vfx.draw_cpu(surf, v._cpu_tex, v._cpu_cache, props=v.props)
        self._draw_overlay(surf)

    def _draw_overlay(self, surf):
        clip = surf.get_clip()
        surf.set_clip(self.rect)
        for u in self.c.units:
            if u.alive and u.merged <= 0:
                self.view._draw_hud(surf, u)
        self.view._draw_fx(surf)
        surf.set_clip(clip)
