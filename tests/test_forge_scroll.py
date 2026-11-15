"""Кузня: список изделий/сетов крутится колесом так же, как в ювелирке."""
from types import SimpleNamespace

from game.tavern_rooms import StationOverlay


def station(mode, n=12, rows=3):
    o = object.__new__(StationOverlay)
    o.mode = mode
    o.scroll = 0
    o.app = SimpleNamespace(profile=SimpleNamespace(
        xd={"artifacts": {"sets": {f"s{i}": {} for i in range(n)}}}))
    o.set_list_rows = lambda: rows
    return o


def test_forge_item_mode_scrolls_with_mouse_wheel():
    o = station("item")
    StationOverlay.wheel(o, -1)
    assert o.scroll == 1
    StationOverlay.wheel(o, 1)
    assert o.scroll == 0


def test_jewel_craft_mode_still_scrolls():
    o = station("craft")
    StationOverlay.wheel(o, -2)
    assert o.scroll == 2


def test_other_modes_do_not_scroll_the_set_list():
    o = station("store")
    StationOverlay.wheel(o, 5)
    assert o.scroll == 0
