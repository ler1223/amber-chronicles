"""Галерея эффектов: настоящий маленький бой на манекенах (как превью навыка), навык применяется только по нажатию —
сцена остаётся с последствиями (горящая земля, следы, лёд, пар), пока не нажмёшь ещё раз.

python tools/vfx_gallery.py                  окно
python tools/vfx_gallery.py --only fireball  сразу выбран навык (первое совпадение)
python tools/vfx_gallery.py --sheet out.png --only fireball,meteor --times 0.2,0.6,1.5,3
                                             раскадровка без окна: время — от начала каста

В окне:
  список слева — мышью (колесо листает), ↑/↓, PgUp/PgDn; набор букв — поиск по названию (Backspace стирает)
  клик / Enter / Пробел / F5 — применить выбранный (ещё раз — сцена сбрасывается); сам навык не повторяется
  F2 — рельеф под целью: обычный → вода → камень → лёд → лава;  F9 — пиксельные / старые эффекты
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

parser = argparse.ArgumentParser()
parser.add_argument("--sheet")
parser.add_argument("--only")
parser.add_argument("--times", default="0.3,0.8,1.6,3.0")
args = parser.parse_args()
if args.sheet:
    os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame  # noqa: E402

from sim import meta  # noqa: E402
from sim.build import build_proto  # noqa: E402
from sim.data import GameData  # noqa: E402
from ui import theme as T  # noqa: E402
from ui.pixfx import family  # noqa: E402
from ui.present import Presenter  # noqa: E402
from ui.settings import SETTINGS  # noqa: E402
from ui.skill_preview import BACK, MAIN, SIDE, SkillPreview  # noqa: E402

LIST_W = 380
VIEW = pygame.Rect(LIST_W + 10, 40, T.SCREEN_W - LIST_W - 20, T.SCREEN_H - 90)
TERRAINS = [None, "water", "stone", "ice_floor", "lava"]
TERRAIN_NAMES = {None: "обычный", "water": "вода", "stone": "камень", "ice_floor": "лёд", "lava": "лава"}
ROW = 24


def entries(data):
    """(подпись, класс, путь, ветки, навык): навыки всех героев на всех путях, база и ветки A2/B2;
    затем вражеские навыки огня и льда (их применяет маг)."""
    out, seen = [], set()
    for cls, c in data.classes.items():
        for path in [None] + list(meta.paths_for(data, cls)):
            proto = build_proto(data, cls, path=path)
            for sid in proto["skills"]:
                for br in [None] + sorted(data.branches.get(sid, {})):
                    key = (sid, br)
                    if key in seen:
                        continue
                    seen.add(key)
                    sk = data.skills[sid]
                    fam = family(sk)
                    mark = {"fire": "  [огонь]", "ice": "  [лёд]"}.get(fam, "")
                    label = f"{c['name']} · {sk['name']}" + (f" ({br}2)" if br else "") + mark
                    out.append((label, cls, path, {sid: (br, 2)} if br else {}, sid))
    for sid, sk in data.skills.items():
        if sid.startswith("e_") and family(sk):
            out.append((f"враг · {sk['name']}  [{'огонь' if family(sk) == 'fire' else 'лёд'}]", "mage", None, {},
                        sid))
    return out


class Gallery:
    """Сцена для Presenter: превью-бой справа, список навыков слева."""

    def __init__(self, data):
        self.data = data
        self.items = entries(data)
        self.filter = ""
        self.sel = 0
        self.scroll = 0
        self.terrain = 0
        self.pv = SkillPreview(data, VIEW, loop=False, zoom=105)
        self.mouse = (0, 0)
        self.play()

    # ---------- выбор ----------

    def shown(self):
        f = self.filter.lower()
        return [i for i, it in enumerate(self.items) if f in it[0].lower() or f in it[4].lower()]

    def current(self):
        sh = self.shown()
        return self.items[sh[min(self.sel, len(sh) - 1)]] if sh else None

    def _inject(self, sid):
        """Вражеский навык — магу в руки: тот же бой и манекены."""
        p = self.pv.proto
        if sid not in p["skill_defs"]:
            p["skill_defs"][sid] = self.data.skills[sid]
            p["skills"] = list(p["skills"]) + [sid]

    def play(self):
        it = self.current()
        if it is None:
            return
        _, cls, path, branches, sid = it
        pv = self.pv
        ter = TERRAINS[self.terrain]
        pv.terrain = {} if ter is None else {p: ter for p in self._area(MAIN, 1) + [SIDE, BACK]}
        if sid.startswith("e_"):
            pv.proto = build_proto(self.data, cls, branches=branches, path=path)
            self._inject(sid)
            pv.cls, pv.sid, pv.title = cls, sid, ""
            pv.restart()
        else:
            pv.show(cls, path, branches, sid)
        for u in (pv.caster, pv.ally):            # только навык — без автоатак, чтобы видеть последствия
            u.attack_timer = u.atk_cd = 999.0

    @staticmethod
    def _area(c, r):
        return [(c[0] + dx, c[1] + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1)]

    def move(self, d):
        n = len(self.shown())
        if not n:
            return
        self.sel = max(0, min(n - 1, self.sel + d))
        vis = (T.SCREEN_H - 120) // ROW
        if self.sel < self.scroll:
            self.scroll = self.sel
        elif self.sel >= self.scroll + vis:
            self.scroll = self.sel - vis + 1

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
        elif ev.type == pygame.MOUSEWHEEL:
            n = len(self.shown())
            self.scroll = max(0, min(max(0, n - 5), self.scroll - ev.y * 3))
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and ev.pos[0] < LIST_W and ev.pos[1] >= 68:
            i = self.scroll + (ev.pos[1] - 68) // ROW
            if 0 <= i < len(self.shown()):
                self.sel = i
                self.play()
        elif ev.type == pygame.KEYDOWN:
            k = ev.key
            if k in (pygame.K_UP, pygame.K_DOWN):
                self.move(-1 if k == pygame.K_UP else 1)
            elif k in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
                self.move(-15 if k == pygame.K_PAGEUP else 15)
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_F5):
                self.play()                       # применить (ещё раз) — только по нажатию
            elif k == pygame.K_F2:
                self.terrain = (self.terrain + 1) % len(TERRAINS)
                self.play()
            elif k == pygame.K_F9:
                SETTINGS["pixel_fx"] = not SETTINGS.get("pixel_fx", True)
                self.play()
            elif k == pygame.K_BACKSPACE:
                self.filter = self.filter[:-1]
                self.sel = self.scroll = 0
            elif ev.unicode and ev.unicode.isprintable():
                self.filter += ev.unicode         # поиск по названию: русские и латинские буквы
                self.sel = self.scroll = 0

    # ---------- кадр (для Presenter) ----------

    def update(self, dt):
        self.pv.update(dt)

    @property
    def vfx(self):
        return self.pv.vfx

    def plane(self):
        return self.pv.plane()

    def glow_layer(self):
        return self.pv.view.glow_layer()

    def draw_layers(self, world, ui, units):
        world.fill((0, 0, 0))
        self.pv.draw_layers(world, units, ui)
        self._draw_ui(ui)

    def draw(self, surf):
        self.pv.draw_cpu(surf)
        self._draw_ui(surf)

    def _draw_ui(self, surf):
        pygame.draw.rect(surf, (18, 20, 28), (0, 0, LIST_W, T.SCREEN_H))
        T.text(surf, "Поиск: " + (self.filter or "— набери буквы —"), (12, 14), 16,
               (255, 230, 150) if self.filter else T.TEXT_DIM)
        sh = self.shown()
        T.text(surf, f"{len(sh)} из {len(self.items)}", (12, 40), 13, T.TEXT_DIM)
        vis = (T.SCREEN_H - 120) // ROW
        for row, idx in enumerate(sh[self.scroll:self.scroll + vis]):
            i = self.scroll + row
            y = 70 + row * ROW
            label = self.items[idx][0]
            if i == self.sel:
                pygame.draw.rect(surf, (60, 74, 110), (4, y - 2, LIST_W - 8, ROW))
            elif pygame.Rect(4, y - 2, LIST_W - 8, ROW).collidepoint(self.mouse):
                pygame.draw.rect(surf, (34, 38, 52), (4, y - 2, LIST_W - 8, ROW))
            col = (255, 170, 110) if "[огонь]" in label else (160, 210, 255) if "[лёд]" in label else (225, 225, 235)
            T.text(surf, label[:46], (12, y), 14, col)
        it = self.current()
        title = it[0] if it else "ничего не найдено"
        T.text(surf, title, (VIEW.x, 10), 18, (255, 235, 170), shadow=True)
        mode = "пиксельные" if SETTINGS.get("pixel_fx", True) else "старые"
        T.text(surf, f"Enter / Пробел / F5 — применить · F2 — под целью: {TERRAIN_NAMES[TERRAINS[self.terrain]]} · "
               f"F9 — эффекты: {mode} · ↑/↓, колесо — выбор · буквы — поиск · Esc — выход",
               (VIEW.x, T.SCREEN_H - 30), 14, T.TEXT_DIM)


def main():
    pygame.init()
    data = GameData()
    if args.sheet:
        screen = pygame.display.set_mode((10, 10))
        presenter = Presenter(screen, True, window=False)
    else:
        screen = pygame.display.set_mode((T.SCREEN_W, T.SCREEN_H), pygame.OPENGL | pygame.DOUBLEBUF, vsync=1)
        presenter = Presenter(screen, True, window=True)
    g = Gallery(data)
    if args.only:
        first = args.only.split(",")[0]
        g.filter = first
        g.sel = 0
        g.play()

    if args.sheet:
        keys = args.only.split(",") if args.only else [it[4] for it in g.items]
        rows = [i for i, it in enumerate(g.items) if any(k == it[4] or k in it[0] for k in keys)]
        times = [float(t) for t in args.times.split(",")]
        tw, th = 480, 300
        sheet = pygame.Surface((tw * len(times), th * len(rows)))
        g.filter = ""
        for r, idx in enumerate(rows):
            g.sel = g.shown().index(idx)
            g.play()
            t = 0.0
            for col, at in enumerate(times):
                while t < at:
                    g.update(1 / 60)
                    t += 1 / 60
                presenter.frame(g)
                img = presenter.snapshot().subsurface(VIEW)
                sheet.blit(pygame.transform.smoothscale(img, (tw, th)), (col * tw, r * th))
            T.text(sheet, g.items[idx][0], (8, r * th + 6), 16, (255, 255, 120), shadow=True)
        pygame.image.save(sheet, args.sheet)
        return

    clock = pygame.time.Clock()
    running = True
    while running:
        dt = min(clock.tick(60) / 1000, 0.05)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                running = False
            else:
                g.handle(ev)
        g.update(dt)
        presenter.frame(g)
        pygame.display.flip()


if __name__ == "__main__":
    main()
