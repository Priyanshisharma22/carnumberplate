import pygame
import osmnx as ox
import networkx as nx
import random
import math
import time
import requests
from io import BytesIO
from PIL import Image

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
WIDTH, HEIGHT = 1200, 800
ROAD_COLOR = (80, 80, 80)
NODE_COLOR = (0, 0, 255)
AMB_COLOR = (255, 0, 0)
BOX_COLOR = (255, 255, 0)
TEXT_COLOR = (0, 0, 0)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Ambulance Route - Zoom & Pan")
font = pygame.font.SysFont("Arial", 14)

# -------------------------------------------------
# INPUT
# -------------------------------------------------
def get_latlon(prompt):
    raw = input(prompt).replace(",", " ").split()
    return float(raw[0]), float(raw[1])

sx, sy = get_latlon("Source (lat lon): ")
dx, dy = get_latlon("Destination (lat lon): ")

# -------------------------------------------------
# REAL MAP TILE (OSM)
# -------------------------------------------------
def download_osm_tile(lat, lon, zoom=14):
    x = int((lon + 180) / 360 * (2 ** zoom))
    y = int(
        (1 - math.log(math.tan(math.radians(lat)) +
         1 / math.cos(math.radians(lat))) / math.pi) / 2 * (2 ** zoom)
    )
    url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
    print("Downloading:", url)
    data = requests.get(url).content
    img = Image.open(BytesIO(data)).resize((WIDTH, HEIGHT))
    return pygame.image.fromstring(img.tobytes(), img.size, img.mode)

bg_map = download_osm_tile((sx + dx) / 2, (sy + dy) / 2)

# -------------------------------------------------
# NETWORK
# -------------------------------------------------
north = max(sx, dx) + 0.02
south = min(sx, dx) - 0.02
east = max(sy, dy) + 0.02
west = min(sy, dy) - 0.02

print("Downloading network...")
G = ox.graph_from_bbox(north, south, east, west, network_type='drive')
G = ox.utils_graph.get_undirected(G)

source = ox.distance.nearest_nodes(G, sy, sx)
dest = ox.distance.nearest_nodes(G, dy, dx)
route = nx.shortest_path(G, source, dest, weight="length")

nodes = ox.graph_to_gdfs(G, edges=False)
min_lat, max_lat = nodes['y'].min(), nodes['y'].max()
min_lon, max_lon = nodes['x'].min(), nodes['x'].max()

def base_transform(lat, lon):
    x = (lon - min_lon) / (max_lon - min_lon) * WIDTH
    y = HEIGHT - (lat - min_lat) / (max_lat - min_lat) * HEIGHT
    return x, y

node_xy = {n: base_transform(G.nodes[n]['y'], G.nodes[n]['x']) for n in G.nodes}

# -------------------------------------------------
# ZOOM + PAN VARIABLES
# -------------------------------------------------
zoom = 1.0
offset_x, offset_y = 0, 0
dragging = False
last_mouse = (0, 0)

def world_to_screen(x, y):
    return int(x * zoom + offset_x), int(y * zoom + offset_y)

def draw_text(text, x, y):
    screen.blit(font.render(text, True, TEXT_COLOR), (x, y))

# -------------------------------------------------
# TRAFFIC + SIGNAL
# -------------------------------------------------
traffic = {}
signal_state = {}
last_signal_change = {}
signal_interval = 40

for n in route:
    traffic[n] = {
        "cars": random.randint(5, 25),
        "buses": random.randint(3, 20),
        "bikes": random.randint(10, 35)
    }
    signal_state[n] = "GREEN"
    last_signal_change[n] = time.time()

# -------------------------------------------------
# AMBULANCE
# -------------------------------------------------
current_idx = 0
speed = 120  # pixels/sec
amb_x, amb_y = node_xy[route[0]]

def move_towards(p1, p2, speed, dt):
    x1, y1 = p1
    x2, y2 = p2
    dist = math.hypot(x2 - x1, y2 - y1)
    if dist < 1:
        return p2, True
    dx = (x2 - x1) / dist * speed * dt
    dy = (y2 - y1) / dist * speed * dt
    return (x1 + dx, y1 + dy), False

clock = pygame.time.Clock()

# -------------------------------------------------
# MAIN LOOP
# -------------------------------------------------
running = True
while running:
    dt = clock.tick(60) / 1000.0

    # EVENTS -------------------------------------------------
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        # Zoom
        if event.type == pygame.MOUSEWHEEL:
            zoom *= 1.1 if event.y > 0 else 0.9

        # Pan start
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3:
                dragging = True
                last_mouse = pygame.mouse.get_pos()

        # Pan end
        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 3:
                dragging = False

    # Panning
    if dragging:
        mx, my = pygame.mouse.get_pos()
        dx = mx - last_mouse[0]
        dy = my - last_mouse[1]
        offset_x += dx
        offset_y += dy
        last_mouse = (mx, my)

    # UPDATE TRAFFIC -----------------------------------
    for n in route:
        if time.time() - last_signal_change[n] >= signal_interval:
            signal_state[n] = "RED" if signal_state[n] == "GREEN" else "GREEN"
            last_signal_change[n] = time.time()

        if signal_state[n] == "RED":
            traffic[n]["cars"] += random.randint(0, 2)
            traffic[n]["buses"] += random.randint(0, 2)
            traffic[n]["bikes"] += random.randint(0, 3)
        else:
            traffic[n]["cars"] = max(1, traffic[n]["cars"] - random.randint(0, 1))
            traffic[n]["buses"] = max(1, traffic[n]["buses"] - random.randint(0, 1))
            traffic[n]["bikes"] = max(1, traffic[n]["bikes"] - random.randint(0, 2))

    # AMBULANCE MOVE -----------------------------------
    if current_idx < len(route) - 1:
        p1 = (amb_x, amb_y)
        p2 = node_xy[route[current_idx + 1]]
        (amb_x, amb_y), reached = move_towards(p1, p2, speed, dt)
        if reached:
            current_idx += 1

            # 🔥 NEW FEATURE: Print node ambulance passed
            print("Ambulance passed node:", route[current_idx])

    # DRAW -------------------------------------------------
    scaled_bg = pygame.transform.scale(bg_map, (int(WIDTH * zoom), int(HEIGHT * zoom)))
    screen.blit(scaled_bg, (offset_x, offset_y))

    # Roads
    for u, v in G.edges():
        x1, y1 = node_xy[u]
        x2, y2 = node_xy[v]
        pygame.draw.line(screen, ROAD_COLOR, world_to_screen(x1, y1), world_to_screen(x2, y2), 2)

    # Nodes + boxes
    for n in route:
        x, y = node_xy[n]
        sx, sy = world_to_screen(x, y)
        pygame.draw.circle(screen, NODE_COLOR, (sx, sy), int(4 * zoom))

        box = pygame.Rect(sx + 10, sy - 10, int(160 * zoom), int(70 * zoom))
        pygame.draw.rect(screen, BOX_COLOR, box)
        pygame.draw.rect(screen, (0, 0, 0), box, 2)

        t = traffic[n]
        sig = signal_state[n]
        info = [
            f"Node: {n}",
            f"Signal: {sig}",
            f"Cars: {t['cars']}",
            f"Buses: {t['buses']}",
            f"Bikes: {t['bikes']}",
        ]

        y_offset = 0
        for line in info:
            draw_text(line, box.x + 5, box.y + y_offset)
            y_offset += 14

    # Ambulance
    ax, ay = world_to_screen(amb_x, amb_y)
    pygame.draw.circle(screen, AMB_COLOR, (ax, ay), int(6 * zoom))

    pygame.display.flip()

pygame.quit()
