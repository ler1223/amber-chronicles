"""OpenGL-композитор кадра боя.

Порядок: карта света → земля (освещённая) → эффекты под юнитами → юниты (освещённые) → эффекты над юнитами
(частицы, модельки, шейдерные эффекты, ленты) → bloom из светящихся эффектов → сборка (искажение,
хроматическая аберрация, радиальное размытие, вспышка, виньетка, полосы кадра) → интерфейс.

Землю, юнитов и интерфейс рисует pygame на обычных поверхностях; сюда они приходят текстурами. Камера (зум,
тряска) сдвигает всё, кроме интерфейса. Работает и без окна (standalone-контекст) — для скриншотов и тестов.
"""
import numpy as np
import pygame

try:
    import moderngl
except ImportError:          # без moderngl остаётся CPU-путь
    moderngl = None

from ui.props import build_prop_atlas, load_props
from ui.settings import SETTINGS
from ui import theme as T
from ui.vfx import FLOATS, GROUPS, RIB_FLOATS, SFX_FLOATS
from ui.vfx_textures import INDEX, build_atlas, make_noise

FLASH_K = 0.6          # общая сила вспышек экрана (значения в vfx.json — относительные)

CAMERA = """
uniform vec2 u_screen;
uniform vec3 u_cam;         // центр зума (px) и зум
uniform vec2 u_shake;       // тряска (px)
vec2 cam(vec2 p) { return u_cam.xy + (p - u_cam.xy) * u_cam.z + u_shake; }
vec4 ndc(vec2 p) { return vec4(p.x / u_screen.x * 2.0 - 1.0, 1.0 - p.y / u_screen.y * 2.0, 0.0, 1.0); }
"""

FULLSCREEN_VS = """
#version 330
in vec2 in_pos;
out vec2 v_uv;
uniform float u_flipv;      // 1 — текстура из pygame (первая строка — верх), 0 — отрисованная GL (первая — низ)
void main() {
    v_uv = vec2(in_pos.x * 0.5 + 0.5, u_flipv > 0.5 ? 0.5 - in_pos.y * 0.5 : 0.5 + in_pos.y * 0.5);
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

LAYER_VS = """
#version 330
in vec2 in_pos;
out vec2 v_uv;
""" + CAMERA + """
void main() {
    v_uv = vec2(in_pos.x * 0.5 + 0.5, 0.5 - in_pos.y * 0.5);
    gl_Position = ndc(cam(v_uv * u_screen));
}
"""

LAYER_FS = """
#version 330
in vec2 v_uv;
out vec4 f;
uniform sampler2D u_tex;
uniform sampler2D u_light;
uniform vec2 u_screen;
uniform float u_dim;
uniform float u_alpha;
void main() {
    vec4 c = texture(u_tex, v_uv) * u_alpha;
    vec3 L = texture(u_light, gl_FragCoord.xy / u_screen).rgb;
    L = L / (1.0 + L);                              // насыщение: десять вспышек не выжигают поле добела
    vec3 rgb = c.rgb * (1.0 - u_dim) * (1.0 + L * 1.1) + L * 0.04;
    f = vec4(rgb * c.a, c.a);                       // предумноженный цвет
}
"""

PLANE_FS = """
#version 330
out vec4 f;
uniform sampler2D u_flat;
uniform sampler2D u_light;
uniform vec2 u_screen;
uniform vec3 u_cam;
uniform vec2 u_shake;
uniform vec4 u_proj;        // центр доски на экране (x, y), фокус, расстояние камеры
uniform vec2 u_cs;          // cos, sin наклона
uniform vec2 u_center;      // центр доски в клетках
uniform vec4 u_flatmap;     // поля слева и сверху (клеток), пикселей на клетку
uniform vec2 u_flat_size;
uniform vec4 u_board;       // доска в клетках: x0, y0, x1, y1
uniform vec3 u_fog;
uniform float u_dim;
// HD-2D: пиксель экрана → луч камеры → точка на земле → пиксель плоской карты.
// Вне доски земля мягко размыта (глубина резкости), вдали тонет в дымке.
void main() {
    vec2 p = vec2(gl_FragCoord.x, u_screen.y - gl_FragCoord.y);
    p = (p - u_shake - u_cam.xy) / u_cam.z + u_cam.xy;           // обратная камера (зум, тряска)
    float u = (p.x - u_proj.x) / u_proj.z, v = (p.y - u_proj.y) / u_proj.z;
    float den = u_cs.y + v * u_cs.x;
    vec3 rgb = u_fog;
    if (den > 0.0005) {
        float t = v * u_proj.w / den;
        float zc = u_proj.w - t * u_cs.x;
        vec2 g = vec2(u_center.x + u * zc, u_center.y + t);
        vec2 fp = (g + u_flatmap.xy) * u_flatmap.z;
        vec2 uv = fp / u_flat_size;
        if (uv.x >= 0.0 && uv.y >= 0.0 && uv.x < 1.0 && uv.y < 1.0) {
            vec2 out_b = max(u_board.xy - g, g - u_board.zw);
            float away = max(max(out_b.x, out_b.y), 0.0);
            float lod = clamp(away * 0.55 + max(-g.y - 1.0, 0.0) * 0.25, 0.0, 3.2);
            vec3 sharp = texelFetch(u_flat, ivec2(fp), 0).rgb;
            vec3 soft = textureLod(u_flat, uv, lod).rgb;
            rgb = mix(sharp, soft, clamp(lod, 0.0, 1.0));
            float fog = clamp((-g.y - 0.5) / 9.0, 0.0, 0.85) + clamp((g.y - u_board.w - 1.5) / 6.0, 0.0, 0.3);
            float edge = min(min(uv.x, 1.0 - uv.x) * 8.0, min(uv.y, 1.0 - uv.y) * 8.0);
            fog = max(fog, 1.0 - clamp(edge, 0.0, 1.0));
            rgb = mix(rgb, u_fog, fog);
        }
    }
    vec3 L = texture(u_light, gl_FragCoord.xy / u_screen).rgb;
    L = L / (1.0 + L);
    rgb = rgb * (1.0 - u_dim) * (1.0 + L * 1.1) + L * 0.04;
    f = vec4(rgb, 1.0);
}
"""

PARTICLE_VS = """
#version 330
in vec2 in_corner;
in vec2 i_pos; in vec2 i_half; in float i_rot; in float i_ys; in vec4 i_color; in vec4 i_uv;
out vec2 v_uv; out vec4 v_color;
""" + CAMERA + """
void main() {
    vec2 p = in_corner * i_half;
    float c = cos(i_rot), s = sin(i_rot);
    p = vec2(p.x * c - p.y * s, p.x * s + p.y * c);
    p.y *= i_ys;                                        // круги на земле сплющены (вид 3/4)
    gl_Position = ndc(cam(i_pos) + p * u_cam.z);
    v_uv = mix(i_uv.xy, i_uv.zw, in_corner * 0.5 + 0.5);
    v_color = i_color;
}
"""

PARTICLE_FS = """
#version 330
in vec2 v_uv; in vec4 v_color;
out vec4 f;
uniform sampler2D u_atlas;
uniform float u_fx;
void main() {
    vec4 t = texture(u_atlas, v_uv);                    // атлас с предумноженной альфой
    f = vec4(t.rgb * v_color.rgb * v_color.a, t.a * v_color.a) * u_fx;
}
"""

SFX_VS = """
#version 330
in vec2 in_corner;
in vec2 i_pos; in vec2 i_half; in float i_rot; in float i_ys; in vec4 i_color; in vec4 i_p; in vec2 i_q;
out vec2 v_lc; out vec4 v_color; out vec4 v_p; out vec2 v_q; out float v_rot;
""" + CAMERA + """
void main() {
    vec2 p = in_corner * i_half;
    float c = cos(i_rot), s = sin(i_rot);
    p = vec2(p.x * c - p.y * s, p.x * s + p.y * c);
    p.y *= i_ys;
    gl_Position = ndc(cam(i_pos) + p * u_cam.z);
    v_lc = in_corner; v_color = i_color; v_p = i_p; v_q = i_q; v_rot = i_rot;
}
"""

COMMON_FS = """
uniform sampler2D u_noise;
float N(vec2 uv) { return texture(u_noise, uv).r; }
float N2(vec2 uv) { return texture(u_noise, uv).g; }
float V(vec2 uv) { return texture(u_noise, uv).b; }
float NF(vec2 uv) { return texture(u_noise, uv).a; }
vec3 fire(float h) {
    h = clamp(h, 0.0, 1.0);
    vec3 c = mix(vec3(0.45, 0.04, 0.0), vec3(1.0, 0.32, 0.04), smoothstep(0.0, 0.4, h));
    c = mix(c, vec3(1.0, 0.75, 0.25), smoothstep(0.4, 0.75, h));
    return mix(c, vec3(1.0, 1.0, 0.92), smoothstep(0.75, 1.0, h));
}
vec3 whiten(vec3 c, float k) { float m = max(c.r, max(c.g, c.b)); return mix(c, vec3(m), clamp(k, 0.0, 1.0)); }
"""

SFX_FS = """
#version 330
in vec2 v_lc; in vec4 v_color; in vec4 v_p; in vec2 v_q; in float v_rot;
out vec4 f;
uniform float u_fx;
""" + COMMON_FS + """
void main() {
    vec2 lc = v_lc;
    float r = length(lc);
    float a = atan(lc.y, lc.x);
    float t = v_p.x, seed = v_p.y, extra = v_p.w, age = v_q.x;
    int mode = int(v_p.z + 0.5);
    vec3 col = v_color.rgb;
    float I = 0.0;
    if (mode == 0 || mode == 8) {                       // ударная волна (8 — сектор в сторону удара)
        float R = mix(0.22, 0.92, 1.0 - pow(1.0 - t, 3.0));
        float w = mix(0.11, 0.04, t);
        float n = N(vec2(a / 6.2832 * 3.0 + seed, r * 0.5 - age * 0.4));
        float band = exp(-pow((r - R) / w, 2.0));
        float inner = smoothstep(R, 0.0, r) * 0.1 * (1.0 - t);
        I = (band * (0.5 + 0.9 * n) + inner * n) * smoothstep(1.0, 0.93, r);
        I *= smoothstep(t * 0.7, t * 0.7 + 0.35, n + 0.25);
        if (mode == 8) I *= smoothstep(extra, extra * 0.55, abs(a));
        col = whiten(col, band * 0.4);
    } else if (mode == 1) {                             // вихрь
        float sw = a + r * (4.0 + extra) - age * 6.0;
        float arms = 0.5 + 0.5 * sin(sw * 3.0);
        float n = N(vec2(sw / 6.2832 + seed, r * 0.8 - age * 0.7));
        I = pow(arms, 2.0) * (0.35 + n) * smoothstep(1.0, 0.5, r) * smoothstep(0.05, 0.3, r);
        I += smoothstep(0.4, 0.0, r) * 0.35;
    } else if (mode == 2) {                             // столп света/огня (сверху вниз)
        float open = smoothstep(0.0, 0.12, t) * (1.0 - 0.85 * smoothstep(0.45, 1.0, t));
        float xs = abs(lc.x) / max(0.03, open);
        float n = N(vec2(lc.x * 0.5 + seed, lc.y * 0.4 + age * 2.2));
        float n2 = NF(vec2(lc.x * 0.8 - seed, lc.y * 0.9 + age * 3.5));
        float core = exp(-xs * xs * 16.0);
        float body = exp(-xs * xs * 2.2) * (0.3 + 0.9 * n * (0.6 + n2));
        float vert = smoothstep(-1.0, -0.55, lc.y) * smoothstep(1.0, 0.86, lc.y);
        I = (core * 1.5 + body) * vert + exp(-pow((lc.y - 0.86) / 0.06, 2.0)) * exp(-xs * xs * 0.8) * 0.8 * open;
        col = whiten(col, core * 0.7);
    } else if (mode == 3 || mode == 9) {                // энергетическая сфера (9 — огненная)
        float sph = sqrt(max(0.0, 1.0 - r * r));
        vec2 suv = lc / (1.0 + sph);
        float n = N(suv * 0.55 + vec2(age * 0.45 + seed, age * 0.25));
        float n2 = N2(suv * 1.1 - vec2(age * 0.6, seed - age * 0.3));
        float body = smoothstep(1.0, 0.72, r);
        float core = exp(-r * r * 7.0);
        float rim = smoothstep(0.55, 0.92, r) * body;
        float turb = n * n2 * 2.2;
        I = body * (0.3 + 0.9 * turb) + core * 0.9 + rim * 0.35 + smoothstep(1.35, 0.85, r) * 0.12;
        if (mode == 9) {
            col = fire(core * 0.9 + body * turb * 0.55 + 0.1) * col;
        } else {
            col = whiten(col, core * 0.45 + turb * 0.1);
        }
    } else if (mode == 4) {                             // купол щита
        float body = smoothstep(1.0, 0.96, r);
        float fres = pow(clamp(r, 0.0, 1.0), 3.0);
        float cells = smoothstep(0.1, 0.0, V(lc * 0.45 + vec2(seed, age * 0.04)));
        float scan = smoothstep(0.85, 1.0, sin(lc.y * 5.0 - age * 5.0));
        I = body * (fres * 0.9 + cells * (0.2 + 0.4 * fres) + 0.05 + scan * 0.15);
        float edge = 1.0 - min(1.0, age * 3.5) * 2.4;       // купол «вырастает» снизу вверх
        I = I * smoothstep(edge, edge + 0.25, lc.y) + body * exp(-pow((lc.y - edge) / 0.05, 2.0)) * 1.2;
        col = whiten(col, fres * 0.3);
    } else if (mode == 5) {                             // круг на земле: заливка с шумом и яркий край
        float n = N(lc * 0.5 + vec2(seed, -age * 0.15));
        float edge = smoothstep(1.0, 0.9, r) * smoothstep(0.72, 0.96, r);
        float fill = smoothstep(1.0, 0.0, r) * (0.2 + 0.6 * n);
        I = (edge * 1.2 + fill) * smoothstep(1.0, 0.97, r);
        I *= smoothstep(t * 0.9, t * 0.9 + 0.25, n + 0.15);
    } else if (mode == 6) {                             // светящиеся трещины в земле
        float e = V(lc * 0.32 + seed);
        float lines = smoothstep(0.07, 0.0, e);
        float mask = smoothstep(1.0, 0.25, r + (N(lc * 0.2 + seed) - 0.5) * 0.5);
        float reach = smoothstep(r - 0.12, r + 0.05, min(1.0, t * 3.0) * 1.1);
        I = lines * mask * reach * (1.0 + 1.5 * exp(-r * r * 5.0));
        col = whiten(col, lines * exp(-r * r * 3.0) * 0.5);
    } else if (mode == 7) {                             // аура: языки пламени вокруг юнита
        float up = (1.0 - lc.y) * 0.5;
        float n = N(vec2(lc.x * 0.45 + seed, lc.y * 0.35 + age * 1.1));
        float n2 = N2(vec2(lc.x * 0.9 - seed, lc.y * 0.7 + age * 1.9));
        float w = 0.8 - up * 0.3;
        float x = abs(lc.x + (n - 0.5) * 0.35 * up);
        float body = smoothstep(w, w * 0.45, x);
        float tongues = smoothstep(up - 0.05, up + 0.35, n * n2 * 2.4);
        float edge = 0.35 + 0.65 * smoothstep(0.0, w * 0.8, x);
        I = body * tongues * edge * smoothstep(1.0, 0.8, lc.y);
    } else if (mode == 10 || mode == 11) {              // лучи из центра (11 — острые, ледяные)
        float rays = NF(vec2(a / 6.2832 * (mode == 11 ? 2.0 : 5.0) + seed, 0.37));
        rays = pow(rays, mode == 11 ? 6.0 : 3.0) * (mode == 11 ? 6.0 : 3.0);
        float reach = min(1.0, t * 1.8) * 1.05;
        I = rays * smoothstep(reach, reach - 0.35, r) * smoothstep(0.0, 0.12, r) + exp(-r * r * 14.0) * (1.0 - t);
        col = whiten(col, exp(-r * r * 6.0));
    }
    float A = clamp(I, 0.0, 4.0) * v_color.a;
    f = vec4(col * A, clamp(A, 0.0, 1.0)) * u_fx;
}
"""

DISTORT_FS = """
#version 330
in vec2 v_lc; in vec4 v_color; in vec4 v_p; in vec2 v_q; in float v_rot;
out vec4 f;
""" + COMMON_FS + """
void main() {
    vec2 lc = v_lc;
    float r = length(lc);
    float t = v_p.x, seed = v_p.y, strength = v_p.w * v_color.a, age = v_q.x;
    int mode = int(v_p.z + 0.5);
    vec2 dir = r > 0.001 ? lc / r : vec2(0.0);
    vec2 off = vec2(0.0);
    if (mode == 20) {                                   // кольцо преломления (ударная волна)
        float R = mix(0.08, 0.95, 1.0 - pow(1.0 - t, 2.5));
        float w = mix(0.16, 0.06, t);
        off = dir * exp(-pow((r - R) / w, 2.0)) * strength * (1.0 - t);
    } else if (mode == 21) {                            // марево над огнём
        vec2 n = vec2(N(lc * 0.35 + vec2(seed, age * 0.9)), N2(lc * 0.35 + vec2(-seed, age * 1.2))) - 0.5;
        off = n * 2.0 * smoothstep(1.0, 0.2, r) * strength;
    } else {                                            // втягивание к центру
        off = -dir * sin(3.1416 * min(r, 1.0)) * (1.0 - r) * strength * 2.0;
    }
    float c = cos(v_rot), s = sin(v_rot);
    off = vec2(off.x * c - off.y * s, off.x * s + off.y * c);
    f = vec4(off, 0.0, 1.0);
}
"""

RIBBON_VS = """
#version 330
in vec2 in_pos; in vec2 in_uv; in vec4 in_color; in vec4 in_p;
out vec2 v_uv; out vec4 v_color; out vec4 v_p;
""" + CAMERA + """
void main() {
    gl_Position = ndc(cam(in_pos));
    v_uv = in_uv; v_color = in_color; v_p = in_p;
}
"""

RIBBON_FS = """
#version 330
in vec2 v_uv; in vec4 v_color; in vec4 v_p;
out vec4 f;
uniform float u_fx;
""" + COMMON_FS + """
void main() {
    float u = v_uv.x, v = v_uv.y;
    float across = 1.0 - abs(v * 2.0 - 1.0);
    int mode = int(v_p.x + 0.5);
    float seed = v_p.y, L = v_p.z, age = v_p.w;
    vec3 col = v_color.rgb;
    float I;
    if (mode == 1) {                                    // взмах оружия: ядро-линия, рвётся с хвоста
        float n = N(vec2(L * 0.006 + seed, v * 0.5));
        I = pow(across, 1.3) * (0.55 + 0.8 * n) * (1.0 - u * 0.6);
        I *= smoothstep(u * 1.1 - 0.1, u * 1.1 + 0.2, n + 0.1);
        col = whiten(col, pow(across, 10.0) * (1.0 - u));
        I += pow(across, 12.0) * (1.0 - u) * 1.2;
    } else if (mode == 2) {                             // дым
        float n = N(vec2(L * 0.004 - age * 0.3 + seed, v * 0.6 + seed));
        I = pow(across, 1.2) * (0.3 + n) * (1.0 - u) * 0.8;
    } else if (mode == 3) {                             // огонь
        float n = N(vec2(L * 0.006 - age * 2.0 + seed, v * 0.5 + seed));
        float heat = across * (1.0 - u) * (0.5 + 0.9 * n);
        col = fire(heat * 1.2) * col;
        I = smoothstep(0.04, 0.35, heat) * (0.6 + heat);
    } else if (mode == 5) {                             // молния: тонкое белое ядро, рваное сияние
        float n = NF(vec2(L * 0.02 + seed - age * 9.0, v * 0.5));
        float core = pow(across, 6.0);
        I = (core * 2.0 + pow(across, 1.5) * (0.35 + 0.6 * n)) * (1.0 - u) * step(0.15, n + 0.3);
        col = whiten(col, core);
    } else if (mode == 4) {                             // вода: плотная струя с пеной
        float n = N(vec2(L * 0.008 - age * 1.2 + seed, v * 0.8));
        I = pow(across, 0.7) * (0.55 + 0.6 * n) * pow(1.0 - u, 0.8);
        col = whiten(col, smoothstep(0.65, 0.95, n) * across);
    } else {                                            // энергия: волокна шума бегут по ленте
        float n = N(vec2(L * 0.004 - age * 1.6 + seed, v * 0.35 + seed));
        float core = pow(across, 8.0) * (1.0 - u);
        I = pow(across, 1.6) * (0.4 + n * 1.1) * pow(1.0 - u, 1.2) + core;
        col = whiten(col, core * 0.7);
    }
    float A = max(I, 0.0) * v_color.a;
    f = vec4(col * A, clamp(A, 0.0, 1.0)) * u_fx;
}
"""

BRIGHT_FS = """
#version 330
in vec2 v_uv;
out vec4 f;
uniform sampler2D u_tex;
uniform float u_threshold;
void main() {
    vec3 c = texture(u_tex, v_uv).rgb;
    float l = max(max(c.r, c.g), c.b);
    float k = smoothstep(u_threshold, u_threshold + 0.6, l);
    f = vec4(c * k, 1.0);
}
"""

BLUR_FS = """
#version 330
in vec2 v_uv;
out vec4 f;
uniform sampler2D u_tex;
uniform vec2 u_dir;
void main() {
    float w[5] = float[](0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);
    vec3 c = texture(u_tex, v_uv).rgb * w[0];
    for (int i = 1; i < 5; i++) {
        c += texture(u_tex, v_uv + u_dir * float(i)).rgb * w[i];
        c += texture(u_tex, v_uv - u_dir * float(i)).rgb * w[i];
    }
    f = vec4(c, 1.0);
}
"""

COMBINE_FS = """
#version 330
in vec2 v_uv;
out vec4 f;
uniform sampler2D u_scene;
uniform sampler2D u_b1; uniform sampler2D u_b2; uniform sampler2D u_b3;
uniform sampler2D u_dist;
uniform vec2 u_screen;
uniform float u_bloom;
uniform vec3 u_flash;
uniform float u_aberr;
uniform float u_radial;
uniform vec2 u_rc;
uniform float u_bars;
uniform float u_vignette;
vec3 scene(vec2 uv) {
    if (u_aberr > 0.002) {
        vec2 d = (uv - 0.5) * u_aberr * 0.014;
        return vec3(texture(u_scene, uv + d).r, texture(u_scene, uv).g, texture(u_scene, uv - d).b);
    }
    return texture(u_scene, uv).rgb;
}
void main() {
    vec2 d = texture(u_dist, v_uv).rg;
    vec2 uv = v_uv + vec2(d.x, -d.y) / u_screen;
    vec3 c = scene(uv);
    if (u_radial > 0.002) {                              // радиальное размытие к точке удара
        vec2 dir = uv - u_rc;
        for (int i = 1; i < 10; i++) c += scene(uv - dir * u_radial * 0.011 * float(i));
        c /= 10.0;
    }
    vec3 b = texture(u_b1, uv).rgb * 0.6 + texture(u_b2, uv).rgb * 0.8 + texture(u_b3, uv).rgb * 1.0;
    c += b * u_bloom + u_flash;
    // мягкое насыщение: всё, что ярче 1, уходит в белое, а не обрезается по каналам
    vec3 over = max(c - 1.0, 0.0);
    c = min(c, 1.0) + vec3(dot(over, vec3(0.33)));
    c *= 1.0 - u_vignette * smoothstep(0.35, 0.95, length((v_uv - 0.5) * vec2(1.0, 0.8)) * 1.4);
    float bar = u_bars * 0.1;
    c *= smoothstep(bar, bar + 0.004, v_uv.y) * smoothstep(1.0 - bar, 1.0 - bar - 0.004, v_uv.y);
    f = vec4(min(c, 1.0), 1.0);
}
"""

UI_FS = """
#version 330
in vec2 v_uv;
out vec4 f;
uniform sampler2D u_tex;
uniform vec4 u_tint;         // 1 — как есть; темнее — подложка в полях вокруг кадра
void main() { f = texture(u_tex, v_uv) * u_tint; }
"""


class GLRenderer:
    """window=True — рисует в окно pygame (pygame.OPENGL); иначе — во внеэкранный буфер (read() для скриншота)."""

    def __init__(self, size, window=True, bloom=1.0, threshold=0.25, props=None):
        self.w, self.h = size
        self.ctx = moderngl.create_context() if window else moderngl.create_standalone_context()
        self.window = window
        self.window_size = None          # фактический размер окна (ctx.screen.size кэшируется при создании контекста)
        self.bloom, self.threshold = bloom, threshold
        ctx = self.ctx
        self.premul = (moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA)
        quad = np.array([-1, -1, 1, -1, -1, 1, 1, 1], np.float32)
        self.quad = ctx.buffer(quad.tobytes())
        prog = ctx.program
        self.prog_layer = prog(vertex_shader=LAYER_VS, fragment_shader=LAYER_FS)
        self.prog_bright = prog(vertex_shader=FULLSCREEN_VS, fragment_shader=BRIGHT_FS)
        self.prog_blur = prog(vertex_shader=FULLSCREEN_VS, fragment_shader=BLUR_FS)
        self.prog_combine = prog(vertex_shader=FULLSCREEN_VS, fragment_shader=COMBINE_FS)
        self.prog_ui = prog(vertex_shader=FULLSCREEN_VS, fragment_shader=UI_FS)
        self.prog_ui["u_tint"] = (1.0, 1.0, 1.0, 1.0)
        self.prog_plane = prog(vertex_shader=FULLSCREEN_VS, fragment_shader=PLANE_FS)
        self.vao_plane = ctx.vertex_array(self.prog_plane, [(self.quad, "2f", "in_pos")])
        self.tex_plane = None
        self.vao = {name: ctx.vertex_array(p, [(self.quad, "2f", "in_pos")])
                    for name, p in (("layer", self.prog_layer), ("bright", self.prog_bright),
                                    ("blur", self.prog_blur), ("combine", self.prog_combine), ("ui", self.prog_ui))}
        corners = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], np.float32).tobytes())
        # частицы, модельки, свет — один формат инстанса
        self.prog_p = prog(vertex_shader=PARTICLE_VS, fragment_shader=PARTICLE_FS)
        self.cap = 50000
        self.inst = ctx.buffer(reserve=self.cap * FLOATS * 4, dynamic=True)
        self.vao_p = ctx.vertex_array(self.prog_p, [
            (corners, "2f", "in_corner"),
            (self.inst, "2f 2f 1f 1f 4f 4f/i", "i_pos", "i_half", "i_rot", "i_ys", "i_color", "i_uv"),
        ])
        # шейдерные эффекты и искажение
        self.sfx_cap = 2000
        self.sfx_buf = ctx.buffer(reserve=self.sfx_cap * SFX_FLOATS * 4, dynamic=True)
        self.prog_sfx = prog(vertex_shader=SFX_VS, fragment_shader=SFX_FS)
        self.prog_dist = prog(vertex_shader=SFX_VS, fragment_shader=DISTORT_FS)
        fmt = (self.sfx_buf, "2f 2f 1f 1f 4f 4f 2f/i", "i_pos", "i_half", "i_rot", "i_ys", "i_color", "i_p", "i_q")
        self.vao_sfx = ctx.vertex_array(self.prog_sfx, [(corners, "2f", "in_corner"), fmt])
        self.vao_dist = ctx.vertex_array(self.prog_dist, [(corners, "2f", "in_corner"), fmt])
        # ленты
        self.rib_cap = 60000
        self.rib_buf = ctx.buffer(reserve=self.rib_cap * RIB_FLOATS * 4, dynamic=True)
        self.prog_rib = prog(vertex_shader=RIBBON_VS, fragment_shader=RIBBON_FS)
        self.vao_rib = ctx.vertex_array(self.prog_rib, [
            (self.rib_buf, "2f 2f 4f 4f", "in_pos", "in_uv", "in_color", "in_p")])
        # текстуры
        atlas, self.uvs = build_atlas()
        self.atlas = ctx.texture((atlas.shape[1], atlas.shape[0]), 4, np.ascontiguousarray(atlas).tobytes())
        self.atlas.build_mipmaps()
        self.atlas.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        self.glow_uv = tuple(self.uvs[INDEX["glow"]])
        noise = make_noise_cached()
        self.noise = ctx.texture((noise.shape[1], noise.shape[0]), 4, np.ascontiguousarray(noise).tobytes())
        self.noise.repeat_x = self.noise.repeat_y = True
        self.noise.build_mipmaps()
        self.noise.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        props = props if props is not None else load_props()
        self.props_tex = None
        if props:
            patlas, self.prop_uvs, self.prop_dims, _ = build_prop_atlas(props)
            self.props_tex = ctx.texture((patlas.shape[1], patlas.shape[0]), 4, np.ascontiguousarray(patlas).tobytes())
            self.props_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        # буферы
        self.tex_ground = ctx.texture((self.w, self.h), 4)
        self.tex_units = ctx.texture((self.w, self.h), 4)
        self.tex_glow = ctx.texture((self.w, self.h), 4)     # яркие пиксели пиксельных эффектов (ui/pixfx.py)
        self.tex_ui = ctx.texture((self.w, self.h), 4)
        self.scene = ctx.texture((self.w, self.h), 4, dtype="f2")
        self.fbo_scene = ctx.framebuffer([self.scene])
        # свет: только аддитивные эффекты — источник bloom (мир и спрайты не светятся сами)
        self.light = ctx.texture((self.w, self.h), 4, dtype="f2")
        self.fbo_light = ctx.framebuffer([self.light])
        hw, hh = self.w // 2, self.h // 2
        self.lightmap = ctx.texture((hw, hh), 4, dtype="f2")
        self.fbo_lightmap = ctx.framebuffer([self.lightmap])
        self.dist = ctx.texture((hw, hh), 4, dtype="f2")
        self.fbo_dist = ctx.framebuffer([self.dist])
        self.levels = []
        for k in (2, 4, 8):
            size = (self.w // k, self.h // k)
            a, b = ctx.texture(size, 4, dtype="f2"), ctx.texture(size, 4, dtype="f2")
            for t in (a, b):
                t.repeat_x = t.repeat_y = False
            self.levels.append((a, b, ctx.framebuffer([a]), ctx.framebuffer([b]), size))
        # пустышка: после кадра отвязываем ею слоты текстур — иначе текстура, в которую потом пишем,
        # остаётся привязанной к слоту чтения, и драйвер пропускает запись (петля обратной связи)
        self.dummy = ctx.texture((1, 1), 4, bytes(4))
        # кадр всегда собирается в буфер 1280×800; в окно он выводится растянутым под его размер (view)
        self.out = ctx.texture((self.w, self.h), 4)
        self.out.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.fbo_out = ctx.framebuffer([self.out])
        self.view = None           # (x, y, ширина, высота) кадра в окне; None — окно ровно 1280×800

    # ---------- загрузка поверхностей ----------

    def _upload(self, tex, surf):
        """Память поверхности уходит в текстуру как есть (без копии через tobytes); порядок каналов
        выравнивает swizzle текстуры — обычно в памяти pygame лежит BGRA."""
        order = self._order(surf)
        if order is None:
            tex.swizzle = "RGBA"
            tex.write(pygame.image.tobytes(surf, "RGBA"))
            return
        if tex.swizzle != order:
            tex.swizzle = order
        tex.write(surf.get_view("1"))

    def _order(self, surf):
        """Порядок каналов в памяти 32-битной поверхности без отступов строк; None — нужна конвертация."""
        if surf.get_bytesize() != 4 or surf.get_pitch() != surf.get_width() * 4:
            return None
        masks = surf.get_masks()
        names = {}
        for ch, m in zip("RGBA", masks):
            if m:
                names[{0xFF: 0, 0xFF00: 1, 0xFF0000: 2, 0xFF000000: 3}.get(m, -1)] = ch
        if -1 in names or len(names) < 3:
            return None
        for k in range(4):
            names.setdefault(k, "1")     # нет альфы (обычная поверхность) — считаем непрозрачной
        return "".join(names[k] for k in range(4))

    # ---------- проходы ----------

    def _cam(self, prog, sc):
        zoom = sc.zoom if sc else 1.0
        cx, cy = sc.center if sc else (self.w / 2, self.h / 2)
        ox, oy = sc.offset if sc else (0.0, 0.0)
        prog["u_screen"] = (float(self.w), float(self.h))
        prog["u_cam"] = (float(cx), float(cy), float(zoom))
        prog["u_shake"] = (float(ox), float(oy))

    def _fx(self, sc):
        """Яркость эффектов: на паузе приглушаются, чтобы было видно поле и фигурки."""
        return 1.0 - 0.6 * (sc.calm if sc else 0.0)

    def _instances(self, rows, tex, blend, sc, solid=False):
        n = min(len(rows), self.cap)
        if not n:
            return
        self.ctx.blend_func = blend
        tex.use(0)
        self.prog_p["u_atlas"] = 0
        self.prog_p["u_fx"] = 1.0 if solid else self._fx(sc)
        self._cam(self.prog_p, sc)
        self.inst.write(rows[:n].tobytes())
        self.vao_p.render(moderngl.TRIANGLE_STRIP, instances=n)

    def _sfx(self, rows, blend, sc, distort=False):
        n = min(len(rows), self.sfx_cap)
        if not n:
            return
        self.ctx.blend_func = blend
        p = self.prog_dist if distort else self.prog_sfx
        self.noise.use(1)
        p["u_noise"] = 1
        if not distort:
            p["u_fx"] = self._fx(sc)
        self._cam(p, sc)
        self.sfx_buf.write(rows[:n].tobytes())
        (self.vao_dist if distort else self.vao_sfx).render(moderngl.TRIANGLE_STRIP, instances=n)

    def _ribbons(self, verts, blend, sc):
        n = min(len(verts), self.rib_cap)
        if not n:
            return
        self.ctx.blend_func = blend
        self.noise.use(1)
        self.prog_rib["u_noise"] = 1
        self.prog_rib["u_fx"] = self._fx(sc)
        self._cam(self.prog_rib, sc)
        self.rib_buf.write(verts[:n].tobytes())
        self.vao_rib.render(moderngl.TRIANGLES, vertices=n)

    def _layer(self, tex, sc, blend, alpha=1.0):
        self.ctx.blend_func = blend
        tex.use(0)
        self.lightmap.use(2)
        p = self.prog_layer
        p["u_tex"], p["u_light"] = 0, 2
        p["u_alpha"] = alpha
        p["u_dim"] = sc.dim * 0.45 if sc else 0.0
        self._cam(p, sc)
        self.vao["layer"].render(moderngl.TRIANGLE_STRIP)

    def _plane(self, plane, sc):
        """Земля HD-2D: плоская карта на наклонной плоскости (ui/projection.py)."""
        from ui import projection as P
        surf, fog = plane
        size = surf.get_size()
        if self.tex_plane is None or self.tex_plane.size != size:
            self.tex_plane = self.ctx.texture(size, 4)
            self.tex_plane.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        self._upload(self.tex_plane, surf)
        self.tex_plane.build_mipmaps()
        self.ctx.blend_func = (moderngl.ONE, moderngl.ZERO)
        self.tex_plane.use(0)
        self.lightmap.use(2)
        p = self.prog_plane
        p["u_flat"], p["u_light"] = 0, 2
        p["u_dim"] = sc.dim * 0.45 if sc else 0.0
        p["u_flipv"] = 0.0
        self._cam(p, sc)
        sp = P.shader_params()
        p["u_proj"], p["u_cs"], p["u_center"] = sp["proj"], sp["cs"], sp["center"]
        p["u_flatmap"], p["u_flat_size"], p["u_board"] = sp["flat"], sp["flat_size"], sp["board"]
        p["u_fog"] = tuple(float(v) for v in fog)
        self.vao_plane.render(moderngl.TRIANGLE_STRIP)

    def _lab(self):
        if getattr(self, "lab_gl", None) is None:
            from ui.fxlab.gl import LabGL
            self.lab_gl = LabGL(self.ctx, self.noise)
        return self.lab_gl

    def render(self, world, vfx=None, ui=None, units=None, plane=None, glow=None, lab=None):
        """world — земля (или весь мир, если units нет), units — прозрачный слой юнитов, ui — интерфейс.
        plane — (плоская карта, цвет дымки): земля HD-2D вместо world. glow — яркие пиксели эффектов для bloom."""
        ctx = self.ctx
        sc = vfx.screen if vfx else None
        add = (moderngl.ONE, moderngl.ONE)
        if plane is None:
            self._upload(self.tex_ground, world)
        if units is not None:
            self._upload(self.tex_units, units)
        if glow is not None:
            self._upload(self.tex_glow, glow)
        groups = vfx.batches(self.uvs) if vfx else {g: np.zeros((0, FLOATS), np.float32) for g in GROUPS}
        sfx = vfx.sfx_rows() if vfx else {}
        ribs = vfx.ribbon_verts() if vfx else {}
        props = vfx.prop_rows(self.prop_uvs, self.prop_dims) if (vfx and self.props_tex) else np.zeros((0, FLOATS))
        ctx.enable(moderngl.BLEND)
        # 0. карта света (половинное разрешение)
        self.fbo_lightmap.use()
        self.fbo_lightmap.clear()
        ctx.viewport = (0, 0, self.w // 2, self.h // 2)
        if vfx is not None:
            self._instances(vfx.light_rows(self.glow_uv), self.atlas, add, sc)
        # 1. земля и всё, что под юнитами
        self.fbo_scene.use()
        self.fbo_scene.clear()
        ctx.viewport = (0, 0, self.w, self.h)
        if plane is not None:
            self._plane(plane, sc)
        else:
            self._layer(self.tex_ground, sc, (moderngl.ONE, moderngl.ZERO))
        if vfx is not None:
            self._sfx(sfx["under_alpha"], self.premul, sc)
            self._instances(groups["under_alpha"], self.atlas, self.premul, sc)
            self._sfx(sfx["under_add"], add, sc)
            self._instances(groups["under_add"], self.atlas, add, sc)
        if lab is not None:                    # стили эффектов (ui/fxlab): то, что лежит на земле
            self._lab().time = vfx.time if vfx else 0.0
            self._lab().draw(lab, "ground", sc, (self.w, self.h), self._fx(sc))
        # 2. юниты и укрытия
        if units is not None:
            self._layer(self.tex_units, sc, self.premul)
        # 3. над юнитами: дым и капли, модельки, затем свет
        if vfx is not None:
            self._instances(groups["air_alpha"], self.atlas, self.premul, sc)
            self._ribbons(ribs["alpha"], self.premul, sc)
            self._sfx(sfx["air_alpha"], self.premul, sc)
            if self.props_tex is not None:
                self._instances(props, self.props_tex, self.premul, sc, solid=True)
            self._sfx(sfx["air_add"], add, sc)
            self._ribbons(ribs["add"], add, sc)
            self._instances(groups["air_add"], self.atlas, add, sc)
        if lab is not None:
            self._lab().draw(lab, "air", sc, (self.w, self.h), self._fx(sc))
        # 3б. фигурки просвечивают сквозь эффекты: слой юнитов ещё раз, полупрозрачно (где эффекта нет —
        #     кадр не меняется: тот же цвет поверх того же цвета)
        if units is not None and vfx is not None:
            self._layer(self.tex_units, sc, self.premul, 0.35 + 0.45 * sc.calm)
        # 4. источник bloom: все светящиеся эффекты ещё раз
        self.fbo_light.use()
        self.fbo_light.clear()
        if vfx is not None:
            self._sfx(sfx["under_add"], add, sc)
            self._instances(groups["under_add"], self.atlas, add, sc)
            self._sfx(sfx["air_add"], add, sc)
            self._ribbons(ribs["add"], add, sc)
            self._instances(groups["air_add"], self.atlas, add, sc)
        if lab is not None:                   # стили эффектов: светящееся (сложение) — ещё раз в источник свечения
            self._lab().draw(lab, "ground", sc, (self.w, self.h), self._fx(sc), only_add=True)
            self._lab().draw(lab, "air", sc, (self.w, self.h), self._fx(sc), only_add=True)
        if glow is not None:                  # пиксельные эффекты светятся только двумя верхними цветами палитры
            self._layer(self.tex_glow, sc, add, 0.95 * self._fx(sc))
        # 5. искажение (половинное разрешение)
        self.fbo_dist.use()
        self.fbo_dist.clear()
        ctx.viewport = (0, 0, self.w // 2, self.h // 2)
        if vfx is not None:
            self._sfx(sfx["distort"], add, sc, distort=True)
        ctx.disable(moderngl.BLEND)
        # 6. bloom: свет → уменьшение и размытие на трёх уровнях
        src = self.light
        for i, (a, b, fa, fb, size) in enumerate(self.levels):
            ctx.viewport = (0, 0, *size)
            fa.use()
            fa.clear()
            src.use(0)
            if i == 0:
                self.prog_bright["u_tex"] = 0
                self.prog_bright["u_threshold"] = self.threshold
                self.prog_bright["u_flipv"] = 0.0
                self.vao["bright"].render(moderngl.TRIANGLE_STRIP)
            else:
                self.prog_blur["u_tex"] = 0
                self.prog_blur["u_dir"] = (0.0, 0.0)
                self.prog_blur["u_flipv"] = 0.0
                self.vao["blur"].render(moderngl.TRIANGLE_STRIP)
            for direction, (s_tex, d_fbo) in (((1.0 / size[0], 0.0), (a, fb)), ((0.0, 1.0 / size[1]), (b, fa))):
                d_fbo.use()
                d_fbo.clear()
                s_tex.use(0)
                self.prog_blur["u_tex"] = 0
                self.prog_blur["u_dir"] = direction
                self.vao["blur"].render(moderngl.TRIANGLE_STRIP)
            src = a
        # 7. сборка: сцена с искажением + bloom + вспышка, аберрация, размытие, полосы кадра
        target = self.fbo_out
        target.use()
        target.clear()
        ctx.viewport = (0, 0, self.w, self.h)
        self.scene.use(0)
        for i, (a, *_rest) in enumerate(self.levels):
            a.use(i + 1)
        self.dist.use(4)
        p = self.prog_combine
        p["u_scene"], p["u_b1"], p["u_b2"], p["u_b3"], p["u_dist"] = 0, 1, 2, 3, 4
        p["u_screen"] = (float(self.w), float(self.h))
        p["u_bloom"] = self.bloom * SETTINGS["bloom"] * self._fx(sc)
        p["u_flipv"] = 0.0
        flash = (np.array(sc.flash_color) * sc.flash * FLASH_K) if sc and sc.flash > 0 else np.zeros(3)
        p["u_flash"] = tuple(float(v) for v in flash)
        p["u_aberr"] = float(sc.aberration) if sc else 0.0
        p["u_radial"] = float(sc.radial) if sc else 0.0
        rc = sc.radial_center if sc else (self.w / 2, self.h / 2)
        p["u_rc"] = (rc[0] / self.w, 1.0 - rc[1] / self.h)
        p["u_bars"] = float(sc.bars) if sc else 0.0
        p["u_vignette"] = 0.18 + (0.3 * sc.dim if sc else 0.0)
        self.vao["combine"].render(moderngl.TRIANGLE_STRIP)
        # 8. интерфейс поверх (обычная альфа)
        if ui is not None:
            self._upload(self.tex_ui, ui)
            ctx.enable(moderngl.BLEND)
            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
            self.tex_ui.use(0)
            self.prog_ui["u_tex"] = 0
            self.prog_ui["u_flipv"] = 1.0
            self.vao["ui"].render(moderngl.TRIANGLE_STRIP)
            ctx.disable(moderngl.BLEND)
        if self.window:                        # 9. в окно: кадр растянут с сохранением пропорций, поля — цвета фона
            ctx.screen.use()
            sw, sh = self.window_size or ctx.screen.size
            ctx.viewport = (0, 0, sw, sh)
            ctx.screen.clear(T.BG[0] / 255, T.BG[1] / 255, T.BG[2] / 255, 1.0)
            x, y, w, h = self.view or (0, 0, self.w, self.h)
            self.out.use(0)
            self.prog_ui["u_tex"] = 0
            self.prog_ui["u_flipv"] = 0.0
            if (x, y, w, h) != (0, 0, sw, sh):
                # поля: приглушённый растянутый кадр — на ультрашироком экране не пусто, а «эмбиент»
                self.prog_ui["u_tint"] = (0.26, 0.28, 0.34, 1.0)
                self.vao["ui"].render(moderngl.TRIANGLE_STRIP)
            self.prog_ui["u_tint"] = (1.0, 1.0, 1.0, 1.0)
            ctx.viewport = (x, sh - y - h, w, h)
            self.vao["ui"].render(moderngl.TRIANGLE_STRIP)
        for unit in range(5):
            self.dummy.use(unit)

    def read(self):
        """Кадр внеэкранного буфера как pygame.Surface (для скриншотов и тестов)."""
        data = self.fbo_out.read(components=3)
        img = pygame.image.frombytes(data, (self.w, self.h), "RGB")
        return pygame.transform.flip(img, False, True)


_NOISE = None


def make_noise_cached():
    """Шум для шейдеров считается секунду — держим в памяти и на диске рядом с атласом."""
    global _NOISE
    if _NOISE is None:
        import os
        from ui.vfx_textures import BAKE_VERSION, CACHE_DIR
        path = os.path.join(CACHE_DIR, f"noise_v{BAKE_VERSION}.npy")
        if os.path.exists(path):
            _NOISE = np.load(path)
        else:
            _NOISE = make_noise()
            try:
                os.makedirs(CACHE_DIR, exist_ok=True)
                np.save(path, _NOISE)
            except OSError:
                pass
    return _NOISE
