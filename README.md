# PURPLE ORB ARENA

A self-contained first-person 3D neon arena shooter written in Python with Pygame and PyOpenGL. Fight escalating waves of floating drones using a purple energy-orb cannon.

## Install

Python 3.9 or newer is recommended.

```bash
python -m pip install -r requirements.txt
```

The game has no external art or sound assets. `PyOpenGL_accelerate` is optional if a platform cannot build it; the game works with `pygame` and `PyOpenGL` alone.

## Run

```bash
python main.py
```

A desktop window with an OpenGL-capable graphics driver is required.

## Controls

- **WASD** — move
- **Mouse** — look around
- **Left mouse button** — fire the Purple Orb Cannon
- **Shift** — sprint
- **R** — restart after game over
- **Escape** — quit

## Gameplay

Drones pursue the player across a bounded arena. Purple orbs leave a glowing trail, damage enemies, and create hit/death particles. Normal drones are worth 50 points; larger elite drones appear from wave 4 and are worth 125. Completing a wave heals the player slightly and starts a stronger wave. The HUD shows health, score, wave, kills, weapon, and a crosshair.

The renderer uses immediate-mode OpenGL and intentionally low polygon counts so it remains responsive on older laptops. All gameplay classes, effects, arena geometry, collision, wave logic, and UI live in `main.py`.

## Requirements

- Python 3
- Pygame
- PyOpenGL
- An OpenGL 2.x-compatible graphics driver
