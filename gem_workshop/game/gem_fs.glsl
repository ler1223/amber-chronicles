#version 330

in vec2 v_uv;
out vec4 f;

// ---- геометрия камня: выпуклый многогранник ----
uniform vec4 u_pl[128];      // нормаль (оси камня) и отступ
uniform float u_kind[128];   // 0 полировка, 1 шлифовка, 2 сырьё, 3 рундист
uniform float u_grit[128];   // микрорельеф грани 0..1
uniform int u_n;
uniform mat3 u_rot;          // мир <- камень
uniform vec2 u_size;
uniform float u_scale;
uniform vec2 u_off;

// ---- материал ----
uniform vec3 u_absorb;
uniform vec3 u_tint;
uniform vec3 u_ior;
uniform float u_trans;
uniform float u_dark;
uniform float u_time;

// ---- включения ----
uniform vec4 u_inc[16];      // центр, радиус
uniform vec4 u_inck[16];     // тип, нормаль/плотность
uniform float u_incsurf[16]; // 1 — включение выходит на поверхность
uniform int u_ninc;

// ---- карта цвета ----
uniform int u_cfon;
uniform mat3 u_cfA;
uniform vec3 u_cfb;
uniform vec4 u_wk[4];
uniform vec4 u_wa;
uniform vec2 u_cfg;
uniform vec4 u_pal[6];
uniform int u_npal;

// ---- свет ----
// Фонарик живёт в осях камня. Это важно: при повороте камня луч остаётся
// мировым светом, а не «приклеенным» к экрану.
uniform vec3 u_lpos;
uniform vec3 u_ldir;         // направление, куда светит фонарик (нормализовано)
uniform vec3 u_lcol;         // линейный цвет
uniform float u_lint;
uniform float u_lcos;        // косинус внешнего угла конуса
uniform float u_lsoft;       // мягкость края конуса
uniform float u_ltan;        // тангенс половины угла — для объёмного луча
uniform float u_lref;        // опорная дистанция inverse-square
uniform float u_lon;         // 0/1
uniform float u_env;         // множитель окружающего света

// ---- поверхность ----
uniform float u_rough;       // базовая шероховатость 0..1
uniform float u_dirt;        // загрязнение/плёнка 0..1
uniform float u_film;        // толщина плёнки / мутность
uniform float u_damage;      // нарушенный слой 0..1
uniform float u_polish;      // качество полировки 0..1
uniform float u_wet;         // вода/масло 0..1
uniform float u_scratches;   // царапины 0..1
uniform float u_pleo;        // сила плеохроизма
uniform float u_biref;       // двупреломление (для визуального разделения)
uniform vec3 u_opaxis;       // оптическая ось
uniform float u_star;
uniform vec3 u_caxis;
uniform vec4 u_dome;

const float PI = 3.14159265359;

// ============================================================
//  Шум только для НИЗКОЧАСТОТНОЙ грязи. Никакого «меха»:
//  микрорельеф задаётся BSDF, а не высокочастотной нормалью.
// ============================================================
float hash21(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash21(i), hash21(i + vec2(1.0, 0.0)), f.x),
               mix(hash21(i + vec2(0.0, 1.0)), hash21(i + vec2(1.0, 1.0)), f.x), f.y);
}

float dirt_pattern(vec3 p) {
    vec2 q = vec2(p.x + p.z * 0.7, p.y - p.z * 0.4) * 0.045;
    float a = vnoise(q);
    float b = vnoise(q * 2.1 + 7.3);
    float c = vnoise(q * 0.47 + 1.7);
    return clamp(0.18 + 0.55 * a + 0.18 * b + 0.09 * c, 0.0, 1.0);
}

// ============================================================
//  Окружение: тёмная студия, мягкие источники, никакого
//  равномерного «мультяшного» залива.
// ============================================================
vec3 env(vec3 d) {
    float up = clamp(-d.y, 0.0, 1.0);
    vec3 c = mix(vec3(0.025, 0.022, 0.025), vec3(0.23, 0.22, 0.23), up * up);
    float z = d.z;
    c += vec3(0.55, 0.52, 0.48) * smoothstep(0.35, 0.60, z) * (1.0 - smoothstep(0.88, 0.96, z));
    float az = atan(d.y, d.x) + u_time * 0.12;
    float ring = pow(max(0.0, cos(az * 6.0)), 30.0) * smoothstep(0.55, 0.72, z) * (1.0 - smoothstep(0.82, 0.90, z));
    float ring2 = pow(max(0.0, cos(az * 9.0 + 1.3)), 50.0) * smoothstep(0.82, 0.88, z) * (1.0 - smoothstep(0.93, 0.97, z));
    c += vec3(2.6, 2.5, 2.3) * ring + vec3(1.8, 1.9, 2.1) * ring2;
    float w = 0.15 * sin(u_time * 0.35);
    vec3 L1 = normalize(vec3(-0.55 + w, -0.75, 0.38));
    vec3 L2 = normalize(vec3(0.65, -0.55 + w, 0.50));
    vec3 L4 = normalize(vec3(-0.75, 0.25, 0.55));
    c += vec3(2.2, 2.0, 1.7) * pow(max(dot(d, L1), 0.0), 60.0);
    c += vec3(1.3, 1.5, 1.8) * pow(max(dot(d, L2), 0.0), 45.0);
    c += vec3(0.55, 0.38, 0.22) * pow(max(dot(d, L4), 0.0), 12.0);
    vec3 wd = normalize(vec3(0.45, -0.7, 0.55));
    float a = dot(d, wd);
    if (a > 0.94) {
        vec3 r = d - wd * a;
        if (abs(r.x) < 0.22 && abs(r.y) < 0.14 && (abs(r.x) > 0.012 && abs(r.y) > 0.012))
            c += vec3(1.1, 1.2, 1.3);
    }
    c *= 1.0 - 0.85 * smoothstep(0.975, 0.995, z);
    return c * u_env;
}

// ============================================================
//  Оптика
// ============================================================
// Точный френель для неполяризованного света (среднее s- и p-компонент).
// Для TIR возвращает 1.0; это важно для павильона и критического угла.
float fresnel(float cosi, float n1, float n2) {
    cosi = clamp(cosi, 0.0, 1.0);
    float eta = n1 / max(n2, 1e-4);
    float sint2 = eta * eta * (1.0 - cosi * cosi);
    if (sint2 >= 1.0) return 1.0;
    float cost = sqrt(max(0.0, 1.0 - sint2));
    float rs = (n1 * cosi - n2 * cost) / (n1 * cosi + n2 * cost + 1e-5);
    float rp = (n1 * cost - n2 * cosi) / (n1 * cost + n2 * cosi + 1e-5);
    return 0.5 * (rs * rs + rp * rp);
}

float D_GGX(float NoH, float a) {
    float a2 = a * a;
    float d = NoH * NoH * (a2 - 1.0) + 1.0;
    return a2 / (PI * d * d + 1e-5);
}

float G_Schlick(float NoV, float k) {
    return NoV / (NoV * (1.0 - k) + k + 1e-5);
}

float G_Smith(float NoV, float NoL, float a) {
    float k = a * 0.5;
    return G_Schlick(NoV, k) * G_Schlick(NoL, k);
}

// Возвращает зеркальную часть для одного канала. rough — perceptual roughness.
float specular_ggx(vec3 N, vec3 V, vec3 L, float rough, float F0) {
    vec3 H = normalize(V + L);
    float NoH = max(dot(N, H), 0.0);
    float NoV = max(dot(N, V), 1e-4);
    float NoL = max(dot(N, L), 1e-4);
    float VoH = max(dot(V, H), 0.0);
    float a = max(0.02, rough * rough);
    float D = D_GGX(NoH, a);
    float G = G_Smith(NoV, NoL, a);
    float F = F0 + (1.0 - F0) * pow(1.0 - VoH, 5.0);
    return D * G * F / (4.0 * NoV * NoL + 1e-4);
}

// ============================================================
//  Три студийных источника вокруг камня.
//  Они не «подсветка фона», а физические точки в мире: ключевой,
//  заполняющий и контровой. Поэтому камень не проваливается в чёрное
//  пятно, даже когда фонарик выключен.
// ============================================================
vec3 studio_pos(int i) {
    if (i == 0) return vec3(-260.0, -170.0, 330.0);   // ключевой, слева-снизу
    if (i == 1) return vec3( 300.0, -120.0, 260.0);   // заполняющий, справа
    return vec3(  20.0,  280.0, -230.0);               // контровой, сверху-сзади
}

vec3 studio_col(int i) {
    if (i == 0) return vec3(1.00, 0.82, 0.62);         // тёплый
    if (i == 1) return vec3(0.62, 0.78, 1.00);         // холодный
    return vec3(0.88, 0.92, 1.00);                     // нейтральный
}

float studio_power(int i) {
    if (i == 0) return 2.4;
    if (i == 1) return 1.55;
    return 1.8;
}

vec3 studio_light_rgb(vec3 p, vec3 N, vec3 V, float rough, vec3 albedo) {
    vec3 outC = vec3(0.0);
    for (int i = 0; i < 3; i++) {
        // Мировые координаты → оси камня.
        vec3 lp = transpose(u_rot) * studio_pos(i);
        vec3 Lv = lp - p;
        float dist = length(Lv);
        if (dist < 1e-3) continue;
        vec3 L = Lv / dist;
        float NoL = max(dot(N, L), 0.0);
        if (NoL <= 0.0) continue;
        float att = (420.0 * 420.0) / (dist * dist + 420.0 * 420.0 * 0.10);
        vec3 F0 = vec3(fresnel(1.0, 1.0, u_ior.r),
                       fresnel(1.0, 1.0, u_ior.g),
                       fresnel(1.0, 1.0, u_ior.b));
        vec3 spec = vec3(specular_ggx(N, V, L, rough, F0.r),
                         specular_ggx(N, V, L, rough, F0.g),
                         specular_ggx(N, V, L, rough, F0.b));
        // У грубой/грязной поверхности нет чистого зеркального блика.
        spec *= 1.0 - smoothstep(0.15, 0.55, rough);
        vec3 diff = albedo * (NoL / PI) * (vec3(1.0) - F0);
        outC += studio_col(i) * studio_power(i) * att * (diff + spec);
    }
    return outC;
}

// ============================================================
//  Фонарик
// ============================================================
float flash_at(vec3 p) {
    if (u_lon < 0.5) return 0.0;
    vec3 rel = p - u_lpos;
    float dist = length(rel);
    if (dist < 1e-3) return 0.0;
    vec3 dir = rel / dist;
    float cone = smoothstep(u_lcos - u_lsoft, u_lcos + u_lsoft, dot(dir, normalize(u_ldir)));
    float att = (u_lref * u_lref) / (dist * dist + 1.0);
    return u_lint * cone * att;
}

// Свет внутри объёма: приближение луча как конуса. Он нужен для
// рассеяния на включениях и для «свечения» камня изнутри.
float flash_entry(vec3 p);
float flash_inside(vec3 p) {
    if (u_lon < 0.5) return 0.0;
    vec3 rel = p - u_lpos;
    float along = dot(rel, normalize(u_ldir));
    if (along <= 0.0) return 0.0;
    vec3 perp = rel - normalize(u_ldir) * along;
    float radius = max(1.0, along * u_ltan);
    float spot = exp(-dot(perp, perp) / max(1.0, radius * radius * 0.75));
    float att = (u_lref * u_lref) / (along * along + u_lref * u_lref * 0.08);
    return u_lint * spot * att * 0.55 + flash_entry(p) * 0.75;
}

// Свет, который реально входит в камень через грань. В отличие от
// «конуса в вакууме», здесь учитывается точка входа, нормаль грани,
// френелевское пропускание и оптическая толщина до точки рассеяния.
float flash_entry(vec3 p) {
    if (u_lon < 0.5) return 0.0;
    vec3 toL = u_lpos - p;
    float dist = length(toL);
    if (dist < 1e-3) return 0.0;
    vec3 dir = toL / dist;
    float tmin = 1e9;
    int j = -1;
    for (int i = 0; i < u_n; i++) {
        float dn = dot(dir, u_pl[i].xyz);
        if (dn > 1e-6) {
            float t = (u_pl[i].w - dot(p, u_pl[i].xyz)) / dn;
            if (t > 1e-4 && t < tmin) { tmin = t; j = i; }
        }
    }
    if (j < 0) return 0.0;
    vec3 q = p + dir * tmin;
    vec3 Nq = u_pl[j].xyz;
    float cosi = clamp(abs(dot(dir, Nq)), 0.0, 1.0);
    float T = 1.0 - fresnel(cosi, 1.0, u_ior.y);
    float beam = flash_at(q);
    float path = exp(-max(0.0, tmin) * u_absorb.y * 0.55);
    return beam * T * path;
}

vec3 flash_color(float v) {
    return u_lcol * v;
}

// ============================================================
//  Цвет и поглощение
// ============================================================
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

vec3 tintAt(vec3 p) {
    return u_cfon > 0 ? clamp(palAt(fieldT(p)) * 1.1, 0.05, 1.0) : u_tint;
}

// Плеохроизм: цвет зависит от направления луча и оптической оси.
// Это не «перекраска», а модуляция поглощения по двум направлениям.
vec3 pleoTint(vec3 d) {
    if (u_pleo < 0.01) return vec3(1.0);
    vec3 ax = normalize(u_opaxis + vec3(1e-5));
    float a = 0.5 + 0.5 * dot(normalize(d), ax);
    vec3 A = vec3(1.0 + u_pleo * 0.36, 1.0 - u_pleo * 0.16, 1.0 - u_pleo * 0.26);
    vec3 B = vec3(1.0 - u_pleo * 0.22, 1.0 + u_pleo * 0.30, 1.0 + u_pleo * 0.12);
    return clamp(mix(A, B, a), 0.35, 1.65);
}

vec3 absorbAt(vec3 p) {
    if (u_cfon == 0) return u_absorb;
    vec3 c = palAt(fieldT(p));
    return pow(1.0 - c, vec3(1.4)) * 0.016 * u_dark + 0.0004;
}

// ============================================================
//  Включения как объёмные рассеиватели
// ============================================================
void inclusions(vec3 p, vec3 d, float tmax, int ch, inout float acc, inout float thr, float beam) {
    if (u_lon < 0.5 || beam <= 0.0) return;
    for (int q = 0; q < u_ninc; q++) {
        vec3 c = u_inc[q].xyz;
        float r = u_inc[q].w;
        float kq = u_inck[q].x;
        vec3 oc = p - c;
        float b = dot(oc, d);
        float disc = b * b - (dot(oc, oc) - r * r);
        if (disc <= 0.0) continue;
        float sq = sqrt(disc);
        float t0 = max(-b - sq, 0.0);
        float t1 = min(-b + sq, tmax);
        if (t1 <= t0) continue;
        float chord = t1 - t0;
        float lit = beam * u_lcol[ch] * 4.5;
        float surf = u_incsurf[q];

        if (kq < 0.5) {
            // Кристаллик: тёмное тело, яркие сколы по краям.
            float edge = 1.0 - chord / (2.0 * r + 1e-5);
            acc += thr * lit * (0.18 + 2.2 * edge * edge);
            thr *= 0.10;
        } else if (kq < 1.5) {
            // Пузырёк: яркий ободок, прозрачная середина.
            float rim = pow(max(0.0, 1.0 - chord / (2.0 * r + 1e-5)), 3.0);
            acc += thr * lit * 2.2 * rim;
            thr *= 1.0 - 0.65 * rim;
        } else if (kq < 2.5) {
            // Перо/трещина: тонкая блестящая плоскость.
            vec3 n = normalize(u_inck[q].yzw + vec3(1e-5));
            float dn = dot(d, n);
            if (abs(dn) > 1e-4) {
                float tp = dot(c - p, n) / dn;
                if (tp > 0.0 && tp < tmax && length(p + d * tp - c) < r) {
                    float shine = pow(abs(dn), 0.5);
                    acc += thr * lit * (0.30 + 1.2 * shine);
                    thr *= 0.45;
                }
            }
        } else if (kq < 3.5) {
            // Облако: объёмное рассеяние; именно оно даёт молочность.
            float dens = 0.035 + 0.10 * surf;
            float a = 1.0 - exp(-chord * dens);
            float impact = sqrt(max(0.0, r * r - b * b));
            float soft = clamp(impact / max(r, 1e-4), 0.0, 1.0);
            float lumpy = 0.55 + 0.45 * dirt_pattern(c * 0.23 + p * 0.08);
            a *= (0.22 + 0.78 * soft) * lumpy;
            vec3 cloudCol = mix(u_lcol, vec3(1.0), 0.72);
            acc += thr * beam * cloudCol[ch] * 4.0 * a;
            thr *= 1.0 - a * 0.25;
        } else if (kq < 4.5) {
            // Шёлк: ориентированные иглы.
            float dens = u_inck[q].y;
            vec3 ax = normalize(u_caxis);
            vec3 a0 = normalize(cross(ax, abs(ax.x) < 0.9 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0)));
            vec3 a1 = cross(ax, a0);
            float w = 0.15 * sin(u_time * 0.35);
            vec3 L1 = normalize(vec3(-0.55 + w, -0.75, 0.38));
            vec3 L2 = normalize(vec3(0.65, -0.55 + w, 0.50));
            float sc = 0.0;
            for (int n = 0; n < 3; n++) {
                float an = 1.0471976 * float(n);
                vec3 ai = a0 * cos(an) + a1 * sin(an);
                float e1 = dot(d, ai) - dot(L1, ai);
                float e2 = dot(d, ai) - dot(L2, ai);
                sc += exp(-e1 * e1 / 0.00025) + exp(-e2 * e2 / 0.00025) * 0.25;
            }
            float a = 1.0 - exp(-chord * 0.010 * dens);
            acc += thr * lit * a * (0.30 + 1.8 * sc);
            thr *= 1.0 - a * 0.6;
        } else if (kq < 5.5) {
            // Каверна: поверхностная полость, забитая грязью.
            float dirt = 0.35 + 0.55 * surf;
            acc += thr * lit * 0.14 * (1.0 - dirt);
            thr *= 0.35;
        } else if (kq < 6.5) {
            // Спайность: плоскость, может дать опасный скол.
            vec3 n = normalize(u_inck[q].yzw + vec3(1e-5));
            float dn = dot(d, n);
            if (abs(dn) > 1e-4) {
                float tp = dot(c - p, n) / dn;
                if (tp > 0.0 && tp < tmax && length(p + d * tp - c) < r) {
                    acc += thr * lit * 0.80 * pow(abs(dn), 0.4);
                    thr *= 0.55;
                }
            }
        } else {
            // Внутреннее зерно: тонкие линии.
            float a = 1.0 - exp(-chord * 0.06);
            acc += thr * lit * a * 0.70;
            thr *= 1.0 - a * 0.4;
        }
    }
}

// ============================================================
//  Короткий внутренний путь для сырья/матовой поверхности.
//  Сырьё не «непрозрачный камень»: свет входит в него, мутнеет,
//  рассеивается на включениях и выходит обратно.
// ============================================================
vec3 rough_inside(vec3 p0, vec3 rd, vec3 N, float F0, float filmT, float rough) {
    vec3 outC = vec3(0.0);
    for (int ch = 0; ch < 3; ch++) {
        float ior = u_ior[ch];
        vec3 d = refract(rd, N, 1.0 / ior);
        if (dot(d, d) < 0.5) continue;
        vec3 p = p0 + d * 1e-4;
        float thr = (1.0 - F0) * filmT * (0.26 + 0.34 * (1.0 - rough));
        float acc = 0.0;
        for (int b = 0; b < 4; b++) {
            float tmin = 1e9;
            int j = -1;
            for (int i = 0; i < u_n; i++) {
                float dn = dot(d, u_pl[i].xyz);
                if (dn > 1e-6) {
                    float t = (u_pl[i].w - dot(p, u_pl[i].xyz)) / dn;
                    if (t < tmin) { tmin = t; j = i; }
                }
            }
            if (j < 0) break;
            float beam = flash_inside(p + d * tmin * 0.5);
            vec3 ab = u_absorb;
            if (u_cfon > 0)
                ab = (absorbAt(p + d * tmin * 0.17) + absorbAt(p + d * tmin * 0.5) + absorbAt(p + d * tmin * 0.83)) / 3.0;
            thr *= exp(-ab[ch] * tmin);
            if (u_ninc > 0) inclusions(p, d, tmin, ch, acc, thr, beam);
            // мутность нарушенного слоя внутри
            acc += thr * beam * u_lcol[ch] * (0.02 + 0.10 * u_damage + 0.04 * rough) * tintAt(p)[ch];
            p += d * tmin;
            vec3 Nx = u_pl[j].xyz;
            if (u_kind[j] > 0.5) {
                acc += thr * beam * u_lcol[ch] * (0.06 + 0.18 * u_grit[j]) * tintAt(p)[ch];
                break;
            }
            float ci = dot(d, Nx);
            float s2 = ior * ior * (1.0 - ci * ci);
            if (s2 >= 1.0) {
                d = reflect(d, Nx);
            } else {
                float Fx = fresnel(ci, ior, 1.0);
                vec3 out_d = refract(d, Nx, ior);
                acc += thr * (1.0 - Fx) * env(u_rot * out_d)[ch] * 0.06 * tintAt(p)[ch];
                thr *= Fx;
                d = reflect(d, Nx);
            }
            p += d * 1e-4;
            if (thr < 0.01) break;
        }
        outC[ch] = acc;
    }
    return outC;
}

// ============================================================
//  Трассировка
// ============================================================
vec4 trace(vec2 px) {
    vec3 ro = transpose(u_rot) * vec3((px - u_size * 0.5 - u_off) / u_scale, 10.0);
    vec3 rd = transpose(u_rot) * vec3(0.0, 0.0, -1.0);

    float tin = -1e9, tout = 1e9;
    int ein = -1;
    for (int i = 0; i < u_n; i++) {
        vec3 n = u_pl[i].xyz;
        float dn = dot(rd, n);
        float dist = u_pl[i].w - dot(ro, n);
        if (abs(dn) < 1e-6) {
            if (dist < 0.0) return vec4(0.0);
            continue;
        }
        float t = dist / dn;
        if (dn < 0.0) {
            if (t > tin) { tin = t; ein = i; }
        } else {
            if (t < tout) tout = t;
        }
    }
    if (ein < 0 || tin >= tout) return vec4(0.0);

    vec3 p0 = ro + rd * tin;
    vec3 N = u_pl[ein].xyz;
    float k = u_kind[ein];
    float rough = clamp(max(u_grit[ein], u_rough), 0.02, 1.0);
    float dirt = clamp(u_dirt * (0.35 + 0.65 * dirt_pattern(p0)), 0.0, 1.0);
    float film = clamp(u_film * (0.45 + 0.55 * dirt_pattern(p0 + vec3(13.0))), 0.0, 1.0);
    float wet = clamp(u_wet, 0.0, 1.0);
    // Грязь — не только цвет: она реально ослабляет свет, идущий внутрь.
    float filmT = exp(-(film * (1.0 - 0.65 * wet) * 1.8 + dirt * (1.0 - 0.50 * wet) * 1.55));
    float damage = clamp(u_damage, 0.0, 1.0);
    float polish = clamp(u_polish, 0.0, 1.0);
    float scratch = u_scratches * smoothstep(0.72, 0.98, dirt_pattern(p0 * 2.7 + vec3(5.0)));

    // Кабошон: сглаживание кромок — форма, а не шум.
    bool smooth_dome = u_dome.w > 0.5 && N.z < -0.05;
    if (smooth_dome) {
        vec3 sn = N;
        for (int i = 0; i < u_n; i++) {
            vec3 ni = u_pl[i].xyz;
            if (i == ein || ni.z > -0.05) continue;
            float dd = u_pl[i].w - dot(p0, ni);
            sn += ni * exp(-max(dd, 0.0) / u_dome.x);
        }
        N = normalize(sn);
    }

    // Кромка: не геометрический шум, а мягкое затенение у ребра.
    float edge = 1e9;
    for (int i = 0; i < u_n; i++) {
        if (i == ein) continue;
        float d2 = u_pl[i].w - dot(p0, u_pl[i].xyz);
        float s = length(u_pl[i].xyz - N * dot(u_pl[i].xyz, N));
        if (s > 1e-3) edge = min(edge, d2 / s);
    }
    float edgeK = smooth_dome ? 1.0 : smoothstep(0.0, 1.6 / max(u_scale, 1.0), edge);

    // Очень слабый мезорельеф: низкая частота, чтобы камень не был
    // идеально-плоским, но и не превращался в «шерсть».
    if (k > 0.5 && rough > 0.15) {
        vec3 t1 = normalize(cross(N, abs(N.z) < 0.9 ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0)));
        vec3 t2 = cross(N, t1);
        float e = 0.6;
        float h0 = dirt_pattern(p0 * 0.7);
        float hx = dirt_pattern((p0 + t1 * e) * 0.7);
        float hy = dirt_pattern((p0 + t2 * e) * 0.7);
        N = normalize(N + (t1 * (hx - h0) + t2 * (hy - h0)) * 0.10);
    }

    vec3 tint = tintAt(p0) * pleoTint(rd);
    vec3 dirtCol = mix(vec3(0.045, 0.035, 0.026), vec3(0.22, 0.17, 0.12), dirt_pattern(p0 * 1.3));
    vec3 col = vec3(0.0);

    // ---- матовая / сырая / шлифованная поверхность ----
    if (k > 0.5) {
        vec3 V = -rd;
        vec3 L = normalize(u_lpos - p0);
        float NoL = max(dot(N, L), 0.0);
        float NoV = max(dot(N, V), 1e-4);
        float F0 = fresnel(1.0, 1.0, u_ior.y);
        float lit = flash_at(p0);
        float dirtMask = 0.38 + 0.62 * dirt_pattern(p0 * 0.9);
        vec3 albedo = mix(tint, dirtCol * 0.55, dirt) * 0.82;
        // диффузная составляющая грязной поверхности
        vec3 diff = albedo * (lit * u_lcol * NoL / PI) * (1.0 - F0);
        // зеркальная составляющая микрофасетов
        float spec = specular_ggx(N, V, L, rough * (1.0 - 0.25 * wet), F0);
        spec *= 1.0 - smoothstep(0.15, 0.55, rough);
        vec3 specC = u_lcol * lit * spec * (1.0 + 0.45 * wet);
        // плёнка даёт свой мягкий блик и «сальный» вид
        float filmSpec = pow(max(dot(reflect(-L, N), V), 0.0), 8.0 + 24.0 * (1.0 - rough));
        specC += dirtCol * u_lcol * lit * filmSpec * film * 0.55 * (1.0 - rough);
        // Царапины — тонкие следы, а не белые пятна.
        specC += mix(dirtCol, u_lcol, 0.25) * lit * scratch * 0.10 * (1.0 - rough);
        specC *= 1.0 - dirt * 0.55;
        // окружающий свет и три студийных источника вокруг камня
        vec3 amb = albedo * env(u_rot * N) * (0.10 + 0.12 * (1.0 - rough));
        vec3 studio = studio_light_rgb(p0, N, V, rough, albedo) * (1.0 - dirt * 0.35);
        float inside = flash_inside(p0 + N * 0.5);
        // Внутреннее свечение — только от объёма, не белые пятна от грязи.
        vec3 sss = tint * u_lcol * inside * (0.012 + 0.045 * damage) * filmT;
        // Плёнка в основном поглощает и чуть рассеивает; она не светится.
        vec3 filmScatter = dirtCol * u_lcol * inside * 0.012 * dirt * filmT;
        col = diff + specC + amb + studio + sss + filmScatter;
        col *= 1.0 - dirt * 0.72 * dirtMask;
        // Грязь скапливается у кромок и в углублениях.
        col *= 1.0 - dirt * 0.30 * (1.0 - edgeK);
        // Тонкий слой глины/пыли: не белые пятна, а тёплый матовый налёт.
        col = mix(col, dirtCol * (0.42 + 0.30 * dirt_pattern(p0 * 1.4)), dirt * 0.55);
        col = mix(col, mix(tint, vec3(0.35, 0.31, 0.25), 0.65), film * 0.30);
        // Внутренний свет: именно он проявляет включения в сырье.
        vec3 inner = rough_inside(p0, rd, N, F0, filmT, rough);
        col += inner * (0.16 + 0.14 * (1.0 - rough));
        col *= mix(0.72, 1.0, edgeK);
        return vec4(col, 1.0);
    }

    // ---- полированная / прозрачная грань ----
    for (int ch = 0; ch < 3; ch++) {
        float ior = u_ior[ch];
        float cosi = -dot(rd, N);
        float F = fresnel(cosi, 1.0, ior);
        float lit = flash_at(p0);
        vec3 L = normalize(u_lpos - p0);
        float spec = specular_ggx(N, -rd, L, max(rough, 0.03 + 0.08 * (1.0 - polish)), fresnel(1.0, 1.0, ior));
        float acc = F * env(u_rot * reflect(rd, N))[ch] + spec * lit * u_lcol[ch] * (1.0 + 0.35 * wet);
        // три студийных источника: камень не должен быть чёрным пятном
        vec3 studio = studio_light_rgb(p0, N, -rd, max(rough, 0.03 + 0.08 * (1.0 - polish)),
                                       dirtCol * dirt * 0.35);
        acc += studio[ch];
        // грязь на полированной грани: слабый диффузный слой
        acc += dirtCol[ch] * lit * dirt * 0.12;
        acc += u_lcol[ch] * lit * scratch * 0.16;
        vec3 d = refract(rd, N, 1.0 / ior);
        vec3 p = p0 + d * 1e-4;
        float thr = (1.0 - F) * filmT;
        // Свет, вошедший через грань, — не только отражение: он идёт внутрь
        // и подсвечивает включения. Это входная радиация, а не экранное пятно.
        float entryLit = flash_at(p0);
        acc += thr * entryLit * u_lcol[ch] * (0.05 + 0.10 * damage + 0.04 * dirt);
        float scattered = 0.0;

        for (int b = 0; b < 7; b++) {
            float tmin = 1e9;
            int j = -1;
            for (int i = 0; i < u_n; i++) {
                float dn = dot(d, u_pl[i].xyz);
                if (dn > 1e-6) {
                    float t = (u_pl[i].w - dot(p, u_pl[i].xyz)) / dn;
                    if (t < tmin) { tmin = t; j = i; }
                }
            }
            if (j < 0) break;

            // Свет фонарика внутри объёма: рассеяние на нарушенном слое
            // и на включениях. Это не экранное пятно, а луч в материале.
            float beam = flash_inside(p + d * tmin * 0.5);
            vec3 ab = u_absorb;
            if (u_cfon > 0)
                ab = (absorbAt(p + d * tmin * 0.17) + absorbAt(p + d * tmin * 0.5) + absorbAt(p + d * tmin * 0.83)) / 3.0;
            thr *= exp(-ab[ch] * tmin);
            if (u_ninc > 0) inclusions(p, d, tmin, ch, acc, thr, beam);
            // слабое объёмное рассеяние в нарушенном слое/плёнке
            float vol = (0.010 + 0.075 * damage + 0.020 * film) * (0.4 + 0.6 * tint[ch]);
            acc += thr * beam * u_lcol[ch] * vol;
            scattered += thr * vol;

            p += d * tmin;
            vec3 Nx = u_pl[j].xyz;
            if (u_kind[j] > 0.5) {
                // внутренняя матовая граница: свет рассеивается и гаснет
                acc += thr * beam * u_lcol[ch] * (0.10 + 0.25 * u_grit[j]);
                thr = 0.0;
                break;
            }
            float ci = dot(d, Nx);
            float s2 = ior * ior * (1.0 - ci * ci);
            if (s2 >= 1.0) {
                d = reflect(d, Nx);
            } else {
                float Fx = fresnel(ci, ior, 1.0);
                vec3 out_d = refract(d, Nx, ior);
                acc += thr * (1.0 - Fx) * env(u_rot * out_d)[ch];
                // на выходе фонарик тоже может дать блик
                float outLit = flash_at(p);
                acc += thr * (1.0 - Fx) * outLit * u_lcol[ch] * dirt * 0.04;
                thr *= Fx;
                d = reflect(d, Nx);
            }
            p += d * 1e-4;
            if (thr < 0.01) break;
        }
        acc += thr * 0.04 * u_env;
        col[ch] = acc;
    }

    // мутность: рассеяние на плёнке и нарушенном слое, а не серый туман
    float haze = clamp(dirt * 0.16 + film * 0.10 + damage * 0.06, 0.0, 0.55);
    vec3 hazeCol = mix(tint, dirtCol, clamp(dirt * 0.7, 0.0, 0.7)) * (0.10 + 0.18 * u_env);
    col = mix(col, hazeCol, haze);
    col *= mix(0.65, 1.0, edgeK);
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
    c *= 1.25;
    c = c / (1.0 + c * 0.42);
    c = pow(max(c, 0.0), vec3(1.0 / 1.15));
    float alpha = clamp(mix(0.62, 1.0, u_trans), 0.0, 1.0);
    f = vec4(c * s.a * alpha, s.a * alpha);
}
