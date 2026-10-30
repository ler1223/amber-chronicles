"""Переключатель стилей эффектов: пиксельный пилот (ui/pix_battle.py) или стили лаборатории (ui/fxlab/pilot.py).
Стиль — настройка fx_style (F9 в бою и в галерее): старые → пиксельные → флипбуки → шейдеры → меши → симуляция."""
from ui.fxlab.pilot import LabPilot
from ui.pix_battle import PixelPilot
from ui.settings import next_style


class FxRouter:
    def __init__(self, view):
        self.pixel = PixelPilot(view)
        self.lab = LabPilot(view)

    def _active(self):
        return self.lab if self.lab.on else self.pixel

    def __getattr__(self, name):
        return getattr(self._active(), name)

    def reset(self):
        self.pixel.reset()
        self.lab.reset()

    def update(self, dt):
        self.pixel.update(dt)
        self.lab.update(dt)

    def toggle(self):
        """Следующий стиль. Возвращает его подпись."""
        label = next_style()
        self.pixel.toggle()
        self.lab.toggle()
        return label

    def lab_frame(self):
        return self.lab.lab_frame() if self.lab.on else None
