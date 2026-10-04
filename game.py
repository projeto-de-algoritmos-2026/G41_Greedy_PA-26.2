import argparse
import math
import os
import random
import struct
from collections import Counter
from dataclasses import dataclass

import pygame


SCREEN_WIDTH = 960
SCREEN_HEIGHT = 640
ROOM_WIDTH = 760
ROOM_HEIGHT = 480
BACKPACK_CAPACITY = 7.0
VICTORY_SCORE = 100
MAX_ENERGY = 100.0
PLAYER_SPEED = 220
SOUND_SAMPLE_RATE = 22050


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

        center = (int(self.x), int(self.y))
        is_valuable = self.value >= 30
        if is_valuable:
            pygame.draw.circle(surface, (255, 205, 90), center, self.radius + 5, 2)
        pygame.draw.circle(surface, self.color, center, self.radius)
        outline_color = (255, 230, 160) if is_valuable else (255, 255, 255)
        pygame.draw.circle(surface, outline_color, center, self.radius, 2)

        label_color = (255, 214, 120) if is_valuable else (230, 230, 230)
        label = font.render(self.name, True, label_color)
        surface.blit(label, (self.x - 26, self.y - 32))

        meta_color = (255, 214, 120) if is_valuable else (220, 220, 220)
        meta = font.render(f"{self.total_available}x / {self.weight}kg / {self.value}p", True, meta_color)
        surface.blit(meta, (self.x - 45, self.y + 18))

    def collides_with(self, player):
        distance_squared = (self.x - player.x) ** 2 + (self.y - player.y) ** 2
        collision_distance = self.radius + player.radius
        return not self.collected and distance_squared <= collision_distance ** 2


@dataclass
class Particle:
    x: float
    y: float
    velocity_x: float
    velocity_y: float
    color: tuple[int, int, int]
    radius: int
    lifetime: float
    label: str = ""

    def update(self, dt):
        self.x += self.velocity_x * dt
        self.y += self.velocity_y * dt
        self.velocity_y += 70 * dt
        self.lifetime -= dt

    def draw(self, surface, font):
        intensity = max(0.0, min(self.lifetime / 0.8, 1.0))
        color = tuple(int(channel * intensity) for channel in self.color)
        if self.label:
            label = font.render(self.label, True, color)
            surface.blit(label, (self.x, self.y))
        elif self.lifetime > 0:
            radius = max(1, int(self.radius * intensity))
            pygame.draw.circle(surface, color, (int(self.x), int(self.y)), radius)


class SoundEffects:
    def __init__(self):
        self.sounds = {}
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=SOUND_SAMPLE_RATE, size=-16, channels=1, buffer=512)
            self.sounds = {
                "collect": self._create_sound(((620, 0.07), (880, 0.12)), 0.18),
                "move": self._create_footstep(),
                "victory": self._create_sound(((523, 0.12), (659, 0.12), (784, 0.12), (1046, 0.28)), 0.2),
                "defeat": self._create_sound(((420, 0.14), (320, 0.16), (220, 0.3)), 0.18),
            }
        except pygame.error:
            self.sounds = {}

    @staticmethod
    def _create_sound(notes, volume):
        samples = bytearray()
        for frequency, duration in notes:
            sample_count = int(SOUND_SAMPLE_RATE * duration)
            attack_samples = max(1, int(SOUND_SAMPLE_RATE * 0.01))
            release_samples = max(1, int(SOUND_SAMPLE_RATE * 0.04))
            for index in range(sample_count):
                envelope = min(1.0, index / attack_samples, (sample_count - index) / release_samples)
                value = int(32767 * volume * envelope * math.sin(2 * math.pi * frequency * index / SOUND_SAMPLE_RATE))
                samples.extend(struct.pack("<h", value))
        return pygame.mixer.Sound(buffer=bytes(samples))

    @staticmethod
    def _create_footstep():
        sample_count = int(SOUND_SAMPLE_RATE * 0.12)
        samples = bytearray()
        for index in range(sample_count):
            progress = index / sample_count
            envelope = (1.0 - progress) ** 2.5
            time = index / SOUND_SAMPLE_RATE
            low_thump = math.sin(2 * math.pi * 125 * time) * 0.55
            shoe_tap = math.sin(2 * math.pi * 245 * time) * 0.2
            surface_noise = random.uniform(-1.0, 1.0) * 0.2
            value = int(32767 * 0.5 * envelope * (low_thump + shoe_tap + surface_noise))
            samples.extend(struct.pack("<h", value))
        return pygame.mixer.Sound(buffer=bytes(samples))

    def play(self, name):
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()


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
        self.energy = MAX_ENERGY
        self.max_energy = MAX_ENERGY

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

        is_moving = dx != 0 or dy != 0
        if is_moving:
            self.energy = max(0.0, self.energy - 8 * dt)
            length = (dx * dx + dy * dy) ** 0.5
            movement_speed = self.speed if self.energy > 0 else self.speed * 0.6
            move_x = (dx / length) * movement_speed * dt
            move_y = (dy / length) * movement_speed * dt

            self.x += move_x
            if self.collides_with_any(obstacles):
                self.x -= move_x

            self.y += move_y
            if self.collides_with_any(obstacles):
                self.y -= move_y
        else:
            self.energy = min(self.max_energy, self.energy + 18 * dt)

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

    def draw(
        self,
        surface,
        font,
        goal_value: int = VICTORY_SCORE,
        energy: float = MAX_ENERGY,
        max_energy: float = MAX_ENERGY,
    ):
        pygame.draw.rect(surface, (22, 24, 31), (self.x, self.y, self.width, self.height), border_radius=10)
        pygame.draw.rect(surface, (60, 60, 70), (self.x, self.y, self.width, self.height), 2, border_radius=10)

        bar_x = self.x + 18
        bar_w = self.width - 36
        bar_h = 12

        title = font.render("MOCHILA", True, (255, 255, 255))
        surface.blit(title, (self.x + 18, self.y + 8))

        energy_percent = min(energy / max_energy, 1.0) if max_energy > 0 else 0.0
        if energy_percent > 0.5:
            energy_color = (80, 220, 120)
        elif energy_percent > 0.2:
            energy_color = (255, 190, 75)
        else:
            energy_color = (240, 90, 85)
        energy_text = font.render(f"Energia: {energy:.0f}/{max_energy:.0f}", True, (235, 235, 235))
        surface.blit(energy_text, (self.x + 18, self.y + 28))
        pygame.draw.rect(surface, (35, 42, 55), (bar_x, self.y + 45, bar_w, bar_h), border_radius=8)
        pygame.draw.rect(
            surface,
            energy_color,
            (bar_x, self.y + 45, bar_w * energy_percent, bar_h),
            border_radius=8,
        )

        weight_text = font.render(f"Peso: {self.current_weight:.1f}/{self.capacity:.1f} kg", True, (235, 235, 235))
        surface.blit(weight_text, (self.x + 18, self.y + 62))
        weight_bar_y = self.y + 79
        pygame.draw.rect(surface, (35, 42, 55), (bar_x, weight_bar_y, bar_w, bar_h), border_radius=8)
        weight_color = (240, 90, 85) if self.percent() >= 0.9 else (80, 220, 120)
        pygame.draw.rect(
            surface,
            weight_color,
            (bar_x, weight_bar_y, bar_w * self.percent(), bar_h),
            border_radius=8,
        )

        score_bar_y = self.y + 96
        score_percent = min(self.total_value / goal_value, 1.0) if goal_value > 0 else 0.0
        pygame.draw.rect(surface, (35, 42, 55), (bar_x, score_bar_y, bar_w, bar_h), border_radius=6)
        pygame.draw.rect(
            surface,
            (255, 190, 75),
            (bar_x, score_bar_y, bar_w * score_percent, bar_h),
            border_radius=6,
        )
        score_text = font.render(f"Pontos: {self.total_value}/{goal_value} pts", True, (255, 214, 102))
        surface.blit(score_text, (self.x + 18, self.y + 113))

        inventory_title = font.render("ITENS", True, (180, 220, 255))
        surface.blit(inventory_title, (self.x + 18, self.y + 136))
        item_counts = Counter(item.name for item in self.inventory)
        inventory_rows = [f"{name} x{count}" for name, count in item_counts.items()]
        if not inventory_rows:
            inventory_rows = ["(vazio)"]
        for index, row in enumerate(inventory_rows):
            item_text = font.render(row, True, (220, 230, 240))
            surface.blit(item_text, (self.x + 18, self.y + 153 + index * 15))


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
        self.audio = SoundEffects()

        self.player = Player(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        self.backpack = BackpackUI(620, 420, 290, 220, BACKPACK_CAPACITY)
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
        self.game_state = "playing"
        self.interaction_message = ""
        self.message_timer = 0.0
        self.low_energy_warning = False
        self.movement_sound_timer = 0.0
        self.particles: list[Particle] = []

    def show_message(self, message: str, duration: float = 2.5):
        self.interaction_message = message
        self.message_timer = duration

    def spawn_burst(self, x, y, color, count, label=""):
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(35, 130)
            self.particles.append(
                Particle(
                    x,
                    y,
                    math.cos(angle) * speed,
                    math.sin(angle) * speed,
                    color,
                    random.randint(2, 5),
                    random.uniform(0.35, 0.8),
                )
            )
        if label:
            self.particles.append(Particle(x, y - 8, 0, -34, (255, 235, 170), 0, 0.8, label))

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if self.game_state == "playing" and event.type == pygame.KEYDOWN and event.key == pygame.K_e:
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
        if self.game_state != "playing":
            return

        target = self.nearest_interactable()
        if target is None:
            self.show_message("Nada para interagir por perto.")
            return

        if isinstance(target, Item):
            if self.backpack.add_item(target):
                self.audio.play("collect")
                self.spawn_burst(target.x, target.y, target.color, 14, f"+{target.value} pts")
                self.update_game_state()
                if self.game_state == "playing":
                    self.show_message(f"{target.name} coletado.")
            else:
                self.show_message("Mochila sem capacidade suficiente.")
            return

        target.interact(self.player, self.backpack)
        self.show_message("Porta aberta." if target.open else "Porta fechada.")

    def best_possible_score(self):
        remaining_capacity = self.backpack.capacity - self.backpack.current_weight
        possible_scores = {0.0: 0}

        for item in self.items:
            if item.collected:
                continue
            updated_scores = possible_scores.copy()
            for weight, score in possible_scores.items():
                combined_weight = round(weight + item.weight, 4)
                if combined_weight <= remaining_capacity:
                    updated_scores[combined_weight] = max(
                        updated_scores.get(combined_weight, 0),
                        score + item.value,
                    )
            possible_scores = updated_scores

        return self.backpack.total_value + max(possible_scores.values(), default=0)

    def update_game_state(self):
        if self.backpack.total_value >= VICTORY_SCORE:
            self.game_state = "won"
            self.show_message("Meta alcançada! Você venceu.")
            self.audio.play("victory")
            self.spawn_burst(SCREEN_WIDTH / 2, 190, (100, 235, 155), 42)
        elif self.best_possible_score() < VICTORY_SCORE:
            self.game_state = "lost"
            self.show_message("Não há combinações suficientes. Você perdeu.")
            self.audio.play("defeat")
            self.spawn_burst(SCREEN_WIDTH / 2, 190, (235, 90, 85), 30)

    def update(self, dt):
        self.message_timer = max(0.0, self.message_timer - dt)
        for particle in self.particles:
            particle.update(dt)
        self.particles = [particle for particle in self.particles if particle.lifetime > 0]
        if self.game_state != "playing":
            return
        keys = pygame.key.get_pressed()
        solid_obstacles = self.obstacles + self.doors
        previous_position = (self.player.x, self.player.y)
        self.player.update(dt, keys, solid_obstacles)
        has_moved = previous_position != (self.player.x, self.player.y)
        if has_moved:
            self.movement_sound_timer -= dt
            if self.movement_sound_timer <= 0:
                self.audio.play("move")
                self.movement_sound_timer = 0.32
                self.spawn_burst(self.player.x, self.player.y + self.player.radius - 3, (150, 175, 195), 2)
        else:
            self.movement_sound_timer = 0.0
        if self.player.energy <= 20 and not self.low_energy_warning:
            self.show_message("Energia baixa.")
            self.low_energy_warning = True
        elif self.player.energy >= 40:
            self.low_energy_warning = False

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
        for particle in self.particles:
            particle.draw(self.screen, self.font)
        self.backpack.draw(
            self.screen,
            self.font,
            VICTORY_SCORE,
            self.player.energy,
            self.player.max_energy,
        )

        target = self.nearest_interactable()
        if isinstance(target, Item):
            prompt = f"E: coletar {target.name} (+{target.value} pts)"
        elif isinstance(target, Door):
            prompt = "E: abrir porta" if not target.open else "E: fechar porta"
        else:
            prompt = "WASD/setas: mover | E: interagir"
        info = self.font.render(prompt, True, (200, 200, 200))
        self.screen.blit(info, (40, 530))
        if self.message_timer > 0 and self.interaction_message:
            message = self.font.render(self.interaction_message, True, (255, 214, 102))
            self.screen.blit(message, (40, 555))

        if self.game_state != "playing":
            color = (80, 220, 140) if self.game_state == "won" else (245, 110, 100)
            title_text = "VITÓRIA" if self.game_state == "won" else "DERROTA"
            title = self.big_font.render(title_text, True, color)
            score = self.font.render(
                f"Pontuação final: {self.backpack.total_value}/{VICTORY_SCORE} pts",
                True,
                (245, 245, 245),
            )
            panel = pygame.Rect(SCREEN_WIDTH // 2 - 190, SCREEN_HEIGHT // 2 - 65, 380, 130)
            pygame.draw.rect(self.screen, (22, 24, 31), panel, border_radius=10)
            pygame.draw.rect(self.screen, color, panel, 2, border_radius=10)
            self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20)))
            self.screen.blit(score, score.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 22)))

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