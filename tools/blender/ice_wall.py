"""Blender: ледяная стена-ледник (vfx_skills.md, «Ледяная стена»). Запуск:

  "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe" -b -P tools/blender/ice_wall.py -- assets/vfx/ice_wall.json [preview.png]

Строит процедурные модели стены длиной 1–5 клеток (по 3 варианта): гранёные колонны разной высоты с разломами между
ними, зубчатый верх, снег на верхних гранях и вал снега у подножия. Запекает затенение в углублениях (AO, Cycles) и
физически раскалывает кусок стены в одну клетку (rigid body): глыбы падают и раскатываются по земле.
Выход — JSON с треугольниками (координаты в клетках: x вдоль стены 0..L, y поперёк, z вверх), цветом и AO граней,
и траекториями глыб раскола. Игра рисует это сама в пикселях нашей камерой (ui/pixmesh.py).
"""
import json
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else "ice_wall.json"
PREVIEW = ARGS[1] if len(ARGS) > 1 else None

H = 1.4            # высота, клеток
T = 0.6            # толщина
SNOW = (0.93, 0.96, 1.0)
VARIANTS = 3
BREAK_FPS = 24
BREAK_FRAMES = 30


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 16
    sc.cycles.device = "CPU"
    return sc


def column(bm, rng, x0, x1, h, inset_f, inset_b, tone, colors, mound=True):
    """Колонна: стопка колец (прямоугольников) с дрожанием граней + зубчатый верх с вершиной-пиком."""
    levels = sorted([0.0] + [h * rng.uniform(0.12, 0.88) for _ in range(rng.randint(2, 4))] + [h])
    rings = []
    for i, z in enumerate(levels):
        j = 0.0 if i == 0 else 0.045                 # фасад колонны выпирает и западает гранями
        top = i == len(levels) - 1
        ring = [
            (x0 + rng.uniform(0, j * 0.5), -T / 2 + inset_f + rng.uniform(-j, j), z + (rng.uniform(-0.03, 0.03) if top else 0)),
            (x1 - rng.uniform(0, j * 0.5), -T / 2 + inset_f + rng.uniform(-j, j), z + (rng.uniform(-0.03, 0.03) if top else 0)),
            (x1 - rng.uniform(0, j * 0.5), T / 2 - inset_b + rng.uniform(-j, j), z + (rng.uniform(-0.06, 0.0) if top else 0)),
            (x0 + rng.uniform(0, j * 0.5), T / 2 - inset_b + rng.uniform(-j, j), z + (rng.uniform(-0.06, 0.0) if top else 0)),
        ]
        rings.append([bm.verts.new(v) for v in ring])
    faces = []
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(4):
            faces.append(bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k])))
    faces.append(bm.faces.new(rings[-1]))
    for f in faces:
        colors[f] = tone
    if rng.random() < 0.4:                       # не на каждой колонне снег — верх местами голый лёд
        return faces
    # снежная шапка: плита чуть шире колонны, нависает спереди, верх бугристый
    top = rings[-1]
    zt = max(v.co.z for v in top)
    th = rng.uniform(0.05, 0.1)
    over = rng.uniform(0.02, 0.06)
    lo = [(x0 - 0.01, -T / 2 + inset_f - over, zt - th * 0.6), (x1 + 0.01, -T / 2 + inset_f - over, zt - th * 0.6),
          (x1 + 0.01, T / 2 - inset_b + 0.01, zt - th * 0.4), (x0 - 0.01, T / 2 - inset_b + 0.01, zt - th * 0.4)]
    hi = [(x + rng.uniform(-0.01, 0.01), y + (0.015 if k < 2 else -0.01), zt + th * rng.uniform(0.5, 1.0))
          for k, (x, y, _) in enumerate(lo)]
    lv = [bm.verts.new(v) for v in lo]
    hv = [bm.verts.new(v) for v in hi]
    mid = bm.verts.new(((x0 + x1) / 2, (lo[0][1] + lo[2][1]) / 2, zt + th * rng.uniform(1.0, 1.5)))
    for k in range(4):
        colors[bm.faces.new((lv[k], lv[(k + 1) % 4], hv[(k + 1) % 4], hv[k]))] = -1.0
        colors[bm.faces.new((hv[k], hv[(k + 1) % 4], mid))] = -1.0
    return faces


def wall_mesh(length, seed):
    """Стена длиной length клеток вдоль x (0..length), центр толщины y=0."""
    rng = random.Random(seed)
    bm = bmesh.new()
    colors = {}
    x = 0.0
    while x < length - 0.05:
        w = min(rng.uniform(0.24, 0.5), length - x)
        if length - x - w < 0.16:
            w = length - x
        end = min(x + w / 2, length - x - w / 2)                 # концы стены осыпаются: ниже и уже
        taper = min(1.0, 0.62 + end * 1.6)
        h = H * rng.uniform(0.62, 1.0) * taper            # перепад высот: между колоннами видны ледяные грани
        if rng.random() < 0.15:
            h *= rng.uniform(0.78, 0.9)                          # откололась верхушка
        tone = rng.uniform(0.0, 1.0)
        column(bm, rng, x + 0.012, x + w - 0.012, h, rng.uniform(0.0, 0.12) + (1 - taper) * 0.1,
               rng.uniform(0.0, 0.05), tone, colors)
        x += w
    # снежный вал у подножия спереди: кочки
    x = 0.0
    while x < length:
        w = rng.uniform(0.2, 0.4)
        x1 = min(length, x + w)
        y0 = -T / 2 - rng.uniform(0.04, 0.12)
        zt = rng.uniform(0.08, 0.2)
        vs = [bm.verts.new(v) for v in ((x, y0, 0), (x1, y0, 0), (x1, -T / 2 + 0.05, 0), (x, -T / 2 + 0.05, 0))]
        top = bm.verts.new(((x + x1) / 2, -T / 2 - 0.01, zt))
        for k in range(4):
            colors[bm.faces.new((vs[k], vs[(k + 1) % 4], top))] = -1.0
        x = x1
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    return bm, colors


def face_color(f, tone):
    """Снег — на гранях, смотрящих вверх, и на вале; лёд — голубой с разбросом по колоннам."""
    nz = f.normal.z
    if tone < 0 or nz > 0.97:
        return SNOW
    return (0.14 + 0.2 * tone, 0.34 + 0.26 * tone, 0.66 + 0.2 * tone)


def make_object(name, bm, colors_by_face=None):
    me = bpy.data.meshes.new(name)
    tones = {}
    if colors_by_face is not None:
        bm.faces.ensure_lookup_table()
        for f in bm.faces:
            tones[f.index] = next((t for ff, t in colors_by_face.items() if ff.is_valid and ff.index == f.index), 0.5)
    bm.to_mesh(me)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def bake_ao(ob):
    """AO в атрибут цвета углов граней (Cycles bake)."""
    me = ob.data
    attr = me.color_attributes.new("ao", "FLOAT_COLOR", "CORNER")
    me.color_attributes.active_color = attr
    mat = bpy.data.materials.new("ice")
    mat.use_nodes = True
    me.materials.append(mat)
    for o in bpy.context.scene.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.context.scene.cycles.samples = 32
    bpy.ops.object.bake(type="AO", target="VERTEX_COLORS")
    return attr


def ground():
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    g = bpy.context.active_object
    g.name = "ground"
    return g


def export_wall(length, seed):
    """Модель стены: треугольники, цвет грани, AO по углам."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    g = ground()
    bm, colors = wall_mesh(length, seed)
    bm.faces.ensure_lookup_table()
    tone_of = {f.index: colors.get(f, 0.5) for f in bm.faces}
    cols = {f.index: face_color(f, tone_of[f.index]) for f in bm.faces}
    ob = make_object(f"wall{length}_{seed}", bm)
    bm.free()
    attr = bake_ao(ob)
    tris = []
    me = ob.data
    for poly in me.polygons:
        vs = [list(me.vertices[me.loops[li].vertex_index].co) for li in poly.loop_indices]
        ao = [attr.data[li].color[0] for li in poly.loop_indices]
        tris.append({"v": [[round(c, 4) for c in v] for v in vs], "c": [round(c, 3) for c in cols[poly.index]],
                     "ao": [round(a, 3) for a in ao]})
    bpy.data.objects.remove(g)
    return ob, tris


def fracture(seed):
    """Кусок стены в одну клетку раскалывается: колонны ломаются на 2–3 глыбы, глыбы получают толчок наружу-вверх
    и падают (rigid body). Возвращает глыбы (треугольники в своей системе) и их матрицы по кадрам."""
    sc = bpy.context.scene
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    rng = random.Random(seed)
    if sc.rigidbody_world is not None:           # прошлый раскол: мир и его запечённый кэш — заново
        bpy.ops.ptcache.free_bake_all()
        bpy.ops.rigidbody.world_remove()
    bpy.ops.rigidbody.world_add()
    sc.rigidbody_world.point_cache.frame_end = BREAK_FRAMES + 2
    sc.frame_start, sc.frame_end = 1, BREAK_FRAMES + 2
    sc.render.fps = BREAK_FPS
    g = ground()
    bpy.context.view_layer.objects.active = g
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    g.rigid_body.friction = 0.9
    chunks = []
    x = 0.0
    while x < 0.999:
        w = min(rng.uniform(0.24, 0.45), 1.0 - x)
        h = H * rng.uniform(0.82, 1.0)
        cuts = sorted([0.0] + [h * rng.uniform(0.3, 0.75) for _ in range(rng.randint(1, 2))] + [h])
        tone = rng.random()
        for z0, z1 in zip(cuts[:-1], cuts[1:]):
            bm = bmesh.new()
            colors = {}
            column(bm, rng, -w / 2 + 0.01, w / 2 - 0.01, z1 - z0, rng.uniform(0, 0.05), rng.uniform(0, 0.04), tone,
                   colors)
            bmesh.ops.triangulate(bm, faces=list(bm.faces))
            bm.faces.ensure_lookup_table()
            for v in bm.verts:
                v.co.z -= (z1 - z0) / 2
            cols = [face_color(f, tone) for f in bm.faces]
            ob = make_object(f"chunk{len(chunks)}", bm)
            bm.free()
            ob.location = (x + w / 2, 0, z0 + (z1 - z0) / 2)
            bpy.context.view_layer.objects.active = ob
            for o in sc.objects:
                o.select_set(o is ob)
            bpy.ops.rigidbody.object_add(type="ACTIVE")
            ob.rigid_body.collision_shape = "CONVEX_HULL"
            ob.rigid_body.mass = (z1 - z0) * w
            ob.rigid_body.friction = 0.7
            ob.rigid_body.restitution = 0.15
            # толчок: два первых кадра глыба ведётся анимацией (наружу и вверх), потом летит сама
            push = Vector((rng.uniform(-0.6, 0.6), -rng.uniform(0.5, 1.3), rng.uniform(0.2, 1.0) * (z0 / H + 0.3)))
            ob.rigid_body.kinematic = True
            ob.keyframe_insert("location", frame=1)
            ob.keyframe_insert("rotation_euler", frame=1)
            ob.keyframe_insert("rigid_body.kinematic", frame=1)
            ob.location = Vector(ob.location) + push * (2 / BREAK_FPS)
            ob.rotation_euler = (rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1))
            ob.keyframe_insert("location", frame=3)
            ob.keyframe_insert("rotation_euler", frame=3)
            ob.keyframe_insert("rigid_body.kinematic", frame=3)
            ob.rigid_body.kinematic = False
            ob.keyframe_insert("rigid_body.kinematic", frame=4)
            chunks.append((ob, cols))
        x += w
    bpy.ops.ptcache.bake_all(bake=True)
    out = []
    for ob, cols in chunks:
        me = ob.data
        tris = [{"v": [[round(c, 4) for c in me.vertices[me.loops[li].vertex_index].co] for li in p.loop_indices],
                 "c": [round(c, 3) for c in cols[p.index]]} for p in me.polygons]
        out.append({"tris": tris, "frames": []})
    for f in range(3, 3 + BREAK_FRAMES):
        sc.frame_set(f)
        for (ob, _), rec in zip(chunks, out):
            m = ob.matrix_world
            rec["frames"].append([round(m[i][j], 4) for i in range(3) for j in range(4)])
    return out


def preview(path, tris_list):
    """Контрольный рендер стен (Cycles) — для глаза, игра его не использует."""
    sc = bpy.context.scene
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    for i, (length, tris) in enumerate(tris_list):
        bm = bmesh.new()
        for t in tris:
            bm.faces.new([bm.verts.new(v) for v in t["v"]])
        me = bpy.data.meshes.new("p")
        bm.to_mesh(me)
        ob = bpy.data.objects.new("p", me)
        sc.collection.objects.link(ob)
        ob.location = (-3, i * 1.6, 0)
        mat = bpy.data.materials.new("m")
        mat.use_nodes = True
        next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.55, 0.75, 0.95, 1)
        me.materials.append(mat)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.location = (0, -6, 9)
    cam.rotation_euler = (math.radians(45), 0, 0)
    sc.camera = cam
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(40), math.radians(-30), 0)
    sc.render.resolution_x, sc.render.resolution_y = 640, 480
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    reset()
    walls = {}
    for length in range(1, 6):
        for v in range(VARIANTS):
            _, tris = export_wall(length, 100 * length + v)
            walls[f"{length}_{v}"] = tris
    breaks = [fracture(900 + v) for v in range(2)]
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"height": H, "thick": T, "fps": BREAK_FPS, "walls": walls, "breaks": breaks}, f)
    print("ICE_WALL_OK", OUT, sum(len(t) for t in walls.values()), "tris")


main()
