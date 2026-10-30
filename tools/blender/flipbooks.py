"""Blender: флипбуки эффектов из настоящей симуляции (Mantaflow) и физики — подход «флипбуки» (vfx_skills.md).

  "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe" -b -P tools/blender/flipbooks.py -- assets/vfx/flipbooks [имя ...]

Каждый эффект — отдельная сцена: симуляция огня/дыма или падение осколков, камера под 45° (как камера боя),
прозрачный фон, Cycles. Кадры складываются в лист <имя>.png (сетка кадров) + <имя>.json (размер кадра, число
кадров, fps, якорь — где в кадре точка эффекта). Игра проигрывает их без пикселизации (ui/fxlab).
"""
import json
import math
import os
import random
import sys

import bpy
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(ARGS[0] if ARGS else "flipbooks")
ONLY = set(ARGS[1:])
SIZE = 192
PITCH = math.radians(45)


def scene(frames, size=SIZE, samples=24):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.frame_start, sc.frame_end = 1, frames
    sc.view_settings.view_transform = "Standard"
    sc.cycles.volume_step_rate = 2.0
    sc.cycles.max_bounces = 4
    return sc


def camera(sc, target=(0, 0, 0.8), dist=7.0, ortho=3.2):
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = ortho
    t = Vector(target)
    cam.location = t + Vector((0, -math.cos(PITCH) * dist, math.sin(PITCH) * dist))
    cam.rotation_euler = (PITCH, 0, 0)
    sc.camera = cam
    return cam


def sun(sc, strength=3.0):
    s = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    s.data.energy = strength
    s.rotation_euler = (math.radians(40), math.radians(-35), 0)
    sc.collection.objects.link(s)
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    nt = w.node_tree                       # узлы ищем по типу: имена локализуются (русский Blender)
    bg = next((n for n in nt.nodes if n.type == "BACKGROUND"), None) or nt.nodes.new("ShaderNodeBackground")
    out = next((n for n in nt.nodes if n.type == "OUTPUT_WORLD"), None) or nt.nodes.new("ShaderNodeOutputWorld")
    bg.inputs[1].default_value = 0.35
    nt.links.new(bg.outputs[0], out.inputs[0])
    sc.world = w


def gas_domain(size, res, z=None, fire=True, vorticity=0.25, dissolve=18, name="dom"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, size[2] / 2 if z is None else z))
    d = bpy.context.active_object
    d.name = name
    d.scale = size
    m = d.modifiers.new("Fluid", "FLUID")
    m.fluid_type = "DOMAIN"
    ds = m.domain_settings
    ds.domain_type = "GAS"
    ds.resolution_max = res
    ds.cache_type = "ALL"
    ds.cache_directory = os.path.join(bpy.app.tempdir, name + "_cache")
    ds.vorticity = vorticity
    ds.use_dissolve_smoke = True
    ds.dissolve_speed = dissolve
    ds.burning_rate = 0.85
    ds.flame_smoke = 0.6
    ds.flame_vorticity = 0.6
    ds.alpha = -0.001
    ds.beta = 0.3 if fire else 0.05
    ds.use_adaptive_domain = False
    return d, m


def flow(obj, kind="BOTH", fuel=1.6, temp=1.5, vel=None, smoke_color=(0.3, 0.3, 0.3), density=1.0):
    m = obj.modifiers.new("Fluid", "FLUID")
    m.fluid_type = "FLOW"
    fs = m.flow_settings
    fs.flow_type = kind
    fs.flow_behavior = "INFLOW"
    fs.flow_source = "MESH"
    fs.surface_distance = 0.4
    fs.fuel_amount = fuel
    fs.temperature = temp
    fs.density = density
    fs.smoke_color = smoke_color
    if vel is not None:
        fs.use_initial_velocity = True
        fs.velocity_normal = vel[0]
        if isinstance(vel[1], (tuple, list)):
            fs.velocity_coord = vel[1]
    obj.hide_render = True
    return m


def bake(domain):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    domain.select_set(True)
    bpy.context.view_layer.objects.active = domain
    with bpy.context.temp_override(active_object=domain, object=domain):
        bpy.ops.fluid.bake_all()


def volume_material(domain, fire_strength=6.0, smoke=(0.25, 0.24, 0.24), density=6.0, blackbody=1.0,
                    smoke_emit=0.0):
    """Объём: плотность — из «density» симуляции, свечение — из «flame» через градиент огня
    (тёмно-красный → оранжевый → жёлто-белый); дым серый (или белый у снега)."""
    mat = bpy.data.materials.new("vol")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    pv.inputs["Color"].default_value = (*smoke, 1)
    pv.inputs["Blackbody Intensity"].default_value = 0.0
    dens = nt.nodes.new("ShaderNodeAttribute")
    dens.attribute_name = "density"
    dm = nt.nodes.new("ShaderNodeMath")
    dm.operation = "MULTIPLY"
    dm.inputs[1].default_value = density
    nt.links.new(dens.outputs["Fac"], dm.inputs[0])
    nt.links.new(dm.outputs[0], pv.inputs["Density"])
    if fire_strength > 0:
        fl = nt.nodes.new("ShaderNodeAttribute")
        fl.attribute_name = "flame"
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        cr = ramp.color_ramp
        cr.elements[0].position, cr.elements[0].color = 0.0, (0.2, 0.01, 0.0, 1)
        cr.elements[1].position, cr.elements[1].color = 1.0, (1.0, 0.92, 0.6, 1)
        e = cr.elements.new(0.3)
        e.color = (0.85, 0.12, 0.01, 1)
        e = cr.elements.new(0.6)
        e.color = (1.0, 0.38, 0.04, 1)
        e = cr.elements.new(0.85)
        e.color = (1.0, 0.62, 0.15, 1)
        nt.links.new(fl.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], pv.inputs["Emission Color"])
        em = nt.nodes.new("ShaderNodeMath")
        em.operation = "MULTIPLY"
        em.inputs[1].default_value = fire_strength
        nt.links.new(fl.outputs["Fac"], em.inputs[0])
        nt.links.new(em.outputs[0], pv.inputs["Emission Strength"])
    else:
        pv.inputs["Emission Color"].default_value = (*smoke, 1)
        pv.inputs["Emission Strength"].default_value = smoke_emit
    nt.links.new(pv.outputs[0], out.inputs["Volume"])
    domain.data.materials.append(mat)


def render_frames(name, frames, fps, anchor, every=1, start=1, mode="alpha"):
    """Рендер кадров в лист (сетка до 8 в ряд). anchor — (x, y) в долях кадра, где точка эффекта.
    mode «fire» — два прохода, как делают флипбуки огня в играх: RGB — только свечение на чёрном (кладётся
    сложением), A — плотность дыма с прозрачным фоном (кладётся обычной прозрачностью, цвет дыма — в игре).
    mode «alpha» — обычный RGBA (лёд, снег, стена)."""
    import numpy as np
    sc = bpy.context.scene
    tmp = os.path.join(bpy.app.tempdir, name)
    os.makedirs(tmp, exist_ok=True)
    lights = [o for o in sc.objects if o.type == "LIGHT"]
    world = sc.world
    out = []

    def shot(path):
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(path)
        w, h = im.size
        a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]
        bpy.data.images.remove(im)
        return a

    for i, f in enumerate(range(start, start + frames * every, every)):
        sc.frame_set(f)
        sc.render.film_transparent = True
        dens = shot(os.path.join(tmp, f"a{i:03d}.png"))
        if mode == "fire":
            sc.render.film_transparent = False
            energy = [lt.data.energy for lt in lights]
            for lt in lights:
                lt.data.energy = 0.0
            if world is not None:
                sc.world = None
            glow = shot(os.path.join(tmp, f"g{i:03d}.png"))
            for lt, e in zip(lights, energy):
                lt.data.energy = e
            sc.world = world
            frame = np.concatenate([glow[..., :3], dens[..., 3:4]], -1)
        else:
            frame = dens
        out.append(frame)
    h, w = out[0].shape[:2]
    cols = min(8, len(out))
    rows = (len(out) + cols - 1) // cols
    sheet = np.zeros((rows * h, cols * w, 4), np.float32)
    for k, fr in enumerate(out):
        sheet[(k // cols) * h:(k // cols + 1) * h, (k % cols) * w:(k % cols + 1) * w] = fr
    img = bpy.data.images.new(name, cols * w, rows * h, alpha=True)
    img.pixels = sheet[::-1].ravel()
    img.filepath_raw = os.path.join(OUT, name + ".png")
    img.file_format = "PNG"
    img.save()
    with open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8") as f:
        json.dump({"frame": [w, h], "cols": cols, "frames": len(out), "fps": fps, "anchor": anchor,
                   "mode": mode}, f)
    print("FLIPBOOK_OK", name, len(out))


def principled(mat):
    nt = mat.node_tree                     # по типу, а не по имени: имена узлов локализуются
    b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if b is None:
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)             or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(b.outputs[0], out.inputs[0])
    return b


def explosion(name="explosion", radius=0.5, frames=24, res=72, big=False, test=False):
    """Взрыв: источник топлива за 6 кадров раздувается от 0.2 до радиуса — огненный шар растёт, горит,
    коптит и поднимается грибом (плавучесть горячего газа)."""
    sc = scene(frames + 8, samples=8 if test else 24)
    dom, m = gas_domain((4, 4, 4), res, z=1.9, vorticity=0.6, dissolve=40 if not big else 48)
    ds = m.domain_settings
    ds.burning_rate = 0.5
    ds.flame_ignition = 1.1
    ds.alpha = 0.8
    ds.beta = 2.5
    bpy.ops.mesh.primitive_ico_sphere_add(radius=1.0, subdivisions=3, location=(0, 0, 0.7))
    src = bpy.context.active_object
    fm = flow(src, fuel=2.5, temp=3.0, vel=(3.0, (0.0, 0.0, 1.5)), density=0.8)
    fm.flow_settings.surface_distance = 0.15
    fm.flow_settings.volume_density = 1.0
    for f, k in ((1, 0.15), (3, 0.55), (5, 0.85), (6, 1.0)):
        src.scale = (radius * k,) * 3
        src.location = (0, 0, 0.7)
        src.keyframe_insert("scale", frame=f)
        src.keyframe_insert("location", frame=f)
    src.location = (0, 0, -10)
    src.keyframe_insert("location", frame=7)
    bake(dom)
    if test:
        for f in (3, 6, 10, 16):
            sc.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            d2 = dom.evaluated_get(dg).modifiers["Fluid"].domain_settings
            print("GRID", f, max(d2.density_grid or [0]), max(d2.flame_grid or [0]), max(d2.heat_grid or [0]),
                  len(d2.density_grid))
    volume_material(dom, fire_strength=2.2, density=9.0, smoke=(0.12, 0.11, 0.11))
    camera(sc, target=(0, 0, 1.1), ortho=2.3 if not big else 2.8)
    sun(sc)
    render_frames(name, 4 if test else frames, 24, [0.5, 0.72], start=4 if test else 2, every=4 if test else 1,
                  mode="fire")


def fire_loop(name="fire_loop", frames=24, res=64):
    """Пламя на земле (горящая клетка): несколько маленьких источников у земли с толчком вверх, жар всплывает
    сильно — языки тянутся вверх и рвутся; берём кадры после разгона."""
    sc = scene(64)
    dom, m = gas_domain((1.2, 1.2, 2.4), res, vorticity=0.45, dissolve=12)
    ds = m.domain_settings
    ds.alpha, ds.beta = 0.6, 3.5
    ds.burning_rate = 0.7
    for i, (x, y) in enumerate(((-0.18, -0.1), (0.15, 0.12), (0.02, -0.2), (-0.05, 0.2))):
        bpy.ops.mesh.primitive_ico_sphere_add(radius=0.1, subdivisions=2, location=(x, y, 0.08))
        fm = flow(bpy.context.active_object, fuel=1.4, temp=2.2, vel=(0.0, (0.0, 0.0, 1.8)), density=0.4)
        fm.flow_settings.surface_distance = 0.08
    bake(dom)
    volume_material(dom, fire_strength=2.6, density=4.0, smoke=(0.12, 0.11, 0.11))
    camera(sc, target=(0, 0, 0.85), ortho=1.9)
    sun(sc)
    render_frames(name, frames, 24, [0.5, 0.86], start=34, mode="fire")


def projectile(name="fire_head", frames=16, res=48):
    """Голова огненного снаряда: источник летит вбок, огонь срывается назад — кадры в системе снаряда."""
    sc = scene(40)
    dom, _ = gas_domain((3.0, 1.2, 1.2), res, z=0.6, vorticity=0.5, dissolve=8)
    dom.location.x = -0.9
    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.18, subdivisions=3, location=(0.35, 0, 0.6))
    src = bpy.context.active_object
    flow(src, fuel=2.0, temp=2.0, vel=(0.0, 0.0))
    src.modifiers["Fluid"].flow_settings.use_initial_velocity = True
    src.modifiers["Fluid"].flow_settings.velocity_coord = (-4.0, 0.0, 0.6)    # поток назад: снаряд летит вправо
    bake(dom)
    volume_material(dom, fire_strength=3.5, density=3.0, smoke=(0.12, 0.11, 0.11))
    camera(sc, target=(-0.6, 0, 0.6), ortho=2.6)
    sun(sc)
    render_frames(name, frames, 24, [0.68, 0.5], start=22, mode="fire")


def snow_cloud(name="snow_cloud", frames=24, res=56):
    """Снежная туча: белый дым клубится и медленно ползёт (без огня)."""
    sc = scene(60)
    dom, _ = gas_domain((3.0, 3.0, 1.6), res, vorticity=0.6, dissolve=40, name="cloud", fire=False)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.7, location=(0, 0, 0.8))
    src = bpy.context.active_object
    src.scale = (1.4, 1.4, 0.4)
    flow(src, kind="SMOKE", temp=0.2, smoke_color=(0.85, 0.9, 1.0), density=0.8, vel=(0.6, 0.0))
    bake(dom)
    volume_material(dom, fire_strength=0.0, smoke=(0.86, 0.92, 1.0), density=4.0, smoke_emit=0.25)
    camera(sc, target=(0, 0, 0.8), ortho=3.6)
    sun(sc, 4.0)
    render_frames(name, frames, 12, [0.5, 0.5], start=30)


def shards(name="ice_burst", frames=20, count=46, big=False):
    """Ледяные осколки: гранёные куски разлетаются по баллистике и скачут по земле (анимация считается тут же)."""
    sc = scene(frames + 2, samples=24)
    rnd = random.Random(7 if not big else 11)
    mat = bpy.data.materials.new("ice")
    mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = (0.55, 0.78, 1.0, 1)
    b.inputs["Roughness"].default_value = 0.08
    b.inputs["Transmission Weight"].default_value = 0.6
    b.inputs["IOR"].default_value = 1.31
    b.inputs["Emission Color"].default_value = (0.5, 0.75, 1.0, 1)
    b.inputs["Emission Strength"].default_value = 0.25
    g = 9.0
    for k in range(count):
        bpy.ops.mesh.primitive_ico_sphere_add(radius=rnd.uniform(0.04, 0.12) * (1.4 if big else 1), subdivisions=1)
        o = bpy.context.active_object
        o.scale = (rnd.uniform(0.5, 1.0), rnd.uniform(0.4, 0.9), rnd.uniform(0.8, 1.8))
        o.data.materials.append(mat)
        a = rnd.uniform(0, math.tau)
        sp = rnd.uniform(1.2, 3.6) * (1.3 if big else 1)
        vz = rnd.uniform(1.5, 4.5)
        x = y = 0.0
        z = 0.4
        vx, vy = math.cos(a) * sp, math.sin(a) * sp
        rot = [rnd.uniform(-8, 8) for _ in range(3)]
        for f in range(1, frames + 2):
            t = 1 / 24
            vz -= g * t
            x, y, z = x + vx * t, y + vy * t, z + vz * t
            if z < 0.05:
                z, vz, vx, vy = 0.05, -vz * 0.3, vx * 0.6, vy * 0.6
            o.location = (x, y, z)
            o.rotation_euler = [r * f * t for r in rot]
            o.keyframe_insert("location", frame=f)
            o.keyframe_insert("rotation_euler", frame=f)
    camera(sc, target=(0, 0, 0.6), ortho=4.5 if big else 3.4)
    sun(sc, 4.0)
    render_frames(name, frames, 24, [0.5, 0.62], start=1)


def ice_wall(name="ice_wall"):
    """Ледяная стена (модель из assets/vfx/ice_wall.json) в настоящем материале льда: просвечивает, преломляет.
    Кадры: длины 1–5 вдоль ряда (ось x) и вглубь поля (ось y)."""
    path = os.path.join(os.path.dirname(OUT), "ice_wall.json")
    with open(path, encoding="utf-8") as f:
        walls = json.load(f)["walls"]
    import bmesh
    for axis in ("x", "y"):
        for length in range(1, 6):
            sc = scene(1, size=96 * length if axis == "x" else 256, samples=48)
            sc.render.resolution_x = 110 * length + 40 if axis == "x" else 260
            sc.render.resolution_y = 230 if axis == "x" else 120 * length + 160
            bm = bmesh.new()
            snow = []
            for t in walls[f"{length}_0"]:
                vs = [bm.verts.new(v) for v in t["v"]]
                f2 = bm.faces.new(vs)
                snow.append(sum(t["c"]) > 2.6)
            me = bpy.data.meshes.new("w")
            bm.to_mesh(me)
            ob = bpy.data.objects.new("w", me)
            sc.collection.objects.link(ob)
            ice = bpy.data.materials.new("ice")
            ice.use_nodes = True
            b = principled(ice)
            b.inputs["Base Color"].default_value = (0.12, 0.42, 0.85, 1)
            b.inputs["Roughness"].default_value = 0.2
            b.inputs["Transmission Weight"].default_value = 0.08
            b.inputs["Subsurface Weight"].default_value = 0.6
            b.inputs["Subsurface Radius"].default_value = (0.15, 0.4, 1.0)
            b.inputs["Emission Color"].default_value = (0.2, 0.5, 1.0, 1)
            b.inputs["Emission Strength"].default_value = 0.12
            sn = bpy.data.materials.new("snow")
            sn.use_nodes = True
            principled(sn).inputs["Base Color"].default_value = (0.92, 0.95, 1.0, 1)
            principled(sn).inputs["Roughness"].default_value = 0.8
            me.materials.append(ice)
            me.materials.append(sn)
            for p, s in zip(me.polygons, snow):
                p.material_index = 1 if s else 0
            if axis == "x":
                ob.location = (-length / 2, 0, 0)
            else:
                ob.rotation_euler = (0, 0, math.radians(90))
                ob.location = (0, -length / 2, 0)
            mpx = 1 / 110                                  # 110 пикселей на клетку в кадре
            cam = camera(sc, target=(0, 0, 0.6), ortho=sc.render.resolution_x * mpx if axis == "x"
                         else sc.render.resolution_y * mpx)
            sun(sc, 3.5)
            sc.render.filepath = os.path.join(OUT, f"{name}_{axis}{length}.png")
            bpy.ops.render.render(write_still=True)
            print("FLIPBOOK_OK", f"{name}_{axis}{length}")
    with open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8") as f:
        json.dump({"px_per_cell": 110, "anchor_z": 0.6}, f)


JOBS = {"explosion": explosion, "test": lambda: explosion("test", res=40, test=True), "explosion_big": lambda: explosion("explosion_big", 0.62, 30, 80, big=True),
        "fire_loop": fire_loop, "fire_head": projectile, "snow_cloud": snow_cloud, "ice_burst": shards,
        "ice_burst_big": lambda: shards("ice_burst_big", 24, 80, big=True), "ice_wall": ice_wall}

os.makedirs(OUT, exist_ok=True)
for key, fn in JOBS.items():
    if ONLY and key not in ONLY:
        continue
    fn()
