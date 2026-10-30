"""Кадр команд стилей: что нарисовать видеокартой в этом кадре. Координаты — экран мира (до камеры).

Слои: ground — на земле под юнитами, air — над юнитами (фигурки потом просвечивают). Порядок внутри слоя —
порядок добавления; подряд идущие команды одного вида и смешивания рисуются одним вызовом.
Смешивание: alpha — обычная прозрачность (предумноженная), add — свет складывается (и идёт в свечение).
"""
import numpy as np

INST = 14          # pos2 half2 rot1 uv/params4 color4 mode1


class LabFrame:
    def __init__(self):
        self.layers = {"ground": [], "air": []}
        self.textures = {}         # имя → (RGBA uint8 [h, w, 4], линейная фильтрация)

    def clear(self):
        for v in self.layers.values():
            v.clear()
        self.textures.clear()

    def _add(self, layer, kind, key, blend, row):
        cmds = self.layers[layer]
        if cmds and cmds[-1][0] == kind and cmds[-1][1] == key and cmds[-1][2] == blend:
            cmds[-1][3].append(row)
        else:
            cmds.append((kind, key, blend, [row]))

    def sprite(self, layer, sheet, uv, x, y, w, h, rot=0.0, color=(1, 1, 1, 1), mode=0, blend="alpha"):
        """Кадр флипбука. uv — (u0, v0, u1, v1) в листе; mode 0 — RGBA, 1 — дым листа огня (альфа × цвет),
        2 — свечение листа огня (RGB, кладётся сложением)."""
        self._add(layer, "sprite", sheet, blend, (x, y, w / 2, h / 2, rot, *uv, *color, mode))

    def quad(self, layer, mode, x, y, w, h, rot=0.0, color=(1, 1, 1, 1), p=(0, 0, 0, 0), blend="alpha"):
        """Шейдерный эффект в прямоугольнике (центр x, y; размер w×h; поворот rot рад). p — параметры режима."""
        self._add(layer, "quad", None, blend, (x, y, w / 2, h / 2, rot, *p, *color, mode))

    def mesh(self, layer, verts, blend="alpha"):
        """Треугольники: массив [n, 12] — x, y, u, v, r, g, b, a, режим, свет, возраст, зерно."""
        cmds = self.layers[layer]
        if cmds and cmds[-1][0] == "mesh" and cmds[-1][2] == blend:
            cmds[-1][3].append(verts)
        else:
            cmds.append(("mesh", None, blend, [verts]))

    def texture(self, layer, name, rgba, rect, blend="alpha"):
        """Картинка из numpy (симуляция) в прямоугольник экрана rect = (x, y, w, h), с линейной фильтрацией."""
        self.textures[name] = rgba
        x, y, w, h = rect
        self._add(layer, "tex", name, blend, (x + w / 2, y + h / 2, w / 2, h / 2, 0.0, 0, 0, 1, 1, 1, 1, 1, 1, 3))

    def packed(self, layer):
        """[(вид, ключ, смешивание, данные float32)]."""
        out = []
        for kind, key, blend, rows in self.layers[layer]:
            if kind == "mesh":
                out.append((kind, key, blend, np.ascontiguousarray(np.concatenate(rows).astype(np.float32))))
            else:
                out.append((kind, key, blend, np.array(rows, np.float32)))
        return out
