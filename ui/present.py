"""Вывод кадра: через OpenGL (частицы, bloom, вспышки на видеокарте) или напрямую pygame (без шейдеров).

Сцена с эффектами (бой) умеет draw_layers(земля, интерфейс, юниты) и отдаёт vfx; остальные экраны — просто draw(surf).
Логический холст подстраивается под окно (ui/layout.py): на ультрашироком экране он шире 1280, и сцены рисуют
интерфейс по всей ширине. Экраны со сложной фиксированной вёрсткой помечены stage = True: они рисуются в
координатах 1280×800 и ставятся по центру, а поля заливаются фоном (без чёрных полос и «призрачного» меню).
"""
import pygame

from ui import layout as L
from ui import theme as T


class Presenter:
    def __init__(self, screen, use_gl=True, window=True):
        self.screen = screen
        self.window = window
        self.size = (T.SCREEN_W, T.SCREEN_H)
        self.gl = None
        if use_gl:
            try:
                from ui.gl_renderer import GLRenderer
                self.gl = GLRenderer(self.size, window=window)
            except Exception as exc:          # нет moderngl/драйвера — работаем без шейдеров
                print(f"OpenGL недоступен ({exc}), рисую без него")
                self.gl = None
        self.world = self.ui = self.units = self.canvas = None
        self.stage = None
        self._alloc()

    # ---------- поверхности ----------

    def _alloc(self):
        if self.gl:
            self.world = pygame.Surface(self.size)
            self.ui = pygame.Surface(self.size, pygame.SRCALPHA)
            self.units = pygame.Surface(self.size, pygame.SRCALPHA)
        else:
            self.canvas = pygame.Surface(self.size)
        self.stage = pygame.Surface((L.BASE_W, L.BASE_H))

    def resize(self):
        """Логический холст изменился (окно потянули/полный экран): новые поверхности и FBO."""
        size = (T.SCREEN_W, T.SCREEN_H)
        if size == self.size:
            return
        self.size = size
        if self.gl:
            self.gl.resize(*size)
        self._alloc()

    def _ensure_size(self):
        if (T.SCREEN_W, T.SCREEN_H) != self.size:
            self.size = (T.SCREEN_W, T.SCREEN_H)
            if self.gl:
                self.gl.resize(*self.size)
            self._alloc()

    def _ambient(self, canvas, w, h):
        """Размытая приглушённая копия кадра — фон в полях, без читаемых «призраков» интерфейса."""
        small = pygame.transform.smoothscale(canvas, (max(1, w // 10), max(1, h // 10)))
        amb = pygame.transform.smoothscale(small, (w, h))
        amb.fill((70, 72, 82), special_flags=pygame.BLEND_RGB_MULT)
        return amb

    # ---------- кадр ----------

    def frame(self, scene):
        from ui import display
        self._ensure_size()
        disp = display.CURRENT if self.window else None
        stage = getattr(scene, "stage", False)

        if stage:
            with T.design():
                scene.draw(self.stage)
            ox = T.content_ox()
            if self.gl:
                self.world.fill(T.BG)
                self.world.blit(self.stage, (ox, 0))
                if disp is not None:
                    self.gl.view = disp.view()
                    self.gl.window_size = disp.size()
                self.gl.render(self.world)
                return
            screen = pygame.display.get_surface() or self.screen
            self.screen = screen
            if disp is None or disp.view() == (0, 0, T.SCREEN_W, T.SCREEN_H):
                screen.fill(T.BG)
                screen.blit(self.stage, (ox, 0))
                return
            self.canvas.fill(T.BG)
            self.canvas.blit(self.stage, (ox, 0))
            self._blit_cpu(screen, disp)
            return

        if not self.gl:
            screen = pygame.display.get_surface() or self.screen
            self.screen = screen
            if disp is None or disp.view() == (0, 0, T.SCREEN_W, T.SCREEN_H):
                scene.draw(screen)
                return
            scene.draw(self.canvas)
            self._blit_cpu(screen, disp)
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

    def _blit_cpu(self, screen, disp):
        """Кадр логического холста → окно: поля размытым фоном, кадр по центру."""
        x, y, w, h = disp.view()
        sw, sh = screen.get_size()
        if (x, y, w, h) != (0, 0, sw, sh):
            screen.blit(self._ambient(self.canvas, sw, sh), (0, 0))
        # вверх — чёткие пиксели, вниз (маленькое окно) — сглаживание, чтобы текст читался
        scale = pygame.transform.scale if w >= T.SCREEN_W else pygame.transform.smoothscale
        screen.blit(scale(self.canvas, (w, h)), (x, y))

    def snapshot(self):
        """Текущий кадр как Surface (для скриншота)."""
        return self.gl.read() if self.gl and not self.gl.window else self.screen.copy()
