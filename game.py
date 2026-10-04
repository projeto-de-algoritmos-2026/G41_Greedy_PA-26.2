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
ROOM_X = 30
ROOM_Y = 30
ROOM_WALL_THICKNESS = 3
BACKPACK_CAPACITY = 7.0
VICTORY_SCORE = 90
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
    available_fraction: float = 1.0

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
        ratio = self.value / self.weight if self.weight > 0 else 0
        meta = font.render(f"{self.weight}kg / {self.value}p / {ratio:.1f}p/kg", True, meta_color)
        surface.blit(meta, (self.x - 45, self.y + 18))

    def collides_with(self, player):
        distance_squared = (self.x - player.x) ** 2 + (self.y - player.y) ** 2
        collision_distance = self.radius + player.radius
        return self.available_fraction > 0 and distance_squared <= collision_distance ** 2


@dataclass(frozen=True)
class LootSelection:
    item: Item
    fraction: float


def fractional_knapsack(items: list[Item], capacity: float) -> list[LootSelection]:
    remaining_capacity = max(0.0, capacity)
    selections = []
    ranked_items = sorted(
        (item for item in items if item.available_fraction > 0 and item.weight > 0 and item.value > 0),
        key=lambda item: item.value / item.weight,
        reverse=True,
    )

    for item in ranked_items:
        if remaining_capacity <= 1e-9:
            break
        available_weight = item.weight * item.available_fraction
        selected_weight = min(available_weight, remaining_capacity)
        fraction = selected_weight / item.weight
        selections.append(LootSelection(item, fraction))
        remaining_capacity -= selected_weight

    return selections


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
            step_count = max(1, math.ceil(max(abs(move_x), abs(move_y)) / (self.radius / 2)))
            step_x = move_x / step_count
            step_y = move_y / step_count

            for _ in range(step_count):
                self.x += step_x
                if self.collides_with_any(obstacles):
                    self.x -= step_x

                self.y += step_y
                if self.collides_with_any(obstacles):
                    self.y -= step_y
        else:
            self.energy = min(self.max_energy, self.energy + 18 * dt)

        self.x = max(
            ROOM_X + ROOM_WALL_THICKNESS + self.radius,
            min(self.x, ROOM_X + ROOM_WIDTH - ROOM_WALL_THICKNESS - self.radius),
        )
        self.y = max(
            ROOM_Y + ROOM_WALL_THICKNESS + self.radius,
            min(self.y, ROOM_Y + ROOM_HEIGHT - ROOM_WALL_THICKNESS - self.radius),
        )

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
        self.total_value = 0.0
        self.inventory: list[LootSelection] = []

    @property
    def collected_items(self) -> list[str]:
        return [selection.item.name for selection in self.inventory]

    def add_item(self, item: Item) -> bool:
        return self.add_fraction(item, 1.0)

    def add_fraction(self, item: Item, fraction: float) -> bool:
        fraction = min(max(fraction, 0.0), item.available_fraction)
        selected_weight = item.weight * fraction
        if item.collected or fraction <= 0 or self.current_weight + selected_weight > self.capacity + 1e-9:
            return False
        self.inventory.append(LootSelection(item, fraction))
        self.current_weight += selected_weight
        self.total_value += item.value * fraction
        item.available_fraction = max(0.0, item.available_fraction - fraction)
        item.collected = item.available_fraction <= 1e-9
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
        score_text = font.render(f"Valor total: {self.total_value:g}/{goal_value} pts", True, (255, 214, 102))
        surface.blit(score_text, (self.x + 18, self.y + 113))

        inventory_title = font.render("ITENS", True, (180, 220, 255))
        surface.blit(inventory_title, (self.x + 18, self.y + 136))
        item_amounts = Counter()
        for selection in self.inventory:
            item_amounts[selection.item.name] += selection.fraction
        inventory_rows = [f"{name} x{amount:g}" for name, amount in item_amounts.items()]
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
        self.fullscreen = not self.headless
        if self.fullscreen:
            self.display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            self.screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        else:
            self.display = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
            self.screen = self.display
        pygame.display.set_caption("Laboratório de Loot")

        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 22)
        self.big_font = pygame.font.SysFont(None, 32)
        self.label_font = pygame.font.SysFont(None, 24)
        self.audio = SoundEffects()

        self.obstacles = [
            pygame.Rect(140, 80, 90, 180),
            pygame.Rect(340, 90, 120, 160),
            pygame.Rect(560, 95, 120, 170),
        ]
        self.reset_session()

    def reset_session(self):
        self.player = Player(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        self.backpack = BackpackUI(620, 420, 290, 220, BACKPACK_CAPACITY)
        item_types = [
            ("Soro Curativo", 1.5, 24, 8, (80, 200, 130)),
            ("Pólvora", 2.0, 34, 6, (255, 180, 80)),
            ("Combustível", 3.2, 45, 5, (190, 120, 240)),
            ("Soro Curativo", 1.5, 24, 8, (80, 200, 130)),
            ("Pólvora", 2.0, 34, 6, (255, 180, 80)),
            ("Combustível", 3.2, 45, 5, (190, 120, 240)),
        ]
        self.items = []
        for name, weight, value, total_available, color in item_types:
            x, y = self._random_item_position(name, weight, value, total_available)
            self.items.append(Item(name, x, y, weight, value, total_available, color))

        self.game_state = "playing"
        self.interaction_message = ""
        self.message_timer = 0.0
        self.low_energy_warning = False
        self.movement_sound_timer = 0.0
        self.particles: list[Particle] = []

    def _item_visual_bounds(self, name, x, y, weight, value, total_available):
        item_bounds = pygame.Rect(x - Item.radius, y - Item.radius, Item.radius * 2, Item.radius * 2)
        label_bounds = self.font.render(name, True, (255, 255, 255)).get_rect(topleft=(round(x - 26), round(y - 32)))
        meta_text = f"{total_available}x / {weight}kg / {value}p"
        meta_bounds = self.font.render(meta_text, True, (255, 255, 255)).get_rect(topleft=(round(x - 45), round(y + 18)))
        return item_bounds.union(label_bounds).union(meta_bounds)

    def _random_item_position(self, name, weight, value, total_available):
        clearance = Item.radius + self.player.radius + 6
        room_area = pygame.Rect(
            ROOM_X + ROOM_WALL_THICKNESS,
            ROOM_Y + ROOM_WALL_THICKNESS,
            ROOM_WIDTH - ROOM_WALL_THICKNESS * 2,
            ROOM_HEIGHT - ROOM_WALL_THICKNESS * 2,
        )
        backpack_area = pygame.Rect(self.backpack.x, self.backpack.y, self.backpack.width, self.backpack.height).inflate(12, 12)

        for _ in range(2000):
            x = random.uniform(room_area.left + Item.radius, room_area.right - Item.radius)
            y = random.uniform(room_area.top + Item.radius, room_area.bottom - Item.radius)
            if math.hypot(x - self.player.x, y - self.player.y) < 85:
                continue
            visual_bounds = self._item_visual_bounds(name, x, y, weight, value, total_available)
            if not room_area.contains(visual_bounds) or visual_bounds.colliderect(backpack_area):
                continue
            approach_bounds = pygame.Rect(x - clearance, y - clearance, clearance * 2, clearance * 2)
            if any(visual_bounds.colliderect(obstacle) or approach_bounds.colliderect(obstacle) for obstacle in self.obstacles):
                continue
            if any(
                visual_bounds.colliderect(
                    self._item_visual_bounds(
                        item.name,
                        item.x,
                        item.y,
                        item.weight,
                        item.value,
                        item.total_available,
                    ).inflate(8, 8)
                )
                for item in self.items
            ):
                continue
            if any(math.hypot(x - item.x, y - item.y) < 85 for item in self.items):
                continue
            return x, y

        raise RuntimeError("Não foi possível encontrar espaço para posicionar os itens.")

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
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_r:
                    self.reset_session()
                elif self.game_state == "playing" and event.key == pygame.K_e:
                    self.interact()
                elif self.game_state == "playing" and event.key == pygame.K_f:
                    self.optimize_loot()
        return True

    def nearest_interactable(self):
        nearby_items = [item for item in self.items if item.collides_with(self.player)]
        if not nearby_items:
            return None
        return min(nearby_items, key=lambda item: (item.x - self.player.x) ** 2 + (item.y - self.player.y) ** 2)

    def interact(self):
        if self.game_state != "playing":
            return

        target = self.nearest_interactable()
        if target is None:
            self.show_message("Nada para interagir por perto.")
            return

        remaining_capacity = self.backpack.capacity - self.backpack.current_weight
        fraction = min(target.available_fraction, remaining_capacity / target.weight)
        if fraction <= 1e-9:
            self.show_message("A mochila está cheia.")
            return

        if not self.backpack.add_fraction(target, fraction):
            self.show_message("Não foi possível coletar este item.")
            return

        self.audio.play("collect")
        selected_value = target.value * fraction
        self.spawn_burst(target.x, target.y, target.color, 14, f"+{selected_value:g} pts")
        self.update_game_state()
        if self.game_state == "playing":
            self.show_message(f"{target.name} x{fraction:g} coletado.")

    def optimize_loot(self):
        if self.game_state != "playing":
            return
        if self.nearest_interactable() is None:
            self.show_message("Aproxime-se de um item para otimizar o saque.")
            return

        selected_loot = fractional_knapsack(
            self.items,
            self.backpack.capacity - self.backpack.current_weight,
        )
        if not selected_loot:
            self.show_message("A mochila já está cheia.")
            return

        for selection in selected_loot:
            if self.backpack.add_fraction(selection.item, selection.fraction):
                item = selection.item
                self.audio.play("collect")
                selected_value = item.value * selection.fraction
                self.spawn_burst(item.x, item.y, item.color, 14, f"+{selected_value:g} pts")

        self.update_game_state()
        if self.game_state == "playing":
            self.show_message(
                f"Saque otimizado: {self.backpack.current_weight:.1f} kg / "
                f"{self.backpack.total_value:g} pts."
            )

    def best_possible_score(self):
        remaining_capacity = self.backpack.capacity - self.backpack.current_weight
        remaining_selections = fractional_knapsack(self.items, remaining_capacity)
        remaining_value = sum(selection.item.value * selection.fraction for selection in remaining_selections)
        return self.backpack.total_value + remaining_value

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
        solid_obstacles = self.obstacles
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

        room_rect = pygame.Rect(ROOM_X, ROOM_Y, ROOM_WIDTH, ROOM_HEIGHT)
        floor_rect = room_rect.inflate(-12, -12)
        pygame.draw.rect(self.screen, (34, 45, 49), room_rect, border_radius=16)
        pygame.draw.rect(self.screen, (39, 52, 55), floor_rect, border_radius=10)

        for grid_x in range(floor_rect.left + 40, floor_rect.right, 48):
            pygame.draw.line(self.screen, (46, 60, 62), (grid_x, floor_rect.top), (grid_x, floor_rect.bottom), 1)
        for grid_y in range(floor_rect.top + 40, floor_rect.bottom, 48):
            pygame.draw.line(self.screen, (46, 60, 62), (floor_rect.left, grid_y), (floor_rect.right, grid_y), 1)

        for table in self.obstacles:
            pygame.draw.rect(self.screen, (24, 34, 36), table, border_radius=8)
            tabletop = table.inflate(-6, -6)
            pygame.draw.rect(self.screen, (69, 91, 85), tabletop, border_radius=6)
            pygame.draw.rect(
                self.screen,
                (115, 145, 129),
                tabletop,
                1,
                border_radius=6,
            )
            drawer_y = table.y + table.height // 2
            pygame.draw.line(
                self.screen,
                (43, 62, 61),
                (table.x + 7, drawer_y),
                (table.right - 7, drawer_y),
                2,
            )

            vial = pygame.Rect(table.x + 12, table.y + 22, 17, 28)
            pygame.draw.rect(self.screen, (166, 205, 174), (vial.x + 5, vial.y - 7, 7, 9), border_radius=2)
            pygame.draw.rect(self.screen, (105, 173, 146), vial, border_radius=4)
            pygame.draw.rect(self.screen, (195, 229, 196), vial, 2, border_radius=4)
            pygame.draw.rect(self.screen, (208, 177, 83), (vial.x + 3, vial.bottom - 8, vial.width - 6, 5))

            flask_center_x = table.right - 23
            flask_neck = pygame.Rect(flask_center_x - 4, table.y + 25, 8, 17)
            flask_bowl = [
                (flask_center_x - 4, table.y + 38),
                (flask_center_x + 4, table.y + 38),
                (flask_center_x + 13, table.y + 59),
                (flask_center_x + 11, table.y + 73),
                (flask_center_x - 11, table.y + 73),
                (flask_center_x - 13, table.y + 59),
            ]
            pygame.draw.rect(self.screen, (166, 205, 174), flask_neck, border_radius=2)
            pygame.draw.polygon(self.screen, (82, 151, 135), flask_bowl)
            pygame.draw.polygon(self.screen, (195, 229, 196), flask_bowl, 2)
            pygame.draw.line(
                self.screen,
                (226, 204, 119),
                (flask_center_x - 8, table.y + 61),
                (flask_center_x + 8, table.y + 61),
                2,
            )

            microscope_x = table.centerx
            microscope_y = table.bottom - 27
            pygame.draw.rect(self.screen, (38, 51, 55), (microscope_x - 19, microscope_y + 11, 38, 5), border_radius=2)
            pygame.draw.line(
                self.screen,
                (183, 197, 178),
                (microscope_x - 8, microscope_y + 12),
                (microscope_x - 5, microscope_y - 10),
                4,
            )
            pygame.draw.line(
                self.screen,
                (183, 197, 178),
                (microscope_x - 5, microscope_y - 10),
                (microscope_x + 9, microscope_y - 17),
                4,
            )
            pygame.draw.circle(self.screen, (199, 215, 190), (microscope_x + 11, microscope_y - 18), 4)
            pygame.draw.line(
                self.screen,
                (183, 197, 178),
                (microscope_x - 14, microscope_y + 4),
                (microscope_x + 8, microscope_y + 4),
                3,
            )

        pygame.draw.line(self.screen, (88, 133, 127), (48, 48), (760, 48), 3)
        pygame.draw.rect(self.screen, (68, 82, 84), room_rect, 3, border_radius=16)

        label = self.label_font.render("LABORATÓRIO / SETOR DE PESQUISA", True, (236, 245, 237))
        label_x = SCREEN_WIDTH - label.get_width() - 24
        self.screen.blit(label, (label_x, 4))

    def draw(self):
        self.draw_background()

        for item in self.items:
            item.draw(self.screen, self.font)

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
            prompt = "E: coletar item | F: otimizar saque"
        else:
            prompt = "WASD/setas: mover | E: coletar | F: otimizar saque"
        info = self.font.render(prompt, True, (200, 200, 200))
        self.screen.blit(info, (40, 530))
        controls = self.font.render("R: reiniciar  |  Esc: sair", True, (155, 177, 177))
        self.screen.blit(controls, (40, 602))
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

        if self.fullscreen:
            display_width, display_height = self.display.get_size()
            scale = min(display_width / SCREEN_WIDTH, display_height / SCREEN_HEIGHT)
            scaled_size = (int(SCREEN_WIDTH * scale), int(SCREEN_HEIGHT * scale))
            scaled_screen = pygame.transform.smoothscale(self.screen, scaled_size)
            self.display.fill((12, 17, 20))
            destination = (
                (display_width - scaled_size[0]) // 2,
                (display_height - scaled_size[1]) // 2,
            )
            self.display.blit(scaled_screen, destination)
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