"""Лист иллюстраций из генератора (2×2 картинки на одном изображении) → assets/illustrations/<id>.png.

  python tools/import_illustrations.py лист.png --sheet 3 [--preview out.png]
  python tools/import_illustrations.py лист.png --names act_0,act_1,act_2,tavern

--sheet N — номер листа из SHEETS (порядок картинок на листе: слева направо, сверху вниз; промпты —
art_prompts.md, раздел «Иллюстрации экспедиции»). Каждая четверть листа обрезается по своей картинке (поля и
рамки генератора срезаются), уменьшается до 192×128 усреднением и получает общую ограниченную палитру —
так иллюстрации выглядят пиксель-артом одного стиля. В игре они растягиваются ×2.5 без сглаживания.
Рядом, в assets/illustrations/hd/, кладётся тот же кадр без уменьшения — его берут полноэкранные сцены
(события, акты, таверна, лагерь, торговец, итоги).
"""
import os
import sys

import numpy as np
import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "illustrations")
HD = os.path.join(OUT, "hd")        # те же кадры в исходном разрешении — для полноэкранных сцен
W, H = 192, 128
ORDER = [
    "act_0", "act_1", "act_2", "tavern",
    "camp", "shop", "victory", "defeat",
    "sunken_chest", "leeches", "drowning", "idol",
    "abandoned_camp", "bone_marsh", "spore_mushroom", "frog_merchant",
    "training", "fog_voices", "sunken_chapel", "sunken_chapel.belfry",
    "sunken_chapel.dive", "sunken_chapel.altar", "toad_bazaar", "toad_bazaar.market",
    "toad_bazaar.seer", "leech_master", "leech_master.talk", "smith_cart",
    "smith_rescue", "smith_debt", "witch_hut", "witch_hut.inside",
    "witch_envoy", "witch_price", "amber_glow", "magpie_nest",
    "grotto_entrance", "priest_wisps", "archer_ambush", "mage_gas",
    "guard_bridge", "druid_heron", "cryo_pond", "greedy_find",
    # события болота с последствиями (листы 11–18)
    "toad_prisoner", "poacher_return", "toad_tax", "toad_coronation",
    "drowned_bell", "bell_ringer", "plague_village", "village_feast",
    "village_mob", "mirror_pool", "hungry_spirit", "rival_party",
    "rival_finale", "ferryman", "sunken_library", "sunken_library.tome",
    "witch_hunters", "leech_egg", "leech_hatch", "fog_doubles",
    "amber_altar", "deserter", "wisp_lead", "wisp_hoard",
    "hag_riddle", "hag_riddle.deal", "frog_gambler", "croc_legend",
    "reed_child", "toad_wedding", "sunken_caravan", "moon_frog",
    # глава «Огненные кузни» (листы 19+; промпты — prompts_forge.md)
    "forge_act_0", "forge_act_1", "forge_act_2", "anvil",
    "slave_revolt", "revolt_rising", "revolt_end", "golem_core",
    "golem_awakening", "cult_initiation", "cult_ascension", "cold_anvil",
    "ghost_forge", "ash_nest", "chained_ifrit", "volcano_whisper",
    "forge_herald", "lava_dam", "cooling_cistern", "starsteel_vein",
    "molten_river", "overseer_bribe", "bellows_hall", "slag_merchant",
    "master_blueprints", "fire_trial", "trapped_miner", "salamander_nest",
    "hammer_duel", "golem_parts", "flame_preacher", "ash_storm",
    "broken_automaton", "heat_altar", "obsidian_mirror", "runaway_apprentice",
    "quench_bath", "smoke_signal", "slave_cache", "tribute_cart",
    "hot_springs", "master_contest", "old_armory", "fire_ale",
    "tunnel_collapse", "guild_contract", "contract_due", "lava_raft",
    "ember_orphans", "brass_oracle", "guild_feast", "guild_toll",
    "room_muster", "room_workshop", "room_yard", "room_fame",          # комнаты таверны (лист 32)
    "room_build", "room_cemetery", "room_library", "room_dorm",        # комнаты таверны (лист 33)
    "room_dorm_2", "room_dorm_3", "room_dorm_4", "room_dorm_5",        # комнаты общежития (лист 34)
    "yard_sky_low", "yard_sky_mid", "yard_sky_high", "room_dorm_6",    # небо двора слоями + чердак (лист 35)
    "ws_bench_jewel", "ws_bench_forge", "ws_bench_alchemy", "ws_bench_leather",   # верстаки мини-игр (лист 36)
    "room_market", "market_gems", "market_goods", "market_night",       # рынок (лист 37)
]
SHEETS = [ORDER[i:i + 4] for i in range(0, len(ORDER), 4)]


def content_box(a, x0, y0, x1, y1):
    """Рамка картинки внутри четверти: отрезаем однотонные поля по краям."""
    cell = a[y0:y1, x0:x1].astype(float)
    bg = np.median(np.concatenate([cell[0], cell[-1], cell[:, 0], cell[:, -1]]), axis=0)
    diff = np.abs(cell - bg).sum(-1) > 40
    rows = np.where(diff.mean(1) > 0.2)[0]
    cols = np.where(diff.mean(0) > 0.2)[0]
    if len(rows) < 10 or len(cols) < 10:
        return x0, y0, x1, y1
    return x0 + cols[0], y0 + rows[0], x0 + cols[-1] + 1, y0 + rows[-1] + 1


def fit_crop(x0, y0, x1, y1):
    """Обрезка под 3:2 по центру."""
    w, h = x1 - x0, y1 - y0
    if w / h > W / H:
        nw = int(h * W / H)
        x0 += (w - nw) // 2
        x1 = x0 + nw
    else:
        nh = int(w * H / W)
        y0 += (h - nh) // 2
        y1 = y0 + nh
    return x0, y0, x1, y1


def palette(px, k=40, iters=10, seed=0):
    rng = np.random.default_rng(seed)
    cent = px[rng.choice(len(px), min(k, len(px)), replace=False)].astype(float)
    for _ in range(iters):
        lab = np.argmin(((px[:, None, :] - cent[None]) ** 2).sum(-1), 1)
        for j in range(len(cent)):
            sel = px[lab == j]
            if len(sel):
                cent[j] = sel.mean(0)
    return cent


def run(src, names, preview=None, cols=2, rows=2):
    pygame.init()
    img = pygame.image.load(src)
    a = pygame.surfarray.array3d(img).transpose(1, 0, 2)
    hh, ww = a.shape[:2]
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(HD, exist_ok=True)
    smalls = []
    for i, name in enumerate(names):
        cx, cy = i % cols, i // cols
        box = content_box(a, ww * cx // cols, hh * cy // rows, ww * (cx + 1) // cols, hh * (cy + 1) // rows)
        x0, y0, x1, y1 = fit_crop(*box)
        sub = pygame.surfarray.make_surface(np.ascontiguousarray(a[y0:y1, x0:x1].transpose(1, 0, 2)))
        pygame.image.save(sub, os.path.join(HD, f"{name}.png"))
        small = pygame.transform.smoothscale(sub, (W, H))
        smalls.append((name, small))
    # общая палитра листа: иллюстрации одного листа — одна гамма
    allpx = np.concatenate([pygame.surfarray.array3d(s).reshape(-1, 3) for _, s in smalls]).astype(float)
    cent = palette(allpx[::7])
    out = []
    for name, s in smalls:
        px = pygame.surfarray.array3d(s).astype(float)
        lab = np.argmin(((px.reshape(-1, 3)[:, None, :] - cent[None]) ** 2).sum(-1), 1)
        q = cent[lab].reshape(px.shape).astype(np.uint8)
        surf = pygame.surfarray.make_surface(q)
        pygame.image.save(surf, os.path.join(OUT, f"{name}.png"))
        out.append(surf)
        print(f"{name}: {W}x{H}")
    if preview:
        sheet = pygame.Surface((W * 2 * len(out), H * 2))
        for k, s in enumerate(out):
            sheet.blit(pygame.transform.scale(s, (W * 2, H * 2)), (k * W * 2, 0))
        pygame.image.save(sheet, preview)


if __name__ == "__main__":
    argv = sys.argv[1:]
    opts = {}
    for flag in ("--sheet", "--names", "--preview"):
        if flag in argv:
            k = argv.index(flag)
            opts[flag] = argv[k + 1]
            del argv[k:k + 2]
    if not argv or not ("--sheet" in opts or "--names" in opts):
        print(__doc__)
        for i, sh in enumerate(SHEETS):
            print(f"  лист {i}: {', '.join(sh)}")
        raise SystemExit(1)
    names = opts["--names"].split(",") if "--names" in opts else SHEETS[int(opts["--sheet"])]
    run(argv[0], names, opts.get("--preview"))
