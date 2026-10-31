"""«Новые союзники»: открылась глава — открылись и её герои. Для каждого: зачем он в этой главе (против чего или
с чем сочетается), ключевой навык и кнопка «Посмотреть в деле» — превью навыка. Показывается один раз."""
import pygame

from game.meta_scenes import MetaScene
from game.title_scene import GOLD
from ui import theme as T
from ui import widgets as W
from ui.sprites import SpriteBank

ROLE = {"melee": "ближний бой", "ranged": "дальний бой", "caster": "маг", "support": "поддержка"}


class NewAlliesScene(MetaScene):
    hint = "Новые герои уже в лагере — бесплатно. «Посмотреть в деле» — превью их ключевого навыка."

    def __init__(self, app, entries):
        super().__init__(app)
        self.entries = entries               # [(глава, {"cls", "skill", "why"})]
        self.sprites = SpriteBank()
        self.clock = 0.0
        self.on_back = self.done

    def done(self):
        from game.hub_scene import HubScene
        self.app.profile.mark_seen([h["cls"] for _, h in self.entries])
        self.app.switch(HubScene(self.app))

    def update(self, dt):
        super().update(dt)
        self.clock += dt

    def key(self, k):
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.done()

    def act(self, action):
        prof, data = self.app.profile, self.app.data
        if action[0] == "look":
            from game.meta_scenes import HeroesScene
            h = action[1]
            scene = HeroesScene(self.app, h["cls"], "skills")
            scene.show_skill(h["skill"])
            scene.on_back = lambda: self.app.switch(self)
            self.app.switch(scene)
        elif action[0] == "squad":
            cls = action[1]
            if cls in prof.squad:
                self.say(f"{data.classes[cls]['name']} уже в отряде")
            else:
                ok, msg = prof.toggle_squad(cls)
                self.say(f"{data.classes[cls]['name']} в отряде!" if ok else
                         "Отряд полон — замените кого-нибудь в «Отряде»")
        elif action[0] == "done":
            self.done()

    def draw(self, surf):
        data = self.app.data
        self.hits = []
        surf.fill(T.BG)
        cid = self.entries[0][0]
        b = data.biomes[cid]
        ox = T.content_ox()
        T.text(surf, "Новые союзники", (ox + 24, 14), 32, GOLD, True)
        T.text(surf, f"Глава {b.get('order', 0) + 1} «{b['name']}»: эти герои отвечают на её угрозы — и уже в лагере",
               (ox + 24, 56), 17, T.TEXT_DIM)
        n = len(self.entries)
        cw = min(600, (T.SCREEN_W - 48 - (n - 1) * 16) // max(1, n))
        x = (T.SCREEN_W - (n * cw + (n - 1) * 16)) // 2
        for i, (ch, h) in enumerate(self.entries):
            r = pygame.Rect(x + i * (cw + 16), 96, cw, 520)
            self._card(surf, r, ch, h)
        done = pygame.Rect(T.SCREEN_W // 2 - 150, 640, 300, 50)
        W.button(surf, done, "В лагерь", self.mouse, accent=GOLD)
        self.hit(done, ("done",), "Герои останутся доступны в «Отряде»")
        self.draw_footer(surf)

    def _card(self, surf, r, cid, h):
        prof, data = self.app.profile, self.app.data
        cls = h["cls"]
        c = data.classes[cls]
        pygame.draw.rect(surf, T.PANEL, r, border_radius=12)
        pygame.draw.rect(surf, tuple(c["color"]), r, 2, border_radius=12)
        img = self.sprites.get([cls], cls, tuple(c["color"]), look=c.get("look"))
        img = pygame.transform.scale(img, (img.get_width() * 3, img.get_height() * 3))
        bob = 4 * __import__("math").sin(self.clock * 2 + r.x)
        pygame.draw.ellipse(surf, (24, 26, 32), (r.x + 24, r.y + 186, 150, 26))
        surf.blit(img, (r.x + 100 - img.get_width() / 2, r.y + 200 - img.get_height() - bob))
        x = r.x + 200
        T.text(surf, c["name"], (x, r.y + 18), 26, T.TEXT, True)
        T.text(surf, ROLE.get(c["role"], c["role"]), (x, r.y + 52), 15, T.TEXT_DIM)
        g = c.get("gauge") or {}
        if g:
            T.text(surf, f"Шкала «{g['name']}»", (x, r.y + 74), 14, tuple(g.get("color", (200, 200, 200))), True)
        y = r.y + 224
        T.text(surf, "Зачем он здесь", (r.x + 18, y), 17, GOLD, True)
        y += 26
        for line in T.wrap(h["why"], 15, r.w - 36):
            T.text(surf, line, (r.x + 18, y), 15, T.TEXT)
            y += 20
        y += 10
        sk = data.skills[h["skill"]]
        T.text(surf, f"Ключевой навык: {sk['name']}", (r.x + 18, y), 16, (255, 180, 120), True)
        y += 24
        for line in T.wrap(sk["desc"], 14, r.w - 36)[:3]:
            T.text(surf, line, (r.x + 18, y), 14, (200, 205, 220))
            y += 18
        look = pygame.Rect(r.x + 18, r.bottom - 58, (r.w - 50) // 2, 40)
        W.button(surf, look, "Посмотреть в деле", self.mouse, accent=(170, 140, 255))
        self.hit(look, ("look", h), "Превью ключевого навыка на манекенах")
        join = pygame.Rect(look.right + 14, r.bottom - 58, (r.w - 50) // 2, 40)
        if cls in prof.squad:
            T.text(surf, "В отряде", join.center, 18, GOLD, True, center=True)
        else:
            W.button(surf, join, "В отряд", self.mouse, accent=GOLD)
            self.hit(join, ("squad", cls), "Взять в отряд (если есть место; заменить — в «Отряде»)")
