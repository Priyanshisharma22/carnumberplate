# traffic_final.py
import pygame
import random
import sys
from pygame.math import Vector2

# ---------- CONFIG ----------
WIDTH, HEIGHT = 1000, 800
CENTER = Vector2(WIDTH // 2, HEIGHT // 2)
FPS = 60

SPAWN_INTERVAL = 900      # ms between spawn attempts
STOP_DISTANCE = 160       # how far from center vehicles stop (stop-line)
LANE_OFFSETS = [-90, -35, 35, 90]  # lanes side-by-side (4 lanes)
SAFE_GAP = 72             # safe gap between queued vehicles
MAX_QUEUE = 6             # max vehicles allowed queued in a single lane

VEHICLE_TYPES = {
    "car":  {"size": (28, 50),  "speed": 180, "color": (34, 139, 34)},
    "bus":  {"size": (40, 100), "speed": 120, "color": (178, 34, 34)},
    "bike": {"size": (18, 36),  "speed": 220, "color": (30, 144, 255)},
}

# ---------- PYGAME INIT ----------
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Realistic 4-Way: Stop Before Intersection, No Overlap")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 28)
small_font = pygame.font.SysFont(None, 18)

global_counts = {"car": 0, "bus": 0, "bike": 0}

# ---------- VEHICLE CLASS ----------
class Vehicle:
    def __init__(self, vtype, direction, lane_offset):
        self.vtype = vtype
        self.width, self.height = VEHICLE_TYPES[vtype]["size"]
        self.color = VEHICLE_TYPES[vtype]["color"]
        self.speed = VEHICLE_TYPES[vtype]["speed"]
        self.direction = direction         # 'N','S','E','W'
        self.lane_offset = lane_offset     # lateral offset for lane
        self.stopped = False

        global_counts[vtype] += 1
        self.id = global_counts[vtype]

        # spawn positions (just off-screen)
        margin = 120
        if direction == "N":
            self.pos = Vector2(CENTER.x + lane_offset, -margin)
            self.vel = Vector2(0, 1)
        elif direction == "S":
            self.pos = Vector2(CENTER.x + lane_offset, HEIGHT + margin)
            self.vel = Vector2(0, -1)
        elif direction == "W":
            self.pos = Vector2(-margin, CENTER.y + lane_offset)
            self.vel = Vector2(1, 0)
        elif direction == "E":
            self.pos = Vector2(WIDTH + margin, CENTER.y + lane_offset)
            self.vel = Vector2(-1, 0)

    def update(self, dt, vehicles):
        # if already stopped, do nothing (remains at its final queued position)
        if self.stopped:
            return

        # move forward
        self.pos += self.vel * self.speed * dt

        # queue logic: determine front-most stopped vehicle in same lane (if any)
        if self.direction == "N":
            base_stop_y = CENTER.y - STOP_DISTANCE
            # other vehicles in same lane (exclude self)
            lane_mates = [v for v in vehicles if v is not self and v.direction == "N" and v.lane_offset == self.lane_offset]
            stopped_mates = [v for v in lane_mates if v.stopped]
            if stopped_mates:
                # front-most has largest y
                front = max(stopped_mates, key=lambda v: v.pos.y)
                # new target is front.pos.y - SAFE_GAP (so we stand behind)
                target_y = front.pos.y - SAFE_GAP
                # ensure target is not inside central box zone
                min_allowed_y = CENTER.y - STOP_DISTANCE - (MAX_QUEUE-1)*SAFE_GAP
                if target_y > min_allowed_y:
                    target_y = max(target_y, min_allowed_y)
                if self.pos.y >= target_y:
                    self.pos.y = target_y
                    self.pos.x = CENTER.x + self.lane_offset  # align lane x
                    self.stopped = True
            else:
                # nobody stopped yet in lane: stop at base_stop_y
                if self.pos.y >= base_stop_y:
                    self.pos.y = base_stop_y
                    self.pos.x = CENTER.x + self.lane_offset
                    self.stopped = True

        elif self.direction == "S":
            base_stop_y = CENTER.y + STOP_DISTANCE
            lane_mates = [v for v in vehicles if v is not self and v.direction == "S" and v.lane_offset == self.lane_offset]
            stopped_mates = [v for v in lane_mates if v.stopped]
            if stopped_mates:
                front = min(stopped_mates, key=lambda v: v.pos.y)  # front-most has smallest y
                target_y = front.pos.y + SAFE_GAP
                max_allowed_y = CENTER.y + STOP_DISTANCE + (MAX_QUEUE-1)*SAFE_GAP
                if target_y < max_allowed_y:
                    target_y = min(target_y, max_allowed_y)
                if self.pos.y <= target_y:
                    self.pos.y = target_y
                    self.pos.x = CENTER.x + self.lane_offset
                    self.stopped = True
            else:
                if self.pos.y <= base_stop_y:
                    self.pos.y = base_stop_y
                    self.pos.x = CENTER.x + self.lane_offset
                    self.stopped = True

        elif self.direction == "W":
            base_stop_x = CENTER.x - STOP_DISTANCE
            lane_mates = [v for v in vehicles if v is not self and v.direction == "W" and v.lane_offset == self.lane_offset]
            stopped_mates = [v for v in lane_mates if v.stopped]
            if stopped_mates:
                front = max(stopped_mates, key=lambda v: v.pos.x)
                target_x = front.pos.x - SAFE_GAP
                min_allowed_x = CENTER.x - STOP_DISTANCE - (MAX_QUEUE-1)*SAFE_GAP
                if target_x > min_allowed_x:
                    target_x = max(target_x, min_allowed_x)
                if self.pos.x >= target_x:
                    self.pos.x = target_x
                    self.pos.y = CENTER.y + self.lane_offset
                    self.stopped = True
            else:
                if self.pos.x >= base_stop_x:
                    self.pos.x = base_stop_x
                    self.pos.y = CENTER.y + self.lane_offset
                    self.stopped = True

        elif self.direction == "E":
            base_stop_x = CENTER.x + STOP_DISTANCE
            lane_mates = [v for v in vehicles if v is not self and v.direction == "E" and v.lane_offset == self.lane_offset]
            stopped_mates = [v for v in lane_mates if v.stopped]
            if stopped_mates:
                front = min(stopped_mates, key=lambda v: v.pos.x)
                target_x = front.pos.x + SAFE_GAP
                max_allowed_x = CENTER.x + STOP_DISTANCE + (MAX_QUEUE-1)*SAFE_GAP
                if target_x < max_allowed_x:
                    target_x = min(target_x, max_allowed_x)
                if self.pos.x <= target_x:
                    self.pos.x = target_x
                    self.pos.y = CENTER.y + self.lane_offset
                    self.stopped = True
            else:
                if self.pos.x <= base_stop_x:
                    self.pos.x = base_stop_x
                    self.pos.y = CENTER.y + self.lane_offset
                    self.stopped = True

    def draw(self, surf):
        if self.direction in ("N", "S"):
            w, h = self.width, self.height
        else:
            w, h = self.height, self.width
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (int(self.pos.x), int(self.pos.y))
        pygame.draw.rect(surf, self.color, rect)
        # type and id labels
        surf.blit(small_font.render(self.vtype[0].upper(), True, (255,255,255)), (rect.centerx - 6, rect.centery - 8))
        surf.blit(small_font.render(str(self.id), True, (255,215,0)), (rect.centerx - 6, rect.top - 16))

    def is_offscreen(self):
        return (self.pos.x < -200 or self.pos.x > WIDTH + 200 or self.pos.y < -200 or self.pos.y > HEIGHT + 200)


# ---------- DRAW ROAD ----------
def draw_intersection(surf):
    surf.fill((200,200,200))
    road_w = 300
    pygame.draw.rect(surf, (50,50,50), (CENTER.x - road_w//2, 0, road_w, HEIGHT))
    pygame.draw.rect(surf, (50,50,50), (0, CENTER.y - road_w//2, WIDTH, road_w))
    pygame.draw.rect(surf, (40,40,40), (CENTER.x - 90, CENTER.y - 90, 180, 180))
    pygame.draw.circle(surf, (255,215,0), (int(CENTER.x), int(CENTER.y)), 8)

    # stop lines
    ls = 100
    lw = 4
    pygame.draw.line(surf, (255,255,255), (CENTER.x - ls//2, CENTER.y - STOP_DISTANCE), (CENTER.x + ls//2, CENTER.y - STOP_DISTANCE), lw)
    pygame.draw.line(surf, (255,255,255), (CENTER.x - ls//2, CENTER.y + STOP_DISTANCE), (CENTER.x + ls//2, CENTER.y + STOP_DISTANCE), lw)
    pygame.draw.line(surf, (255,255,255), (CENTER.x - STOP_DISTANCE, CENTER.y - ls//2), (CENTER.x - STOP_DISTANCE, CENTER.y + ls//2), lw)
    pygame.draw.line(surf, (255,255,255), (CENTER.x + STOP_DISTANCE, CENTER.y - ls//2), (CENTER.x + STOP_DISTANCE, CENTER.y + ls//2), lw)


# ---------- MAIN LOOP ----------
vehicles = []
directions = ["N", "S", "E", "W"]
last_spawn = pygame.time.get_ticks()
running = True

while running:
    dt = clock.tick(FPS) / 1000.0
    now = pygame.time.get_ticks()

    # events
    for e in pygame.event.get():
        if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
            running = False

    # spawn attempt: choose a direction and lane where queue < MAX_QUEUE
    if now - last_spawn > SPAWN_INTERVAL:
        vtype = random.choice(list(VEHICLE_TYPES.keys()))
        direction = random.choice(directions)
        # try to pick a lane with space; if none available in chosen direction, try others
        lane_choice = None
        order = LANE_OFFSETS[:]
        random.shuffle(order)
        for lane in order:
            queued = sum(1 for v in vehicles if v.direction == direction and v.lane_offset == lane and v.stopped)
            if queued < MAX_QUEUE:
                lane_choice = lane
                break
        # if chosen direction had no lane with space, try other directions
        if lane_choice is None:
            for dir_try in directions:
                order2 = LANE_OFFSETS[:]
                random.shuffle(order2)
                for lane in order2:
                    queued = sum(1 for v in vehicles if v.direction == dir_try and v.lane_offset == lane and v.stopped)
                    if queued < MAX_QUEUE:
                        direction = dir_try
                        lane_choice = lane
                        break
                if lane_choice is not None:
                    break

        # spawn only if lane_choice found
        if lane_choice is not None:
            vehicles.append(Vehicle(vtype, direction, lane_choice))
        # else skip spawn this cycle (lanes are full)
        last_spawn = now

    # update all vehicles
    for v in vehicles:
        v.update(dt, vehicles)

    # remove offscreen (left the scene after crossing; note: no crossing logic here)
    vehicles = [v for v in vehicles if not v.is_offscreen()]

    # draw everything
    draw_intersection(screen)
    for v in vehicles:
        v.draw(screen)

    # counts per direction
    counts = {d: {"car":0,"bus":0,"bike":0} for d in directions}
    for v in vehicles:
        if v.stopped:
            counts[v.direction][v.vtype] += 1

    # HUD (direction labels and counts)
    screen.blit(font.render("NORTH", True, (0,0,150)), (CENTER.x - 40, CENTER.y - 300))
    screen.blit(font.render(f"🚗{counts['N']['car']} 🚌{counts['N']['bus']} 🏍️{counts['N']['bike']}", True, (0,0,0)), (CENTER.x - 90, CENTER.y - 270))
    screen.blit(font.render("SOUTH", True, (0,0,150)), (CENTER.x - 40, CENTER.y + 240))
    screen.blit(font.render(f"🚗{counts['S']['car']} 🚌{counts['S']['bus']} 🏍️{counts['S']['bike']}", True, (0,0,0)), (CENTER.x - 90, CENTER.y + 270))
    screen.blit(font.render("WEST", True, (0,0,150)), (CENTER.x - 480, CENTER.y - 20))
    screen.blit(font.render(f"🚗{counts['W']['car']} 🚌{counts['W']['bus']} 🏍️{counts['W']['bike']}", True, (0,0,0)), (CENTER.x - 400, CENTER.y + 10))
    screen.blit(font.render("EAST", True, (0,0,150)), (CENTER.x + 260, CENTER.y - 20))
    screen.blit(font.render(f"🚗{counts['E']['car']} 🚌{counts['E']['bus']} 🏍️{counts['E']['bike']}", True, (0,0,0)), (CENTER.x + 200, CENTER.y + 10))

    pygame.display.flip()

pygame.quit()
sys.exit()
