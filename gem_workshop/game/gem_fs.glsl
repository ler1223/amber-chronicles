#version 330

in vec2 v_uv;
out vec4 f;

// ---- геометрия камня: выпуклый многогранник ----
uniform vec4 u_pl[128];      // нормаль (оси камня) и отступ
uniform float u_kind[128];   // 0 полировка, 1 шлифовка, 2 сырая корка, 3 рундист, 4 природная грань, 5 раковистый скол
uniform float u_grit[128];   // микрорельеф грани 0..1
uniform vec4 u_fdir[128];    // природная грань: xyz — направление поперёк штрихов, w — частота; скол: xyz — точка удара
uniform int u_n;
uniform mat3 u_rot;          // мир <- камень
uniform vec2 u_size;
uniform float u_scale;
uniform vec2 u_off;
uniform float u_round;       // скругление кромок сырой корки (окатанность), единицы камня
uniform float u_stain;       // ржавый налёт на старых изломах 0..1
// ---- порода, в которой сидит кристалл: второе выпуклое тело, непрозрачное ----
uniform vec4 u_mpl[32];
uniform int u_mn;            // 0 — породы нет
uniform int u_mrock;         // 0 мрамор, 1 пегматит, 2 тёмная порода, 3 агатовая корка

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
uniform vec4 u_incaxis[16];  // ось эллипсоида, вытянутость
uniform vec4 u_incm[16];     // рельеф (разница n), непрозрачность, зерно, запас
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
uniform int u_czon;          // зоны роста: есть ли центр кристалла в карте
uniform vec3 u_cfo;          // центр кристалла в карте (мм)
uniform vec4 u_cz;           // сила, шаг (мм), «гуще к верхушке», фаза
uniform int u_czm;           // 0 — шестиугольник, 1 — ромбоэдр

// ---- свет ----
// Фонарик живёт в осях камня: при повороте камня луч остаётся мировым светом.
uniform vec3 u_lpos;
uniform vec3 u_ldir;
uniform vec3 u_lcol;
uniform float u_lint;
uniform float u_lcos;
uniform float u_lsoft;
uniform float u_ltan;
uniform float u_lref;
uniform float u_lon;
uniform float u_env;

// ---- поверхность ----
uniform float u_rough;
uniform float u_dirt;
uniform float u_film;
uniform float u_damage;
uniform float u_polish;
uniform float u_wet;
uniform float u_scratches;
uniform float u_pleo;
uniform float u_biref;
uniform vec3 u_opaxis;
uniform float u_star;
uniform vec3 u_caxis;
uniform vec4 u_dome;

const float PI = 3.14159265359;

// Матовые грани (свет рассеивают): шлифовка, сырая корка, рундист.
// Природная грань и свежий скол — блестящие, сквозь них видно внутрь.
bool matte(float k) { return k > 0.5 && k < 3.5; }

// ============================================================
//  Шум
// ============================================================
float hash21(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

vec2 hash22(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return fract(sin(p) * 43758.5453);
}

float hash31(vec3 p) {
    return fract(sin(dot(p, vec3(12.9898, 78.233, 37.719))) * 43758.5453);
}

float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash21(i), hash21(i + vec2(1.0, 0.0)), f.x),
               mix(hash21(i + vec2(0.0, 1.0)), hash21(i + vec2(1.0, 1.0)), f.x), f.y);
}

float fbm2(vec2 p) {
    return 0.55 * vnoise(p) + 0.30 * vnoise(p * 2.07 + 5.3) + 0.15 * vnoise(p * 4.13 + 1.7);
}

float vnoise3(vec3 p) {
    vec3 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = mix(mix(hash31(i), hash31(i + vec3(1, 0, 0)), f.x),
                  mix(hash31(i + vec3(0, 1, 0)), hash31(i + vec3(1, 1, 0)), f.x), f.y);
    float b = mix(mix(hash31(i + vec3(0, 0, 1)), hash31(i + vec3(1, 0, 1)), f.x),
                  mix(hash31(i + vec3(0, 1, 1)), hash31(i + vec3(1, 1, 1)), f.x), f.y);
    return mix(a, b, f.z);
}

// Капли залеченной трещины: расстояние до ближайшей капли (клетки Вороного).
float drops(vec2 x, out float rnd) {
    vec2 i = floor(x), fp = fract(x);
    float best = 9.0;
    rnd = 0.0;
    for (int yy = -1; yy <= 1; yy++) {
        for (int xx = -1; xx <= 1; xx++) {
            vec2 g = vec2(float(xx), float(yy));
            vec2 o = hash22(i + g);
            vec2 r = g + o * 0.8 + 0.1 - fp;
            float dd = dot(r, r);
            if (dd < best) { best = dd; rnd = hash21(i + g + 3.7); }
        }
    }
    return sqrt(best);
}

// ============================================================
//  Окружение: тёмная студия, мягкие источники
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

// Окружение для матовых поверхностей: усреднённое, без отражений ламп и колец
// (матовая корка не может отразить чёткую картинку).
vec3 env_soft(vec3 d) {
    float up = clamp(-d.y, 0.0, 1.0);
    vec3 c = mix(vec3(0.05, 0.045, 0.05), vec3(0.30, 0.29, 0.29), up);
    c += vec3(0.20, 0.19, 0.18) * smoothstep(0.0, 0.9, d.z);
    return c * u_env;
}

// ============================================================
//  Оптика
// ============================================================
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

// Интерференция в тонком слое (воздух/жидкость в трещине): цвет по длине волны.
float film_ch(float h_um, float cosT, int ch) {
    float lam = ch == 0 ? 0.65 : (ch == 1 ? 0.53 : 0.45);
    return 0.5 + 0.5 * cos(12.566 * h_um * cosT / lam + PI);
}

// ============================================================
//  Три студийных источника вокруг камня
// ============================================================
vec3 studio_pos(int i) {
    if (i == 0) return vec3(-260.0, -170.0, 330.0);
    if (i == 1) return vec3( 300.0, -120.0, 260.0);
    return vec3(  20.0,  280.0, -230.0);
}

vec3 studio_col(int i) {
    if (i == 0) return vec3(1.00, 0.90, 0.78);
    if (i == 1) return vec3(0.62, 0.78, 1.00);
    return vec3(0.88, 0.92, 1.00);
}

float studio_power(int i) {
    if (i == 0) return 2.4;
    if (i == 1) return 1.55;
    return 1.8;
}

vec3 studio_light_rgb(vec3 p, vec3 N, vec3 V, float rough, vec3 albedo) {
    vec3 outC = vec3(0.0);
    for (int i = 0; i < 3; i++) {
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
        spec *= 1.0 - smoothstep(0.15, 0.55, rough);
        vec3 diff = albedo * (NoL / PI) * (vec3(1.0) - F0);
        outC += studio_col(i) * studio_power(i) * att * (diff + spec);
    }
    return outC;
}

// Рассеянный свет студии, падающий на матовую поверхность (без зеркальной части).
vec3 studio_irr(vec3 p, vec3 N) {
    vec3 outC = vec3(0.0);
    for (int i = 0; i < 3; i++) {
        vec3 lp = transpose(u_rot) * studio_pos(i);
        vec3 Lv = lp - p;
        float dist = length(Lv);
        vec3 L = Lv / max(dist, 1e-3);
        // мягкое «обволакивание»: матовый камень светится и чуть за терминатором
        float w = clamp((dot(N, L) + 0.25) / 1.25, 0.0, 1.0);
        float att = (420.0 * 420.0) / (dist * dist + 420.0 * 420.0 * 0.10);
        outC += studio_col(i) * studio_power(i) * att * w / PI;
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

// Луч внутри камня считается один раз на пиксель: точка входа, направление после
// преломления и то, насколько матовый вход его рассеял (сырая корка — как матовая лампа).
vec3 g_bq;
vec3 g_bd;
float g_bT;
float g_bdiff;
float g_batt;
bool g_bon;

void setup_beam() {
    g_bon = false;
    g_bq = vec3(0.0);
    g_bd = vec3(0.0, 0.0, 1.0);
    g_bT = 0.0;
    g_bdiff = 0.0;
    g_batt = 0.0;
    if (u_lon < 0.5) return;
    vec3 L = u_lpos;
    vec3 dir = normalize(u_ldir);
    float tmin = 1e9;
    int j = -1;
    for (int i = 0; i < u_n; i++) {
        float dn = dot(dir, u_pl[i].xyz);
        if (dn < -1e-6) {
            float t = (u_pl[i].w - dot(L, u_pl[i].xyz)) / dn;
            if (t > 1e-4 && t < tmin) {
                // точка должна лежать на камне, а не на продолжении плоскости
                vec3 q = L + dir * t;
                bool inside = true;
                for (int m = 0; m < u_n; m++) {
                    if (m != i && dot(q, u_pl[m].xyz) - u_pl[m].w > 0.05) { inside = false; break; }
                }
                if (inside) { tmin = t; j = i; }
            }
        }
    }
    if (j < 0) return;
    vec3 Nq = u_pl[j].xyz;
    float cosi = clamp(-dot(dir, Nq), 0.0, 1.0);
    float ior = max(1.01, u_ior.y);
    vec3 dIn = refract(dir, Nq, 1.0 / ior);
    if (dot(dIn, dIn) < 0.5) return;
    float kj = u_kind[j];
    g_bq = L + dir * tmin;
    g_bd = normalize(dIn);
    g_bT = 1.0 - fresnel(cosi, 1.0, ior);
    g_bdiff = matte(kj) ? clamp(0.55 + 0.45 * max(u_rough, u_grit[j]), 0.0, 1.0)
                        : (kj > 4.5 ? 0.22 : (kj > 3.5 ? 0.06 : 0.0));
    g_batt = (u_lref * u_lref) / (tmin * tmin + u_lref * u_lref * 0.08);
    g_bon = true;
}

float flash_inside(vec3 p) {
    if (!g_bon) return 0.0;
    vec3 rel = p - g_bq;
    float along = dot(rel, g_bd);
    float dist = length(rel);
    float dirPart = 0.0;
    if (along > 0.0) {
        vec3 perp = rel - g_bd * along;
        float radius = max(1.5, along * u_ltan + 2.0);
        dirPart = exp(-dot(perp, perp) / max(1.0, radius * radius * 0.70));
    }
    // матовый вход: свет расходится во все стороны от пятна входа
    float diffPart = exp(-dist / 48.0) * 0.85;
    float v = mix(dirPart, diffPart, g_bdiff);
    return u_lint * g_bT * g_batt * v * exp(-dist * u_absorb.y * 0.35);
}

// Направление, в котором свет фонарика идёт через точку p.
vec3 beam_dir(vec3 p) {
    vec3 r = p - g_bq;
    float l = length(r);
    vec3 radial = l > 1e-3 ? r / l : g_bd;
    return normalize(mix(g_bd, radial, g_bdiff));
}

// ============================================================
//  Цвет и поглощение
// ============================================================
// Зоны роста по геометрии кристалла — та же формула, что sim/gems.zone_t:
// pc — точка в осях кристалла (мм, ось c = z), полосы параллельны граням.
float zone_t(vec3 pc) {
    float d;
    if (u_czm == 1) {
        float sr = 0.78591, cr = 0.61823;               // sin/cos 51.8° — грань r кварца
        d = -1e9;
        for (int k = 0; k < 6; k++) {
            float a = float(k) * 1.0471976;
            float sg = (k - (k / 2) * 2) == 0 ? 1.0 : -1.0;
            d = max(d, pc.x * sr * cos(a) + pc.y * sr * sin(a) + pc.z * cr * sg);
        }
    } else {
        d = max(max(abs(pc.x), abs(0.5 * pc.x + 0.866 * pc.y)), abs(-0.5 * pc.x + 0.866 * pc.y));
    }
    float band = tanh(2.2 * sin(6.2831853 * d / u_cz.y + u_cz.w)) / tanh(2.2);
    return u_cz.x * band + u_cz.z * clamp(pc.z / 3.0, -1.0, 1.0);
}

float fieldT(vec3 p) {
    vec3 q = u_cfA * p + u_cfb;
    float s = 0.0;
    for (int i = 0; i < 4; i++) s += u_wa[i] * sin(dot(u_wk[i].xyz, q) + u_wk[i].w);
    float t = 0.5 + 0.5 * s / (u_wa.x + u_wa.y + u_wa.z + u_wa.w) * u_cfg.x;
    if (u_czon > 0) t += zone_t(q - u_cfo);
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

vec3 pleoTint(vec3 d) {
    if (u_pleo < 0.01) return vec3(1.0);
    vec3 ax = normalize(u_opaxis + vec3(1e-5));
    float a = 0.5 + 0.5 * dot(normalize(d), ax);
    vec3 A = vec3(1.0 + u_pleo * 0.36, 1.0 - u_pleo * 0.16, 1.0 - u_pleo * 0.26);
    vec3 B = vec3(1.0 - u_pleo * 0.22, 1.0 + u_pleo * 0.30, 1.0 + u_pleo * 0.12);
    return clamp(mix(A, B, a), 0.35, 1.65);
}

// Поглощение — на миллиметр пути, а не на единицу модели: у сырья и огранки
// разный масштаб единиц (u_cfA переводит единицы в мм), а цвет одного и того же
// камня не должен зависеть от того, огранён он или нет.
// 0.45/мм: типичный фиолетовый аметист на 5 мм пропускает ≈ ¼ зелёного.
const float ABSORB_PER_MM = 0.45;

vec3 absorbAt(vec3 p) {
    if (u_cfon == 0) return u_absorb;
    vec3 c = palAt(fieldT(p));
    float mmu = length(u_cfA[0]);
    return (pow(1.0 - c, vec3(1.4)) * ABSORB_PER_MM * u_dark + 0.01) * mmu;
}

// ============================================================
//  Поверхность грани
// ============================================================
// Природная грань: штриховка роста (ступеньки) и лёгкая волнистость.
// Раковистый скол: концентрическая рябь от точки удара.
// amp — сила рельефа: изнутри камня (внутренние отражения) рябь ослаблена, иначе
// лучи трёх цветов на мелких гребнях разлетаются в цветной шум.
vec3 face_normal(vec3 N, vec3 p, int j, float amp) {
    float k = u_kind[j];
    vec4 fd = u_fdir[j];
    if (k > 3.5 && k < 4.5) {
        vec3 t1 = normalize(cross(N, abs(N.z) < 0.9 ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0)));
        vec3 t2 = cross(N, t1);
        vec2 q = vec2(dot(p, t1), dot(p, t2));
        float e = 1.5;
        float w0 = vnoise(q * 0.025);
        vec2 g = vec2(vnoise((q + vec2(e, 0.0)) * 0.025) - w0, vnoise((q + vec2(0.0, e)) * 0.025) - w0) / e;
        N = normalize(N - (t1 * g.x + t2 * g.y) * 0.6 * amp);
        if (fd.w > 0.0 && dot(fd.xyz, fd.xyz) > 0.25) {
            // ступеньки роста: пологий подъём и резкая кромка, шаг и высота неровные,
            // часть ступенек обрывается посреди грани
            float s = dot(p, fd.xyz) * fd.w + 1.6 * vnoise(q * 0.03);
            float ph = fract(s);
            float st = floor(s);
            float alive = step(0.25, vnoise(vec2(dot(p, cross(N, fd.xyz)) * 0.03, st * 1.7)));
            float hgt = 0.4 + 1.2 * hash21(vec2(st, 3.1));
            float slope = (ph < 0.86 ? 0.10 : -0.55) * hgt * alive;
            N = normalize(N + fd.xyz * slope * 0.32 * amp);
        }
    } else if (k > 4.5) {
        vec3 rel = p - fd.xyz;
        rel -= N * dot(rel, N);
        float d = length(rel);
        if (d > 1e-3) {
            // волны излома неровные: расстояние «плывёт» по углу, гребни то гуще, то реже
            vec3 t1 = normalize(cross(N, abs(N.z) < 0.9 ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0)));
            float ang = atan(dot(rel, cross(N, t1)), dot(rel, t1));
            float dw = d * (1.0 + 0.35 * (vnoise(vec2(ang * 2.2, 4.0)) - 0.5)) + 6.0 * vnoise(rel.xy * 0.04 + rel.z * 0.03);
            float rip = sin(dw * 0.50) * (0.6 + 0.4 * sin(dw * 0.13 + 1.0)) * exp(-d / 75.0);
            N = normalize(N + (rel / d) * rip * 0.05 * amp);
        }
    }
    return N;
}

// Скругление кромок окатанной корки: нормаль плавно переходит к соседним граням.
vec3 rounded_normal(vec3 N, vec3 p, int ein, float rad) {
    vec3 sn = N;
    for (int i = 0; i < u_n; i++) {
        if (i == ein) continue;
        float dd = u_pl[i].w - dot(p, u_pl[i].xyz);
        sn += u_pl[i].xyz * exp(-max(dd, 0.0) / rad);
    }
    return normalize(sn);
}

// ============================================================
//  Включения
// ============================================================
// Типы: 0 кристаллик, 1 пузырь газа, 2 перо, 3 облако, 4 шёлк, 5 каверна,
// 6 спайность, 7 зерно, 8 отпечаток, 9 полость с пузырьком, 10 ореол.
//
// Два правила атласа:
//  - светлое поле (свет идёт прямо на зрителя): включение — тёмная помеха;
//    тёмное поле (свет сбоку): то же включение светится;
//  - контраст — от разницы показателей преломления (u_incm.x), а не константа.
// Через матовую корку дальние включения размываются (blurK × расстояние).

vec3 local_axis(int q, out float aspect) {
    aspect = max(0.35, u_incaxis[q].w);
    vec3 ax = u_incaxis[q].xyz;
    if (u_inck[q].x > 8.5 && u_inck[q].x < 9.5) ax = u_caxis;   // полость повторяет форму хозяина
    return normalize(ax + vec3(1e-5));
}

// Пересечение с маленьким многогранником (шестигранная призма с торцами)
// в локальных осях: ocL, dL — уже с учётом вытянутости.
bool poly_hit(vec3 ocL, vec3 dL, float rr, float seed, float tmax, out float t0, out float t1, out vec3 nIn) {
    t0 = -1e9;
    t1 = 1e9;
    nIn = vec3(0.0, 0.0, 1.0);
    for (int k = 0; k < 8; k++) {
        vec3 n;
        float o;
        if (k < 6) {
            float a = float(k) * 1.0471976 + seed * 6.0;
            float tilt = (hash21(vec2(seed * 13.0, float(k))) - 0.5) * 0.35;
            n = normalize(vec3(cos(a), sin(a), tilt));
            o = rr * (0.78 + 0.22 * hash21(vec2(float(k), seed * 7.0)));
        } else {
            float sgn = k == 6 ? 1.0 : -1.0;
            vec2 h = hash22(vec2(seed * 5.0, float(k))) - 0.5;
            n = normalize(vec3(h * 0.6, sgn));
            o = rr * (0.85 + 0.15 * hash21(vec2(seed, float(k) * 3.0)));
        }
        float dn = dot(dL, n);
        float dist = o - dot(ocL, n);
        if (abs(dn) < 1e-6) {
            if (dist < 0.0) return false;
            continue;
        }
        float t = dist / dn;
        if (dn < 0.0) {
            if (t > t0) { t0 = t; nIn = n; }
        } else {
            t1 = min(t1, t);
        }
    }
    t0 = max(t0, 0.0);
    t1 = min(t1, tmax);
    return t1 > t0;
}

// Плоскость включения: точка попадания и координаты в её плоскости (в радиусах).
bool plane_hit(vec3 p, vec3 d, vec3 c, vec3 n, float r, float tmax, out vec3 hp, out vec2 uv,
               out vec3 t1v, out vec3 t2v) {
    hp = vec3(0.0);
    uv = vec2(9.0);
    t1v = vec3(1.0, 0.0, 0.0);
    t2v = vec3(0.0, 1.0, 0.0);
    float dn = dot(d, n);
    if (abs(dn) < 1e-4) return false;
    float tp = dot(c - p, n) / dn;
    if (tp <= 0.0 || tp >= tmax) return false;
    hp = p + d * tp;
    t1v = normalize(cross(n, abs(n.x) < 0.9 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0)));
    t2v = cross(n, t1v);
    uv = vec2(dot(hp - c, t1v), dot(hp - c, t2v)) / r;
    return length(uv) < 1.6;
}

void inclusions(vec3 p, vec3 d, float tmax, int ch, inout float acc, inout float thr, float blurK, vec3 eP) {
    float nh = u_ior.y;
    for (int q = 0; q < u_ninc; q++) {
        vec3 c = u_inc[q].xyz;
        float r = u_inc[q].w;
        float kq = u_inck[q].x;
        vec4 mat = u_incm[q];
        float relief = mat.x;
        float seed = mat.z;

        // размытие через корку: дальнее от входа — мягче и бледнее
        float blur = blurK * length(c - eP);
        float soft = r / (r + blur);
        float kk = pow(soft, 1.5);

        float lit = flash_inside(c) * u_lcol[ch] * 3.0;
        vec3 bd = beam_dir(c);
        float fwd = smoothstep(0.30, 0.92, dot(bd, -d));
        float sideW = mix(1.0, 0.15, fwd);         // светлое поле гасит свечение
        float amb = 0.035 * u_env;

        // ---------- объёмные тела ----------
        if (kq < 1.5 || (kq > 2.5 && kq < 5.5) || (kq > 6.5 && kq < 7.5) || (kq > 8.5 && kq < 9.5)) {
            float aspect;
            vec3 ax = local_axis(q, aspect);
            vec3 tan1 = normalize(cross(ax, abs(ax.x) < 0.9 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0)));
            vec3 tan2 = cross(ax, tan1);
            vec3 oc = p - c;
            float rr = r + 0.6 * blur;
            vec3 ocL = vec3(dot(oc, tan1), dot(oc, tan2), dot(oc, ax) / aspect);
            vec3 dL = vec3(dot(d, tan1), dot(d, tan2), dot(d, ax) / aspect);
            float ldL = length(dL);

            if (kq < 0.5 || (kq > 8.5 && kq < 9.5)) {
                // ---- кристаллик / полость в форме кристалла хозяина ----
                float t0, t1;
                vec3 nL;
                if (!poly_hit(ocL, dL, rr, seed, tmax, t0, t1, nL)) continue;
                float chord = (t1 - t0) * ldL;
                float e = clamp(1.0 - chord / (2.0 * rr), 0.0, 1.0);
                float rim = smoothstep(0.35, 0.92, e);
                vec3 nS = normalize(tan1 * nL.x + tan2 * nL.y + ax * (nL.z / aspect));
                vec3 rf = reflect(d, nS);
                float glint = pow(max(dot(rf, -bd), 0.0), 10.0);
                float opac = kq < 0.5 ? mat.y : 0.0;
                float a0 = thr;
                acc += a0 * kk * (lit * (glint * (0.35 + 0.65 * relief) + sideW * relief * 0.22 * (1.0 - opac))
                                  + amb * glint * relief);
                thr *= 1.0 - kk * clamp(opac * 0.95 + (1.0 - opac) * relief * (0.18 + 0.72 * rim), 0.0, 0.97);

                if (kq > 8.5) {
                    // пузырёк всплывает вверх по экрану: при повороте камня он двигается
                    vec3 up = transpose(u_rot) * vec3(0.0, -1.0, 0.0);
                    float rb = r * (0.30 + 0.10 * seed);
                    vec3 cb = c + up * (r * 0.40);
                    vec3 ob = p - cb;
                    float b = dot(ob, d);
                    float disc = b * b - (dot(ob, ob) - rb * rb);
                    if (disc > 0.0) {
                        float sq = sqrt(disc);
                        float u0 = max(-b - sq, 0.0), u1 = min(-b + sq, tmax);
                        if (u1 > u0) {
                            float eb = clamp(1.0 - (u1 - u0) / (2.0 * rb), 0.0, 1.0);
                            float ring = smoothstep(0.25, 0.70, eb);
                            acc += thr * kk * (lit * (pow(eb, 6.0) * 1.1 * sideW + 0.10 * (1.0 - ring)) + amb * pow(eb, 6.0));
                            thr *= 1.0 - kk * 0.90 * ring;
                        }
                    }
                }
                continue;
            }

            // эллипсоид
            float b = dot(ocL, dL) / (ldL * ldL);
            float c2 = (dot(ocL, ocL) - rr * rr) / (ldL * ldL);
            float disc = b * b - c2;
            if (disc <= 0.0) continue;
            float sq = sqrt(disc);
            float t0 = max(-b - sq, 0.0);
            float t1 = min(-b + sq, tmax);
            if (t1 <= t0) continue;
            float chord = (t1 - t0) * ldL;
            float e = clamp(1.0 - chord / (2.0 * rr), 0.0, 1.0);

            if (kq < 1.5) {
                // ---- пузырь газа: толстое тёмное кольцо, светлая середина ----
                float ring = smoothstep(0.22, 0.72, e);
                acc += thr * kk * (lit * (pow(e, 5.0) * 1.2 * sideW + 0.10 * (1.0 - ring)) + amb * pow(e, 5.0));
                thr *= 1.0 - kk * 0.92 * ring * max(relief, 0.6);
            } else if (kq < 3.5) {
                // ---- облако точек: сзади — серая муть, сбоку — молочное свечение ----
                float dens = 0.045 + 0.10 * u_incsurf[q];
                float a = 1.0 - exp(-chord * dens);
                float lumpy = 0.45 + 0.55 * vnoise3(c * 0.2 + (p + d * (t0 + t1) * 0.5) * 0.22);
                a *= (0.25 + 0.75 * (1.0 - e)) * lumpy * kk;
                // отдельные точки-искры (видны вблизи и через окошко)
                vec3 pm = p + d * mix(t0, t1, 0.5);
                float sp = step(0.965, hash31(floor(pm * 1.6) + seed * 31.0)) * soft;
                vec3 cloudCol = mix(u_lcol, vec3(1.0), 0.35);
                acc += thr * (lit / 3.0 * cloudCol[ch] * 1.4 * a * sideW + lit * sp * 0.25 * sideW);
                thr *= 1.0 - a * 0.80;
            } else if (kq < 4.5) {
                // ---- шёлк: три системы игл поперёк оси, блеск по направлению света ----
                float dens = u_inck[q].y;
                vec3 cax = normalize(u_caxis);
                vec3 a0 = normalize(cross(cax, abs(cax.x) < 0.9 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0)));
                vec3 a1 = cross(cax, a0);
                float sc = 0.0;
                for (int n = 0; n < 3; n++) {
                    float an = 1.0471976 * float(n);
                    vec3 ai = a0 * cos(an) + a1 * sin(an);
                    float e1 = dot(d, ai) + dot(bd, ai);
                    sc += exp(-e1 * e1 / 0.0008);
                }
                float a = (1.0 - exp(-chord * 0.010 * dens)) * kk;
                acc += thr * (lit * a * (0.10 * sideW + 0.55 * sc) + amb * a * sc * 3.0);
                thr *= 1.0 - a * 0.45;
            } else if (kq < 5.5) {
                // ---- каверна у поверхности ----
                acc += thr * lit * 0.06 * sideW * kk;
                thr *= 1.0 - 0.6 * kk * smoothstep(0.1, 0.6, 1.0 - e);
            } else {
                // ---- внутреннее зерно ----
                float a = (1.0 - exp(-chord * 0.05)) * kk;
                acc += thr * lit * a * 0.45 * sideW;
                thr *= 1.0 - a * 0.35;
            }
            continue;
        }

        // ---------- плоские: перо, спайность, отпечаток, ореол ----------
        vec3 n = normalize(u_inck[q].yzw + vec3(1e-5));
        vec3 hp, t1v, t2v;
        vec2 uv;
        if (!plane_hit(p, d, c, n, r, tmax, hp, uv, t1v, t2v)) continue;
        float sd = seed * 37.0;
        float bw = 0.04 + blur / max(r, 1e-3);
        float plit = flash_inside(hp) * u_lcol[ch] * 3.0;
        vec3 pbd = beam_dir(hp);
        float pfwd = smoothstep(0.30, 0.92, dot(pbd, -d));
        float psideW = mix(1.0, 0.15, pfwd);

        if (kq < 2.5 || (kq > 5.5 && kq < 6.5)) {
            // ---- перо (открытая трещина) / спайность ----
            bool cleave = kq > 5.5;
            vec2 w = uv * (cleave ? vec2(1.0) : vec2(0.82, 1.18));
            float rho = length(w);
            float jag = cleave ? 0.12 : 0.55;
            float shape = rho + jag * (fbm2(w * 1.6 + sd) - 0.5) + (cleave ? 0.02 : 0.12) * (vnoise(w * 7.0 + sd) - 0.5);
            float m = 1.0 - smoothstep(0.78 - bw, 0.78 + bw, shape);
            if (m <= 0.001) continue;
            // изгиб поверхности трещины
            vec3 nn = n;
            if (!cleave) {
                float ee = 0.05;
                float h0 = fbm2(w * 1.3 + sd + 9.0);
                vec2 g = vec2(fbm2((w + vec2(ee, 0.0)) * 1.3 + sd + 9.0) - h0,
                              fbm2((w + vec2(0.0, ee)) * 1.3 + sd + 9.0) - h0) / ee;
                nn = normalize(n + (t1v * g.x + t2v * g.y) * 0.35);
            }
            // ступеньки излома
            float sa = sd * 0.37;
            float s = dot(w, vec2(cos(sa), sin(sa))) * (cleave ? 6.0 : 9.0) + (cleave ? 0.6 : 2.5) * vnoise(w * 3.0 + sd);
            float stepLine = smoothstep(0.82, 1.0, abs(fract(s) - 0.5) * 2.0) * soft;
            // толщина воздушного зазора: тоньше к краю
            float h = mix(0.10, 0.60, fbm2(w * 0.9 + sd + 5.0)) * (0.45 + 0.55 * clamp(1.0 - rho / 0.8, 0.0, 1.0));
            float ci = abs(dot(d, nn));
            float si = sqrt(max(0.0, 1.0 - ci * ci));
            float crit = 1.0 / nh;
            float tir = smoothstep(crit - 0.04, crit + 0.04, si);
            float cosT = sqrt(max(0.0, 1.0 - nh * nh * si * si));
            float Fr = min(1.0, fresnel(ci, nh, 1.0) * 1.8);
            float R = mix(Fr * (0.5 + 1.0 * film_ch(h, cosT, ch)), 1.0, tir);
            R = clamp(R + stepLine * 0.35, 0.0, 1.0);
            vec3 rdir = reflect(d, nn);
            float glint = pow(max(dot(rdir, -pbd), 0.0), 6.0);
            float lightR = plit * glint + plit * 0.08 * psideW + env(u_rot * rdir)[ch] * 0.10;
            acc += thr * m * kk * R * lightR;
            thr *= 1.0 - m * kk * clamp(0.20 + 0.75 * R, 0.0, 0.95);
        } else if (kq < 8.5) {
            // ---- отпечаток (залеченная трещина): кружево из капель ----
            float rho = length(uv);
            float shape = rho + 0.40 * (fbm2(uv * 1.4 + sd) - 0.5);
            float m = 1.0 - smoothstep(0.80 - bw, 0.80 + bw, shape);
            if (m <= 0.001) continue;
            float lace = smoothstep(0.40, 0.58, fbm2(uv * 1.9 + sd + 2.0));
            // сетка капель вытянута вдоль плоскости — «узор пальца»
            float sa = sd * 0.21;
            mat2 rot = mat2(cos(sa), -sin(sa), sin(sa), cos(sa));
            vec2 gv = rot * uv * vec2(16.0, 9.0) + vec2(3.0 * fbm2(uv * 2.0 + sd), 0.0);
            float rnd;
            float f1 = drops(gv, rnd);
            float rad = 0.16 + 0.20 * rnd;
            float drop = 1.0 - smoothstep(rad * 0.65, rad, f1);
            float edgeD = smoothstep(rad * 0.45, rad * 0.95, f1) * drop;   // тёмный обод капли
            float detail = clamp(blur / max(r, 1e-3) * 5.0, 0.0, 1.0);
            float cover = mix(drop, 0.30, detail) * lace * m * kk;
            float rimc = mix(edgeD, 0.25, detail) * lace * m * kk;
            float h = mix(0.2, 0.9, fbm2(uv * 2.3 + sd + 7.0));
            float ci = abs(dot(d, n));
            float filmC = film_ch(h, ci, ch);
            acc += thr * (plit * cover * (0.20 + 0.55 * filmC) * psideW + amb * cover * 0.5);
            thr *= 1.0 - clamp(rimc * 0.55 * max(relief, 0.5) + cover * 0.12, 0.0, 0.8);
        } else {
            // ---- ореол напряжения вокруг кристаллика: круглый диск с кольцами ----
            float rho = length(uv);
            float m = (1.0 - smoothstep(0.92 - bw, 0.92 + bw, rho + 0.06 * (vnoise(uv * 6.0 + sd) - 0.5)))
                      * smoothstep(0.08, 0.16, rho);
            if (m <= 0.001) continue;
            float rings = 0.5 + 0.5 * cos(rho * PI * 7.0 + 0.6 * vnoise(uv * 4.0 + sd));
            float h = mix(0.10, 0.45, rho);
            float ci = abs(dot(d, n));
            float Fr = min(1.0, fresnel(ci, nh, 1.0) * 1.8);
            float R = clamp(Fr * (0.4 + 1.6 * film_ch(h, ci, ch)) * (0.55 + 0.45 * rings), 0.0, 1.0);
            vec3 rdir = reflect(d, n);
            float glint = pow(max(dot(rdir, -pbd), 0.0), 5.0);
            acc += thr * m * kk * (R * (plit * glint + env(u_rot * rdir)[ch] * 0.10) + plit * 0.05 * psideW * rings);
            thr *= 1.0 - m * kk * clamp(0.10 + 0.6 * R + 0.15 * rings, 0.0, 0.85);
        }
    }
}

// ============================================================
//  Порода вокруг кристалла
// ============================================================
bool rock_hit(vec3 ro, vec3 rd, out float tin, out int fi) {
    tin = -1e9;
    fi = -1;
    float tout = 1e9;
    for (int i = 0; i < u_mn; i++) {
        vec3 n = u_mpl[i].xyz;
        float dn = dot(rd, n);
        float dist = u_mpl[i].w - dot(ro, n);
        if (abs(dn) < 1e-6) {
            if (dist < 0.0) return false;
            continue;
        }
        float t = dist / dn;
        if (dn < 0.0) {
            if (t > tin) { tin = t; fi = i; }
        } else {
            tout = min(tout, t);
        }
    }
    return fi >= 0 && tin < tout;
}

bool in_rock(vec3 p) {
    if (u_mn == 0) return false;
    for (int i = 0; i < u_mn; i++)
        if (dot(p, u_mpl[i].xyz) - u_mpl[i].w > 0.3) return false;
    return true;
}

vec3 rock_albedo(vec3 p) {
    float g = 0.6 * vnoise3(p * 0.35) + 0.4 * vnoise3(p * 0.9 + 3.0);   // мелкое зерно
    if (u_mrock == 0) {
        // белый мрамор: сахаристое зерно и серые прожилки
        float v = abs(sin(dot(p, vec3(0.031, 0.047, 0.022)) * 3.0 + 4.0 * vnoise3(p * 0.035)));
        vec3 c = vec3(0.86, 0.84, 0.80) * (0.92 + 0.10 * g);
        return mix(vec3(0.48, 0.48, 0.50), c, smoothstep(0.0, 0.18, v));
    }
    if (u_mrock == 1) {
        // пегматит: неровные зёрна белого полевого шпата, серого кварца, чёрной слюды
        float a = vnoise3(p * 0.09 + 1.7) * 0.7 + vnoise3(p * 0.21) * 0.3;
        float m = vnoise3(p * 0.16 + 9.0);
        vec3 c = a < 0.5 ? vec3(0.86, 0.82, 0.76) : vec3(0.56, 0.57, 0.60);
        c = mix(c, vec3(0.12, 0.11, 0.10), smoothstep(0.72, 0.76, m));
        return c * (0.88 + 0.16 * g);
    }
    if (u_mrock == 2) {
        // тёмная порода: базальт / сланец с редкими светлыми крапинами
        float sp = smoothstep(0.80, 0.84, vnoise3(p * 0.45 + 5.0));
        return mix(vec3(0.20, 0.20, 0.21), vec3(0.62, 0.60, 0.56), sp) * (0.85 + 0.25 * g);
    }
    // серая агатовая корка жеоды: тонкие полосы
    float b = sin(length(p.xy) * 0.35 + 2.0 * vnoise3(p * 0.04));
    return mix(vec3(0.42, 0.42, 0.45), vec3(0.62, 0.62, 0.64), 0.5 + 0.5 * b) * (0.9 + 0.12 * g);
}

vec3 rock_shade(vec3 p, vec3 rd, int fi) {
    vec3 N = u_mpl[fi].xyz;
    // неровная поверхность камня
    float e = 0.8;
    float h0 = vnoise3(p * 0.12);
    vec3 gr = vec3(vnoise3((p + vec3(e, 0.0, 0.0)) * 0.12) - h0,
                   vnoise3((p + vec3(0.0, e, 0.0)) * 0.12) - h0,
                   vnoise3((p + vec3(0.0, 0.0, e)) * 0.12) - h0) / e;
    N = normalize(N - (gr - N * dot(gr, N)) * 6.0);
    vec3 alb = rock_albedo(p);
    vec3 irr = studio_irr(p, N);
    vec3 L = normalize(u_lpos - p);
    float lit = flash_at(p) * max(dot(N, L), 0.0) / PI;
    float stainM = u_stain * smoothstep(0.45, 0.8, vnoise3(p * 0.05 + 11.0));
    alb = mix(alb, vec3(0.50, 0.30, 0.12), stainM * 0.7);
    return alb * (irr * 0.85 + lit * u_lcol + env_soft(u_rot * N) * 0.25);
}

// ============================================================
//  Сырьё под матовой коркой: свет входит, мутнеет, рассеивается на включениях.
// ============================================================
vec3 rough_inside(vec3 p0, vec3 rd, vec3 N, float F0, float frost) {
    vec3 outC = vec3(0.0);
    // матовая поверхность рассеивает луч на ~10–15°: пятно размытия ≈ 0.2 × глубина
    float blurK = 0.10 + 0.16 * frost;
    for (int ch = 0; ch < 3; ch++) {
        float ior = u_ior[ch];
        vec3 d = refract(rd, N, 1.0 / ior);
        if (dot(d, d) < 0.5) continue;
        vec3 p = p0 + d * 1e-4;
        float thr = (1.0 - F0) * (0.55 + 0.25 * (1.0 - frost));
        float acc = 0.0;
        for (int b = 0; b < 6; b++) {
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
            vec3 ab = u_absorb;
            if (u_cfon > 0)
                ab = (absorbAt(p + d * tmin * 0.17) + absorbAt(p + d * tmin * 0.5) + absorbAt(p + d * tmin * 0.83)) / 3.0;
            // свечение объёма от фонарика: собираем по трём пробам на отрезке
            float vb = 0.0;
            for (int s = 0; s < 3; s++) {
                vec3 ps = p + d * tmin * (0.2 + 0.3 * float(s));
                vb += flash_inside(ps) * exp(-ab[ch] * tmin * (0.2 + 0.3 * float(s)));
            }
            acc += thr * vb / 3.0 * u_lcol[ch] * (0.030 + 0.08 * u_damage) * tmin * 0.06 * (0.35 + 0.65 * tintAt(p)[ch]);
            if (u_ninc > 0) inclusions(p, d, tmin, ch, acc, thr, blurK, p0);
            thr *= exp(-ab[ch] * tmin);
            p += d * tmin;
            vec3 Nx = u_pl[j].xyz;
            if (in_rock(p)) {                            // кристалл упирается в породу: виден её отражённый свет
                acc += thr * rock_albedo(p)[ch] * 0.30 * u_env;   // светлая порода подсвечивает кристалл сзади
                break;
            }
            if (matte(u_kind[j])) {
                // дальняя матовая стенка светится тем, что за ней: фонарик сзади — пятно света
                float behind = flash_at(p) * 0.40 + flash_inside(p - Nx * 1.0) * 0.30;
                acc += thr * (behind * u_lcol[ch] + env_soft(u_rot * d)[ch] * 0.25) * (0.35 + 0.65 * tintAt(p)[ch]);
                break;
            }
            Nx = face_normal(Nx, p, j, 0.2);
            float ci = dot(d, Nx);
            float s2 = ior * ior * (1.0 - ci * ci);
            if (s2 >= 1.0) {
                d = reflect(d, Nx);
            } else {
                float Fx = fresnel(ci, ior, 1.0);
                vec3 out_d = refract(d, Nx, ior);
                acc += thr * (1.0 - Fx) * env_soft(u_rot * out_d)[ch] * 0.30;
                acc += thr * (1.0 - Fx) * flash_at(p) * u_lcol[ch] * 0.55;
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
    bool miss = false;
    for (int i = 0; i < u_n; i++) {
        vec3 n = u_pl[i].xyz;
        float dn = dot(rd, n);
        float dist = u_pl[i].w - dot(ro, n);
        if (abs(dn) < 1e-6) {
            if (dist < 0.0) { miss = true; break; }
            continue;
        }
        float t = dist / dn;
        if (dn < 0.0) {
            if (t > tin) { tin = t; ein = i; }
        } else {
            if (t < tout) tout = t;
        }
    }
    if (ein < 0 || tin >= tout) miss = true;
    // порода впереди кристалла (или кристалла на луче нет)
    if (u_mn > 0) {
        float tr;
        int fr;
        if (rock_hit(ro, rd, tr, fr) && (miss || tr < tin))
            return vec4(rock_shade(ro + rd * tr, rd, fr), 1.0);
    }
    if (miss) return vec4(0.0);

    vec3 p0 = ro + rd * tin;
    vec3 N = u_pl[ein].xyz;
    float k = u_kind[ein];
    // у старого излома своя степень затёртости (grit), у корки и шлифовки — общая
    float rough = (k > 1.5 && k < 2.5 && u_grit[ein] > 0.01) ? u_grit[ein]
                                                            : clamp(max(u_grit[ein], u_rough), 0.02, 1.0);
    float damage = clamp(u_damage, 0.0, 1.0);
    float polish = clamp(u_polish, 0.0, 1.0);
    float wet = clamp(u_wet, 0.0, 1.0);
    float scratch = u_scratches * smoothstep(0.72, 0.98, vnoise(vec2(p0.x + p0.z * 0.7, p0.y) * 0.12));

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

    float edge = 1e9;
    for (int i = 0; i < u_n; i++) {
        if (i == ein) continue;
        float d2 = u_pl[i].w - dot(p0, u_pl[i].xyz);
        float s = length(u_pl[i].xyz - N * dot(u_pl[i].xyz, N));
        if (s > 1e-3) edge = min(edge, d2 / s);
    }
    float edgeK = smooth_dome ? 1.0 : smoothstep(0.0, 1.6 / max(u_scale, 1.0), edge);

    vec3 tint = tintAt(p0) * pleoTint(rd);
    vec3 col = vec3(0.0);

    // ---- матовая поверхность: сырая корка, свежая шлифовка, рундист ----
    if (matte(k)) {
        bool crust = k > 1.5 && k < 2.5;
        bool pebble = crust && u_grit[ein] < 0.01;       // окатанная корка (у старых изломов grit задан)
        float roundR = crust ? u_round : 0.0;
        if (roundR > 0.5) N = rounded_normal(N, p0, ein, roundR);
        // окатанная корка неоднородна: где-то белее (ушибы, «сахар»), где-то прозрачнее
        float patchy = vnoise3(p0 * 0.07);
        float frost = clamp(rough * (0.75 + 0.45 * patchy), 0.0, 1.0);
        vec3 V = -rd;
        float F0 = fresnel(1.0, 1.0, u_ior.y);
        float NoV = max(dot(N, V), 1e-4);

        // Матовая поверхность сама белёсая: микросколы рассеивают свет до того,
        // как он войдёт в камень. Цвет тела виден сквозь неё, приглушённо.
        float white = 0.09 + 0.14 * frost + (pebble ? 0.07 * smoothstep(0.55, 0.85, vnoise3(p0 * 0.35 + 3.0)) : 0.0);
        vec3 irr = studio_irr(p0, N);
        vec3 surf = irr * white * vec3(0.95, 0.93, 0.90);
        // свет студии, вошедший в тело и вернувшийся: цвет камня, дважды прошедший
        // поглощение и приглушённый рассеянием в корке
        vec3 t2 = tint * tint;
        vec3 body = irr * mix(t2, vec3(dot(t2, vec3(0.3, 0.5, 0.2))), 0.35 * frost) * (0.26 + 0.20 * (1.0 - frost));
        vec3 amb = env_soft(u_rot * N) * (white * 0.8 + 0.18 * tint);

        // фонарик спереди/сбоку по поверхности
        vec3 L = normalize(u_lpos - p0);
        float NoL = max(dot(N, L), 0.0);
        float lit = flash_at(p0);
        vec3 fl = lit * u_lcol * (NoL / PI) * (white * 1.4 + 0.45 * tint * tint);
        // мягкий широкий блик матовой поверхности (у кромок — сильнее, по Френелю)
        float sheen = specular_ggx(N, V, L, 0.55 + 0.3 * frost, F0) * (1.0 - frost * 0.5);
        vec3 spec = u_lcol * lit * sheen * 0.6;
        // «сахар»: на корке вспыхивают отдельные микрограни
        float grain = 0.0;
        if (pebble && lit > 0.0 && NoL > 0.0) {
            vec3 cell = floor(p0 * 1.4);
            vec3 mn = normalize(N + (vec3(hash31(cell), hash31(cell + 1.3), hash31(cell + 2.7)) - 0.5) * 0.9);
            grain = pow(max(dot(reflect(-L, mn), V), 0.0), 40.0) * step(0.55, hash31(cell + 9.1));
        }
        spec += u_lcol * lit * grain * 0.35;
        vec3 fres = studio_light_rgb(p0, N, V, 0.6, vec3(0.0)) * 0.5;

        vec3 inner = rough_inside(p0, rd, N, F0, frost);
        // ржавый налёт (окислы железа) на старых изломах: пятнами и потёками, глушит просвет
        float stainM = 0.0;
        if (crust && u_stain > 0.0) {
            float s1 = vnoise3(p0 * 0.045 + 3.0);
            float s2 = vnoise3(vec3(p0.x * 0.02, p0.y * 0.02, p0.z * 0.11) + 7.0);   // потёки вдоль
            stainM = u_stain * smoothstep(0.42, 0.78, 0.6 * s1 + 0.4 * s2);
            inner *= 1.0 - 0.85 * stainM;
        }
        col = surf + body + amb + fl + spec + fres + inner * (0.65 + 0.35 * (1.0 - frost));
        if (stainM > 0.0) {
            vec3 rust = mix(vec3(0.42, 0.24, 0.08), vec3(0.62, 0.40, 0.14), vnoise3(p0 * 0.3));
            col = mix(col, rust * (irr * 0.7 + vec3(lit) * u_lcol * NoL * 0.3 + 0.03), stainM * 0.85);
        }
        col *= mix(0.80, 1.0, roundR > 0.5 ? 1.0 : edgeK);
        // свежая шлифовка (не корка) — заметно белее, как матовое стекло
        if (!crust && k < 1.5) col = mix(col, (irr + vec3(lit) * u_lcol) * 0.22 * mix(tint, vec3(1.0), 0.6), 0.35 * rough);
        return vec4(col, 1.0);
    }

    // ---- блестящая грань: полировка, природная грань, свежий скол ----
    if (k > 3.5) N = face_normal(N, p0, ein, 1.0);
    float blurK = k > 4.5 ? 0.07 : (k > 3.5 ? 0.025 : 0.0);
    float surfR = k > 4.5 ? 0.06 : (k > 3.5 ? 0.07 : max(rough, 0.03 + 0.08 * (1.0 - polish)));
    // У сырья с неровными природными гранями «огонь» размазан: рябь и ступеньки работают
    // как линзы и размножали бы цветные края. Огранка сохраняет полную дисперсию.
    float dispK = k > 3.5 ? 0.2 : 1.0;
    for (int ch = 0; ch < 3; ch++) {
        float ior = mix(u_ior.y, u_ior[ch], dispK);
        float cosi = -dot(rd, N);
        float F = fresnel(cosi, 1.0, ior);
        float lit = flash_at(p0);
        vec3 L = normalize(u_lpos - p0);
        float spec = specular_ggx(N, -rd, L, surfR, fresnel(1.0, 1.0, ior));
        float acc = F * env(u_rot * reflect(rd, N))[ch] + spec * lit * u_lcol[ch] * (1.0 + 0.35 * wet);
        vec3 studio = studio_light_rgb(p0, N, -rd, surfR, vec3(0.0));
        acc += studio[ch];
        acc += u_lcol[ch] * lit * scratch * 0.16;
        vec3 d = refract(rd, N, 1.0 / ior);
        vec3 p = p0 + d * 1e-4;
        float thr = 1.0 - F;
        acc += thr * lit * u_lcol[ch] * (0.04 + 0.10 * damage);

        for (int b = 0; b < 12; b++) {
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
            if (u_ninc > 0) inclusions(p, d, tmin, ch, acc, thr, blurK, p0);
            thr *= exp(-ab[ch] * tmin);
            float vol = (0.008 + 0.06 * damage) * (0.4 + 0.6 * tint[ch]);
            acc += thr * beam * u_lcol[ch] * vol;

            p += d * tmin;
            vec3 Nx = u_pl[j].xyz;
            if (in_rock(p)) {                            // кристалл упирается в породу: виден её отражённый свет
                acc += thr * rock_albedo(p)[ch] * 0.30 * u_env;   // светлая порода подсвечивает кристалл сзади
                thr = 0.0;
                break;
            }
            if (matte(u_kind[j])) {
                float behind = flash_at(p) * 0.40 + beam * 0.25;
                acc += thr * (behind * u_lcol[ch] + env_soft(u_rot * d)[ch] * 0.25) * (0.35 + 0.65 * tintAt(p)[ch]);
                thr = 0.0;
                break;
            }
            if (u_kind[j] > 3.5) Nx = face_normal(Nx, p, j, 0.2);
            float ci = dot(d, Nx);
            float s2 = ior * ior * (1.0 - ci * ci);
            if (s2 >= 1.0) {
                d = reflect(d, Nx);
            } else {
                float Fx = fresnel(ci, ior, 1.0);
                vec3 out_d = refract(d, Nx, ior);
                float outLit = flash_at(p);
                acc += thr * (1.0 - Fx) * env(u_rot * out_d)[ch] * 0.72;
                acc += thr * (1.0 - Fx) * outLit * u_lcol[ch] * 1.10;
                thr *= Fx;
                d = reflect(d, Nx);
            }
            p += d * 1e-4;
            if (thr < 0.01) break;
        }
        acc += thr * 0.04 * u_env;
        col[ch] = acc;
    }

    float haze = clamp(damage * 0.06, 0.0, 0.3);
    col = mix(col, tint * (0.10 + 0.18 * u_env), haze);
    col *= mix(0.65, 1.0, edgeK);
    return vec4(col, 1.0);
}

void main() {
    setup_beam();
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
