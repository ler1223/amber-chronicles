"""Сеть EntityNet на numpy — для процессов-бойцов лаборатории и окна: без torch.

torch с CUDA-библиотеками занимает в каждом процессе ~0.85 ГБ, а бойцу нужен только прямой проход маленькой сети.
Здесь те же формулы, что в entity_net.EntityNet.forward (проверено тестом: расхождение ~1e-5), веса — словарь
numpy-массивов из state_dict. Файл весов для бойцов — .npz (save/lab/live/weights_<версия>.npz).
"""
import json

import numpy as np

from . import battle_obs as B


def _erf(x):
    """erf (Абрамовиц и Стиган 7.1.26, ошибка < 1.5e-7): в numpy своего нет."""
    s = np.sign(x)
    a = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * a)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * \
        np.exp(-a * a)
    return s * y


def _gelu_erf(x):
    return 0.5 * x * (1.0 + _erf(x * 0.7071067811865476))


def _gelu_tanh(x):
    return 0.5 * x * (1.0 + np.tanh(0.7978845608028654 * (x + 0.044715 * x * x * x)))


_gelu = _gelu_tanh


def _lin(P, name, x):
    return x @ P[name + ".weight"].T + P[name + ".bias"]


def _ln(P, name, x):
    m = x.mean(-1, keepdims=True)
    v = ((x - m) ** 2).mean(-1, keepdims=True)
    return (x - m) / np.sqrt(v + 1e-5) * P[name + ".weight"] + P[name + ".bias"]


def softmax(x):
    x = x - x.max(-1, keepdims=True)
    e = np.exp(x)
    return e / e.sum(-1, keepdims=True)


def _conv3(P, name, x):
    """Свёртка 3×3 с полями 1 через im2col: [B, C, H, W] → [B, O, H, W]."""
    w = P[name + ".weight"]
    O, C = w.shape[:2]
    Bn, _, H, W = x.shape
    xp = np.pad(x, ((0, 0), (0, 0), (1, 1), (1, 1)))
    cols = np.empty((Bn, C, 3, 3, H, W), np.float32)
    for ky in range(3):
        for kx in range(3):
            cols[:, :, ky, kx] = xp[:, :, ky:ky + H, kx:kx + W]
    out = w.reshape(O, C * 9) @ cols.reshape(Bn, C * 9, H * W)
    return (out + P[name + ".bias"][None, :, None]).reshape(Bn, O, H, W)


def forward(P, arch, ob):
    """Прямой проход: те же выходы, что EntityNet.forward — логиты типа [B,T], юнита [B,T,U], клетки [B,T,121],
    ценность [B]."""
    global _gelu
    _gelu = _gelu_erf if arch.get("gelu", "tanh") == "none" else _gelu_tanh
    d, heads = arch["d"], arch["heads"]
    Bn, U = ob["units"].shape[:2]
    S = ob["skills"].shape[1]
    tt = P["tok_type.weight"]
    hu = _lin(P, "unit_mlp.1", _gelu(_lin(P, "unit_in", ob["units"]) + P["kind_emb.weight"][ob["kinds"]])) + tt[1]
    hs = _lin(P, "skill_mlp.1", _gelu(_lin(P, "skill_in", ob["skills"]) + P["skill_emb.weight"][ob["sids"]])) + tt[2]
    fm = _gelu(_conv3(P, "map_conv.1", _gelu(_conv3(P, "map_in", ob["map"]))))
    pooled = np.concatenate([fm.mean((2, 3)), fm.max((2, 3))], 1)
    hm = (_lin(P, "map_tok", pooled) + tt[3])[:, None]
    hg = (_lin(P, "glob_in", ob["glob"]) + tt[0])[:, None]
    x = np.concatenate([hg, hm, hu, hs], 1)
    pad = np.concatenate([np.zeros((Bn, 2), bool), ob["upad"], ob["spad"]], 1)
    neg = np.where(pad, -np.inf, 0.0).astype(np.float32)[:, None, None, :]
    hd = d // heads

    def split(z):
        return z.reshape(Bn, -1, heads, hd).transpose(0, 2, 1, 3)
    for i in range(arch["layers"]):
        p = f"tr.layers.{i}."
        h = _ln(P, p + "norm1", x)
        q, k, v = np.split(h @ P[p + "self_attn.in_proj_weight"].T + P[p + "self_attn.in_proj_bias"], 3, -1)
        q, k, v = split(q), split(k), split(v)
        att = softmax(q @ k.transpose(0, 1, 3, 2) / np.sqrt(hd) + neg)
        o = (att @ v).transpose(0, 2, 1, 3).reshape(Bn, -1, d)
        x = x + _lin(P, p + "self_attn.out_proj", o)
        x = x + _lin(P, p + "linear2", _gelu(_lin(P, p + "linear1", _ln(P, p + "norm2", x))))
    g, me = x[:, 0], x[:, 2]
    yu, ys = x[:, 2:2 + U], x[:, 2 + U:]
    ctx = _gelu(_lin(P, "ctx.0", np.concatenate([g, me], -1)))
    base = _lin(P, "base_type", ctx)
    cs = np.concatenate([np.broadcast_to(ctx[:, None], (Bn, S, d)), ys], -1)
    sk = _lin(P, "skill_type.2", _gelu(_lin(P, "skill_type.0", cs)))[..., 0]
    max_s = arch.get("max_s", B.MAX_S)
    if S < max_s:
        sk = np.concatenate([sk, np.full((Bn, max_s - S), -1e9, np.float32)], 1)
    type_logits = np.concatenate([base, sk], 1)
    tv = np.concatenate([np.broadcast_to(P["type_vec.weight"][None], (Bn, B.T_SKILL, d)), ys], 1)
    if S < max_s:
        tv = np.concatenate([tv, np.zeros((Bn, max_s - S, d), np.float32)], 1)
    T = tv.shape[1]
    qq = _lin(P, "query.2", _gelu(_lin(P, "query.0", np.concatenate([np.broadcast_to(ctx[:, None], (Bn, T, d)), tv],
                                                                     -1))))
    kk = _lin(P, "key", yu)
    unit_logits = qq @ kk.transpose(0, 2, 1) / np.sqrt(d)
    cw = P["cell_f.weight"]
    cf = (cw.reshape(cw.shape[0], -1) @ fm.reshape(Bn, fm.shape[1], -1)) + P["cell_f.bias"][None, :, None]
    cell_logits = _lin(P, "cell_q", qq) @ cf / np.sqrt(cf.shape[1])
    v = _lin(P, "v.2", _gelu(_lin(P, "v.0", ctx)))[:, 0]
    return type_logits, unit_logits, cell_logits, v


def collate(obs_list, max_u=None, max_s=None):
    """Пачка наблюдений для решения: формы как у entity_net.collate (полные маски), numpy."""
    n = len(obs_list)
    U, S = max_u or B.MAX_U, max_s or B.MAX_S
    UF, SF = obs_list[0]["units"].shape[1], obs_list[0]["skills"].shape[1]
    out = {"units": np.zeros((n, U, UF), np.float32), "upad": np.ones((n, U), bool),
           "kinds": np.zeros((n, U), np.int64), "skills": np.zeros((n, S, SF), np.float32),
           "spad": np.ones((n, S), bool), "sids": np.zeros((n, S), np.int64)}
    for i, o in enumerate(obs_list):
        k = len(o["units"])
        out["units"][i, :k] = o["units"]
        out["upad"][i, :k] = False
        out["kinds"][i, :k] = o["kinds"]
        s = len(o["skills"])
        out["skills"][i, :s] = o["skills"]
        out["sids"][i, :s] = o["sids"]
        out["spad"][i, :s] = False
    out["upad"][:, 0] = False
    out["spad"][:, 0] = False
    out["map"] = np.stack([o["map"] for o in obs_list]).astype(np.float32)
    out["glob"] = np.stack([o["glob"] for o in obs_list]).astype(np.float32)
    for k in ("tmask", "umask", "cmask"):
        out[k] = np.stack([o[k] for o in obs_list])
    return out


def act(P, arch, obs_list, greedy=False, rng=None):
    """Решения пачкой — тот же ответ, что entity_net.act: [(тип, цель, logp, ценность, вероятности)]."""
    rng = rng or np.random.default_rng()
    ob = collate(obs_list, arch.get("max_u"), arch.get("max_s"))
    tl, ul, cl, v = forward(P, arch, ob)
    pt = softmax(np.where(ob["tmask"], tl, -1e9))
    pu = softmax(np.where(ob["umask"], ul, -1e9))
    pc = softmax(np.where(ob["cmask"], cl, -1e9))
    out = []
    for i, o in enumerate(obs_list):
        p = pt[i].astype(np.float64)
        a = int(np.argmax(p)) if greedy else int(rng.choice(len(p), p=p / p.sum()))
        lp = float(np.log(p[a] + 1e-9))
        tt = o["ttype"][a]
        tgt, ptg = 0, None
        if a != B.T_HOLD and tt != B.TGT_NONE:
            ptg = (pu[i, a] if tt == B.TGT_UNIT else pc[i, a]).astype(np.float64)
            tgt = int(np.argmax(ptg)) if greedy else int(rng.choice(len(ptg), p=ptg / ptg.sum()))
            lp += float(np.log(ptg[tgt] + 1e-9))
        out.append((a, tgt, lp, float(v[i]), (pt[i], ptg, pu[i], pc[i])))
    return out


# ---------- файл весов ----------

def save(path, states, extra=None):
    """{ключ: {"net": state_dict (torch или numpy), "names", "arch"}} (+ extra) → .npz без pickle."""
    arr = {}
    meta = {"extra": extra or {}, "nets": {}}
    for key, st in states.items():
        meta["nets"][key] = {"names": st["names"], "arch": st["arch"]}
        for name, w in st["net"].items():
            a = w.detach().cpu().numpy() if hasattr(w, "detach") else np.asarray(w)
            arr[f"{key}|{name}"] = a
    arr["__meta__"] = np.frombuffer(json.dumps(meta, ensure_ascii=False).encode("utf-8"), np.uint8)
    with open(path, "wb") as f:
        np.savez(f, **arr)


def load(path):
    """→ ({ключ: {"net": {имя: массив}, "names", "arch"}}, extra)."""
    with np.load(path) as z:
        meta = json.loads(bytes(z["__meta__"]).decode("utf-8"))
        out = {k: {"net": {}, "names": v["names"], "arch": v["arch"]} for k, v in meta["nets"].items()}
        for name in z.files:
            if name == "__meta__":
                continue
            key, _, part = name.partition("|")
            a = z[name]
            out[key]["net"][part] = a.astype(np.float32) if a.dtype.kind == "f" else a
    return out, meta["extra"]


INPUTS = {"unit_in.weight": ("unit", 1), "kind_emb.weight": ("kinds", 0), "skill_in.weight": ("skill", 1),
          "skill_emb.weight": ("skills", 0), "map_in.weight": ("map", 1), "glob_in.weight": ("glob", 1)}


def adapt(P, old, new, seed=0):
    """Как entity_net.adapt, но для numpy-весов: столбцы входов и строки словарей — по именам; новые признаки —
    нулевые веса, новые виды и навыки — случайный вектор."""
    rng = np.random.default_rng(seed)
    out = dict(P)
    for k, (group, axis) in INPUTS.items():
        o, n = old.get(group, []), new[group]
        if list(o) == list(n):
            continue
        oi = {name: i for i, name in enumerate(o)}
        w = P[k]
        shape = list(w.shape)
        shape[axis] = len(n)
        base = np.zeros(shape, np.float32) if axis == 1 else rng.standard_normal(shape).astype(np.float32)
        for j, name in enumerate(n):
            if name in oi:
                if axis == 1:
                    base[:, j] = w[:, oi[name]]
                else:
                    base[j] = w[oi[name]]
        out[k] = base
    return out
