"""
Pure-Python (PyGame) version restricted to Delhi NCR (faster, smaller graph).
Features preserved:
 - NCR road network caching (ncr_road_cache.pkl)
 - Nearest nodes + shortest path
 - Route polyline
 - Traffic boxes (cars, buses, bikes) per intersection
 - 40s signal cycle + per-second counters update
 - Single moving ambulance
"""

import os
import time
import math
import random
import pickle
import pygame
import osmnx as ox
import networkx as nx

# --------------------
# Config
# --------------------
CACHE_FILE = "ncr_road_cache.pkl"
WIDTH, HEIGHT = 1400, 900
BG = (250, 250, 250)
ROAD_COL = (140, 140, 140)
ROUTE_COL = (200, 30, 30)
AMB_COL = (0, 60, 200)
BOX_BG = (255, 245, 170)
BOX_BORDER = (40, 40, 40)
FPS = 30
AMB_MOVE_MS = 700        # how often ambulance steps (ms)
TRAFFIC_UPDATE_MS = 1000 # counters update interval (ms)
SIGNAL_CYCLE_MS = 40000  # 40 seconds

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Delhi NCR Ambulance Route - Pure Python")
clock = pygame.time.Clock()
font_small = pygame.font.SysFont(None, 16)
font_tiny = pygame.font.SysFont(None, 14)

# --------------------
# Utilities
# --------------------
def prompt_coords(text):
    raw = input(text).replace(",", " ").split()
    return float(raw[0]), float(raw[1])

def world_to_screen(lat, lon, bounds):
    # bounds: (minx, miny, maxx, maxy) where x=lon, y=lat
    minx, miny, maxx, maxy = bounds
    # protect division by zero
    if maxx - minx == 0 or maxy - miny == 0:
        return WIDTH//2, HEIGHT//2
    x = (lon - minx) / (maxx - minx) * WIDTH
    y = HEIGHT - (lat - miny) / (maxy - miny) * HEIGHT
    return int(x), int(y)

# --------------------
# 1) Map & input
# --------------------
print("Enter coordinates (Example: 28.6139 77.2090)")
sx, sy = prompt_coords("Source (lat lon): ")
dx, dy = prompt_coords("Destination (lat lon): ")
print(f"Source: {sx}, {sy}\nDestination: {dx}, {dy}\n")

# --------------------
# 2) Load/Download NCR network (cache)
# --------------------
if os.path.exists(CACHE_FILE):
    print("✔ Loading Delhi NCR road network from cache...")
    with open(CACHE_FILE, "rb") as f:
        G = pickle.load(f)
    print("✔ Loaded from cache.\n")
else:
    # try National Capital Region first; if it fails, fall back to Delhi
    try_names = ["National Capital Region, India", "Delhi, India"]
    G = None
    for place in try_names:
        try:
            print(f"Attempting to download road network for: {place} ...")
            G = ox.graph_from_place(place, network_type="drive")
            G = ox.utils_graph.get_undirected(G)
            print(f"✔ Downloaded: {place}\n")
            break
        except Exception as e:
            print(f"✖ failed for '{place}': {e}")
            G = None

    if G is None:
        raise RuntimeError("Failed to download road network for NCR/Delhi. Check internet or OSMnx installation.")

    print("Saving cache...")
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(G, f)
    print(f"✔ Cache saved as {CACHE_FILE}\n")

# --------------------
# 3) Shortest path
# --------------------
print("Finding nearest road nodes...")
src_node = ox.distance.nearest_nodes(G, sy, sx)
dst_node = ox.distance.nearest_nodes(G, dy, dx)

print("Calculating shortest path...")
route = nx.shortest_path(G, src_node, dst_node, weight="length")
route_coords = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in route]
print("✔ Shortest path computed.\n")

# Print path roads (like original)
print("Ambulance Path Segments:\n")
for i in range(len(route)-1):
    u, v = route[i], route[i+1]
    ed = G.get_edge_data(u, v)
    name = "Unnamed Road"
    if ed:
        first = list(ed.keys())[0]
        name = ed[first].get("name", "Unnamed Road")
    print(f"{u} → {v} | Road: {name}")
    time.sleep(0.05)

# --------------------
# 4) Prepare Geo data (draw only nearby roads for speed)
# --------------------
nodes_gdf, edges_gdf = ox.graph_to_gdfs(G)
# compute route bbox and expand margin
lats = [lat for lat, lon in route_coords]
lons = [lon for lat, lon in route_coords]
min_lat, max_lat = min(lats), max(lats)
min_lon, max_lon = min(lons), max(lons)
lat_margin = (max_lat - min_lat) * 1.2 + 0.01
lon_margin = (max_lon - min_lon) * 1.2 + 0.01
bbox_minx = min_lon - lon_margin
bbox_maxx = max_lon + lon_margin
bbox_miny = min_lat - lat_margin
bbox_maxy = max_lat + lat_margin
bounds = (bbox_minx, bbox_miny, bbox_maxx, bbox_maxy)

# Filter edges to those that intersect expanded bbox for performance
def edge_in_bbox(row):
    minx, miny, maxx, maxy = row.geometry.bounds
    return not (maxx < bbox_minx or minx > bbox_maxx or maxy < bbox_miny or miny > bbox_maxy)

edges_near = edges_gdf[edges_gdf.apply(edge_in_bbox, axis=1)]

# --------------------
# 5) Traffic boxes (one per route node)
# --------------------
class TrafficBox:
    def __init__(self, node, next_name):
        self.node = node
        self.lat = G.nodes[node]['y']
        self.lon = G.nodes[node]['x']
        self.next_name = next_name
        self.signal = "GREEN"
        self.last_switch = time.time()
        self.cars = random.randint(5, 25)
        self.buses = random.randint(3, 20)
        self.bikes = random.randint(10, 35)

    def update_counters(self, dt_ms):
        # Signal cycle handled separately by timer; update counters at second intervals
        if self.signal == "RED":
            self.cars += 2
            self.buses += 1
            self.bikes += 3
        else:
            self.cars = max(1, self.cars - 1)
            self.buses = max(1, self.buses - 1)
            self.bikes = max(1, self.bikes - 2)

    def toggle_signal(self):
        self.signal = "RED" if self.signal == "GREEN" else "GREEN"
        self.last_switch = time.time()

# get road_name for each node (next on route)
boxes = []
for i, node in enumerate(route):
    if i < len(route)-1:
        nxt = route[i+1]
        ed = G.get_edge_data(node, nxt)
        road_name = "Unnamed Road"
        if ed:
            road_name = ed[list(ed.keys())[0]].get("name", "Unnamed Road")
    else:
        road_name = "Destination"
    boxes.append(TrafficBox(node, road_name))

# mapping node -> TrafficBox
tb_map = {tb.node: tb for tb in boxes}

# --------------------
# 6) Timers for ambulance and traffic updates
# --------------------
AMB_EVENT = pygame.USEREVENT + 1
TRAFFIC_EVENT = pygame.USEREVENT + 2
SIGNAL_EVENT = pygame.USEREVENT + 3
pygame.time.set_timer(AMB_EVENT, AMB_MOVE_MS)
pygame.time.set_timer(TRAFFIC_EVENT, TRAFFIC_UPDATE_MS)
pygame.time.set_timer(SIGNAL_EVENT, SIGNAL_CYCLE_MS)

# --------------------
# 7) Run main loop
# --------------------
amb_idx = 0
running = True

# Precompute route screen points
route_screen = [world_to_screen(lat, lon, bounds) for lat, lon in route_coords]

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == AMB_EVENT:
            if amb_idx < len(route_screen) - 1:
                amb_idx += 1

        if event.type == TRAFFIC_EVENT:
            # update counters
            for tb in boxes:
                tb.update_counters(TRAFFIC_UPDATE_MS)

        if event.type == SIGNAL_EVENT:
            # toggle all signals every 40 seconds (same as original per-intersection cycle)
            for tb in boxes:
                tb.toggle_signal()

    # draw background
    screen.fill(BG)

    # draw roads (filtered)
    for _, row in edges_near.iterrows():
        coords = list(row.geometry.coords)
        if len(coords) < 2:
            continue
        pts = [world_to_screen(c[1], c[0], bounds) for c in coords]
        pygame.draw.lines(screen, ROAD_COL, False, pts, 1)

    # draw route polyline
    if len(route_screen) >= 2:
        pygame.draw.lines(screen, ROUTE_COL, False, route_screen, 4)

    # draw ambulance
    ax, ay = route_screen[amb_idx]
    pygame.draw.circle(screen, AMB_COL, (ax, ay), 7)

    # draw traffic boxes (for route nodes)
    for tb in boxes:
        x, y = world_to_screen(tb.lat, tb.lon, bounds)
        # offset so boxes don't sit directly on the marker (keeps them visible)
        bx, by = x + 8, y - 36
        w, h = 160, 72
        # background
        pygame.draw.rect(screen, BOX_BG, (bx, by, w, h))
        pygame.draw.rect(screen, BOX_BORDER, (bx, by, w, h), 2)
        # text lines
        screen.blit(font_small.render(f"Node: {tb.node}", True, (0, 0, 0)), (bx + 6, by + 3))
        screen.blit(font_tiny.render(f"Next: {tb.next_name}", True, (0, 0, 0)), (bx + 6, by + 20))
        # Signal color/text
        sig_color = (200, 0, 0) if tb.signal == "RED" else (0, 120, 0)
        screen.blit(font_small.render(f"Signal: {tb.signal}", True, sig_color), (bx + 6, by + 36))
        # counters
        screen.blit(font_tiny.render(f"Cars: {tb.cars}", True, (0, 0, 0)), (bx + 6, by + 52))
        screen.blit(font_tiny.render(f"Buses: {tb.buses}", True, (0, 0, 0)), (bx + 70, by + 52))
        screen.blit(font_tiny.render(f"Bikes: {tb.bikes}", True, (0, 0, 0)), (bx + 120, by + 52))

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
