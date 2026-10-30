"""Видеокарта для стилей эффектов (ui/fxlab): флипбуки, шейдерные эффекты, меши, текстуры симуляции.

Вызывается из ui/gl_renderer.py: draw(слой) — в сцену, draw_glow() — светящееся ещё раз в источник свечения.
Шейдерные эффекты — один фрагментный шейдер с режимами (огненный шар-комета, взрыв, ударная волна, пламя,
огонь на юните, морозный взрыв, туча, шквал, наледь, жар земли); меши — свой шейдер (оболочка взрыва, лента
хвоста, языки пламени, кристаллы льда).
"""
import json
import os

import numpy as np
import pygame

import moderngl

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FLIP_DIR = os.path.join(ROOT, "assets", "vfx", "flipbooks")

CAM = """
uniform vec2 u_screen;
uniform vec3 u_cam;
uniform vec2 u_shake;
vec2 cam(vec2 p) { return u_cam.xy + (p - u_cam.xy) * u_cam.z + u_shake; }
vec4 ndc(vec2 p) { return vec4(p.x / u_screen.x * 2.0 - 1.0, 1.0 - p.y / u_screen.y * 2.0, 0.0, 1.0); }
"""

INST_VS = """
#version 330
in vec2 in_corner;
in vec2 i_pos; in vec2 i_half; in float i_rot; in vec4 i_p; in vec4 i_color; in float i_mode;
out vec2 v_lc; out vec2 v_uv; out vec4 v_p; out vec4 v_color; out float v_mode; out vec2 v_world;
""" + CAM + """
void main() {
    vec2 p = in_corner * i_half;
    float c = cos(i_rot), s = sin(i_rot);
    p = vec2(p.x * c - p.y * s, p.x * s + p.y * c);
    v_world = i_pos + p;
    gl_Position = ndc(cam(i_pos + p));
    v_lc = in_corner;
    v_uv = vec2(mix(i_p.x, i_p.z, in_corner.x * 0.5 + 0.5), mix(i_p.y, i_p.w, in_corner.y * 0.5 + 0.5));
    v_p = i_p; v_color = i_color; v_mode = i_mode;
}
"""

SPRITE_FS = """
#version 330
in vec2 v_lc; in vec2 v_uv; in vec4 v_p; in vec4 v_color; in float v_mode; in vec2 v_world;
out vec4 f;
uniform sampler2D u_tex;
uniform float u_fx;
void main() {
    vec4 t = texture(u_tex, v_uv);
    int mode = int(v_mode + 0.5);
    if (mode == 1) {                 // дым листа огня: альфа — плотность, цвет — из команды
        float a = t.a * v_color.a;
        f = vec4(v_color.rgb * a, a);
    } else if (mode == 2) {          // свечение листа огня — сложением
        f = vec4(t.rgb * v_color.rgb * v_color.a * u_fx, 0.0);
    } else if (mode == 3) {          // предумноженная картинка (симуляция жидкости)
        f = vec4(t.rgb * v_color.a, t.a * v_color.a);
    } else {
        float a = t.a * v_color.a;
        f = vec4(t.rgb * v_color.rgb * a, a);
    }
}
"""

NOISE = """
uniform sampler2D u_noise;
uniform float u_time;
float N(vec2 uv) { return texture(u_noise, uv).r; }
float N2(vec2 uv) { return texture(u_noise, uv).g; }
float VR(vec2 uv) { return texture(u_noise, uv).b; }
float FB(vec2 uv) { return texture(u_noise, uv).a; }
float fbm(vec2 uv) { return N(uv) * 0.55 + N(uv * 2.03 + 0.37) * 0.3 + N(uv * 4.1 + 0.71) * 0.15; }
vec3 fire(float h) {
    h = clamp(h, 0.0, 1.0);
    vec3 c = mix(vec3(0.35, 0.03, 0.0), vec3(1.0, 0.28, 0.03), smoothstep(0.0, 0.45, h));
    c = mix(c, vec3(1.0, 0.68, 0.2), smoothstep(0.45, 0.8, h));
    return mix(c, vec3(1.0, 0.97, 0.85), smoothstep(0.8, 1.0, h));
}
vec3 ice(float h) {
    h = clamp(h, 0.0, 1.0);
    vec3 c = mix(vec3(0.05, 0.16, 0.38), vec3(0.3, 0.62, 0.95), smoothstep(0.0, 0.5, h));
    return mix(c, vec3(0.92, 0.98, 1.0), smoothstep(0.5, 1.0, h));
}
"""

QUAD_FS = """
#version 330
in vec2 v_lc; in vec2 v_uv; in vec4 v_p; in vec4 v_color; in float v_mode; in vec2 v_world;
out vec4 f;
uniform float u_fx;
""" + NOISE + """
void main() {
    vec2 lc = v_lc;                       // −1..1 в прямоугольнике эффекта
    int mode = int(v_mode + 0.5);
    float age = v_p.x, seed = v_p.y, k = v_p.z, q = v_p.w;
    vec3 rgb = vec3(0.0); float a = 0.0; vec3 glow = vec3(0.0);
    float r = length(lc);
    if (mode == 0) {                      // огненный шар-комета: летит вдоль +x, ядро впереди, хвост рвётся назад
        vec2 p = lc;
        float head = smoothstep(0.42, 0.0, length((p - vec2(0.55, 0.0)) * vec2(1.0, 1.4)));
        float tailw = mix(0.04, 0.55, clamp((p.x + 1.0) / 1.55, 0.0, 1.0));
        float n = fbm(vec2(p.x * 0.9 - u_time * 2.8 + seed, p.y * 0.8 + seed));
        float tail = smoothstep(tailw, tailw * 0.2, abs(p.y + (n - 0.5) * 0.5)) * smoothstep(-1.0, 0.4, p.x)
                     * smoothstep(0.98, 0.5, p.x);
        float h = max(head, tail * (0.35 + 0.65 * n) * smoothstep(-1.0, 0.3, p.x));
        glow = fire(h * 1.15) * h * 1.6;
        a = smoothstep(0.05, 0.4, tail * (1.0 - n)) * 0.0;
    } else if (mode == 1) {               // взрыв: огненный шар растёт, остывает от края, в конце — копоть
        float t = age;                    // 0..1
        float R = mix(0.25, 0.95, 1.0 - pow(1.0 - min(t * 1.6, 1.0), 3.0));
        float n = fbm(lc * 1.4 + vec2(seed, -u_time * 0.35)) ;
        float n2 = fbm(lc * 2.6 + vec2(-seed, u_time * 0.6));
        float d = r / R + (n - 0.5) * 0.55 + (n2 - 0.5) * 0.25;
        float body = smoothstep(1.0, 0.75, d);
        float heat = clamp((1.0 - d) * 1.4 - t * 1.25 + 0.35 + (n2 - 0.5) * 0.4, 0.0, 1.0);
        glow = fire(heat * 0.95) * body * heat * 1.5;
        float smoke = body * smoothstep(0.15, 0.6, t) * (1.0 - heat);
        rgb = mix(vec3(0.16, 0.12, 0.1), vec3(0.32, 0.29, 0.27), n) * smoke;
        a = smoke * (1.0 - smoothstep(0.7, 1.0, t)) * 0.92;
        glow *= 1.0 - smoothstep(0.75, 1.0, t);
        glow += vec3(1.0, 0.95, 0.8) * smoothstep(0.25, 0.0, r) * smoothstep(0.12, 0.0, t) * 3.0;
    } else if (mode == 2) {               // ударная волна по земле (прямоугольник сплющен перспективой)
        float t = age;
        float R = mix(0.05, 1.0, 1.0 - pow(1.0 - t, 2.5));
        float w = mix(0.14, 0.04, t);
        float n = N(vec2(atan(lc.y, lc.x) * 0.6 + seed, t));
        float ring = smoothstep(w, 0.0, abs(r - R)) * (1.0 - t) * (0.6 + 0.4 * n);
        glow = mix(v_color.rgb, vec3(1.0), 0.3) * ring * 1.4;
        a = ring * 0.25;
        rgb = vec3(0.35, 0.3, 0.25) * a;
    } else if (mode == 3) {               // языки пламени (огонь на площади): шум в координатах мира — без швов
        vec2 w = v_world * 0.012;
        float y01 = lc.y * 0.5 + 0.5;     // 0 — верх, 1 — низ
        float n = fbm(vec2(w.x * 2.6 + seed, y01 * 0.8 + u_time * 1.7));
        float n2 = fbm(vec2(w.x * 5.3 - seed, y01 * 1.4 + u_time * 2.6));
        // языки: шум, срезанный тем сильнее, чем выше, — снизу сплошное пламя, вверху отдельные язычки
        float tongue = (n * 0.75 + n2 * 0.45) * 1.25 - (1.0 - y01) * 1.25;
        tongue *= k;
        float side = smoothstep(1.0, 0.7, abs(lc.x)) * smoothstep(1.0, 0.88, y01 + 0.0) ;
        float flame = smoothstep(0.12, 0.42, tongue) * side;
        float h = clamp(tongue * 1.4 + 0.15, 0.0, 0.92);
        glow = fire(h) * flame * 0.95;
        float smoke = smoothstep(0.35, 0.05, y01) * smoothstep(0.2, 0.5, n2) * side * 0.35 * k;
        rgb = vec3(0.12, 0.1, 0.09) * smoke;
        a = smoke;
    } else if (mode == 4) {               // огонь на юните: язычки по фигуре, гуще снизу
        float y01 = lc.y * 0.5 + 0.5;
        float n = fbm(vec2(lc.x * 1.6 + seed, y01 * 0.9 + u_time * 2.2));
        float body = smoothstep(1.0, 0.55, abs(lc.x) + (1.0 - y01) * 0.3);
        float tongue = n * 1.3 - (1.0 - y01) * 1.2;
        float flame = smoothstep(0.15, 0.45, tongue) * body;
        glow = fire(clamp(tongue * 1.3 + 0.1, 0.0, 0.9)) * flame * 0.8;
    } else if (mode == 5) {               // морозный взрыв: белая вспышка, кольцо инея, острые лучи
        float t = age;
        float ang = atan(lc.y, lc.x);
        float rays = pow(N(vec2(ang * 0.35 + seed, 0.37)), 5.0) * 4.0;
        float R = mix(0.1, 1.0, 1.0 - pow(1.0 - t, 3.0));
        float ring = smoothstep(0.12, 0.0, abs(r - R)) * (1.0 - t);
        float burst = smoothstep(R, 0.0, r) * rays * (1.0 - t);
        float core = smoothstep(0.35, 0.0, r) * smoothstep(0.25, 0.0, t);
        glow = ice(0.7 + 0.3 * rays) * (ring + burst * 0.8) * 0.9 + vec3(0.9, 0.97, 1.0) * core * 1.2;
        float mist = smoothstep(1.0, 0.2, r) * smoothstep(0.0, 0.3, t) * (1.0 - t) * fbm(lc + seed);
        rgb = vec3(0.85, 0.92, 1.0) * mist * 0.6; a = mist * 0.6;
    } else if (mode == 6) {               // снежная туча: клубы закручиваются
        float ang = atan(lc.y, lc.x) + u_time * 0.4 + r * 1.5;
        vec2 sw = vec2(cos(ang), sin(ang)) * r;
        float n = fbm(sw * 1.3 + seed) * 0.7 + fbm(lc * 2.5 + vec2(u_time * 0.2, seed)) * 0.3;
        float d = smoothstep(1.0, 0.45, r + (n - 0.5) * 0.6);
        rgb = mix(vec3(0.5, 0.56, 0.66), vec3(0.93, 0.96, 1.0), n) * d;
        a = d * smoothstep(0.25, 0.6, n) * k;
        rgb *= k;
    } else if (mode == 7) {               // шквал: ледяные штрихи наискось
        vec2 p = v_world * vec2(0.03, 0.012);
        float x = p.x + p.y * 0.55;
        float lane = fract(x * 3.0 + seed);
        float id = floor(x * 3.0 + seed);
        float sp = 1.3 + N(vec2(id * 0.137, 0.5)) * 1.2;
        float yy = fract(p.y * 0.6 - u_time * sp + N(vec2(id * 0.31, 0.2)));
        float streak = smoothstep(0.06, 0.0, abs(lane - 0.5)) * smoothstep(0.0, 0.25, yy) * smoothstep(0.45, 0.25, yy);
        float area = smoothstep(1.0, 0.8, r);
        glow = vec3(0.75, 0.9, 1.0) * streak * area * k * 1.3;
    } else if (mode == 8) {               // наледь на земле: грани ячеек, трещины, блик
        vec2 w = v_world * 0.02;
        float cell = VR(w * 0.35 + seed);
        float crack = smoothstep(0.08, 0.0, cell);
        float edge = smoothstep(1.0, 0.82, max(abs(lc.x), abs(lc.y)) + (FB(w * 0.4) - 0.5) * 0.25);
        float glint = smoothstep(0.03, 0.0, abs(fract((v_world.x + v_world.y) * 0.004 - u_time * 0.15) - 0.5));
        rgb = mix(vec3(0.55, 0.78, 0.95), vec3(0.95, 0.99, 1.0), crack + glint * 0.6);
        a = edge * (0.32 + crack * 0.5 + glint * 0.3) * k;
        rgb *= a;
    } else if (mode == 9) {               // жар земли под огнём: угли перемигиваются
        vec2 w = v_world * 0.02;
        float n = fbm(w * 0.8 + vec2(u_time * 0.1, seed));
        float n2 = fbm(w * 1.7 - vec2(seed, u_time * 0.25));
        float edge = smoothstep(1.0, 0.7, max(abs(lc.x), abs(lc.y)) + (n - 0.5) * 0.35);
        float heat = smoothstep(0.55, 0.85, n2) * edge * k;
        glow = fire(0.3 + heat * 0.5) * heat * 0.9;
        rgb = vec3(0.07, 0.05, 0.04) * edge * 0.7 * k;
        a = edge * 0.7 * k;
    } else if (mode == 10) {              // мягкое пятно света/жара (вспышка)
        float g = exp(-r * r * 4.0) * k * (1.0 - smoothstep(0.6, 1.0, r));
        glow = v_color.rgb * g;
    }
    float fx = u_fx;
    f = vec4((rgb + glow * fx) * v_color.a, a * v_color.a);
}
"""

MESH_VS = """
#version 330
in vec2 in_pos; in vec2 in_uv; in vec4 in_color; in vec4 in_p;
out vec2 v_uv; out vec4 v_color; out vec4 v_p; out vec2 v_world;
""" + CAM + """
void main() { gl_Position = ndc(cam(in_pos)); v_uv = in_uv; v_color = in_color; v_p = in_p; v_world = in_pos; }
"""

MESH_FS = """
#version 330
in vec2 v_uv; in vec4 v_color; in vec4 v_p; in vec2 v_world;
out vec4 f;
uniform float u_fx;
""" + NOISE + """
void main() {
    int mode = int(v_p.x + 0.5);
    float light = v_p.y, age = v_p.z, seed = v_p.w;
    vec3 rgb = vec3(0.0); float a = 0.0; vec3 glow = vec3(0.0);
    if (mode == 0) {                      // оболочка взрыва: шум «съедает» оболочку с возрастом, край горячий
        float n = fbm(v_uv * vec2(3.0, 2.0) + vec2(seed, -u_time * 0.8));
        float cut = age * 1.15 - 0.1;
        float keep = smoothstep(cut, cut + 0.12, n);
        float edge = smoothstep(cut + 0.2, cut, n) * keep;
        float heat = clamp(1.0 - age * 1.3 + light * 0.4 + edge * 0.6, 0.0, 1.0);
        glow = fire(heat * 0.92) * keep * (0.35 + light * 0.8) * 1.1;
        a = keep * smoothstep(0.35, 0.8, age) * 0.7;
        rgb = vec3(0.14, 0.11, 0.1) * a;
        glow *= 1.0 - smoothstep(0.55, 0.95, age);
    } else if (mode == 1) {               // лента хвоста: огонь бежит назад, рвётся
        float n = fbm(vec2(v_uv.x * 3.0 + u_time * 3.0 + seed, v_uv.y * 1.2));
        float side = 1.0 - abs(v_uv.y * 2.0 - 1.0);
        float h = side * (1.0 - v_uv.x) * 1.4 + (n - 0.5) * 0.7;
        glow = fire(h) * smoothstep(0.2, 0.6, h) * 1.5;
    } else if (mode == 2) {               // язык пламени (конус): шум бежит вверх, кончик рвётся
        float n = fbm(vec2(v_uv.x * 2.0 + seed, v_uv.y * 1.3 - u_time * 2.2));
        float h = (1.0 - v_uv.y) * 1.25 + (n - 0.5) * 0.9 - abs(v_uv.x - 0.5) * 0.8;
        glow = fire(clamp(h * 0.75, 0.0, 0.9) * age) * smoothstep(0.3, 0.7, h) * age * 0.55;
    } else if (mode == 3) {               // лёд: ровный свет граней, край светлее, блик бежит
        float rim = light;
        float glint = smoothstep(0.04, 0.0, abs(fract(v_uv.x * 0.7 + v_uv.y * 0.4 - u_time * 0.25 + seed) - 0.5));
        float n = FB(v_uv * 2.0 + seed);
        vec3 c = mix(v_color.rgb * (0.55 + 0.5 * rim), vec3(0.95, 0.99, 1.0), glint * 0.5 + (n - 0.5) * 0.08);
        rgb = c; a = 1.0;
        glow = vec3(0.4, 0.6, 0.9) * glint * 0.4;
        rgb *= a;
    } else if (mode == 4) {               // снежная шапка/снег: матовый, свет по грани
        rgb = v_color.rgb * (0.7 + 0.35 * light); a = 1.0;
    } else if (mode == 5 || mode == 6) {  // клетка земли: 5 — наледь, 6 — жар под огнём; края — только там,
        vec2 lc = v_uv;                   // где соседа нет (light — биты соседей: 1 слева, 2 справа, 4 сверху, 8 снизу)
        float bits = light;
        bool L = mod(bits, 2.0) >= 1.0, R = mod(floor(bits / 2.0), 2.0) >= 1.0;
        bool T = mod(floor(bits / 4.0), 2.0) >= 1.0, B = mod(floor(bits / 8.0), 2.0) >= 1.0;
        float e = 1.0;
        if (lc.x < 0.0 && !L) e = min(e, 1.0 + lc.x);
        if (lc.x > 0.0 && !R) e = min(e, 1.0 - lc.x);
        if (lc.y < 0.0 && !T) e = min(e, 1.0 + lc.y);
        if (lc.y > 0.0 && !B) e = min(e, 1.0 - lc.y);
        vec2 w = v_world * 0.02;
        float n = fbm(w * 0.7 + seed);
        float edge = smoothstep(0.0, 0.45, e + (n - 0.5) * 0.5);
        if (mode == 5) {
            float cell = VR(w * 0.35);
            float crack = smoothstep(0.08, 0.0, cell);
            float glint = smoothstep(0.03, 0.0, abs(fract((v_world.x + v_world.y) * 0.004 - u_time * 0.15) - 0.5));
            vec3 c = mix(vec3(0.55, 0.78, 0.95), vec3(0.95, 0.99, 1.0), clamp(crack + glint * 0.6, 0.0, 1.0));
            a = edge * (0.28 + crack * 0.5 + glint * 0.3) * age;
            rgb = c * a;
        } else {
            float n2 = fbm(w * 1.7 - vec2(seed, u_time * 0.25));
            float heat = smoothstep(0.55, 0.85, n2) * edge * age;
            glow = fire(0.3 + heat * 0.5) * heat * 0.9;
            a = edge * 0.72 * age;
            rgb = vec3(0.07, 0.05, 0.04) * a;
        }
    }
    f = vec4((rgb + glow * u_fx) * v_color.a, a * v_color.a);
}
"""


class LabGL:
    def __init__(self, ctx, noise):
        self.ctx = ctx
        self.noise = noise
        self.premul = (moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA)
        self.add = (moderngl.ONE, moderngl.ONE)
        corners = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], np.float32).tobytes())
        self.cap = 20000
        self.inst = ctx.buffer(reserve=self.cap * 14 * 4, dynamic=True)
        fmt = (self.inst, "2f 2f 1f 4f 4f 1f/i", "i_pos", "i_half", "i_rot", "i_p", "i_color", "i_mode")
        self.prog_sprite = ctx.program(vertex_shader=INST_VS, fragment_shader=SPRITE_FS)
        self.prog_quad = ctx.program(vertex_shader=INST_VS, fragment_shader=QUAD_FS)
        self.vao_sprite = ctx.vertex_array(self.prog_sprite, [(corners, "2f", "in_corner"), fmt])
        self.vao_quad = ctx.vertex_array(self.prog_quad, [(corners, "2f", "in_corner"), fmt])
        self.mesh_cap = 300000
        self.mesh_buf = ctx.buffer(reserve=self.mesh_cap * 12 * 4, dynamic=True)
        self.prog_mesh = ctx.program(vertex_shader=MESH_VS, fragment_shader=MESH_FS)
        self.vao_mesh = ctx.vertex_array(self.prog_mesh, [(self.mesh_buf, "2f 2f 4f 4f", "in_pos", "in_uv",
                                                           "in_color", "in_p")])
        self.sheets = {}
        self.dyn = {}
        self.time = 0.0

    def sheet(self, name):
        tex = self.sheets.get(name)
        if tex is None:
            path = os.path.join(FLIP_DIR, name + ".png")
            img = pygame.image.load(path)
            data = pygame.image.tobytes(img, "RGBA")
            tex = self.ctx.texture(img.get_size(), 4, data)
            tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self.sheets[name] = tex
        return tex

    def _cam(self, p, sc, w, h):
        zoom = sc.zoom if sc else 1.0
        cx, cy = sc.center if sc else (w / 2, h / 2)
        ox, oy = sc.offset if sc else (0.0, 0.0)
        p["u_screen"] = (float(w), float(h))
        p["u_cam"] = (float(cx), float(cy), float(zoom))
        p["u_shake"] = (float(ox), float(oy))

    def _set(self, p, sc, w, h, fx):
        self._cam(p, sc, w, h)
        if "u_fx" in p:
            p["u_fx"] = fx
        if "u_noise" in p:
            self.noise.use(1)
            p["u_noise"] = 1
        if "u_time" in p:
            p["u_time"] = self.time

    def draw(self, frame, layer, sc, size, fx=1.0, only_add=False):
        if frame is None:
            return
        w, h = size
        for kind, key, blend, data in frame.packed(layer):
            if only_add and blend != "add":
                continue
            self.ctx.blend_func = self.add if blend == "add" else self.premul
            if kind == "mesh":
                n = min(len(data), self.mesh_cap)
                if not n:
                    continue
                self._set(self.prog_mesh, sc, w, h, fx)
                self.mesh_buf.write(data[:n].tobytes())
                self.vao_mesh.render(moderngl.TRIANGLES, vertices=n)
                continue
            n = min(len(data), self.cap)
            if kind == "quad":
                prog, vao = self.prog_quad, self.vao_quad
            else:
                prog, vao = self.prog_sprite, self.vao_sprite
                if kind == "tex":
                    rgba = frame.textures[key]
                    tex = self.dyn.get(key)
                    if tex is None or tex.size != (rgba.shape[1], rgba.shape[0]):
                        tex = self.dyn[key] = self.ctx.texture((rgba.shape[1], rgba.shape[0]), 4)
                        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
                    tex.write(np.ascontiguousarray(rgba).tobytes())
                else:
                    tex = self.sheet(key)
                tex.use(0)
                prog["u_tex"] = 0
            self._set(prog, sc, w, h, fx)
            self.inst.write(data[:n].tobytes())
            vao.render(moderngl.TRIANGLE_STRIP, instances=n)


def sheet_info(name):
    with open(os.path.join(FLIP_DIR, name + ".json"), encoding="utf-8") as f:
        return json.load(f)
