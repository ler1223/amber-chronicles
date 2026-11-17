"""Запуск отдельного прототипа «Грань».

Из корня репозитория:
    python gem_workshop/main.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from workshop.app import WorkshopApp  # noqa: E402


if __name__ == "__main__":
    WorkshopApp().run()
