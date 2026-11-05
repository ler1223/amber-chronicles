"""Лист спрайтов из генератора (ChatGPT, все персонажи на одной картинке, пурпурный фон) → спрайты игры.

  python tools/import_sheet.py лист.png [папка] [--set ch12] [--preview out.png] [--res 2]

--res 2 — модели высокой детализации (холст и рост фигуры ×2, по умолчанию в assets/sprites/x2): игра берёт их
при настройке «Детализация моделей: высокая», а если файла нет — обычный спрайт.

--set — какой это лист (порядок фигур на нём, см. SETS и prompts_more.md): ch12, heroes2, crypt_pass, steppe_tomb,
fae_sunken, citadel, objects, env1, env2. Папка по умолчанию — assets/sprites (у окружения — assets/sprites/env).

Картинка генератора — не настоящий пиксель-арт (нет ровной сетки, есть шум), поэтому каждый персонаж:
  1. вырезается по своей связной области (соседи с перекрытым оружием не попадают), мелкие оторванные кусочки
     (огоньки, кристаллы, искры) приклеиваются к ближайшему персонажу;
  2. край отступает на 2 пикселя (пурпурная кайма фона не попадает в цвет);
  3. уменьшается усреднением в общем масштабе (персонажи сохраняют рост относительно друг друга), элита и
     боссы — в свой холст;
  4. палитра урезается (k-средних), снаружи добавляется тёмный контур в 1 пиксель;
  5. ставится ногами на нижний ряд, по центру холста.
Порядок на листе — как в запросе (prompts_more.md, первый лист — art_prompts.md): ряды сверху вниз, в ряду слева
направо. Окружение (env1, env2) не держит общий масштаб: каждый предмет вписывается в свой холст (дерево выше камня).
"""
import os
import sys

import numpy as np
import pygame

ORDER = ["warrior", "mage", "priest", "archer", "guardian", "cryo", "assassin", "druid", "druid_bear",
         "slime", "bog_archer", "beetle", "frog_shaman", "slime_king", "ice_witch",
         "fire_imp", "salamander", "hammer_thrower", "flame_priest", "magma_golem", "forge_overseer", "forge_lord"]
ENV1 = ["grass_block", "grass_log", "grass_tree", "grass_bush", "grass_rock",
        "ash_block", "ash_log", "ash_rock", "ash_deadtree",
        "dirt_block", "dirt_log", "dirt_tombstone", "dirt_deadtree", "dirt_rock",
        "snow_block", "snow_log", "snow_pine", "snow_rock"]
ENV2 = ["dry_block", "dry_log", "dry_bush", "dry_rock",
        "sand_block", "sand_log", "sand_column", "sand_rock",
        "moss_block", "moss_log", "moss_mushroom", "moss_tree",
        "wet_block", "wet_log", "wet_column", "wet_rock",
        "marble_block", "marble_log", "marble_column", "marble_rock"]
SETS = {
    "ch12": ORDER,
    "heroes2": ["shaman", "bard", "alchemist", "ram", "trapper", "necro", "chrono",
                "gravity", "geomancer", "brewer", "bloodrager", "tactician", "binder",
                "druid_wolf", "spirit_tree", "ent", "totem_storm", "totem_heal", "skeleton_minion", "decoy"],
    "crypt_pass": ["toxic_slime", "bog_horror", "obsidian_guard", "living_lava",
                   "skeleton", "skeleton_archer", "ghoul", "necromancer", "banshee", "bone_golem", "wraith",
                   "death_knight", "lich",
                   "frost_wolf", "yeti", "ice_archer", "frost_shaman", "ice_golem", "frost_wyrmling",
                   "yeti_alpha", "frost_giant"],
    "steppe_tomb": ["raider", "storm_hawk", "stormcaller", "steppe_ogre", "thunder_elemental", "wind_rider",
                    "warchief", "storm_khan",
                    "mummy", "scarab", "tomb_archer", "sand_priest", "sarcophagus", "sand_golem", "anubis_guard",
                    "tomb_guardian", "pharaoh"],
    "fae_sunken": ["sprite", "thorn_beast", "illusionist", "maneater", "dryad", "treant", "shade_fae",
                   "fae_knight", "fae_queen",
                   "drowned", "eel", "siren", "crab_knight", "deep_priest", "kraken_arm",
                   "drowned_captain", "deep_lord"],
    "citadel": ["sky_knight", "harpy", "sentinel", "seraph", "arcanist", "griffin", "void_watcher",
                "storm_paladin", "archon"],
    "objects": ["barrel_powder", "barrel_oil", "barrel_big", "boulder", "nest", "hearth",
                "ice_idol", "raider_tent", "hive", "witch_ring", "conch", "anchor", "cart", "prisoner",
                "ward_torch", "caravan", "lightning_rod", "glow_tree", "bell", "sky_bridge", "bone_wall"],
    "env1": ENV1,
    "env2": ENV2,
    "swamp_new": ["mosquito_swarm", "bog_croc", "spore_shroom", "toad_spearman", "bog_hag", "will_wisp",
                  "elder_leech", "mire_king", "toad_queen"],
    "forge_events": ["slag_slave", "ember_hound", "bellows_keeper", "chain_smith", "ash_wraith",
                     "cinder_caster", "cult_zealot", "crucible_golem", "free_golem", "magma_vent",
                     "overseer_groh", "crucible_titan", "volcano_heart", "smith_ghost", "ash_wyrm"],
    "icons_forge": ["map_anvil", "map_ash", "mat_ore", "mat_obsidian", "mat_starsteel", "mat_emberheart",
                    "unique_starforged_blade", "unique_obsidian_aegis", "unique_ember_crown", "unique_volcano_maul",
                    "unique_magma_bow", "unique_forge_heart_ring"],
    "icons_gifts2": ["gift_iron_will", "gift_quick_hands", "gift_sharp_eye", "gift_deep_focus", "gift_ghoul_kiss", "gift_ap_spring", "gift_glass_cannon", "gift_thorn_skin", "gift_last_stand", "gift_fire_soul", "gift_frost_soul", "gift_storm_soul", "gift_elusive_step", "gift_bloodlust", "gift_wide_soul", "gift_giant_slayer", "gift_berserk_blood", "gift_steel_shell", "gift_far_sight", "gift_leech_arrows", "gift_arcane_flow", "gift_spellsurge"],
    "icons_gifts3": ["gift_kind_hands", "gift_warden", "gift_duel_honor", "gift_hot_string", "gift_flame_heart", "gift_undying_faith", "gift_knife_back", "gift_pack_call", "gift_spear_wall", "gift_ancestor_voice", "gift_perfect_pitch", "gift_double_charge", "gift_battering", "gift_prey", "gift_ice_bastion", "gift_bone_lord", "gift_spare_time", "gift_star_weight", "gift_mountain_roots", "gift_strong_brew", "gift_blood_thirst", "gift_marshal", "gift_fate_threads"],
    "icons_items2": ["item_dagger", "item_hammer", "item_wand", "item_leather", "item_cloak", "item_idol", "item_signet", "unique_thunder_maul", "unique_widow_dagger", "unique_frost_wand", "unique_ember_wand", "unique_mirror_cloak", "unique_leech_vest", "unique_hunter_cloak", "unique_thorn_crown", "unique_war_drum"],
    "icons_items3": ["unique_phoenix_feather", "unique_gambler_ring", "unique_king_seal", "unique_eel_band", "unique_marsh_lantern", "unique_toad_crown", "unique_storm_bow", "unique_bone_staff", "unique_headsman_axe", "unique_warden_plate", "unique_serpent_ring", "unique_sun_amulet", "unique_instant_ring", "unique_ash_cloak", "unique_tide_wand", "unique_obsidian_knife"],
    "icons_map": ["map_battle", "map_elite", "map_boss", "map_event", "map_camp", "map_shop", "map_thread"],
    "swamp_events": ["poacher", "reed_militia", "rust_merc", "rust_captain", "witch_hunter",
                     "fog_double", "bell_ringer", "old_tooth", "leech_mother", "kvaks"],
    "necro_time": ["corpse_1", "corpse_2", "corpse_3", "corpse_4",
                   "skeleton_minion_1", "skeleton_minion_2", "skeleton_minion_3", "skeleton_minion_4",
                   "fx_hourglass"],
    "icons_items": ["item_blade", "item_staff", "item_axe", "item_bow", "item_mail", "item_robe", "item_plate", "item_charm", "item_fang", "item_totem", "item_band", "item_loop", "item_seal", "unique_slime_crown", "unique_toad_staff", "unique_witch_ring", "unique_horror_hide", "unique_drowned_lamp", "unique_mire_fang", "unique_beetle_seal", "unique_reed_cloak", "unique_shaman_drum", "unique_cattail_bolt"],
    "icons_gifts": ["gift_amber_blood", "gift_master_hand", "gift_word_power", "gift_second_wind", "gift_reactor", "gift_wet_hunter", "gift_mire_fury", "gift_living_wall", "gift_ash_heart", "gift_permafrost", "gift_holy_spring", "gift_heron_eye", "gift_reed_shadow", "gift_bog_roots", "gift_witch_gift", "gift_amber_heart", "gift_leech_bond"],
}
ELITE = {"slime_king", "forge_overseer", "death_knight", "yeti_alpha", "warchief", "tomb_guardian", "fae_knight",
         "drowned_captain", "storm_paladin", "rust_captain", "crucible_golem"}
BOSS = {"ice_witch", "forge_lord", "lich", "frost_giant", "storm_khan", "pharaoh", "fae_queen", "deep_lord",
        "archon", "mire_king", "toad_queen", "bell_ringer", "old_tooth", "leech_mother", "kvaks",
        "overseer_groh", "crucible_titan", "volcano_heart", "smith_ghost", "ash_wyrm"}
CANVAS = {**{n: 40 for n in ELITE}, **{n: 48 for n in BOSS}}   # элита ×2 = 80, боссы = 96
ENV_SIZE = {"tree": (32, 46), "pine": (28, 48), "deadtree": (28, 40), "column": (20, 46), "block": (36, 34),
            "log": (34, 18), "bush": (24, 16), "rock": (24, 18), "tombstone": (16, 20), "mushroom": (22, 26)}
MATERIALS = ("grass", "ash", "dirt", "snow", "dry", "sand", "moss", "wet", "marble")
FIT = {"druid_bear"}            # растянуть до холста (облик медведя — крупный зверь)
MAGENTA = np.array([245, 5, 245])


def canvas(name):
    """Холст спрайта (ширина, высота) и вписывать ли фигуру в свой холст (иначе — общий масштаб листа)."""
    mat, _, kind = name.partition("_")
    if mat in MATERIALS and kind in ENV_SIZE:
        return ENV_SIZE[kind], True
    if name == "magma_vent":                           # жерло — низкий холмик в обычном холсте (ноги внизу)
        return (32, 32), True
    if name.startswith("corpse_"):                     # лежащий скелет — шире, чем выше
        return (40, 24), True
    if name == "fx_hourglass":                         # песочные часы вокруг юнита
        return (40, 56), True
    if mat in ("item", "unique", "gift", "map"):         # иконки 32×32, каждая вписывается в свой холст
        return (32, 32), True
    n = CANVAS.get(name, 32)
    return (n, n), name in CANVAS or name in FIT


def components(fg):
    h, w = fg.shape
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    al = pygame.surfarray.pixels_alpha(surf)
    al[:] = fg.T * 255
    del al
    comps = pygame.mask.from_surface(surf).connected_components(20)
    out = []
    for c in comps:
        m = pygame.surfarray.array_alpha(c.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))) > 0
        out.append((c.get_bounding_rects()[0], m.T, c.count()))
    return out


def erode(m, n):
    for _ in range(n):
        m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    return m


def kmeans(px, k, iters=12, seed=0):
    rng = np.random.default_rng(seed)
    k = min(k, len(px))
    cent = px[rng.choice(len(px), k, replace=False)].astype(float)
    for _ in range(iters):
        lab = np.argmin(((px[:, None, :] - cent[None]) ** 2).sum(-1), 1)
        for j in range(k):
            sel = px[lab == j]
            if len(sel):
                cent[j] = sel.mean(0)
    return cent, lab


def shrink(rgb, mask, scale):
    """Усреднение с учётом прозрачности: цвет считается только по закрашенным пикселям."""
    h, w = mask.shape
    nh, nw = max(1, round(h * scale)), max(1, round(w * scale))
    ys = (np.arange(nh + 1) * h / nh).astype(int)
    xs = (np.arange(nw + 1) * w / nw).astype(int)
    out = np.zeros((nh, nw, 3))
    cov = np.zeros((nh, nw))
    cs = np.cumsum(np.cumsum(np.pad(rgb * mask[..., None], ((1, 0), (1, 0), (0, 0))), 0), 1)
    ms = np.cumsum(np.cumsum(np.pad(mask.astype(float), ((1, 0), (1, 0))), 0), 1)
    for i in range(nh):
        for j in range(nw):
            y0, y1, x0, x1 = ys[i], ys[i + 1], xs[j], xs[j + 1]
            n = ms[y1, x1] - ms[y0, x1] - ms[y1, x0] + ms[y0, x0]
            area = max(1, (y1 - y0) * (x1 - x0))
            cov[i, j] = n / area
            if n:
                out[i, j] = (cs[y1, x1] - cs[y0, x1] - cs[y1, x0] + cs[y0, x0]) / n
    return out, cov


def make_sprite(rgb, mask, size, scale, colors=22):
    """size — (ширина, высота) холста."""
    sw, sh = size
    small, cov = shrink(rgb, mask, scale)
    alpha = cov > 0.42
    if not alpha.any():
        return None
    px = small[alpha]
    cent, lab = kmeans(px, colors)
    small[alpha] = cent[lab]
    # контур снаружи: прозрачный сосед закрашенного — тёмный цвет соседа
    pad_a = np.pad(alpha, 1)
    pad_c = np.pad(small, ((1, 1), (1, 1), (0, 0)))
    out_a = pad_a.copy()
    out_c = pad_c.copy()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = np.roll(np.roll(pad_a, dy, 0), dx, 1)
        nc = np.roll(np.roll(pad_c, dy, 0), dx, 1)
        edge = nb & ~out_a
        out_c[edge] = nc[edge] * 0.28 + np.array([12, 8, 16]) * 0.72
        out_a |= edge
    ys, xs = np.nonzero(out_a)
    out_a = out_a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    out_c = out_c[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    ch, cw = out_a.shape
    if ch > sh or cw > sw:                           # не влезло — ещё раз чуть мельче
        return make_sprite(rgb, mask, size, scale * min(sh / ch, sw / cw) * 0.97, colors)
    out = np.zeros((sh, sw, 4), np.uint8)
    y0, x0 = sh - ch, (sw - cw) // 2
    out[y0:, x0:x0 + cw, :3] = np.clip(out_c, 0, 255)
    out[y0:, x0:x0 + cw, 3] = out_a * 255
    return out


def rows(rects):
    """Порядок фигур: ряды сверху вниз (по нижнему краю), в ряду — слева направо."""
    med = float(np.median([r.h for r in rects]))
    out, row, base = [], [], None
    for i in sorted(range(len(rects)), key=lambda i: rects[i].bottom):
        if row and rects[i].bottom - base > med * 0.5:
            out += sorted(row, key=lambda j: rects[j].left)
            row = []
        if not row:
            base = rects[i].bottom
        row.append(i)
    return out + sorted(row, key=lambda j: rects[j].left)


def run(src, folder, preview=None, names=ORDER, res=1):
    pygame.init()
    img = pygame.image.load(src)
    a = pygame.surfarray.array3d(img).transpose(1, 0, 2).astype(float)
    fg = np.abs(a - MAGENTA).sum(-1) > 120
    if names and all(canvas(n)[1] and n.partition("_")[0] in ("item", "unique", "gift", "map", "mat") for n in names):
        # иконки: искры, ноты, кольца и пары предметов — части одной иконки; склеиваем их расширенной маской
        # радиус склейки — самый большой, при котором иконок на листе ровно столько, сколько ждём
        comps = None
        for steps in (14, 10, 7, 4, 0):
            grow = fg.copy()
            for _ in range(steps):
                grow = grow | np.roll(grow, 1, 0) | np.roll(grow, -1, 0) | np.roll(grow, 1, 1) | np.roll(grow, -1, 1)
            cand = []
            for r, m, _ in components(grow):
                m = m & fg
                cand.append((r, m, int(m.sum())))
            cand.sort(key=lambda c: c[2], reverse=True)
            if comps is None:
                comps = cand
            if sum(1 for c in cand if c[2] > 1500) == len(names):
                comps = cand
                break
    else:
        comps = sorted(components(fg), key=lambda c: c[2], reverse=True)
    big = [c for c in comps[:len(names)] if c[2] > 1500]
    if len(big) != len(names):
        raise SystemExit(f"на листе {len(big)} фигур, ожидалось {len(names)}")
    small = comps[len(names):]
    masks = [c[1].copy() for c in big]
    pts = []                                           # пиксели каждой фигуры (через 3) — для поиска ближайшей
    for b in big:
        ys, xs = np.nonzero(b[1][::3, ::3])
        pts.append(np.stack([xs * 3, ys * 3], 1))
    for r, m, _ in small:                              # огоньки и кристаллы — к ближайшей фигуре по её пикселям
        c = np.array([r.centerx, r.centery])
        d = [np.min(np.abs(p - c).sum(1)) for p in pts]
        i = int(np.argmin(d))
        if d[i] < 70:
            masks[i] |= m
    order = rows([b[0] for b in big])
    # общий масштаб: рост обычной фигуры листа (верхняя четверть по росту) → 29 пикселей спрайта
    plain = [big[i][0].h for name, i in zip(names, order) if not canvas(name)[1]]
    hero_h = float(np.percentile(plain, 75)) if plain else 230.0
    os.makedirs(folder, exist_ok=True)
    out = {}
    for name, i in zip(names, order):
        r = big[i][0]
        mask = erode(masks[i], 2)[r.top:r.bottom, r.left:r.right]
        rgb = a[r.top:r.bottom, r.left:r.right]
        (sw, sh), fit = canvas(name)
        sw, sh = sw * res, sh * res
        scale = min((sw - 2) / r.w, (sh - 2) / r.h) if fit else 29 * res / hero_h
        spr = make_sprite(rgb, mask, (sw, sh), scale, colors=22 if res == 1 else 30)
        surf = pygame.image.frombuffer(np.ascontiguousarray(spr).tobytes(), (sw, sh), "RGBA").copy()
        pygame.image.save(surf, os.path.join(folder, f"{name}.png"))
        out[name] = surf
        print(f"{name}: {sw}x{sh}")
    if preview:
        sheet = pygame.Surface((len(out) * 100, 220))
        sheet.fill((46, 70, 48))
        for k, (name, s) in enumerate(out.items()):
            kk = max(1, 96 // s.get_height()) if s.get_height() > 32 else 2
            big2 = pygame.transform.scale(s, (s.get_width() * kk, s.get_height() * kk))
            sheet.blit(big2, (k * 100 + 50 - big2.get_width() // 2, 200 - big2.get_height()))
        pygame.image.save(sheet, preview)


if __name__ == "__main__":
    argv = sys.argv[1:]
    opts = {}
    for flag in ("--preview", "--set", "--res"):
        if flag in argv:
            k = argv.index(flag)
            opts[flag] = argv[k + 1]
            del argv[k:k + 2]
    which = opts.get("--set", "ch12")
    if not argv or which not in SETS:
        print(__doc__)
        raise SystemExit(1)
    res = int(opts.get("--res", 1))
    default = ("assets/sprites/env" if which.startswith("env") else
               "assets/icons" if which.startswith("icons") else "assets/sprites")
    if res > 1:
        default = os.path.join(default, f"x{res}")
    run(argv[0], argv[1] if len(argv) > 1 else default, opts.get("--preview"), SETS[which], res)
