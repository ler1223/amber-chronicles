"""Вывод кадра: через OpenGL (частицы, bloom, вспышки на видеокарте) или напрямую pygame (без шейдеров).

Сцена с эффектами (бой) умеет draw_layers(земля, интерфейс, юниты) и отдаёт vfx; остальные экраны — просто draw(surf).
Кадр всегда рисуется в логическом размере 1280×800, а затем растягивается под окно (ui/display.py).
"""
import pygame

from ui import theme as T


class Presenter:
    def __init__(self, screen, use_gl=True, window=True):
        self.screen = screen
        self.window = window
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
        from ui import display
        disp = display.CURRENT if self.window else None
        if not self.gl:
            screen = pygame.display.get_surface() or self.screen
            self.screen = screen
            if disp is None or disp.view() == (0, 0, T.SCREEN_W, T.SCREEN_H):
                scene.draw(screen)
                return
            if getattr(self, "canvas", None) is None:          # без OpenGL: кадр 1280×800 → окно
                self.canvas = pygame.Surface((T.SCREEN_W, T.SCREEN_H))
            scene.draw(self.canvas)
            x, y, w, h = disp.view()
            if (x, y, w, h) != (0, 0, *screen.get_size()):
                # поля вокруг кадра: тёмный оттенок края кадра (без второй растяжки на весь экран)
                edge = pygame.transform.average_color(self.canvas, (0, 0, 6, T.SCREEN_H))[:3]
                screen.fill((edge[0] // 4, edge[1] // 4, edge[2] // 4))
            else:
                screen.fill(T.BG)
            # вверх — чёткие пиксели, вниз (маленькое окно) — сглаживание, чтобы текст читался
            scale = pygame.transform.scale if w >= T.SCREEN_W else pygame.transform.smoothscale
            screen.blit(scale(self.canvas, (w, h)), (x, y))
            return
        if disp is not None:
            self.gl.view = disp.view()
            self.gl.window_size = disp.size()
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
