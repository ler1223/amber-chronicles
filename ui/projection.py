"""HD-2D: поле — плоскость под наклоном, камера с перспективой.

Три системы координат:
  клетки (gx, gy)   — мир на земле: клетка (x, y) занимает [x, x+1) × [y, y+1); gz — высота над землёй (в клетках);
  плоская карта     — текстура «строго сверху», FLAT пикселей на клетку, с полями местности вокруг доски;
                      в неё рисуется вся земля: тайлы, лужи, подсветки клеток, приказы, следы на поле;
  экран             — куда камера проецирует землю (видеокарта или numpy кладут плоскую карту на плоскость)
                      и где стоят фигурки-билборды, эффекты и интерфейс.

Камера смотрит на центр доски сверху-спереди под углом PITCH: дальние ряды меньше и плотнее ближних.
"""
import math

FLAT = 64                       # пикселей плоской карты на клетку (пиксель-арт 32×32 ×2)
COLS, ROWS = 10, 6              # размер доски (все карты 10×6)
MARGIN_L, MARGIN_T, MARGIN_R, MARGIN_B = 9, 10, 9, 3     # клеток местности вокруг доски
FLAT_W = (MARGIN_L + COLS + MARGIN_R) * FLAT
FLAT_H = (MARGIN_T + ROWS + MARGIN_B) * FLAT

PITCH = math.radians(45)        # наклон камеры от горизонта
DEPTH_RATIO = 1.25              # ближний ряд шире дальнего во столько раз
PX_PER_CELL = 80.0              # ширина клетки в центре доски на экране
BASE_PX = 80.0                  # при такой ширине клетки фигурки в масштабе 1 (на больших досках — мельче)
MAX_NEAR_W = 900.0              # ближний ряд доски не шире этого (правее — панель интерфейса)
CENTER_SCREEN = (464.0, 362.0)  # куда на экране попадает центр доски

COS, SIN = math.cos(PITCH), math.sin(PITCH)
# расстояние камеры (в клетках): (D + c·R/2) / (D − c·R/2) = DEPTH_RATIO
_H = ROWS / 2
DIST = COS * _H * (DEPTH_RATIO + 1) / (DEPTH_RATIO - 1)
FOCAL = PX_PER_CELL * DIST
CX, CY = COLS / 2, ROWS / 2
GROUND_YS = SIN                 # во сколько раз круг на земле в центре доски ниже, чем шире
_DEFAULT = (CENTER_SCREEN, PX_PER_CELL)


def set_board(cols, rows):
    """Размер доски боя (клеток). Камера подстраивается: доска влезает в экран, фигурки — по размеру клетки."""
    global COLS, ROWS, FLAT_W, FLAT_H, DIST, CX, CY, PX_PER_CELL, FOCAL
    COLS, ROWS = cols, rows
    FLAT_W = (MARGIN_L + COLS + MARGIN_R) * FLAT
    FLAT_H = (MARGIN_T + ROWS + MARGIN_B) * FLAT
    DIST = COS * (ROWS / 2) * (DEPTH_RATIO + 1) / (DEPTH_RATIO - 1)
    CX, CY = COLS / 2, ROWS / 2
    near = (DEPTH_RATIO + 1) / 2                     # во сколько раз ближний ряд шире среднего
    PX_PER_CELL = min(_DEFAULT[1], MAX_NEAR_W / (COLS * near), 430.0 / (ROWS * 0.75))
    FOCAL = PX_PER_CELL * DIST


def configure(center, px_per_cell):
    """Камера смотрит в другое место экрана другим масштабом (окно превью навыка в подготовке героя)."""
    global CENTER_SCREEN, PX_PER_CELL, FOCAL
    CENTER_SCREEN, PX_PER_CELL = (float(center[0]), float(center[1])), float(px_per_cell)
    FOCAL = PX_PER_CELL * DIST


def reset():
    """Доска 10×6 и камера боя по умолчанию."""
    set_board(10, 6)
    configure(*_DEFAULT)


def view_key():
    return CENTER_SCREEN, FOCAL, COLS, ROWS


def project(gx, gy, gz=0.0):
    """Клетки (+высота) → экран (x, y) и масштаб фигурки (1 — в центре доски)."""
    t = gy - CY
    zc = DIST - t * COS - gz * SIN
    yc = -t * SIN + gz * COS
    zc = max(zc, 0.05)
    return (CENTER_SCREEN[0] + FOCAL * (gx - CX) / zc, CENTER_SCREEN[1] - FOCAL * yc / zc,
            DIST / zc * PX_PER_CELL / BASE_PX)


def unproject(sx, sy):
    """Экран → точка на земле (gx, gy) или None, если выше горизонта."""
    u = (sx - CENTER_SCREEN[0]) / FOCAL
    v = (sy - CENTER_SCREEN[1]) / FOCAL
    den = SIN + v * COS
    if den <= 1e-4:
        return None
    t = v * DIST / den
    zc = DIST - t * COS
    return CX + u * zc, CY + t


def scale_at(gy):
    """Масштаб фигурки на этой глубине: перспектива и размер клетки (большая доска — фигурки мельче)."""
    return DIST / max(0.05, DIST - (gy - CY) * COS) * PX_PER_CELL / BASE_PX


# ---------- клетки ----------

def cell_ground(pos):
    """Центр клетки на земле (в клетках)."""
    return pos[0] + 0.5, pos[1] + 0.5


def cell_screen(pos):
    gx, gy = cell_ground(pos)
    x, y, _ = project(gx, gy)
    return x, y


def cell_corners(pos):
    """Четыре угла клетки на экране: дальний левый, дальний правый, ближний правый, ближний левый."""
    x, y = pos
    return [project(x, y)[:2], project(x + 1, y)[:2], project(x + 1, y + 1)[:2], project(x, y + 1)[:2]]


def screen_to_cell(sx, sy, cols=None, rows=None):
    cols, rows = cols or COLS, rows or ROWS
    g = unproject(sx, sy)
    if g is None:
        return None
    x, y = math.floor(g[0]), math.floor(g[1])
    return (x, y) if 0 <= x < cols and 0 <= y < rows else None


# ---------- плоская карта ----------

def flat_rect(pos):
    """Клетка на плоской карте (pygame.Rect-совместимый кортеж)."""
    return ((MARGIN_L + pos[0]) * FLAT, (MARGIN_T + pos[1]) * FLAT, FLAT, FLAT)


def ground_to_flat(gx, gy):
    return (MARGIN_L + gx) * FLAT, (MARGIN_T + gy) * FLAT


def flat_to_ground(fx, fy):
    return fx / FLAT - MARGIN_L, fy / FLAT - MARGIN_T


def screen_to_flat(sx, sy):
    g = unproject(sx, sy)
    return None if g is None else ground_to_flat(*g)


def flat_to_screen(fx, fy):
    x, y, _ = project(*flat_to_ground(fx, fy))
    return x, y


def shader_params():
    """Числа для шейдера плоскости (ui/gl_renderer.py, PLANE_FS)."""
    return {"proj": (CENTER_SCREEN[0], CENTER_SCREEN[1], FOCAL, DIST), "cs": (COS, SIN), "center": (CX, CY),
            "flat": (MARGIN_L, MARGIN_T, FLAT, 0.0), "flat_size": (FLAT_W, FLAT_H), "board": (0.0, 0.0, COLS, ROWS)}
