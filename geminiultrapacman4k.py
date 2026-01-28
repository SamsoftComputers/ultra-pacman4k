import pygame
import sys
import math
import random
import array

# ---------------------------------------------------------------------------
# CONSTANTS & CONFIGURATION
# ---------------------------------------------------------------------------
FPS = 60
TILE_SIZE = 8
SCALE = 3  # Scale factor for modern screens (24px tiles)
SCREEN_WIDTH = 28 * TILE_SIZE * SCALE
SCREEN_HEIGHT = 31 * TILE_SIZE * SCALE + (20 * SCALE) # Extra height for UI

# Colors (R, G, B)
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_WALL = (33, 33, 255)  # NES Blue
COLOR_PELLET = (255, 184, 151)
COLOR_PACMAN = (255, 255, 0)
COLOR_BLINKY = (255, 0, 0)
COLOR_PINKY = (255, 184, 255)
COLOR_INKY = (0, 255, 255)
COLOR_CLYDE = (255, 184, 82)
COLOR_FRIGHTENED = (33, 33, 255) # Blue/White flashing
COLOR_RED = (255, 0, 0)
COLOR_YELLOW = (255, 255, 0)

# Audio Config
SAMPLE_RATE = 44100
BIT_DEPTH = 16

# ---------------------------------------------------------------------------
# MAZE LAYOUT (Standard Arcade/NES 28x31)
# ---------------------------------------------------------------------------
MAZE_LAYOUT = [
    "############################",
    "#............##............#",
    "#.####.#####.##.#####.####.#",
    "#o####.#####.##.#####.####o#",
    "#.####.#####.##.#####.####.#",
    "#..........................#",
    "#.####.##.########.##.####.#",
    "#.####.##.########.##.####.#",
    "#......##....##....##......#",
    "######.#####-##-#####.######",
    "     #.#####-##-#####.#     ",
    "     #.##----------##.#     ",
    "######.##-###--###-##.######",
    "------.--|#      #|--.------",
    "######.##-########-##.######",
    "     #.##----------##.#     ",
    "     #.##-########-##.#     ",
    "######.##-########-##.######",
    "#............##............#",
    "#.####.#####.##.#####.####.#",
    "#o..##.......  .......##..o#",
    "###.##.##.########.##.##.###",
    "###.##.##.########.##.##.###",
    "#......##....##....##......#",
    "#.##########.##.##########.#",
    "#.##########.##.##########.#",
    "#..........................#",
    "############################",
    "                            ",
    "                            ",
    "                            "
]
MAZE_LAYOUT = MAZE_LAYOUT[:31]

# ---------------------------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------------------------

class Vec2:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __add__(self, other):
        return Vec2(self.x + other.x, self.y + other.y)
    
    def __sub__(self, other):
        return Vec2(self.x - other.x, self.y - other.y)
        
    def __mul__(self, scalar):
        return Vec2(self.x * scalar, self.y * scalar)
    
    def __eq__(self, other):
        return abs(self.x - other.x) < 0.001 and abs(self.y - other.y) < 0.001
    
    def __hash__(self):
        return hash((round(self.x, 3), round(self.y, 3)))
    
    def dist_sq(self, other):
        return (self.x - other.x)**2 + (self.y - other.y)**2
        
    def as_int(self):
        return (int(self.x), int(self.y))
        
    def __repr__(self):
        return f"({self.x:.2f}, {self.y:.2f})"

DIRS = {
    "NONE": Vec2(0, 0),
    "UP": Vec2(0, -1),
    "DOWN": Vec2(0, 1),
    "LEFT": Vec2(-1, 0),
    "RIGHT": Vec2(1, 0)
}

class SoundSynthesizer:
    @staticmethod
    def generate_square_wave(freq, duration, volume, decay=0.0):
        """Generate a retro square wave sound buffer."""
        n_samples = int(SAMPLE_RATE * duration)
        buf = array.array('h', [0] * n_samples)
        
        period = int(SAMPLE_RATE / freq) if freq > 0 else 1
        amplitude = int(32767 * volume)
        
        for i in range(n_samples):
            # Apply decay
            current_amp = amplitude
            if decay > 0:
                current_amp = int(amplitude * (1.0 - (i / n_samples) * decay))
            
            # Square wave logic
            if period > 0 and (i // (period // 2)) % 2 == 0:
                buf[i] = current_amp
            else:
                buf[i] = -current_amp
                
        return pygame.mixer.Sound(buffer=buf)

    @staticmethod
    def generate_siren(start_freq, end_freq, duration, volume):
        """Generate a rising/falling siren sound."""
        n_samples = int(SAMPLE_RATE * duration)
        buf = array.array('h', [0] * n_samples)
        amplitude = int(32767 * volume)
        
        for i in range(n_samples):
            t = i / n_samples
            # Wobbly siren frequency
            freq = start_freq + (end_freq - start_freq) * math.sin(t * math.pi * 10) 
            period = int(SAMPLE_RATE / freq) if freq > 0 else 1
            
            if period > 0 and (i // (period // 2)) % 2 == 0:
                buf[i] = amplitude
            else:
                buf[i] = -amplitude
        return pygame.mixer.Sound(buffer=buf)

# ---------------------------------------------------------------------------
# ACTORS
# ---------------------------------------------------------------------------

class Actor:
    def __init__(self, x, y, speed_base):
        self.pos = Vec2(x + 0.5, y + 0.5)
        self.dir = DIRS["NONE"]
        self.next_dir = DIRS["NONE"]
        self.speed_base = speed_base
        self.radius = 0.4
        self.angle = 180  # Degrees
        
    def can_move(self, walls, direction):
        target = self.pos + direction * 0.5 # Look ahead half a tile
        tx, ty = int(target.x), int(target.y)
        
        # Tunnel check
        if tx < 0 or tx >= 28:
            return True
            
        # Specific gate logic: Only ghosts in "dead" or "exit" mode can cross (13,12) and (14,12)
        if (tx, ty) == (13, 12) or (tx, ty) == (14, 12):
            return False 
            
        return (tx, ty) not in walls

    def align_to_grid(self):
        """Snap to center of tile axis opposite to movement"""
        if self.dir.x != 0:
            self.pos.y = math.floor(self.pos.y) + 0.5
        elif self.dir.y != 0:
            self.pos.x = math.floor(self.pos.x) + 0.5

class Pacman(Actor):
    def __init__(self):
        # 0.14 tiles/frame @ 60FPS ~ 8.4 tiles/sec (Famicom feel)
        super().__init__(13, 23, speed_base=0.14) 
        self.mouth_angle = 0
        self.mouth_speed = 4
        self.mouth_closing = False
        self.dir = DIRS["LEFT"]
        self.next_dir = DIRS["LEFT"]
        self.freeze_timer = 0 # For eating pause
        
    def update(self, walls, speed_mod):
        # Handle eating pause (Arcade pauses 1 frame for pellet, 3 for power)
        if self.freeze_timer > 0:
            self.freeze_timer -= 1
            return

        # Change direction if next dir is valid
        if self.next_dir.x != 0 or self.next_dir.y != 0:
            if self.can_move(walls, self.next_dir):
                # Only turn if close to center to prevent corner cutting glitches
                dist_to_center = 0
                if self.next_dir.x != 0:
                    dist_to_center = abs(self.pos.y - (int(self.pos.y) + 0.5))
                else:
                    dist_to_center = abs(self.pos.x - (int(self.pos.x) + 0.5))
                
                # Famicom has slightly more forgiving cornering than Arcade
                if dist_to_center < 0.20: 
                    self.dir = self.next_dir
                    self.align_to_grid()
            else:
                # Keep trying current dir
                if not self.can_move(walls, self.dir):
                    self.dir = DIRS["NONE"]
        
        # Move if direction is valid
        if self.can_move(walls, self.dir):
            self.pos += self.dir * (self.speed_base * speed_mod)
            self.mouth_speed = 4 # Animate when moving
        else:
            self.mouth_speed = 0 # Stop animation when stuck
            self.mouth_angle = 45 # Open mouth when stuck
            
        # Tunnel wrap-around
        if self.pos.x < -0.5:
            self.pos.x = 27.5
        elif self.pos.x >= 28.5:
            self.pos.x = 0.5
            
        # Update mouth animation
        if self.mouth_speed > 0:
            if self.mouth_closing:
                self.mouth_angle -= self.mouth_speed
                if self.mouth_angle <= 0:
                    self.mouth_closing = False
                    self.mouth_angle = 0
            else:
                self.mouth_angle += self.mouth_speed
                if self.mouth_angle >= 45:
                    self.mouth_closing = True
                    self.mouth_angle = 45
                
        # Update facing angle
        if self.dir == DIRS["RIGHT"]:
            self.angle = 0
        elif self.dir == DIRS["DOWN"]:
            self.angle = 270 
        elif self.dir == DIRS["LEFT"]:
            self.angle = 180
        elif self.dir == DIRS["UP"]:
            self.angle = 90

class Ghost(Actor):
    def __init__(self, x, y, color, behavior_mode="SCATTER"):
        super().__init__(x, y, speed_base=0.14)
        self.base_color = color # FIXED: Persist identity
        self.color = color
        self.home_tile = Vec2(x, y)
        self.target_tile = Vec2(0, 0)
        self.behavior_mode = behavior_mode
        self.mode_timer = 0
        self.frightened_timer = 0
        self.release_timer = 0
        self.is_in_house = True
        self.is_eaten = False
        self.eye_dir = DIRS["LEFT"]
        
    def set_target(self, pacman_pos, blinky_pos=None, pacman_dir=None):
        if self.is_eaten:
            self.target_tile = Vec2(13, 11) # Ghost House center
            return
            
        if self.behavior_mode == "FRIGHTENED":
            # Pseudo-random target for frightened
            self.target_tile = Vec2(random.randint(0, 27), random.randint(0, 30))
            return
            
        if self.behavior_mode == "SCATTER":
            # Arcade-Accurate Scatter Targets
            if self.base_color == COLOR_BLINKY: self.target_tile = Vec2(25, -3) # Top Right
            elif self.base_color == COLOR_PINKY: self.target_tile = Vec2(2, -3) # Top Left
            elif self.base_color == COLOR_INKY: self.target_tile = Vec2(27, 31) # Bottom Right
            elif self.base_color == COLOR_CLYDE: self.target_tile = Vec2(0, 31) # Bottom Left
            return

        tx, ty = int(pacman_pos.x), int(pacman_pos.y)
        
        # CHASE TARGETING LOGIC
        if self.base_color == COLOR_BLINKY:
            self.target_tile = Vec2(tx, ty)
            
        elif self.base_color == COLOR_PINKY:
            # 1:1 ARCADE BUG: If Pac-Man is facing UP, Pinky also targets 4 tiles LEFT (Overflow)
            offset_vec = pacman_dir if pacman_dir else DIRS["LEFT"]
            target = Vec2(tx, ty) + (offset_vec * 4)
            if pacman_dir == DIRS["UP"]:
                target.x -= 4 # Arcade overflow bug
            self.target_tile = target
                
        elif self.base_color == COLOR_INKY:
            if blinky_pos and pacman_dir:
                # 1:1 ARCADE BUG: Same UP/LEFT overflow applies to the intermediate point for Inky
                offset_vec = pacman_dir * 2
                pivot = Vec2(tx, ty) + offset_vec
                if pacman_dir == DIRS["UP"]:
                    pivot.x -= 2 # Arcade overflow bug
                
                vec = pivot - blinky_pos
                self.target_tile = pivot + vec
            else:
                self.target_tile = Vec2(tx, ty)
                
        elif self.base_color == COLOR_CLYDE:
            dist = self.pos.dist_sq(pacman_pos)
            if dist < 64: # 8 tiles squared
                self.target_tile = Vec2(0, 31) # Scatter target
            else:
                self.target_tile = Vec2(tx, ty)
    
    def choose_direction(self, walls, available_dirs):
        if not available_dirs:
            return DIRS["NONE"]
            
        reverse_dir = Vec2(-self.dir.x, -self.dir.y)
        
        # Frightened: Random turn
        if self.behavior_mode == "FRIGHTENED":
            candidates = [d for d in available_dirs if not (d == reverse_dir and len(available_dirs) > 1)]
            return random.choice(candidates) if candidates else random.choice(available_dirs)
        
        # Normal Pathfinding: Minimize distance to target
        best_dir = None
        best_dist = float('inf')
        
        # Standard Red/Pink/Blue/Orange logic: never reverse spontaneously
        for d in available_dirs:
            if d == reverse_dir and len(available_dirs) > 1:
                continue
            
            test_pos = self.pos + d
            dist = test_pos.dist_sq(self.target_tile)
            if dist < best_dist:
                best_dist = dist
                best_dir = d
                
        return best_dir if best_dir else available_dirs[0]
    
    def reverse_direction(self):
        """Force 180 degree turn immediately."""
        self.dir = Vec2(-self.dir.x, -self.dir.y)
    
    def update(self, game, walls, pacman_pos, pacman_dir, blinky_pos, speed_mod, level):
        prev_mode = self.behavior_mode
        
        # --- Mode Timer Logic ---
        if self.behavior_mode == "FRIGHTENED":
            self.frightened_timer -= 1
            if self.frightened_timer <= 0:
                self.behavior_mode = "CHASE" # Default return to chase
                if not self.is_eaten:
                    self.color = self.base_color # FIXED: Restore base color
        elif not self.is_eaten:
            # Standard Scatter/Chase Cycle (Arcade Timings)
            self.mode_timer += 1
            # Level 1 timings
            cycle_times = [
                (7, "SCATTER"), (20, "CHASE"),
                (7, "SCATTER"), (20, "CHASE"),
                (5, "SCATTER"), (20, "CHASE"),
                (5, "SCATTER"), (-1, "CHASE")
            ]
            
            # Simple level scaling for timings (Arcade speeds up modes later)
            if level >= 5:
                 cycle_times = [
                    (5, "SCATTER"), (20, "CHASE"),
                    (5, "SCATTER"), (20, "CHASE"),
                    (5, "SCATTER"), (1033, "CHASE"), # effectively forever
                    (1/60, "SCATTER"), (-1, "CHASE")
                ]

            current_time = self.mode_timer / FPS
            accumulated_time = 0
            target_mode = "CHASE"
            
            for duration, mode in cycle_times:
                if duration == -1:
                    target_mode = mode
                    break
                accumulated_time += duration
                if current_time < accumulated_time:
                    target_mode = mode
                    break
            
            self.behavior_mode = target_mode

        # --- Reversal Logic ---
        # FIXED: Ghosts must reverse direction when switching modes (Scatter <-> Chase)
        if prev_mode != self.behavior_mode and not self.is_eaten:
            if prev_mode in ["SCATTER", "CHASE"] and self.behavior_mode in ["SCATTER", "CHASE"]:
                self.reverse_direction()
        
        # --- House Logic ---
        if self.is_in_house:
            self.release_timer += 1
            # Release priority: Blinky(0), Pinky(immediate), Inky(30 dots), Clyde(60 dots)
            # Simplified for this implementation using time
            release_time = [0, 2, 6, 10][[COLOR_BLINKY, COLOR_PINKY, COLOR_INKY, COLOR_CLYDE].index(self.base_color)] * FPS
            if self.release_timer > release_time:
                self.is_in_house = False
                self.pos = Vec2(13.5, 11) # Exit house
        
        # Set Target
        self.set_target(pacman_pos, blinky_pos, pacman_dir)
        
        # --- Movement Logic ---
        available_dirs = []
        for dname, dvec in DIRS.items():
            if dname != "NONE":
                # Special House Gate Logic check
                target = self.pos + dvec * 0.5
                tx, ty = int(target.x), int(target.y)
                is_gate = (tx, ty) == (13, 12) or (tx, ty) == (14, 12)
                
                # Can only enter gate if eaten or exiting house
                if is_gate:
                    if self.is_eaten or self.is_in_house:
                         available_dirs.append(dvec)
                elif self.can_move(walls, dvec):
                    available_dirs.append(dvec)
        
        # Decision point: Center of tile
        if available_dirs:
            dx = abs(self.pos.x - (int(self.pos.x) + 0.5))
            dy = abs(self.pos.y - (int(self.pos.y) + 0.5))
            
            if dx < 0.15 and dy < 0.15:
                self.pos.x = int(self.pos.x) + 0.5
                self.pos.y = int(self.pos.y) + 0.5
                self.dir = self.choose_direction(walls, available_dirs)
        
        # Move
        current_speed_vec = self.dir * 0
        if self.can_move(walls, self.dir) or (self.is_eaten and ((int(self.pos.x), int(self.pos.y)) in [(13,12), (14,12)])):
            speed = self.speed_base * speed_mod
            
            # Cruise Elroy (Blinky Speeds up when dots are low)
            if self.base_color == COLOR_BLINKY and self.behavior_mode == "CHASE" and not self.is_eaten:
                dots_left = len(game.pellets) + len(game.power_pellets)
                # Thresholds approximate Level 1
                if dots_left < 20: # Elroy 2
                    speed *= 1.10
                elif dots_left < 40: # Elroy 1
                    speed *= 1.05

            if self.behavior_mode == "FRIGHTENED": speed *= 0.6
            if self.is_eaten: speed *= 2.0
            if self.is_in_house: speed = 0.5 # Moving inside house
            
            # Tunnel Slowdown (Ghosts move at ~50% speed in tunnels)
            if int(self.pos.y) == 14 and (self.pos.x < 5 or self.pos.x > 22):
                speed *= 0.5

            current_speed_vec = self.dir * speed
            self.pos += current_speed_vec
            
        # Tunnel Wrap
        if self.pos.x < -0.5: self.pos.x = 27.5
        elif self.pos.x >= 28.5: self.pos.x = 0.5
        
        self.eye_dir = self.dir
        
        # --- Resurrection Logic ---
        if self.is_eaten:
            # Reached house center
            if abs(self.pos.x - 13.5) < 1.0 and abs(self.pos.y - 11) < 1.0:
                self.is_eaten = False
                self.behavior_mode = "CHASE"
                self.color = self.base_color # FIXED: Restore base color
                self.dir = DIRS["LEFT"] # Exit house direction

# ---------------------------------------------------------------------------
# GAME STATE
# ---------------------------------------------------------------------------

class Game:
    def __init__(self):
        self.level = 1
        self.score = 0
        self.high_score = 10000
        self.lives = 3
        self.extra_life_given = False
        self.pellets = set()
        self.power_pellets = set()
        self.walls = set()
        self.fruit_spawned = False
        self.fruit_timer = 0
        self.fruit_type = 0
        self.fruit_pos = Vec2(13.5, 17.5)
        self.game_over = False
        self.paused = False
        self.frightened_mode = False
        self.frightened_timer = 0
        self.ghost_eaten_multiplier = 1
        self.combo_timer = 0
        self.init_maze()
        
        self.pacman = Pacman()
        self.ghosts = [
            Ghost(13, 11, COLOR_BLINKY),
            Ghost(13, 14, COLOR_PINKY),
            Ghost(11, 14, COLOR_INKY),
            Ghost(15, 14, COLOR_CLYDE)
        ]
        
        self.sounds = self.generate_sounds()
        
    def generate_sounds(self):
        return {
            'eat_pellet': SoundSynthesizer.generate_square_wave(440, 0.05, 0.2, 0.5),
            'eat_power': SoundSynthesizer.generate_square_wave(880, 0.3, 0.3, 0.2),
            'eat_ghost': SoundSynthesizer.generate_square_wave(1200, 0.1, 0.4, 0.1),
            'death': SoundSynthesizer.generate_siren(880, 110, 1.0, 0.4),
            'fruit': SoundSynthesizer.generate_square_wave(600, 0.2, 0.3, 0.1),
            'start': SoundSynthesizer.generate_square_wave(330, 0.5, 0.5, 0.5)
        }
    
    def init_maze(self):
        """Initialize maze walls, pellets, and power pellets from layout"""
        self.walls.clear()
        self.pellets.clear()
        self.power_pellets.clear()
        
        for y, row in enumerate(MAZE_LAYOUT):
            for x, char in enumerate(row):
                pos = (x, y)
                if char == '#':
                    self.walls.add(pos)
                elif char == '.':
                    self.pellets.add(pos)
                elif char == 'o':
                    self.power_pellets.add(pos)
    
    def get_speed_mod(self):
        """Calculate speed multiplier based on level"""
        if self.level == 1: return 0.8
        elif self.level <= 4: return 0.9
        elif self.level <= 20: return 1.0
        else: return 1.0 # Cap at 100% speed for control
    
    def check_collisions(self):
        """Handle Pac-Man collisions with pellets, ghosts, and fruit"""
        px, py = int(self.pacman.pos.x), int(self.pacman.pos.y)
        
        # Check pellet (using set lookup for O(1))
        if (px, py) in self.pellets:
            self.pellets.remove((px, py))
            self.score += 10
            self.sounds['eat_pellet'].play()
            self.pacman.freeze_timer = 1 # Slight eating delay
            
            # Level 256 glitch logic
            if self.level == 256 and len(self.pellets) == 0:
                self.level_up()
            
            if not self.extra_life_given and self.score >= 10000:
                self.lives += 1
                self.extra_life_given = True
        
        # Check power pellet
        if (px, py) in self.power_pellets:
            self.power_pellets.remove((px, py))
            self.score += 50
            self.sounds['eat_power'].play()
            self.pacman.freeze_timer = 3 # Longer delay for power pellets
            self.frightened_mode = True
            self.frightened_timer = 6 * FPS  # 6 seconds
            self.ghost_eaten_multiplier = 1
            
            for ghost in self.ghosts:
                if not ghost.is_eaten:
                    ghost.behavior_mode = "FRIGHTENED"
                    ghost.frightened_timer = self.frightened_timer
                    # Flip direction immediately when frightened
                    ghost.reverse_direction()
        
        # Check fruit
        if self.fruit_spawned and px == 13 and py == 17:
            self.fruit_spawned = False
            points = [100, 300, 500, 700, 1000, 2000, 3000, 5000][min(self.level - 1, 7)]
            self.score += points
            self.sounds['fruit'].play()
        
        # Check ghost collisions
        for ghost in self.ghosts:
            # Simple circle/box collision
            if ghost.pos.dist_sq(self.pacman.pos) < 1.0:
                if ghost.behavior_mode == "FRIGHTENED" and not ghost.is_eaten:
                    ghost.is_eaten = True
                    ghost.behavior_mode = "CHASE"
                    points = 200 * self.ghost_eaten_multiplier
                    self.score += points
                    self.ghost_eaten_multiplier *= 2
                    self.sounds['eat_ghost'].play()
                    self.pacman.freeze_timer = 20 # Pause for eating ghost
                    
                elif not ghost.is_eaten:
                    self.lives -= 1
                    if self.lives <= 0:
                        self.game_over = True
                    else:
                        self.reset_positions()
                    self.sounds['death'].play()
                    break
    
    def reset_positions(self):
        """Reset actors for new life/level"""
        self.pacman.pos = Vec2(13.5, 23.5)
        self.pacman.dir = DIRS["LEFT"]
        self.pacman.next_dir = DIRS["LEFT"]
        
        positions = [(13, 11), (13, 14), (11, 14), (15, 14)]
        
        for i, ghost in enumerate(self.ghosts):
            ghost.pos = Vec2(positions[i][0] + 0.5, positions[i][1] + 0.5)
            ghost.dir = DIRS["LEFT"]
            ghost.is_eaten = False
            ghost.behavior_mode = "SCATTER"
            ghost.frightened_timer = 0
            ghost.is_in_house = (i > 0)
            ghost.release_timer = 0
            ghost.color = ghost.base_color # Ensure color reset
        
        self.frightened_mode = False
        self.frightened_timer = 0
    
    def level_up(self):
        self.level += 1
        if self.level == 256:
            self.apply_kill_screen_glitch()
        else:
            self.init_maze()
        
        self.reset_positions()
        self.fruit_spawned = False
        if self.level in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20]:
            self.fruit_timer = 10 * FPS
            self.fruit_type = min(self.level - 1, 7)
    
    def apply_kill_screen_glitch(self):
        """Memory corruption style glitch for Level 256"""
        for y in range(len(MAZE_LAYOUT)):
            for x in range(14, 28):
                if random.random() > 0.4: self.walls.add((x, y))
                else: self.walls.discard((x, y))
                if (x, y) not in self.walls and random.random() > 0.6:
                    self.pellets.add((x, y))
    
    def update(self):
        if self.game_over or self.paused: return
        
        speed_mod = self.get_speed_mod()
        
        self.pacman.update(self.walls, speed_mod)
        
        blinky_pos = self.ghosts[0].pos
        for ghost in self.ghosts:
            ghost.update(self, self.walls, self.pacman.pos, self.pacman.dir, blinky_pos, speed_mod, self.level)
        
        self.check_collisions()
        
        if self.frightened_mode:
            self.frightened_timer -= 1
            if self.frightened_timer <= 0:
                self.frightened_mode = False
                for ghost in self.ghosts:
                    if not ghost.is_eaten:
                        ghost.behavior_mode = "CHASE"
                        ghost.color = ghost.base_color
        
        if self.fruit_timer > 0:
            self.fruit_timer -= 1
            if self.fruit_timer == 0: self.fruit_spawned = True
        
        if len(self.pellets) == 0 and len(self.power_pellets) == 0:
            self.level_up()

# ---------------------------------------------------------------------------
# RENDERING
# ---------------------------------------------------------------------------

class Renderer:
    def __init__(self, screen):
        self.screen = screen
        pygame.font.init()
        self.font = pygame.font.SysFont('courier', 24 * SCALE // 3, bold=True)
        self.small_font = pygame.font.SysFont('courier', 16 * SCALE // 3)
        
    def draw_maze(self, game):
        for x, y in game.walls:
            rect = pygame.Rect(x * TILE_SIZE * SCALE, y * TILE_SIZE * SCALE, TILE_SIZE * SCALE, TILE_SIZE * SCALE)
            pygame.draw.rect(self.screen, COLOR_WALL, rect)
            if MAZE_LAYOUT[y][x] == '#':
                inner = rect.inflate(-4 * SCALE, -4 * SCALE)
                pygame.draw.rect(self.screen, (66, 66, 255), inner)
        
        for x, y in game.pellets:
            center = (x * TILE_SIZE * SCALE + TILE_SIZE * SCALE // 2, y * TILE_SIZE * SCALE + TILE_SIZE * SCALE // 2)
            pygame.draw.circle(self.screen, COLOR_PELLET, center, 2 * SCALE)
            
        for x, y in game.power_pellets:
            center = (x * TILE_SIZE * SCALE + TILE_SIZE * SCALE // 2, y * TILE_SIZE * SCALE + TILE_SIZE * SCALE // 2)
            radius = 4 * SCALE + int(math.sin(pygame.time.get_ticks() * 0.01) * 2)
            pygame.draw.circle(self.screen, COLOR_PELLET, center, radius)
    
    def draw_pacman(self, pacman):
        center = (pacman.pos.x * TILE_SIZE * SCALE, pacman.pos.y * TILE_SIZE * SCALE)
        radius = pacman.radius * TILE_SIZE * SCALE
        
        # FIXED: Optimized polygon drawing instead of full circle + mask
        if pacman.mouth_angle <= 0:
            pygame.draw.circle(self.screen, COLOR_PACMAN, center, radius)
        else:
            angle_rad = math.radians(pacman.angle)
            mouth_rad = math.radians(pacman.mouth_angle)
            
            # Vertices for the pie slice
            points = [center]
            steps = 20
            # Draw the solid part (the pacman body)
            # From (angle + mouth) around to (angle + 360 - mouth)
            start_a = angle_rad + mouth_rad
            end_a = angle_rad + 2 * math.pi - mouth_rad
            
            for i in range(steps + 1):
                curr_a = start_a + (end_a - start_a) * (i / steps)
                px = center[0] + radius * math.cos(curr_a)
                py = center[1] + radius * math.sin(curr_a)
                points.append((px, py))
            
            pygame.draw.polygon(self.screen, COLOR_PACMAN, points)
    
    def draw_ghost(self, ghost):
        center = (ghost.pos.x * TILE_SIZE * SCALE, ghost.pos.y * TILE_SIZE * SCALE)
        radius = ghost.radius * TILE_SIZE * SCALE
        
        if ghost.is_eaten: color = COLOR_WHITE
        elif ghost.behavior_mode == "FRIGHTENED":
            # Flashing near end of frightened time
            if ghost.frightened_timer < 2 * FPS and (ghost.frightened_timer // 10) % 2:
                color = COLOR_WHITE
            else:
                color = COLOR_FRIGHTENED
        else:
            color = ghost.color
            
        if not ghost.is_eaten:
            # Draw Dome
            pygame.draw.circle(self.screen, color, center, radius)
            # Draw Feet (Rectangle to cover bottom of circle + waves)
            rect = pygame.Rect(center[0] - radius, center[1], radius * 2, radius)
            pygame.draw.rect(self.screen, color, rect)
            
            # Wavy feet
            feet = 3
            foot_w = (radius * 2) / feet
            for i in range(feet):
                fx = center[0] - radius + i * foot_w
                fy = center[1] + radius
                offset = math.sin(pygame.time.get_ticks() * 0.01 + i) * 3
                pygame.draw.circle(self.screen, color, (fx + foot_w/2, fy - offset), foot_w/2)

        # Eyes
        eye_off_x = radius * 0.35
        eye_off_y = -radius * 0.15
        
        eye_color = COLOR_WHITE
        pupil_color = (0, 0, 255) # Blue pupils like arcade
        
        # Calculate eye position based on look direction
        look_off_x, look_off_y = 0, 0
        if ghost.eye_dir == DIRS["LEFT"]: look_off_x = -2 * SCALE
        elif ghost.eye_dir == DIRS["RIGHT"]: look_off_x = 2 * SCALE
        elif ghost.eye_dir == DIRS["UP"]: look_off_y = -2 * SCALE
        elif ghost.eye_dir == DIRS["DOWN"]: look_off_y = 2 * SCALE
        
        # Draw Whites
        pygame.draw.circle(self.screen, eye_color, (center[0] - eye_off_x + look_off_x, center[1] + eye_off_y + look_off_y), radius * 0.3)
        pygame.draw.circle(self.screen, eye_color, (center[0] + eye_off_x + look_off_x, center[1] + eye_off_y + look_off_y), radius * 0.3)
        
        # Draw Pupils
        pygame.draw.circle(self.screen, pupil_color, (center[0] - eye_off_x + look_off_x * 1.5, center[1] + eye_off_y + look_off_y * 1.5), radius * 0.15)
        pygame.draw.circle(self.screen, pupil_color, (center[0] + eye_off_x + look_off_x * 1.5, center[1] + eye_off_y + look_off_y * 1.5), radius * 0.15)

    def draw_fruit(self, game):
        if not game.fruit_spawned: return
        center = (game.fruit_pos.x * TILE_SIZE * SCALE, game.fruit_pos.y * TILE_SIZE * SCALE)
        colors = [(255,0,0), (255,180,180), (255,165,0), (255,0,0), (0,255,0), (255,255,0), (200,0,200), (255,255,255)]
        color = colors[game.fruit_type % 8]
        pygame.draw.circle(self.screen, color, center, 6 * SCALE)

    def draw_ui(self, game):
        score_t = self.font.render(f"SCORE: {game.score}", True, COLOR_WHITE)
        self.screen.blit(score_t, (10, 5))
        
        level_t = self.font.render(f"LEVEL: {min(game.level, 256)}", True, COLOR_WHITE)
        self.screen.blit(level_t, (SCREEN_WIDTH - level_t.get_width() - 10, 5))
        
        # Lives
        for i in range(max(0, game.lives - 1)):
            x = 20 * SCALE + i * 15 * SCALE
            pygame.draw.circle(self.screen, COLOR_PACMAN, (x, SCREEN_HEIGHT - 10 * SCALE), 5 * SCALE)
            
        if game.game_over:
            t = self.font.render("GAME OVER", True, COLOR_RED)
            self.screen.blit(t, (SCREEN_WIDTH//2 - t.get_width()//2, SCREEN_HEIGHT//2))
            t2 = self.small_font.render("Press R to Restart", True, COLOR_WHITE)
            self.screen.blit(t2, (SCREEN_WIDTH//2 - t2.get_width()//2, SCREEN_HEIGHT//2 + 40))

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    pygame.init()
    try:
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-BIT_DEPTH, channels=1)
    except:
        print("Audio failed to init, continuing without sound")
    
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("PAC-MAN NES EDITION")
    clock = pygame.time.Clock()
    
    game = Game()
    renderer = Renderer(screen)
    game.sounds['start'].play()
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP or event.key == pygame.K_w: game.pacman.next_dir = DIRS["UP"]
                elif event.key == pygame.K_DOWN or event.key == pygame.K_s: game.pacman.next_dir = DIRS["DOWN"]
                elif event.key == pygame.K_LEFT or event.key == pygame.K_a: game.pacman.next_dir = DIRS["LEFT"]
                elif event.key == pygame.K_RIGHT or event.key == pygame.K_d: game.pacman.next_dir = DIRS["RIGHT"]
                elif event.key == pygame.K_r: 
                    game = Game()
                    game.sounds['start'].play()
                elif event.key == pygame.K_p: game.paused = not game.paused
                elif event.key == pygame.K_ESCAPE: running = False

        if not game.paused:
            game.update()
            
        screen.fill(COLOR_BLACK)
        renderer.draw_maze(game)
        renderer.draw_fruit(game)
        for ghost in game.ghosts: renderer.draw_ghost(ghost)
        renderer.draw_pacman(game.pacman)
        renderer.draw_ui(game)
        
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
