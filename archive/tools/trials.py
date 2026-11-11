"""Испытания сетей: одни и те же бои для автопилота, сети, случайных ходов, бездействия и планировщика.

  python tools/trials.py
  python tools/trials.py --modes autopilot,net --battles 100 --powers 0.5,0.75,1.0,1.25 --jobs 4
  python tools/trials.py --modes autopilot,net,net_auto --battles 100 --powers 1.0
  python tools/trials.py --checkpoint data/neural --json save/trials.json
  python tools/trials.py --full --checkpoint save/lab_full --battles 100

Подробности и таблицы — docs/neural_lab.md, разделы 9 и 10. Боевая логика не меняется: инструмент только
прогоняет существующий бой с разными источниками приказов.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main():
    from sim.trials import main as trials_main
    return trials_main()


if __name__ == "__main__":
    raise SystemExit(main())
