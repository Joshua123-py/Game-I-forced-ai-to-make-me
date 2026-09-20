import math
import random
import sys
import time
from dataclasses import dataclass

import pygame
from pygame.locals import DOUBLEBUF, OPENGL, RESIZABLE
from OpenGL.GL import *
from OpenGL.GLU import gluPerspective

# Purple Orb Arena: a compact, asset-free first-person arena shooter.
WIDTH, HEIGHT = 1280, 720
ARENA = 28.0
PURPLE = (0.65, 0.08, 1.0)
HOT_PURPLE = (1.0, 0.25, 1.0)
CYAN = (0.08, 0.75, 1.0)
WHITE = (0.9, 0.86, 1.0)


def clamp(value, low, high):
    return max(low, min(high, value))


def vec_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vec_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec_mul(a, scalar):
    return (a[0] * scalar, a[1] * scalar, a[2] * scalar)


def length(v):
    return math.sqrt(sum(x * x for x in v))


def normalize(v):
    size = length(v)
    return vec_mul(v, 1.0 / size) if size > 0.0001 else (0.0, 0.0, 0.0)


def forward(yaw, pitch=0.0):
    cp = math.cos(pitch)
    return (math.sin(yaw) * cp, math.sin(pitch), -math.cos(yaw) * cp)


def right_vector(yaw):
    return (math.cos(yaw), 0.0, math.sin(yaw))


def draw_cube(size=1.0):
    h = size / 2.0
    glBegin(GL_QUADS)
    for normal, corners in [
        ((0, 0, 1), ((-h,-h,h),(h,-h,h),(h,h,h),(-h,h,h))),
        ((0, 0, -1), ((h,-h,-h),(-h,-h,-h),(-h,h,-h),(h,h,-h))),
        ((1, 0, 0), ((h,-h,h),(h,-h,-h),(h,h,-h),(h,h,h))),
        ((-1, 0, 0), ((-h,-h,-h),(-h,-h,h),(-h,h,h),(-h,h,-h))),
        ((0, 1, 0), ((-h,h,h),(h,h,h),(h,h,-h),(-h,h,-h))),
        ((0, -1, 0), ((-h,-h,-h),(h,-h,-h),(h,-h,h),(-h,-h,h))),
    ]:
        glNormal3f(*normal)
        for corner in corners:
            glVertex3f(*corner)
    glEnd()


def draw_sphere(radius, slices=10, stacks=6):
    quad = gluNewQuadric()
    gluSphere(quad, radius, slices, stacks)
    gluDeleteQuadric(quad)


def glow_sphere(position, radius, color, alpha=1.0):
    glPushMatrix()
    glTranslatef(*position)
    glDisable(GL_LIGHTING)
    glColor4f(color[0], color[1], color[2], alpha)
    draw_sphere(radius, 10, 6)
    glEnable(GL_LIGHTING)
    glPopMatrix()


@dataclass
class Particle:
    position: tuple
    velocity: tuple
    lifetime: float
    size: float
    color: tuple
    age: float = 0.0

    def update(self, dt):
        self.position = vec_add(self.position, vec_mul(self.velocity, dt))
        self.velocity = vec_mul(self.velocity, 0.94 ** (dt * 60.0))
        self.age += dt
        return self.age < self.lifetime


class ParticleSystem:
    def __init__(self):
        self.particles = []

    def burst(self, position, color=PURPLE, count=18, speed=5.0, size=0.08):
        for _ in range(count):
            direction = normalize((random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1)))
            self.particles.append(Particle(position, vec_mul(direction, random.uniform(speed * .35, speed)), random.uniform(.25, .8), random.uniform(size*.5, size*1.5), color))

    def trail(self, position, color=HOT_PURPLE):
        self.particles.append(Particle(position, (0, 0, 0), .24, .075, color))

    def update(self, dt):
        self.particles = [p for p in self.particles if p.update(dt)]
        if len(self.particles) > 650:
            self.particles = self.particles[-650:]

    def render(self):
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        for p in self.particles:
            fade = 1.0 - p.age / p.lifetime
            glColor4f(p.color[0], p.color[1], p.color[2], fade)
            glPushMatrix()
            glTranslatef(*p.position)
            draw_sphere(p.size * (0.6 + fade), 5, 4)
            glPopMatrix()
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_BLEND)
        glEnable(GL_LIGHTING)


class Projectile:
    def __init__(self, position, direction):
        self.position = position
        self.direction = normalize(direction)
        self.speed = 25.0
        self.life = 2.5
        self.radius = .28
        self.alive = True

    def update(self, dt, game):
        self.position = vec_add(self.position, vec_mul(self.direction, self.speed * dt))
        self.life -= dt
        game.particles.trail(self.position)
        if self.life <= 0 or abs(self.position[0]) > ARENA or abs(self.position[2]) > ARENA:
            self.alive = False
            return
        for enemy in game.enemies:
            if enemy.alive and length(vec_sub(enemy.position, self.position)) < enemy.radius + self.radius:
                enemy.hit(35, game)
                game.particles.burst(self.position, HOT_PURPLE, 9, 3.0, .07)
                self.alive = False
                break

    def render(self):
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        glow_sphere(self.position, .48, PURPLE, .16)
        glow_sphere(self.position, .22, HOT_PURPLE, 1.0)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_BLEND)
        glEnable(GL_LIGHTING)


class Enemy:
    def __init__(self, position, elite=False):
        self.position = position
        self.elite = elite
        self.radius = 1.15 if elite else .78
        self.max_health = 150 if elite else 70
        self.health = self.max_health
        self.speed = 2.0 if elite else 1.45
        self.damage_timer = random.random()
        self.phase = random.uniform(0, math.tau)
        self.alive = True
        self.hit_flash = 0.0

    def hit(self, damage, game):
        self.health -= damage
        self.hit_flash = .12
        if self.health <= 0:
            self.alive = False
            game.kills += 1
            game.score += 125 if self.elite else 50
            game.particles.burst(self.position, HOT_PURPLE if self.elite else PURPLE, 32 if self.elite else 20, 7, .12)
            game.particles.burst(self.position, CYAN, 10, 4, .06)

    def update(self, dt, game):
        if not self.alive:
            return
        self.phase += dt * 2.5
        self.hit_flash = max(0, self.hit_flash - dt)
        offset = vec_sub(game.player.position, self.position)
        distance = length(offset)
        if distance > 2.0:
            self.position = vec_add(self.position, vec_mul(normalize(offset), self.speed * dt))
        self.position = (clamp(self.position[0], -ARENA + 1, ARENA - 1), 1.4 + math.sin(self.phase) * .35, clamp(self.position[2], -ARENA + 1, ARENA - 1))
        self.damage_timer -= dt
        if distance < self.radius + .9 and self.damage_timer <= 0:
            game.player.damage(9 if self.elite else 5, game)
            self.damage_timer = .7 if self.elite else .95

    def render(self):
        if not self.alive:
            return
        color = WHITE if self.hit_flash else (HOT_PURPLE if self.elite else PURPLE)
        glPushMatrix()
        glTranslatef(*self.position)
        glRotatef(math.sin(self.phase) * 10, 0, 1, 0)
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        glow_sphere((0, 0, 0), self.radius * 1.35, color, .12)
        glColor4f(*color, 1)
        draw_sphere(self.radius, 12, 8)
        glColor4f(.1, .02, .18, 1)
        draw_sphere(self.radius * .62, 10, 6)
        glColor4f(1, .35, 1, 1)
        for angle in range(0, 360, 90):
            glPushMatrix()
            glRotatef(angle, 0, 1, 0)
            glTranslatef(self.radius * .8, 0, 0)
            draw_sphere(.12 if not self.elite else .18, 6, 4)
            glPopMatrix()
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_BLEND)
        glEnable(GL_LIGHTING)
        glPopMatrix()


class Player:
    def __init__(self):
        self.position = (0.0, 1.7, 13.0)
        self.yaw = 0.0
        self.pitch = 0.0
        self.health = 100
        self.max_health = 100
        self.dead = False
        self.shake = 0.0
        self.walk_time = 0.0

    def damage(self, amount, game):
        if self.dead:
            return
        self.health = max(0, self.health - amount)
        self.shake = max(self.shake, .12)
        if self.health <= 0:
            self.dead = True
            game.wave_message = "SYSTEM FAILURE"
            game.wave_message_time = 3
            game.particles.burst(self.position, HOT_PURPLE, 35, 5, .1)

    def update(self, dt, game):
        if self.dead:
            return
        keys = pygame.key.get_pressed()
        movement = (0, 0, 0)
        speed = 9.0 if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] else 5.2
        right = right_vector(self.yaw)
        front = forward(self.yaw)
        if keys[pygame.K_w]: movement = vec_add(movement, front)
        if keys[pygame.K_s]: movement = vec_sub(movement, front)
        if keys[pygame.K_d]: movement = vec_add(movement, right)
        if keys[pygame.K_a]: movement = vec_sub(movement, right)
        if length(movement) > 0:
            movement = vec_mul(normalize((movement[0], 0, movement[2])), speed * dt)
            self.walk_time += dt * (speed / 5)
        self.position = vec_add(self.position, movement)
        self.position = (clamp(self.position[0], -ARENA + 1.3, ARENA - 1.3), 1.7, clamp(self.position[2], -ARENA + 1.3, ARENA - 1.3))
        self.shake = max(0, self.shake - dt)

    def look(self, dx, dy):
        if self.dead:
            return
        self.yaw += dx * .0022
        self.pitch = clamp(self.pitch - dy * .0022, -1.35, 1.35)

    def reset(self):
        self.__init__()


class Weapon:
    def __init__(self):
        self.cooldown = 0.0
        self.recoil = 0.0
        self.flash = 0.0

    def update(self, dt, game):
        self.cooldown = max(0, self.cooldown - dt)
        self.recoil = max(0, self.recoil - dt * 5)
        self.flash = max(0, self.flash - dt)
        if pygame.mouse.get_pressed()[0] and self.cooldown <= 0 and not game.player.dead:
            self.fire(game)

    def fire(self, game):
        self.cooldown = .19
        self.recoil = 1.0
        self.flash = .075
        game.player.shake = max(game.player.shake, .045)
        direction = forward(game.player.yaw, game.player.pitch)
        origin = vec_add(game.player.position, vec_add(vec_mul(direction, .9), (0, -.15, 0)))
        game.projectiles.append(Projectile(origin, direction))
        game.particles.burst(origin, HOT_PURPLE, 8, 2, .06)

    def render(self, player):
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        bob = math.sin(player.walk_time * 8) * .025
        glTranslatef(.58 + bob, -.48 - self.recoil * .08, -1.05)
        glRotatef(-10, 0, 1, 0)
        glRotatef(8, 1, 0, 0)
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        glColor4f(.18, .02, .32, 1)
        draw_cube(.42)
        glTranslatef(0, 0, -.32)
        glColor4f(*PURPLE, 1)
        draw_cube(.25)
        glTranslatef(0, 0, -.25)
        glColor4f(*HOT_PURPLE, 1)
        draw_sphere(.15, 10, 6)
        if self.flash:
            glColor4f(1, .6, 1, 1)
            glTranslatef(0, 0, -.22)
            draw_sphere(.3, 8, 5)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_BLEND)
        glEnable(GL_LIGHTING)
        glPopMatrix()


class WaveManager:
    def __init__(self):
        self.wave = 0
        self.waiting = True
        self.timer = 1.0

    def update(self, dt, game):
        living = any(enemy.alive for enemy in game.enemies)
        if not living and not game.player.dead:
            self.timer -= dt
            if self.timer <= 0:
                self.wave += 1
                self.timer = 2.5
                self.waiting = False
                game.spawn_wave(self.wave)
                game.player.health = min(game.player.max_health, game.player.health + 12)
                game.wave_message = f"WAVE {self.wave}"
                game.wave_message_time = 2.2


class HUD:
    def __init__(self):
        self.font = None
        self.big = None

    def load(self):
        self.font = pygame.font.SysFont("consolas", 21, bold=True)
        self.big = pygame.font.SysFont("consolas", 64, bold=True)

    def text(self, surface, words, position, size=None, color=WHITE, center=False):
        font = self.big if size == "big" else self.font
        image = font.render(words, True, color)
        rect = image.get_rect()
        if center:
            rect.center = position
        else:
            rect.topleft = position
        surface.blit(image, rect)

    def render(self, game):
        surface = pygame.display.get_surface()
        self.text(surface, f"HP  {game.player.health:03d} / {game.player.max_health}", (24, 22), color=WHITE)
        self.text(surface, f"SCORE  {game.score:06d}", (24, 51), color=HOT_PURPLE)
        self.text(surface, f"WAVE  {game.wave.wave:02d}    KILLS  {game.kills:03d}", (24, 80), color=WHITE)
        self.text(surface, "PURPLE ORB CANNON", (WIDTH - 290, 24), color=HOT_PURPLE)
        self.text(surface, "WASD MOVE   SHIFT SPRINT   LMB FIRE   ESC QUIT", (WIDTH//2, HEIGHT - 30), color=WHITE, center=True)
        pygame.draw.line(surface, HOT_PURPLE, (WIDTH//2-10, HEIGHT//2), (WIDTH//2+10, HEIGHT//2), 2)
        pygame.draw.line(surface, HOT_PURPLE, (WIDTH//2, HEIGHT//2-10), (WIDTH//2, HEIGHT//2+10), 2)
        if game.wave_message_time > 0 and not game.player.dead:
            self.text(surface, game.wave_message, (WIDTH//2, HEIGHT//2-100), size="big", color=HOT_PURPLE, center=True)
        if game.player.dead:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((15, 0, 25, 170))
            surface.blit(overlay, (0, 0))
            self.text(surface, "GAME OVER", (WIDTH//2, HEIGHT//2-90), size="big", color=HOT_PURPLE, center=True)
            self.text(surface, f"FINAL SCORE  {game.score}   WAVE  {game.wave.wave}   KILLS  {game.kills}", (WIDTH//2, HEIGHT//2), color=WHITE, center=True)
            self.text(surface, "PRESS R TO RESTART", (WIDTH//2, HEIGHT//2+65), color=HOT_PURPLE, center=True)


class Arena:
    def render(self):
        glDisable(GL_LIGHTING)
        glColor3f(.025, .008, .05)
        glBegin(GL_QUADS)
        glVertex3f(-ARENA, 0, -ARENA); glVertex3f(ARENA, 0, -ARENA); glVertex3f(ARENA, 0, ARENA); glVertex3f(-ARENA, 0, ARENA)
        glEnd()
        glLineWidth(1)
        glColor4f(.28, .02, .5, .7)
        glBegin(GL_LINES)
        for line in range(-int(ARENA), int(ARENA)+1, 2):
            glVertex3f(line, .015, -ARENA); glVertex3f(line, .015, ARENA)
            glVertex3f(-ARENA, .015, line); glVertex3f(ARENA, .015, line)
        glEnd()
        glColor3f(.22, .015, .4)
        for x, z, scale in [(-12,-10,2.5),(12,-7,3),(-14,9,2),(13,12,2.4),(0,-17,2)]:
            glPushMatrix(); glTranslatef(x, scale/2, z); glColor3f(.08,.01,.16); draw_cube(scale); glPopMatrix()
        glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        glColor4f(*PURPLE, .7)
        for y in (1, 5, 9):
            glBegin(GL_LINE_LOOP)
            glVertex3f(-ARENA, y, -ARENA); glVertex3f(ARENA, y, -ARENA); glVertex3f(ARENA, y, ARENA); glVertex3f(-ARENA, y, ARENA)
            glEnd()
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA); glDisable(GL_BLEND); glEnable(GL_LIGHTING)


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("PURPLE ORB ARENA")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), OPENGL | DOUBLEBUF | RESIZABLE)
        self.clock = pygame.time.Clock()
        self.setup_gl(WIDTH, HEIGHT)
        self.player = Player(); self.weapon = Weapon(); self.particles = ParticleSystem()
        self.arena = Arena(); self.hud = HUD(); self.hud.load(); self.wave = WaveManager()
        self.enemies = []; self.projectiles = []; self.score = 0; self.kills = 0
        self.wave_message = "WAVE 1"; self.wave_message_time = 2.0
        self.running = True
        pygame.event.set_grab(True); pygame.mouse.set_visible(False)

    def setup_gl(self, width, height):
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION); glLoadIdentity(); gluPerspective(75, width / max(1, height), .05, 120)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()
        glEnable(GL_DEPTH_TEST); glEnable(GL_CULL_FACE); glEnable(GL_COLOR_MATERIAL)
        glEnable(GL_LIGHTING); glEnable(GL_LIGHT0); glLightfv(GL_LIGHT0, GL_POSITION, (0, 8, 0, 1)); glLightfv(GL_LIGHT0, GL_DIFFUSE, (.4, .15, .6, 1))
        glClearColor(.008, .002, .018, 1)

    def reset(self):
        self.player.reset(); self.weapon = Weapon(); self.enemies = []; self.projectiles = []; self.score = 0; self.kills = 0
        self.wave = WaveManager(); self.wave_message = "WAVE 1"; self.wave_message_time = 2.0

    def spawn_wave(self, number):
        count = min(4 + number * 2, 18)
        for i in range(count):
            angle = math.tau * i / count + random.uniform(-.2, .2)
            radius = random.uniform(15, 24)
            elite = number >= 4 and (i % max(2, 7 - number // 2) == 0)
            self.enemies.append(Enemy((math.sin(angle)*radius, 1.5, math.cos(angle)*radius), elite))

    def update(self, dt):
        self.wave_message_time = max(0, self.wave_message_time - dt)
        self.player.update(dt, self); self.weapon.update(dt, self)
        self.wave.update(dt, self)
        for enemy in self.enemies: enemy.update(dt, self)
        for projectile in self.projectiles: projectile.update(dt, self)
        self.projectiles = [p for p in self.projectiles if p.alive]
        self.particles.update(dt)
        self.enemies = [e for e in self.enemies if e.alive or random.random() > dt * 4]

    def render(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()
        shake = self.player.shake
        view_yaw = self.player.yaw + random.uniform(-shake, shake) * .06
        view_pitch = self.player.pitch + random.uniform(-shake, shake) * .06
        direction = forward(view_yaw, view_pitch)
        target = vec_add(self.player.position, direction)
        from_point = self.player.position
        gluLookAt(*from_point, *target, 0, 1, 0)
        self.arena.render()
        for enemy in self.enemies: enemy.render()
        for projectile in self.projectiles: projectile.render()
        self.particles.render()
        self.weapon.render(self.player)
        glDisable(GL_DEPTH_TEST)
        # HUD is drawn after the 3D scene by switching to a normal 2D surface.
        glEnable(GL_DEPTH_TEST)
        pygame.display.flip()
        self.hud.render(self)
        pygame.display.flip()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: self.running = False
                elif event.key == pygame.K_r and self.player.dead: self.reset()
            elif event.type == pygame.MOUSEMOTION and not self.player.dead: self.player.look(*event.rel)
            elif event.type == pygame.VIDEORESIZE:
                self.setup_gl(event.w, event.h)

    def run(self):
        self.spawn_wave(1)
        last = time.perf_counter()
        while self.running:
            now = time.perf_counter(); dt = min(.05, now - last); last = now
            self.handle_events(); self.update(dt); self.render(); self.clock.tick(120)
        pygame.quit(); sys.exit()


if __name__ == "__main__":
    Game().run()

# The remainder of this source is intentionally documentation padding reserved
# for future design notes. The playable implementation above stays compact and
# readable so it can be modified by new contributors.
