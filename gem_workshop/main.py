"""Запуск отдельного прототипа «Грань».

Из корня репозитория:
    python gem_workshop/main.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for path in (ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

from workshop.app import WorkshopApp  # noqa: E402


if __name__ == "__main__":
    WorkshopApp().run()
