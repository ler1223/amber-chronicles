"""Optional decisions yielded by battle relic effects."""

from dataclasses import dataclass


@dataclass
class RelicChoice:
    prompt: str
    options: list
