"""QoL интерфейса: автофит кнопок, фильтры/сборки артефактов, причины нехватки ресурсов."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from sim.data import GameData  # noqa: E402
from sim import expedition as X  # noqa: E402
from sim import artifacts as A  # noqa: E402
from ui import theme as T  # noqa: E402
from ui import widgets as W  # noqa: E402

pygame.init()
DATA = GameData()
ED = X.expedition_data(DATA)
XD = ED.expedition


def test_button_label_fits_actual_font():
    label = W._fit_button("Очень длинное название кнопки", 120)
    assert T.font(18, True).size(label)[0] <= 120


def test_artifact_flags_preset_and_auto_equip():
    p = X.ExpeditionProfile(ED)
    h = p.recruitable()[0]
    h.rank = 3
    kinds = ("bracers", "belt", "ring")
    sid = next(iter(XD["artifacts"]["sets"]))
    for i, kind in enumerate(kinds):
        art = A.make(XD, f"q{i}", kind, sid, 1.0)
        p.stash[art["uid"]] = art
    p.toggle_art_flag("q0", "favorite")
    p.toggle_art_flag("q1", "junk")
    assert p.art_flag("q0", "favorite") and p.art_flag("q1", "junk")
    assert p.auto_equip_best(h) >= 1 and h.arts
    assert p.save_art_preset(h)
    saved = list(h.arts)
    for uid in list(h.arts):
        p.unequip(h, uid)
    assert p.apply_art_preset(h) == len(saved)
    assert h.arts == saved


def test_missing_cost_reports_only_shortfall():
    p = X.ExpeditionProfile(ED)
    p.glory = 10
    p.mats = {"ore": 2}
    miss = p.missing_cost({"glory": 30, "ore": 5, "cut_gems": [{"min_q": 1.0}]})
    assert ("glory", 20) in miss and ("ore", 3) in miss and ("cut_gems", 1) in miss


def test_chest_search_and_set_collection(tmp_path):
    from tests.test_expedition_ui import new_app, frame
    from game import tavern_rooms as R

    app = new_app(tmp_path)
    p = app.profile
    sid = next(iter(XD["artifacts"]["sets"]))
    for i, kind in enumerate(("bracers", "belt", "ring")):
        art = A.make(XD, f"ui{i}", kind, sid, 1.0)
        p.stash[art["uid"]] = art
    R.go(app, "muster")
    room = app.scene
    overlay = R.ChestOverlay(room, p.recruitable()[0])
    room.overlay = overlay
    frame(app)
    overlay.query = "пояс"
    assert [a["kind"] for a in overlay.arts()] == ["belt"]
    overlay.act("sets")
    assert isinstance(room.overlay, R.SetCollectionOverlay)
    frame(app)


def test_market_filter_and_sell_all_confirmation(tmp_path):
    from tests.test_expedition_ui import new_app, frame
    from game import tavern_rooms as R

    app = new_app(tmp_path)
    p = app.profile
    p.gems = [{"uid": "sellme", "id": "ruby", "q": 1.0, "size": 1.0, "col": 0.6,
               "cl": 0.8, "cut": "table"}]
    R.go(app, "market")
    room = app.scene
    room.act(("mfilter", "cut"))
    assert room.filter == "cut"
    room.act("sell_all")
    assert isinstance(room.overlay, R.ConfirmOverlay)
    room.overlay.act("confirm_yes")
    assert not p.gems
    frame(app)
