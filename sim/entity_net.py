"""Сеть «по сущностям»: токены юнитов, навыков, карты и общего → трансформер → тип действия и цель.

  юниты  [n, UF] + вид   ─ кодировщик юнита ─┐
  навыки [s, SF] + номер ─ кодировщик навыка ─┤
  карта  [MC, 11, 11]    ─ свёртки ─ токен ───┼─ трансформер (внимание: каждый токен смотрит на все) ─┐
  общее  [GF]            ─ кодировщик ────────┘                                                    │
                                                                                                    ▼
  контекст = выход(общий токен) ‖ выход(токен самого юнита)
  тип:   ждать / атака / шаг — из контекста; навык k — из контекста и выхода токена навыка k
  цель:  запрос q_тип (контекст + выход навыка или вектор типа)
         юнит  — указатель: q · ключ(выход токена юнита)            (атака, навык на врага/союзника)
         клетка — q · признаки клетки из свёрток карты 11×11         (шаг, навык на клетку)
  ценность — из контекста.

Вероятность хода = p(тип) · p(цель | тип); для PPO логарифмы складываются. Любое число юнитов и навыков (маска
пустых мест), любые признаки — по именам (adapt: веса переносятся на новый состав признаков).
"""
import numpy as np

from . import battle_obs as B

ARCH = {"d": 64, "heads": 4, "layers": 2, "ff": 128, "conv": 32, "kind_dim": 16, "skill_dim": 16,
        "gelu": "tanh"}        # GELU через tanh: в numpy (бойцы) вдвое быстрее точной формулы через erf


def _torch():
    import torch
    return torch


def make_net(dims, arch=None):
    torch = _torch()
    nn = torch.nn
    a = dict(ARCH, **(arch or {}))
    d, cv = a["d"], a["conv"]
    import functools
    G = functools.partial(nn.GELU, approximate=a["gelu"])
    act_fn = functools.partial(torch.nn.functional.gelu, approximate=a["gelu"])

    class EntityNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.dims, self.arch = dict(dims), a
            self.unit_in = nn.Linear(dims["unit"], d)
            self.kind_emb = nn.Embedding(dims["kinds"], d)
            self.unit_mlp = nn.Sequential(G(), nn.Linear(d, d))
            self.skill_in = nn.Linear(dims["skill"], d)
            self.skill_emb = nn.Embedding(dims["skills"], d)
            self.skill_mlp = nn.Sequential(G(), nn.Linear(d, d))
            self.map_in = nn.Conv2d(dims["map"], cv, 3, padding=1)
            self.map_conv = nn.Sequential(G(), nn.Conv2d(cv, cv, 3, padding=1), G())
            self.map_tok = nn.Linear(2 * cv, d)
            self.glob_in = nn.Linear(dims["glob"], d)
            self.tok_type = nn.Embedding(4, d)              # общий, юнит, навык, карта
            layer = nn.TransformerEncoderLayer(d, a["heads"], a["ff"], dropout=0.0, batch_first=True,
                                               norm_first=True, activation=act_fn)
            self.tr = nn.TransformerEncoder(layer, a["layers"], enable_nested_tensor=False)
            self.ctx = nn.Sequential(nn.Linear(2 * d, d), G())
            self.base_type = nn.Linear(d, B.T_SKILL)
            self.skill_type = nn.Sequential(nn.Linear(2 * d, d), G(), nn.Linear(d, 1))
            self.type_vec = nn.Embedding(B.T_SKILL, d)
            self.query = nn.Sequential(nn.Linear(2 * d, d), G(), nn.Linear(d, d))
            self.key = nn.Linear(d, d)
            self.cell_q = nn.Linear(d, cv)
            self.cell_f = nn.Conv2d(cv, cv, 1)
            self.v = nn.Sequential(nn.Linear(d, d), G(), nn.Linear(d, 1))

        def forward(self, ob):
            """ob — пачка (collate): units [B,U,UF], upad [B,U] (True — пусто), kinds, skills [B,S,SF], spad, sids,
            map [B,MC,11,11], glob [B,GF]. → type_logits [B,T], unit_logits [B,T,U], cell_logits [B,T,121], v [B]."""
            Bn, U = ob["units"].shape[:2]
            S = ob["skills"].shape[1]
            tt = self.tok_type.weight
            hu = self.unit_mlp(self.unit_in(ob["units"]) + self.kind_emb(ob["kinds"])) + tt[1]
            hs = self.skill_mlp(self.skill_in(ob["skills"]) + self.skill_emb(ob["sids"])) + tt[2]
            fm = self.map_conv(self.map_in(ob["map"]))                         # [B, cv, 11, 11]
            pooled = torch.cat([fm.mean((2, 3)), fm.amax((2, 3))], 1)
            hm = (self.map_tok(pooled) + tt[3])[:, None]
            hg = (self.glob_in(ob["glob"]) + tt[0])[:, None]
            x = torch.cat([hg, hm, hu, hs], 1)
            pad = torch.cat([torch.zeros(Bn, 2, dtype=torch.bool, device=x.device), ob["upad"], ob["spad"]], 1)
            y = self.tr(x, src_key_padding_mask=pad)
            g, me = y[:, 0], y[:, 2]                     # общий токен и первый юнит (сам наблюдатель)
            yu, ys = y[:, 2:2 + U], y[:, 2 + U:]
            ctx = self.ctx(torch.cat([g, me], -1))
            base = self.base_type(ctx)                                          # [B, 3]
            sk = self.skill_type(torch.cat([ctx[:, None].expand(-1, S, -1), ys], -1)).squeeze(-1)  # [B, S]
            max_s = self.arch.get("max_s", B.MAX_S)
            if S < max_s:
                sk = torch.cat([sk, sk.new_full((Bn, max_s - S), -1e9)], 1)
            type_logits = torch.cat([base, sk], 1)
            tv = torch.cat([self.type_vec.weight[None].expand(Bn, -1, -1), ys], 1)  # [B, 3+S, d]
            if S < max_s:
                tv = torch.cat([tv, tv.new_zeros(Bn, max_s - S, tv.shape[-1])], 1)
            q = self.query(torch.cat([ctx[:, None].expand(-1, tv.shape[1], -1), tv], -1))   # [B, T, d]
            k = self.key(yu)                                                    # [B, U, d]
            unit_logits = torch.einsum("btd,bud->btu", q, k) / (q.shape[-1] ** 0.5)
            cf = self.cell_f(fm).flatten(2)                                      # [B, cv, 121]
            cell_logits = torch.einsum("btc,bcn->btn", self.cell_q(q), cf) / (cf.shape[1] ** 0.5)
            return type_logits, unit_logits, cell_logits, self.v(ctx).squeeze(-1)

    return EntityNet()


# ---------- пачки ----------

OBS_KEYS = ("units", "kinds", "skills", "sids", "map", "glob", "tmask", "umask", "cmask", "ttype")


def limits(arch):
    """Размеры полного наблюдения из arch — для stack_rows/sample_row."""
    a = arch or {}
    return {k: a[k] for k in ("max_u", "max_s") if k in a}


def collate(obs_list, device="cpu", full=True, max_u=None, max_s=None, n_types=None):
    """Список наблюдений → тензоры с добивкой до общей длины. full — маски целей по всем типам (решение);
    иначе umask/cmask — только для выбранного типа (обучение: в образце хранится одна строка).
    max_u/max_s/n_types — размеры полного наблюдения (full_obs); по умолчанию — старые battle_obs."""
    torch = _torch()
    n = len(obs_list)
    U = max_u or B.MAX_U
    S = (max_s or B.MAX_S) if full else max(1, max(len(o["skills"]) for o in obs_list))   # решение — постоянная форма
    UF = obs_list[0]["units"].shape[1]
    SF = obs_list[0]["skills"].shape[1]
    units = np.zeros((n, U, UF), np.float32)
    upad = np.ones((n, U), bool)
    kinds = np.zeros((n, U), np.int64)
    sids = np.zeros((n, S), np.int64)
    spad = np.ones((n, S), bool)
    skills = np.zeros((n, S, SF), np.float32)
    for i, o in enumerate(obs_list):
        k = len(o["units"])
        units[i, :k] = o["units"]
        upad[i, :k] = False
        kinds[i, :k] = o["kinds"]
        s = len(o["skills"])
        if s:
            skills[i, :s] = o["skills"]
            sids[i, :s] = o["sids"]
            spad[i, :s] = False
    spad[:, 0] = False if S else spad[:, 0]          # хотя бы одно место — иначе внимание без ключей
    upad[:, 0] = False
    out = {"units": units, "upad": upad, "kinds": kinds, "skills": skills, "spad": spad, "sids": sids,
           "map": np.stack([o["map"] for o in obs_list]).astype(np.float32),
           "glob": np.stack([o["glob"] for o in obs_list]).astype(np.float32),
           "tmask": np.stack([o["tmask"] for o in obs_list])}
    if full:
        um = np.zeros((n, n_types or B.N_TYPES, U), bool)
        for i, o in enumerate(obs_list):
            um[i, :, :o["umask"].shape[1]] = o["umask"]
        out["umask"] = um
        out["cmask"] = np.stack([o["cmask"] for o in obs_list])
        out["ttype"] = np.stack([o["ttype"] for o in obs_list])
    return {k: torch.as_tensor(v, device=device) for k, v in out.items()}


# ---------- решение ----------

FAST_KEYS = ("units", "upad", "kinds", "skills", "spad", "sids", "map", "glob")


def fast(net):
    """Сеть для решений: TorchScript (трассировка с вшитыми весами) — на процессоре в ~1.3 раза быстрее.
    Веса сети поменялись — нужен новый fast(). Не вышло — обычная сеть."""
    torch = _torch()

    class Wrap(torch.nn.Module):
        def __init__(self, n):
            super().__init__()
            self.n = n

        def forward(self, units, upad, kinds, skills, spad, sids, map_, glob):
            return self.n({"units": units, "upad": upad, "kinds": kinds, "skills": skills, "spad": spad,
                           "sids": sids, "map": map_, "glob": glob})
    try:
        import warnings
        dims = net.dims
        a = net.arch
        U, S, side = a.get("max_u", B.MAX_U), a.get("max_s", B.MAX_S), a.get("side", B.SIDE)
        ex = {"units": torch.zeros(2, U, dims["unit"]), "upad": torch.zeros(2, U, dtype=torch.bool),
              "kinds": torch.zeros(2, U, dtype=torch.long), "skills": torch.zeros(2, S, dims["skill"]),
              "spad": torch.zeros(2, S, dtype=torch.bool), "sids": torch.zeros(2, S, dtype=torch.long),
              "map": torch.zeros(2, dims["map"], side, side), "glob": torch.zeros(2, dims["glob"])}
        was = net.training
        net.eval()
        with warnings.catch_warnings(), torch.inference_mode():
            warnings.simplefilter("ignore")
            tr = torch.jit.freeze(torch.jit.trace(Wrap(net), tuple(ex[k] for k in FAST_KEYS), check_trace=False))
        net.train(was)
        return lambda ob: tr(*(ob[k] for k in FAST_KEYS))
    except Exception:                                # noqa: BLE001
        return None


def act(net, obs_list, greedy=False, rng=None, fn=None):
    """Пачка наблюдений → [(тип, цель, logp, ценность, (вероятности типов, вероятности целей выбранного типа))].
    fn — ускоренная сеть из fast()."""
    torch = _torch()
    rng = rng or np.random.default_rng()
    with torch.inference_mode():
        ob = collate(obs_list, max_u=net.arch.get("max_u"), max_s=net.arch.get("max_s"),
                     n_types=net.arch.get("n_types"))
        tl, ul, cl, v = (fn or net)(ob)
        tl = tl.masked_fill(~ob["tmask"], -1e9)
        pt = torch.softmax(tl, -1).numpy()
        ul = ul.masked_fill(~ob["umask"], -1e9)
        cl = cl.masked_fill(~ob["cmask"], -1e9)
        pu = torch.softmax(ul, -1).numpy()
        pc = torch.softmax(cl, -1).numpy()
        v = v.numpy()
    out = []
    for i, o in enumerate(obs_list):
        p = pt[i]
        a = int(np.argmax(p)) if greedy else int(rng.choice(len(p), p=p / p.sum()))
        lp = float(np.log(p[a] + 1e-9))
        tt = o["ttype"][a]
        tgt, ptg = 0, None
        if a != B.T_HOLD and tt != B.TGT_NONE:
            ptg = pu[i, a] if tt == B.TGT_UNIT else pc[i, a]
            tgt = int(np.argmax(ptg)) if greedy else int(rng.choice(len(ptg), p=ptg / ptg.sum()))
            lp += float(np.log(ptg[tgt] + 1e-9))
        out.append((a, tgt, lp, float(v[i]), (p, ptg, pu[i], pc[i])))
    return out


def sample_row(obs, a, tgt):
    """Образец для обучения: наблюдение (float16) и маска целей только выбранного типа."""
    tt = int(obs["ttype"][a])
    um = np.zeros(obs["umask"].shape[1], bool)
    k = obs["umask"].shape[1]
    um[:k] = obs["umask"][a]
    return {"units": obs["units"].astype(np.float16), "kinds": obs["kinds"], "skills": obs["skills"].astype(np.float16),
            "sids": obs["sids"], "map": obs["map"].astype(np.float16), "glob": obs["glob"], "tmask": obs["tmask"],
            "um": um, "cm": obs["cmask"][a].copy(), "tt": tt if a != B.T_HOLD else B.TGT_NONE}


# ---------- обучение ----------

def logp_of(net, ob, a_type, a_tgt, um, cm, tt):
    """log p(тип, цель), энтропия (типа + цели) и ценность для пачки образцов."""
    torch = _torch()
    tl, ul, cl, v = net(ob)
    tl = tl.masked_fill(~ob["tmask"], -1e9)
    lpt = torch.log_softmax(tl, -1)
    ar = torch.arange(len(a_type), device=tl.device)
    lp = lpt[ar, a_type]
    ent = -(lpt.exp() * lpt.clamp(min=-30)).sum(-1)
    ul = ul[ar, a_type].masked_fill(~um, -1e9)
    cl = cl[ar, a_type].masked_fill(~cm, -1e9)
    lpu = torch.log_softmax(ul, -1)
    lpc = torch.log_softmax(cl, -1)
    is_u = tt == B.TGT_UNIT
    is_c = tt == B.TGT_CELL
    lp_tu = lpu.gather(1, a_tgt.clamp(max=ul.shape[1] - 1)[:, None]).squeeze(1)
    lp_tc = lpc.gather(1, a_tgt.clamp(max=cl.shape[1] - 1)[:, None]).squeeze(1)
    lp = lp + torch.where(is_u, lp_tu, torch.zeros_like(lp)) + torch.where(is_c, lp_tc, torch.zeros_like(lp))
    eu = -(lpu.exp() * lpu.clamp(min=-30)).sum(-1)
    ec = -(lpc.exp() * lpc.clamp(min=-30)).sum(-1)
    ent = ent + torch.where(is_u, eu, torch.zeros_like(ent)) + torch.where(is_c, ec, torch.zeros_like(ent))
    return lp, ent, v


def stack_rows(rows, max_u=None, max_s=None):
    """Образцы sample_row → пачка массивов одной формы (юниты до MAX_U, навыки до MAX_S, карта в uint8 с шагом
    1/127): так пачка быстро передаётся между процессами и разом уходит на видеокарту.
    max_u/max_s — размеры полного наблюдения (full_obs); по умолчанию — старые battle_obs."""
    n = len(rows)
    U, S = max_u or B.MAX_U, max_s or B.MAX_S
    UF, SF = rows[0]["units"].shape[1], rows[0]["skills"].shape[1]
    out = {"units": np.zeros((n, U, UF), np.float16), "upad": np.ones((n, U), bool), "kinds": np.zeros((n, U), np.int16),
           "skills": np.zeros((n, S, SF), np.float16), "spad": np.ones((n, S), bool), "sids": np.zeros((n, S), np.int16)}
    for i, r in enumerate(rows):
        k = len(r["units"])
        out["units"][i, :k] = r["units"]
        out["upad"][i, :k] = False
        out["kinds"][i, :k] = r["kinds"]
        s = len(r["skills"])
        out["skills"][i, :s] = r["skills"]
        out["sids"][i, :s] = r["sids"]
        out["spad"][i, :s] = False
    out["upad"][:, 0] = False
    out["spad"][:, 0] = False
    m = np.stack([r["map"] for r in rows]).astype(np.float32)
    out["map"] = np.clip(np.rint((m + 1) * 127), 0, 255).astype(np.uint8)
    out["glob"] = np.stack([r["glob"] for r in rows]).astype(np.float32)
    out["tmask"] = np.stack([r["tmask"] for r in rows])
    out["um"] = np.stack([r["um"] for r in rows])
    out["cm"] = np.stack([r["cm"] for r in rows])
    out["tt"] = np.array([r["tt"] for r in rows], np.int8)
    return out


def to_device(obs, device):
    """Пачка stack_rows → тензоры на устройстве (float16 → float32, карта uint8 → −1…1, номера → long)."""
    torch = _torch()
    t = {}
    for k, v in obs.items():
        x = torch.as_tensor(v, device=device)
        if k == "map":
            x = x.float() / 127 - 1
        elif x.dtype == torch.float16:
            x = x.float()
        elif x.dtype in (torch.int16, torch.int8):
            x = x.long()
        t[k] = x
    return t


def ppo_step(net, opt, batch, device="cpu", epochs=4, minibatch=512, clip=0.2, bc=0.5, ent=0.01, vf=0.5, vclip=None,
             pi=1.0):
    """PPO (+ подражание примерам) по пачке process(). → метрики.
    vclip — обрезка изменения ценности за шаг (как у политики); pi=0 — учить только критика (разогрев)."""
    torch = _torch()
    n = len(batch["a_type"])
    adv_all = np.asarray(batch["adv"], np.float32)
    nd = np.asarray(batch["demo"]) < 0.5
    if nd.sum() > 1:
        m, s = adv_all[nd].mean(), adv_all[nd].std() + 1e-6
        adv_all = (adv_all - m) / s
    obs = to_device(batch["obs"], device)                 # вся пачка — на устройство один раз
    col = {k: torch.as_tensor(np.asarray(batch[k]), device=device) for k in ("a_type", "a_tgt")}
    col.update({k: torch.as_tensor(np.asarray(v, np.float32), device=device) for k, v in
                (("logp", batch["logp"]), ("adv", adv_all), ("ret", batch["ret"]), ("demo", batch["demo"]),
                 ("val", batch.get("val", batch["ret"])))})
    net.train()
    stats = {"pi": 0.0, "v": 0.0, "ent": 0.0, "kl": 0.0, "clip": 0.0, "n": 0}
    for _ in range(epochs):
        perm = torch.randperm(n, device=device)
        for k in range(0, n, minibatch):
            idx = perm[k:k + minibatch]
            ob = {key: obs[key][idx] for key in ("units", "upad", "kinds", "skills", "spad", "sids", "map", "glob",
                                                  "tmask")}
            at, ag = col["a_type"][idx].long(), col["a_tgt"][idx].long()
            old, adv, ret, demo = col["logp"][idx], col["adv"][idx], col["ret"][idx], col["demo"][idx]
            lp, entropy, v = logp_of(net, ob, at, ag, obs["um"][idx], obs["cm"][idx], obs["tt"][idx])
            ratio = torch.exp((lp - old).clamp(-20, 20))
            pg = -torch.min(ratio * adv, torch.clamp(ratio, 1 - clip, 1 + clip) * adv)
            nd_t = 1 - demo
            pg = (pg * nd_t).sum() / torch.clamp(nd_t.sum(), min=1.0)
            bc_loss = (-lp * demo).sum() / torch.clamp(demo.sum(), min=1.0)
            vsq = (v - ret) ** 2
            if vclip:                                     # ценность не уходит дальше ±vclip от прежней за шаг
                v_old = col["val"][idx]
                vsq = torch.max(vsq, (v_old + (v - v_old).clamp(-vclip, vclip) - ret) ** 2)
            vl = (vsq * nd_t).sum() / torch.clamp(nd_t.sum(), min=1.0)
            e = entropy.mean()
            loss = pi * (pg - ent * e) + vf * vl + bc * bc_loss
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 0.5)
            opt.step()
            with torch.no_grad():
                stats["pi"] += float(pg)
                stats["v"] += float(vl)
                stats["ent"] += float(e)
                stats["kl"] += float(((old - lp) * nd_t).sum() / torch.clamp(nd_t.sum(), min=1.0))
                stats["clip"] += float((((ratio - 1).abs() > clip).float() * nd_t).sum() / torch.clamp(nd_t.sum(),
                                                                                                         min=1.0))
                stats["bc"] = stats.get("bc", 0.0) + float(bc_loss)
                stats["n"] += 1
    m = max(1, stats.pop("n"))
    return {k: v / m for k, v in stats.items()}


# ---------- перенос весов на новый состав признаков ----------

INPUTS = {"unit_in.weight": ("unit", 1), "kind_emb.weight": ("kinds", 0), "skill_in.weight": ("skill", 1),
          "skill_emb.weight": ("skills", 0), "map_in.weight": ("map", 1), "glob_in.weight": ("glob", 1)}


def adapt(state, old_names, new_names, fresh):
    """Веса сети, обученной на old_names, → под new_names: столбцы входов и строки словарей — по именам.
    Новые признаки — нулевые веса (сеть ведёт себя как раньше, пока не научится их использовать), новые виды и
    навыки — случайный вектор свежей сети."""
    torch = _torch()
    out = {}
    for k, w in state.items():
        if k not in INPUTS:
            out[k] = w
            continue
        group, axis = INPUTS[k]
        old, new = old_names.get(group, []), new_names[group]
        if list(old) == list(new):
            out[k] = w
            continue
        oi = {n: i for i, n in enumerate(old)}
        base = fresh[k].clone()
        if axis == 1:
            base.zero_() if group != "map" else base.mul_(0)
            for j, n in enumerate(new):
                if n in oi:
                    base[:, j] = w[:, oi[n]]
        else:
            for j, n in enumerate(new):
                if n in oi:
                    base[j] = w[oi[n]]
        out[k] = base
    _ = torch
    return out
