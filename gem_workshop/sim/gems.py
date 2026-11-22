"""Самоцветы «как в жизни» (квиз 2026-11-11): 4C — масса (караты), чистота (примеси), цвет (насыщенность) и
качество огранки; плюс редкость вида и вид огранки. Всё нелинейно: цена ≈ караты^1.8 × множители, сила камня тоже
растёт нелинейно (средний камень ≈ прежние +2.5%, лучший ≈ ×5, с мягким потолком).

Необработанный камень (profile.rough): {"uid", "id", "seed", "size" (караты), "col" (насыщенность 0–1),
"incl": [примеси]}. Примесь: {"k": вид, "p": [u, v, w], "r": радиус, "n": нормаль (трещина), "d": плотность (шёлк)};
у сырого камня p и r — в долях кристалла (u, v — по радиусу призмы, w — по длине), у огранённого — в единицах
камня (радиус рундиста = 100, как на станке).
Огранённый (profile.gems): {"uid", "id", "q" (качество огранки), "size" (караты), "col", "cl" (чистота 0–1),
"incl", "cut", "shape", "star" (астеризм)}.

Огранки (CUTS): ярусы — (сторона P низ / C верх, граней, угол °, доля радиуса, сдвиг индекса); контур рундиста
(outline) — круг или выпуклый многоугольник; dome — кабошон (купол после граней). Стартовые три простые огранки
известны сразу; остальные — книги у бродячего ювелира на рынке (tier — сложность, book — цена), книги идут по
качеству не выше максимальной открытой + 50%. Авторские (rare) — одиночные огранки мастеров прошлого: редкие свитки
(изредка у ювелира, награда похода), камень дороже."""
import math
import random

# ---------- огранки ----------

CUTS = (
    {"id": "table", "name": "Столовая", "tier": 0, "book": 0, "cap": 1.00, "value": 0.8,
     "outline": "square", "desc": "старинная: площадка и четыре грани с каждой стороны",
     "tiers": (("P", 4, 45, 1.0, 0), ("C", 4, 40, 1.0, 0), ("C", 1, 0, 0.55, 0))},
    {"id": "baguette", "name": "Багет", "tier": 1, "book": 1500, "cap": 1.40, "value": 0.9,
     "outline": "rect", "desc": "вытянутая ступенчатая",
     "tiers": (("P", 4, 45, 1.0, 0), ("P", 4, 30, 0.5, 0), ("C", 4, 38, 1.0, 0), ("C", 1, 0, 0.6, 0))},
    {"id": "rose", "name": "Роза", "tier": 1, "book": 1600, "cap": 1.50, "value": 0.9,
     "outline": None, "desc": "старинная: плоское дно и купол из треугольных граней",
     "tiers": (("P", 1, 0, 1.0, 0), ("C", 6, 30, 1.0, 0), ("C", 6, 16, 0.5, 8))},
    {"id": "emerald", "name": "Изумрудная", "tier": 1, "book": 2000, "cap": 1.70, "value": 1.0,
     "outline": "octrect", "desc": "ступенчатая, срезанные углы",
     "tiers": (("P", 4, 48, 1.0, 0), ("P", 4, 38, 0.62, 0), ("C", 4, 42, 1.0, 0), ("C", 4, 28, 0.72, 0),
               ("C", 1, 0, 0.55, 0))},
    {"id": "single", "name": "Простая восьмёрка", "tier": 1, "book": 1400, "cap": 1.45, "value": 0.9,
     "outline": None, "desc": "по восемь граней сверху и снизу — огранка мелких камней",
     "tiers": (("P", 8, 41, 1.0, 0), ("C", 8, 35, 1.0, 0), ("C", 1, 0, 0.55, 0))},
    {"id": "hexagon", "name": "Шестигранник", "tier": 1, "book": 1700, "cap": 1.50, "value": 0.95,
     "outline": "hexagon", "desc": "шестиугольная ступенчатая",
     "tiers": (("P", 6, 46, 1.0, 0), ("P", 6, 34, 0.55, 0), ("C", 6, 40, 1.0, 0), ("C", 1, 0, 0.6, 0))},
    {"id": "trapeze", "name": "Трапеция", "tier": 1, "book": 1700, "cap": 1.55, "value": 0.9,
     "outline": "trapeze", "desc": "ступенчатая трапеция — боковой камень в оправе",
     "tiers": (("P", 4, 45, 1.0, 0), ("P", 4, 32, 0.55, 0), ("C", 4, 38, 1.0, 0), ("C", 1, 0, 0.6, 0))},
    {"id": "half_moon", "name": "Полумесяц", "tier": 1, "book": 1900, "cap": 1.60, "value": 0.95,
     "outline": "half_moon", "desc": "половина круга: дуга и прямой край",
     "tiers": (("P", 8, 44, 1.0, 0), ("C", 8, 36, 1.0, 0), ("C", 1, 0, 0.6, 0))},
    {"id": "cushion", "name": "Кушон", "tier": 2, "book": 4000, "cap": 2.10, "value": 1.05,
     "outline": "cushion", "desc": "подушка: квадрат со скруглёнными углами",
     "tiers": (("P", 8, 42, 1.0, 0), ("P", 4, 30, 0.45, 6), ("C", 8, 36, 1.0, 6), ("C", 1, 0, 0.55, 0))},
    {"id": "princess", "name": "Принцесса", "tier": 2, "book": 4500, "cap": 2.20, "value": 1.1,
     "outline": "square", "desc": "квадратная с острыми углами, яркая",
     "tiers": (("P", 4, 42, 1.0, 0), ("P", 4, 40, 1.0, 12), ("P", 8, 44, 1.0, 6), ("C", 4, 36, 1.0, 0),
               ("C", 4, 34, 1.0, 12), ("C", 1, 0, 0.6, 0))},
    {"id": "asscher", "name": "Ашер", "tier": 2, "book": 4500, "cap": 2.30, "value": 1.1,
     "outline": "asscher", "desc": "квадратная ступенчатая, «зеркальный зал»",
     "tiers": (("P", 8, 48, 1.0, 0), ("P", 8, 36, 0.6, 0), ("C", 8, 40, 1.0, 0), ("C", 8, 26, 0.72, 0),
               ("C", 1, 0, 0.55, 0))},
    {"id": "mazarin", "name": "Мазарини", "tier": 2, "book": 5000, "cap": 2.40, "value": 1.05,
     "outline": None, "desc": "старинная круглая: 17 граней короны",
     "tiers": (("P", 8, 42, 1.0, 0), ("P", 8, 44, 1.0, 6), ("C", 8, 38, 1.0, 0), ("C", 8, 26, 0.62, 6),
               ("C", 1, 0, 0.5, 0))},
    {"id": "star", "name": "Звёздный кабошон", "tier": 2, "book": 5500, "cap": 2.20, "value": 1.0,
     "outline": None, "dome": True, "desc": "купол; камень с шёлком даёт звезду — ось кристалла вверх",
     "tiers": (("P", 1, 0, 1.0, 0), ("C", 8, 64, 1.0, 0), ("C", 8, 46, 0.82, 6), ("C", 8, 28, 0.58, 0),
               ("C", 1, 0, 0.32, 0))},
    {"id": "french", "name": "Французская", "tier": 2, "book": 4200, "cap": 2.15, "value": 1.05,
     "outline": "square", "desc": "квадрат, корона из треугольников — «конверт» на площадке",
     "tiers": (("P", 4, 42, 1.0, 12), ("P", 4, 44, 1.0, 0), ("C", 4, 32, 1.0, 12), ("C", 4, 24, 0.7, 0),
               ("C", 1, 0, 0.5, 0))},
    {"id": "octagon", "name": "Восьмигранник", "tier": 2, "book": 4600, "cap": 2.25, "value": 1.05,
     "outline": "octagon", "desc": "правильный восьмиугольник, ступени",
     "tiers": (("P", 8, 48, 1.0, 0), ("P", 8, 36, 0.6, 0), ("C", 8, 40, 1.0, 0), ("C", 8, 27, 0.72, 0),
               ("C", 1, 0, 0.55, 0))},
    {"id": "old_mine", "name": "Старая шахтная", "tier": 2, "book": 5200, "cap": 2.45, "value": 1.1,
     "outline": "cushion", "desc": "подушка с высокой короной и калеттой — огранка старых копей",
     "tiers": (("P", 8, 42, 1.0, 0), ("P", 8, 44, 1.0, 6), ("P", 1, 0, 0.08, 0), ("C", 8, 40, 1.0, 0),
               ("C", 8, 26, 0.45, 6), ("C", 1, 0, 0.45, 0))},
    {"id": "kite", "name": "Воздушный змей", "tier": 2, "book": 4800, "cap": 2.30, "value": 1.05,
     "outline": "kite", "desc": "длинный нос и короткий хвост",
     "tiers": (("P", 8, 42, 1.0, 0), ("P", 4, 30, 0.45, 6), ("C", 8, 36, 1.0, 6), ("C", 1, 0, 0.55, 0))},
    {"id": "shield", "name": "Щит", "tier": 2, "book": 5000, "cap": 2.35, "value": 1.1,
     "outline": "shield", "desc": "прямой верх и острый низ, как у рыцарского щита",
     "tiers": (("P", 8, 43, 1.0, 0), ("P", 8, 45, 1.0, 6), ("C", 8, 36, 1.0, 0), ("C", 1, 0, 0.58, 0))},
    {"id": "barrel", "name": "Бочонок", "tier": 2, "book": 4400, "cap": 2.20, "value": 1.0,
     "outline": "barrel", "desc": "прямоугольник с выпуклыми боками, ступени и скосы",
     "tiers": (("P", 4, 46, 1.0, 0), ("P", 4, 44, 1.0, 12), ("P", 4, 34, 0.6, 0), ("C", 4, 40, 1.0, 0),
               ("C", 4, 40, 1.0, 12), ("C", 4, 28, 0.7, 0), ("C", 1, 0, 0.55, 0))},
    {"id": "checker", "name": "Шахматная", "tier": 2, "book": 6000, "cap": 2.60, "value": 1.05,
     "outline": None, "desc": "плоское дно, купол в шашечку — светится без глубины",
     "tiers": (("P", 1, 0, 1.0, 0), ("C", 8, 48, 1.0, 0), ("C", 8, 38, 0.75, 6), ("C", 8, 28, 0.5, 0),
               ("C", 8, 18, 0.28, 6), ("C", 1, 0, 0.15, 0))},
    {"id": "double_rose", "name": "Двойная роза", "tier": 2, "book": 5600, "cap": 2.50, "value": 1.0,
     "outline": None, "desc": "роза с обеих сторон — без площадки и без дна",
     "tiers": (("P", 6, 40, 1.0, 0), ("P", 6, 22, 0.5, 8), ("C", 6, 30, 1.0, 0), ("C", 6, 16, 0.5, 8))},
    {"id": "oval", "name": "Овал", "tier": 3, "book": 9000, "cap": 3.20, "value": 1.15,
     "outline": "oval", "desc": "вытянутый бриллиант",
     "tiers": (("P", 8, 41, 1.0, 0), ("P", 8, 45, 1.0, 6), ("C", 8, 35, 1.0, 0), ("C", 4, 22, 0.55, 6),
               ("C", 1, 0, 0.56, 0))},
    {"id": "old_european", "name": "Староевропейская", "tier": 3, "book": 9000, "cap": 3.00,
     "value": 1.1, "outline": None, "desc": "высокая корона, маленькая площадка и калетта",
     "tiers": (("P", 8, 42, 1.0, 0), ("P", 8, 44, 1.0, 6), ("P", 1, 0, 0.06, 0), ("C", 8, 40, 1.0, 0),
               ("C", 8, 24, 0.45, 6), ("C", 1, 0, 0.42, 0))},
    {"id": "radiant", "name": "Радиант", "tier": 3, "book": 10000, "cap": 3.30, "value": 1.15,
     "outline": "octrect", "desc": "прямоугольник со срезанными углами и бриллиантовыми гранями",
     "tiers": (("P", 8, 41, 1.0, 0), ("P", 8, 44, 1.0, 6), ("C", 8, 35, 1.0, 0), ("C", 8, 24, 0.6, 6),
               ("C", 1, 0, 0.6, 0))},
    {"id": "trilliant", "name": "Триллиант", "tier": 3, "book": 10000, "cap": 3.10, "value": 1.1,
     "outline": "trilliant", "desc": "треугольная с выпуклыми сторонами",
     "tiers": (("P", 3, 42, 1.0, 16), ("P", 3, 44, 1.0, 0), ("C", 3, 36, 1.0, 16), ("C", 3, 38, 1.0, 0),
               ("C", 6, 22, 0.6, 8), ("C", 1, 0, 0.55, 0))},
    {"id": "lozenge", "name": "Ромб", "tier": 3, "book": 9500, "cap": 3.10, "value": 1.1,
     "outline": "lozenge", "desc": "ромб с бриллиантовыми гранями",
     "tiers": (("P", 8, 41, 1.0, 0), ("P", 8, 44, 1.0, 6), ("C", 8, 35, 1.0, 0), ("C", 8, 22, 0.56, 6),
               ("C", 1, 0, 0.56, 0))},
    {"id": "briolette", "name": "Бриолет", "tier": 3, "book": 11000, "cap": 3.40, "value": 1.2,
     "outline": "teardrop", "desc": "длинная капля, вся в гранях, без площадки — для подвесок",
     "tiers": (("P", 8, 44, 1.0, 0), ("P", 8, 46, 1.0, 6), ("C", 8, 52, 1.0, 0), ("C", 8, 40, 0.6, 6),
               ("C", 8, 26, 0.32, 0))},
    {"id": "portrait", "name": "Портретная", "tier": 3, "book": 8500, "cap": 3.05, "value": 1.05,
     "outline": "octrect", "desc": "тонкая пластина с огромной площадкой — сквозь неё видно, как в окно",
     "tiers": (("P", 8, 36, 1.0, 0), ("C", 8, 14, 1.0, 0), ("C", 1, 0, 0.85, 0))},
    {"id": "hex_brilliant", "name": "Шестиугольный бриллиант", "tier": 3, "book": 10000, "cap": 3.20,
     "value": 1.15, "outline": "hexagon", "desc": "шестиугольник с бриллиантовой игрой",
     "tiers": (("P", 6, 41, 1.0, 0), ("P", 6, 43, 1.0, 8), ("C", 6, 35, 1.0, 0), ("C", 6, 38, 1.0, 8),
               ("C", 6, 22, 0.56, 8), ("C", 1, 0, 0.56, 0))},
    {"id": "cushion_brilliant", "name": "Кушон-бриллиант", "tier": 3, "book": 11000, "cap": 3.35,
     "value": 1.15, "outline": "cushion", "desc": "подушка с бриллиантовыми гранями — мягкий блеск",
     "tiers": (("P", 8, 41, 1.0, 0), ("P", 8, 44, 1.0, 6), ("C", 8, 35, 1.0, 0), ("C", 8, 38, 1.0, 6),
               ("C", 8, 22, 0.56, 6), ("C", 1, 0, 0.56, 0))},
    {"id": "brilliant", "name": "Круглая бриллиантовая", "tier": 4, "book": 18000, "cap": 5.00,
     "value": 1.25, "outline": None, "desc": "57 граней в жизни — вершина огранки",
     "tiers": (("P", 8, 41, 1.0, 0), ("P", 8, 44, 1.0, 6), ("C", 8, 35, 1.0, 0), ("C", 8, 22, 0.56, 6),
               ("C", 1, 0, 0.56, 0))},
    {"id": "pear", "name": "Груша", "tier": 4, "book": 16000, "cap": 4.60, "value": 1.2,
     "outline": "pear", "desc": "капля: круглый край и острый носик",
     "tiers": (("P", 8, 41, 1.0, 0), ("P", 8, 44, 1.0, 6), ("C", 8, 35, 1.0, 0), ("C", 8, 22, 0.56, 6),
               ("C", 1, 0, 0.56, 0))},
    {"id": "marquise", "name": "Маркиза", "tier": 4, "book": 16000, "cap": 4.60, "value": 1.2,
     "outline": "marquise", "desc": "лодочка с двумя острыми концами",
     "tiers": (("P", 8, 41, 1.0, 0), ("P", 8, 44, 1.0, 6), ("C", 8, 35, 1.0, 0), ("C", 8, 22, 0.56, 6),
               ("C", 1, 0, 0.56, 0))},
    {"id": "heart", "name": "Сердце", "tier": 4, "book": 20000, "cap": 4.80, "value": 1.25,
     "outline": "heart", "desc": "два округлых плеча и острый носик",
     "tiers": (("P", 8, 41, 1.0, 0), ("P", 8, 44, 1.0, 6), ("C", 8, 35, 1.0, 0), ("C", 8, 22, 0.56, 6),
               ("C", 1, 0, 0.56, 0))},
    {"id": "jubilee", "name": "Юбилейная", "tier": 4, "book": 22000, "cap": 4.75, "value": 1.25,
     "outline": None, "desc": "круглая без площадки: верх сходится в точку, 88 граней в жизни",
     "tiers": (("P", 8, 41, 1.0, 0), ("P", 8, 44, 1.0, 6), ("C", 8, 35, 1.0, 0), ("C", 8, 38, 1.0, 6),
               ("C", 16, 28, 0.7, 3), ("C", 8, 20, 0.4, 0), ("C", 8, 12, 0.2, 6))},
    {"id": "portuguese", "name": "Португальская", "tier": 4, "book": 26000, "cap": 4.90, "value": 1.3,
     "outline": None, "desc": "круг из ярусов по 16 граней — самая долгая работа",
     "tiers": (("P", 16, 41, 1.0, 0), ("P", 16, 44, 0.6, 3), ("C", 16, 36, 1.0, 0), ("C", 16, 28, 0.7, 3),
               ("C", 16, 18, 0.45, 0), ("C", 1, 0, 0.45, 0))},
    # --- авторские огранки: редкие свитки (бродячий ювелир изредка, награды похода); камень такой огранки дороже ---
    {"id": "dragon_eye", "name": "Око дракона", "tier": 3, "book": 30000, "cap": 4.00, "value": 1.4,
     "rare": True, "outline": "marquise", "desc": "лодочка с хребтом и щелью-зрачком вдоль камня",
     "tiers": (("P", 8, 42, 1.0, 0), ("P", 8, 44, 1.0, 6), ("C", 2, 30, 1.0, 24), ("C", 2, 44, 1.0, 0),
               ("C", 4, 36, 1.0, 12), ("C", 1, 0, 0.2, 0))},
    {"id": "mermaid_tear", "name": "Слеза русалки", "tier": 3, "book": 32000, "cap": 4.30, "value": 1.4,
     "rare": True, "outline": "teardrop", "desc": "капля с высокой мягкой короной — будто вот-вот скатится",
     "tiers": (("P", 8, 46, 1.0, 0), ("P", 8, 30, 0.5, 6), ("C", 8, 55, 1.0, 0), ("C", 8, 42, 0.65, 6),
               ("C", 8, 28, 0.38, 0), ("C", 8, 15, 0.18, 6))},
    {"id": "witch_coffin", "name": "Ведьмин гроб", "tier": 3, "book": 26000, "cap": 3.90, "value": 1.35,
     "rare": True, "outline": "coffin", "desc": "вытянутый шестиугольник с тройной ступенью — тёмная глубина",
     "tiers": (("P", 8, 48, 1.0, 0), ("P", 8, 38, 0.62, 0), ("P", 8, 30, 0.35, 0), ("C", 8, 42, 1.0, 0),
               ("C", 8, 30, 0.72, 0), ("C", 1, 0, 0.5, 0))},
    {"id": "amber_comb", "name": "Соты", "tier": 3, "book": 29000, "cap": 4.20, "value": 1.35,
     "rare": True, "outline": "hexagon", "desc": "шестиугольники друг в друге, каждый повёрнут — как пчелиные соты",
     "tiers": (("P", 6, 46, 1.0, 0), ("P", 6, 36, 0.62, 8), ("P", 6, 28, 0.35, 0), ("C", 6, 40, 1.0, 0),
               ("C", 6, 32, 0.72, 8), ("C", 6, 24, 0.48, 0), ("C", 1, 0, 0.3, 0))},
    {"id": "mill_wheel", "name": "Мельничное колесо", "tier": 3, "book": 28000, "cap": 4.40,
     "value": 1.35, "rare": True, "outline": None, "desc": "16 пологих спиц вокруг широкой площадки",
     "tiers": (("P", 16, 40, 1.0, 0), ("P", 16, 43, 1.0, 3), ("C", 16, 22, 1.0, 0), ("C", 1, 0, 0.68, 0))},
    {"id": "moon_eye", "name": "Лунный глаз", "tier": 3, "book": 24000, "cap": 3.60, "value": 1.35,
     "rare": True, "outline": "oval", "dome": True, "desc": "высокий овальный кабошон — лунная дорожка по куполу",
     "tiers": (("P", 1, 0, 1.0, 0), ("C", 8, 66, 1.0, 0), ("C", 8, 50, 0.84, 6), ("C", 8, 32, 0.6, 0),
               ("C", 1, 0, 0.3, 0))},
    {"id": "north_star", "name": "Звезда Севера", "tier": 4, "book": 40000, "cap": 4.70, "value": 1.45,
     "rare": True, "outline": "hexagon", "desc": "шестилучевая звезда на короне и в глубине",
     "tiers": (("P", 6, 42, 1.0, 0), ("P", 6, 44, 1.0, 8), ("P", 12, 40, 0.5, 4), ("C", 6, 34, 1.0, 8),
               ("C", 6, 36, 1.0, 0), ("C", 6, 20, 0.5, 8), ("C", 1, 0, 0.45, 0))},
    {"id": "storm_eye", "name": "Глаз бури", "tier": 4, "book": 45000, "cap": 4.85, "value": 1.5,
     "rare": True, "outline": None, "desc": "ярусы короны закручены спиралью — камень будто вращается",
     "tiers": (("P", 8, 41, 1.0, 0), ("P", 8, 44, 1.0, 6), ("C", 8, 35, 1.0, 0), ("C", 8, 29, 0.78, 2),
               ("C", 8, 23, 0.58, 4), ("C", 8, 17, 0.4, 6), ("C", 8, 11, 0.24, 8), ("C", 1, 0, 0.14, 0))},
    {"id": "ember_heart", "name": "Сердце углей", "tier": 4, "book": 50000, "cap": 4.90, "value": 1.5,
     "rare": True, "outline": "heart", "desc": "сердце со спиральной короной — жар изнутри",
     "tiers": (("P", 8, 41, 1.0, 0), ("P", 8, 44, 1.0, 6), ("C", 8, 36, 1.0, 0), ("C", 8, 28, 0.7, 3),
               ("C", 8, 20, 0.45, 6), ("C", 8, 12, 0.25, 9), ("C", 1, 0, 0.16, 0))},
)
CUT_BY_ID = {c["id"]: c for c in CUTS}
Q_MIN, Q_MAX = 0.7, 5.0                         # качество огранки: грубая 70% … вершина мастерства 500%

# стартовый набор: три самые простые огранки по пределу качества (без авторских свитков)
START_CUTS = tuple(c["id"] for c in sorted((c for c in CUTS if not c.get("rare")),
                                           key=lambda c: (c["cap"], c["tier"]))[:3])

# лупа на станке (продаёт бродячий ювелир): оправа с первой линзой, затем линзы по одной; кратности складываются
LOUPE = (("loupe", "Лупа ювелира: оправа и линза ×2", 2, 2500),
         ("lens3", "Линза ×3", 3, 4000),
         ("lens4", "Линза ×4", 4, 6500),
         ("lens6", "Линза ×6", 6, 10000))
LOUPE_BY_ID = {t[0]: t for t in LOUPE}
AUTOFOCUS = ("loupe_af", "Автофокус лупы (часовой механизм)", 9000)

# шлифовальные диски: скорость стачивания против чистоты грани (грубый — быстро, но в царапинах); средний — от
# ювелира, остальные — у бродячего ювелира. (id, название, скорость, чистота грани, цена)
DISKS = (("lap_coarse", "Грубый диск (зерно 260)", 1.8, 0.78, 1500),
         ("lap_medium", "Средний диск (зерно 600)", 1.0, 0.94, 0),
         ("lap_fine", "Тонкий диск (зерно 1200)", 0.55, 1.0, 3500),
         ("lap_diamond", "Алмазный диск", 1.5, 0.99, 14000))
DISK_BY_ID = {d[0]: d for d in DISKS}
GRIT = {"lap_coarse": 1.0, "lap_medium": 0.42, "lap_fine": 0.06, "lap_diamond": 0.12}   # шероховатость грани
START_DISK = "lap_medium"
START_CUT = START_CUTS[0]
GIRDLE_N = 32                                   # плоскостей рундиста у фигурного контура


def cut_index(cid):
    return next(i for i, c in enumerate(CUTS) if c["id"] == cid)


def is_rare(cid):
    """Авторская огранка (свиток): редкая, камень такой огранки ценится выше."""
    return bool(CUT_BY_ID.get(cid, {}).get("rare"))


def roll_rare_scroll(rng, known):
    """Авторский свиток — награда похода: случайная неизвестная авторская огранка (или None)."""
    pool = [c["id"] for c in CUTS if c.get("rare") and c["id"] not in known]
    return rng.choice(pool) if pool else None


def cut_name(cid):
    c = CUT_BY_ID.get(cid)
    return c["name"] if c else "огранка неизвестна"


def max_cut_cap(known):
    """Максимальный предел качества среди открытых огранок (по умолчанию — стартовый набор)."""
    known = set(known or ())
    return max((CUT_BY_ID[c]["cap"] for c in known if c in CUT_BY_ID),
               default=max(CUT_BY_ID[c]["cap"] for c in START_CUTS))


def book_cuts(known, count=2):
    """Книги у ювелира: следующие неизвестные обычные огранки по качеству, не выше максимума +50%."""
    known = set(known or ())
    limit = max_cut_cap(known) + 0.50
    pool = sorted((c for c in CUTS if c["id"] not in known and not c.get("rare") and c["cap"] <= limit),
                  key=lambda c: c["cap"])
    return [c["id"] for c in pool[:max(1, int(count))]]


def _arc(cx, cy, r, a0, a1, n=12):
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n))
            for k in range(n + 1)]


def _outline_pts(name):
    """Точки контура рундиста (выпуклая оболочка задаёт форму); ось X — длина камня."""
    if name == "square":
        return [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    if name == "rect":
        return [(-1, -0.55), (1, -0.55), (1, 0.55), (-1, 0.55)]
    if name == "octrect":
        return [(-1, -0.5), (-0.78, -0.72), (0.78, -0.72), (1, -0.5), (1, 0.5), (0.78, 0.72), (-0.78, 0.72),
                (-1, 0.5)]
    if name == "asscher":
        return [(-1, -0.6), (-0.6, -1), (0.6, -1), (1, -0.6), (1, 0.6), (0.6, 1), (-0.6, 1), (-1, 0.6)]
    if name == "cushion":
        pts = []
        for k in range(48):                                      # суперэллипс: подушка
            a = math.tau * k / 48
            c, s = math.cos(a), math.sin(a)
            pts.append((math.copysign(abs(c) ** 0.5, c), math.copysign(abs(s) ** 0.5, s)))
        return pts
    if name == "oval":
        return [(math.cos(math.tau * k / 48), 0.72 * math.sin(math.tau * k / 48)) for k in range(48)]
    if name == "pear":
        return _arc(-0.38, 0.0, 0.62, math.pi * 0.35, math.pi * 1.65, 24) + [(1.0, 0.0)]
    if name == "marquise":
        R = (1 + 0.42 ** 2) / (2 * 0.42)                          # дуги через концы (±1, 0) и ширину 0.42
        a = math.asin(1 / R)
        return _arc(0, 0.42 - R, R, math.pi / 2 - a, math.pi / 2 + a, 16) + \
            _arc(0, R - 0.42, R, -math.pi / 2 - a, -math.pi / 2 + a, 16)
    if name == "heart":
        return _arc(-0.3, -0.42, 0.46, math.pi * 0.5, math.pi * 1.55, 14) + \
            _arc(-0.3, 0.42, 0.46, math.pi * 0.45, math.pi * 1.5, 14) + [(1.0, 0.0)]
    if name == "hexagon":                                        # стороны смотрят на азимуты 0°, 60°…
        return [(math.cos(math.radians(30 + 60 * k)), math.sin(math.radians(30 + 60 * k))) for k in range(6)]
    if name == "octagon":
        return [(math.cos(math.radians(22.5 + 45 * k)), math.sin(math.radians(22.5 + 45 * k))) for k in range(8)]
    if name == "trapeze":
        return [(-1, -0.7), (1, -0.4), (1, 0.4), (-1, 0.7)]
    if name == "half_moon":
        return [(x, 0.92 * y) for x, y in _arc(0, 0, 1, -math.pi / 2, math.pi / 2, 16)]
    if name == "kite":
        return [(1, 0), (-0.2, -0.62), (-0.75, 0), (-0.2, 0.62)]
    if name == "shield":
        return [(-0.85, -0.75), (0.3, -0.68), (0.72, -0.36), (1, 0), (0.72, 0.36), (0.3, 0.68), (-0.85, 0.75)]
    if name == "lozenge":
        return [(-1, 0), (0, -0.6), (1, 0), (0, 0.6)]
    if name == "barrel":
        pts = []
        for k in range(9):
            x = -1 + k / 4
            y = 0.5 + 0.12 * math.cos(math.pi * x / 2)
            pts += [(x, y), (x, -y)]
        return pts
    if name == "coffin":
        return [(-1, -0.3), (-0.5, -0.55), (1, -0.32), (1, 0.32), (-0.5, 0.55), (-1, 0.3)]
    if name == "teardrop":
        return _arc(-0.5, 0.0, 0.48, math.pi * 0.4, math.pi * 1.6, 24) + [(1.0, 0.0)]
    if name == "trilliant":
        pts = []
        for k in range(3):
            a0 = math.tau * k / 3
            a1 = a0 + math.tau / 3
            mid = (a0 + a1) / 2
            for j in range(9):                                   # выпуклая сторона между вершинами
                t = j / 8
                x0, y0 = math.cos(a0), math.sin(a0)
                x1, y1 = math.cos(a1), math.sin(a1)
                bulge = 0.12 * math.sin(math.pi * t)
                pts.append((x0 + (x1 - x0) * t + bulge * math.cos(mid), y0 + (y1 - y0) * t + bulge * math.sin(mid)))
        return pts
    return None


_SUPPORT = {}


def outline_planes(name):
    """Рундист: [(азимут, отступ)] — опорная функция контура, нормирована: самая дальняя точка = 1."""
    if name not in _SUPPORT:
        pts = _outline_pts(name)
        if pts is None:
            _SUPPORT[name] = None
        else:
            cx = (max(p[0] for p in pts) + min(p[0] for p in pts)) / 2
            cy = (max(p[1] for p in pts) + min(p[1] for p in pts)) / 2
            pts = [(x - cx, y - cy) for x, y in pts]
            far = max(math.hypot(*p) for p in pts)
            pts = [(x / far, y / far) for x, y in pts]
            _SUPPORT[name] = (pts, [(math.tau * k / GIRDLE_N, max(x * math.cos(math.tau * k / GIRDLE_N) +
                                                                     y * math.sin(math.tau * k / GIRDLE_N)
                                                                     for x, y in pts)) for k in range(GIRDLE_N)])
    return _SUPPORT[name]


def support(name, phi):
    """Опорная функция контура в направлении phi (круг — 1)."""
    o = outline_planes(name) if name else None
    if not o:
        return 1.0
    return max(x * math.cos(phi) + y * math.sin(phi) for x, y in o[0])


# ---------- настройки ----------

# Форма сырья влияет на выход, ориентацию и выбор огранки.
FORM_NAMES = {
    "octahedron": "октаэдр",
    "cube": "куб",
    "prism": "призма",
    "macle": "макл",
    "massive": "массивный",
    "dodecahedron": "додекаэдр",
}
FORM_YIELD = {
    "octahedron": 1.12,
    "cube": 1.05,
    "prism": 1.00,
    "macle": 0.88,
    "massive": 0.82,
    "dodecahedron": 0.95,
}
ROUGH_FORMS = {
    "ruby": ("prism", "massive", "macle"),
    "sapphire": ("prism", "massive", "macle"),
    "emerald": ("prism", "massive"),
    "topaz": ("prism", "massive"),
    "amethyst": ("prism", "massive"),
    "diamond": ("octahedron", "macle", "cube"),
    "spinel": ("octahedron", "macle"),
    "zircon": ("prism", "massive"),
    "tourmaline": ("prism", "massive"),
    "peridot": ("prism", "massive"),
    "garnet": ("dodecahedron", "massive"),
    "opal": ("massive",),
}


def form_name(form):
    return FORM_NAMES.get(form, form or "массивный")


def form_yield(form):
    return FORM_YIELD.get(form, 1.0)


# Облик куска сырья (docs/rough_to_gem_reality.md): в партиях в основном обломки,
# пластинки, щепки и кристаллы в породе; окатыши — у прочных камней из россыпей;
# целый красивый кристалл — редкость.
SHAPE_NAMES = {"fragment": "обломок", "plate": "пластинка", "sliver": "щепка", "matrix": "в породе",
               "pebble": "окатыш", "crystal": "кристалл"}
# Выход: из плоской пластинки и тонкой щепки камень выходит меньше; у куска в породе
# часть кристалла скрыта.
SHAPE_YIELD = {"fragment": 0.95, "plate": 0.72, "sliver": 0.75, "matrix": 0.85, "pebble": 1.0, "crystal": 1.1}
ALLUVIAL = {"ruby", "sapphire", "spinel", "garnet", "peridot", "zircon", "diamond"}
SHAPE_WEIGHTS = {"fragment": 0.42, "plate": 0.13, "sliver": 0.15, "matrix": 0.22, "crystal": 0.08}
SHAPE_WEIGHTS_ALLUVIAL = {"pebble": 0.25, "fragment": 0.30, "plate": 0.15, "sliver": 0.05, "matrix": 0.18,
                          "crystal": 0.07}
SHAPE_WEIGHTS_GID = {"tourmaline": {"sliver": 0.35, "fragment": 0.30, "matrix": 0.20, "plate": 0.07, "crystal": 0.08}}
# Порода, в которой сидит кристалл: 0 — белый мрамор, 1 — пегматит (полевой шпат, кварц, слюда),
# 2 — тёмная порода (базальт, сланец), 3 — серая агатовая корка жеоды.
MATRIX_ROCK = {"ruby": 0, "spinel": 0, "sapphire": 2, "emerald": 2, "garnet": 2, "amethyst": 3,
               "tourmaline": 1, "topaz": 1}
# Белые непрозрачные зоны (их отрезают): у кварца — белое основание кристаллов.
MILKY_CHANCE = {"amethyst": 0.5, "sapphire": 0.3, "ruby": 0.25, "emerald": 0.3, "topaz": 0.2, "tourmaline": 0.25}


def roll_look(gid, seed):
    """Облик куска: форма и ржавый налёт на старых изломах (свой поток случайности)."""
    rng = random.Random(f"look:{gid}:{seed}")         # строка хешируется: без корреляций соседних зёрен
    w = SHAPE_WEIGHTS_GID.get(gid) or (SHAPE_WEIGHTS_ALLUVIAL if gid in ALLUVIAL else SHAPE_WEIGHTS)
    x = rng.uniform(0, sum(w.values()))
    shape = "fragment"
    for k, v in w.items():
        x -= v
        if x <= 0:
            shape = k
            break
    stain = 0.0
    if rng.random() < (0.75 if shape == "matrix" else 0.5):
        stain = round(rng.uniform(0.25, 0.9), 2)
    return {"shape": shape, "stain": stain}


def rough_shape(r):
    """Облик куска; у старых сохранений — по прежней «форме»."""
    if r.get("shape"):
        return r["shape"]
    if r.get("form") == "massive":
        return "pebble" if r.get("id") in ALLUVIAL else "fragment"
    return "crystal"


def shape_name(r):
    return SHAPE_NAMES.get(rough_shape(r), "кусок")


def rough_yield(r):
    if r.get("shape"):
        return SHAPE_YIELD.get(r["shape"], 1.0)
    return form_yield(r.get("form"))


def roll_milky(gid, seed):
    """Белая непрозрачная зона — у конца или края куска; её стоит увести в отход."""
    rng = random.Random(f"milky:{gid}:{seed}")
    if rng.random() >= MILKY_CHANCE.get(gid, 0.15):
        return []
    a = rng.uniform(0, math.tau)
    rr = rng.uniform(0.25, 0.5)
    z = rng.choice((-1, 1)) * rng.uniform(0.35, 0.6)
    return [{"k": "milky", "p": [round(rr * math.cos(a), 3), round(rr * math.sin(a), 3), round(z, 3)],
             "r": round(rng.uniform(0.16, 0.28), 3), "seed": round(rng.random(), 4)}]


DEF = {
    "rough_ct": {"median": 2.2, "sigma": 0.55, "min": 0.4, "max": 7.0},
    "yield": 0.2,                     # ожидаемая доля массы после огранки (для цены сырого)
    "rough_k": 0.6,                   # сырой камень — доля ожидаемой цены огранённого
    "ct_exp": 1.8,
    "color_k": [0.6, 1.8], "clarity_k": [0.45, 2.0], "cut_k": [0.6, 1.7],
    "power": {"ref_ct": 0.45, "ct_exp": 0.75, "cut_exp": 0.7, "soft": 3.0, "cap": 12.0, "min": 0.3},
    "cut_price_exp": 1.5,             # цена от качества огранки: q^1.5 (быстрее статов: q^0.7)
    "clarity_grades": [[0.95, "Безупречный"], [0.85, "Очень чистый"], [0.7, "Чистый"], [0.5, "Мелкие примеси"],
                       [0.3, "Заметные примеси"], [0.0, "Мутный"]],
    "color_words": [[0.8, "густой"], [0.6, "насыщенный"], [0.4, "ровный"], [0.2, "светлый"], [0.0, "бледный"]],
    "incl_kinds": {"crystal": {"name": "кристаллик", "w": 1.0}, "bubble": {"name": "пузырёк", "w": 0.5},
                   "feather": {"name": "трещина", "w": 1.3}, "cloud": {"name": "облачко", "w": 0.6},
                   "silk": {"name": "шёлк", "w": 0.25}, "cavity": {"name": "каверна", "w": 1.5},
                   "cleavage": {"name": "спайность", "w": 1.8}, "graining": {"name": "внутреннее зерно", "w": 0.8},
                   # залеченная трещина: видна, но камень не колет
                   "fingerprint": {"name": "отпечаток", "w": 0.55},
                   "two_phase": {"name": "полость с пузырьком", "w": 0.7},
                   "milky": {"name": "белая зона", "w": 1.1}},
    "jeweler": {"chance": 0.55, "books": [1, 2], "rough": [1, 2], "rare_chance": 0.2,
                "names": ["Ювелир Мирон Скло", "Огранщица Ветта", "Старый Лазарь Гранёный", "Ювелирша Ольва"]},
}


def cfg(xd):
    j = dict(DEF)
    j.update((xd or {}).get("jewelry") or {})
    return j


def gem_def(xd, gid):
    return xd["artifacts"]["gems"][gid]


def per_ct(xd, gid):
    g = gem_def(xd, gid)
    return g.get("per_ct", g.get("price", 200) * 20)


# ---------- сырьё ----------

def roll_rough(xd, gid, rng, uid, size=None, premium=False):
    """Необработанный камень: караты (логнормально), насыщенность цвета, примеси (свои у вида), шёлк."""
    j = cfg(xd)
    gd = gem_def(xd, gid)
    rc = j["rough_ct"]
    if size is None:
        size = rc["median"] * math.exp(rng.gauss(0.25 if premium else 0.0, rc["sigma"]))
        size = max(rc["min"], min(rc["max"], size))
    col = rng.betavariate(3.2, 2.0) if premium else rng.betavariate(2.2, 2.2)
    r = {"uid": uid, "id": gid, "seed": rng.randrange(1, 10 ** 6), "size": round(size, 2), "col": round(col, 3)}
    frng = random.Random(r["seed"] * 17 + 5)
    r["form"] = frng.choice(ROUGH_FORMS.get(gid, ("prism", "massive")))
    ax = (frng.gauss(0, 1), frng.gauss(0, 1), frng.gauss(0, 1))
    am = math.sqrt(sum(v * v for v in ax)) or 1.0
    r["axis"] = tuple(round(v / am, 4) for v in ax)
    r["incl"] = roll_incl(xd, gid, random.Random(r["seed"] * 7 + 1), premium)
    r["cf"] = roll_window(random.Random(r["seed"] * 11 + 3))
    r.update(roll_look(gid, r["seed"]))
    r["incl"] += roll_milky(gid, r["seed"])
    return r


def roll_window(rng):
    """Окно камня в карте оттенков вида: смещение (мм) в большом поле."""
    return {"o": [round(rng.uniform(-4000, 4000), 2) for _ in range(3)]}


# Рецепты включений по минералу (docs/atlas_inclusions_rough.md, §1 и §3): какие
# типы и как часто, во сколько раз больше/меньше среднего числа, доля кристалликов
# с ореолом напряжения. Пузыри газа — признак стекла/синтетики, у природных камней их нет.
INCL_RECIPES = {
    # кварц: залеченные трещины, перья, полости с пузырьком; кристаллики почти невидимы (тот же n)
    "amethyst": {"kinds": {"fingerprint": 3.0, "feather": 2.0, "two_phase": 2.0, "crystal": 1.0, "cloud": 1.0},
                 "mean": 1.0},
    # корунд: кристаллики (циркон — с ореолом), отпечатки, облака; шёлк — отдельно (вид в данных)
    "sapphire": {"kinds": {"crystal": 2.5, "fingerprint": 3.0, "feather": 1.5, "cloud": 1.5, "two_phase": 0.5,
                           "cavity": 0.3}, "halo": 0.4, "mean": 1.0},
    "ruby": {"kinds": {"crystal": 2.5, "fingerprint": 2.5, "feather": 2.0, "cloud": 1.5, "cavity": 0.4},
             "halo": 0.3, "mean": 1.1},
    # изумруд: «сад» — трещины и многофазные полости, это норма вида
    # clarity: включения весят меньше — рынок ждёт «сад» у изумруда, у аквамарина — нет
    "emerald": {"kinds": {"feather": 3.0, "two_phase": 3.0, "crystal": 1.5, "fingerprint": 1.5, "cloud": 1.0},
                "mean": 1.3, "clarity": 0.55},
    # топаз: спайность по базису, полости, отпечатки
    "topaz": {"kinds": {"cleavage": 1.5, "two_phase": 2.0, "fingerprint": 2.0, "feather": 1.0, "crystal": 0.5},
              "mean": 0.9},
    "tourmaline": {"kinds": {"feather": 2.0, "fingerprint": 2.0, "two_phase": 1.5, "graining": 0.8},
                   "mean": 1.0},
}
DEFAULT_RECIPE = {"kinds": {"crystal": 2.0, "feather": 1.0, "cloud": 2.0, "fingerprint": 1.0, "cavity": 0.5,
                            "graining": 0.5}, "mean": 1.0}

# Радиус — доля радиуса кристалла (кристалл ≈ 10 мм: 0.1 ≈ 0.5 мм).
INCL_SIZE = {"crystal": (0.02, 0.08), "bubble": (0.015, 0.05), "feather": (0.06, 0.17),
             "cloud": (0.04, 0.1), "cavity": (0.025, 0.075), "cleavage": (0.05, 0.14),
             "graining": (0.02, 0.06), "fingerprint": (0.09, 0.22), "two_phase": (0.025, 0.07)}


def incl_recipe(gid):
    return INCL_RECIPES.get(gid, DEFAULT_RECIPE)


def _pick(rng, weights):
    total = sum(weights.values())
    x = rng.uniform(0, total)
    for k, w in weights.items():
        x -= w
        if x <= 0:
            return k
    return k


def _unit(v):
    m = math.sqrt(sum(x * x for x in v)) or 1.0
    return [round(x / m, 4) for x in v]


def _incl_place(rng, k):
    """Положение включения (доли кристалла: xy — радиус призмы, z — полудлина).

    Залеченные трещины и перья чаще идут от поверхности внутрь (кристалл трескался
    и залечивался снаружи), остальное — по всему объёму."""
    a = rng.uniform(0, math.tau)
    if k in ("fingerprint", "feather"):
        rr = 0.75 * (0.35 + 0.65 * math.sqrt(rng.random()))
    else:
        rr = 0.75 * math.sqrt(rng.random())
    return [round(rr * math.cos(a), 3), round(rr * math.sin(a), 3), round(rng.uniform(-0.72, 0.72), 3)]


def _plane_normal(rng, k, p_):
    """Нормаль плоского включения. Отпечатки и перья тянутся вдоль поверхности
    (нормаль ближе к радиальной), спайность — строго поперёк оси кристалла."""
    if k == "cleavage":
        return [0.0, 0.0, 1.0]
    rnd = [rng.gauss(0, 1) for _ in range(3)]
    radial = [p_[0], p_[1], 0.0]
    if k in ("fingerprint", "feather") and (radial[0] or radial[1]):
        rad = _unit(radial)
        rnd = _unit(rnd)
        return _unit([rad[i] * 0.9 + rnd[i] * 0.7 for i in range(3)])
    return _unit(rnd)


def roll_incl(xd, gid, rng, premium=False):
    gd = gem_def(xd, gid)
    rec = incl_recipe(gid)
    mean = gd.get("incl", 2.0) * rec.get("mean", 1.0) * (0.5 if premium else 1.0)
    n = 0
    L, p = math.exp(-mean), 1.0                          # число примесей — по Пуассону
    while True:
        p *= rng.random()
        if p < L or n >= 8:
            break
        n += 1
    out = []
    for _ in range(n):
        k = _pick(rng, rec["kinds"])
        p_ = _incl_place(rng, k)
        lo, hi = INCL_SIZE[k]
        base_r = rng.uniform(lo, hi)
        halo = k == "crystal" and rng.random() < rec.get("halo", 0.0)
        n_plane = _plane_normal(rng, k, p_) if k in ("feather", "cleavage", "fingerprint") else None

        # Облака и кристаллики — не один шар, а маленькая ассоциация.
        # Так включение читается как природное образование, а не примитив.
        copies = 1
        if k == "cloud":
            copies = rng.choice((2, 2, 3, 3, 4))
        elif k == "crystal":
            copies = rng.choice((1, 2, 2))
        elif k == "feather":
            copies = rng.choice((1, 1, 2))

        for j in range(copies):
            spread = base_r * (0.75 if k == "cloud" else 0.35)
            jitter = (rng.uniform(-spread, spread), rng.uniform(-spread, spread),
                      rng.uniform(-spread, spread)) if j > 0 else (0.0, 0.0, 0.0)
            inc = {
                "k": k,
                "p": [round(p_[0] + jitter[0], 3), round(p_[1] + jitter[1], 3),
                      round(p_[2] + jitter[2], 3)],
                "r": round(base_r * (rng.uniform(0.45, 0.8) if j else 1.0), 3),
                "seed": round(rng.random(), 4),           # форма и материал включения в рендере
            }
            if n_plane is not None:
                # соседние куски одной трещины почти параллельны
                inc["n"] = n_plane if j == 0 else _unit([n_plane[i] + rng.gauss(0, 0.15) for i in range(3)])
            if k in ("crystal", "cloud", "bubble"):
                inc["axis"] = _unit([rng.gauss(0, 1) for _ in range(3)])
                inc["aspect"] = 1.0 if k == "bubble" else round(rng.uniform(0.55, 1.55), 2)
            if k == "two_phase":                          # полость повторяет кристалл: вытянута по его оси
                inc["aspect"] = round(rng.uniform(1.2, 2.2), 2)
            if halo and j == 0:
                inc["halo"] = 1.0
            if k == "cavity":
                inc["surf"] = 1.0
            elif k == "feather" and rng.random() < 0.35:
                inc["surf"] = 1.0
            out.append(inc)
            if len(out) >= 15:
                break
        if len(out) >= 15:
            break
    if rng.random() < gd.get("silk", 0.0):              # шёлк (иглы рутила): мутит, но даёт звезду в кабошоне
        out.append({"k": "silk", "p": [0.0, 0.0, 0.0], "r": 0.55, "d": round(rng.uniform(0.35, 1.0), 2)})
    return out


def ensure_rough(xd, r):
    """Старый камень (без цвета и примесей) — достроить из его seed."""
    if "col" not in r:
        rng = random.Random(r.get("seed", 1) * 13 + 5)
        r["col"] = round(rng.betavariate(2.2, 2.2), 3)
    if "incl" not in r:
        r["incl"] = roll_incl(xd, r["id"], random.Random(r.get("seed", 1) * 7 + 1))
    if "cf" not in r:
        r["cf"] = roll_window(random.Random(r.get("seed", 1) * 11 + 3))
    if "form" not in r:
        frng = random.Random(r.get("seed", 1) * 17 + 5)
        r["form"] = frng.choice(ROUGH_FORMS.get(r.get("id"), ("prism", "massive")))
        ax = (frng.gauss(0, 1), frng.gauss(0, 1), frng.gauss(0, 1))
        am = math.sqrt(sum(v * v for v in ax)) or 1.0
        r["axis"] = tuple(round(v / am, 4) for v in ax)
    return r


def ensure_gem(xd, g):
    """Старый огранённый камень/камень в гнезде: средние цвет и чистота."""
    g.setdefault("size", 0.45)
    g.setdefault("col", 0.5)
    g.setdefault("incl", [])
    g.setdefault("cl", 0.6)
    g.setdefault("q", 1.0)
    return g


# ---------- оттенки: одна непрерывная карта на вид, камень — окно в ней ----------
# Карта вида — сумма нескольких волн в миллиметрах (как общая текстура паттернов в CS): значение t ∈ [0, 1]
# переводится в цвет по палитре вида. Камень видит своё окно (смещение в карте — из seed, поворот — как его
# поставили при разметке): мелкий почти всегда однотонный, крупный ловит переходы. Палитра: (t, цвет, имя,
# ценность оттенка); середина (t≈0.5) — основной цвет вида, края карты — редкие оттенки.
# zoning — как рынок смотрит на разноцветность: penalty (рубин, изумруд: зональность — дефект), parti (сапфир:
# размытые зоны — минус, чёткий двухцветный «парти» — плюс), collector (топаз, аметист: двухцветные — дороже).

COLOR_MAPS = {
    "ruby": {"lam": (16.0, 34.0), "gain": 0.9, "sharp": 0.8, "zoning": "penalty",
             "pal": ((0.0, (215, 70, 150), "малиновый", 0.7), (0.28, (230, 62, 105), "розово-красный", 0.85),
                     (0.5, (238, 72, 82), "красный", 1.0), (0.72, (226, 34, 64), "«голубиная кровь»", 1.35),
                     (1.0, (240, 112, 70), "оранжево-красный", 0.75))},
    "sapphire": {"lam": (18.0, 34.0), "gain": 1.0, "sharp": 1.0, "zoning": "parti",
                 "pal": ((0.0, (60, 190, 175), "бирюзовый", 0.7), (0.5, (80, 125, 245), "синий", 1.0),
                         (0.66, (50, 85, 225), "«королевский» синий", 1.3), (0.84, (130, 95, 225), "фиолетовый", 0.85),
                         (1.0, (240, 195, 70), "жёлтый", 0.75))},
    "emerald": {"lam": (18.0, 36.0), "gain": 0.8, "sharp": 0.7, "zoning": "penalty",
                "pal": ((0.0, (60, 195, 180), "голубовато-зелёный", 1.05), (0.5, (80, 215, 115), "зелёный", 1.0),
                        (0.7, (40, 190, 90), "густо-зелёный", 1.25), (1.0, (165, 215, 80), "желтовато-зелёный", 0.7))},
    "topaz": {"lam": (17.0, 34.0), "gain": 1.1, "sharp": 1.2, "zoning": "collector",
              "pal": ((0.0, (130, 190, 250), "голубой", 0.8), (0.25, (245, 240, 215), "бесцветный", 0.4),
                      (0.5, (250, 200, 80), "золотой", 1.0), (0.78, (250, 140, 60), "имперский", 1.7),
                      (1.0, (240, 120, 150), "розовый", 1.5))},
    "amethyst": {"lam": (17.0, 34.0), "gain": 1.05, "sharp": 1.3, "zoning": "collector",
                 "pal": ((0.0, (245, 205, 80), "цитриновый", 0.9), (0.25, (220, 195, 240), "лавандовый", 0.55),
                         (0.5, (170, 90, 230), "фиолетовый", 1.0), (0.8, (115, 45, 185), "«сибирский»", 1.35),
                         (1.0, (90, 40, 120), "тёмный", 0.95))},
}
WAVE_AMPS = (1.0, 0.6, 0.4, 0.25)
_WAVES = {}

# Зоны роста по геометрии кристалла (atlas §1.9): полосы параллельны граням.
# hex — шестиугольником вокруг оси (корунд, берилл); rhomb — под гранями ромбоэдра
# (кварц/аметист), tip — цвет гуще к верхушке (+z). amp — сдвиг по палитре, lam — шаг (мм).
# Та же формула — в шейдере (game/gem_fs.glsl: zone_t); считается в осях кристалла (мм).
ZONES = {
    "amethyst": {"mode": "rhomb", "amp": 0.06, "lam": 1.6, "tip": 0.10},
    "sapphire": {"mode": "hex", "amp": 0.05, "lam": 1.2, "tip": 0.0},
    "ruby": {"mode": "hex", "amp": 0.04, "lam": 1.5, "tip": 0.0},
    "emerald": {"mode": "hex", "amp": 0.035, "lam": 2.0, "tip": 0.0},
    "topaz": {"mode": "hex", "amp": 0.03, "lam": 2.2, "tip": 0.03},
}
ZONE_MODES = {"hex": 0, "rhomb": 1}
_RHOMB = math.radians(51.8)                           # нормаль грани r кварца к оси c


def zone_phase(o):
    """Фаза полос — своя у каждого камня (от его окна в карте)."""
    if not o:
        return 0.0
    v = (o[0] * 0.0137 + o[1] * 0.0291 + o[2] * 0.0173) % 1.0
    return v * math.tau


def zone_t(gid, pc, o):
    """Сдвиг t от зон роста; pc — точки в осях кристалла (мм, ось c = z), o — окно камня."""
    import numpy as np
    z = ZONES.get(gid)
    pc = np.asarray(pc, float).reshape(-1, 3)
    if not z or o is None:
        return np.zeros(len(pc))
    x, y, h = pc[:, 0], pc[:, 1], pc[:, 2]
    if z["mode"] == "rhomb":
        s, c = math.sin(_RHOMB), math.cos(_RHOMB)
        d = np.full(len(pc), -1e9)
        for k in range(6):
            a = k * math.pi / 3
            sg = 1.0 if k % 2 == 0 else -1.0
            d = np.maximum(d, x * s * math.cos(a) + y * s * math.sin(a) + h * c * sg)
    else:
        d = np.maximum(np.maximum(np.abs(x), np.abs(0.5 * x + 0.866 * y)), np.abs(-0.5 * x + 0.866 * y))
    band = np.tanh(2.2 * np.sin(math.tau * d / z["lam"] + zone_phase(o))) / math.tanh(2.2)
    return z["amp"] * band + z["tip"] * np.clip(h / 3.0, -1.0, 1.0)


def color_map(gid):
    return COLOR_MAPS.get(gid) or {"lam": (8.0, 16.0), "gain": 0.6, "sharp": 0.8, "zoning": "penalty",
                                   "pal": ((0.5, (200, 200, 200), "", 1.0),)}


def waves(gid):
    """Волны карты вида: [(kx, ky, kz, фаза)] в 1/мм — одни и те же для всех камней вида."""
    if gid not in _WAVES:
        cm = color_map(gid)
        rng = random.Random("colormap:" + gid)
        out = []
        for i in range(4):
            lam = cm["lam"][0] + (cm["lam"][1] - cm["lam"][0]) * rng.random()
            v = [rng.gauss(0, 1) for _ in range(3)]
            m = math.sqrt(sum(x * x for x in v)) or 1.0
            k = math.tau / lam
            out.append((v[0] / m * k, v[1] / m * k, v[2] / m * k, rng.uniform(0, math.tau)))
        _WAVES[gid] = out
    return _WAVES[gid]


def field_t(gid, pts, o=None):
    """t ∈ [0, 1] карты вида в точках (мм); pts — список (x, y, z). Та же формула — в шейдере (gem_gl).
    o — начало окна камня в карте (центр кристалла): с ним добавляются зоны роста по граням."""
    import numpy as np
    cm = color_map(gid)
    p = np.asarray(pts, float).reshape(-1, 3)
    s = np.zeros(len(p))
    for a, (kx, ky, kz, ph) in zip(WAVE_AMPS, waves(gid)):
        s += a * np.sin(p @ np.array([kx, ky, kz]) + ph)
    t = 0.5 + 0.5 * s / sum(WAVE_AMPS) * cm["gain"]
    if o is not None:
        t = t + zone_t(gid, p - np.asarray(o, float), o)
    sh = cm["sharp"]
    t = 0.5 + 0.5 * np.tanh(sh * (t - 0.5) * 2) / math.tanh(sh)
    return np.clip(t, 0.0, 1.0)


def pal_at(gid, t):
    """Цвет и ценность оттенка в точке t палитры (непрерывно)."""
    pal = color_map(gid)["pal"]
    if t <= pal[0][0]:
        return pal[0][1], pal[0][3]
    for (t0, c0, _, v0), (t1, c1, _, v1) in zip(pal, pal[1:]):
        if t <= t1:
            k = (t - t0) / max(1e-6, t1 - t0)
            return tuple(a + (b - a) * k for a, b in zip(c0, c1)), v0 + (v1 - v0) * k
    return pal[-1][1], pal[-1][3]


def nearest_stop(gid, t):
    pal = color_map(gid)["pal"]
    return min(range(len(pal)), key=lambda i: abs(pal[i][0] - t))


_BALL = []


def unit_ball(n=240):
    """Равномерные точки в единичном шаре (одни и те же — оценка детерминирована)."""
    if not _BALL:
        rng = random.Random(4242)
        while len(_BALL) < n:
            p = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
            if p[0] * p[0] + p[1] * p[1] + p[2] * p[2] <= 1:
                _BALL.append(p)
    return _BALL


def color_stats(gid, ts):
    """Состав оттенков по значениям карты: главный (по медиане), доля заметно других оттенков (|Δt| > 0.12) с
    каждой стороны; ценность оттенка — среднее по объёму."""
    import numpy as np
    t = np.asarray(ts, float)
    if not len(t):
        return None
    med = float(np.median(t))
    lo, hi = t[t < med - 0.12], t[t > med + 0.12]
    n = len(t)
    main = nearest_stop(gid, med)
    top = [[main, round(1 - (len(lo) + len(hi)) / n, 3)]]
    for side in sorted((lo, hi), key=len, reverse=True):
        if len(side) / n >= 0.05:
            i = nearest_stop(gid, float(side.mean()))
            if i == main:                                  # тот же оттенок палитры, но заметно другой тон
                i = max(0, min(len(color_map(gid)["pal"]) - 1, main + (1 if side is hi else -1)))
            top.append([i, round(len(side) / n, 3)])
    hv = float(np.mean([pal_at(gid, float(x))[1] for x in t]))
    return {"top": top, "hv": round(hv, 3), "mi": round(1 - top[0][1], 3)}


def sphere_stats(gid, center, radius_mm, o=None):
    """Оттенки шара радиусом radius_mm вокруг точки карты (сырой камень «как есть», камень с прилавка).
    o — центр кристалла в карте (зоны роста); у сырья это и есть центр шара."""
    pts = [(center[0] + x * radius_mm, center[1] + y * radius_mm, center[2] + z * radius_mm)
           for x, y, z in unit_ball()]
    return color_stats(gid, field_t(gid, pts, o))


def stone_mm_radius(xd, gid, ct):
    sg = gem_def(xd, gid).get("sg", 3.5)
    return (3 * 200.0 * ct / sg / (4 * math.pi)) ** (1 / 3)


def k_zoning(gid, cz):
    """Как рынок смотрит на разноцветность (реальные ориентиры: зональность рубина/изумруда −20…−45%,
    сапфир «парти» с чёткими зонами до +40%, аметрин и двухцветный топаз до +60%)."""
    if not cz:
        return 1.0
    mi = cz.get("mi", 0.0)
    top = cz.get("top", [])
    second = top[1][1] if len(top) > 1 else 0.0
    gap = abs(top[0][0] - top[1][0]) if len(top) > 1 else 0
    kind = color_map(gid)["zoning"]
    if kind == "penalty":
        return 1 - 0.45 * min(1.0, mi / 0.6)
    if kind == "parti":
        if second >= 0.25 and gap >= 2:                  # два далёких оттенка крупными зонами — «парти»
            return 1 + 0.4 * min(1.0, second / 0.4)
        return 1 - 0.35 * min(1.0, mi / 0.6)
    if second >= 0.2:                                    # collector: двухцветный — редкость и спрос
        return 1 + 0.6 * min(1.0, mi / 0.5)
    return 1 + 0.15 * mi


def k_hue(cz):
    return cz.get("hv", 1.0) if cz else 1.0


def gem_colors(xd, g):
    """Состав оттенков огранённого камня (из огранки — точный; иначе — по шару его окна в карте)."""
    if g.get("cz"):
        return g["cz"]
    cf = g.get("cf")
    if not cf:
        return None
    return sphere_stats(g["id"], cf["b"], stone_mm_radius(xd, g["id"], g.get("size", 0.45)), cf.get("o"))


def rough_colors(xd, r):
    ensure_rough(xd, r)
    return sphere_stats(r["id"], r["cf"]["o"], stone_mm_radius(xd, r["id"], r["size"]), r["cf"]["o"])


def colors_text(gid, cz):
    if not cz or not cz.get("top"):
        return ""
    pal = color_map(gid)["pal"]
    parts = [f"{pal[i][2]} {s * 100:.0f}%" for i, s in cz["top"]]
    return "оттенки: " + " · ".join(parts) if len(parts) > 1 else "оттенок: " + pal[cz["top"][0][0]][2]


def random_rotation(rng):
    """Случайный поворот 3×3 (строки)."""
    q = [rng.gauss(0, 1) for _ in range(4)]
    m = math.sqrt(sum(x * x for x in q))
    w, x, y, z = (v / m for v in q)
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


# ---------- чистота, цвет ----------

def incl_weight(xd, inc, scale=1.0, gid=None):
    """Заметность примеси: вид × размер^1.5; со стороны короны (−z, видна сквозь площадку) — сильнее.
    gid — вид камня: у изумруда включения — норма и весят меньше."""
    j = cfg(xd)
    kw = j["incl_kinds"].get(inc["k"], {"w": 1.0})["w"]
    if gid:
        kw *= incl_recipe(gid).get("clarity", 1.0)
    if inc["k"] == "silk":
        return kw * inc.get("d", 0.5)
    r = inc["r"] * scale / 100.0
    vis = 1.3 if inc["p"][2] < 0 else 1.0
    return kw * 9.0 * r ** 1.5 * vis


def clarity(xd, incl, scale=1.0, gid=None):
    """Чистота 0–1 по примесям (в единицах огранённого камня; scale — пересчёт; gid — вид камня)."""
    return round(math.exp(-sum(incl_weight(xd, i, scale, gid) for i in incl)), 3)


def rough_clarity(xd, r):
    """Чистота сырого камня, если гранить «как есть» (все примеси остаются): радиус — в доле кристалла,
    огранённый камень ≈ 55% радиуса кристалла."""
    return clarity(xd, r.get("incl", []), scale=100 / 0.55, gid=r.get("id"))


def grade(xd, cl):
    return next(w for v, w in cfg(xd)["clarity_grades"] if cl >= v)


def color_word(xd, col):
    return next(w for v, w in cfg(xd)["color_words"] if col >= v)


def tint(base, col):
    """Цвет тела камня по насыщенности: бледный — к белому, густой — темнее и чище."""
    pale = tuple(b + (255 - b) * 0.55 for b in base)
    deep = tuple(b * 0.78 for b in base)
    if col < 0.5:
        k = col / 0.5
        return tuple(int(p + (b - p) * k) for p, b in zip(pale, base))
    k = (col - 0.5) / 0.5
    return tuple(int(b + (d - b) * k) for b, d in zip(base, deep))


def _expk(lo, hi, t):
    """Множитель от lo до hi экспоненциально по t ∈ [0, 1]."""
    t = max(0.0, min(1.0, t))
    return lo * (hi / lo) ** t


def k_color(xd, col):
    return _expk(*cfg(xd)["color_k"], col)


def k_clarity(xd, cl):
    return _expk(*cfg(xd)["clarity_k"], cl)


def k_cut(xd, q):
    """Цена от качества огранки: q^1.5 (100% — ×1, 500% — ×11)."""
    return max(0.3, q) ** cfg(xd)["cut_price_exp"]


# ---------- цена ----------

def cut_value(xd, g):
    """Цена огранённого: цена карата вида × караты^1.8 × насыщенность × чистота × огранка × вид огранки × звезда
    × ценность оттенков × разноцветность (по виду: дефект, «парти» или редкость)."""
    ensure_gem(xd, g)
    j = cfg(xd)
    c = CUT_BY_ID.get(g.get("cut"), {"value": 1.0})
    star = 1 + 2.0 * g.get("star", 0.0)
    cz = gem_colors(xd, g)
    v = per_ct(xd, g["id"]) * g["size"] ** j["ct_exp"] * k_color(xd, g["col"]) * k_clarity(xd, g["cl"]) * \
        k_cut(xd, g["q"]) * c["value"] * star * k_hue(cz) * k_zoning(g["id"], cz)
    return int(round(v, -1)) if v > 100 else int(v)


def rough_value(xd, r):
    """Цена сырого: доля ожидаемой цены огранённого (выход массы, чистота «как есть», обычная работа)."""
    ensure_rough(xd, r)
    j = cfg(xd)
    ct = r["size"] * j["yield"] * rough_yield(r)
    cz = rough_colors(xd, r)
    v = j["rough_k"] * per_ct(xd, r["id"]) * ct ** j["ct_exp"] * k_color(xd, r["col"]) * \
        k_clarity(xd, rough_clarity(xd, r)) * k_hue(cz) * k_zoning(r["id"], cz)
    return int(round(v, -1)) if v > 100 else int(v)


def rough_visible_value(xd, r):
    """Цена куска по видимому: масса, форма, цвет; чистота — средняя (нутра продавец не знает)."""
    ensure_rough(xd, r)
    j = cfg(xd)
    ct = r["size"] * j["yield"] * rough_yield(r)
    v = j["rough_k"] * per_ct(xd, r["id"]) * ct ** j["ct_exp"] * k_color(xd, r["col"]) * k_clarity(xd, 0.55)
    return int(round(v, -1)) if v > 100 else int(v)


def estimate(xd, gid, ct, col, cl, q=1.0, cut=None, star=0.0, cz=None):
    return cut_value(xd, {"id": gid, "size": ct, "col": col, "cl": cl, "q": q, "cut": cut, "star": star, "cz": cz})


# ---------- сила ----------

def power(xd, g):
    """Множитель статов камня: ≈1 у среднего (0.45 кар., ровный цвет, мелкие примеси, добротная огранка);
    растёт нелинейно, после 1.5 — мягкий потолок (≈ ×5)."""
    if "cl" not in g:                                     # старый камень в гнезде: только качество
        return g.get("q", 1.0)
    p = cfg(xd)["power"]
    s = (max(0.05, g.get("size", 0.45)) / p["ref_ct"]) ** p["ct_exp"]
    s *= (k_color(xd, g.get("col", 0.5)) / k_color(xd, 0.5)) ** 0.6
    s *= (k_clarity(xd, g.get("cl", 0.6)) / k_clarity(xd, 0.6)) ** 0.6
    s *= max(0.3, g.get("q", 1.0)) ** p["cut_exp"]                 # огранка 500% — ×3 силы
    s *= 1 + 0.5 * g.get("star", 0.0)
    soft, cap = p["soft"], p["cap"]
    if s > soft:
        s = soft + (cap - soft) * (1 - math.exp(-(s - soft) / (cap - soft)))
    return round(max(p["min"], s), 3)


def socket_entry(g):
    """Что хранится в гнезде артефакта (без формы)."""
    return {k: v for k, v in g.items() if k != "uid"}            # камень целиком: его можно снова вынуть


def unsocket_cost(xd, g):
    """Снять камень с оправы: работа ювелира — 5% цены камня, не меньше 150 золота."""
    return max(150, int(round(cut_value(xd, dict(g)) * 0.05, -1)))


def describe(xd, g, rough=False):
    """Строки описания камня: караты, цвет, чистота, огранка/цена."""
    gd = gem_def(xd, g["id"])
    if rough:
        ensure_rough(xd, g)
        n = len([i for i in g["incl"] if i["k"] != "silk"])
        silk = any(i["k"] == "silk" for i in g["incl"])
        out = [f"{g['size']:.2f} кар. · цвет {color_word(xd, g['col'])} · {shape_name(g)}",
               f"примесей: {n}" + (" · шёлк (звезда в кабошоне)" if silk else "") +
               f" · «как есть»: {grade(xd, rough_clarity(xd, g)).lower()}"]
        ct_ = colors_text(g["id"], rough_colors(xd, g))
        return out + ([ct_] if ct_ else [])
    ensure_gem(xd, g)
    out = [f"{g['size']:.2f} кар. · {cut_name(g.get('cut'))}",
           f"цвет {color_word(xd, g['col'])} · {grade(xd, g['cl']).lower()} · огранка {g['q'] * 100:.0f}%"]
    if g.get("star", 0) > 0.05:
        out.append(f"звезда {g['star'] * 100:.0f}%")
    ct_ = colors_text(g["id"], gem_colors(xd, g))
    if ct_:
        out.append(ct_)
    return out


def stat_text(xd, g):
    from sim import artifacts as A
    k = power(xd, g)
    return "; ".join(A.entry_text(e, k) for e in gem_def(xd, g["id"])["stats"])


# ---------- рынок ----------

def roll_cut(xd, rng, uid, gid):
    """Огранённый камень на прилавке: свой размер, цвет, примеси (в единицах камня), огранка."""
    r = roll_rough(xd, gid, rng, "tmp")
    ct = round(r["size"] * rng.uniform(0.15, 0.25), 2)
    incl = []
    for i in r["incl"]:
        if i["k"] == "silk" or rng.random() < 0.5:
            continue
        inc = dict(i, p=[round(x * 60, 1) for x in i["p"]], r=round(i["r"] * 100 / 0.55, 1))
        incl.append(inc)
    cut = rng.choice([c["id"] for c in CUTS if not c.get("dome") and not c.get("rare")])
    cap = CUT_BY_ID[cut]["cap"]
    sg = gem_def(xd, gid).get("sg", 3.5)
    mmu = (200.0 * ct / sg / 1.6e6) ** (1 / 3)          # мм на единицу формы (объём идеала ≈ 1.6e6)
    rot = random_rotation(rng)
    cf = {"A": [round(v * mmu, 6) for row in rot for v in row], "b": r["cf"]["o"], "o": r["cf"]["o"]}
    g = {"uid": uid, "id": gid, "q": round(Q_MIN + (cap - Q_MIN) * rng.uniform(0.4, 0.9), 2), "size": ct,
         "col": r["col"], "incl": incl, "cl": clarity(xd, incl, gid=gid), "cut": cut, "cf": cf}
    g["cz"] = sphere_stats(gid, cf["b"], stone_mm_radius(xd, gid, ct), cf["o"])
    return g


# ---------- витрина ----------
# Витрина Ювелирной: 6 мест под огранённые камни; с ценником гости таверны покупают камень после похода.
SHOWCASE = {"slots": 6, "sale_k": 0.45, "chance": 0.3}


def showcase_price(xd, g):
    """Цена камня для гостя таверны (дороже, чем отдать рынку)."""
    return int(round(cut_value(xd, g) * SHOWCASE["sale_k"], -1))


def tool_info(tid):
    """(название, цена, описание) лупы или диска."""
    if tid in LOUPE_BY_ID:
        t = LOUPE_BY_ID[tid]
        return t[1], t[3], "кратности линз складываются; сильнее — уже зона резкости"
    if tid == AUTOFOCUS[0]:
        return AUTOFOCUS[1], AUTOFOCUS[2], "лупа сама держит резкость при смене линз (АФ на оправе)"
    d = DISK_BY_ID[tid]
    return d[1], d[4], f"скорость ×{d[2]:.2f} · чистота грани {d[3] * 100:.0f}%"


def next_loupe(owned):
    """Следующая часть лупы на продажу: сначала оправа, потом линзы по порядку."""
    return next((t[0] for t in LOUPE if t[0] not in owned), None)


def roll_jeweler(xd, rng, known, new_rough, owned=()):
    """Бродячий ювелир: книги огранок не случайные — только следующие по качеству, не выше
    максимальной открытой + 50%; 1–2 отборных камня, часть лупы."""
    j = cfg(xd)["jeweler"]
    if rng.random() >= j["chance"]:
        return None
    known = set(known or ())
    top_cap = max_cut_cap(known)
    limit = top_cap + 0.50
    max_books = max(1, int(j["books"][-1]))
    books = book_cuts(known, max_books)
    rare = [c["id"] for c in CUTS
            if c.get("rare") and c["id"] not in known and c["cap"] <= limit]
    if rare and rng.random() < j.get("rare_chance", 0.2):              # авторский свиток — изредка и дорого
        books.append(rng.choice(rare))
    stones = [new_rough(rng) for _ in range(rng.randint(*j["rough"]))]
    nxt = next_loupe(owned)
    tools = [nxt] if nxt and (nxt == "loupe" or rng.random() < 0.7) else []
    if "loupe" in owned and AUTOFOCUS[0] not in owned and rng.random() < 0.5:
        tools.append(AUTOFOCUS[0])
    disks = [d[0] for d in DISKS if d[0] not in owned and d[0] != START_DISK]
    if disks and rng.random() < 0.6:                  # диск — один из ещё не купленных (алмазный — реже)
        tools.append(rng.choices(disks, [0.4 if d == "lap_diamond" else 1.0 for d in disks])[0])
    return {"name": rng.choice(j["names"]), "books": books, "rough": stones, "tools": tools}
