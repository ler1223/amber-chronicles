"""Локальные данные «Грани»: только то, что нужно мастерской."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


class WorkshopData:
    def __init__(self):
        with open(os.path.join(DATA, "expedition.json"), encoding="utf-8") as f:
            self.expedition = json.load(f)


def load():
    return WorkshopData()
