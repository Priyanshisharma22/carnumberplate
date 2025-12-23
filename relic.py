import pygame
import sys
import random
import math

pygame.init()

# ------------------------------
# DISPLAY: FULLSCREEN WINDOW
# ------------------------------
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
WIDTH, HEIGHT = screen.get_size()
pygame.display.set_caption("Ambulance + Smart Traffic (A–E Network)")

FONT = pygame.font.SysFont("arial", 22)
SMALL = pygame.font.SysFont("arial", 18)

BASE_W, BASE_H = WIDTH, HEIGHT

# ------------------------------
# NODES (INTERSECTIONS A–E)
# ------------------------------
nodes = [
    {"id": 0, "label": "A", "fx": 0.13, "fy": 0.25},
    {"id": 1, "label": "B", "fx": 0.50, "fy": 0.18},
    {"id": 2, "label": "C", "fx": 0.87, "fy": 0.25},
    {"id": 3, "label": "D", "fx": 0.25, "fy": 0.75},
    {"id": 4, "label": "E", "fx": 0.75, "fy": 0.75},
]

spawn_point = {"fx": 0.50, "fy": 0.50}

# ------------------------------
# ROADS (GRAPH EDGES)
# ------------------------------
edges = [
    (0, 1),   # A-B
    (1, 2),   # B-C
    (0, 3),   # A-D
    (3, 4),   # D-E
    (1, 4)    # B-E
]

adj = {i: [] for i in range(len(nodes))}
for a, b in edges:
    adj[a].append(b)
    adj[b].append(a)

# ------------------------------
# WORLD / CAMERA
# ------------------------------
camera_zoom = 1.0
camera_offset = [0.0, 0.0]
dragging = False

def get_world_pos(nid):
    n = nodes[nid]
    return n["fx"] * BASE_W, n["fy"] * BASE_H

def distance(a, b):
    ax, ay = get_world_pos(a)
    bx, by = get_world_pos(b)
    return math.dist((ax, ay), (bx, by))

def world_to_screen(wx, wy):
    return int(wx * camera_zoom + camera_offset[0]), int(wy * camera_zoom + camera_offset[1])

# ------------------------------
# TRAFFIC SYSTEM
# ------------------------------
BOX_BG = (255, 215, 0)
BOX_BORDER = (0, 0, 0)
BOX_TEXT = (0, 0, 0)

class IntersectionSim:
    def __init__(self, nid):
        self.nid = nid
        self.neighbors = adj[nid][:]
        self.traffic = {}
        self.capacities = {}

        for nb in self.neighbors:
            self.traffic[nb] = {
                "car": random.randint(5, 12),
                "bike": random.randint(5, 15),
                "bus": random.randint(0, 2),
            }
            self.capacities[nb] = random.randint(15, 40)

        self.busyness = random.uniform(0.5, 1.5)
        self.order = self.neighbors[:]
        self.green_index = 0
        self.green_neighbor = self.order[0] if self.order else None
        self.green_timer = 0

        total = self.total_vehicles(self.green_neighbor)
        self.current_green_duration = self.calc_green_duration(total)

        self.spawn_timer = 0
        self.discharge_timer = 0
        self.discharge_interval = 600

    def total_vehicles(self, nb):
        if nb is None or nb not in self.traffic:
            return 0
        d = self.traffic[nb]
        return d["car"] + d["bike"] + d["bus"]

    @staticmethod
    def calc_green_duration(total_vehicles):
        duration = total_vehicles * 1000
        if total_vehicles >= 20:
            return 30000
        return max(10000, min(30000, duration))

    def update(self, dt_ms):

        if not self.order:
            return

        self.green_timer += dt_ms

        # Spawn vehicles at red directions
        self.spawn_timer += dt_ms
        if self.spawn_timer >= 1000:
            self.spawn_timer = 0
            for nb in self.order:
                if nb == self.green_neighbor:
                    continue

                cap = self.capacities[nb]
                side = self.traffic[nb]

                if random.random() < (0.15 * self.busyness):
                    side["car"] = min(cap, side["car"] + 1)
                if random.random() < (0.20 * self.busyness):
                    side["bike"] = min(cap, side["bike"] + 1)
                if random.random() < (0.05 * self.busyness):
                    side["bus"] = min(cap, side["bus"] + 1)

        # Discharge vehicles on green
        self.discharge_timer += dt_ms
        if self.discharge_timer >= self.discharge_interval:
            self.discharge_timer = 0
            self.discharge_interval = random.randint(500, 900)

            nb = self.green_neighbor
            if nb is not None:
                side = self.traffic[nb]
                options = []

                if side["car"] > 0: options.append("car")
                if side["bike"] > 0: options.append("bike")
                if side["bus"] > 0: options.append("bus")

                if options:
                    c = random.choice(options)
                    side[c] = max(0, side[c] - 1)

        # Change signal
        if self.green_timer >= self.current_green_duration:
            self.green_timer = 0
            self.green_index = (self.green_index + 1) % len(self.order)
            self.green_neighbor = self.order[self.green_index]

            total = self.total_vehicles(self.green_neighbor)
            self.current_green_duration = self.calc_green_duration(total)

intersection_sims = [IntersectionSim(i) for i in range(len(nodes))]

# ------------------------------
# DRAW FUNCTIONS
# ------------------------------
def draw_background():
    screen.fill((15, 30, 55))

def draw_roads():
    ROAD_WIDTH = 60
    BORDER = 8
    EXTEND = 4000

    for a, b in edges:
        ax, ay = get_world_pos(a)
        bx, by = get_world_pos(b)

        dx = bx - ax
        dy = by - ay
        length = math.hypot(dx, dy)
        if length == 0:
            continue

        dx /= length
        dy /= length

        wx1 = ax - dx * EXTEND
        wy1 = ay - dy * EXTEND
        wx2 = bx + dx * EXTEND
        wy2 = by + dy * EXTEND

        sx1, sy1 = world_to_screen(wx1, wy1)
        sx2, sy2 = world_to_screen(wx2, wy2)

        pygame.draw.line(screen, (240, 240, 240),
                         (sx1, sy1), (sx2, sy2), ROAD_WIDTH + BORDER)
        pygame.draw.line(screen, (32, 32, 32),
                         (sx1, sy1), (sx2, sy2), ROAD_WIDTH)

        line_len = math.hypot(sx2 - sx1, sy2 - sy1)
        if line_len == 0:
            continue

        seg = max(1, int(line_len // 40))
        for i in range(seg):
            t1 = i / seg
            t2 = t1 + 0.5 / seg
            dx1 = sx1 + (sx2 - sx1) * t1
            dy1 = sy1 + (sy2 - sy1) * t1
            dx2 = sx1 + (sx2 - sx1) * t2
            dy2 = sy1 + (sy2 - sy1) * t2
            pygame.draw.line(screen, (245, 208, 66),
                             (dx1, dy1), (dx2, dy2), 6)

def draw_nodes():
    for n in nodes:
        wx, wy = get_world_pos(n["id"])
        x, y = world_to_screen(wx, wy)
        pygame.draw.circle(screen, (12, 190, 120), (x, y), 22)
        pygame.draw.circle(screen, (0, 40, 25), (x, y), 18)
        pygame.draw.circle(screen, (70, 255, 170), (x, y), 14)
        screen.blit(FONT.render(n["label"], True, (0, 0, 0)), (x - 8, y - 10))


def draw_info_box(surface, text, wx, wy):
    sx, sy = world_to_screen(wx, wy)
    padding = 8
    lines = text.split("\n")
    rendered = [SMALL.render(line, True, BOX_TEXT) for line in lines]
    w = max((r.get_width() for r in rendered), default=0)
    h = sum(r.get_height() for r in rendered) + (len(lines) - 1) * 4
    rect = pygame.Rect(sx - w // 2 - padding, sy - h // 2 - padding,
                       w + 2 * padding, h + 2 * padding)

    pygame.draw.rect(surface, BOX_BG, rect)
    pygame.draw.rect(surface, BOX_BORDER, rect, 2)

    y = rect.y + padding
    for r in rendered:
        surface.blit(r, (rect.x + padding, y))
        y += r.get_height() + 4


# ------------------------------
# REMOVE DOWN BOX FOR C (id=2)
# ------------------------------
def draw_all_info_boxes():

    DEFAULT_DIST = 70
    ROAD_ALIGN_THRESHOLD_DEG = 40
    MIN_GAP = 6
    RELAX_PASSES = 12
    MAX_PUSH = 80

    node_world = {i: get_world_pos(i) for i in range(len(nodes))}
    node_screen = {i: world_to_screen(*node_world[i]) for i in range(len(nodes))}

    CARDINALS = [
        ("up",    (0, -1), 90),
        ("right", (1, 0), 0),
        ("down",  (0, 1), 270),
        ("left",  (-1, 0), 180),
    ]

    boxes = []

    for nid, sim in enumerate(intersection_sims):
        xw, yw = node_world[nid]

        road_dirs = []
        for nb in sim.neighbors:
            x2, y2 = node_world[nb]
            dx = x2 - xw
            dy = y2 - yw
            d = math.hypot(dx, dy)
            if d != 0:
                road_dirs.append(((dx / d, dy / d), nb))

        for name, (cx, cy), _ in CARDINALS:

            if nid == 2 and name == "down":
                continue

            chosen_dir = (cx, cy)
            aligned_nb = None
            best_dot = -1

            for (rdx, rdy), nb in road_dirs:
                dot = rdx * cx + rdy * cy
                if dot > best_dot:
                    best_dot = dot
                    best_rd = (rdx, rdy, nb)

            if best_dot > math.cos(math.radians(ROAD_ALIGN_THRESHOLD_DEG)):
                chosen_dir = (best_rd[0], best_rd[1])
                aligned_nb = best_rd[2]

            world_dx = chosen_dir[0] * (DEFAULT_DIST / camera_zoom)
            world_dy = chosen_dir[1] * (DEFAULT_DIST / camera_zoom)

            wx = xw + world_dx
            wy = yw + world_dy

            sx, sy = world_to_screen(wx, wy)

            if aligned_nb is not None:
                d = sim.traffic.get(aligned_nb)
                green = nodes[sim.green_neighbor]["label"] if sim.green_neighbor is not None else "-"
                text = f"To {nodes[aligned_nb]['label']}\nGreen→ {green}\nC:{d['car']} B:{d['bike']} Bus:{d['bus']}"
            else:
                text = f"{name.upper()}\nGreen→ -\nC:0 B:0 Bus:0"

            lines = text.split("\n")
            rendered = [SMALL.render(l, True, BOX_TEXT) for l in lines]
            w = max(r.get_width() for r in rendered) + 16
            h = sum(r.get_height() for r in rendered) + (len(lines) - 1) * 4 + 16
            rect = pygame.Rect(sx - w // 2, sy - h // 2, w, h)

            boxes.append({
                "nid": nid,
                "sx": float(sx),
                "sy": float(sy),
                "wx": wx,
                "wy": wy,
                "rect": rect,
                "text": text,
            })

    # RELAXATION (same logic)
    for nid in range(len(nodes)):
        group = [b for b in boxes if b["nid"] == nid]

        for _ in range(RELAX_PASSES):
            moved = False
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    ri = group[i]["rect"]
                    rj = group[j]["rect"]

                    if ri.colliderect(rj):
                        cx_i, cy_i = ri.center
                        cx_j, cy_j = rj.center
                        vx, vy = cx_i - cx_j, cy_i - cy_j
                        norm = math.hypot(vx, vy) or 1
                        ux, uy = vx / norm, vy / norm
                        overlap = ri.clip(rj)
                        push = min(max(overlap.width, overlap.height) / 2 + MIN_GAP, MAX_PUSH)
                        dx = ux * push
                        dy = uy * push

                        ri.x += dx
                        ri.y += dy
                        rj.x -= dx
                        rj.y -= dy

                        group[i]["sx"], group[i]["sy"] = ri.center
                        group[j]["sx"], group[j]["sy"] = rj.center

                        group[i]["wx"] = (group[i]["sx"] - camera_offset[0]) / camera_zoom
                        group[i]["wy"] = (group[i]["sy"] - camera_offset[1]) / camera_zoom
                        group[j]["wx"] = (group[j]["sx"] - camera_offset[0]) / camera_zoom
                        group[j]["wy"] = (group[j]["sy"] - camera_offset[1]) / camera_zoom

                        moved = True
            if not moved:
                break

    for b in boxes:
        draw_info_box(screen, b["text"], b["wx"], b["wy"])


# ------------------------------
# PATHFINDING
# ------------------------------
def shortest_path(start, end):
    dist = {i: float("inf") for i in adj}
    prev = {i: None for i in adj}
    visited = {i: False for i in adj}
    dist[start] = 0

    for _ in range(len(nodes)):
        u = None
        best = float("inf")
        for v in dist:
            if not visited[v] and dist[v] < best:
                u = v
                best = dist[v]

        if u is None:
            break

        visited[u] = True
        for nb in adj[u]:
            alt = dist[u] + distance(u, nb)
            if alt < dist[nb]:
                dist[nb] = alt
                prev[nb] = u

    if dist[end] == float("inf"):
        return None

    path = []
    cur = end
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return list(reversed(path))


# ------------------------------
# USER INPUT
# ------------------------------
print("\nAvailable Intersections:")
print("0=A, 1=B, 2=C, 3=D, 4=E\n")

def get_valid_index(prompt):
    while True:
        try:
            val = int(input(prompt))
            if 0 <= val < len(nodes):
                return val
            print("Enter valid number 0–4.")
        except:
            print("Invalid input.")

source = get_valid_index("SOURCE (0-4): ")
dest = get_valid_index("DEST (0-4): ")

path = shortest_path(source, dest)
print("Shortest Path:", path)

if path is None:
    path = []

# ------------------------------
# AMBULANCE SYSTEM
# ------------------------------
ambulance = {
    "active": False,
    "path": path,
    "seg_idx": 0,
    "wx": None,
    "wy": None,
    "speed": 30.0,
    "last_logged": None
}

# Start ambulance
if len(path) >= 2:
    ambulance["active"] = True
    ambulance["seg_idx"] = 0
    ambulance["wx"], ambulance["wy"] = get_world_pos(path[0])
    # Log the starting node immediately
    if ambulance["last_logged"] != ambulance["seg_idx"]:
        print("Passed from:", nodes[path[0]]["label"])
        ambulance["last_logged"] = ambulance["seg_idx"]
else:
    ambulance["active"] = False


def update_ambulance(dt):

    if not ambulance["active"]:
        return

    if len(ambulance["path"]) < 2:
        ambulance["active"] = False
        return

    move_left = ambulance["speed"] * (dt / 1000.0)

    while move_left > 0 and ambulance["active"]:
        si = ambulance["seg_idx"]
        if si >= len(ambulance["path"]) - 1:
            # reached destination
            dest_label = nodes[ambulance["path"][-1]]["label"]
            print("Ambulance reached destination:", dest_label)
            ambulance["active"] = False
            break

        a_id = ambulance["path"][si]
        b_id = ambulance["path"][si + 1]
        ax, ay = get_world_pos(a_id)
        bx, by = get_world_pos(b_id)

        # If ambulance position is None (shouldn't be), snap to a_id
        if ambulance["wx"] is None:
            ambulance["wx"], ambulance["wy"] = ax, ay

        tx = bx - ambulance["wx"]
        ty = by - ambulance["wy"]
        seg_dist = math.hypot(tx, ty)

        if seg_dist < 1e-6:
            # arrived exactly at b_id
            ambulance["wx"], ambulance["wy"] = bx, by
            ambulance["seg_idx"] += 1
            # log arrival at this new node (if not logged)
            if ambulance.get("last_logged") != ambulance["seg_idx"]:
                nid = ambulance["path"][ambulance["seg_idx"]]
                print("Passed from:", nodes[nid]["label"])
                ambulance["last_logged"] = ambulance["seg_idx"]
            # if that was final node, will be handled at top of loop next iteration
            continue

        ux = tx / seg_dist
        uy = ty / seg_dist

        if move_left >= seg_dist:
            # reach end of this segment (b_id)
            ambulance["wx"], ambulance["wy"] = bx, by
            move_left -= seg_dist
            ambulance["seg_idx"] += 1
            # log arrival at this node
            if ambulance.get("last_logged") != ambulance["seg_idx"]:
                nid = ambulance["path"][ambulance["seg_idx"]]
                print("Passed from:", nodes[nid]["label"])
                ambulance["last_logged"] = ambulance["seg_idx"]
            # continue loop to use remaining move_left
        else:
            # move partway along segment
            ambulance["wx"] += ux * move_left
            ambulance["wy"] += uy * move_left
            move_left = 0.0


def draw_ambulance():
    if ambulance["wx"] is None:
        return
    sx, sy = world_to_screen(ambulance["wx"], ambulance["wy"])
    # fixed screen radius for visibility
    radius = max(6, int(10))
    pygame.draw.circle(screen, (255, 50, 50), (sx, sy), radius)      # red fill
    pygame.draw.circle(screen, (255, 255, 255), (sx, sy), radius, 2)  # white border


# ------------------------------
# MAIN LOOP
# ------------------------------
clock = pygame.time.Clock()
running = True

while running:

    dt = clock.tick(60)

    for e in pygame.event.get():

        if e.type == pygame.QUIT:
            running = False

        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            running = False

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
            dragging = True
            drag_start = e.pos
            cam_start = camera_offset.copy()

        if e.type == pygame.MOUSEBUTTONUP and e.button == 3:
            dragging = False

        if e.type == pygame.MOUSEMOTION and dragging:
            mx, my = e.pos
            camera_offset[0] = cam_start[0] + (mx - drag_start[0])
            camera_offset[1] = cam_start[1] + (my - drag_start[1])

        if e.type == pygame.MOUSEWHEEL:
            old_zoom = camera_zoom
            camera_zoom *= 1.1 ** e.y
            camera_zoom = max(0.4, min(3.5, camera_zoom))

            mx, my = pygame.mouse.get_pos()
            wx = (mx - camera_offset[0]) / old_zoom
            wy = (my - camera_offset[1]) / old_zoom
            camera_offset[0] = mx - wx * camera_zoom
            camera_offset[1] = my - wy * camera_zoom

    for sim in intersection_sims:
        sim.update(dt)

    update_ambulance(dt)

    draw_background()
    draw_roads()
    draw_nodes()
    draw_all_info_boxes()
    draw_ambulance()

    pygame.display.update()

pygame.quit()
sys.exit()
