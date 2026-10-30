"""Вывод кадра: через OpenGL (частицы, bloom, вспышки на видеокарте) или напрямую pygame (без шейдеров).

Сцена с эффектами (бой) умеет draw_layers(земля, интерфейс, юниты) и отдаёт vfx; остальные экраны — просто draw(surf).
"""
import pygame

from ui import theme as T


class Presenter:
    def __init__(self, screen, use_gl=True, window=True):
        self.screen = screen
        self.gl = None
        if use_gl:
            try:
                from ui.gl_renderer import GLRenderer
                self.gl = GLRenderer((T.SCREEN_W, T.SCREEN_H), window=window)
            except Exception as exc:          # нет moderngl/драйвера — работаем без шейдеров
                print(f"OpenGL недоступен ({exc}), рисую без него")
                self.gl = None
        if self.gl:
            self.world = pygame.Surface((T.SCREEN_W, T.SCREEN_H))
            self.ui = pygame.Surface((T.SCREEN_W, T.SCREEN_H), pygame.SRCALPHA)
            self.units = pygame.Surface((T.SCREEN_W, T.SCREEN_H), pygame.SRCALPHA)

    def frame(self, scene):
        if not self.gl:
            scene.draw(self.screen)
            return
        if hasattr(scene, "draw_layers"):
            self.ui.fill((0, 0, 0, 0))
            scene.draw_layers(self.world, self.ui, self.units)
            plane = scene.plane() if hasattr(scene, "plane") else None
            glow = scene.glow_layer() if hasattr(scene, "glow_layer") else None
            lab = scene.lab_frame() if hasattr(scene, "lab_frame") else None
            self.gl.render(self.world, scene.vfx, self.ui, self.units, plane=plane, glow=glow, lab=lab)
        else:
            scene.draw(self.world)
            self.gl.render(self.world)

    def snapshot(self):
        """Текущий кадр как Surface (для скриншота)."""
        return self.gl.read() if self.gl and not self.gl.window else self.screen.copy()
