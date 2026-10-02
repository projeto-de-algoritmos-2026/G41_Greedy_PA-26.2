import argparse
import os
from dataclasses import dataclass

import pygame


SCREEN_WIDTH = 960
SCREEN_HEIGHT = 640
ROOM_WIDTH = 760
ROOM_HEIGHT = 480
BACKPACK_CAPACITY = 32.0
PLAYER_SPEED = 220


@dataclass
class Item:
    name: str
    x: float
    y: float
    weight: float
    value: int
    total_available: int
    color: tuple[int, int, int]
    radius: int = 14
    collected: bool = False

    def draw(self, surface, font):
        if self.collected:
            return

        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surface, (255, 255, 255), (int(self.x), int(self.y)), self.radius, 2)

        label = font.render(self.name, True, (230, 230, 230))
        surface.blit(label, (self.x - 26, self.y - 32))

        meta = font.render(f"{self.total_available}x / {self.weight}kg / {self.value}p", True, (220, 220, 220))
        surface.blit(meta, (self.x - 45, self.y + 18))


class Player:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.radius = 18
        self.speed = PLAYER_SPEED

    def update(self, dt, keys):
        dx = 0
        dy = 0

        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += 1

        if dx != 0 or dy != 0:
            length = (dx * dx + dy * dy) ** 0.5
            self.x += (dx / length) * self.speed * dt
            self.y += (dy / length) * self.speed * dt

        self.x = max(50, min(self.x, ROOM_WIDTH - 50))
        self.y = max(80, min(self.y, ROOM_HEIGHT - 30))

    def draw(self, surface):
        pygame.draw.circle(surface, (90, 180, 255), (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surface, (20, 40, 80), (int(self.x), int(self.y)), self.radius, 3)


class BackpackUI:
    def __init__(self, x: float, y: float, width: float, height: float, capacity: float):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.capacity = capacity
        self.current_weight = 0.0
        self.total_value = 0
        self.collected_items: list[str] = []

    def add_item(self, item: Item):
        self.current_weight += item.weight
        self.total_value += item.value
        self.collected_items.append(item.name)

    def percent(self) -> float:
        if self.capacity <= 0:
            return 0.0
        return min(self.current_weight / self.capacity, 1.0)

    def draw(self, surface, font):
        pygame.draw.rect(surface, (22, 24, 31), (self.x, self.y, self.width, self.height), border_radius=10)
        pygame.draw.rect(surface, (60, 60, 70), (self.x, self.y, self.width, self.height), 2, border_radius=10)

        bar_x = self.x + 18
        bar_y = self.y + 42
        bar_w = self.width - 36
        bar_h = 24

        pygame.draw.rect(surface, (35, 42, 55), (bar_x, bar_y, bar_w, bar_h), border_radius=12)
        fill = max(0.0, min(self.percent(), 1.0))
        pygame.draw.rect(surface, (80, 220, 120), (bar_x, bar_y, bar_w * fill, bar_h), border_radius=12)

        title = font.render("MOCHILA", True, (255, 255, 255))
        surface.blit(title, (self.x + 18, self.y + 10))

        info = font.render(f"{self.current_weight:.1f}/{self.capacity:.1f} kg", True, (235, 235, 235))
        surface.blit(info, (self.x + 18, self.y + 76))

        value_text = font.render(f"Valor total: {self.total_value} pts", True, (255, 214, 102))
        surface.blit(value_text, (self.x + 18, self.y + 106))

        if self.collected_items:
            item_list = font.render("Coletado: " + ", ".join(self.collected_items[:3]), True, (180, 220, 255))
            surface.blit(item_list, (self.x + 18, self.y + 132))


class Game:
    def __init__(self, headless: bool = False):
        self.headless = headless
        if self.headless:
            os.environ["SDL_VIDEODRIVER"] = "dummy"

        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Laboratório de Loot")

        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 22)
        self.big_font = pygame.font.SysFont(None, 32)

        self.player = Player(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        self.backpack = BackpackUI(620, 470, 290, 150, BACKPACK_CAPACITY)
        self.items = [
            Item(name="Soro Curativo", x=150, y=120, weight=1.5, value=18, total_available=8, color=(80, 200, 130)),
            Item(name="Pólvora", x=265, y=170, weight=2.0, value=32, total_available=6, color=(255, 180, 80)),
            Item(name="Combustível", x=500, y=140, weight=3.2, value=45, total_available=5, color=(190, 120, 240)),
            Item(name="Soro Curativo", x=360, y=260, weight=1.5, value=18, total_available=8, color=(80, 200, 130)),
            Item(name="Pólvora", x=660, y=240, weight=2.0, value=32, total_available=6, color=(255, 180, 80)),
            Item(name="Combustível", x=210, y=330, weight=3.2, value=45, total_available=5, color=(190, 120, 240)),
        ]

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
        return True

    def update(self, dt):
        keys = pygame.key.get_pressed()
        self.player.update(dt, keys)

        for item in self.items:
            if item.collected:
                continue

            distance = ((item.x - self.player.x) ** 2 + (item.y - self.player.y) ** 2) ** 0.5
            if distance < 25:
                item.collected = True
                self.backpack.add_item(item)

    def draw_background(self):
        self.screen.fill((15, 17, 22))

        room_rect = pygame.Rect(30, 30, ROOM_WIDTH, ROOM_HEIGHT)
        pygame.draw.rect(self.screen, (40, 45, 55), room_rect, border_radius=16)
        pygame.draw.rect(self.screen, (85, 92, 104), room_rect, 3, border_radius=16)

        for sx in range(60, ROOM_WIDTH, 120):
            pygame.draw.rect(self.screen, (58, 62, 74), (sx, 80, 60, 260), border_radius=12)

        pygame.draw.rect(self.screen, (24, 31, 38), (140, 80, 90, 180), border_radius=10)
        pygame.draw.rect(self.screen, (24, 31, 38), (340, 90, 120, 160), border_radius=10)
        pygame.draw.rect(self.screen, (24, 31, 38), (560, 95, 120, 170), border_radius=10)

        label = self.big_font.render("SALA DE LOOT / LABORATÓRIO", True, (255, 255, 255))
        self.screen.blit(label, (55, 18))

    def draw(self):
        self.draw_background()

        for item in self.items:
            item.draw(self.screen, self.font)

        self.player.draw(self.screen)
        self.backpack.draw(self.screen, self.font)

        info = self.font.render("Use WASD ou setas para mover", True, (200, 200, 200))
        self.screen.blit(info, (40, 530))

        pygame.display.flip()

    def run(self):
        running = True
        last_time = pygame.time.get_ticks()

        while running:
            now = pygame.time.get_ticks()
            dt = (now - last_time) / 1000
            last_time = now

            running = self.handle_events()
            self.update(dt)
            self.draw()
            self.clock.tick(60)

        pygame.quit()


def parse_args():
    parser = argparse.ArgumentParser(description="Base do jogo de loot em laboratório")
    parser.add_argument("--headless", action="store_true", help="Executa em modo sem janela (para testes automáticos)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        game = Game(headless=True)
        pygame.time.delay(500)
        pygame.quit()
    else:
        game = Game(headless=False)
        game.run()