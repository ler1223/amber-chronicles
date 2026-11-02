"""Отрисовка боя: поле в виде 3/4, спрайты с процедурной анимацией, частицы, панели. Состояние боя только читается.

Порядок кадра: земля → подсветки клеток → (укрытия и юниты по глубине) → частицы → полоски HP/пипсы/надписи → панели.
"""
import math

import pygame

from sim import autocast as AC
from sim.combat import ENEMY, NEUTRAL, PLAYER
from sim.grid import PERMANENT, cheb
from ui import theme as T
from sim import movement as MV
from sim import stats as ST
from ui import icons as IC
from ui import projection as P
from ui.ground import GroundPainter, prop_image
from ui.marks import MarkLayer
from ui.fxlab.router import FxRouter
from ui.props import load_props
from ui.sprites import DRAWERS, SpriteBank
from ui.vfx import Light, VfxWorld, resolve_color
from ui.vfx_textures import make_textures

SKILL_KEYS = "QWERTYUIOP"
RIGHT_X = 924
BOTTOM_Y = 608
PANEL_Y = 64

BUFF_TEXT = {
    "armor": lambda v: f"+{v:g} брони", "atk_mult": lambda v: f"урон ×{v:g}", "atk_speed": lambda v: "быстрые атаки",
    "dmg_taken": lambda v: ("уязвим" if v > 1 else "стойкость"), "thorns": lambda v: "шипы",
    "regen": lambda v: f"+{v:g} HP/с", "slow": lambda v: ("замедлен" if v > 1 else "ускорен"),
    "immune": lambda v: "иммунитет", "stealth": lambda v: "в тени", "ap_rate": lambda v: "AP быстрее",
    "atk_tag": lambda v: "клинок с ядом" if v == "poison" else f"атаки: {v}",
}
BUFF_GOOD = {"atk_speed", "thorns", "regen", "immune", "stealth", "ap_rate", "atk_tag"}
ARROW = (235, 225, 200)
LUNGE_T, HIT_T = 0.18, 0.16
TOSS_T = 0.32              # бросок тарана: столько летит брошенный
# события, которые показываются по прилёте снаряда (а не в момент выстрела)
DELAYED = {"damage", "heal", "status", "reaction", "passive", "link", "line", "buff", "execute", "thorns", "interrupt",
           "stun", "taunt", "shield", "cleanse", "fizzle", "death", "cell_reaction", "backstab", "sleep", "pull",
           "refresh", "revive", "summon", "knockback", "mine", "charm", "fall", "armor_break", "rise"}
ARENA_COLORS = {"eruption": (255, 120, 40), "lightning": (170, 180, 255), "avalanche": (200, 230, 255),
                "tide": (90, 160, 255), "wind": (220, 230, 240), "sandstorm": (220, 190, 120)}


def buff_good(stat, value):
    if stat in ("armor", "atk_mult"):
        return value > (0 if stat == "armor" else 1)
    if stat == "slow":
        return value < 1
    return stat in BUFF_GOOD or (stat == "dmg_taken" and value < 1)


def fit(s, size, width):
    """Обрезает строку по ширине, добавляя «…»."""
    f = T.font(size)
    if f.size(s)[0] <= width:
        return s
    while s and f.size(s + "…")[0] > width:
        s = s[:-1]
    return s + "…"


class Fx:
    """Короткоживущий визуальный эффект; время — игровое, на паузе замирает."""

    def __init__(self, kind, ttl, **kw):
        self.kind = kind
        self.ttl = ttl
        self.age = 0.0
        self.__dict__.update(kw)

    @property
    def k(self):
        return min(1.0, self.age / self.ttl)


class Anim:
    """Процедурная анимация юнита: куда смотрит, выпад, вздрагивание от удара."""

    def __init__(self, u):
        self.facing = 1 if u.team == PLAYER else -1
        self.lunge = 0.0
        self.lunge_dir = (0.0, 0.0)
        self.hit = 0.0
        self.toss = 0.0        # бросок: сколько ещё лететь по дуге


def FR(pos):
    """Клетка на плоской карте земли (pygame.Rect)."""
    return pygame.Rect(P.flat_rect(pos))


class BattleView:
    def __init__(self, data):
        self.data = data
        self.fx = []
        self.log = []
        # HD-2D: земля рисуется на плоской карте (вид строго сверху), видеокарта кладёт её на наклонную плоскость
        self.flat = pygame.Surface((P.FLAT_W, P.FLAT_H))
        self.overlay = pygame.Surface((P.FLAT_W, P.FLAT_H), pygame.SRCALPHA)
        self.painter = GroundPainter(data)
        self._scaled = {}          # (картинка, масштаб) → увеличенный спрайт
        self._route_unit = None
        self.enemy_rects = []      # строки списка врагов справа: (прямоугольник, юнит)
        self.hover_unit = None     # юнит под курсором в списке — подсвечен на поле
        self.icon_tips = []        # (значок в панели, подпись)
        self._prop_imgs = {}
        self.squad_rects = []
        self.skill_rects = []
        self.auto_rects = []
        self.start_button = None
        self.clock = 0.0
        self.sprites = SpriteBank()
        self.props = load_props()
        self.vfx = VfxWorld(props={n: i for i, n in enumerate(self.props)})
        self.marks = MarkLayer((P.FLAT_W, P.FLAT_H), self.props)
        self.anims = {}
        self.gone = set()          # враги, уже рассыпавшиеся на частицы
        self.fallen = set()        # павшие герои — лежат
        self._cpu_tex = None
        self._cpu_cache = {}
        self._ground = None
        self.sprite_rects = []     # (rect, unit) в порядке отрисовки — для клика по спрайту
        self.combat = None
        self._emit_acc = {}
        self._dim = {}
        self._line = ("pierce_line", (235, 240, 255), 1.0, 0)
        self.gl_camera = False     # рисуем через OpenGL — интерфейс над юнитами следует за камерой
        self.pix = FxRouter(self)  # стиль эффектов огня и льда: пиксельный или стили ui/fxlab (art_style.md)

    # ---------- события симуляции → эффекты ----------

    def reset(self, combat):
        P.set_board(combat.grid.w, combat.grid.h)       # доска любого размера: камера и плоская карта под неё
        if self.flat.get_size() != (P.FLAT_W, P.FLAT_H):
            self.flat = pygame.Surface((P.FLAT_W, P.FLAT_H))
            self.overlay = pygame.Surface((P.FLAT_W, P.FLAT_H), pygame.SRCALPHA)
            self.marks = MarkLayer((P.FLAT_W, P.FLAT_H), self.props)
        self.combat = combat
        self.grid = combat.grid
        self.banner = None         # крупная надпись над полем: волна, передышка, фаза босса
        self.fx.clear()
        self.log.clear()
        self.vfx.clear()
        self.anims.clear()
        self._emit_acc.clear()
        self.gone.clear()
        self.fallen.clear()
        self.marks.clear()
        self._prop_imgs.clear()
        self.pix.reset()
        self.relayout()

    def relayout(self):
        """Ширина холста изменилась: доска по центру свободной части, панель — у правого края."""
        global RIGHT_X
        T.GRID_X, RIGHT_X = T.battle_rects()
        P.configure((T.GRID_X + T.GRID_W // 2, 362), P.PX_PER_CELL)
        cx = T.GRID_X + T.GRID_W // 2
        self.vfx.screen.center = (float(cx), 360.0)
        self.vfx.screen.radial_center = (float(cx), 360.0)
        self._cpu_tex = None
        self._ground = None

    def anim(self, u):
        a = self.anims.get(u.id)
        if a is None:
            a = self.anims[u.id] = Anim(u)
        return a

    def ground_pos(self, u):
        """Где юнит стоит на земле (в клетках), с учётом шага между клетками."""
        ax, ay = P.cell_ground(u.prev_cell)
        bx, by = P.cell_ground(u.cell)
        t = u.move_t
        t = t * t * (3 - 2 * t)
        return ax + (bx - ax) * t, ay + (by - ay) * t

    def feet_pos(self, u):
        x, y, _ = P.project(*self.ground_pos(u))
        return x, y

    def flat_feet(self, u):
        return P.ground_to_flat(*self.ground_pos(u))

    def depth(self, u):
        """Масштаб фигурки по глубине: ближе к камере — крупнее."""
        return P.scale_at(self.ground_pos(u)[1])

    def scaled(self, img, k):
        """Спрайт в масштабе глубины (ступени по 0.04 — кэш не раздувается, пиксели остаются чёткими)."""
        k = round(k * 25) / 25
        if abs(k - 1) < 0.02:
            return img
        key = (id(img), k)
        out = self._scaled.get(key)
        if out is None or out[0] is not img:
            if len(self._scaled) > 3000:
                self._scaled.clear()
            out = self._scaled[key] = (img, pygame.transform.scale(
                img, (max(1, round(img.get_width() * k)), max(1, round(img.get_height() * k)))))
        return out[1]

    def sprite_of(self, u, flip=False, flash=False):
        if u.obj:                      # объект поля: своя моделька (assets/sprites/<id>.png или заглушка)
            return self.sprites.get([u.proto_id], "object", u.color, False, flip, flash, {"object": u.obj.get("art")})
        if u.form:                     # облик друида: свой спрайт (druid_bear.png / bear.png) или заглушка зверя
            return self.sprites.get([f"{u.proto_id}_{u.form}", u.form], u.form, u.color, u.boss, flip, flash)
        names = [u.proto.get("path"), u.proto_id]
        look = u.proto.get("look")
        kind = u.proto_id if u.proto_id in DRAWERS or look else u.role
        return self.sprites.get(names, kind, u.color, u.boss, flip, flash, look)

    def unit_h(self, u):
        return self.sprite_of(u).get_height() * self.depth(u)

    def unit_pos(self, u):
        """Центр тела — сюда летят снаряды и отсюда всплывают надписи."""
        x, y = self.feet_pos(u)
        return x, y - self.unit_h(u) * 0.42

    def tag_color(self, tag, default=(255, 255, 255)):
        return tuple(self.data.tags[tag]["color"]) if tag else default

    def float_text(self, u_or_pos, s, color, size=16, ttl=1.0, dy=0):
        if isinstance(u_or_pos, tuple):
            x, y = u_or_pos
        else:
            x, y = self.unit_pos(u_or_pos)
            y -= self.unit_h(u_or_pos) * 0.3
        # раскладываем одновременные надписи над юнитом, чтобы не слипались
        busy = sum(1 for f in self.fx if f.kind == "text" and f.age < 0.25 and abs(f.x - x) < 30 and abs(f.y0 - y) < 60)
        self.fx.append(Fx("text", ttl, x=x, y0=y - 20 - dy - busy * 16, s=s, color=color, size=size))

    def _face(self, u, target_x):
        x, _ = self.feet_pos(u)
        if abs(target_x - x) > 4:
            self.anim(u).facing = 1 if target_x > x else -1

    def _ctx(self, caster=None, target=None, center=None, cells=None, color=None, scale=1.0, tier=0):
        """Точки для таймлайна эффекта. Функции — чтобы эффект, сыгранный позже, взял актуальную позицию."""
        ctx = {"color": color, "scale": scale, "tier": tier, "caster_unit": caster, "target_unit": target}
        if caster is not None:
            ctx["caster"] = self.unit_pos(caster)
            ctx["caster_ground"] = self.feet_pos(caster)
            ctx["caster_fn"] = lambda: self.unit_pos(caster)
            ctx["caster_ground_fn"] = lambda: self.feet_pos(caster)
        if target is not None:
            ctx["target"] = self.unit_pos(target)
            ctx["target_ground"] = self.feet_pos(target)
            ctx["target_fn"] = lambda: self.unit_pos(target)
            ctx["target_ground_fn"] = lambda: self.feet_pos(target)
        elif center is not None:
            gx, gy = T.cell_feet(center)
            ctx["target_ground"] = (gx, gy)
            ctx["target"] = T.cell_center(center)
        elif caster is not None:
            ctx["target"], ctx["target_ground"] = ctx["caster"], ctx["caster_ground"]
        ctx["cells"] = [T.cell_feet(p) for p in cells] if cells else [ctx.get("target_ground")]
        g = P.unproject(*ctx["target_ground"]) if ctx.get("target_ground") else None
        if g is not None:                       # перспектива: вдали эффект мельче, вблизи крупнее
            ctx["scale"] = scale * P.scale_at(g[1])
        if "caster" in ctx and "target" in ctx:
            (ax, ay), (bx, by) = ctx["caster"], ctx["target"]
            ctx["dir"] = math.degrees(math.atan2(by - ay, bx - ax)) if (ax, ay) != (bx, by) else 0.0
        return ctx

    def consume(self, events):
        """События одного кадра симуляции. После атаки/навыка со снарядом связанные события (урон, реакции,
        смерть) показываются по прилёте — откладываются на время полёта."""
        delay = 0.0
        for e in events:
            t = e["t"]
            if t == "log":
                self.log.append((e["text"], e["color"]))
                self.log = self.log[-60:]
            elif t in ("attack", "skill"):
                delay = self._action(e)
            elif delay > 0 and t in DELAYED:
                self.vfx.after(delay, lambda e=e: self._event(e))
            else:
                self._event(e)

    def skill_spec(self, sid, sk):
        """Описание визуала навыка с учётом ветки: у ветки может быть свой вид (branches.A/B), ступень и руны
        делают эффект крупнее. Возвращает (spec, ступень)."""
        lib = self.vfx.lib
        spec = lib["skills"].get(sid if sid else "_on_death") or lib["defaults"].get(sk["target"] if sk else "self", {})
        tier = 0
        if sk and sk.get("branch"):
            b, tier = sk["branch"]
            over = spec.get("branches", {}).get(b)
            if over:
                spec = dict(spec, **over)
        return spec, tier

    def _action(self, e):
        """Атака или навык: снаряд и удар по цели. Возвращает время до попадания."""
        lib = self.vfx.lib
        if e["t"] == "attack":
            src, dst = e["src"], e["dst"]
            a, b = self.unit_pos(src), self.unit_pos(dst)
            self._face(src, b[0])
            if e["kind"] == "melee":
                an = self.anim(src)
                d = math.dist(a, b) or 1
                an.lunge, an.lunge_dir = LUNGE_T, ((b[0] - a[0]) / d, (b[1] - a[1]) / d)
                spec, color = lib["attacks"]["melee"], self.tag_color(e["tag"], (255, 250, 240))
            elif src.role == "ranged":
                kind = lib["unit_attacks"].get(src.proto_id, "arrow")
                spec, color = lib["attacks"][kind], self.tag_color(e["tag"], ARROW)
            else:
                spec, color = lib["attacks"]["bolt"], self.tag_color(e["tag"], T.mix(src.color, (255, 255, 255), 0.4))
            d = self.pix.attack(e, a, b)
            if d is not None:
                return d
            ctx = self._ctx(src, dst, color=color)
            return self._launch(spec, ctx, a, b, color, melee=e["kind"] == "melee")
        u = e["unit"]
        sid = e["skill"]
        sk = u.skill_defs.get(sid) if sid else None
        tags = [eff.get("tag") for eff in (sk["effects"] if sk else []) if eff.get("tag")]
        tag = tags[0] if tags else None
        spec, tier = self.skill_spec(sid, sk)
        color = tuple(spec["color"]) if spec.get("color") else self.tag_color(tag, (255, 230, 150))
        override = spec.get("by_tag", {}).get(tag)
        if override:
            spec = dict(spec, impact=override)
        radius = sk.get("radius", 0) if sk else 1
        center = e["center"]
        cells = self._cells_around(center, radius) if radius else None
        tunit = e["target"] if e["target"] is not None and e["target"] is not u else None
        scale = spec.get("scale", 1.0) * (1 + 0.14 * tier + 0.05 * len(sk.get("runes", []) if sk else []))
        ctx = self._ctx(u, tunit, center if tunit is None and center != u.cell else None, cells, color, scale, tier)
        if tunit is not None or center != u.cell:
            self._face(u, ctx["target"][0])
        if sk:
            name = sk["name"] + (" ·авто" if e.get("auto") else "")
            self.float_text(u, name, (255, 235, 170), 14, ttl=1.0, dy=10)
            for p in cells or []:
                self.fx.append(Fx("cell", 0.45, pos=p, color=color))
        if spec.get("release") and not self.pix.own_release(sid):
            self.vfx.play(spec["release"], ctx)
        self._line = (spec.get("line_fx", "pierce_line"), color, scale, tier)   # для события «line» этого навыка
        far = tunit is not None or center != u.cell
        d = self.pix.skill(u, sk, spec, ctx, color, far, radius, tier, sid)
        if d is not None:
            return d
        return self._launch(spec if far else dict(spec, travel=None), ctx, ctx["caster"], ctx["target"], color)

    def _launch(self, spec, ctx, a, b, color, melee=False):
        impact = spec.get("impact")
        tr = spec.get("travel")
        extra = spec.get("delay", 0.0)          # удар таймлайна наступает не сразу (стрелы ещё падают с неба)
        if tr:
            col = tuple(tr["color"]) if tr.get("color") else color
            if tr.get("to") == "ground":
                b = ctx["target_ground"]
            if tr.get("from") == "sky":
                off = tr.get("sky", [-140, -560])
                a = (b[0] + off[0], b[1] + off[1])
            scale = ctx.get("scale", 1.0)
            return extra + self.vfx.projectile(
                a, b, tr.get("speed", 800), tr.get("head"), tr.get("trail"), col, tr.get("arc", 0),
                tr.get("head_scale", 1.0) * scale, on_hit=(lambda: self.vfx.play(impact, ctx)) if impact else None,
                trail_rate=tr.get("trail_rate", 150), ribbon=tr.get("ribbon"), prop=tr.get("prop"),
                sfx=tr.get("sfx"), light=tr.get("light"), dur=tr.get("time"), stick=tr.get("stick"),
                prop_scale=tr.get("prop_scale", 2.0), spin=math.radians(tr.get("spin", 0)))
        if melee:      # удар — на пике выпада
            self.vfx.after(LUNGE_T * 0.45, lambda: self.vfx.play(impact, ctx))
            return LUNGE_T * 0.45
        if impact:
            self.vfx.play(impact, ctx)
        return extra

    def _event(self, e):
        t = e["t"]
        V = self.vfx
        pix = self.pix.event(e)      # пиксельный пилот нарисовал своё — старый эффект не играем
        if t == "damage":
            u = e["unit"]
            col = T.DMG_TO_PLAYER if u.team == PLAYER else T.DMG_TO_ENEMY
            if e["kind"] in ("dot", "hazard"):
                col = self.tag_color(e["tag"], (255, 150, 80))
            s = f"-{e['amount']}" if e["amount"] or not e["absorbed"] else f"щит -{e['absorbed']}"
            if e.get("blocked"):
                s += " (блок)"
            if e.get("cover"):
                s += " (укр.)"
            self.float_text(u, s, col, 18 if e["amount"] >= 15 else 15)
            if e["kind"] in ("melee", "ranged", "spell"):
                self.anim(u).hit = HIT_T
                if e["tag"] and not pix:
                    V.play(f"hit_{e['tag']}", self._ctx(target=u))
                if e["amount"] >= 30 and not pix:
                    V.play("big_hit", self._ctx(target=u))
            elif e["kind"] in ("dot", "hazard") and not pix:
                V.emit("burn", *self.unit_pos(u), count=3)
        elif t == "heal" and e["amount"] > 0:
            self.float_text(e["unit"], f"+{e['amount']}", T.HEAL, 16)
            V.play("heal_small", self._ctx(target=e["unit"], color=(140, 255, 170)))
        elif t == "status":
            tag = self.data.tags[e["tag"]]
            self.float_text(e["unit"], tag["name"], tuple(tag["color"]), 13, ttl=0.8)
            if not pix:
                V.play(f"status_{e['tag']}", self._ctx(target=e["unit"], color=tuple(tag["color"])))
        elif t == "reaction" and e.get("friendly"):     # союзник или среда: теги погасили друг друга
            self.float_text(e["unit"], e["name"], (190, 225, 245), 15, ttl=1.0, dy=10)
            V.play("cleanse_small", self._ctx(target=e["unit"], color=(190, 225, 245)))
        elif t == "reaction":
            u = e["unit"]
            c1, c2 = (self.tag_color(x) for x in e["tags"])
            x, y = self.unit_pos(u)
            if not pix:
                V.play(f"reaction_{e['id']}", self._ctx(target=u, color=T.mix(c1, c2, 0.5)))
            self.fx.append(Fx("text", 1.4, x=x, y0=y - 70, s=e["name"].upper() + "!", color=T.mix(c1, c2, 0.5),
                              size=24))
        elif t == "passive":
            u = e["unit"]
            same = next((f for f in self.fx if f.kind == "badge" and f.unit is u and f.name == e["name"]), None)
            if same:
                same.age, same.count = 0.0, same.count + 1
            else:
                self.fx.append(Fx("badge", 1.6, unit=u, name=e["name"], count=1))
            self.fx.append(Fx("pip", 0.8, unit=u, idx=u.pp))  # пипс, который только что потрачен
            V.play("passive", self._ctx(target=u))
            if e["kind"] == "intercede" and e["other"] is not None:
                self.fx.append(Fx("link", 0.6, src=u, dst=e["other"], color=T.PP_COLOR))
                V.emit_line("light_motes", self.unit_pos(u), self.unit_pos(e["other"]), T.PP_COLOR, step=14)
        elif t == "link":          # отскок/цепь: короткий снаряд от одной цели к другой; гроза — молния
            col = tuple(e["color"]) if e.get("color") else (230, 230, 255)
            ctx = self._ctx(e["src"], e["dst"], color=col)
            if col == tuple(self.data.tags["storm"]["color"]):
                V.bolt(ctx["caster"], ctx["target"], col, 8, 0.26, 0.2, 1)
                V.play("link_storm", ctx)
            else:
                V.projectile(ctx["caster"], ctx["target"], 1400, ["bolt_head", "bolt_halo"], None, col,
                             ribbon="link", on_hit=lambda: V.play("link_hit", ctx))
        elif t == "line":          # пронзание: лента через всю линию (вид — от навыка, что её выпустил)
            name, color, scale, tier = self._line
            ctx = self._ctx(e["src"], color=color, scale=scale, tier=tier)
            if e["cells"]:
                ctx["target"] = T.cell_center(e["cells"][-1])
                ctx["target_ground"] = T.cell_feet(e["cells"][-1])
                ctx["cells"] = [T.cell_feet(c) for c in e["cells"]]
            V.play(name, ctx)
        elif t == "buff" and e.get("fresh", True):
            good = buff_good(e["stat"], e["value"])
            self.float_text(e["unit"], BUFF_TEXT.get(e["stat"], lambda v: e["stat"])(e["value"]),
                            (150, 240, 160) if good else (255, 150, 120), 13, ttl=1.0)
            V.play("buff_good" if good else "buff_bad", self._ctx(target=e["unit"]))
        elif t == "execute":
            self.float_text(e["unit"], "КАЗНЬ", (255, 90, 80), 16, ttl=1.0, dy=12)
            V.play("big_hit", self._ctx(target=e["unit"], color=(255, 90, 80)))
        elif t == "thorns":
            self.fx.append(Fx("link", 0.4, src=e["unit"], dst=e["dst"], color=(200, 200, 210)))
        elif t == "interrupt":
            self.float_text(e["unit"], "Каст сорван!", T.CAST, 15)
            V.emit("hit_sparks", *self.unit_pos(e["unit"]), color=T.CAST)
        elif t == "stun":
            look = e.get("look", "stun")
            if look != "sleep":
                self.float_text(e["unit"], IC.CONTROL_NAMES.get(look, "Оглушение") + "!",
                                IC.CONTROL_COLORS.get(look, (255, 240, 120)), 17, ttl=1.1, dy=8)
        elif t == "taunt":
            self.float_text(e["unit"], "!", T.TEAM_ENEMY, 22, ttl=0.7)
        elif t == "shield":
            self.float_text(e["unit"], f"Щит {e['amount']}", (220, 230, 255), 14)
            V.play("shield_small", self._ctx(target=e["unit"]))
        elif t == "cleanse":
            names = [IC.CONTROL_NAMES.get(n) or (self.data.tags[n]["name"] if n in self.data.tags else
                     IC.BUFF_NAMES.get(n, n)) for n in e.get("names", [])]
            text = "Снято: " + ", ".join(dict.fromkeys(names)) if names else "Очищен"
            self.float_text(e["unit"], fit(text, 14, 220), (240, 240, 200), 14, ttl=1.2)
            V.play("cleanse_small", self._ctx(target=e["unit"]))
        elif t == "fizzle":
            self.float_text(e["unit"], "Не вышло", T.TEXT_DIM, 13)
        elif t == "death":
            u = e["unit"]
            V.play("death", self._ctx(target=u))
            if u.team != PLAYER or u.summon:   # враг и тотем рассыпаются на пиксели, герой остаётся лежать
                rect = next((r for r, w in self.sprite_rects if w is u), None)
                if rect is not None:
                    V.emit_sprite(self.sprite_of(u, self.anim(u).facing < 0), rect)
                self.gone.add(u.id)
            else:
                self.fallen.add(u.id)
        elif t == "cell_reaction":
            x, y = T.cell_center(e["pos"])
            self.fx.append(Fx("cell", 0.6, pos=e["pos"], color=self.tag_color(e["tag"])))
            if not pix:
                V.play("cell_burst", self._ctx(center=e["pos"], color=self.tag_color(e["tag"])))
            self.float_text((x, y + 20), e["name"], self.tag_color(e["tag"]), 13, ttl=1.1)
        elif t == "cast_start":
            self._cast_visuals(e["unit"], e["skill"])
        elif t == "arena_warn":
            self._arena_warn(e)
        elif t == "arena_hit":
            self._arena_hit(e)
        elif t == "tide_end":
            pts = [T.cell_feet(p) for p in e["cells"]]
            if pts:
                V.play("tide_wave", {"cells": pts[::3], "target": pts[0], "target_ground": pts[0], "scale": 0.6})
        elif t == "rise":
            u = e["unit"]
            self.gone.discard(u.id)
            self.float_text(u, "Встаёт!", (190, 230, 160), 16, ttl=1.1)
            V.play("rise_fx", self._ctx(target=u, color=(170, 230, 160)))
        elif t == "charm":
            self.float_text(e["unit"], "Очарован!", (255, 140, 210), 16)
            V.play("charm_fx", self._ctx(target=e["unit"], color=(255, 140, 210)))
        elif t == "charm_end":
            self.float_text(e["unit"], "Пришёл в себя", (220, 220, 230), 13, ttl=0.8)
        elif t == "fall":
            self.float_text(e["unit"], "Падение!", (200, 200, 255), 17, ttl=1.1)
            V.play("fall_fx", self._ctx(target=e["unit"]))
        elif t == "portal":
            for p in (e["src"], e["dst"]):
                gx, gy = T.cell_feet(p)
                V.play("portal_fx", {"target": (gx, gy - 26), "target_ground": (gx, gy), "cells": [(gx, gy)],
                                     "color": (190, 140, 255), "scale": 1.0})
        elif t == "slide":
            V.emit("skid", *self.feet_pos(e["unit"]))
        elif t == "armor_break":
            self.float_text(e["unit"], "Броня расколота!", (255, 190, 120), 14, ttl=1.0, dy=12)
            V.play("armor_break_fx", self._ctx(target=e["unit"]))
        elif t == "frost_armor" and not pix:
            V.play("frost_armor_fx", self._ctx(target=e["unit"]))
        elif t == "summon":
            u = e["unit"]
            V.play("summon_appear", self._ctx(target=u, color=u.color))
        elif t == "aura":
            self._aura(e["unit"], e["radius"])
        elif t == "form":
            u = e["unit"]
            col = (150, 240, 120) if e["form"] != "wolf" else (200, 200, 220)
            V.play("shapeshift", self._ctx(caster=u, color=col))
            self.float_text(u, {"bear": "Медведь", "wolf": "Волк"}.get(e["form"], "Человек"), col, 14)
        elif t == "reveal":
            V.play("reveal_fx", self._ctx(target=e["unit"]))
        elif t == "backstab":
            self.float_text(e["unit"], "В спину!", (255, 90, 110), 15, ttl=0.9, dy=14)
            V.play("backstab_fx", self._ctx(target=e["unit"]))
        elif t == "sleep":
            self.float_text(e["unit"], "Сон", (210, 190, 255), 14)
        elif t == "wake":
            self.float_text(e["unit"], "Проснулся!", (255, 230, 150), 13, ttl=0.8)
        elif t == "pull":
            V.play("pull_fx", self._ctx(e["src"], e["unit"], color=(200, 200, 210)))
        elif t == "refresh":
            if e.get("ap"):
                self.float_text(e["unit"], f"+{e['ap']} AP", T.AP_COLOR, 15)
            V.play("refresh_fx", self._ctx(target=e["unit"]))
        elif t == "revive":
            u = e["unit"]
            self.fallen.discard(u.id)
            self.gone.discard(u.id)
            self.float_text(u, "Воскрешён!", (255, 240, 170), 17, ttl=1.3)
            V.play("heal_small", self._ctx(target=u, color=(255, 240, 170)))
        elif t == "object_break":
            u = e["unit"]
            eff = e.get("fx") or {}
            rect = next((r for r, w in self.sprite_rects if w is u), None)
            if rect is not None and not pix:
                V.emit_sprite(self.sprite_of(u), rect)
            self.gone.add(u.id)
            gx, gy = T.cell_feet(u.cell)
            r = eff.get("radius", 0)
            cells = [T.cell_feet(p) for p in self._cells_around(u.cell, r)] if r else [(gx, gy)]
            if eff.get("damage"):
                col = self.tag_color(eff.get("tag"), (255, 150, 60))
                if not pix:
                    V.play("mine_blast", {"target": (gx, gy - 26), "target_ground": (gx, gy), "cells": cells,
                                      "color": col, "scale": 1.0 + 0.4 * r})
                self.float_text((gx, gy - 40), "ВЗРЫВ!", col, 22, ttl=1.1)
            else:
                col = tuple(self.data.config["hazards"][eff["hazard"]]["color"]) if eff.get("hazard") else u.color
                if not pix:
                    V.play("cell_burst", {"target": (gx, gy - 20), "target_ground": (gx, gy), "cells": cells,
                                      "color": col, "scale": 1.0})
                if u.obj.get("guard"):
                    self.float_text((gx, gy - 40), "ПОТЕРЯН!", (255, 110, 110), 20, ttl=1.4)
        elif t == "crit":
            self.float_text(e["unit"], "КРИТ!", (255, 215, 90), 19, ttl=0.9, dy=22)
        elif t == "dodge":
            self.float_text(e["unit"], "уклонился", (170, 230, 255), 14, ttl=0.8, dy=6)
        elif t == "collision":
            u = e["unit"]
            self.float_text(u, f"Удар! -{e['amount']}", (255, 210, 140), 16, ttl=0.9, dy=16)
            self.anim(u).hit = HIT_T
            V.play("big_hit", self._ctx(target=u, color=(255, 220, 170)))
        elif t in ("spawn", "source_spawn"):
            u = e["unit"]
            V.play("summon_appear", self._ctx(target=u, color=u.color))
        elif t == "wave":
            self.banner = [f"ВОЛНА {e['wave']} / {e['total']}", "", 2.2, (255, 170, 120)]
        elif t == "intermission":
            self.banner = ["ПЕРЕДЫШКА", "Перестройтесь: следующая волна уже видна. Enter — вызвать сразу", 2.6,
                           (150, 210, 255)]
        elif t == "phase":
            self.banner = [e["name"].upper() or "НОВАЯ ФАЗА", e["unit"].name, 2.2, (255, 130, 90)]
            V.play("big_hit", self._ctx(target=e["unit"], color=(255, 130, 90)))
        elif t == "enrage":
            self.banner = [f"ВРАГИ В ЯРОСТИ ×{e['mult']:.2f}", "Бой затянулся — враги бьют всё сильнее", 2.4,
                           (255, 110, 90)]
        elif t == "gather":
            gx, gy = T.cell_feet(e["center"])
            V.play("gravity_fx", {"target": (gx, gy - 20), "target_ground": (gx, gy), "cells": [(gx, gy)],
                                  "color": (180, 150, 255), "scale": 1.0 + 0.3 * e.get("radius", 2)})
        elif t == "swap":
            u, src = e["unit"], e["src"]
            V.emit_line("light_motes", self.unit_pos(u), self.unit_pos(src), (190, 160, 255), step=8)
            self.float_text(u, "Обмен!", (190, 160, 255), 15, ttl=0.9)
        elif t == "levitate":
            self.float_text(e["unit"], "Невесомость!", (190, 160, 255), 16, ttl=1.0, dy=8)
        elif t == "land":
            self.float_text(e["unit"], "Падение!", (220, 200, 255), 15, ttl=0.9)
            V.play("land_impact", self._ctx(target=e["unit"], color=(190, 160, 255)))
        elif t == "terrain_cast":
            names = {"grass": "Корни!", "water": "Волна!", "stone": "Валун!", "lava": "Извержение!",
                     "ice_floor": "Шипы льда!"}
            self.float_text(e["unit"], names.get(e["ground"], "Сила земли"), (190, 220, 140), 14, ttl=0.9, dy=10)
        elif t == "reagent":
            self.float_text(e["unit"], f"Реактив ×{len(e['tags'])}", (190, 230, 140), 16, ttl=1.0, dy=10)
        elif t == "order":
            self.float_text(e["unit"], e["name"], (255, 210, 110), 16, ttl=1.0, dy=14)
            V.play("buff_good", self._ctx(target=e["unit"], color=(255, 210, 110)))
        elif t == "rage":
            self.float_text(e["unit"], f"Ярость ×{e['value']:.2f}", (255, 90, 80), 15, ttl=0.9)
        elif t == "tether":
            self.float_text(e["unit"], "Привязь", (255, 170, 200), 14, ttl=0.9)
        elif t == "merge":
            self.float_text(e["host"], "Слияние!", (255, 170, 200), 17, ttl=1.2, dy=10)
            V.play("spirit_link_fx", self._ctx(target=e["host"], color=(255, 170, 200)))
        elif t == "unmerge":
            self.float_text(e["unit"], "Вышел", (255, 190, 210), 14, ttl=0.9)
        elif t == "trap_set":
            gx, gy = T.cell_feet(e["pos"])
            V.play("trap_snap", {"target": (gx, gy - 10), "target_ground": (gx, gy), "cells": [(gx, gy)],
                                 "color": (200, 190, 150), "scale": 0.7})
        elif t == "wall":
            self.float_text(e["src"], "Ледяная стена", (170, 220, 255), 14, ttl=0.8)
        elif t == "terrain":
            pts = [T.cell_feet(p) for p in e["cells"]]
            fx_name, col = {"lava": ("eruption_hit", (255, 120, 40)), "water": ("tide_wave", (90, 160, 255)),
                            "stone": ("land_impact", (180, 170, 150)), "grass": ("nature_bloom", (140, 220, 110))
                            }.get(e["terrain"], ("ice_nova", (190, 230, 255)))
            if not pix:
                V.play(fx_name, {"target": pts[0], "target_ground": pts[0], "cells": pts, "color": col, "scale": 0.7})
        elif t == "shatter" and not pix:
            V.play("reaction_shatter", self._ctx(target=e["unit"], color=(190, 230, 255)))
        elif t == "corpse_use":
            gx, gy = T.cell_feet(e["pos"])
            col = {"blast": (140, 230, 110), "raise": (200, 230, 180), "devour": (170, 120, 230),
                   "cloud": (110, 200, 80), "wall": (225, 215, 195)}.get(e["do"], (200, 200, 200))
            V.play("toxic_burst" if e["do"] in ("blast", "cloud") else "raise_fx",
                   {"target": (gx, gy - 20), "target_ground": (gx, gy), "cells": [(gx, gy)], "color": col,
                    "scale": 1.0})
        elif t == "rewind":
            a, b = T.cell_feet(e["src"]), T.cell_feet(e["dst"])
            V.emit_line("light_motes", a, b, (240, 210, 120), step=8)
            self.float_text(e["unit"], "Откат!", (240, 215, 130), 16, ttl=1.0)
            V.play("refresh_fx", self._ctx(target=e["unit"], color=(240, 210, 120)))
        elif t == "stasis":
            self.float_text(e["unit"], "Стазис!", (240, 205, 110), 17, ttl=1.0, dy=8)
        elif t == "intercept":
            g, w = e["unit"], e["ward"]
            self.float_text(g, "Перехват!", (150, 200, 255), 15, ttl=0.9, dy=14)
            self.fx.append(Fx("link", 0.4, src=w, dst=g, color=(150, 200, 255)))
            V.play("shield_impact", self._ctx(target=g, color=(150, 200, 255)))
        elif t == "guard":
            self.float_text(e["unit"], "Под защитой", (150, 200, 255), 14, ttl=1.0)
        elif t == "watch":
            self.float_text(e["unit"], "Дозор", (255, 210, 120), 14, ttl=0.9)
        elif t == "watch_fire":
            self.float_text(e["dst"], "ДОЗОР!", (255, 200, 90), 18, ttl=1.0, dy=10)
        elif t == "detonate" and not pix:
            gx, gy = T.cell_feet(e["pos"])
            V.play("fire_explosion", {"target": (gx, gy - 24), "target_ground": (gx, gy), "cells": [(gx, gy)],
                                      "color": (255, 140, 50), "scale": P.scale_at(e["pos"][1] + 0.5)})
        elif t == "delay_hit":
            if e["unit"] is not None:
                V.play("great_heal", self._ctx(target=e["unit"], color=(255, 240, 170)))
        elif t == "fuse":
            self.float_text(e["unit"], "Фитиль!", (255, 170, 80), 14, ttl=0.9)
        elif t == "toss":
            self.anim(e["unit"]).toss = TOSS_T
        elif t == "rush":
            V.emit_line("light_motes", T.cell_feet(e["src"]), T.cell_feet(e["dst"]), (230, 210, 180), step=10)
        elif t == "beat":
            u = e["unit"]
            V.play("aura_pulse", self._ctx(caster=u, color=(255, 170, 220), scale=0.8))
            self.float_text(u, f"♪ {e['beat']}/{e['beats']}", (255, 180, 230), 13, ttl=0.7, dy=6)
        elif t == "note":
            self.float_text(e["src"], "♪", (255, 180, 230), 18, ttl=0.8, dy=20)
        elif t == "finale":
            u = e["unit"]
            V.play("inspire_fx", self._ctx(caster=u, color=(255, 170, 220)))
            self.float_text(u, f"Финал! нот: {e['notes']}", (255, 190, 235), 18, ttl=1.4, dy=12)
        elif t == "mine":
            gx, gy = T.cell_feet(e["pos"])
            if not pix:
                V.play("mine_blast", {"target": (gx, gy - 26), "target_ground": (gx, gy), "cells": [(gx, gy)],
                                  "color": (255, 150, 60), "scale": 1.0})
            self.float_text((gx, gy - 30), "Мина!", (255, 150, 90), 15, ttl=0.9)

    def _cast_visuals(self, u, sid):
        """Каст: магический круг и круг-заливка под ногами, свет, искры снизу вверх и сходящиеся огоньки, у больших
        заклинаний — копящаяся сфера над головой, затемнение и полосы кадра. Всё живёт, пока идёт каст."""
        sk = u.skill_defs[sid]
        lib = self.vfx.lib["casts"]
        spec, tier = self.skill_spec(sid, sk)
        cast = dict(lib["default"], **lib.get(sid, {}))
        if sk.get("branch"):
            cast.update(lib.get(f"{sid}.{sk['branch'][0]}", {}))
        tag = next((eff["tag"] for eff in sk["effects"] if eff.get("tag")), None)
        color = tuple(spec["color"]) if spec.get("color") else self.tag_color(
            tag, (255, 215, 140) if u.team == PLAYER else (255, 120, 100))
        alive = (lambda: u.alive and u.cast is not None and u.cast["skill"] == sid)
        V = self.vfx
        size = cast["size"] * (1.4 if u.boss else 1) * (1 + 0.12 * tier)
        feet = (lambda: self.feet_pos(u))
        V.decal(shape=cast["circle"], pos=feet, size=size, color=resolve_color("tag", color), alive=alive,
                alpha=(0.95, 0.95), grow=(1, 1), spin=70, ground=True, hdr=1.6, fade=0.2, under=True)
        V.add_sfx("cast_disc", feet, color, size / 120, alive=alive)
        V.add_light({"radius": size * 1.2, "intensity": 0.9, "flicker": 0.15}, feet, color, alive=alive)
        V.emitter("cast_motes", 30, lambda e: self.feet_pos(u), color, alive=alive)
        V.emitter("cast_converge", 22, lambda e: self.unit_pos(u), color, alive=alive)
        area = self.pix.cast_area(u, sid, sk, alive)     # Буран: туча над целью — сферы над головой нет
        if cast.get("orb") and not area:  # сфера над головой копит силу
            head = (lambda: (self.feet_pos(u)[0], self.feet_pos(u)[1] - self.unit_h(u) - 22))
            if not self.pix.cast_orb(u, sk, head, alive, tier):
                V.add_sfx(cast["orb"], head, color, 1 + 0.15 * tier, alive=alive)
            V.add_sfx({"mode": "d_pinch", "size": 140, "extra": 6}, head, color, 1.0, alive=alive)
        if cast.get("dim") or u.boss:
            V.screen_fx(dim=cast.get("dim", 0.3), dim_time=sk["cast"])
        if cast.get("bars"):
            V.screen_fx(bars=cast["bars"], bars_time=sk["cast"] + 0.4)

    def _arena_warn(self, e):
        """Предупреждение о событии поля: клетки мигают, крупная надпись."""
        col = ARENA_COLORS.get(e["kind"], (255, 220, 120))
        for p in e["cells"]:
            self.fx.append(Fx("warn", e["delay"], pos=p, color=col))
        if e["kind"] == "wind":
            arrow = "→ →" if e["dir"][0] > 0 else "← ←"
            text = f"{e['name']} {arrow}"
        else:
            text = e["name"] + "!"
        self.fx.append(Fx("banner", e["delay"] + 0.6, s=text, color=col))

    def _arena_hit(self, e):
        V = self.vfx
        kind, cells = e["kind"], e["cells"]
        pts = [T.cell_feet(p) for p in cells]
        if self.pix.arena(kind, pts):
            return
        ctx = lambda p: {"target": (p[0], p[1] - 26), "target_ground": p, "cells": [p], "scale": 1.0,  # noqa: E731
                         "color": ARENA_COLORS.get(kind)}
        if kind == "eruption":
            for p in pts:
                V.play("eruption_hit", ctx(p))
        elif kind == "lightning":
            for p in pts:
                V.play("lightning_cell", ctx(p))
        elif kind == "avalanche" and pts:
            V.play("avalanche_hit", dict(ctx(pts[0]), cells=pts))
        elif kind == "tide" and pts:
            V.play("tide_wave", dict(ctx(pts[0]), cells=pts[::2]))
        elif kind == "wind":
            edge = 0 if e["dir"][0] > 0 else self.grid.w
            rows = [P.project(edge, y + 0.5)[:2] for y in range(self.grid.h)]
            mid = P.project(edge, self.grid.h / 2)[:2]
            V.play("wind_gust", {"target": mid, "cells": rows, "scale": 1.0,
                                 "target_ground": mid, "dir": 0 if e["dir"][0] > 0 else 180})
            for x, y in rows:
                V.emit("wind_lines", x, y, count=4, angle=0 if e["dir"][0] > 0 else 180)
        elif kind == "sandstorm":
            dur = 6.0
            lx, ly = P.project(0, self.grid.h / 2)[:2]
            V.emitter("sand_storm", 14, (lx - 30, ly), duration=dur)
            V.emitter("sand_grit", 90, lambda em: P.project(-0.2, self.vfx.prng.uniform(0, self.grid.h))[:2],
                      duration=dur)
            V.screen_fx(dim=0.25, dim_time=dur)

    def _aura(self, u, radius):
        """Пульс ауры призыва: кольцо; боевая аура бьёт молниями во врагов вокруг, провокация — красными кольцами."""
        V = self.vfx
        kinds = {e["type"] for e in u.aura["effects"]}
        ctx = self._ctx(caster=u, color=u.color)
        V.play("aura_pulse", dict(ctx, scale=max(0.5, radius / 2)))
        if "damage" in kinds:
            src = self.unit_pos(u)
            src = (src[0], src[1] - 16)
            for f in self.combat.alive():
                if f.is_enemy(u) and cheb(f.cell, u.cell) <= radius:
                    V.bolt(src, self.unit_pos(f), (170, 175, 255), 7, 0.24, 0.2, 0)
        if "taunt" in kinds:
            V.play("taunt_pulse", dict(ctx, scale=0.6))

    def _cells_around(self, center, r):
        return self.grid.in_radius(center, r)

    def update(self, game_dt, real_dt):
        if self.banner:
            self.banner[2] -= real_dt
            if self.banner[2] <= 0:
                self.banner = None
        self.clock += real_dt
        for f in self.fx:
            f.age += game_dt  # на паузе эффекты замирают вместе с боем
        self.fx = [f for f in self.fx if f.age < f.ttl]
        for a in self.anims.values():
            a.lunge = max(0.0, a.lunge - game_dt)
            a.hit = max(0.0, a.hit - game_dt)
            a.toss = max(0.0, a.toss - game_dt)
        if game_dt > 0 and self.combat:
            self._ambient(game_dt)
        self.pix.update(game_dt)
        self.vfx.real_update(real_dt)
        self.vfx.update(game_dt)
        for name, x, y, size, rot, alpha, flat in self.vfx.marks:
            g = P.unproject(x, y)             # след ложится на плоскую карту: перспектива сплющит его сама
            if g is not None:
                fx, fy = P.ground_to_flat(*g)
                k = P.FLAT / (P.BASE_PX * P.scale_at(g[1]))
                self.marks.stamp(name, fx, fy, size * k, rot, alpha, 1.0 if flat < 1 else flat)
        self.vfx.marks.clear()
        self.marks.fade(game_dt)
        if self.combat:
            self._frame_lights()

    def _rate(self, key, per_sec, dt):
        """Сколько частиц выпустить за кадр при частоте per_sec (дробный остаток копится)."""
        acc = self._emit_acc.get(key, 0.0) + per_sec * dt
        n = int(acc)
        self._emit_acc[key] = acc - n
        return n

    def _ambient(self, dt):
        """Постоянные источники: горящие и ледяные клетки, вода, статусы на юнитах."""
        V = self.vfx
        pix = self.pix.on
        for pos, cell in self.grid.cells.items():
            if cell.hazard:
                x, y = T.cell_feet(pos)
                if cell.hazard in ("fire", "ice") and pix:
                    pass
                elif cell.hazard == "fire":
                    for _ in range(self._rate(("hz", pos), 7, dt)):
                        V.emit("flame_fb", x, y - 22)
                    for _ in range(self._rate(("he", pos), 4, dt)):
                        V.emit("heat_embers", x, y - 6)
                elif cell.hazard == "ice":
                    for _ in range(self._rate(("hz", pos), 4, dt)):
                        V.emit("ice_cell", x, y - 10)
                elif cell.hazard == "poison":
                    for _ in range(self._rate(("hz", pos), 2.5, dt)):
                        V.emit("toxic_puff", x, y - 16)
                elif cell.hazard == "oil":
                    for _ in range(self._rate(("hz", pos), 0.8, dt)):
                        V.emit("water_glint", x, y - 4, color=(255, 220, 150))
            elif cell.terrain == "water":
                for _ in range(self._rate(("w", pos), 1.0, dt)):
                    V.emit("water_glint", *T.cell_center(pos))
            elif cell.terrain == "lava":
                x, y = T.cell_feet(pos)
                for _ in range(self._rate(("lv", pos), 2.5, dt)):
                    V.emit("lava_bubble", x, y - 16)
                for _ in range(self._rate(("le", pos), 2.0, dt)):
                    V.emit("heat_embers", x, y - 6)
            elif cell.terrain == "ice_floor":
                for _ in range(self._rate(("if", pos), 0.6, dt)):
                    V.emit("frost_sparkle", *T.cell_center(pos))
            if cell.portal:
                x, y = T.cell_feet(pos)
                for _ in range(self._rate(("pt", pos), 6, dt)):
                    V.emit("portal_motes", x, y - 6)
        for u in self.combat.alive():
            x, y = self.unit_pos(u)
            if "fire" in u.statuses and not pix:
                for _ in range(self._rate(("burn", u.id), 8, dt)):
                    V.emit("burn", x, y + 4)
            if "water" in u.statuses:
                for _ in range(self._rate(("wet", u.id), 3, dt)):
                    V.emit("water_drip", x, y)
            if "ice" in u.statuses and not pix:
                for _ in range(self._rate(("ice", u.id), 3, dt)):
                    V.emit("frost_sparkle", x, y)
            if "storm" in u.statuses:
                for _ in range(self._rate(("storm", u.id), 4, dt)):
                    V.emit("storm_crackle", x, y)
            if "poison" in u.statuses:
                for _ in range(self._rate(("poison", u.id), 3, dt)):
                    V.emit("poison_bubbles", x, y, count=1)
            if "oil" in u.statuses:
                for _ in range(self._rate(("oil", u.id), 3, dt)):
                    V.emit("oil_drips", x, y + 6)
            if u.asleep:
                for _ in range(self._rate(("zz", u.id), 1.5, dt)):
                    V.emit("zzz", x + 10, y - 30)

    def _frame_lights(self):
        """Свет на этот кадр: горящие клетки, лёд, горящие юниты."""
        fl = self.vfx.frame_lights
        fl.clear()
        t = self.clock
        for pos, cell in self.grid.cells.items():
            if cell.hazard == "fire":
                x, y = T.cell_feet(pos)
                k = 0.55 + 0.15 * math.sin(t * 13 + pos[0] * 3.1) * math.sin(t * 5.3 + pos[1])
                fl.append(Light((x, y - 10), resolve_color((255, 130, 40), None), 95, k, fadein=0))
            elif cell.hazard == "ice":
                fl.append(Light(T.cell_feet(pos), resolve_color((120, 190, 255), None), 80, 0.3, fadein=0))
            elif cell.hazard == "poison":
                fl.append(Light(T.cell_feet(pos), resolve_color((130, 220, 90), None), 70, 0.25, fadein=0))
            if cell.terrain == "lava":
                k = 0.5 + 0.12 * math.sin(t * 3 + pos[0] * 1.7 + pos[1])
                fl.append(Light(T.cell_feet(pos), resolve_color((255, 110, 40), None), 85, k, fadein=0))
            elif cell.portal:
                fl.append(Light(T.cell_feet(pos), resolve_color((170, 110, 255), None), 70, 0.5, fadein=0))
        for u in self.combat.alive():
            if "fire" in u.statuses:
                fl.append(Light(self.unit_pos(u), resolve_color((255, 140, 50), None), 70,
                                0.45 + 0.1 * math.sin(t * 17 + u.id), fadein=0))

    def uncam(self, p):
        """Точка экрана → мир (обратная камера: зум и тряска при касте)."""
        if not self.gl_camera:
            return p
        sc = self.vfx.screen
        (cx, cy), z, (ox, oy) = sc.center, sc.zoom, sc.offset
        return cx + (p[0] - ox - cx) / z, cy + (p[1] - oy - cy) / z

    def pick_unit(self, pos, ok=None, reach=30):
        """Юнит под курсором: попадание в фигурку (передние перекрывают задних), иначе ближайшая фигурка в пределах
        reach пикселей — не нужно искать клетку, на которую юнит уже перешёл. ok(u) — кого вообще можно выбрать."""
        x, y = self.uncam(pos)
        best = None
        for rect, u in reversed(self.sprite_rects):
            if not u.alive or (ok is not None and not ok(u)):
                continue
            if rect.collidepoint(x, y):
                return u
            dx = max(rect.left - x, 0, x - rect.right)
            dy = max(rect.top - y, 0, y - rect.bottom)
            d = (dx * dx + dy * dy) ** 0.5
            if d < reach and (best is None or d < best[0]):
                best = (d, u)
        return best[1] if best else None

    def unit_at_screen(self, pos):
        return self.pick_unit(pos, reach=0)

    # ---------- кадр ----------

    def draw(self, surf, scene):
        """Без OpenGL: мир, частицы упрощённо на CPU, интерфейс — всё в одну поверхность."""
        self.draw_world(surf, scene)
        if self._cpu_tex is None:
            self._cpu_tex = make_textures()
        self.vfx.draw_cpu(surf, self._cpu_tex, self._cpu_cache, props=self.props)
        self.draw_ui(surf, scene)

    def draw_layers(self, world, ui, scene, units=None):
        """С OpenGL: земля (плоская карта → плоскость, см. plane), юниты и интерфейс отдельно; эффекты под
        юнитами, над ними и свечение кладёт видеокарта между слоями."""
        self.gl_camera = True
        self.draw_ground(world, scene, warp=False)
        if units is None:
            self._draw_world(world, scene)
        else:
            units.fill((0, 0, 0, 0))
            self._draw_world(units, scene)
        self.draw_ui(ui, scene)

    def draw_world(self, surf, scene):
        self.draw_ground(surf, scene)
        self._draw_world(surf, scene)

    def lab_frame(self):
        """Для видеокарты: команды стилей эффектов (ui/fxlab) на этот кадр или None."""
        return self.pix.lab_frame()

    def glow_layer(self):
        """Для видеокарты: яркие пиксели пиксельных эффектов — источник свечения (или None)."""
        return self.pix.glow_layer()

    def plane(self):
        """Для видеокарты: плоская карта земли и цвет дымки вдали."""
        return self.flat, self.painter.fog(self.combat) if self.combat else (0.5, 0.5, 0.6)

    def draw_ground(self, surf, scene, warp=True):
        """Вся земля — на плоской карте self.flat. warp — сразу положить её на экран (без OpenGL)."""
        c = scene.combat
        flat = self.flat
        self.overlay.fill((0, 0, 0, 0))
        self._draw_ground(flat, c)
        if scene.phase == "deploy":
            self._draw_deploy_zone(scene)
        self._draw_objective_ground(c)
        self._draw_targeting(scene)
        self._draw_telegraphs(c)
        for f in self.fx:
            if f.kind == "cell":
                pygame.draw.rect(self.overlay, (*f.color, int(120 * (1 - f.k))), FR(f.pos))
            elif f.kind == "warn":                 # событие поля: клетка мигает всё чаще
                pulse = 0.5 + 0.5 * math.sin(self.clock * (8 + 16 * f.k))
                r = FR(f.pos)
                pygame.draw.rect(self.overlay, (*f.color, int(40 + 110 * f.k * pulse)), r)
                pygame.draw.rect(self.overlay, (*f.color, 230), r.inflate(-int(30 * (1 - f.k)), -int(30 * (1 - f.k))), 3)
        self._draw_mechanics_ground(c)
        hover = scene.hover_cell if not scene.dragging else None
        if hover:                                  # мягкая сетка: клетка под курсором подсвечена на земле
            pygame.draw.rect(self.overlay, (255, 255, 255, 40), FR(hover))
            pygame.draw.rect(self.overlay, (255, 255, 255, 200), FR(hover), 3)
        flat.blit(self.overlay, (0, 0))
        self.overlay.fill((0, 0, 0, 0))
        self._draw_orders(scene)
        flat.blit(self.overlay, (0, 0))
        if warp:
            self.painter.warp(flat, surf, self.painter.fog(c))

    def _draw_mechanics_ground(self, c):
        """Механики героев на земле: зоны дозора, связь телохранителя, круг песни, бочки с фитилём."""
        for u in c.alive():
            if u.watch:
                w = u.watch
                k = w["left"] / max(w["total"], 0.01)
                pulse = 0.5 + 0.5 * math.sin(self.clock * 5)
                for p in self._cells_around(w["center"], w["radius"]):
                    r = FR(p)
                    pygame.draw.rect(self.overlay, (255, 190, 90, int(30 + 30 * pulse)), r)
                    pygame.draw.rect(self.overlay, (255, 200, 110, 200), r.inflate(-10, -10), 2)
                cx, cy = FR(w["center"]).center
                rad = int(20 + 6 * pulse)
                pygame.draw.circle(self.overlay, (255, 210, 120, 230), (cx, cy), rad, 3)
                pygame.draw.line(self.overlay, (255, 210, 120, 230), (cx - rad - 8, cy), (cx + rad + 8, cy), 2)
                pygame.draw.line(self.overlay, (255, 210, 120, 230), (cx, cy - rad - 8), (cx, cy + rad + 8), 2)
                pygame.draw.arc(self.overlay, (255, 240, 200, 255), (cx - rad - 5, cy - rad - 5, 2 * rad + 10,
                                                                    2 * rad + 10), 0, k * math.tau, 3)
                pygame.draw.line(self.overlay, (255, 200, 110, 90), self.flat_feet(u), (cx, cy), 2)
            if u.tethered_by is not None and u.tethered_by.alive and u.tethered_by.merged <= 0:
                b = u.tethered_by
                a, z = self.flat_feet(b), self.flat_feet(u)
                wave = []
                for i in range(13):            # нить чуть колышется
                    k = i / 12
                    wave.append((a[0] + (z[0] - a[0]) * k,
                                 a[1] + (z[1] - a[1]) * k + math.sin(self.clock * 4 + k * 9) * 6 * math.sin(k * math.pi)))
                pygame.draw.lines(self.overlay, (255, 170, 200, 210), False, wave, 3)
            if u.guarded_by is not None and u.guarded_by.alive:
                g = u.guarded_by
                near = cheb(g.cell, u.cell) <= 1
                col = (150, 200, 255, 220 if near else 90)
                pygame.draw.line(self.overlay, col, self.flat_feet(g), self.flat_feet(u), 4 if near else 2)
                pygame.draw.circle(self.overlay, col, [int(v) for v in self.flat_feet(u)], 22, 3)
            if u.song:
                s = u.song
                ph = s["t"] / s["every"]
                rad = int((s["radius"] + 0.5) * P.FLAT)
                fx, fy = [int(v) for v in self.flat_feet(u)]
                pygame.draw.circle(self.overlay, (255, 170, 220, 40), (fx, fy), rad)
                pygame.draw.circle(self.overlay, (255, 170, 220, 200), (fx, fy), rad, 3)
                pygame.draw.circle(self.overlay, (255, 210, 240, int(200 * (1 - ph))), (fx, fy), int(rad * ph), 3)
            if u.obj and u.fuse > 0:
                fx, fy = [int(v) for v in self.flat_feet(u)]
                blink = int(self.clock * 10) % 2
                pygame.draw.circle(self.overlay, (255, 80, 50, 160 if blink else 60), (fx, fy), 30, 4)

    def _draw_objective_ground(self, c):
        """Круг удержания и клетки, откуда выйдет следующая волна (в передышку и на разведке)."""
        ob = c.objective
        if ob and ob["type"] == "hold":
            pulse = int(25 * math.sin(self.clock * 2.5))
            for p in ob["cells"]:
                r = FR(tuple(p))
                pygame.draw.rect(self.overlay, (255, 215, 90, 55 + pulse), r)
                pygame.draw.rect(self.overlay, (255, 225, 120, 200), r.inflate(-6, -6), 2)
        if c.intermission > 0 or c.time == 0:
            pulse = 0.5 + 0.5 * math.sin(self.clock * 6)
            for _, p in c.next_wave_preview():
                r = FR(p)
                pygame.draw.rect(self.overlay, (255, 90, 70, int(40 + 50 * pulse)), r)
                pygame.draw.rect(self.overlay, (255, 120, 90, 220), r.inflate(-10, -10), 2)

    def cam(self, p):
        """Точка мира → экран с учётом камеры (зум, тряска): надписи и полоски над юнитами едут вместе с миром.
        Без OpenGL камеры нет (zoom 1, тряска только у частиц) — точка не меняется."""
        if not self.gl_camera:
            return p
        sc = self.vfx.screen
        (cx, cy), z, (ox, oy) = sc.center, sc.zoom, sc.offset
        return cx + (p[0] - cx) * z + ox, cy + (p[1] - cy) * z + oy

    def draw_ui(self, surf, scene):
        c = scene.combat
        self.icon_tips = []
        for u in c.units:
            if u.alive and u.merged <= 0 and not (scene.dragging and u is scene.picked):
                self._draw_hud(surf, u)
        if scene.phase == "deploy" and scene.picked and scene.dragging:
            img = self.sprite_of(scene.picked)
            surf.blit(img, (scene.mouse[0] - img.get_width() / 2, scene.mouse[1] - img.get_height() * 0.6))
        self._draw_fx(surf)
        if not scene.dragging:
            self._draw_hover(surf, scene)
        self._draw_top(surf, scene)
        self._draw_objective(surf, scene)
        if self.banner:
            text, sub, left, col = self.banner
            k = min(1.0, left / 0.4)
            cx = T.GRID_X + T.GRID_W // 2
            T.text(surf, text, (cx, T.GRID_Y + 70), 44, T.mix(T.BG, col, k), True, center=True, shadow=True)
            if sub:
                T.text(surf, sub, (cx, T.GRID_Y + 110), 17, T.mix(T.BG, (230, 235, 245), k), center=True, shadow=True)
        if scene.phase == "deploy":
            self._draw_scouting(surf, scene)
        else:
            self._draw_right(surf, scene)
        self._draw_bottom(surf, scene)
        if getattr(scene, "route", None):
            cells, sec = scene.route_preview()
            if cells:
                T.text(surf, f"маршрут: {len(cells)} кл. · {sec:.1f} с", (scene.mouse[0] + 18, scene.mouse[1] + 14),
                       14, (170, 255, 190), True, shadow=True)
        if scene.toast:
            T.text(surf, scene.toast[0], (T.GRID_X + 440, BOTTOM_Y - 22), 18, (255, 200, 120), True, center=True,
                   shadow=True)
        if c.result:
            self._draw_result(surf, c.result, scene)

    def objective_text(self, c):
        """Цель боя одной строкой и доля выполнения 0..1 (или None)."""
        ob = c.objective
        if not ob:
            return "Цель: победить всех врагов", None
        if ob["type"] == "hold":
            return f"Удержать: {ob.get('name', 'точку')} — {c.hold:.0f}/{ob['time']:g} с", c.hold / ob["time"]
        if ob["type"] == "destroy":
            src = [u for u in c.units if u.obj and u.obj.get("source")]
            left = sum(1 for u in src if u.alive)
            return f"Разрушить источники: осталось {left} из {len(src)}, затем добить врагов", \
                (len(src) - left) / max(1, len(src))
        g = c.guards()
        hp = sum(max(0, u.hp) for u in g)
        mx = sum(u.max_hp for u in g) or 1
        return f"{ob.get('name', 'Защитить')} — {hp}/{mx}", hp / mx

    def _draw_objective(self, surf, scene):
        """Плашка под заголовком: цель, волна, передышка."""
        c = scene.combat
        text, frac = self.objective_text(c)
        x, y = T.GRID_X, 48
        T.text(surf, text, (x, y), 15, (255, 225, 140), True, shadow=True)
        if frac is not None:
            w = 220
            bx = x + T.font(15, True).size(text)[0] + 12
            pygame.draw.rect(surf, (20, 20, 24), (bx, y + 4, w, 10), border_radius=4)
            pygame.draw.rect(surf, (255, 205, 90), (bx, y + 4, int(w * max(0.0, min(1.0, frac))), 10), border_radius=4)
        if c.wave_total > 1:
            s = f"Волна {c.wave}/{c.wave_total}"
            if c.intermission > 0:
                s += f" · передышка {c.intermission:.1f} с (Enter — вызвать сразу)"
            elif c.waves and scene.phase != "deploy":
                s += f" · следующая через {max(0.0, c.wave_timeout - c.wave_clock):.0f} с, если не отбить раньше"
            T.text(surf, s, (x + T.GRID_W - 8 - T.font(15, True).size(s)[0], y), 15,
                   (150, 210, 255) if c.intermission > 0 else T.TEXT_DIM, True, shadow=True)

    def _draw_ground(self, surf, c):
        """Плоская карта: земля главы (ui/ground.py), следы, рябь воды, клетки-опасности."""
        cfg = self.data.config
        surf.blit(self.painter.base(c), (0, 0))
        if self.marks.count:
            surf.blit(self.marks.surf, (0, 0))
        for pos, cell in c.grid.cells.items():
            if cell.base_terrain:                    # прилив или каток: временный рельеф поверх земли
                r = FR(pos)
                surf.blit(self.painter.water_layer(c, cell.terrain), r, r)
            if cell.terrain != "water" and not cell.hazard:
                continue
            r = FR(pos)
            if cell.terrain == "water":
                base = tuple(cfg["terrain"]["water"]["color"])
                for i in range(3):
                    y = r.y + 14 + i * 18 + math.sin(self.clock * 2 + pos[0] + i) * 3
                    x0 = r.x + 8 + int(6 * math.sin(self.clock * 0.7 + pos[1] * 2 + i))
                    pygame.draw.line(surf, T.mix(base, (255, 255, 255), 0.22), (x0, y), (x0 + 26, y), 2)
            if cell.hazard:
                h = cfg["hazards"][cell.hazard]
                if h.get("hidden"):                  # капкан ловчего: виден только своим
                    if cell.hazard_team == PLAYER:
                        img = self.props.get("trap_open")
                        if img is not None:
                            img = pygame.transform.scale(img, (img.get_width() * 3, img.get_height() * 3))
                            surf.blit(img, img.get_rect(center=r.center))
                        pygame.draw.circle(surf, (200, 190, 150), r.center, 26, 2)
                    continue
                if cell.hazard == "mine":            # мина: маленький диск с огоньком, а не заливка клетки
                    cx, cy = r.centerx, r.centery
                    pygame.draw.circle(surf, (60, 60, 66), (cx, cy), 10)
                    pygame.draw.circle(surf, (110, 110, 120), (cx, cy), 10, 2)
                    blink = 150 + int(100 * (0.5 + 0.5 * math.sin(self.clock * 6)))
                    pygame.draw.circle(surf, (blink, 50, 40), (cx, cy - 1), 2)
                    continue
                alpha = {"fire": 90, "poison": 70, "oil": 85, "briar": 100}.get(cell.hazard, 130)
                if not (cell.hazard in ("fire", "ice") and self.pix.on):   # огонь и лёд — поверхность (ui/pixfire.py)
                    pygame.draw.rect(self.overlay, (*h["color"], alpha), r)
                if cell.hazard == "briar":           # терновник: колючие штрихи
                    for i in range(5):
                        hx = r.x + 12 + (pos[0] * 31 + i * 17) % (r.w - 24)
                        hy = r.y + 16 + (pos[1] * 23 + i * 13) % (r.h - 26)
                        pygame.draw.line(surf, (40, 70, 30), (hx, hy + 8), (hx + 4, hy), 2)
                        pygame.draw.line(surf, (40, 70, 30), (hx + 4, hy), (hx + 8, hy + 7), 2)
                if cell.hazard == "ice" and not self.pix.on:
                    pygame.draw.line(surf, (235, 250, 255), (r.x + 12, r.y + 16), (r.centerx, r.centery), 2)
                    pygame.draw.line(surf, (235, 250, 255), (r.centerx, r.centery), (r.right - 16, r.y + 24), 2)
                    pygame.draw.line(surf, (235, 250, 255), (r.centerx, r.centery), (r.x + 30, r.bottom - 10), 2)
                if cell.hazard_time != PERMANENT:
                    T.text(surf, f"{cell.hazard_time:.0f}", (r.right - 14, r.y + 4), 12, (255, 255, 255))
        self.pix.ground(surf, c)                     # пиксельные поверхности и следы — поверх рельефа
        for b in c.corpses:                          # трупы — ресурс некроманта: кости на земле, бледнеют
            r = FR(b["cell"])
            a = int(220 * min(1.0, b["left"] / 4))
            for i in range(3):
                h = (b["cell"][0] * 31 + b["cell"][1] * 17 + i * 13) % 97
                x0, y0 = r.x + 14 + h % 30, r.y + 20 + (h // 7) % 24
                pygame.draw.line(self.overlay, (225, 215, 195, a), (x0, y0), (x0 + 16, y0 + 6 - i * 4), 4)
            pygame.draw.circle(self.overlay, (230, 222, 205, a), (r.centerx + 4, r.centery - 6), 7)
            pygame.draw.circle(self.overlay, (40, 30, 40, a), (r.centerx + 2, r.centery - 7), 2)
            pygame.draw.circle(self.overlay, (40, 30, 40, a), (r.centerx + 6, r.centery - 7), 2)
        surf.blit(self.overlay, (0, 0))
        self.overlay.fill((0, 0, 0, 0))

    def _draw_world(self, surf, scene):
        """Укрытия, деревья, декор вокруг доски и юниты в порядке глубины: кто ближе к камере — рисуется позже.
        Всё стоящее — билборды: стоят вертикально на своей точке земли, масштаб — по глубине."""
        c = scene.combat
        items = []
        for gx, gy, kind, col in self.painter.props(c):
            x, y, k = P.project(gx, gy)
            if -120 < x < T.SCREEN_W + 120 and -40 < y < T.SCREEN_H + 200:
                items.append((y, 0, "prop", (x, y, k, kind, col, gy)))
        for u in c.units:
            if (scene.dragging and u is scene.picked) or u.id in self.gone or (u.obj and not u.alive) \
                    or u.merged > 0:
                continue
            if u.hidden and scene.phase == "deploy":
                continue
            fy = self.feet_pos(u)[1]
            items.append((fy - (40 if u.id in self.fallen else 0), 1, "unit", u))
        self.pix.begin_frame(self.gl_camera)
        items += self.pix.world_items(c)
        items.sort(key=lambda it: (it[0], it[1]))
        self.sprite_rects = []
        for _, _, kind, obj in items:
            if kind == "pix":
                obj[0](surf, *obj[1])
            elif kind == "prop":
                self._draw_prop(surf, *obj)
            elif obj.id in self.fallen:
                self._draw_downed(surf, obj)
            else:      # живой — или только что павший, чья смерть ещё «в полёте» снаряда
                self._draw_unit(surf, obj, obj is scene.selected, scene)

    def _draw_prop(self, surf, x, y, k, kind, col, gy):
        """Укрытие, дерево или декор: билборд у ног (x, y), масштаб k; вдали — тонет в дымке, как и земля."""
        fog = int(max(0.0, min(0.85, (-gy - 0.5) / 9.0)) * 10)
        key = (kind, col, fog)
        img = self._prop_imgs.get(key)
        if img is None:
            img = prop_image(kind, col)
            if fog:
                f = fog / 10
                fc = self.painter.fog(self.combat)
                img.fill((int(255 * (1 - f)),) * 3, special_flags=pygame.BLEND_RGB_MULT)
                img.fill(tuple(int(255 * c * f) for c in fc), special_flags=pygame.BLEND_RGB_ADD)
            self._prop_imgs[key] = img
        img = self.scaled(img, k)
        surf.blit(img, (x - img.get_width() / 2, y - img.get_height() + 4))

    def _draw_deploy_zone(self, scene):
        pulse = int(20 * math.sin(self.clock * 3))
        for pos in scene.combat.deploy_cells():
            r = FR(pos)
            pygame.draw.rect(self.overlay, (90, 230, 120, 45 + pulse), r)
            pygame.draw.rect(self.overlay, (120, 255, 140, 140), r.inflate(-4, -4), 2)

    def _draw_targeting(self, scene):
        if not scene.targeting or not scene.selected:
            return
        sk = scene.selected.skill_defs[scene.targeting]
        u = scene.selected
        for pos in scene.combat.grid.cells:
            if cheb(pos, u.cell) <= sk["range"]:
                pygame.draw.rect(self.overlay, (255, 230, 120, 38), FR(pos))
        hover = scene.hover_cell
        if hover:
            for p in self._cells_around(hover, sk.get("radius", 0)):
                pygame.draw.rect(self.overlay, (255, 220, 80, 90), FR(p))

    def _draw_telegraphs(self, c):
        for u in c.alive():
            if not u.cast:
                continue
            sk = u.skill_defs[u.cast["skill"]]
            tgt = u.cast["target"]
            center = tgt.cell if hasattr(tgt, "cell") else tgt
            if sk["target"] == "self":
                center = u.cell
            col = (255, 70, 60) if u.team != PLAYER else (90, 170, 255)
            k = 1 - u.cast["left"] / u.cast["total"]
            for p in self._cells_around(center, sk.get("radius", 0)):
                r = FR(p)
                pygame.draw.rect(self.overlay, (*col, 50 + int(70 * k)), r)
                pygame.draw.rect(self.overlay, (*col, 220), r.inflate(-int(60 * (1 - k)), -int(50 * (1 - k))), 2)

    def _draw_route(self, start, cells, col, alpha, show_cost=True):
        """Маршрут по клеткам на земле: линия по центрам, точка на каждой клетке, медленные клетки — крупнее."""
        pts = [start] + [P.ground_to_flat(*P.cell_ground(p)) for p in cells]
        pygame.draw.lines(self.overlay, (*col, alpha), False, pts, 4)
        for p, xy in zip(cells, pts[1:]):
            k = MV.step_cost(self.combat, self._route_unit, p) if show_cost and self._route_unit else 1.0
            r = 7 if k <= 1.01 else 11
            pygame.draw.circle(self.overlay, (*(col if k <= 1.01 else (255, 170, 90)), alpha), xy, r)
        pygame.draw.circle(self.overlay, (*col, alpha), pts[-1], 18, 4)

    def _draw_orders(self, scene):
        draft, _ = scene.route_preview() if hasattr(scene, "route_preview") else (None, 0)
        if draft and scene.selected:
            self._route_unit = scene.selected
            self._draw_route(self.flat_feet(scene.selected), draft, (150, 255, 170), 220)
        for u in scene.combat.alive(PLAYER):
            o = u.order
            if not o:
                continue
            a = self.flat_feet(u)
            alpha = 200 if u is scene.selected else 90
            if o["type"] == "path":
                self._route_unit = u
                self._draw_route(a, o["cells"], T.TEAM_PLAYER, alpha)
            elif o["type"] == "move":
                b = P.ground_to_flat(*P.cell_ground(o["cell"]))
                pygame.draw.line(self.overlay, (*T.TEAM_PLAYER, alpha), a, b, 3)
                pygame.draw.circle(self.overlay, (*T.TEAM_PLAYER, alpha), b, 14, 3)
            elif o["type"] == "attack":
                pygame.draw.line(self.overlay, (*T.TEAM_ENEMY, alpha), a, self.flat_feet(o["target"]), 3)
            elif o["type"] == "skill":
                tgt = o["target"]
                b = self.flat_feet(tgt) if hasattr(tgt, "cell") else P.ground_to_flat(*P.cell_ground(tgt))
                pygame.draw.line(self.overlay, (*T.SELECT, alpha), a, b, 3)
                pygame.draw.circle(self.overlay, (*T.SELECT, alpha), b, 16, 3)

    def _draw_downed(self, surf, u):
        """Павший лежит на земле, потемневший."""
        key = (u.id, u.proto_id)
        img = self._dim.get(key)
        if img is None:
            img = pygame.transform.rotate(self.sprite_of(u), 90 if self.anim(u).facing > 0 else -90)
            img = img.copy()
            img.fill((110, 110, 120), special_flags=pygame.BLEND_RGB_MULT)
            self._dim[key] = img
        x, y = T.cell_feet(u.cell)
        img = self.scaled(img, self.depth(u))
        surf.blit(img, (x - img.get_width() / 2, y - img.get_height() + 6))

    def _draw_object(self, surf, u, scene):
        """Объект поля стоит неподвижно, вздрагивает от удара; источник — красное кольцо, охраняемый — синее."""
        rect = self.pix.draw_object(surf, u)      # ледяная стена — обрыв ледника (ui/pixglacier.py)
        if rect is not None:
            self.sprite_rects.append((rect, u))
            return
        fx, fy = self.feet_pos(u)
        a = self.anim(u)
        img = self.scaled(self.sprite_of(u, False, a.hit > HIT_T * 0.4), self.depth(u))
        w, h = img.get_size()
        dx = math.sin(self.clock * 90) * 2 if a.hit > 0 else 0
        if u.fuse > 0:                                # фитиль горит — бочка дрожит
            dx += math.sin(self.clock * 40) * 1.5
        lift = math.sin(math.pi * (1 - a.toss / TOSS_T)) * 60 if a.toss > 0 else 0
        shadow = pygame.Rect(0, 0, int(w * 0.55), max(8, int(w * 0.18)))
        shadow.center = (fx, fy)
        pygame.draw.ellipse(surf, T.mix(T.BG, (0, 0, 0), 0.5), shadow)
        if u.team == PLAYER:
            pygame.draw.ellipse(surf, T.TEAM_PLAYER, shadow.inflate(8, 4), 2)
        elif u.obj.get("source"):
            pygame.draw.ellipse(surf, T.TEAM_ENEMY, shadow.inflate(8, 4), 2)
        rect = pygame.Rect(fx - w / 2 + dx, fy - h + 4 - lift, w, h)
        surf.blit(img, rect)
        if u.fuse > 0 and int(self.clock * 12) % 2:
            pygame.draw.circle(surf, (255, 220, 120), (rect.centerx + 4, rect.top + 4), 4)
        sel = scene.selected
        if sel is not None and sel.order and sel.order.get("target") is u:     # выбранный герой бьёт по нему
            pygame.draw.ellipse(surf, T.TEAM_ENEMY, shadow.inflate(14, 6), 2)
        self.sprite_rects.append((rect, u))

    def _draw_unit(self, surf, u, selected, scene):
        if u.obj:
            self._draw_object(surf, u, scene)
            return
        fx, fy = self.feet_pos(u)
        a = self.anim(u)
        dk = self.depth(u)
        img = self.scaled(self.sprite_of(u, a.facing < 0, a.hit > HIT_T * 0.4), dk)
        if "stealth" in u.buffs:                     # в тени — едва видно (свой отряд видит силуэт)
            img = img.copy()
            img.set_alpha(80 + int(30 * math.sin(self.clock * 5)))
        w0, h0 = img.get_size()
        # дыхание, сжатие от удара, подскок при шаге, выпад к цели, дрожь
        ph = self.clock * 2.4 + u.id * 1.7
        sx, sy = 1 - 0.02 * math.sin(ph), 1 + 0.035 * math.sin(ph)
        if a.hit > 0:
            sx, sy = 1.08, 0.9
        hop = math.sin(math.pi * u.move_t) * 7 if u.move_t < 1 else 0
        if a.toss > 0:                                # брошен — летит по дуге
            hop += math.sin(math.pi * (1 - a.toss / TOSS_T)) * 60
        lk = math.sin(math.pi * (1 - a.lunge / LUNGE_T)) * 12 if a.lunge > 0 else 0
        dx, dy = a.lunge_dir[0] * lk, a.lunge_dir[1] * lk * 0.6
        if a.hit > 0:
            dx += math.sin(self.clock * 90) * 2
        if u.cast:
            dy -= 3 + math.sin(self.clock * 8) * 1.5
        look = ("sleep" if u.asleep else u.stun_look) if u.stun > 0 else None
        if look and self.pix.on and self.pix.spells.unit_held(u):
            look = None                               # заморозка ещё летит — на фигурке её пока нет
        if look == "levitate":                        # невесомость — парит над землёй
            hop += 26 + 4 * math.sin(self.clock * 4 + u.id)
        if look == "stun":                            # оглушён — шатается
            dx += math.sin(self.clock * 6) * 3
        elif look in ("root", "net", "trap"):         # схвачен — дёргается на месте, не дышит
            dx += math.sin(self.clock * 23) * 1.2
            sx, sy = 1.0, 1.0
        elif look in ("freeze", "stasis"):            # вморожен или вне времени — неподвижен
            sx, sy = 1.0, 1.0
        if u.flying:                                  # парит: выше земли и покачивается
            hop += 14 + 3 * math.sin(self.clock * 3 + u.id)
        if u.charmed:
            img = img.copy()
            img.fill((255, 150, 220, 255), special_flags=pygame.BLEND_RGBA_MULT)
        tint = {"freeze": (150, 205, 255), "blind": (120, 110, 130), "sleep": (170, 165, 195),
                "stasis": (255, 225, 150)}.get(look)
        if look == "shock" and int(self.clock * 14) % 3 == 0:
            tint = (200, 230, 255)
        if tint:
            img = img.copy()
            img.fill((*tint, 255), special_flags=pygame.BLEND_RGBA_MULT)
        w, h = max(1, int(w0 * sx)), max(1, int(h0 * sy))
        if (w, h) != (w0, h0):
            img = pygame.transform.scale(img, (w, h))
        # тень и кольцо команды у ног
        sw = int(w0 * (0.75 if u.boss else 0.62) * (0.7 if u.flying else 1.0))
        shadow = pygame.Rect(0, 0, sw, max(8, sw // 3))
        shadow.center = (fx, fy)
        pygame.draw.ellipse(surf, T.mix(T.BG, (0, 0, 0), 0.5), shadow)
        team = T.TEAM_PLAYER if u.team == PLAYER else T.TEAM_ENEMY
        if u.boss or u.elite:
            pygame.draw.ellipse(surf, (240, 200, 80) if u.boss else (200, 205, 215), shadow.inflate(10, 6), 2)
        pygame.draw.ellipse(surf, T.SELECT if selected else team, shadow.inflate(4, 2), 3 if selected else 2)
        if scene.phase == "deploy" and scene.picked is u:
            pygame.draw.ellipse(surf, (120, 255, 140), shadow.inflate(16, 8), 3)
        if u is self.hover_unit or u is getattr(scene, "pick", None):   # под курсором или в списке врагов
            col = T.SELECT if getattr(scene, "targeting", None) else (255, 255, 255)
            pulse = int(3 * math.sin(self.clock * 8))
            pygame.draw.ellipse(surf, col, shadow.inflate(20 + pulse, 10 + pulse // 2), 3)
        if look:                                      # под контролем — пульсирующее кольцо цвета контроля
            col = IC.CONTROL_COLORS.get(look, (255, 230, 120))
            pulse = int(4 + 3 * math.sin(self.clock * 7))
            pygame.draw.ellipse(surf, col, shadow.inflate(10 + pulse, 5 + pulse // 2), 3)
        rect = pygame.Rect(fx - w / 2 + dx, fy - h + 4 + dy - hop, w, h)
        if look == "trap":
            self._draw_trap(surf, fx, fy, dk)
        surf.blit(img, rect)
        froze = self.pix.on_unit(surf, u, rect, look, dk)
        if look and not (look == "freeze" and froze):
            self._draw_control(surf, u, look, rect, fx, fy, dk)
        if u.charmed:
            for i in range(2):
                ang = self.clock * 3 + i * math.pi
                hx, hy = rect.centerx + math.cos(ang) * rect.w * 0.4, rect.top + 4 + math.sin(ang) * 4
                surf.blit(IC.icon("charm", 14, (255, 120, 200)), (hx - 7, hy - 7))
        if u.shield:
            bubble = pygame.Surface((rect.w + 16, rect.h + 10), pygame.SRCALPHA)
            pygame.draw.ellipse(bubble, (190, 215, 255, 45), bubble.get_rect())
            pygame.draw.ellipse(bubble, (220, 235, 255, 170), bubble.get_rect(), 2)
            surf.blit(bubble, (rect.x - 8, rect.y - 5))
        self.sprite_rects.append((rect, u))

    def _draw_trap(self, surf, fx, fy, k):
        img = self.props.get("trap_closed")
        if img is not None:
            img = self.scaled(pygame.transform.scale(img, (img.get_width() * 2, img.get_height() * 2)), k)
            surf.blit(img, (fx - img.get_width() / 2, fy - img.get_height() * 0.7))

    def _draw_control(self, surf, u, look, rect, fx, fy, k):
        """Как выглядит контроль на фигурке: звёзды, корни, сеть, ледяная глыба, разряды, тьма, «Zz»."""
        t = self.clock
        grow = min(1.0, (u.stun_total - u.stun) / 0.3) if u.stun_total else 1.0
        if look == "stun":
            for i in range(4):
                ang = t * 4 + i * math.tau / 4
                x = rect.centerx + math.cos(ang) * rect.w * 0.36
                y = rect.top - 2 + math.sin(ang) * 5 * k
                IC._star(surf, (255, 225, 90) if math.sin(ang) > 0 else (220, 190, 80), x, y, 6 * k)
        elif look == "root":
            top = rect.bottom - rect.h * 0.5 * grow
            for i in range(6):
                bx = rect.x + rect.w * (0.18 + 0.13 * i)
                pts = []
                for j in range(6):
                    f = j / 5
                    y = rect.bottom + 2 - (rect.bottom + 2 - top) * f * (0.75 + 0.25 * ((i * 37) % 5) / 4)
                    x = bx + math.sin(f * 5 + i * 1.7 + t * 1.5) * 4 * k + (rect.centerx - bx) * f * 0.5
                    pts.append((x, y))
                pygame.draw.lines(surf, (40, 70, 30), False, pts, max(2, int(4 * k)))
                pygame.draw.lines(surf, (100, 170, 60), False, pts, max(1, int(2 * k)))
                lx, ly = pts[-1]
                pygame.draw.ellipse(surf, (130, 210, 80), (lx - 3 * k, ly - 2 * k, 6 * k, 4 * k))
        elif look == "net":
            box = rect.inflate(8, 0)
            box.height = int(box.height * grow)
            box.bottom = rect.bottom + 2
            old = surf.get_clip()
            surf.set_clip(box)
            step = max(6, int(9 * k))
            for x in range(box.x - box.h, box.right, step):
                pygame.draw.line(surf, (215, 185, 130), (x, box.bottom), (x + box.h, box.top), 2)
                pygame.draw.line(surf, (215, 185, 130), (x, box.top), (x + box.h, box.bottom), 2)
            surf.set_clip(old)
            pygame.draw.line(surf, (160, 130, 90), (box.x, box.top), (box.right, box.top), 2)
        elif look == "freeze":
            block = rect.inflate(int(12 * k), int(6 * k))
            ice = pygame.Surface(block.size, pygame.SRCALPHA)
            ice.fill((170, 220, 255, 80))
            pygame.draw.rect(ice, (235, 248, 255, 210), ice.get_rect(), 2)
            for i in range(3):
                x = int(block.w * (0.15 + 0.3 * i))
                pygame.draw.line(ice, (255, 255, 255, 140), (x, 4), (x + block.w // 5, block.h // 3), 2)
            surf.blit(ice, block)
        elif look == "shock":
            rng = int(t * 18)
            for i in range(3):
                h = (rng * 31 + i * 97 + u.id * 13) % 997
                x0 = rect.x + (h % max(1, rect.w))
                pts = [(x0, rect.top + 4)]
                for j in range(5):
                    hh = (h * (j + 3)) % 23 - 11
                    pts.append((x0 + hh * k, rect.top + 4 + (rect.h - 8) * (j + 1) / 5))
                pygame.draw.lines(surf, (150, 200, 255), False, pts, 3)
                pygame.draw.lines(surf, (250, 252, 255), False, pts, 1)
        elif look == "blind":
            cloud = pygame.Surface((rect.w + 20, int(rect.h * 0.55)), pygame.SRCALPHA)
            for i in range(5):
                cx = int(cloud.get_width() * (0.15 + 0.17 * i) + math.sin(t * 2 + i) * 3)
                pygame.draw.circle(cloud, (40, 32, 55, 150), (cx, cloud.get_height() // 2), int(10 * k))
            surf.blit(cloud, (rect.x - 10, rect.top - 6))
        elif look == "stasis":
            ring = pygame.Surface((rect.w + 24, rect.h + 16), pygame.SRCALPHA)
            pygame.draw.ellipse(ring, (240, 205, 110, 60), ring.get_rect())
            pygame.draw.ellipse(ring, (255, 225, 140, 220), ring.get_rect(), 2)
            surf.blit(ring, (rect.x - 12, rect.y - 8))
            surf.blit(IC.icon("stasis", int(22 * k), (240, 205, 110)), (rect.centerx - 11 * k, rect.top - 26 * k))
        elif look == "sleep":
            for i in range(2):
                ph = (t * 0.8 + i * 0.5) % 1.0
                T.text(surf, "Z" if i == 0 else "z", (rect.right - 6 + ph * 10, rect.top - ph * 22),
                       int((18 if i == 0 else 14) * k), (215, 195, 255), True, shadow=True)

    def _draw_hud(self, surf, u):
        """Поверх частиц: HP, статусы, каст, баффы, оглушение, AP и личная шкала."""
        fx, fy = self.cam(self.feet_pos(u))
        top = fy - self.unit_h(u) * (self.vfx.screen.zoom if self.gl_camera else 1)
        bw = 60
        bx, by = fx - bw / 2, top - 6
        if u.obj:                      # объекту — только полоска прочности, и то когда она важна
            if u.hp < u.max_hp or u.team != NEUTRAL:
                bw = 44
                bx, by = fx - bw / 2, top + 8
                pygame.draw.rect(surf, (20, 20, 20), (bx - 1, by - 1, bw + 2, 6))
                col = (120, 190, 255) if u.team == PLAYER else (230, 120, 80) if u.team == ENEMY else (200, 190, 170)
                pygame.draw.rect(surf, col, (bx, by, bw * max(0, u.hp) / u.max_hp, 4))
            return
        pygame.draw.rect(surf, (20, 20, 20), (bx - 1, by - 1, bw + 2, 8))
        k = u.hp / u.max_hp
        pygame.draw.rect(surf, T.mix((230, 60, 50), (90, 220, 90), k), (bx, by, bw * k, 6))
        if self.stats_mode() and u.level:          # режим героев: уровень слева от полоски HP
            col = (150, 200, 255) if u.team == PLAYER else ST.level_color(u.level - self.squad_level())
            s = str(u.level)
            w = T.font(12, True).size(s)[0] + 8
            box = pygame.Rect(bx - w - 3, by - 5, w, 15)
            pygame.draw.rect(surf, (16, 16, 22), box, border_radius=4)
            pygame.draw.rect(surf, col, box, 1, border_radius=4)
            T.text(surf, s, box.center, 12, col, True, center=True)
        if u.shield:
            sw = min(bw, bw * u.shield / u.max_hp)
            pygame.draw.rect(surf, (235, 240, 255), (bx, by - 3, sw, 2))
        if u.cast:
            kc = 1 - u.cast["left"] / u.cast["total"]
            pygame.draw.rect(surf, (20, 20, 20), (bx - 1, by + 7, bw + 2, 5))
            pygame.draw.rect(surf, T.CAST, (bx, by + 8, bw * kc, 3))
        # состояния: контроль первым, затем теги, щит, баффы — значки с полоской времени над HP
        states = IC.unit_states(u, self.data, self.combat)
        if states:
            IC.draw_row(surf, states, fx, by - 29, size=22, limit=5)
        # AP / PP: следующий пипс заполняется по мере восстановления
        ap_pos, pp_pos = self._pip_layout(u)
        pr = 5 if u.ap_max + u.pp_max <= 6 else 4
        for positions, color, cur, timer, regen in ((ap_pos, T.AP_COLOR, u.ap, u.ap_timer, u.ap_regen),
                                                     (pp_pos, self.gauge_color(u), u.pp, u.pp_timer, u.pp_regen)):
            for i, p in enumerate(positions):
                if i < cur:
                    pygame.draw.circle(surf, color, p, pr)
                    pygame.draw.circle(surf, (15, 15, 15), p, pr, 1)
                else:
                    pygame.draw.circle(surf, (15, 15, 15), p, pr)
                    pygame.draw.circle(surf, T.mix(color, (0, 0, 0), 0.45), p, pr, 1)
                    if i == cur and regen:
                        pygame.draw.circle(surf, T.mix(color, (0, 0, 0), 0.35), p, 1 + (pr - 2) * timer / regen)

    def stats_mode(self):
        return bool(self.combat and (self.combat.enemy_scale or {}).get("stats"))

    def squad_level(self):
        lv = [h.level for h in self.combat.heroes(PLAYER) if h.level]
        return ST.squad_level(lv) if lv else 1

    def gauge_color(self, u):
        return tuple(u.gauge["color"]) if u.gauge else T.PP_COLOR

    def gauge_name(self, u):
        return u.gauge["name"] if u.gauge else "PP"

    def _pip_layout(self, u):
        x, y = self.cam(self.feet_pos(u))
        total = u.ap_max + u.pp_max
        step = 12 if total <= 6 else max(7, 66 // max(1, total - 1))  # много пипсов — плотнее, в ширину клетки
        gap = (6 if u.ap_max and u.pp_max else 0)
        width = (total - 1) * step + gap
        px, py = x - width / 2, y + 12
        ap = [(px + i * step, py) for i in range(u.ap_max)]
        start = px + u.ap_max * step + gap
        pp = [(start + i * step, py) for i in range(u.pp_max)]
        return ap, pp

    def _draw_badge(self, surf, f, stack):
        """Плашка пассивки под юнитом, под пипсами — не налезает на соседей сбоку."""
        x, y = self.cam(self.feet_pos(f.unit))
        s = f.name + (f" ×{f.count}" if f.count > 1 else "")
        w, h = T.font(12, True).size(s)[0] + 14, 17
        bx = min(max(x - w / 2, T.GRID_X + 2), T.GRID_X + T.GRID_W - w - 2)
        by = y + 20 + stack * 19
        fade = max(0.0, (f.k - 0.75) / 0.25)
        rect = pygame.Rect(bx, by, w, h)
        pygame.draw.rect(surf, T.mix((48, 22, 40), T.BG, fade), rect, border_radius=8)
        pygame.draw.rect(surf, T.mix(T.PP_COLOR, T.BG, fade), rect, 1, border_radius=8)
        T.text(surf, s, rect.center, 12, T.mix((255, 205, 230), T.BG, fade), True, center=True)

    def _draw_fx(self, surf):
        badges = {}
        for f in self.fx:
            k = f.k
            if f.kind == "badge":
                n = badges.get(f.unit.id, 0)
                badges[f.unit.id] = n + 1
                self._draw_badge(surf, f, n)
            elif f.kind == "pip":
                _, pp_pos = self._pip_layout(f.unit)
                if f.idx < len(pp_pos):
                    pygame.draw.circle(surf, T.mix(T.PP_COLOR, T.BG, k), pp_pos[f.idx], 6 + 7 * k, 2)
            elif f.kind == "link":
                a, b = self.cam(self.unit_pos(f.src)), self.cam(self.unit_pos(f.dst))
                pygame.draw.line(surf, T.mix(f.color, T.BG, k), a, b, 2)
                pygame.draw.circle(surf, T.mix(f.color, T.BG, k), b, 5, 2)
            if f.kind == "line":
                col = T.mix(f.color, (0, 0, 0), k * 0.7)
                pygame.draw.line(surf, col, f.a, f.b, max(1, int(f.width * (1 - k) + 1)))
            elif f.kind == "ring":
                r = f.r0 + (f.r1 - f.r0) * k
                rect = pygame.Rect(0, 0, r * 2, r)
                rect.center = (f.x, f.y)
                pygame.draw.ellipse(surf, T.mix(f.color, (0, 0, 0), k * 0.8), rect, max(1, int(5 * (1 - k))))
            elif f.kind == "banner":
                a = min(1.0, (1 - k) * 4)
                col = T.mix(f.color, (0, 0, 0), 1 - a)
                T.text(surf, f.s, (T.GRID_X + T.GRID_W // 2, T.GRID_Y + 14), 30, col, True, center=True, shadow=True)
            elif f.kind == "text":
                y = f.y0 - 28 * k
                col = f.color if k < 0.7 else T.mix(f.color, (0, 0, 0), (k - 0.7) / 0.3 * 0.8)
                T.text(surf, f.s, self.cam((f.x, y)), f.size, col, True, center=True, shadow=True)

    def _draw_hover(self, surf, scene):
        pos = scene.hover_cell
        if not pos:
            return
        c = scene.combat
        u = c.unit_at(pos)
        lines = []
        if u and u.obj:
            col = T.TEAM_PLAYER if u.team == PLAYER else T.TEAM_ENEMY if u.team == ENEMY else (230, 210, 170)
            lines.append((u.name, col))
            lines.append((f"Прочность {max(0, u.hp)}/{u.max_hp}", T.TEXT))
            for line in T.wrap(u.obj.get("desc", ""), 14, 320):
                lines.append((line, (255, 210, 150)))
            if u.obj.get("pushable"):
                lines.append(("Можно толкнуть: удар о юнита или стену ранит обоих", T.TEXT_DIM))
            if u.obj.get("cover"):
                lines.append(("Укрывает соседа от выстрелов", T.TEXT_DIM))
            if u.team == NEUTRAL:
                lines.append(("Ничей: бить по нему — только приказом (клик врагом)", T.TEXT_DIM))
        elif u and scene.phase == "deploy" and u.team != PLAYER:
            # разведка: без точных цифр и списка навыков
            lines.append((u.name, T.TEAM_ENEMY))
            lines.append((self.role_name(u.proto), T.TEXT))
            if scene.scout_hp:
                lines.append((f"HP {u.max_hp}  атака {u.atk_damage}", T.TEXT))
            for tag in self.enemy_tags(u.proto):
                lines.append((f"Тег: {self.data.tags[tag]['name']}", self.tag_color(tag)))
            for m in self.enemy_marks(u.proto):
                lines.append((m, (255, 190, 120)))
        elif u:
            lines.append((f"{u.name}", T.TEAM_PLAYER if u.team == PLAYER else T.TEAM_ENEMY))
            if self.stats_mode() and u.level:
                lines.append((f"Уровень {u.level}" + (f" — {u.title}" if u.title else ""),
                              (150, 200, 255) if u.team == PLAYER else ST.level_color(u.level - self.squad_level())))
                if u.proto.get("attrs"):
                    a = u.proto["attrs"]
                    lines.append((f"Сила {a['str']:.0f} · Ловкость {a['agi']:.0f} · Интеллект {a['int']:.0f} · "
                                  f"крит {u.proto['crit'] * 100:.0f}% · уклон {u.proto['dodge'] * 100:.0f}%",
                                  (190, 210, 240)))
            lines.append((f"HP {u.hp}/{u.max_hp}  броня {u.total_armor()}  атака {u.atk_damage} (дал. {u.atk_range})",
                          T.TEXT))
            if u.atk_tag:
                lines.append((f"Атака с тегом: {self.data.tags[u.atk_tag]['name']}", self.tag_color(u.atk_tag)))
            for stat, (val, left) in u.buffs.items():
                lines.append((f"{BUFF_TEXT.get(stat, lambda v: stat)(val)} — {left:.1f}с",
                              (150, 240, 160) if buff_good(stat, val) else (255, 150, 120)))
            for tag, left in u.statuses.items():
                tg = self.data.tags[tag]
                lines.append((f"{tg['name']} {left:.1f}с — {tg['status']}", tuple(tg["color"])))
            if u.passive:
                lines.append((f"Пассив: {u.passive['name']} — {u.passive['desc']}", self.gauge_color(u)))
            if u.gauge:
                lines.append((f"{u.gauge['name']} {u.pp}/{u.pp_max}: {u.gauge['desc']}", self.gauge_color(u)))
            if u.cast:
                lines.append((f"Кастует: {u.skill_defs[u.cast['skill']]['name']} ({u.cast['left']:.1f}с)", T.CAST))
            if u.on_death:
                lines.append((f"При смерти: {u.on_death['name']}", (255, 170, 90)))
        cell = c.grid.get(pos)
        cfg = self.data.config
        desc = cfg["terrain"][cell.terrain]["name"]
        if cell.cover:
            desc += ", полное укрытие (−50% дальнего урона)" if cell.cover == "full" else ", половина укрытия (−25%)"
        if cell.hazard:
            desc += f", {cfg['hazards'][cell.hazard]['name']}"
        if cell.terrain == "water" and not cell.hazard:
            desc += " — делает мокрым"
        lines.append((desc, T.TEXT_DIM))
        who = scene.selected if scene.selected and scene.selected.alive else u
        if who is not None and not who.obj:
            k = MV.step_cost(c, who, pos)
            if k > 1.01:
                lines.append((f"Ход для «{who.name}»: ×{k:g} медленнее", (255, 180, 110)))
        if u is not None:
            tr = [self.data.traits_def[t]["name"] + f" ({self.data.traits_def[t]['desc']})"
                  for t in sorted(MV.traits(c, u)) if t in self.data.traits_def]
            if tr:
                lines.append(("Особенности: " + ", ".join(tr), (170, 210, 255)))

        w = max(T.font(14).size(s)[0] for s, _ in lines) + 16
        h = len(lines) * 18 + 10
        r = T.cell_rect(pos)
        bx = r.right + 6
        if bx + w > RIGHT_X - 4:
            bx = max(4, r.x - w - 6)
        by = min(r.y, BOTTOM_Y - h - 4)
        box = pygame.Rect(bx, by, w, h)
        pygame.draw.rect(surf, (12, 14, 18), box, border_radius=6)
        pygame.draw.rect(surf, T.PANEL_EDGE, box, 1, border_radius=6)
        for i, (s, col) in enumerate(lines):
            T.text(surf, s, (bx + 8, by + 5 + i * 18), 14, col)

    def _draw_top(self, surf, scene):
        c = scene.combat
        T.text(surf, c.enc["name"], (T.GRID_X, 14), 26, T.TEXT, True)
        if scene.phase == "deploy":
            T.text(surf, "Разведка и расстановка", (T.GRID_X + 380, 20), 20, (120, 255, 140), True)
            b = pygame.Rect(T.GRID_X + T.GRID_W - 190, 10, 190, 44)
            self.start_button = b
            hot = b.collidepoint(scene.mouse)
            pygame.draw.rect(surf, (60, 140, 80) if hot else (44, 110, 62), b, border_radius=8)
            pygame.draw.rect(surf, (120, 255, 140), b, 2, border_radius=8)
            T.text(surf, "В БОЙ  (Пробел)", b.center, 20, (255, 255, 255), True, center=True, shadow=True)
            T.text(surf, "ЛКМ по юниту, затем по клетке", (RIGHT_X, 10), 13, T.TEXT_DIM)
            T.text(surf, "или перетащите · ПКМ/Esc — отмена", (RIGHT_X, 30), 13, T.TEXT_DIM)
            return
        self.start_button = None
        m, s = divmod(int(c.time), 60)
        T.text(surf, f"{m}:{s:02d}", (T.GRID_X + 380, 20), 20, T.TEXT_DIM, True)
        speed = self.data.config["speeds"][scene.speed_idx]
        T.text(surf, f"скорость ×{speed:g}", (T.GRID_X + 450, 22), 16, T.TEXT_DIM)
        if scene.paused and not c.result:
            T.text(surf, "ПАУЗА", (T.GRID_X + 590, 16), 24, T.SELECT, True)
        elif scene.slowmo:
            T.text(surf, "ЗАМЕДЛЕНИЕ", (T.GRID_X + 590, 18), 22, (150, 210, 255), True)
        T.text(surf, "Space пауза · Shift замедл. · F1–F3 скорость", (RIGHT_X, 10), 13, T.TEXT_DIM)
        T.text(surf, "Q–T навыки · вести ПКМ — маршрут · Shift+ПКМ — точка", (RIGHT_X, 30), 13, T.TEXT_DIM)

    def _side_panel(self, surf):
        panel = pygame.Rect(RIGHT_X, PANEL_Y, T.SCREEN_W - RIGHT_X - 16, T.SCREEN_H - PANEL_Y - 16)
        pygame.draw.rect(surf, T.PANEL, panel, border_radius=8)
        return panel

    def _draw_enemies(self, surf, scene, panel, y, bottom):
        """Враги на поле одним списком: HP и все состояния со временем — без наведения на каждого.
        Наведение подсвечивает врага на поле, клик — атаковать его выбранным героем."""
        foes = [u for u in scene.combat.fighters(ENEMY) if not u.hidden]
        foes.sort(key=lambda u: (not u.boss, not u.elite, u.cell[0], u.cell[1]))
        self.enemy_rects = []
        self.hover_unit = None
        if not foes:
            return y
        T.text(surf, f"Враги ({len(foes)})", (panel.x + 10, y), 16, T.TEXT_DIM, True)
        y += 22
        rows = max(1, (bottom - y) // 24)
        for u in foes[:rows]:
            r = pygame.Rect(panel.x + 6, y, panel.w - 12, 22)
            self.enemy_rects.append((r, u))
            if r.collidepoint(scene.mouse):
                self.hover_unit = u
                pygame.draw.rect(surf, (52, 56, 68), r, border_radius=5)
            pygame.draw.circle(surf, u.color, (r.x + 11, r.centery), 9)
            pygame.draw.circle(surf, (240, 200, 80) if u.boss else T.TEAM_ENEMY, (r.x + 11, r.centery), 9, 2)
            T.text(surf, u.label, (r.x + 11, r.centery), 11, (255, 255, 255), True, center=True, shadow=True)
            name = f"[{u.level}] {u.name}" if self.stats_mode() and u.level else u.name
            T.text(surf, fit(name, 13, 110), (r.x + 25, r.y + 3), 13,
                   ST.level_color(u.level - self.squad_level()) if self.stats_mode() and u.level else T.TEXT)
            bx, bw = r.x + 140, 54
            pygame.draw.rect(surf, (15, 15, 15), (bx, r.y + 8, bw, 6))
            pygame.draw.rect(surf, T.mix((230, 60, 50), (90, 220, 90), max(0, u.hp) / u.max_hp),
                             (bx, r.y + 8, bw * max(0, u.hp) / u.max_hp, 6))
            states = IC.unit_states(u, self.data, self.combat)
            if states:
                rects = IC.draw_row(surf, states, bx + bw + 6, r.y + 1, size=16, gap=2, limit=4, center=False)
                self.icon_tips += [(ir, st[3]) for ir, st in zip(rects, states)]
            y += 24
        if len(foes) > rows:
            T.text(surf, f"и ещё {len(foes) - rows}", (panel.x + 10, y), 12, T.TEXT_DIM)
            y += 16
        return y + 6

    def _draw_icon_tip(self, surf, scene):
        """Подсказка к значку состояния в панели: что это и сколько осталось."""
        for r, text in self.icon_tips:
            if r.collidepoint(scene.mouse):
                w = T.font(13).size(text)[0] + 14
                box = pygame.Rect(min(r.x, T.SCREEN_W - w - 4), r.bottom + 6, w, 22)
                pygame.draw.rect(surf, (12, 14, 18), box, border_radius=5)
                pygame.draw.rect(surf, T.PANEL_EDGE, box, 1, border_radius=5)
                T.text(surf, text, (box.x + 7, box.y + 3), 13, T.TEXT)
                return

    def _draw_right(self, surf, scene):
        panel = self._side_panel(surf)
        y = self._draw_squad(surf, scene, panel)
        y = self._draw_enemies(surf, scene, panel, y, panel.y + 470)
        T.text(surf, "Журнал", (panel.x + 10, y), 16, T.TEXT_DIM, True)
        y += 22
        log_bottom = panel.bottom - 128
        rows = []
        for s, col in self.log:
            for line in T.wrap(s, 13, panel.w - 20):
                rows.append((line, col))
        max_rows = (log_bottom - y) // 17
        for line, col in rows[-max_rows:]:
            T.text(surf, line, (panel.x + 10, y), 13, col)
            y += 17
        self._draw_legend(surf, panel)
        self._draw_icon_tip(surf, scene)

    # ---------- разведка ----------

    ROLE_NAMES = {"melee": "Ближний бой", "ranged": "Дальний бой", "caster": "Маг", "support": "Поддержка"}

    def role_name(self, proto):
        return self.ROLE_NAMES.get(proto["role"], proto["role"])

    def enemy_tags(self, proto):
        tags = [proto["attack"].get("tag")]
        for sid in proto.get("skills", []):
            tags += [eff.get("tag") for eff in self.data.skills[sid]["effects"]]
        if proto.get("on_death"):
            tags += [eff.get("tag") for eff in proto["on_death"]["effects"]]
        return list(dict.fromkeys(t for t in tags if t))

    def enemy_marks(self, proto):
        marks = []
        if proto.get("boss"):
            marks.append("Босс")
        if proto.get("elite"):
            marks.append("Элита")
        if proto.get("passive"):
            marks.append(f"Защита: {proto['passive']['name']}")
        if any(eff["type"] == "heal" for sid in proto.get("skills", []) for eff in self.data.skills[sid]["effects"]):
            marks.append("Лечит союзников")
        if proto.get("on_death"):
            marks.append(f"При смерти: {proto['on_death']['name']}")
        return marks

    def _draw_scouting(self, surf, scene):
        panel = self._side_panel(surf)
        y = self._draw_squad(surf, scene, panel)
        T.text(surf, "Разведка", (panel.x + 10, y), 16, T.TEXT_DIM, True)
        y += 24
        groups = {}
        hidden = 0
        for u in scene.combat.units:
            if u.obj:
                continue
            if u.team != PLAYER and u.hidden:
                hidden += 1
            elif u.team != PLAYER:
                groups.setdefault(u.proto_id, []).append(u)
        c = scene.combat
        notes = []
        if c.wave_total > 1:
            more = sum(len(w) for w in c.waves)
            notes.append(f"Волн: {c.wave_total} (ещё {more} врагов). Между волнами — передышка "
                         f"{c.cfg['waves']['intermission']:g} с, ничего не восстанавливается")
        if c.phases:
            notes.append(f"Босс меняется по ходу боя: фаз {len(c.phases) + 1}, на каждой — подкрепление")
        props = [u for u in c.units if u.obj and u.team == NEUTRAL]
        if props:
            names = ", ".join(dict.fromkeys(u.name.lower() for u in props))
            notes.append(f"На поле: {names}")
        for note in notes:
            for line in T.wrap(note, 13, panel.w - 20):
                T.text(surf, line, (panel.x + 10, y), 13, (150, 210, 255))
                y += 17
        if notes:
            y += 4
        if hidden:
            T.text(surf, f"Туман скрывает ещё {hidden} {'врага' if hidden < 5 else 'врагов'}", (panel.x + 10, y), 14,
                   (190, 200, 230), True)
            y += 22
        mech = getattr(scene.combat, "chapter", {}).get("events", [])
        if mech:
            names = ", ".join(dict.fromkeys(ev.get("name", ev["type"]) for ev in mech))
            for line in T.wrap(f"События поля: {names}", 13, panel.w - 20):
                T.text(surf, line, (panel.x + 10, y), 13, (255, 200, 120))
                y += 17
            y += 4
        roles, all_tags = {}, []
        for units in groups.values():
            u = units[0]
            roles[self.role_name(u.proto)] = roles.get(self.role_name(u.proto), 0) + len(units)
            tags = self.enemy_tags(u.proto)
            all_tags += tags
            pygame.draw.circle(surf, u.color, (panel.x + 22, y + 14), 14)
            pygame.draw.circle(surf, T.TEAM_ENEMY, (panel.x + 22, y + 14), 14, 2)
            T.text(surf, u.label, (panel.x + 22, y + 14), 13, (255, 255, 255), True, center=True, shadow=True)
            count = f" ×{len(units)}" if len(units) > 1 else ""
            T.text(surf, f"{u.name}{count}", (panel.x + 44, y), 15, T.TEXT, True)
            x = panel.x + 44
            role = self.role_name(u.proto)
            if scene.scout_hp:
                role += f" · HP {u.max_hp} · атака {u.atk_damage}"
            T.text(surf, role, (x, y + 19), 13, T.TEXT_DIM)
            x += T.font(13).size(role)[0] + 10
            for tag in tags:
                pygame.draw.circle(surf, self.tag_color(tag), (x + 6, y + 28), 6)
                x += 16
            y += 40
            for m in self.enemy_marks(u.proto):
                T.text(surf, m, (panel.x + 44, y - 2), 13, (255, 190, 120))
                y += 16
            y += 4
        y += 4
        threats = " · ".join(f"{k.lower()} ×{v}" for k, v in roles.items())
        for line in T.wrap(f"Угрозы: {threats}", 13, panel.w - 20):
            T.text(surf, line, (panel.x + 10, y), 13, T.TEXT)
            y += 17
        x = panel.x + 10
        T.text(surf, "Теги врагов:", (x, y), 13, T.TEXT)
        x += T.font(13).size("Теги врагов:")[0] + 6
        for tag in dict.fromkeys(all_tags):
            name = self.data.tags[tag]["name"]
            T.text(surf, name, (x, y), 13, self.tag_color(tag), True)
            x += T.font(13, True).size(name)[0] + 8
        self._draw_legend(surf, panel)

    def _draw_squad(self, surf, scene, panel):
        c = scene.combat
        y = panel.y + 8
        T.text(surf, "Отряд", (panel.x + 10, y), 16, T.TEXT_DIM, True)
        y += 24
        self.squad_rects = []
        for i, u in enumerate(c.heroes(PLAYER)):
            r = pygame.Rect(panel.x + 6, y, panel.w - 12, 46)
            self.squad_rects.append((r, u))
            if u is scene.selected:
                pygame.draw.rect(surf, (52, 56, 68), r, border_radius=6)
            col = u.color if u.alive else (70, 70, 70)
            pygame.draw.circle(surf, col, (r.x + 22, r.centery), 15)
            pygame.draw.circle(surf, T.TEAM_PLAYER if u.alive else (90, 90, 90), (r.x + 22, r.centery), 15, 2)
            T.text(surf, u.label, (r.x + 22, r.centery), 16, (255, 255, 255), True, center=True, shadow=True)
            T.text(surf, f"{i + 1}. {u.name}", (r.x + 44, r.y + 3), 15, T.TEXT if u.alive else T.TEXT_DIM, True)
            if not u.alive:
                T.text(surf, "выбыл", (r.x + 44, r.y + 24), 13, T.TEXT_DIM)
            elif u.merged > 0:
                T.text(surf, f"внутри союзника {u.merged:.1f} с", (r.x + 44, r.y + 24), 13, (255, 170, 200))
            else:
                bw = 120
                pygame.draw.rect(surf, (15, 15, 15), (r.x + 44, r.y + 26, bw, 8))
                pygame.draw.rect(surf, T.mix((230, 60, 50), (90, 220, 90), u.hp / u.max_hp),
                                 (r.x + 44, r.y + 26, bw * u.hp / u.max_hp, 8))
                T.text(surf, f"{u.hp}", (r.x + 44 + bw + 6, r.y + 21), 13, T.TEXT)
                px = r.x + 205
                for i2 in range(u.ap_max):
                    pygame.draw.circle(surf, T.AP_COLOR if i2 < u.ap else T.mix(T.AP_COLOR, (0, 0, 0), 0.6), (px + i2 * 10, r.y + 14), 4)
                gc = self.gauge_color(u)
                for i2 in range(u.pp_max):
                    pygame.draw.circle(surf, gc if i2 < u.pp else T.mix(gc, (0, 0, 0), 0.6), (px + i2 * 10, r.y + 30), 4)
                states = IC.unit_states(u, self.data, self.combat)
                if states:
                    rects = IC.draw_row(surf, states[:3], r.right - 3 * 18 - 2, r.y + 24, size=16, gap=2, limit=3,
                                        center=False)
                    self.icon_tips += [(ir, st[3]) for ir, st in zip(rects, states)]
            y += 50
        return y + 6

    def _draw_legend(self, surf, panel):
        y = panel.bottom - 120
        pygame.draw.line(surf, T.PANEL_EDGE, (panel.x + 8, y - 4), (panel.right - 8, y - 4))
        T.text(surf, "Реакции тегов", (panel.x + 10, y), 15, T.TEXT_DIM, True)
        y += 22
        for r in self.data.reactions["unit"]:
            a, b = r["tags"]
            x = panel.x + 14
            for tag in (a, b):
                pygame.draw.circle(surf, self.tag_color(tag), (x, y + 9), 8)
                T.text(surf, self.data.tags[tag]["short"], (x, y + 9), 11, (10, 10, 10), True, center=True)
                x += 20
            T.text(surf, f"{r['name']}: {r['desc']}", (x + 2, y), 13, T.TEXT)
            y += 22

    def _draw_bottom(self, surf, scene):
        panel = pygame.Rect(T.GRID_X, BOTTOM_Y, T.GRID_W, T.SCREEN_H - BOTTOM_Y - 16)
        pygame.draw.rect(surf, T.PANEL, panel, border_radius=8)
        self.skill_rects = []
        self.auto_rects = []
        u = scene.selected
        if not u:
            T.text(surf, "Выберите юнита: клик по нему, Tab или 1–4.", (panel.x + 16, panel.y + 16), 18, T.TEXT_DIM)
            return
        x, y = panel.x + 14, panel.y + 10
        lvl = u.proto.get("level", 1)
        T.text(surf, u.name + (f"  ·  ур. {lvl}" if lvl > 1 else ""), (x, y), 22, T.TEXT, True)
        y += 32
        T.text(surf, f"HP {u.hp}/{u.max_hp}   броня {u.total_armor()}", (x, y), 15, T.TEXT)
        y += 20
        T.text(surf, f"Атака {u.atk_damage}, дальность {u.atk_range}, раз в {u.atk_cd:g}с", (x, y), 14, T.TEXT_DIM)
        y += 22
        T.text(surf, f"AP {u.ap}/{u.ap_max}  (+1 за {u.ap_regen:g}с)", (x, y), 15, T.AP_COLOR, True)
        y += 20
        gc = self.gauge_color(u)
        if u.gauge:
            T.text(surf, f"{u.gauge['name']} {u.pp}/{u.pp_max}", (x, y), 15, gc, True)
            T.text(surf, fit(u.gauge["desc"], 12, 236 - T.font(15, True).size(f"{u.gauge['name']} 0/0")[0] - 10),
                   (x + T.font(15, True).size(f"{u.gauge['name']} {u.pp}/{u.pp_max}")[0] + 8, y + 2), 12, T.TEXT_DIM)
        else:
            T.text(surf, f"PP {u.pp}/{u.pp_max}  (+1 за {u.pp_regen:g}с)", (x, y), 15, gc, True)
        y += 22
        if u.passive:
            p = u.passive
            ready = u.pp >= p["pp"]
            T.text(surf, f"{p['name']} — {'готов' if ready else 'копится'}", (x, y), 13,
                   gc if ready else T.TEXT_DIM, True)
            y += 16
            for line in T.wrap(p["desc"].replace("PP", self.gauge_name(u)), 13, 230)[:2]:
                T.text(surf, line, (x, y), 13, gc if ready else T.TEXT_DIM)
                y += 16

        cx = panel.x + 262
        n = max(1, len(u.skills))
        compact = n > 4
        cw = max(48, (panel.right - cx - 10 - (n - 1) * 8) // n)
        for i, sid in enumerate(u.skills):
            sk = u.skill_defs[sid]
            r = pygame.Rect(cx + i * (cw + 8), panel.y + 10, cw, panel.h - 20)
            self.skill_rects.append((r, i))
            active = scene.targeting == sid
            pygame.draw.rect(surf, (44, 48, 58) if not active else (70, 64, 36), r, border_radius=8)
            pygame.draw.rect(surf, T.SELECT if active else T.PANEL_EDGE, r, 2, border_radius=8)
            T.text(surf, SKILL_KEYS[i] if i < len(SKILL_KEYS) else str(i + 1), (r.x + 10, r.y + 6), 20, T.SELECT, True)
            for j, line in enumerate(T.wrap(sk["name"], 15, cw - 40, True)[:2]):
                T.text(surf, line, (r.x + 34, r.y + 8 + j * 18), 15, T.TEXT, True)
            ap_col = T.AP_COLOR if u.ap >= sk["ap"] else (255, 100, 100)
            info_y = r.y + 46
            T.text(surf, f"AP {sk['ap']}", (r.x + 10, info_y), 14, ap_col, True)
            extra = []
            if sk["cast"]:
                extra.append(f"каст {sk['cast']:g}с")
            if sk["range"]:
                extra.append(f"дал. {sk['range']}")
            if sk["cooldown"]:
                extra.append(f"кд {sk['cooldown']:g}с")
            if compact:
                T.text(surf, " · ".join(extra), (r.x + 10, info_y + 18), 12, T.TEXT_DIM)
                info_y += 16
            else:
                T.text(surf, " · ".join(extra), (r.x + 56, info_y + 1), 13, T.TEXT_DIM)
            max_lines = (r.bottom - info_y - 50) // 16
            for j, line in enumerate(T.wrap(sk["desc"], 13, cw - 18)[:max_lines]):
                T.text(surf, line, (r.x + 10, info_y + 22 + j * 16), 13, T.TEXT)
            for eff in sk["effects"]:
                if eff.get("tag"):
                    pygame.draw.circle(surf, self.tag_color(eff["tag"]), (r.right - 14, r.y + 16), 7)
                    break
            if sk.get("branch"):
                b, tier = sk["branch"]
                T.text(surf, f"{b}{tier}", (r.right - 14, r.y + 34), 12, (255, 150, 90), True, center=True)
            cd = u.cooldowns.get(sid, 0)
            if cd > 0:
                shade = pygame.Surface(r.size, pygame.SRCALPHA)
                shade.fill((0, 0, 0, 150))
                surf.blit(shade, r)
                T.text(surf, f"{cd:.1f}с", r.center, 24, T.TEXT, True, center=True)
            st = u.autocast.get(sid)
            if st is not None:
                strip = pygame.Rect(r.x + 4, r.bottom - 26, r.w - 8, 22)
                self.auto_rects.append((strip, i))
                on = st["on"]
                pygame.draw.rect(surf, (36, 78, 48) if on else (40, 42, 50), strip, border_radius=5)
                if strip.collidepoint(scene.mouse):
                    pygame.draw.rect(surf, (110, 220, 130) if on else T.PANEL_EDGE, strip, 1, border_radius=5)
                label = fit(AC.setting_label(st, self.data.tags), 12, strip.w - 10)
                T.text(surf, label, strip.center, 12, (200, 255, 210) if on else T.TEXT_DIM, on, center=True)
        ed = scene.editor
        if ed and ed["unit"] is u:
            for r, i in self.skill_rects:
                if i == ed["idx"]:
                    w, h = 340, ed["editor"].height()
                    box = pygame.Rect(min(max(r.centerx - w // 2, T.GRID_X), T.GRID_X + T.GRID_W - w),
                                      BOTTOM_Y - h - 6, w, h)
                    ed["rect"] = box
                    ed["editor"].draw(surf, box, scene.mouse)

    def _draw_result(self, surf, result, scene):
        shade = pygame.Surface((T.SCREEN_W, T.SCREEN_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        surf.blit(shade, (0, 0))
        win = result == "victory"
        cx = T.GRID_X + T.GRID_W // 2
        T.text(surf, "ПОБЕДА" if win else "ПОРАЖЕНИЕ", (cx, 280), 64, (120, 230, 120) if win else (240, 90, 80), True,
               center=True, shadow=True)
        hint = "Enter — продолжить" if scene.run_mode else "R — переиграть (с расстановки)    N — следующий бой"
        T.text(surf, hint, (cx, 350), 22, T.TEXT, center=True, shadow=True)
