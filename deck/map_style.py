"""Presentation of the chapter atlas, separate from its route graph."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pygame

from . import skin as SK


@dataclass(frozen=True)
class AtlasStyle:
    art: str
    scene: str
    skin: str
    top: tuple
    bottom: tuple
    trim: tuple
    accent: tuple
    paper: tuple

    @property
    def trail(self):
        return self.bottom, SK.mix(self.trim, self.paper, .32), self.accent

    @property
    def node(self):
        return self.bottom, self.top, self.accent

    @property
    def ribbon(self):
        return self.bottom, self.paper, self.bottom


SWAMP = AtlasStyle("swamp", "act_0", "elf", (39, 54, 44), (13, 23, 22), (103, 125, 86),
                   (202, 233, 151), (184, 196, 148))
FORGE = AtlasStyle("forge", "forge_act_0", "pyro", (51, 36, 37), (24, 16, 20), (145, 94, 68),
                   (255, 181, 112), (215, 164, 119))
ART = Path(__file__).resolve().parents[1] / "assets/ui/map"


def for_run(run):
    chapter = run.chapter_at()
    return FORGE if chapter and (chapter[1].get("id") == "forge" or chapter[0] == 1) else SWAMP


@lru_cache(maxsize=2)
def _source(key):
    return pygame.image.load(ART / f"{key}.png")


@lru_cache(maxsize=8)
def _surroundings(style, size):
    art = pygame.image.load(ART.parents[1] / "illustrations" / "hd" / f"{style.scene}.png")
    zoom = max(size[0] / art.get_width(), size[1] / art.get_height())
    image = pygame.transform.smoothscale(art, tuple(max(n, round(v * zoom)) for v, n in zip(art.get_size(), size)))
    background = pygame.Surface(size)
    background.blit(image, image.get_rect(center=background.get_rect().center))
    shade = SK.vgrad(*size, [(0, (15, 16, 17)), (.13, style.bottom), (.72, style.bottom), (1, (18, 17, 19))],
                     alpha=129)
    background.blit(shade, (0, 0))
    return background


@lru_cache(maxsize=12)
def _landscape(key, size):
    src = _source(key)
    return pygame.transform.smoothscale(src, size)


def backdrop(surf, style, board):
    native, scale, point = SK.ctx(surf)
    native.blit(_surroundings(style, native.get_size()), (0, 0))
    sk = SK.use(style.skin) if style.skin != "elf" else SK.Skin("elf", "grove")
    sk.panel(surf, board, 250, accent=True)
    inside = board.inflate(-22, -22)
    size = (max(1, round(inside.w * scale)), max(1, round(inside.h * scale)))
    x, y = map(round, point(inside.topleft))
    art = pygame.Rect((x, y), size)
    native.blit(_landscape(style.art, size), art)
    outlines = ((art.inflate(6, 6), style.trim), (art, style.bottom))
    for rect, color in outlines:
        pygame.draw.rect(native, color, rect, max(1, round(scale)))
    return sk


def button(surf, sk, rect, text, mouse, *, primary=False):
    sk.button(surf, rect, text, rect.collidepoint(mouse), primary=primary, size=16 if rect.h > 30 else 13,
              glow=False)
