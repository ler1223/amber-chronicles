"""Атлас карт: все карты доступны из выбора героя, фильтры и возврат работают."""
import pygame

from deck.atlas import CardAtlasScreen
from deck.game import DescentGame
from deck.ui import HeroSelect
from tests.test_expedition import ED
from tests.test_expedition_ui import SCREEN


def test_atlas_opens_from_hero_select_and_shows_all_cards():
    g = DescentGame(seed=2, gd=ED)
    sc = HeroSelect(g)
    sc.draw(SCREEN)
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=sc.atlas_rect.center))
    assert isinstance(g.scene, CardAtlasScreen)
    atlas = g.scene
    g.update(1 / 60)                                           # общий цикл игры не должен падать
    g.draw(SCREEN)
    assert len(atlas.filtered()) == len(atlas.data["cards"]["cards"])
    assert atlas.card_rects                                   # на экране есть карты
    atlas.scroll_target = 200
    g.update(1 / 60)
    assert 0 < atlas.scroll < 200                              # прокрутка плавная, а не прыжком


def test_atlas_filters_and_esc_returns():
    g = DescentGame(seed=2, gd=ED)
    g.open_atlas()
    atlas = g.scene
    g.draw(SCREEN)
    priest = next(r for r, key, _ in atlas.filter_rects if key == "priest")
    atlas.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=priest.center))
    assert atlas.filter == "priest"
    assert all(atlas._owner(c) == "priest" for c in atlas.filtered())
    atlas.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert not isinstance(g.scene, CardAtlasScreen)


def test_elf_theme_is_selectable_from_hero_card(monkeypatch):
    from ui import settings

    g = DescentGame(seed=2, gd=ED)
    g.save_settings = False
    sc = HeroSelect(g)
    monkeypatch.setitem(settings.SETTINGS, "elf_theme", "grove")
    sc.draw(SCREEN)
    buttons = {what[2]: r for r, what in sc.hits if what[0] == "elf_theme"}
    assert set(buttons) == {"grove", "moon"}
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=buttons["moon"].center))
    assert sc.pick == "elf"
    assert settings.SETTINGS["elf_theme"] == "moon"
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=buttons["grove"].center))
    assert settings.SETTINGS["elf_theme"] == "grove"


def test_item_atlas_lists_all_relics_and_can_select_the_last_entry():
    g = DescentGame(seed=2, gd=ED)
    back = g.scene
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F2))
    atlas = g.scene
    g.draw(SCREEN)
    item_tab = next(r for r, key, _ in atlas.tab_rects if key == "items")
    g.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=item_tab.center))
    assert atlas.tab == "items"
    g.draw(SCREEN)

    page = atlas.item_page
    assert {item["id"] for item in page.filtered()} == set(g.data["relics"]["relics"])
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_END))
    g.update(1)
    g.draw(SCREEN)
    rect, last = page.entries[-1]
    assert last is page.items[-1]
    g.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
    assert page.selected is last and last["about"]
    g.draw(SCREEN)

    rare = next(r for r, key, _ in page.filters if key == "rare")
    g.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rare.center))
    assert page.filtered() and all(item["rarity"] == "rare" for item in page.filtered())
    assert page.selected in page.filtered() and page.scroll == 0
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert g.scene is back
