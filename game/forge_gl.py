"""3D-сцена ковки (sim/forge_bar.py): изометрия сверху-спереди — взгляд кузнеца на наковальню. OpenGL
(moderngl) в закадровый буфер с глубиной → картинка pygame. Наковальня с рогом, молот, клещи — сетки из
примитивов; металл — поверхность решётки детали с освещением и цветом каления; цель — полупрозрачный призрак.
Нет видеокарты — простой запасной рисунок треугольниками (по глубине). Мировые оси: x — вдоль наковальни,
y — от кузнеца, z — вверх; лицо наковальни — плоскость z = 0."""
import math

import numpy as np
import pygame

from sim import forge_bar as FB

HORN = {"x0": -260.0, "x1": -130.0, "r0": 9.0, "r1": 42.0}   # рог наковальни вдоль −x

VS = """
#version 330
uniform mat4 mvp;
in vec3 in_pos;
in vec3 in_nrm;
in vec3 in_col;
out vec3 v_nrm;
out vec3 v_col;
void main() {
    gl_Position = mvp * vec4(in_pos, 1.0);
    v_nrm = in_nrm;
    v_col = in_col;
}
"""
FS = """
#version 330
uniform vec3 light;
uniform vec3 view;
uniform float alpha;
uniform float glow;
uniform int mode;                                // 0 — сплошное, 1 — призрак, 2 — полупрозрачное сплошное
in vec3 v_nrm;
in vec3 v_col;
out vec4 f;
void main() {
    vec3 n = normalize(v_nrm);
    float lam = max(dot(n, light), 0.0);
    vec3 h = normalize(light + view);
    float spec = pow(max(dot(n, h), 0.0), 40.0);
    float rim = pow(1.0 - max(dot(n, view), 0.0), 3.0);
    vec3 c = v_col * (0.28 + 0.78 * lam) + vec3(1.0, 0.95, 0.85) * spec * 0.35 * (1.0 - glow) + v_col * glow * 0.55;
    if (mode == 2) { f = vec4(c, alpha); return; }
    if (alpha < 0.99) {                          // призрак: стекло, края ярче
        f = vec4(v_col * (0.5 + 0.5 * lam) + v_col * rim, alpha * (0.35 + 0.65 * rim));
        return;
    }
    f = vec4(c, 1.0);
}
"""


def look(eye, target, up=(0, 0, 1)):
    f = np.asarray(target, float) - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    m = np.eye(4)
    m[0, :3], m[1, :3], m[2, :3] = r, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m


def ortho(half_w, half_h, near=-2000.0, far=2000.0):
    m = np.eye(4)
    m[0, 0], m[1, 1] = 1 / half_w, 1 / half_h
    m[2, 2] = -2 / (far - near)
    m[2, 3] = -(far + near) / (far - near)
    return m


# ---------- сетки примитивов ----------

def box(c, half, col):
    c, half = np.asarray(c, float), np.asarray(half, float)
    V, N, T = [], [], []
    for ax in range(3):
        for s in (-1, 1):
            a, b = [k for k in range(3) if k != ax]
            n = np.zeros(3)
            n[ax] = s
            base = len(V)
            for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = np.zeros(3)
                p[ax], p[a], p[b] = s * half[ax], u * half[a], v * half[b]
                V.append(c + p)
                N.append(n)
            T += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    return np.array(V), np.array(N), np.array(T), np.tile(col, (len(V), 1))


def cone_x(x0, x1, r0, r1, zc0, zc1, col, seg=28):
    """Конус вдоль x (рог): от (x0, r0) к (x1, r1), центр по z — от zc0 к zc1."""
    V, N, T = [], [], []
    for i, (x, r, zc) in enumerate(((x0, r0, zc0), (x1, r1, zc1))):
        for k in range(seg):
            a = 2 * math.pi * k / seg
            V.append((x, r * math.cos(a), zc + r * math.sin(a)))
            N.append((-(r1 - r0) / max(1e-6, x1 - x0) * 0.0, math.cos(a), math.sin(a)))
    for k in range(seg):
        k2 = (k + 1) % seg
        T += [(k, seg + k, seg + k2), (k, seg + k2, k2)]
    V.append((x0, 0, zc0))
    N.append((-1, 0, 0))
    for k in range(seg):
        T.append((len(V) - 1, (k + 1) % seg, k))
    return np.array(V, float), np.array(N, float), np.array(T), np.tile(col, (len(V), 1))


def cylinder(p0, p1, r, col, seg=14):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    d /= np.linalg.norm(d)
    a = np.cross(d, (0, 0, 1) if abs(d[2]) < 0.9 else (1, 0, 0))
    a /= np.linalg.norm(a)
    b = np.cross(d, a)
    V, N, T = [], [], []
    for p in (p0, p1):
        for k in range(seg):
            t = 2 * math.pi * k / seg
            n = a * math.cos(t) + b * math.sin(t)
            V.append(p + n * r)
            N.append(n)
    for k in range(seg):
        k2 = (k + 1) % seg
        T += [(k, seg + k, seg + k2), (k, seg + k2, k2)]
    return np.array(V), np.array(N), np.array(T), np.tile(col, (len(V), 1))


def merge(*parts):
    V, N, T, C, off = [], [], [], [], 0
    for v, n, t, c in parts:
        V.append(v)
        N.append(n)
        T.append(t + off)
        C.append(c)
        off += len(v)
    return np.concatenate(V), np.concatenate(N), np.concatenate(T), np.concatenate(C)


def anvil_mesh():
    """Наковальня: лицо (z = 0), подбородок, талия, основание, пень; рог вдоль −x (вершина рога — на z = 0)."""
    steel, dark, wood = (0.33, 0.34, 0.37), (0.22, 0.22, 0.24), (0.36, 0.24, 0.14)
    h = HORN
    return merge(
        box((0, 0, -22), (130, 46, 22), steel),
        box((0, 0, -70), (70, 34, 28), dark),
        box((0, 0, -112), (110, 56, 16), dark),
        cylinder((0, 0, -128), (0, 0, -420), 120, wood, 24),
        cone_x(h["x0"], h["x1"], h["r0"], h["r1"], -h["r0"], -h["r1"], steel),
    )


def hammer_mesh(head_c, kind):
    """Молот: головка (боёк вниз) и рукоять к кузнецу (−y, вверх)."""
    hx, hy = min(FB.HAMMERS.get(kind, (0, 12.0))[1], 26), 24.0          # боёк — на всю ширину бруска
    head = box(head_c, (hx, hy, 34 if kind != "flatter" else 20), (0.30, 0.30, 0.33))
    hc = np.asarray(head_c, float)
    handle = cylinder(hc + (hx, 0, 6), hc + (hx + 190, -40, 70), 6, (0.45, 0.30, 0.16))   # к правой руке
    return merge(head, handle)


def ram_mesh(head_c, die):
    """Автомолот: боёк (плоский, клин или полукруглая обжимка), баба над ним и станина за наковальней."""
    hc = np.asarray(head_c, float)
    steel, dark, iron = (0.36, 0.37, 0.40), (0.24, 0.24, 0.27), (0.20, 0.19, 0.19)
    if die == "die_fuller":
        face = cylinder(hc + (-30, 0, -6), hc + (30, 0, -6), 6, steel, 12)
        face = merge(box(hc + (0, 0, 6), (8, 30, 8), steel), cylinder(hc + (0, -30, -2), hc + (0, 30, -2), 6, steel))
    elif die == "swage":
        face = merge(box(hc + (0, 0, 8), (16, 34, 8), steel), cylinder(hc + (0, -34, 0), hc + (0, 34, 0), 9, steel))
    else:
        face = box(hc + (0, 0, 2), (14, 34, 10), steel)
    ram = box(hc + (0, 0, 70), (28, 40, 58), dark)
    column = box((0, 120, 160), (40, 30, 300), iron)
    beam = box((0, 60, 400), (40, 90, 20), iron)
    rod = cylinder(hc + (0, 0, 128), (0, 0, 400), 9, steel)
    return merge(face, ram, column, beam, rod)


def tongs_mesh(grip_w, d):
    """Клещи: две губки у зажатого конца и рукояти к кузнецу. grip_w — точка хвата, d — куда торчит конец."""
    g = np.asarray(grip_w, float)
    d = np.asarray(d, float) / max(1e-6, np.linalg.norm(d))
    out = []
    for s in (-1, 1):
        a = g + np.array([0, 0, s * 6.0])
        b = g - d * 150 + np.array([0, -70, 30 + s * 8])
        out.append(cylinder(a, b, 4.0, (0.32, 0.30, 0.29), 8))
    return merge(*out)


# ---------- сцена ----------

class Scene:
    """Камера кузнеца и рисование кадра: render(size, piece, ...) → pygame.Surface."""

    def __init__(self):
        self.ctx = None
        self.failed = False
        self.yaw = math.radians(-18)                 # чуть сбоку
        self.pitch = math.radians(48)                # сверху
        self.zoom = 1.0
        self.center = np.array([0.0, 0.0, 20.0])
        self.anvil = anvil_mesh()
        self.fbo_size = None

    # ----- камера -----

    def view_dir(self):
        """Направление ВЗГЛЯДА (от глаза к сцене)."""
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        return np.array([math.sin(self.yaw) * cp, math.cos(self.yaw) * cp, -sp])

    def matrices(self, size, extent=200.0):
        w, h = size
        half_h = extent / self.zoom * 0.6
        half_w = half_h * w / h
        eye = self.center - self.view_dir() * 800
        V = look(eye, self.center)
        P = ortho(half_w, half_h)
        return P @ V, V, (half_w, half_h)

    def to_screen(self, pts, size, extent):
        mvp, _, _ = self.matrices(size, extent)
        h = np.c_[pts, np.ones(len(pts))] @ mvp.T
        w, hgt = size
        return np.stack([(h[:, 0] * 0.5 + 0.5) * w, (0.5 - h[:, 1] * 0.5) * hgt, h[:, 2]], -1)

    def ray(self, sx, sy, size, extent):
        """Луч из точки экрана: (начало, направление) в мире."""
        mvp, V, (hw, hh) = self.matrices(size, extent)
        w, h = size
        nx, ny = (sx / w) * 2 - 1, 1 - (sy / h) * 2
        r, u, f = V[0, :3], V[1, :3], -V[2, :3]
        eye = self.center - self.view_dir() * 800
        return eye + r * nx * hw + u * ny * hh, f

    def pick(self, piece, sx, sy, size, extent):
        """Точка поверхности детали под курсором (мир) или None — луч против треугольников."""
        V, T, _, _ = piece.surface()
        o, d = self.ray(sx, sy, size, extent)
        a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
        e1, e2 = b - a, c - a
        p = np.cross(d, e2)
        det = (e1 * p).sum(1)
        ok = np.abs(det) > 1e-9
        inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
        s = o - a
        u = (s * p).sum(1) * inv
        q = np.cross(s, e1)
        v = (q * d).sum(1) * inv
        t = (q * e2).sum(1) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)
        if not hit.any():
            return None
        i = np.argmin(np.where(hit, t, np.inf))
        return o + d * t[i]

    # ----- рисование -----

    def _gl(self):
        if self.failed:
            return None
        if self.ctx is None:
            try:
                import moderngl
                try:
                    self.ctx = moderngl.get_context()
                except Exception:
                    self.ctx = moderngl.create_standalone_context()
                self.prog = self.ctx.program(vertex_shader=VS, fragment_shader=FS)
            except Exception as exc:
                print(f"Ковка без OpenGL ({exc})")
                self.failed = True
                return None
        return self.ctx

    def render(self, size, piece, metal_rgb, glow, ghost=None, ghost_alpha=0.32, hammer=None, tongs=None,
               extent=200.0, vcol=None):
        """Кадр сцены. metal_rgb — цвет металла (0–1), glow — свечение каления 0–1; ghost — (V, T) призрака в мире;
        hammer — (центр головки, вид); tongs — (точка хвата, направление конца); vcol — свои цвета вершин детали."""
        V, T, N, _ = piece.surface()
        C = np.tile(metal_rgb, (len(V), 1)) if vcol is None else vcol
        parts = [(self.anvil, 0.0)]
        glass = []                                    # автомолот — полупрозрачный: видно, что под бойком
        if hammer is not None:
            kind = hammer[1]
            if kind.startswith("ram:"):
                glass.append(ram_mesh(hammer[0], kind[4:]))
            else:
                parts.append((hammer_mesh(*hammer), 0.0))
        if tongs is not None:
            parts.append((tongs_mesh(*tongs), 0.0))
        parts.append(((V, N, T, C), glow))
        ctx = self._gl()
        if ctx is None:
            return self.render_soft(size, parts + [(g_, 0.0) for g_ in glass], ghost, extent)
        import moderngl
        w, h = size
        if self.fbo_size != size:
            self.fbo = ctx.framebuffer(color_attachments=[ctx.texture(size, 4)],
                                       depth_attachment=ctx.depth_renderbuffer(size))
            self.fbo_size = size
        mvp, Vm, _ = self.matrices(size, extent)
        self.fbo.use()
        ctx.viewport = (0, 0, w, h)
        self.fbo.clear(0.0, 0.0, 0.0, 0.0, depth=1.0)
        ctx.enable(moderngl.DEPTH_TEST)
        ctx.disable(moderngl.CULL_FACE)
        self.prog["mvp"].write(mvp.T.astype("f4").tobytes())
        light = np.array([-0.35, -0.55, 0.76])
        self.prog["light"].value = tuple(light / np.linalg.norm(light))
        self.prog["view"].value = tuple(-self.view_dir())
        for mesh, g in parts:
            self._draw(ctx, mesh, 1.0, g)
        if glass:
            ctx.enable(moderngl.BLEND)
            ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
            ctx.depth_mask = False
            for mesh in glass:
                self._draw(ctx, mesh, 0.38, 0.0, mode=2)
            ctx.depth_mask = True
            ctx.disable(moderngl.BLEND)
        if ghost is not None:
            gv, gt = ghost
            gn = vertex_normals(gv, gt)
            ctx.enable(moderngl.BLEND)
            ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
            ctx.depth_mask = False
            self._draw(ctx, (gv, gn, gt, np.tile((1.0, 0.86, 0.42), (len(gv), 1))), ghost_alpha, 0.0, mode=1)
            ctx.depth_mask = True
            ctx.disable(moderngl.BLEND)
        data = self.fbo.read(components=4)
        try:
            ctx.screen.use()
        except Exception:
            pass
        img = pygame.image.frombuffer(data, size, "RGBA")
        return pygame.transform.flip(img, False, True)

    def _draw(self, ctx, mesh, alpha, glow, mode=0):
        V, N, T, C = mesh
        data = np.hstack([V, N, C]).astype("f4")
        vbo = ctx.buffer(data.tobytes())
        ibo = ctx.buffer(np.asarray(T, "i4").tobytes())
        vao = ctx.vertex_array(self.prog, [(vbo, "3f 3f 3f", "in_pos", "in_nrm", "in_col")], ibo)
        self.prog["alpha"].value = alpha
        self.prog["glow"].value = glow
        self.prog["mode"].value = mode
        vao.render()
        vao.release()
        vbo.release()
        ibo.release()

    def render_soft(self, size, parts, ghost, extent):
        """Без видеокарты: треугольники по глубине, освещение по нормали грани."""
        surf = pygame.Surface(size, pygame.SRCALPHA)
        light = np.array([-0.35, -0.55, 0.76])
        light /= np.linalg.norm(light)
        tris = []
        for (V, N, T, C), g in parts:
            S = self.to_screen(V, size, extent)
            fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
            fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-9)
            lam = np.abs(fn @ light)
            col = C[T].mean(1) * (0.3 + 0.75 * lam[:, None]) + C[T].mean(1) * g * 0.5
            depth = S[T][:, :, 2].mean(1)
            for i in range(len(T)):
                tris.append((depth[i], S[T[i], :2], col[i]))
        tris.sort(key=lambda q: -q[0])
        for _, pts, col in tris:
            pygame.draw.polygon(surf, tuple(int(max(0, min(1, v)) * 255) for v in col), pts.tolist())
        return surf


def vertex_normals(V, T):
    n = np.zeros_like(V, dtype=float)
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    for k in range(3):
        np.add.at(n, T[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
