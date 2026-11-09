"""Состояние юнита в бою. Логика — в combat.py."""


class Unit:
    def __init__(self, uid, team, proto_id, proto, cell):
        self.id = uid
        self.team = team
        self.proto_id = proto_id
        self.proto = proto
        self.name = proto["name"]
        self.label = proto["label"]
        self.color = tuple(proto["color"])
        self.role = proto["role"]
        self.boss = proto.get("boss", False)

        self.max_hp = proto["hp"]
        self.hp = self.max_hp
        self.armor = proto.get("armor", 0)
        self.power = proto.get("power", 1.0)   # множитель урона, лечения и щитов навыков
        self.move_time = proto["move_time"]
        atk = proto["attack"]
        self.atk_damage = atk["damage"]
        self.atk_range = atk["range"]
        self.atk_cd = atk["cooldown"]
        self.atk_tag = atk.get("tag")
        self.atk_kind = atk.get("kind")        # копьё: удар на 2 клетки остаётся ближним

        self.ap_max = proto.get("ap_max", 0)
        self.ap_regen = proto.get("ap_regen", 2.0)
        # личная шкала (бывшие PP): у героя копится от его фишки и стартует с нуля, у врага — по таймеру и полная
        self.gauge = proto.get("gauge")
        self.pp_max = proto.get("pp_max", 0)
        self.pp_regen = proto.get("pp_regen", 3.0)
        self.ap = self.ap_max
        self.pp = 0 if self.gauge else self.pp_max
        self.ap_timer = 0.0
        self.pp_timer = 0.0
        self.gauge_acc = {}    # накопители периодических прибавок шкалы («стоит на месте», «в облике»)
        self.passive = proto.get("passive")
        self.skills = list(proto.get("skills", []))
        self.skill_defs = proto.get("skill_defs") or {}  # Combat дополняет из общих данных
        self.resist = proto.get("resist", {})
        self.elite = proto.get("elite", False)
        self.on_death = proto.get("on_death")

        self.cell = tuple(cell)
        self.prev_cell = self.cell
        self.move_t = 1.0      # прогресс шага 0..1
        self.move_dur = 0.0

        self.order = None      # {"type": "move"|"attack"|"skill", ...}
        self.queue = []        # очередь приказов игрока (Shift): то же, что order, по порядку
        self.uses = {}         # сколько раз за бой применён каждый навык — ранги навыков в походе растут от этого
        self.tally = {"dealt": 0, "taken": 0, "absorbed": 0, "healed": 0, "healed_in": 0, "kills": 0,  # статистика боя
                      # заслуги (награды нейросетей): поглотили мои щиты на союзниках, секунды моего контроля,
                      # баффы союзникам и дебаффы врагам, сорванные касты, насмешки, помощь в убийстве
                      "shielded": 0, "cc": 0.0, "buffs": 0, "debuffs": 0, "interrupts": 0, "taunts": 0, "assists": 0,
                      # эффективные (без overkill) заслуги в долях максимального HP цели: так урон по слабому
                      # юниту не ценится выше урона по боссу, а награда не зависит от масштаба боя
                      "dealt_eff": 0.0, "dealt_frac": 0.0, "healed_frac": 0.0, "shielded_frac": 0.0}
        self.shield_src = None # кто поставил текущий щит
        self.hit_by = {}       # кто бил юнита: {юнит: время последнего удара} — помощь в убийстве
        self.last_hit_by = None
        self.mutator = None    # механика врага на тяжёлых сложностях (sim/mutators.py)
        self.mut_t = 0.0
        self.mut_cd = 0.0
        self.phases_left = []  # фазы босса: доли HP, на которых он зовёт подмогу
        self.cast = None       # {"skill", "target", "left", "total", "ap"}
        self.attack_timer = 0.0
        self.last_target = None
        self.wait = 0.0

        self.statuses = {}     # tag -> оставшиеся секунды
        self.ult_count = {}    # счётчики условий ультимейта за бой (sim/kit.py, ult_ready)
        # пассивка-основа (sim/passives.py): таймер, прошлая цель, Дикость/Гармония, ингредиенты, накопитель, ноты
        self.pass_t = 0.0
        self.pass_target = None
        self.pass_acc = 0.0
        self.wild = 0
        self.harmony = 0
        self.recipe = set()
        self.soil = None
        self.notes = []
        self.last_melody = None
        self.marks = {}        # метки-стаки механик классов (sim/kit.py): id -> {"n", "t", "src", "total"}
        self.quiver = proto.get("quiver")      # лучник: активный тип стрел
        self.stun = 0.0
        self.stun_total = 0.0  # длительность текущего оглушения (для таймера на значке)
        self.stun_look = "stun"
        self.shield = 0
        self.shield_time = 0.0
        self.taunted_by = None
        self.taunt_time = 0.0
        self.cooldowns = {}
        self.reaction_cd = {}
        self.dot_acc = 0.0
        self.hazard_acc = 0.0

        self.buffs = {}        # stat -> [значение, оставшиеся секунды]
        self.buff_total = {}   # stat -> полная длительность (для таймера на значке)
        self.regen_acc = 0.0
        self.autocast = {}     # skill id -> {"on": bool, "conds": [{"type", "value"}]}
        self.auto_timer = 0.0

        self.alive = True
        self.ai_timer = 0.0
        self.kite_cd = 0.0

        # призванные (тотемы): не ходят, живут life секунд, не считаются отрядом
        self.summon = proto.get("summon", False)
        self.static = proto.get("static", False)
        self.owner = None
        self.life = None
        self.aura = proto.get("aura")
        self.aura_timer = 0.0
        # облики друида: базовые статы, к которым облик применяется
        self.forms = proto.get("forms", {})
        self.form = None
        self.base = {"armor": self.armor, "atk_damage": self.atk_damage, "atk_range": self.atk_range,
                     "atk_cd": self.atk_cd, "move_time": self.move_time, "atk_kind": self.atk_kind}
        self.asleep = False    # сон: оглушение, которое снимает любой удар
        # особенности врагов глав
        self.flying = proto.get("flying", False)          # над пропастями и водой, клетки не действуют
        self.undying = proto.get("undying")               # нежить: встаёт после смерти, если не добита огнём
        self.risen = False
        self.heat = proto.get("heat")                     # любит жар: в огне сильнее
        self.frost_armor = proto.get("frost_armor")       # ледяная броня: щит восстанавливается, огонь колет
        self.frost_timer = 0.0
        self.ice_walker = proto.get("ice_walker", False)  # не скользит по льду
        self.lifesteal = proto.get("lifesteal", 0.0)      # атаки лечат на долю урона
        self.airborne = 0.0                               # в прыжке (навык с приземлением): не действует
        self.charm_time = 0.0                             # очарован: сражается за другую сторону
        self.hidden = False                               # туман: не виден на разведке
        self.affix = None
        self.ambush = 1.0      # множитель урона удара из скрытности (на время одного удара/навыка)
        self.level = proto.get("level")   # режим героев: уровень героя или врага (враг — от региона)
        self.title = None                 # «ветеран», «чемпион»
        # объект поля (бочка, валун, источник врагов, обоз): не ходит, не бьёт, без статусов
        self.obj = proto.get("object")
        self.spawned = []      # источник: живые выпущенные им враги
        self.spawn_timer = 0.0
        self.igniter = None    # кто поджёг/разбил бочку — ему засчитывается взрыв
        self.fuse = 0.0        # бочка: горящий фитиль, сек до взрыва
        # механики героев
        self.guarded_by = None  # телохранитель: удары по юниту рядом с ним идут в него
        self.guard_time = 0.0
        self.watch = None       # дозор: {"center", "radius", "left", "mult", "shots"}
        self.song = None        # песня барда: такты и ноты
        self.stasis = 0.0       # стазис хрономанта: вне времени, удары не проходят
        self.levitate = 0.0     # невесомость гравитоманта: толчок дальше, падение — урон
        self.levitate_dmg = 0.0
        self.last_ground = None  # геомант: на какой клетке колдовал в прошлый раз
        self.tethered_by = None  # привязь связующего: половина урона — ему
        self.tether_time = 0.0
        self.merged = 0.0        # связующий внутри союзника
        self.merge_host = None
        self.history = []       # (время, клетка, HP) за последние 5 сек — для отката
        self.hist_acc = 0.0

    def buff(self, stat, default):
        b = self.buffs.get(stat)
        return b[0] if b else default

    def total_armor(self):
        return self.armor + self.buff("armor", 0)

    @property
    def moving(self):
        return self.move_t < 1.0

    def slow_mult(self, tags):
        m = 1.0
        for t in self.statuses:
            m = max(m, tags[t].get("slow", 1.0))
        return m

    def skill_ready(self, sid, skill):
        return self.ap >= skill["ap"] and self.cooldowns.get(sid, 0) <= 0

    @property
    def charmed(self):
        return self.charm_time > 0

    def is_enemy(self, other):
        return (self.team != other.team) != (self.charmed != other.charmed)
