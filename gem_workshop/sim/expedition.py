"""Минимальный загрузчик данных для локального рендера «Грани»."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATH = os.path.join(ROOT, "data", "expedition.json")


def load_expedition():
    with open(_PATH, encoding="utf-8") as f:
        return json.load(f)
