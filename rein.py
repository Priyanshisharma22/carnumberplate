import pygame
import sys
import random
import math

# ---------- Config ----------
WIDTH, HEIGHT = 900, 900
FPS = 60

CENTER = (WIDTH // 2, HEIGHT // 2)
LANES_PER_DIRECTION = 2
LANE_WIDTH = 28
ROAD_HALF_WIDTH = LANES_PER_DIRECTION * LANE_WIDTH

ROAD_COLOR = (30, 30, 30)
BACKGROUND = (34, 139, 34)
LINE_COLOR = (220, 220, 220)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
pygame.display.set_caption("Dynamic Traffic System")

def draw_dashed_line(surf, color, start_pos, end_pos, width=2, dash_length=18, gap_length=14):
    x1, y1 = start_pos
    x2, y2 = end_pos
    length = math.hypot(x2 - x1, y2 - y1)
    dx = (x2 - x1) / length
    dy = (y2 - y1) / length
    drawn = 0.0
    while drawn < length:
        dash_end = min(dash_length, length - drawn)
        sx = x1 + dx * drawn
        sy = y1 + dy * drawn
        ex = x1 + dx * (drawn + dash_end)
        ey = y1 + dy * (drawn + dash_end)
        pygame.draw.line(surf, color, (sx, sy), (ex, ey), width)
        drawn += dash_end + gap_length

def draw_intersection(surf):
    surf.fill(BACKGROUND)
    cx, cy = CENTER
    pygame.draw.rect(surf, ROAD_COLOR, (0, cy - ROAD_HALF_WIDTH, WIDTH, ROAD_HALF_WIDTH * 2))
    pygame.draw.rect(surf, ROAD_COLOR, (cx - ROAD_HALF_WIDTH, 0, ROAD_HALF_WIDTH * 2, HEIGHT))
    draw_dashed_line(surf, (220,220,220), (0, cy), (WIDTH, cy), width=3)
    draw_dashed_line(surf, (220,220,220), (cx, 0), (cx, HEIGHT), width=3)

def draw_signals(active):
    cx, cy = CENTER
    colors = {"GREEN": (0, 255, 0), "RED": (255, 0, 0)}

    pygame.draw.rect(screen, colors["GREEN"] if active == "N" else colors["RED"], (cx - 20, cy - 200, 40, 40))
    pygame.draw.rect(screen, colors["GREEN"] if active == "S" else colors["RED"], (cx - 20, cy + 160, 40, 40))
    pygame.draw.rect(screen, colors["GREEN"] if active == "E" else colors["RED"], (cx + 160, cy - 20, 40, 40))
    pygame.draw.rect(screen, colors["GREEN"] if active == "W" else colors["RED"], (cx - 200, cy - 20, 40, 40))

# ---------- Main Loop ----------
def main():
    font = pygame.font.SysFont(None, 38)

    # initial traffic
    traffic = {
        "N": {"car": 10, "bike": 12, "bus": 3},
        "E": {"car": 9,  "bike": 15, "bus": 4},
        "W": {"car": 11, "bike": 14, "bus": 2},
        "S": {"car": 13, "bike": 18, "bus": 5}
    }

    directions = ["N", "E", "W", "S"]
    current_index = 0
    current_green = directions[current_index]

    green_timer = 0
    spawn_timer = 0

    running = True
    while running:
        dt = clock.tick(FPS)
        green_timer += dt
        spawn_timer += dt

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

        # --------------------
        # CHANGE SIGNAL (5 sec)
        # --------------------
        if green_timer >= 5000:
            green_timer = 0
            current_index = (current_index + 1) % 4
            current_green = directions[current_index]

        # ---------------------
        # VEHICLES ARRIVING (every 1 sec)
        # ---------------------
        if spawn_timer >= 1000:
            spawn_timer = 0
            for d in directions:
                traffic[d]["car"] += random.randint(0, 3)
                traffic[d]["bike"] += random.randint(0, 4)
                traffic[d]["bus"] += random.randint(0, 1)

        # ---------------------
        # GREEN SIDE VEHICLES LEAVING (realistic)
        # ---------------------
        side = traffic[current_green]

        side["car"] = max(3, side["car"] - random.randint(1, 3))
        side["bike"] = max(3, side["bike"] - random.randint(1, 4))
        if side["bus"] > 1:
            side["bus"] -= 1

        draw_intersection(screen)
        draw_signals(current_green)

        # Show all directions
        y = 20
        for d in ["N", "E", "W", "S"]:
            t = traffic[d]
            text = font.render(f"{d} → Cars:{t['car']}  Bikes:{t['bike']}  Bus:{t['bus']}",
                               True, (255, 255, 255))
            screen.blit(text, (20, y))
            y += 40

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
