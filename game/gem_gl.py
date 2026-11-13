"""Самоцвет трассировкой лучей на видеокарте (moderngl): камень — выпуклый многогранник (до 128 плоскостей).
Каждый пиксель — 4 луча (сглаживание) × 3 длины волны (красный, зелёный, синий — свой показатель преломления,
отсюда «огонь»). Луч: вход (Френель: отражение окружения + преломление внутрь), до 7 внутренних отражений
с полным внутренним отражением, поглощение по пути (цвет камня, закон Бугера — Ламберта), выход с преломлением.
Матовые грани (сырой камень, свежая шлифовка, рундист) не пропускают свет зеркально — рассеивают его: недоогранённый
камень выглядит тусклым, огранённый — играет. Нет видеокарты — None (рисует полигональный запасной путь gem3d)."""
import math

import numpy as np
import pygame

MAXP = 128
KIND = {"polish": 0.0, "frost": 1.0, "rough": 2.0, "girdle": 3.0}

VS = """
#version 330
in vec2 in_pos;
out vec2 v_uv;
void main() { v_uv = in_pos * 0.5 + 0.5; gl_Position = vec4(in_pos, 0.0, 1.0); }
"""

FS = """
#version 330
in vec2 v_uv;
out vec4 f;
uniform vec4 u_pl[128];      // нормаль (в осях камня) и отступ
uniform float u_kind[128];   // 0 полировка, 1 свежая шлифовка, 2 сырой, 3 рундист
uniform float u_grit[128];   // шероховатость грани от диска: 1 — грубый (царапины), 0 — гладко
uniform int u_n;
uniform mat3 u_rot;          // мир <- камень (Z мира — к зрителю, Y — вниз по экрану)
uniform vec2 u_size;         // пиксели
uniform float u_scale;       // пикселей на единицу камня
uniform vec2 u_off;          // центр камня относительно центра кадра (лупа: окно вокруг точки)
uniform vec3 u_absorb;       // поглощение (на единицу пути) по каналам
uniform vec3 u_tint;         // цвет тела камня
uniform float u_time;
uniform vec3 u_ior;
uniform vec4 u_inc[16];      // примеси: центр и радиус (в осях камня)
uniform vec4 u_inck[16];     // вид (0 кристаллик, 1 пузырёк, 2 трещина, 3 облачко, 4 шёлк) и нормаль трещины
uniform int u_ninc;
uniform float u_star;        // астеризм (звёздный кабошон с шёлком)
uniform vec3 u_caxis;        // ось кристалла (в осях камня)
uniform vec4 u_dome;         // кабошон: радиус скругления кромок, -, -, вкл
// оттенки в объёме: окно камня в карте вида (sim/gems.py: field_t, pal_at) — p(мм) = A·p + b
uniform int u_cfon;
uniform mat3 u_cfA;
uniform vec3 u_cfb;
uniform vec4 u_wk[4];        // волны карты: k (1/мм), фаза
uniform vec4 u_wa;           // амплитуды волн
uniform vec2 u_cfg;          // усиление, резкость зон
uniform vec4 u_pal[6];       // палитра: цвет (0–1, с насыщенностью камня), t
uniform int u_npal;
uniform float u_dark;        // густота поглощения

vec3 env(vec3 d) {
    // студия огранщика: свод (светлее сверху), софтбоксы вокруг зрителя, кольцо ламп, окно, тёплый отсвет снизу;
    // прямо за зрителем — тёмная «голова» (так камень и выглядит контрастным, как в жизни)
    float up = clamp(-d.y, 0.0, 1.0);
    vec3 c = mix(vec3(0.06, 0.055, 0.06), vec3(0.42, 0.40, 0.40), up * up);
    float z = d.z;
    c += vec3(0.75, 0.72, 0.68) * smoothstep(0.3, 0.55, z) * (1.0 - smoothstep(0.88, 0.95, z));
    float az = atan(d.y, d.x) + u_time * 0.25;
    float ring = pow(max(0.0, cos(az * 6.0)), 30.0) * smoothstep(0.5, 0.7, z) * (1.0 - smoothstep(0.8, 0.88, z));
    float ring2 = pow(max(0.0, cos(az * 9.0 + 1.3)), 50.0) * smoothstep(0.82, 0.88, z) * (1.0 - smoothstep(0.93, 0.96, z));
    c += vec3(6.0, 5.8, 5.4) * ring + vec3(4.0, 4.2, 4.6) * ring2;
    float w = 0.15 * sin(u_time * 0.6);
    vec3 L1 = normalize(vec3(-0.55 + w, -0.75, 0.38));
    vec3 L2 = normalize(vec3(0.65, -0.55 + w, 0.50));
    vec3 L4 = normalize(vec3(-0.75, 0.25, 0.55));
    c += vec3(4.0, 3.6, 3.0) * pow(max(dot(d, L1), 0.0), 50.0);
    c += vec3(2.4, 2.8, 3.4) * pow(max(dot(d, L2), 0.0), 35.0);
    c += vec3(1.2, 0.8, 0.45) * pow(max(dot(d, L4), 0.0), 10.0);
    vec3 wd = normalize(vec3(0.45, -0.7, 0.55));
    float a = dot(d, wd);
    if (a > 0.93) {
        vec3 r = d - wd * a;
        if (abs(r.x) < 0.22 && abs(r.y) < 0.14 && (abs(r.x) > 0.012 && abs(r.y) > 0.012)) c += vec3(1.6, 1.7, 1.9);
    }
    c *= 1.0 - 0.85 * smoothstep(0.975, 0.995, z);   // голова зрителя
    return c;
}

float fresnel(float cosi, float n1, float n2) {
    float r0 = (n1 - n2) / (n1 + n2); r0 *= r0;
    return r0 + (1.0 - r0) * pow(1.0 - clamp(cosi, 0.0, 1.0), 5.0);
}

float hash(vec3 p) { return fract(sin(dot(p, vec3(12.9898, 78.233, 37.719))) * 43758.5453); }
float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1.0, 0.0)), f.x), mix(hash2(i + vec2(0.0, 1.0)), hash2(i + vec2(1.0)), f.x), f.y);
}
// карта высот грани после диска: штрихи вдоль хода диска + ямки зерна; грубее зерно — шире и глубже
float hmap(vec2 q, float grit) {
    float sc = mix(3.2, 1.1, grit);
    vec2 s = q * sc;
    float scratches = vnoise(vec2(s.x * 0.05, s.y * 2.4)) * 0.7 + vnoise(vec2(s.x * 0.12, s.y * 5.0)) * 0.3;
    float pits = vnoise(s * 1.3);
    return scratches + pits * 0.15;
}
vec3 rough_normal(vec3 N, vec3 p, float grit) {
    vec3 t1 = normalize(cross(N, abs(N.z) < 0.9 ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0)));
    vec3 t2 = cross(N, t1);
    vec2 q = vec2(dot(p, t1), dot(p, t2));
    float e = 0.12;
    float h0 = hmap(q, grit);
    vec2 g = vec2(hmap(q + vec2(e, 0.0), grit) - h0, hmap(q + vec2(0.0, e), grit) - h0) / e;
    g /= mix(3.2, 1.1, grit) * 2.4;            // наклон — от глубины штриха, не от частоты
    return normalize(N - (t1 * g.x + t2 * g.y) * grit * 0.32);
}
// видно ли штрихи при этом масштабе: период мельче пикселя — не рябь, а мутность грани
float grit_fade(float grit) {
    float per = 1.0 / (mix(3.2, 1.1, grit) * 2.4);
    return smoothstep(1.2, 4.0, per * u_scale);
}

float fieldT(vec3 p) {
    vec3 q = u_cfA * p + u_cfb;
    float s = 0.0;
    for (int i = 0; i < 4; i++) s += u_wa[i] * sin(dot(u_wk[i].xyz, q) + u_wk[i].w);
    float t = 0.5 + 0.5 * s / (u_wa.x + u_wa.y + u_wa.z + u_wa.w) * u_cfg.x;
    t = 0.5 + 0.5 * tanh(u_cfg.y * (t - 0.5) * 2.0) / tanh(u_cfg.y);
    return clamp(t, 0.0, 1.0);
}
vec3 palAt(float t) {
    vec3 c = u_pal[0].rgb;
    for (int i = 1; i < 6; i++) {
        if (i >= u_npal) break;
        float t0 = u_pal[i - 1].w, t1 = u_pal[i].w;
        if (t >= t0) c = mix(u_pal[i - 1].rgb, u_pal[i].rgb, clamp((t - t0) / max(t1 - t0, 1e-4), 0.0, 1.0));
    }
    return c;
}
vec3 tintAt(vec3 p) { return u_cfon > 0 ? clamp(palAt(fieldT(p)) * 1.1, 0.05, 1.0) : u_tint; }
vec3 absorbAt(vec3 p) {
    if (u_cfon == 0) return u_absorb;
    vec3 c = palAt(fieldT(p));
    return pow(1.0 - c, vec3(1.4)) * 0.016 * u_dark + 0.0004;
}

// примеси на отрезке пути внутри камня: гасят и рассеивают свет (acc — накопленный свет канала, thr — остаток)
void inclusions(vec3 p, vec3 d, float tmax, int ch, inout float acc, inout float thr) {
    for (int q = 0; q < u_ninc; q++) {
        vec3 c = u_inc[q].xyz;
        float r = u_inc[q].w;
        float kq = u_inck[q].x;
        vec3 oc = p - c;
        float b = dot(oc, d);
        float disc = b * b - (dot(oc, oc) - r * r);
        if (disc <= 0.0) continue;
        float sq = sqrt(disc);
        float t0 = max(-b - sq, 0.0), t1 = min(-b + sq, tmax);
        if (t1 <= t0) continue;
        float chord = t1 - t0;
        if (kq < 0.5) {                       // кристаллик: тёмное тело с искрой
            float edge = 1.0 - chord / (2.0 * r);
            acc += thr * (0.03 + 0.25 * edge * edge);
            thr *= 0.1;
        } else if (kq < 1.5) {                // пузырёк: светлый ободок, середина прозрачна
            float rim = pow(1.0 - chord / (2.0 * r), 3.0);
            acc += thr * 0.45 * rim;
            thr *= 1.0 - 0.6 * rim;
        } else if (kq < 2.5) {                // трещина: блестящий диск
            vec3 n = u_inck[q].yzw;
            float dn = dot(d, n);
            if (abs(dn) > 1e-4) {
                float tp = dot(c - p, n) / dn;
                if (tp > 0.0 && tp < tmax && length(p + d * tp - c) < r) {
                    float shine = pow(abs(dn), 0.5);
                    acc += thr * (0.18 + 0.4 * shine * env(u_rot * reflect(d, n))[ch] * 0.5);
                    thr *= 0.45;
                }
            }
        } else if (kq < 3.5) {                // облачко: туман
            float a = 1.0 - exp(-chord * 0.05);
            acc += thr * a * 0.55;
            thr *= 1.0 - a * 0.85;
        } else {                              // шёлк: иглы рутила (3 направления поперёк оси кристалла)
            float dens = u_inck[q].y;
            vec3 ax = normalize(u_caxis);
            vec3 a0 = normalize(cross(ax, abs(ax.x) < 0.9 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0)));
            vec3 a1 = cross(ax, a0);
            float w = 0.15 * sin(u_time * 0.6);
            vec3 L1 = transpose(u_rot) * normalize(vec3(-0.55 + w, -0.75, 0.38));   // лампы — в осях камня
            vec3 L2 = transpose(u_rot) * normalize(vec3(0.65, -0.55 + w, 0.50));
            float sc = 0.0;
            for (int n = 0; n < 3; n++) {
                float an = 1.0471976 * float(n);
                vec3 ai = a0 * cos(an) + a1 * sin(an);
                float e1 = dot(d, ai) - dot(L1, ai);     // игла отражает свет конусом: угол с иглой сохраняется
                float e2 = dot(d, ai) - dot(L2, ai);
                vec3 c1 = vec3(4.0, 3.6, 3.0), c2 = vec3(2.4, 2.8, 3.4);
                sc += exp(-e1 * e1 / 0.00025) * c1[ch] + exp(-e2 * e2 / 0.00025) * c2[ch] * 0.25;
            }
            float a = 1.0 - exp(-chord * 0.008 * dens);
            acc += thr * a * (0.2 + 1.1 * sc);
            thr *= 1.0 - a * 0.6;
        }
    }
}

// цвет одного луча (камера ортографическая), канал ch; возвращает rgb (используется компонента ch) и попадание
vec4 trace(vec2 px) {
    vec3 ro = transpose(u_rot) * vec3((px - u_size * 0.5 - u_off) / u_scale, 10.0);
    vec3 rd = transpose(u_rot) * vec3(0.0, 0.0, -1.0);
    float tin = -1e9, tout = 1e9; int ein = -1;
    for (int i = 0; i < u_n; i++) {
        vec3 n = u_pl[i].xyz;
        float dn = dot(rd, n);
        float dist = u_pl[i].w - dot(ro, n);
        if (abs(dn) < 1e-6) { if (dist < 0.0) return vec4(0.0); continue; }
        float t = dist / dn;
        if (dn < 0.0) { if (t > tin) { tin = t; ein = i; } }
        else { if (t < tout) tout = t; }
    }
    if (ein < 0 || tin >= tout) return vec4(0.0);
    vec3 p0 = ro + rd * tin;
    vec3 N = u_pl[ein].xyz;
    float k = u_kind[ein];
    bool smooth_dome = u_dome.w > 0.5 && N.z < -0.05;
    if (smooth_dome) {                        // кабошон: кромки собственных граней скруглены (форма — игрока)
        vec3 sn = N;
        for (int i = 0; i < u_n; i++) {
            vec3 ni = u_pl[i].xyz;
            if (i == ein || ni.z > -0.05) continue;
            float dd = u_pl[i].w - dot(p0, ni);
            sn += ni * exp(-max(dd, 0.0) / u_dome.x);
        }
        N = normalize(sn);
    }
    // кромка грани: близость второй плоскости
    float edge = 1e9;
    for (int i = 0; i < u_n; i++) {
        if (i == ein) continue;
        float d2 = u_pl[i].w - dot(p0, u_pl[i].xyz);
        float s = length(u_pl[i].xyz - N * dot(u_pl[i].xyz, N));
        if (s > 1e-3) edge = min(edge, d2 / s);
    }
    float edgeK = smooth_dome ? 1.0 : smoothstep(0.0, 1.6 / u_scale * 1.0, edge);
    float gr = u_grit[ein];
    float gfade = grit_fade(gr);
    if (gr > 0.01 && gfade > 0.01) N = rough_normal(N, p0, gr * gfade);   // рельеф от диска (под лупой)
    float haze = (k < 0.5) ? gr * (1.0 - gfade) : 0.0;                    // издали — мутность
    vec3 col = vec3(0.0);
    vec3 Nw = u_rot * N;
    if (k > 0.5) {
        // матовая поверхность: рассеяние, сквозь неё внутренность камня светится тускло
        vec3 Ld = normalize(vec3(-0.5, -0.7, 0.6));
        float diff = max(dot(Nw, Ld), 0.0);
        // свежая шлифовка: чем грубее зерно, тем белее и шершавее (тонкий диск — почти прозрачно-серая)
        float fw = (k < 1.5) ? 0.2 + 0.45 * max(gr, 0.05) : 0.55;
        vec3 tn = tintAt(p0);                 // цвет тела в этом месте (разноцветный камень — по карте)
        vec3 base = (k < 1.5) ? mix(tn, vec3(1.0), fw) : (k < 2.5 ? tn * 0.55 + 0.08 : mix(tn, vec3(0.9), 0.35));
        float grain = (k < 1.5) ? 1.0 : 0.85 + 0.3 * hash(floor(p0 * u_scale * 0.7));
        col = base * (0.28 + 0.72 * diff) * grain;
        col += tn * 0.12;
        return vec4(col * mix(0.55, 1.0, edgeK), 1.0);
    }
    for (int ch = 0; ch < 3; ch++) {
        float ior = mix(u_ior[ch], u_ior.y, clamp(gr * 1.5, 0.0, 1.0));   // шершавая грань — без «огня»
        float cosi = -dot(rd, N);
        float F = fresnel(cosi, 1.0, ior);
        float acc = F * env(u_rot * reflect(rd, N))[ch];
        vec3 d = refract(rd, N, 1.0 / ior);
        vec3 p = p0 + d * 1e-4;
        float thr = 1.0 - F;
        for (int b = 0; b < 7; b++) {
            float tmin = 1e9; int j = -1;
            for (int i = 0; i < u_n; i++) {
                float dn = dot(d, u_pl[i].xyz);
                if (dn > 1e-6) {
                    float t = (u_pl[i].w - dot(p, u_pl[i].xyz)) / dn;
                    if (t < tmin) { tmin = t; j = i; }
                }
            }
            if (j < 0) break;
            if (u_ninc > 0) inclusions(p, d, tmin, ch, acc, thr);
            vec3 ab = u_absorb;
            if (u_cfon > 0)                          // оттенок меняется по пути луча: три пробы
                ab = (absorbAt(p + d * tmin * 0.17) + absorbAt(p + d * tmin * 0.5) + absorbAt(p + d * tmin * 0.83)) / 3.0;
            thr *= exp(-ab[ch] * tmin);
            p += d * tmin;
            vec3 Nx = u_pl[j].xyz;
            if (u_grit[j] > 0.01) Nx = rough_normal(Nx, p, u_grit[j] * grit_fade(u_grit[j]));   // выход сквозь грань
            if (u_kind[j] > 0.5) {               // матовая грань изнутри — свет рассеивается и гаснет
                acc += thr * 0.18 * (0.4 + 0.6 * tintAt(p)[ch]);
                thr = 0.0;
                break;
            }
            float ci = dot(d, Nx);
            float s2 = ior * ior * (1.0 - ci * ci);
            if (s2 >= 1.0) {                     // полное внутреннее отражение
                d = reflect(d, Nx);
            } else {
                float Fx = fresnel(ci, ior, 1.0);
                vec3 out_d = refract(d, Nx, ior);
                acc += thr * (1.0 - Fx) * env(u_rot * out_d)[ch];
                thr *= Fx;
                d = reflect(d, Nx);
            }
            p += d * 1e-4;
            if (thr < 0.01) break;
        }
        acc += thr * 0.05;
        col[ch] = acc;
    }
    col = mix(col, mix(tintAt(p0), vec3(1.0), 0.45) * 0.5, haze * 0.75);   // шершавая грань издали — матовая дымка
    col *= mix(0.6, 1.0, edgeK);
    return vec4(col, 1.0);
}

void main() {
    vec2 px = v_uv * u_size;
    vec4 s = vec4(0.0);
    s += trace(px + vec2(-0.25, -0.25));
    s += trace(px + vec2(0.25, -0.25));
    s += trace(px + vec2(-0.25, 0.25));
    s += trace(px + vec2(0.25, 0.25));
    s *= 0.25;
    vec3 c = s.rgb / max(s.a, 1e-4);
    c *= 1.35;
    c = c / (1.0 + c * 0.45);                 // мягкое тональное сжатие ярких бликов
    c = pow(c, vec3(1.0 / 1.15));
    f = vec4(c * s.a, s.a);                    // предумноженная альфа
}
"""

_STATE = {"ctx": None, "failed": False}


def _ctx():
    if _STATE["failed"]:
        return None
    if _STATE["ctx"] is None:
        try:
            import moderngl
            try:
                ctx = moderngl.get_context()          # контекст окна игры (ui/present.py), если он есть
            except Exception:
                ctx = moderngl.create_standalone_context()
            prog = ctx.program(vertex_shader=VS, fragment_shader=FS)
            quad = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], np.float32).tobytes())
            vao = ctx.vertex_array(prog, [(quad, "2f", "in_pos")])
            _STATE.update(ctx=ctx, prog=prog, vao=vao, fbos={})
        except Exception as exc:                       # нет видеокарты / драйвера — запасной путь
            print(f"Самоцвет без трассировки ({exc})")
            _STATE["failed"] = True
            return None
    return _STATE["ctx"]


def available():
    return _ctx() is not None


def matrix(to_world):
    """3×3 мир <- камень по линейному отображению to_world."""
    cols = [to_world(e) for e in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))]
    return np.array(cols, np.float32).T


def _set(prog, name, value=None, data=None):
    try:
        if data is not None:
            prog[name].write(data)
        else:
            prog[name].value = value
    except KeyError:                                  # униформа выброшена компилятором — не нужна
        pass


def stone_uniforms(prog, faces, color, darkness=1.0, incl=None, star=0.0, axis=None, dome=None, cfield=None):
    """Камень в униформы шейдера (плоскости граней, вид грани, царапины, цвет и поглощение, примеси, звезда,
    купол, карта оттенков). → число граней."""
    pl = np.zeros((MAXP, 4), np.float32)
    kd = np.zeros(MAXP, np.float32)
    gr = np.zeros(MAXP, np.float32)
    k = 0
    for f in faces[:MAXP]:
        n = f["n"]
        pl[k] = (n[0], n[1], n[2], n[0] * f["pts"][0][0] + n[1] * f["pts"][0][1] + n[2] * f["pts"][0][2])
        kd[k] = KIND.get(f["kind"], 0.0)
        gr[k] = f.get("grit", 0.0)
        k += 1
    if dome or getattr(faces, "dome", None):        # кабошон: густое полупрозрачное тело
        darkness *= 3.5
    col = np.array(color[:3], np.float32) / 255.0
    tint = np.clip(col * 1.1, 0.05, 1.0)
    absorb = (1.0 - col) ** 1.4 * 0.016 * darkness + 0.0004   # на единицу пути (радиус камня ≈ 100)
    _set(prog, "u_pl", data=pl.tobytes())
    _set(prog, "u_kind", data=kd.tobytes())
    _set(prog, "u_grit", data=gr.tobytes())
    _set(prog, "u_n", k)
    _set(prog, "u_absorb", tuple(float(x) for x in absorb))
    _set(prog, "u_tint", tuple(float(x) for x in tint))
    _set(prog, "u_ior", (2.38, 2.42, 2.47))
    inc = np.zeros((16, 4), np.float32)
    ink = np.zeros((16, 4), np.float32)
    kinds = {"crystal": 0.0, "bubble": 1.0, "feather": 2.0, "cloud": 3.0, "silk": 4.0}
    m = 0
    for i in (incl or [])[:16]:
        inc[m] = (i["p"][0], i["p"][1], i["p"][2], i["r"])
        n = i.get("n") or (0.0, 0.0, 1.0)
        if i["k"] == "silk":                       # шёлк: в .y — густота игл
            n = (i.get("d", 0.6), 0.0, 0.0)
        ink[m] = (kinds.get(i["k"], 0.0), n[0], n[1], n[2])
        m += 1
    _set(prog, "u_inc", data=inc.tobytes())
    _set(prog, "u_inck", data=ink.tobytes())
    _set(prog, "u_ninc", m)
    _set(prog, "u_star", float(star or 0.0))
    _set(prog, "u_caxis", tuple(float(x) for x in (axis or (0.0, 0.0, 1.0))))
    _set_cfield(prog, cfield, color, darkness)
    dome = dome or getattr(faces, "dome", None)
    _set(prog, "u_dome", (float(dome[0]), float(dome[1]), float(dome[2]), 1.0) if dome else (1.0, 1.0, 0.0, 0.0))
    return k


def render(faces, to_world, size, scale, color, t=0.0, darkness=1.0, incl=None, star=0.0, axis=None, dome=None,
           offset=(0.0, 0.0), cfield=None):
    """Камень в поверхность size×size (предумноженная альфа: блит с BLEND_PREMULTIPLIED). None — нет GPU.
    incl — примеси [{"k", "p", "r", "n"}] в осях камня; star — сила звезды, axis — ось кристалла."""
    ctx = _ctx()
    if ctx is None or not faces:
        return None
    import moderngl
    prog = _STATE["prog"]
    fbos = _STATE["fbos"]
    w = h = int(size)
    if (w, h) not in fbos:
        tex = ctx.texture((w, h), 4)
        fbos[(w, h)] = ctx.framebuffer(color_attachments=[tex])
    fbo = fbos[(w, h)]
    k = stone_uniforms(prog, faces, color, darkness, incl, star, axis, dome, cfield)
    prog["u_rot"].write(matrix(to_world).T.copy().tobytes())     # GLSL — по столбцам
    prog["u_size"].value = (float(w), float(h))
    prog["u_scale"].value = float(scale)
    _set(prog, "u_off", (float(offset[0]), float(offset[1])))
    prog["u_time"].value = float(t)
    prev = ctx.fbo
    prev_vp = ctx.viewport
    fbo.use()
    ctx.viewport = (0, 0, w, h)
    ctx.disable(moderngl.BLEND)
    fbo.clear(0.0, 0.0, 0.0, 0.0)
    _STATE["vao"].render(moderngl.TRIANGLE_STRIP)
    data = fbo.read(components=4)
    try:
        prev.use()
        ctx.viewport = prev_vp
    except Exception:
        pass
    # строка 0 буфера — низ кадра GL, а в шейдере v_uv.y = 0 — верх мира (Y мира — вниз): переворот не нужен
    img = pygame.image.frombuffer(data, (w, h), "RGBA").copy()
    return img.convert_alpha() if pygame.display.get_surface() else img


def _set_cfield(prog, cf, color, darkness):
    """Окно в карте оттенков вида: A (3×3, строки), b (мм), волны и палитра с насыщенностью камня."""
    if not cf:
        _set(prog, "u_cfon", 0)
        return
    from sim import gems as GM
    gid = cf["gid"]
    cm = GM.color_map(gid)
    A = np.array(cf["A"], np.float32).reshape(3, 3)
    _set(prog, "u_cfon", 1)
    _set(prog, "u_cfA", data=A.T.copy().tobytes())          # GLSL — по столбцам
    _set(prog, "u_cfb", tuple(float(v) for v in cf["b"]))
    wk = np.array([list(w) for w in GM.waves(gid)], np.float32)
    _set(prog, "u_wk", data=wk.tobytes())
    _set(prog, "u_wa", tuple(float(a) for a in GM.WAVE_AMPS))
    _set(prog, "u_cfg", (float(cm["gain"]), float(cm["sharp"])))
    pal = np.zeros((6, 4), np.float32)
    for i, (t, rgb, _, _) in enumerate(cm["pal"][:6]):
        c = GM.tint(rgb, cf.get("col", 0.5))
        pal[i] = (c[0] / 255, c[1] / 255, c[2] / 255, t)
    _set(prog, "u_pal", data=pal.tobytes())
    _set(prog, "u_npal", min(6, len(cm["pal"])))
    _set(prog, "u_dark", float(darkness))


def blit(surf, img, center):
    """Блит предумноженной картинки камня по центру."""
    surf.blit(img, (center[0] - img.get_width() // 2, center[1] - img.get_height() // 2),
              special_flags=pygame.BLEND_PREMULTIPLIED)


def draw(surf, faces, to_world, center, scale, color, t=0.0, extent=None, incl=None, star=0.0, axis=None, cfield=None):
    """Трассировка в квадрат вокруг center (сторона — по размеру камня); False — нет GPU (рисуйте запасной путь)."""
    r = extent or max(math.sqrt(sum(c * c for c in p)) for f in faces for p in f["pts"])
    size = int(2 * r * scale + 8)
    img = render(faces, to_world, size, scale, color, t, incl=incl, star=star, axis=axis, cfield=cfield)
    if img is None:
        return False
    blit(surf, img, center)
    return True
