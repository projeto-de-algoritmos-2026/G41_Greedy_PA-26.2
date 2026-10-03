import argparse
import os
from collections import Counter
from dataclasses import dataclass

import pygame


SCREEN_WIDTH = 960
SCREEN_HEIGHT = 640
ROOM_WIDTH = 760
ROOM_HEIGHT = 480
BACKPACK_CAPACITY = 7.0
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

    def collides_with(self, player):
        distance_squared = (self.x - player.x) ** 2 + (self.y - player.y) ** 2
        collision_distance = self.radius + player.radius
        return not self.collected and distance_squared <= collision_distance ** 2


class Door:
    def __init__(self, x: int, y: int, width: int = 34, height: int = 90):
        self.rect = pygame.Rect(x, y, width, height)
        self.open = False

    def collides_with(self, player):
        player_rect = pygame.Rect(
            player.x - player.radius,
            player.y - player.radius,
            player.radius * 2,
            player.radius * 2,
        )
        return not self.open and self.rect.colliderect(player_rect)

    def is_near(self, player):
        closest_x = max(self.rect.left, min(player.x, self.rect.right))
        closest_y = max(self.rect.top, min(player.y, self.rect.bottom))
        distance_squared = (player.x - closest_x) ** 2 + (player.y - closest_y) ** 2
        return distance_squared <= (player.radius + 22) ** 2

    def interact(self, player, backpack):
        self.open = not self.open

    def draw(self, surface, font):
        color = (90, 190, 130) if self.open else (180, 105, 65)
        pygame.draw.rect(surface, color, self.rect, border_radius=5)
        pygame.draw.rect(surface, (235, 225, 205), self.rect, 2, border_radius=5)
        label = font.render("ABERTA" if self.open else "FECHADA", True, (245, 245, 245))
        surface.blit(label, (self.rect.x - 16, self.rect.bottom + 5))


class Player:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.radius = 18
        self.speed = PLAYER_SPEED

    def update(self, dt, keys, obstacles=()):
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
            move_x = (dx / length) * self.speed * dt
            move_y = (dy / length) * self.speed * dt

            self.x += move_x
            if self.collides_with_any(obstacles):
                self.x -= move_x

            self.y += move_y
            if self.collides_with_any(obstacles):
                self.y -= move_y

        self.x = max(50, min(self.x, ROOM_WIDTH - 50))
        self.y = max(80, min(self.y, ROOM_HEIGHT - 30))

    def collides_with_any(self, obstacles):
        player_rect = pygame.Rect(
            self.x - self.radius,
            self.y - self.radius,
            self.radius * 2,
            self.radius * 2,
        )
        for obstacle in obstacles:
            if hasattr(obstacle, "collides_with"):
                if obstacle.collides_with(self):
                    return True
            elif player_rect.colliderect(obstacle):
                return True
        return False

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
        self.inventory: list[Item] = []

    @property
    def collected_items(self) -> list[str]:
        return [item.name for item in self.inventory]

    def add_item(self, item: Item) -> bool:
        if item.collected or item in self.inventory or self.current_weight + item.weight > self.capacity:
            return False
        self.inventory.append(item)
        self.current_weight += item.weight
        self.total_value += item.value
        item.collected = True
        return True

    def percent(self) -> float:
        if self.capacity <= 0:
            return 0.0
        return min(self.current_weight / self.capacity, 1.0)

    def draw(self, surface, font):
        pygame.draw.rect(surface, (22, 24, 31), (self.x, self.y, self.width, self.height), border_radius=10)
        pygame.draw.rect(surface, (60, 60, 70), (self.x, self.y, self.width, self.height), 2, border_radius=10)

        bar_x = self.x + 18
        bar_y = self.y + 35
        bar_w = self.width - 36
        bar_h = 18

        pygame.draw.rect(surface, (35, 42, 55), (bar_x, bar_y, bar_w, bar_h), border_radius=12)
        fill = max(0.0, min(self.percent(), 1.0))
        pygame.draw.rect(surface, (80, 220, 120), (bar_x, bar_y, bar_w * fill, bar_h), border_radius=12)

        title = font.render("MOCHILA", True, (255, 255, 255))
        surface.blit(title, (self.x + 18, self.y + 8))

        info = font.render(f"{self.current_weight:.1f}/{self.capacity:.1f} kg", True, (235, 235, 235))
        surface.blit(info, (self.x + 18, self.y + 58))

        value_text = font.render(f"Valor total: {self.total_value} pts", True, (255, 214, 102))
        surface.blit(value_text, (self.x + 18, self.y + 80))

        inventory_title = font.render("ITENS", True, (180, 220, 255))
        surface.blit(inventory_title, (self.x + 18, self.y + 103))
        item_counts = Counter(item.name for item in self.inventory)
        inventory_rows = [f"{name} x{count}" for name, count in item_counts.items()]
        if not inventory_rows:
            inventory_rows = ["(vazio)"]
        for index, row in enumerate(inventory_rows):
            item_text = font.render(row, True, (220, 230, 240))
            surface.blit(item_text, (self.x + 18, self.y + 122 + index * 18))


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
        self.backpack = BackpackUI(620, 450, 290, 190, BACKPACK_CAPACITY)
        self.items = [
            Item(name="Soro Curativo", x=150, y=120, weight=1.5, value=18, total_available=8, color=(80, 200, 130)),
            Item(name="Pólvora", x=265, y=170, weight=2.0, value=32, total_available=6, color=(255, 180, 80)),
            Item(name="Combustível", x=500, y=140, weight=3.2, value=45, total_available=5, color=(190, 120, 240)),
            Item(name="Soro Curativo", x=360, y=260, weight=1.5, value=18, total_available=8, color=(80, 200, 130)),
            Item(name="Pólvora", x=700, y=280, weight=2.0, value=32, total_available=6, color=(255, 180, 80)),
            Item(name="Combustível", x=210, y=330, weight=3.2, value=45, total_available=5, color=(190, 120, 240)),
        ]
        self.doors = [Door(690, 360)]
        self.obstacles = [
            pygame.Rect(140, 80, 90, 180),
            pygame.Rect(340, 90, 120, 160),
            pygame.Rect(560, 95, 120, 170),
        ]
        self.interaction_message = ""

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                self.interact()
        return True

    def nearest_interactable(self):
        nearby_items = [item for item in self.items if item.collides_with(self.player)]
        nearby_doors = [door for door in self.doors if door.is_near(self.player)]
        targets = nearby_items + nearby_doors
        if not targets:
            return None
        return min(
            targets,
            key=lambda target: (target.x - self.player.x) ** 2 + (target.y - self.player.y) ** 2
            if isinstance(target, Item)
            else (target.rect.centerx - self.player.x) ** 2 + (target.rect.centery - self.player.y) ** 2,
        )

    def interact(self):
        target = self.nearest_interactable()
        if target is None:
            self.interaction_message = "Nada para interagir por perto."
            return

        if isinstance(target, Item):
            if self.backpack.add_item(target):
                self.interaction_message = f"{target.name} coletado."
            else:
                self.interaction_message = "Mochila sem capacidade suficiente."
            return

        target.interact(self.player, self.backpack)
        self.interaction_message = "Porta aberta." if target.open else "Porta fechada."

    def update(self, dt):
        keys = pygame.key.get_pressed()
        solid_obstacles = self.obstacles + self.doors
        self.player.update(dt, keys, solid_obstacles)

    def draw_background(self):
        self.screen.fill((15, 17, 22))

        room_rect = pygame.Rect(30, 30, ROOM_WIDTH, ROOM_HEIGHT)
        pygame.draw.rect(self.screen, (40, 45, 55), room_rect, border_radius=16)
        pygame.draw.rect(self.screen, (85, 92, 104), room_rect, 3, border_radius=16)

        for sx in range(60, ROOM_WIDTH, 120):
            pygame.draw.rect(self.screen, (58, 62, 74), (sx, 80, 60, 260), border_radius=12)

        for obstacle in self.obstacles:
            pygame.draw.rect(self.screen, (24, 31, 38), obstacle, border_radius=10)

        label = self.big_font.render("SALA DE LOOT / LABORATÓRIO", True, (255, 255, 255))
        self.screen.blit(label, (55, 18))

    def draw(self):
        self.draw_background()

        for item in self.items:
            item.draw(self.screen, self.font)

        for door in self.doors:
            door.draw(self.screen, self.font)

        self.player.draw(self.screen)
        self.backpack.draw(self.screen, self.font)

        target = self.nearest_interactable()
        if isinstance(target, Item):
            prompt = f"E: coletar {target.name}"
        elif isinstance(target, Door):
            prompt = "E: abrir porta" if not target.open else "E: fechar porta"
        else:
            prompt = "WASD/setas: mover | E: interagir"
        info = self.font.render(prompt, True, (200, 200, 200))
        self.screen.blit(info, (40, 530))
        if self.interaction_message:
            message = self.font.render(self.interaction_message, True, (255, 214, 102))
            self.screen.blit(message, (40, 555))

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