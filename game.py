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

    def update(self, dt):
        keys = pygame.key.get_pressed()
        self.player.update(dt, keys)