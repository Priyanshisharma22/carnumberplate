import pygame
import sys
import random
import math

# ---------- CONFIG ----------
WIDTH, HEIGHT = 1280, 720
FPS = 60

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
pygame.display.set_caption("4 Intersection KM Network — Smart Traffic Boxes")

font_small = pygame.font.SysFont(None, 20)
font_med = pygame.font.SysFont(None, 24)
font_big = pygame.font.SysFont(None, 28)

# scale: 1 km = 80 pixels
KM = 80

# distances (pixels)
D_I1_I2 = 4 * KM
D_I1_I3 = 6 * KM
D_I2_I4 = 6 * KM  # Fixed: Match geometry (I4 is at I3.cy)
D_I3_I4 = 4 * KM

INT_SIZE = 160
ROAD_WIDTH = 56

# colors
BG = (24, 24, 24)
BLOCK_BG = (34, 139, 34)
ROAD = (36, 36, 36)
LINE = (220, 220, 220)
SIGNAL_GREEN = (0, 200, 0)
SIGNAL_RED = (200, 0, 0)
TEXT_COLOR = (245, 245, 245)

# Yellow Box style
BOX_BG = (255, 215, 0)
BOX_BORDER = (0, 0, 0)
BOX_TEXT = (0, 0, 0)

# ---------- Intersection Class ----------
class Intersection:
    def __init__(self, name, cx, cy):
        self.name = name
        self.cx = int(cx)
        self.cy = int(cy)
        self.rect = pygame.Rect(self.cx - INT_SIZE // 2, self.cy - INT_SIZE // 2, INT_SIZE, INT_SIZE)

        self.traffic = {
            "N": {"car": random.randint(5, 12), "bike": random.randint(5, 15), "bus": random.randint(0, 2)},
            "E": {"car": random.randint(5, 12), "bike": random.randint(5, 15), "bus": random.randint(0, 2)},
            "S": {"car": random.randint(5, 12), "bike": random.randint(5, 15), "bus": random.randint(0, 2)},
            "W": {"car": random.randint(5, 12), "bike": random.randint(5, 15), "bus": random.randint(0, 2)}
        }
        
        # Randomized capacities for this intersection (per side)
        # This ensures not all sides cap at 30/50. Some are small roads, some big.
        self.capacities = {
            "N": random.randint(15, 40),
            "E": random.randint(15, 40),
            "S": random.randint(15, 40),
            "W": random.randint(15, 40)
        }
        
        # Randomized "busyness" factor for this intersection (0.5 to 1.5)
        self.busyness = random.uniform(0.5, 1.5)

        self.order = ["N", "E", "S", "W"]
        self.green_index = 0
        self.green = "N"
        self.green_timer = 0
        # initial duration based on vehicles on initial green side
        self.current_green_duration = self.calc_green_duration(
            self.traffic[self.green]["car"] + self.traffic[self.green]["bike"] + self.traffic[self.green]["bus"]
        )
        self.spawn_timer = 0
        self.discharge_timer = 0
        self.discharge_interval = 600 # ms per vehicle leaving

    @staticmethod
    def calc_green_duration(total_vehicles):
        """
        Updated duration calculation per user's request:
        - Based on number of vehicles on the current green side (cars + bikes + buses)
        - 1 vehicle = 1 second (1000 ms)
        - If vehicles >= 20, directly use max 30 sec
        - Clamp final duration between 10,000 ms (10 sec) and 30,000 ms (30 sec)
        """
        duration = total_vehicles * 1000  # 1 vehicle = 1 second
        if total_vehicles >= 20:
            return 30000
        return max(10000, min(30000, duration))

    def dashed(self, surf, color, p1, p2, width=2, dash=12, gap=8):
        x1, y1 = p1
        x2, y2 = p2
        length = math.hypot(x2 - x1, y2 - y1)
        if length <= 0:
            return
        dx = (x2 - x1) / length
        dy = (y2 - y1) / length
        drawn = 0
        while drawn < length:
            seg = min(dash, length - drawn)
            sx = x1 + dx * drawn
            sy = y1 + dy * drawn
            ex = x1 + dx * (drawn + seg)
            ey = y1 + dy * (drawn + seg)
            pygame.draw.line(surf, color, (sx, sy), (ex, ey), width)
            drawn += seg + gap

    def draw(self, surf, world_to_surf):
        rx, ry = world_to_surf(self.rect.left, self.rect.top)
        # Scale dimensions
        rw = int(self.rect.width * zoom)
        rh = int(self.rect.height * zoom)
        
        surf_rect = pygame.Rect(rx, ry, rw, rh)

        # Scale road width
        scaled_road = int(ROAD_WIDTH * zoom)

        pygame.draw.rect(surf, BLOCK_BG, surf_rect)
        pygame.draw.rect(surf, ROAD, (surf_rect.left, surf_rect.centery - scaled_road // 2, surf_rect.width, scaled_road))
        pygame.draw.rect(surf, ROAD, (surf_rect.centerx - scaled_road // 2, surf_rect.top, scaled_road, surf_rect.height))

        # dashed center lines
        self.dashed(surf, LINE, (surf_rect.left, surf_rect.centery), (surf_rect.right, surf_rect.centery), width=max(1, int(3*zoom)))
        self.dashed(surf, LINE, (surf_rect.centerx, surf_rect.top), (surf_rect.centerx, surf_rect.bottom), width=max(1, int(3*zoom)))

        # small signals
        sz = int(18 * zoom)
        pad = int(8 * zoom)
        # north
        nx = surf_rect.centerx - sz // 2
        ny = surf_rect.top + pad
        pygame.draw.rect(surf, SIGNAL_GREEN if self.green == "N" else SIGNAL_RED, (nx, ny, sz, sz))
        # south
        sx = surf_rect.centerx - sz // 2
        sy = surf_rect.bottom - pad - sz
        pygame.draw.rect(surf, SIGNAL_GREEN if self.green == "S" else SIGNAL_RED, (sx, sy, sz, sz))
        # east
        ex = surf_rect.right - pad - sz
        ey = surf_rect.centery - sz // 2
        pygame.draw.rect(surf, SIGNAL_GREEN if self.green == "E" else SIGNAL_RED, (ex, ey, sz, sz))
        # west
        wx = surf_rect.left + pad
        wy = surf_rect.centery - sz // 2
        pygame.draw.rect(surf, SIGNAL_GREEN if self.green == "W" else SIGNAL_RED, (wx, wy, sz, sz))

        # intersection name
        # Only draw text if zoom is reasonable
        if zoom > 0.4:
            surf.blit(font_big.render(self.name, True, TEXT_COLOR), (surf_rect.left + 8, surf_rect.top + 8))

        # centered box + countdown
        remaining_ms = max(0, self.current_green_duration - self.green_timer)
        remaining_sec = math.ceil(remaining_ms / 1000)

        dir_text = f"GREEN → {self.green}"
        sec_text = f"{remaining_sec} sec left"

        if zoom > 0.5:
            box_w = min(int(260 * zoom), surf_rect.width - 20)
            box_h = int(84 * zoom)
            box_x = surf_rect.left + (surf_rect.width - box_w) // 2
            box_y = surf_rect.top + (surf_rect.height - box_h) // 2

            box_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
            box_surf.fill((10, 10, 10, 160))
            pygame.draw.rect(box_surf, (230, 230, 230), (0, 0, box_w, box_h), 2)
            surf.blit(box_surf, (box_x, box_y))

            dir_surf = font_med.render(dir_text, True, TEXT_COLOR)
            sec_surf = font_med.render(sec_text, True, TEXT_COLOR)
            
            # Center text in box
            surf.blit(dir_surf, dir_surf.get_rect(center=(box_x + box_w // 2, box_y + box_h // 2 - 10)))
            surf.blit(sec_surf, sec_surf.get_rect(center=(box_x + box_w // 2, box_y + box_h // 2 + 18)))

    def update(self, dt):
        self.green_timer += dt

        # --- Spawning Logic (Red Lights) ---
        self.spawn_timer += dt
        if self.spawn_timer >= 1000:
            self.spawn_timer = 0
            # Slowly add vehicles to RED sides only
            for d in self.order:
                if d == self.green:
                    continue # Don't spawn on green
                
                # Balanced spawn rates:
                # Base chance * busyness factor.
                # E.g. 0.15 * 1.0 = 15% chance per second.
                # If red for 30s -> ~4.5 cars added.
                
                cap = self.capacities[d]
                
                if random.random() < (0.15 * self.busyness): # Car
                    self.traffic[d]["car"] = min(cap, self.traffic[d]["car"] + 1)
                
                if random.random() < (0.20 * self.busyness): # Bike (slightly higher)
                    self.traffic[d]["bike"] = min(cap, self.traffic[d]["bike"] + 1)
                
                if random.random() < (0.05 * self.busyness): # Bus (rare)
                    self.traffic[d]["bus"] = min(cap, self.traffic[d]["bus"] + 1)

        # --- Discharge Logic (Green Light) ---
        self.discharge_timer += dt
        if self.discharge_timer >= self.discharge_interval:
            self.discharge_timer = 0
            # Randomize next interval slightly for realism
            self.discharge_interval = random.randint(500, 900) 
            
            side = self.traffic[self.green]
            # Prioritize vehicles? Or just random? Let's remove one random vehicle type if available
            options = []
            if side["car"] > 0: options.append("car")
            if side["bike"] > 0: options.append("bike")
            if side["bus"] > 0: options.append("bus")
            
            if options:
                choice = random.choice(options)
                side[choice] -= 1

        if self.green_timer >= self.current_green_duration:
            self.green_timer = 0
            self.green_index = (self.green_index + 1) % 4
            self.green = self.order[self.green_index]
            
            # Recalculate duration ONLY when light changes
            current_side = self.traffic[self.green]
            total_here = current_side["car"] + current_side["bike"] + current_side["bus"]
            self.current_green_duration = self.calc_green_duration(total_here)

# ---------- WORLD SETUP ----------
START_X = 200
START_Y = 200

I1 = Intersection("Intersection 1", START_X, START_Y)
I2 = Intersection("Intersection 2", START_X + INT_SIZE + D_I1_I2, START_Y)
I3 = Intersection("Intersection 3", START_X, START_Y + INT_SIZE + D_I1_I3)
I4 = Intersection("Intersection 4", I2.cx, I3.cy)

intersections = [I1, I2, I3, I4]

# Camera globals
cam_x = 0
cam_y = 0
zoom = 1.0
ZOOM_MIN = 0.1
ZOOM_MAX = 5.0

panning = False
pan_last = (0, 0)

# Center camera initially
min_x = min(it.cx for it in intersections)
min_y = min(it.cy for it in intersections)
max_x = max(it.cx for it in intersections)
max_y = max(it.cy for it in intersections)
center_x = (min_x + max_x) / 2
center_y = (min_y + max_y) / 2
cam_x = WIDTH / 2 - center_x
cam_y = HEIGHT / 2 - center_y


def world_to_surf(px, py):
    # Apply camera transform: (world - cam) * zoom + center_offset? 
    # Actually standard 2D cam: screen_x = (world_x * zoom) + cam_x
    # But we want cam_x/y to be the offset.
    sx = (px * zoom) + cam_x
    sy = (py * zoom) + cam_y
    return int(sx), int(sy)

def surf_to_world(sx, sy):
    wx = (sx - cam_x) / zoom
    wy = (sy - cam_y) / zoom
    return wx, wy

# ---------- BOX MEASUREMENT & SMART PLACEMENT ----------
def measure_box_text(text):
    # returns width,height of the block (same calculation draw_box uses)
    lines = text.split("\n")
    rendered = [font_small.render(line, True, BOX_TEXT) for line in lines]
    w = max(r.get_width() for r in rendered)
    h = sum(r.get_height() for r in rendered) + (len(lines)-1)*4
    return w, h

def rects_overlap(r1, r2):
    return not (r1.right <= r2.left or r1.left >= r2.right or r1.bottom <= r2.top or r1.top >= r2.bottom)

def overlap_area(rect, rects):
    """Return total overlap area between rect and list of rects"""
    area = 0
    for r in rects:
        if rects_overlap(rect, r):
            ix = max(0, min(rect.right, r.right) - max(rect.left, r.left))
            iy = max(0, min(rect.bottom, r.bottom) - max(rect.top, r.top))
            area += ix * iy
    return area

def compute_box_positions(intersections):
    """
    Smart-close placement:
    - Prefer positions very close to intersection edges (N/S ~25px, E/W ~45px)
    - If overlap occurs, try small nudges (left/right/up/down) within a small radius
    - If still overlapping, pick candidate with minimal overlap area
    Returns dict: { intersection: { 'N': (wx,wy,w,h,rect), ... }, ... }
    """
    placed_rects = []  # store pygame.Rect in world coords
    positions = {}

    for it in intersections:
        pos = {}
        texts = {
            "N": f"Cars: {it.traffic['N']['car']}\nBikes: {it.traffic['N']['bike']}\nBus: {it.traffic['N']['bus']}",
            "S": f"Cars: {it.traffic['S']['car']}\nBikes: {it.traffic['S']['bike']}\nBus: {it.traffic['S']['bus']}",
            "W": f"Cars: {it.traffic['W']['car']}\nBikes: {it.traffic['W']['bike']}\nBus: {it.traffic['W']['bus']}",
            "E": f"Cars: {it.traffic['E']['car']}\nBikes: {it.traffic['E']['bike']}\nBus: {it.traffic['E']['bus']}"
        }

        # close offsets
        close_y = 25   # N/S vertical distance from intersection edge
        close_x = 45   # E/W horizontal distance from intersection edge

        # Candidate generator helper
        def pick_best_candidate(candidates):
            # candidates: list of (cx,cy,w,h,rect)
            # choose first with zero overlap; else smallest overlap area
            best = None
            best_area = None
            for cx, cy, w, h, rect in candidates:
                area = overlap_area(rect, placed_rects)
                if area == 0:
                    return (cx, cy, w, h, rect)
                if best is None or area < best_area:
                    best = (cx, cy, w, h, rect)
                    best_area = area
            return best

        # NORTH candidates (primary just above intersection)
        wN, hN = measure_box_text(texts["N"])
        nx_base = it.cx
        ny_base = it.rect.top - (hN // 2) - close_y
        north_candidates = []
        # try primary and small horizontal nudges
        for dx in (0, -40, 40, -80, 80, -120, 120):
            nx = nx_base + dx
            ny = ny_base
            rectN = pygame.Rect(nx - wN//2 - 8, ny - hN//2 - 8, wN + 16, hN + 16)
            north_candidates.append((nx, ny, wN, hN, rectN))
        chosenN = pick_best_candidate(north_candidates)
        pos["N"] = chosenN
        placed_rects.append(chosenN[4])

        # SOUTH
        wS, hS = measure_box_text(texts["S"])
        sx_base = it.cx
        sy_base = it.rect.bottom + (hS // 2) + close_y
        south_candidates = []
        for dx in (0, -40, 40, -80, 80, -120, 120):
            sx = sx_base + dx
            sy = sy_base
            rectS = pygame.Rect(sx - wS//2 - 8, sy - hS//2 - 8, wS + 16, hS + 16)
            south_candidates.append((sx, sy, wS, hS, rectS))
        chosenS = pick_best_candidate(south_candidates)
        pos["S"] = chosenS
        placed_rects.append(chosenS[4])

        # WEST
        wW, hW = measure_box_text(texts["W"])
        wx_base = it.rect.left - (wW // 2) - close_x
        wy_base = it.cy
        west_candidates = []
        for dy in (0, -40, 40, -80, 80, -120, 120):
            wx = wx_base
            wy = wy_base + dy
            rectW = pygame.Rect(wx - wW//2 - 8, wy - hW//2 - 8, wW + 16, hW + 16)
            west_candidates.append((wx, wy, wW, hW, rectW))
        chosenW = pick_best_candidate(west_candidates)
        pos["W"] = chosenW
        placed_rects.append(chosenW[4])

        # EAST
        wE, hE = measure_box_text(texts["E"])
        ex_base = it.rect.right + (wE // 2) + close_x
        ey_base = it.cy
        east_candidates = []
        for dy in (0, -40, 40, -80, 80, -120, 120):
            ex = ex_base
            ey = ey_base + dy
            rectE = pygame.Rect(ex - wE//2 - 8, ey - hE//2 - 8, wE + 16, hE + 16)
            east_candidates.append((ex, ey, wE, hE, rectE))
        chosenE = pick_best_candidate(east_candidates)
        pos["E"] = chosenE
        placed_rects.append(chosenE[4])

        positions[it] = (pos, texts)

    return positions

# ---------- DRAW BOX ----------
def draw_box(surface, text, world_x, world_y):
    sx, sy = world_to_surf(world_x, world_y)
    padding = 8
    lines = text.split("\n")
    rendered = [font_small.render(line, True, BOX_TEXT) for line in lines]
    w = max(r.get_width() for r in rendered)
    h = sum(r.get_height() for r in rendered) + (len(lines)-1)*4
    
    rect = pygame.Rect(sx - w//2 - padding, sy - h//2 - padding, w + padding*2, h + padding*2)
    pygame.draw.rect(surface, BOX_BG, rect)
    pygame.draw.rect(surface, BOX_BORDER, rect, 2)
    y = rect.y + padding
    for r in rendered:
        surface.blit(r, (rect.x + padding, y))
        y += r.get_height() + 4

# ---------- ROAD DRAW HELPERS ----------
def draw_long_road(surface, p1, p2, horizontal=True):
    sx1, sy1 = world_to_surf(*p1)
    sx2, sy2 = world_to_surf(*p2)
    scaled_road = int(ROAD_WIDTH * zoom)
    
    if horizontal:
        y = sy1
        left = min(sx1, sx2)
        right = max(sx1, sx2)
        
        # Clip to screen for performance
        if right < 0 or left > WIDTH or y + scaled_road < 0 or y - scaled_road > HEIGHT:
            return

        pygame.draw.rect(surface, ROAD, (left, y - scaled_road // 2, right - left, scaled_road))
        pos = left
        while pos < right:
            seg = min(16 * zoom, right - pos)
            pygame.draw.line(surface, LINE, (pos, y), (pos + seg, y), max(1, int(3*zoom)))
            pos += seg + (12 * zoom)
    else:
        x = sx1
        top = min(sy1, sy2)
        bottom = max(sy1, sy2)

        # Clip
        if bottom < 0 or top > HEIGHT or x + scaled_road < 0 or x - scaled_road > WIDTH:
            return

        pygame.draw.rect(surface, ROAD, (x - scaled_road // 2, top, scaled_road, bottom - top))
        pos = top
        while pos < bottom:
            seg = min(16 * zoom, bottom - pos)
            pygame.draw.line(surface, LINE, (x, pos), (x, pos + seg), max(1, int(3*zoom)))
            pos += seg + (12 * zoom)

def draw_distance_label(surface, p1, p2, text):
    sx1, sy1 = world_to_surf(*p1)
    sx2, sy2 = world_to_surf(*p2)
    mx = (sx1 + sx2) // 2
    my = (sy1 + sy2) // 2
    if zoom > 0.3:
        surface.blit(font_small.render(text, True, TEXT_COLOR), (mx - 12, my - 12))

# ---------- MAIN LOOP ----------
def main():
    global cam_x, cam_y, zoom, panning, pan_last

    running = True
    while running:
        dt = clock.tick(FPS)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_PLUS or ev.key == pygame.K_EQUALS:
                    # Zoom in towards center
                    old_zoom = zoom
                    zoom = min(ZOOM_MAX, zoom * 1.15)
                    # Adjust cam to keep center fixed
                    mx, my = WIDTH // 2, HEIGHT // 2
                    # (mx - cam_x) / old_zoom = world_x
                    # new_cam_x = mx - world_x * zoom
                    world_x = (mx - cam_x) / old_zoom
                    world_y = (my - cam_y) / old_zoom
                    cam_x = mx - world_x * zoom
                    cam_y = my - world_y * zoom

                elif ev.key == pygame.K_MINUS or ev.key == pygame.K_UNDERSCORE:
                    old_zoom = zoom
                    zoom = max(ZOOM_MIN, zoom / 1.15)
                    mx, my = WIDTH // 2, HEIGHT // 2
                    world_x = (mx - cam_x) / old_zoom
                    world_y = (my - cam_y) / old_zoom
                    cam_x = mx - world_x * zoom
                    cam_y = my - world_y * zoom

                elif ev.key == pygame.K_LEFT:
                    cam_x += 80
                elif ev.key == pygame.K_RIGHT:
                    cam_x -= 80
                elif ev.key == pygame.K_UP:
                    cam_y += 80
                elif ev.key == pygame.K_DOWN:
                    cam_y -= 80
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button == 1:
                    panning = True
                    pan_last = ev.pos
                elif ev.button == 4: # Wheel up
                    mx, my = ev.pos
                    old_zoom = zoom
                    zoom = min(ZOOM_MAX, zoom * 1.15)
                    world_x = (mx - cam_x) / old_zoom
                    world_y = (my - cam_y) / old_zoom
                    cam_x = mx - world_x * zoom
                    cam_y = my - world_y * zoom
                elif ev.button == 5: # Wheel down
                    mx, my = ev.pos
                    old_zoom = zoom
                    zoom = max(ZOOM_MIN, zoom / 1.15)
                    world_x = (mx - cam_x) / old_zoom
                    world_y = (my - cam_y) / old_zoom
                    cam_x = mx - world_x * zoom
                    cam_y = my - world_y * zoom
            elif ev.type == pygame.MOUSEBUTTONUP:
                if ev.button == 1:
                    panning = False
            elif ev.type == pygame.MOUSEMOTION:
                if panning:
                    mx, my = ev.pos
                    lx, ly = pan_last
                    dx = mx - lx
                    dy = my - ly
                    cam_x += dx
                    cam_y += dy
                    pan_last = (mx, my)

        # update intersections
        for it in intersections:
            it.update(dt)

        screen.fill(BG)

        # draw roads
        draw_long_road(screen, (I1.cx, I1.cy), (I2.cx, I2.cy), horizontal=True)
        draw_distance_label(screen, (I1.cx, I1.cy), (I2.cx, I2.cy), "4 km")

        draw_long_road(screen, (I3.cx, I3.cy), (I4.cx, I4.cy), horizontal=True)
        draw_distance_label(screen, (I3.cx, I3.cy), (I4.cx, I4.cy), "4 km")

        draw_long_road(screen, (I1.cx, I1.cy), (I3.cx, I3.cy), horizontal=False)
        draw_distance_label(screen, (I1.cx, I1.cy), (I3.cx, I3.cy), "6 km")

        draw_long_road(screen, (I2.cx, I2.cy), (I4.cx, I4.cy), horizontal=False)
        draw_distance_label(screen, (I2.cx, I2.cy), (I4.cx, I4.cy), "6 km") # Fixed label

        # draw intersections
        for it in intersections:
            it.draw(screen, world_to_surf)

        # compute smart positions for all boxes (avoids overlaps, keeps proximity)
        # Optimization: Only compute this if traffic changed? Or just keep it, it's not that heavy compared to rendering 16k surface
        positions = compute_box_positions(intersections)

        # draw boxes using positions
        for it, (pos_map, texts) in positions.items():
            # pos_map entries: (cx, cy, w,h, rect)
            # draw using the center coords we computed (rect center)
            # NORTH
            nx, ny, _, _, _ = pos_map["N"]
            draw_box(screen, texts["N"], nx, ny)
            # SOUTH
            sx, sy, _, _, _ = pos_map["S"]
            draw_box(screen, texts["S"], sx, sy)
            # WEST
            wx, wy, _, _, _ = pos_map["W"]
            draw_box(screen, texts["W"], wx, wy)
            # EAST
            ex, ey, _, _, _ = pos_map["E"]
            draw_box(screen, texts["E"], ex, ey)

        hud = f"Zoom: {zoom:.2f}  |  Left-drag to pan  |  Mouse wheel or +/- to zoom  |  Arrow keys to pan"
        screen.blit(font_small.render(hud, True, (220, 220, 220)), (10, 10))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
