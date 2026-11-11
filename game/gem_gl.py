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
uniform int u_n;
uniform mat3 u_rot;          // мир <- камень (Z мира — к зрителю, Y — вниз по экрану)
uniform vec2 u_size;         // пиксели
uniform float u_scale;       // пикселей на единицу камня
uniform vec3 u_absorb;       // поглощение (на единицу пути) по каналам
uniform vec3 u_tint;         // цвет тела камня
uniform float u_time;
uniform vec3 u_ior;

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

// цвет одного луча (камера ортографическая), канал ch; возвращает rgb (используется компонента ch) и попадание
vec4 trace(vec2 px) {
    vec3 ro = transpose(u_rot) * vec3((px - u_size * 0.5) / u_scale, 10.0);
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
    // кромка грани: близость второй плоскости
    float edge = 1e9;
    for (int i = 0; i < u_n; i++) {
        if (i == ein) continue;
        float d2 = u_pl[i].w - dot(p0, u_pl[i].xyz);
        float s = length(u_pl[i].xyz - N * dot(u_pl[i].xyz, N));
        if (s > 1e-3) edge = min(edge, d2 / s);
    }
    float edgeK = smoothstep(0.0, 1.6 / u_scale * 1.0, edge);
    vec3 col = vec3(0.0);
    vec3 Nw = u_rot * N;
    if (k > 0.5) {
        // матовая поверхность: рассеяние, сквозь неё внутренность камня светится тускло
        vec3 Ld = normalize(vec3(-0.5, -0.7, 0.6));
        float diff = max(dot(Nw, Ld), 0.0);
        vec3 base = (k < 1.5) ? mix(u_tint, vec3(1.0), 0.55) : (k < 2.5 ? u_tint * 0.55 + 0.08 : mix(u_tint, vec3(0.9), 0.35));
        float grain = hash(floor(p0 * u_scale * 0.7));
        float scratch = (k < 1.5) ? 0.9 + 0.2 * step(0.82, fract(dot(p0, normalize(vec3(1.0, 0.3, 0.6))) * u_scale * 0.22)) : 1.0;
        col = base * (0.28 + 0.72 * diff) * (0.85 + 0.3 * grain) * scratch;
        col += u_tint * 0.12;
        return vec4(col * mix(0.55, 1.0, edgeK), 1.0);
    }
    for (int ch = 0; ch < 3; ch++) {
        float ior = u_ior[ch];
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
            thr *= exp(-u_absorb[ch] * tmin);
            p += d * tmin;
            vec3 Nx = u_pl[j].xyz;
            if (u_kind[j] > 0.5) {               // матовая грань изнутри — свет рассеивается и гаснет
                acc += thr * 0.18 * (0.4 + 0.6 * u_tint[ch]);
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


def render(faces, to_world, size, scale, color, t=0.0, darkness=1.0):
    """Камень в поверхность size×size (предумноженная альфа: блит с BLEND_PREMULTIPLIED). None — нет GPU."""
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
    pl = np.zeros((MAXP, 4), np.float32)
    kd = np.zeros(MAXP, np.float32)
    k = 0
    for f in faces[:MAXP]:
        n = f["n"]
        pl[k] = (n[0], n[1], n[2], n[0] * f["pts"][0][0] + n[1] * f["pts"][0][1] + n[2] * f["pts"][0][2])
        kd[k] = KIND.get(f["kind"], 0.0)
        k += 1
    col = np.array(color[:3], np.float32) / 255.0
    tint = np.clip(col * 1.1, 0.05, 1.0)
    absorb = (1.0 - col) ** 1.4 * 0.016 * darkness + 0.0004   # на единицу пути (радиус камня ≈ 100)
    prog["u_pl"].write(pl.tobytes())
    prog["u_kind"].write(kd.tobytes())
    prog["u_n"].value = k
    prog["u_rot"].write(matrix(to_world).T.copy().tobytes())     # GLSL — по столбцам
    prog["u_size"].value = (float(w), float(h))
    prog["u_scale"].value = float(scale)
    prog["u_absorb"].value = tuple(float(x) for x in absorb)
    prog["u_tint"].value = tuple(float(x) for x in tint)
    prog["u_time"].value = float(t)
    prog["u_ior"].value = (2.38, 2.42, 2.47)
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


def blit(surf, img, center):
    """Блит предумноженной картинки камня по центру."""
    surf.blit(img, (center[0] - img.get_width() // 2, center[1] - img.get_height() // 2),
              special_flags=pygame.BLEND_PREMULTIPLIED)


def draw(surf, faces, to_world, center, scale, color, t=0.0, extent=None):
    """Трассировка в квадрат вокруг center (сторона — по размеру камня); False — нет GPU (рисуйте запасной путь)."""
    r = extent or max(math.sqrt(sum(c * c for c in p)) for f in faces for p in f["pts"])
    size = int(2 * r * scale + 8)
    img = render(faces, to_world, size, scale, color, t)
    if img is None:
        return False
    blit(surf, img, center)
    return True
