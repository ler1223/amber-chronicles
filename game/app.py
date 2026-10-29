"""Приложение: держит профиль (мета) и текущую вылазку, переключает экраны.

Экраны: титульное меню → лагерь-хаб → карта биома → вылазка (карта узлов, бои, награды) → итоги → лагерь."""
from game.battle_scene import BattleScene
from game.run_scenes import MapScene, RunEndScene, rest_scene, reward_scene, shop_scene, trophy_scene
from game.world_scene import WorldScene
from sim.profile import Profile


class App:
    """profile — sim.profile.Profile; по умолчанию профиль в памяти (без сохранения).
    seed — сид первой вылазки, следующие берут seed + номер вылазки."""

    def __init__(self, data, seed=None, autoplay=False, profile=None, start="title"):
        self.data = data
        self.autoplay = autoplay
        self.seed = seed
        self.profile = profile or Profile(data)
        self.run = None
        self.scene = None
        self.quit = False
        self._campfire = None
        {"title": self.to_title, "hub": self.to_hub, "world": self.to_world}[start]()

    def switch(self, scene):
        self.scene = scene

    def campfire(self):
        """Один костёр на меню и лагерь — огонь не начинается заново при переходе."""
        if self._campfire is None:
            from ui.campfire import Campfire
            self._campfire = Campfire(self.data)
        return self._campfire

    def to_title(self):
        from game.title_scene import TitleScene
        self.run = None
        self.switch(TitleScene(self))

    def to_hub(self):
        from game.hub_scene import HubScene
        self.run = None
        new = self.profile.new_heroes()
        if new and not self.profile.sandbox:            # открылась глава — сначала «Новые союзники»
            from game.allies_scene import NewAlliesScene
            self.switch(NewAlliesScene(self, new))
            return
        self.switch(HubScene(self))

    def new_game(self):
        path = self.profile.path
        self.profile = Profile(self.data, None)
        self.profile.path = path
        self.profile.save()

    def to_world(self):
        self.run = None
        self.switch(WorldScene(self))

    def start_expedition(self, region_id):
        seed = None if self.seed is None else self.seed + self.profile.expeditions
        self.run = self.profile.start_run(region_id, seed)
        self.switch(MapScene(self))

    def enter_node(self, nid):
        node = self.run.enter(nid)
        t = node["type"]
        if t in ("battle", "elite", "boss", "guard"):
            self.switch(BattleScene(self.data, node["encounter"], autoplay=self.autoplay,
                                    squad=self.run.combat_squad(), formation=self.run.formation,
                                    on_finish=self.battle_done, enemy_scale=self.run.enemy_scale(),
                                    scout_hp=bool(self.run.bonus.get("scout_hp")), fx=self.run.combat_fx(),
                                    difficulty=self.run.difficulty, cheats=self.profile.sandbox))
        elif t == "rest":
            self.switch(rest_scene(self))
        elif t == "shop":
            self.switch(shop_scene(self))

    def battle_done(self, combat, formation):
        summary = self.run.finish_battle(combat, formation)
        if self.run.result:
            end = self.profile.finish_run(self.run)

            def show_end():
                self.switch(RunEndScene(self, end))
            self.switch(trophy_scene(self, end, show_end) if end["trophies"] else RunEndScene(self, end))
        else:
            self.switch(reward_scene(self, summary))

    def continue_run(self):
        """После награды/отдыха/торговца — обратно на карту вылазки."""
        self.switch(MapScene(self))
