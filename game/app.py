"""Приложение: держит профиль (мета) и текущую вылазку, переключает экраны.

Экраны: титульное меню → лагерь-хаб → карта биома → вылазка (карта узлов, бои, награды) → итоги → лагерь."""
from game.battle_scene import BattleScene
from game.run_scenes import MapScene, RunEndScene, rest_scene, reward_scene, shop_scene, trophy_scene
from game.world_scene import WorldScene
from sim.profile import Profile


def stats_path(base, mode="stats"):
    """Профиль режима рядом с основным: profile.json → stats.json / story.json, sandbox.json → sandbox_stats.json."""
    import os
    name = os.path.basename(base)
    name = f"{mode}.json" if name == "profile.json" else name.replace(".json", "") + f"_{mode}.json"
    return os.path.join(os.path.dirname(os.path.abspath(base)), name)


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
        self._relayout_scene(scene)

    def _relayout_scene(self, scene):
        """Сцена-колонка (stage) живёт в координатах 1280×800 — пересчитываем её под этот размер."""
        from ui import theme as T
        if not hasattr(scene, "relayout"):
            return
        if getattr(scene, "stage", False):
            with T.design():
                scene.relayout()
        else:
            scene.relayout()

    def relayout(self):
        """Окно изменилось: пересчитать раскладку текущей сцены."""
        if self.scene is not None:
            self._relayout_scene(self.scene)

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
        if self.profile.mode == "story":
            from game.story_scenes import StoryHub
            self.switch(StoryHub(self))
            return
        new = self.profile.new_heroes()
        if new and not self.profile.sandbox:            # открылась глава — сначала «Новые союзники»
            from game.allies_scene import NewAlliesScene
            self.switch(NewAlliesScene(self, new))
            return
        self.switch(HubScene(self))

    def new_game(self):
        path = self.profile.path
        if self.profile.mode == "story":
            from sim.story import StoryProfile
            self.profile = StoryProfile(self.profile.data, None)
            self.profile.path = path
            self.profile.save()
            return
        self.profile = Profile(self.data, None, mode=self.profile.mode)
        self.profile.path = path
        self.profile.save()

    def mode_path(self, mode):
        """Режим героев хранится отдельно (save/stats.json рядом с основным профилем) — основа не трогается."""
        base = getattr(self, "_base_path", None) or self.profile.path
        if self.profile.mode == "base":
            self._base_path = base = self.profile.path
        if mode == "base" or base is None:
            return base
        return stats_path(base, mode)

    def switch_mode(self, mode):
        """Основная игра ⇄ режим героев: свой профиль у каждого, прогресс не смешивается."""
        if mode == self.profile.mode:
            return
        path = self.mode_path(mode)
        sandbox = self.profile.sandbox
        if mode == "story":                     # сюжет: свои бои (обучающие карты) и свой состав героев
            from sim.story import StoryProfile, story_data
            prof = StoryProfile(story_data(self.data), path, sandbox=sandbox)
        else:
            prof = Profile(self.data, path, sandbox=sandbox, mode=mode)
        prof.mode = mode
        prof.path = path
        self.profile = prof
        self.run = None

    def to_world(self):
        self.profile.remember_autocast(self.run)    # вылазку бросили — настройки автокаста не теряются
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
        self.profile.remember_autocast(self.run)
        if self.run.result:
            end = self.profile.finish_run(self.run)

            def show_end():
                self.switch(RunEndScene(self, end))
            self.switch(trophy_scene(self, end, show_end) if end["trophies"] else RunEndScene(self, end))
        else:
            self.switch(reward_scene(self, summary))

    # ---------- сюжет (sim/story.py) ----------

    def story_go(self):
        """Следующая вылазка сюжета: вступление → цепочка боёв."""
        from game.story_scenes import DialogScene
        prof = self.profile
        exp = prof.current()
        seed = None if self.seed is None else self.seed + prof.expeditions
        self.run = prof.start_chain(seed)
        self.switch(DialogScene(self, exp.get("intro", []), lambda: self._story_battle(0), title=exp["name"]))

    def _story_battle(self, i):
        from game.story_scenes import DialogScene
        run, prof = self.run, self.profile
        node = run.enter(i)
        b = node["story"]

        def fight():
            self.switch(BattleScene(prof.data, node["encounter"], autoplay=self.autoplay,
                                    squad=run.combat_squad(), formation=run.formation,
                                    on_finish=self._story_battle_done, enemy_scale=run.enemy_scale(),
                                    fx=run.combat_fx(), difficulty="normal", cheats=prof.sandbox,
                                    tutorial=None if self.autoplay else b.get("tutorial")))
        if b.get("intro"):
            self.switch(DialogScene(self, b["intro"], fight))
        else:
            fight()

    def _story_battle_done(self, combat, formation):
        from game.story_scenes import BetweenScene, DialogScene
        run, prof = self.run, self.profile
        summary = run.finish_battle(combat, formation)
        run.story_xp = getattr(run, "story_xp", 0) + int(summary.get("xp", 0))
        prof.remember_autocast(run)
        if not run.result:                        # передышка сюжета: перевязали раны
            run.heal_all(prof.story.get("heal_between", 0.0))
            nxt = run.nodes[run.node]["next"][0]
            self.switch(BetweenScene(self, summary, lambda: self._story_battle(nxt)))
            return
        end = prof.finish_chain(run)
        if run.result != "victory":
            lines = [{"who": "narrator", "text": "Отряд отступил к лагерю. Раны заживут — попробуйте ещё раз."},
                     {"who": "narrator", "text": f"Добыто янтаря: {end['amber']}."}]
            self.switch(DialogScene(self, lines, self.to_hub))
            return
        lines = list(run.story.get("outro", [])) + [
            {"who": "narrator", "text": f"Вылазка пройдена. Янтарь: +{end['amber']}."}]
        if end.get("hero_xp"):
            lines.append({"who": "narrator", "text": f"Опыт героев: +{end['hero_xp']} каждому."})
        if end.get("level_ups"):
            from sim import stats
            ups = ", ".join(f"{prof.character(c)['name']} {a}→{b}" for c, a, b in end["level_ups"])
            lines.append({"who": "narrator", "text": f"Новые уровни: {ups}."})
            free = sum(stats.points_free(prof.data, prof.heroes[c]["rpg"]) for c in prof.squad)
            if free:
                lines.append({"who": "narrator", "text": f"Свободных очков характеристик: {free} — "
                                                         "потратить в «Подготовке героев»."})

        def trophies():
            if end["trophies"]:
                self.switch(trophy_scene(self, end, self.to_hub))
            else:
                self.to_hub()
        self.switch(DialogScene(self, lines, trophies))

    def continue_run(self):
        """После награды/отдыха/торговца — обратно на карту вылазки."""
        self.switch(MapScene(self))
