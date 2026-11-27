"""Elven casts running on the Expedition particle simulation (cells and height)."""

import math

import numpy as np

from ui import elf_wind, projection
from ui.pixsim import BOUNCE, DIE, Particles

LOOKS = {
    "_d_quick_arrow": "thornshot", "_elf_fate_thread": "thread",
    "_elf_storm_jump": "lightning", "_elf_storm": "thunder", "_elf_dawn": "sunblade",
    "_elf_star_rain": "rain", "_elf_constellation": "stars", "_elf_last_star": "nova",
    "_elf_moon_scythe": "sweep", "e_claw": "claw", "e_star_bolt": "comet",
    "_elf_pollen": "pollen", "e_plague": "spores", "e_sleep": "mist", "e_gravity": "eclipse",
    "frost_guard": "bark", "soul_shield": "moonward", "consecrate": "circle",
    "rejuvenate": "dew", "focus": "firefly", "inspire": "crown", "blessing": "dawn",
    "spirit_tree": "leaves", "spirit_link": "twins", "merge": "forge",
    "blink": "step", "vanish": "mirage", "e_wither": "leafshot",
    "_elf_thorn_attack": "roots", "earth_power": "roots", "e_entangle": "roots",
}

G = 9.0


def _at(feet, height=0.0):
    return (*projection.unproject(*feet), height)


def _direction(a, b):
    delta = np.subtract(b, a)
    return delta / (np.linalg.norm(delta) or 1)


def _particles(view):
    if view.elf_particles is None:
        view.elf_particles = Particles(seed=27)
    return view.elf_particles


def fairy_transition(view, origin, dest, slot, *, arriving):
    """Birth condenses in flight; spent fairies shed warm and cool fragments in a gust."""
    height = .46
    a = (*projection.unproject(*origin, gz=height), height)
    b = (*projection.unproject(*dest, gz=height), height)
    ps = _particles(view)
    wind = 1.25 + .13 * (slot % 3)
    if arriving:
        _flight(view, a, b, .24, "soul", arc=.09, density=1.3)
        ps.spawn(12, a, (_direction(a, b)[0] * 1.5, 0, .55), life=.25,
                 pal="light", smoke=None, temp=1, cool=1.6, size=1.45,
                 spread=.52, jitter=.055, drag=2.2, streak=.025)
        view.vfx.after(.24, lambda: ps.spawn(15, b, (0, 0, .45), life=.26,
                                             pal="soul", smoke=None, temp=1, cool=1.8, size=1.38,
                                             spread=.52, drag=2.8, grav=2, streak=.02))
        return
    ps.spawn(12, a, life=.075, pal="light", smoke=None, temp=1, cool=.7,
             size=1.75, jitter=.052, spread=.45)
    for palette, count, size in (("soul", 27, 1.35), ("light", 13, 1.22), ("petal", 8, 1.12)):
        ps.spawn(count, a, (wind, .28, 1), life=.67, pal=palette, smoke=None,
                 temp=.95, cool=.78, grav=G * .65, drag=2.3, size=size,
                 spread=.95, jitter=.05, streak=.023, land=BOUNCE, bounce=.25)


def _dust(ps, ground, direction, strength):
    """Air knocks loose material off the ground. It expands as it slows."""
    ps.spawn(round(58 * strength), ground, (*direction[:2], .36), life=.65,
             temp=.61, cool=.45, grav=.28, drag=4.4, size=1.6, grow=1.6,
             pal="dust", smoke=None, alpha=.78, spread=.65 + .3 * strength,
             jitter=.12, land=BOUNCE, bounce=.12)


def _strike(view, point, direction, palette, strength=1.0, debris=True, weight=0, *, empowered=False):
    ps = _particles(view)
    if empowered:
        strength *= 1.55
        if weight:
            weight += 1.8
        ps.spawn(round(32 * strength), point, (*direction[:2], 1.6), life=.46,
                 pal="light", smoke=None, temp=.95, cool=1.2, grav=G, drag=2.1,
                 spread=1.4, size=1.37, streak=.035, land=BOUNCE)
    # A short flash, a fast directional spray, and slower pieces that fall and bounce.
    ps.spawn(round(18 * strength), point, life=.075, size=1.9, temp=1, cool=.9,
             pal=palette, smoke=None, jitter=.055 * strength, spread=.44)
    count = round(58 * strength)
    velocity = ps.rng.normal(0, 1.45, (3, count))
    velocity += np.asarray(direction)[:, None] * (1.45 * strength)
    velocity[2] = np.abs(velocity[2]) * .7 + .75
    ps.spawn(count, point, tuple(velocity), life=.55, temp=ps.rng.uniform(.66, 1.0, count),
             cool=.85, grav=G * .82, drag=1.7, size=ps.rng.uniform(.7, 1.6, count),
             pal=palette, smoke=None, jitter=.045, land=BOUNCE, bounce=.31, streak=.026)
    if debris:
        x, y, _ = point
        ground = (x, y, .045)
        cell = view.grid.cells.get((math.floor(x), math.floor(y)))
        if cell is not None and cell.terrain == "water":
            ps.spawn(round(35 * strength), ground, (*direction[:2], 2.25), life=.58,
                     pal="water", smoke=None, temp=.82, cool=.38, grav=G, spread=.85,
                     size=1.3, drag=.7, streak=.021, land=DIE)
        elif cell is None or cell.terrain != "chasm":
            _dust(ps, ground, direction, strength)
    if weight:
        view.vfx.screen_fx(shake=weight, hitstop=.026 if weight < 4 else .041)


def _flight(view, start, end, duration, palette, *, arc=0, core=True, density=1.0):
    """Emit from samples along the path. Released particles keep their own velocity."""
    ps = _particles(view)
    start, end = np.asarray(start), np.asarray(end)
    direction = _direction(start, end)
    steps = max(3, round(duration * 56))

    def emit(fraction):
        point = start + (end - start) * fraction
        point[2] += arc * 4 * fraction * (1 - fraction)
        if core:
            ps.spawn(6, point, life=.055, temp=1, cool=1.1, size=1.55,
                     pal=palette, smoke=None, jitter=.035)
        ps.spawn(max(1, round(5 * density)), point, tuple(direction * 1.25),
                 life=.26, temp=.8, cool=1.45, drag=3.0, grav=1.4, size=1.1,
                 pal=palette, smoke=None, spread=.48, jitter=.027, streak=.018)

    for step in range(steps):
        fraction = step / steps
        view.vfx.after(duration * fraction, lambda f=fraction: emit(f))


def _channel(view, start, end, duration, palette, kind):
    """An irregular discharge or a strip of air with an impulse at its leading edge."""
    ps = _particles(view)
    start, end = np.asarray(start), np.asarray(end)
    direction = _direction(start, end)
    side = np.array((-direction[1], direction[0], .26))
    nodes = np.linspace(start, end, 8)
    if kind == "bolt":
        nodes[1:-1] += ps.rng.uniform(-.18, .18, (6, 1)) * side
    else:
        bend = .27 if kind == "slash" else .13
        nodes += (np.sin(np.linspace(0, math.pi, 8)) * bend)[:, None] * side

    def release(a, b):
        length = np.linalg.norm(b - a)
        count = max(5, round(length * 46))
        coords = np.linspace(a, b, count)
        ps.spawn(count, tuple(coords.T), tuple(side * (.72 if kind == "slash" else .18)),
                 life=.13 if kind == "bolt" else .21, temp=.96, cool=2.2, size=1.32,
                 drag=3.1, grav=.8, pal=palette, smoke=None, jitter=.025, spread=.3,
                 streak=.021)

    for i, (a, b) in enumerate(zip(nodes, nodes[1:])):
        view.vfx.after(duration * i / (len(nodes) - 1), lambda a=a, b=b: release(a, b))


def wind_impact(view, kind, ctx, duration):
    """Add contact physics to the three effects already reviewed in battle."""
    start, ground = _at(ctx["caster_ground"]), _at(ctx["target_ground"])
    direction = _direction(start, ground)
    empowered = ctx.get("empowered", False)
    if empowered:
        _charge(_particles(view), start)
    if kind == "moon":
        point = (*ground[:2], .44)
        _flight(view, (*start[:2], .44), point, duration, "spirit", core=False, density=1.45 if empowered else .65)
        for feet in ctx.get("pierce_points", ()):
            hit = _at(feet, .44)
            phase = math.dist(start[:2], hit[:2]) / max(.01, math.dist(start[:2], ground[:2]))
            view.vfx.after(duration * min(.95, phase), lambda p=hit: _strike(view, p, direction, "spirit", .48,
                                                                             empowered=empowered))
        view.vfx.after(duration, lambda: _strike(view, point, direction, "spirit", .78, weight=2.1,
                                                 empowered=empowered))
    elif kind == "swarm":
        center = np.asarray(start)
        points = sorted((_at(p, .045) for p in ctx["cells"]),
                        key=lambda p: np.linalg.norm(np.subtract(p, center)))
        for point in points:
            drift = _direction(center, point)
            distance = np.linalg.norm(np.subtract(point, center))
            delay = duration * min(1, .4 + .23 * distance)
            view.vfx.after(delay, lambda p=point, d=drift: _dust(_particles(view), p, d * 1.8,
                                                               .72 if empowered else .43))
            if empowered and distance > .5:
                view.vfx.after(delay, lambda p=point, d=drift: _strike(view, p, d, "soul", .34, debris=False))
        view.vfx.after(duration, lambda: _strike(view, (*start[:2], .12), direction, "soul",
                                                  .82, debris=False, weight=3, empowered=empowered))
    else:
        view.vfx.after(duration, lambda: _strike(view, (*ground[:2], .22), direction, "nature", .94, weight=2.5,
                                                 empowered=empowered))


def play(view, kind, ctx):
    world = view.vfx
    ps = _particles(view)
    start, ground = _at(ctx["caster_ground"]), _at(ctx["target_ground"])
    a, b = (*start[:2], .45), (*ground[:2], .45 if ctx["target_unit"] else .18)
    direction = _direction(a, b)
    cells = sorted((_at(point, .05) for point in ctx["cells"]),
                   key=lambda p: math.dist(p[:2], ground[:2]))
    depth = max(.82, min(1.25, ctx["scale"]))
    empowered = ctx.get("empowered", False)
    if empowered:
        _charge(ps, start)

    def strike(point, direction, palette, strength, **opts):
        _strike(view, point, direction, palette, strength, empowered=empowered, **opts)

    if kind == "roots":
        for screen_pt in ctx["cells"] if ctx.get("radius") else [ctx["target_ground"]]:
            world.cues.append(elf_wind.Wind("root", world.time, .64, ctx["caster_ground"], screen_pt, depth, ()))
            pt = _at(screen_pt, .2)
            world.after(.41, lambda p=pt: strike(p, _direction(start, p), "nature",
                                                .45 if ctx.get("radius") else 1.05,
                                                weight=2 if empowered and not ctx.get("radius") else 0))
        return .41
    if kind == "venom":
        _strike(view, (*ground[:2], .08), direction, "poison", .56, debris=False)
        return 0
    if kind in ("thornshot", "comet", "leafshot"):
        duration = max(.16, min(.49, math.dist(a, b) / 12))
        palette = {"thornshot": "steel", "comet": "light", "leafshot": "nature"}[kind]
        if kind == "thornshot":
            origin, target = ctx["caster"], ctx["target"]
            prop = "arrow_ice"
            world.prop(prop, *origin, scale=24 * depth / view.props[prop].get_width(),
                       path=(origin, target, duration, 0), orient=True, life=duration, opaque=True)
        _flight(view, a, b, duration, palette, arc=.13 if kind != "thornshot" else 0, core=kind != "thornshot",
                density=1.75 if empowered else 1.0)
        world.after(duration, lambda: strike(b, direction, palette, .77, weight=1.55))
        return duration
    if kind in ("lightning", "thunder", "sunblade", "thread", "claw"):
        palette = {"thread": "shadow", "sunblade": "light", "claw": "steel"}.get(kind, "storm")
        shape = "thread" if kind == "thread" else "bolt"
        if kind == "thunder":
            a = (b[0] - .15, b[1], 2.3)
        elif kind in ("claw", "sunblade"):
            shape = "slash"
            for i in range(2 if kind == "claw" else 1):
                _channel(view, (b[0] - .45 + .18 * i, b[1], .96), (b[0] + .25 + .18 * i, b[1], .19),
                         .12, palette, shape)
        if shape != "slash":
            _channel(view, a, b, .12, palette, shape)
        weight = 3.8 if kind in ("thunder", "sunblade") else 1.7
        world.after(.12, lambda: strike(b, _direction(a, b), palette, 1.15, weight=weight))
        return .12
    if kind in ("rain", "stars", "nova", "sweep", "balance"):
        duration = .23
        palette = "light" if kind == "nova" else "spirit"
        if kind == "nova":
            _flight(view, (ground[0] - .3, ground[1], 2.7), ground, duration, palette, density=2)
        elif kind in ("sweep", "balance"):
            left = min(pt[0] for pt in cells) - .3
            right = max(pt[0] for pt in cells) + .3
            if kind == "sweep":
                _channel(view, (left, ground[1], .55), (right, ground[1], .35), duration, palette, "slash")
            else:
                _channel(view, (left, ground[1], .6), (*ground[:2], .28), duration, "light", "slash")
                _channel(view, (right, ground[1], .6), (*ground[:2], .28), duration, "shadow", "slash")
        cell_ids = {(math.floor(pt[0]), math.floor(pt[1])) for pt in cells}
        for unit in view.combat.units:
            if unit.team != ctx["caster_unit"].team and unit.alive and not unit.obj and unit.cell in cell_ids:
                point = (*view.ground_pos(unit), .42)
                world.after(duration, lambda p=point: strike(p, _direction(start, p), palette, .71, debris=False))
        for i, pt in enumerate(cells):
            if kind == "rain":
                fall = duration - ((i * 7) % 11) * .006
                sky = (pt[0] - .46, pt[1], 1.8 + (i % 3) * .27)
                _flight(view, sky, pt, fall, palette, density=1.1 if empowered else .52)
                world.after(fall, lambda p=pt: _dust(ps, p, (.75, .10), .25))
            elif kind == "stars":
                high = (*pt[:2], .85)
                ps.spawn(8, high, life=.29, temp=.98, cool=.6, size=1.18, pal=palette, smoke=None,
                         spread=.18, jitter=.045)
                if i:
                    _channel(view, (*cells[i - 1][:2], .85), high, .16, palette, "thread")
            drift = _direction(ground, pt)
            # Center deals the immediate blow; dust and fragments continue outwards.
            force = (1.32 if kind == "nova" else .70) if i == 0 else .34
            delay = duration if not i else duration + min(.14, math.dist(ground[:2], pt[:2]) * .035)
            if kind in ("sweep", "balance") and i:
                world.after(delay, lambda p=pt, d=drift: _dust(ps, p, d, .32))
                continue
            world.after(delay, lambda p=pt, d=drift, s=force, first=i == 0:
                        strike(p, d, palette, s, weight=(4.2 if kind == "nova" else 2.8) if first else 0))
        return duration
    if kind in ("pollen", "mist", "spores", "eclipse", "circle"):
        palette = {"pollen": "light", "spores": "nature", "mist": "fog", "eclipse": "shadow", "circle": "soul"}[kind]
        haze = kind in ("mist", "spores", "pollen")
        for i, pt in enumerate(cells):
            drift = _direction(ground, pt)
            count = (16 if len(cells) > 1 else 46) * (2 if empowered else 1)
            delay = (i % 4) * .02
            if haze and i % 3 == 0:
                x, y, z = pt
                origin = projection.project(x - .30, y, z)[:2]
                target = projection.project(x + .30, y + .15, z)[:2]
                world.cues.append(elf_wind.Wind("ground_drift", world.time + delay, .67, origin, target, depth, ()))
            world.after(delay, lambda p=pt, d=drift: ps.spawn(
                count, p, (.38 + d[0] * .4, d[1] * .55, .32),
                life=.76, temp=.54 if haze else .79, cool=.52, drag=2.7, grav=.4, size=1.08, grow=.65,
                pal=palette, smoke=None, jitter=.21, spread=.36, land=BOUNCE, bounce=.16))
        return .16

    _support(ps, kind, start, ground, b, empowered=empowered)
    return .14


def _charge(ps, origin):
    x, y, _ = origin
    angle = ps.rng.uniform(0, math.tau, 58)
    dx, dy = np.cos(angle), np.sin(angle)
    ps.spawn(58, (x + dx * .48, y + dy * .48, .06), (-dx * 1.9, -dy * 1.9, 1.7),
             life=.29, temp=.97, cool=1.45, grav=2, drag=1.5, size=1.25,
             pal="light", smoke=None, jitter=.06, streak=.028)


def _support(ps, kind, start, ground, target, *, empowered=False):
    palette = {
        "bark": "nature", "moonward": "steel", "forge": "brass", "firefly": "light",
        "dawn": "light", "twins": "storm", "mirage": "shadow", "plant": "nature",
        "leaves": "nature", "well": "spirit", "compass": "nature", "bridge": "spirit",
        "dew": "water", "step": "dust",
    }.get(kind, "soul")
    count = 32 if kind in ("firefly", "twins") else 56
    if empowered:
        count = count * 7 // 4
        x, y, _ = ground
        ps.spawn(24, (x, y, .45), (0, 0, 1.5), life=.45, pal="light", smoke=None,
                 temp=.98, cool=1.0, grav=4.1, drag=1.9, spread=.8, size=1.3, streak=.021)
    angle = ps.rng.uniform(0, math.tau, count)
    dx, dy = np.cos(angle), np.sin(angle)
    radius = ps.rng.uniform(.09, .31, count)
    x, y, _ = ground
    if kind in ("bark", "moonward", "bridge"):
        # Rising shell: narrow at the bottom and spread out at shoulder height.
        ps.spawn(count, (x + dx * radius, y + dy * radius, .065),
                 (dx * .54, dy * .54, ps.rng.uniform(1.55, 2.35, count)),
                 life=.46, grav=4.0, drag=1.65, temp=.91, cool=1.05, size=1.27,
                 pal=palette, smoke=None, land=BOUNCE, streak=.02)
    elif kind == "dew":
        ps.spawn(count, (x + dx * radius, y + dy * radius, ps.rng.uniform(.52, .95, count)),
                 (-dx * .17, -dy * .17, -.18), life=.44, grav=G * .64, drag=1.6, temp=.93,
                 cool=.7, size=1.3, pal=palette, smoke=None, land=BOUNCE, bounce=.3, streak=.022)
    elif kind in ("step", "summon", "plant", "mirage", "leaves"):
        drift = _direction(start, ground)
        _dust(ps, (*ground[:2], .04), drift, .64)
        ps.spawn(count // 2, (*ground[:2], .05), (dx[:count//2], dy[:count//2], 1.3),
                 life=.51, temp=.91, cool=1.12, size=1.28, grav=5.5, drag=2.2,
                 pal=palette, smoke=None, jitter=.11, land=BOUNCE)
    else:
        # Wind carries small motes towards the hero instead of painting a solid halo.
        ps.spawn(count, (x + dx * radius * 2, y + dy * radius * 2, .14),
                 (-dx * .86, -dy * .86, .85 + target[2]), life=.48, temp=.96,
                 cool=1.36, size=1.2, drag=1.9, grav=.8, pal=palette, smoke=None,
                 jitter=.08, spread=.23, streak=.024)
