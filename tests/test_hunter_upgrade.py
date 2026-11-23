"""CZN-улучшение Охотницы: автоматическая усиленная стрела."""
from deck import model as M
from deck.battle import Battle, finish
from tests.test_expedition import ED


def put(u, cell):
    u.cell = u.prev_cell = tuple(cell)


def _battle():
    data = M.load()
    run = M.Run(data=data, seed=91, hero="hunter", variant="mark")
    b = Battle(ED, run, run.fights[0], seed=91)
    h, foe = b.hero, b.foes()[0]
    b.prey = None
    put(h, (2, 2))
    put(foe, (3, 2))
    foe.hp = foe.max_hp = 99
    b.hand = [M.Card("h_upgrade_quiver", run.defs)]
    b.energy = 9
    return b, h, foe, data


def test_upgrade_creates_auto_arrow_at_turn_start():
    b, h, foe, data = _battle()
    upgrade = b.hand[0]
    finish(b.play(upgrade, "main", h))
    assert upgrade in b.powers
    finish(b.start_player_turn())
    auto = next((c for c in b.hand if c.cid == "arrow_auto"), None)
    assert auto is not None
    assert auto.name == "Стрела охоты" and auto.d.get("auto_end")
    assert auto.d["main"]["do"][0]["n"] == 5          # сильнее обычной стрелы (3)
    assert not b.can_play(auto, "main")               # вручную не играется
    assert not b.can_play(auto, "alt")


def test_auto_arrow_fires_at_end_of_turn():
    b, h, foe, data = _battle()
    finish(b.play(b.hand[0], "main", h))
    finish(b.start_player_turn())
    auto = next(c for c in b.hand if c.cid == "arrow_auto")
    hp = foe.hp
    finish(b.auto_end_turn())
    assert auto not in b.hand and foe.hp <= hp - 5
