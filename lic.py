import folium
import os
import time
import math
import osmnx as ox
import networkx as nx
from folium.features import DivIcon
from folium.plugins import AntPath
import webbrowser
import random

# --------------------------------------------------
# UTIL: meters <-> degrees conversion at given latitude
# --------------------------------------------------
def meters_to_deg_lat(m):
    return m / 111320.0

def meters_to_deg_lon(m, lat_deg):
    return m / (111320.0 * math.cos(math.radians(lat_deg)) or 1e-6)

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return 2*R*math.asin(math.sqrt(a))

# --------------------------------------------------
# 1) INDIA MAP BASE
# --------------------------------------------------
india_center = [22.3511148, 78.6677428]
m = folium.Map(location=india_center, zoom_start=12, control_scale=True)
print("India basemap loaded.\n")

# --------------------------------------------------
# 2) USER INPUT
# --------------------------------------------------
def get_coordinates(text):
    raw = input(text).replace(",", " ").split()
    return float(raw[0]), float(raw[1])

print("Enter coordinates (Example: 28.6139 77.2090):")
sx, sy = get_coordinates("\nSource (lat lon): ")
dx, dy = get_coordinates("Destination (lat lon): ")

print(f"\nSource: {sx}, {sy}")
print(f"Destination: {dx}, {dy}\n")

# --------------------------------------------------
# 3) BOUNDING BOX + CACHE
# --------------------------------------------------
north = max(sx, dx) + 0.05
south = min(sx, dx) - 0.05
east = max(sy, dy) + 0.05
west = min(sy, dy) - 0.05

cache_file = f"road_cache_{round(north,3)}_{round(south,3)}_{round(east,3)}_{round(west,3)}.pkl"

if os.path.exists(cache_file):
    import pickle
    print("Loading road network from cache...")
    with open(cache_file, "rb") as f:
        G = pickle.load(f)
    print("✔ Loaded from cache.\n")
else:
    print("Downloading required road network...")
    G = ox.graph_from_bbox(north, south, east, west, network_type='drive')
    G = ox.utils_graph.get_undirected(G)
    print("Road network downloaded!\n")
    try:
        import pickle
        with open(cache_file, "wb") as f:
            pickle.dump(G, f)
        print("Saved network cache.\n")
    except:
        pass

# --------------------------------------------------
# 4) SHORTEST ROUTE
# --------------------------------------------------
source = ox.distance.nearest_nodes(G, sy, sx)
destination = ox.distance.nearest_nodes(G, dy, dx)

print("Calculating shortest path...")
route = nx.shortest_path(G, source, destination, weight="length")
print("Shortest path found!\n")

route_coords = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in route]

# --------------------------------------------------
# 5) DRAW ROAD NETWORK
# --------------------------------------------------
nodes_gdf, edges_gdf = ox.graph_to_gdfs(G)

folium.GeoJson(
    edges_gdf.__geo_interface__,
    name="Roads",
    style_function=lambda x: {"color": "#999", "weight": 1}
).add_to(m)

# --------------------------------------------------
# 6) INTERSECTIONS + TRAFFIC BOXES
# --------------------------------------------------
boxes = []

for i, node in enumerate(route):

    lat = G.nodes[node]['y']
    lon = G.nodes[node]['x']

    if i < len(route)-1:
        nxt = route[i+1]
        ed = G.get_edge_data(node, nxt)
        if ed:
            first = list(ed.keys())[0]
            road_name = ed[first].get("name", "Unnamed Road")
        else:
            road_name = "Unnamed Road"
    else:
        road_name = "Destination"

    # VEHICLE COUNTS (non-zero & different)
    cars = random.randint(5, 25)
    buses = random.randint(3, 20)
    bikes = random.randint(10, 35)

    if cars == buses: buses += 1
    if buses == bikes: bikes += 1
    if cars == bikes: cars += 1

    # ------------------------------
    # HTML + JS (40-sec signals)
    # ------------------------------
    html = f"""
    <div style="
        background-color: yellow;
        border: 2px solid black;
        padding: 6px;
        font-size: 12px;
        white-space: nowrap;
        max-width: 250px;">

        <b>Intersection:</b> {node}<br>
        <b>Next:</b> {road_name}<br>
        <b>Signal:</b> <span id='signal_{node}' style="padding:2px;">GREEN</span><br>

        <b>Cars:</b> <span id='cars_{node}'>{cars}</span><br>
        <b>Buses:</b> <span id='buses_{node}'>{buses}</span><br>
        <b>Bikes:</b> <span id='bikes_{node}'>{bikes}</span><br>

        <script>
        (function() {{
            var id = "{node}";

            var sig = document.getElementById("signal_" + id);
            var cEl = document.getElementById("cars_" + id);
            var bEl = document.getElementById("buses_" + id);
            var kEl = document.getElementById("bikes_" + id);

            var state = "GREEN";

            function updateTraffic() {{
                var cars = parseInt(cEl.innerText) || 1;
                var buses = parseInt(bEl.innerText) || 1;
                var bikes = parseInt(kEl.innerText) || 1;

                if (state === "RED") {{
                    cars += 1 + Math.floor(Math.random() * 3);
                    buses += 1 + Math.floor(Math.random() * 3);
                    bikes += 1 + Math.floor(Math.random() * 4);
                }} else {{
                    cars = Math.max(1, cars - Math.floor(Math.random() * 2));
                    buses = Math.max(1, buses - Math.floor(Math.random() * 2));
                    bikes = Math.max(1, bikes - Math.floor(Math.random() * 3));
                }}

                if (cars === buses) buses += 1;
                if (buses === bikes) bikes += 1;
                if (cars === bikes) cars += 1;

                cEl.innerText = cars;
                bEl.innerText = buses;
                kEl.innerText = bikes;
            }}

            function setSignal() {{
                if (state === "RED") {{
                    sig.innerText = "RED";
                    sig.style.background = "red";
                    sig.style.color = "white";
                }} else {{
                    sig.innerText = "GREEN";
                    sig.style.background = "green";
                    sig.style.color = "white";
                }}
            }}

            // FIXED 40 SEC RED + 40 SEC GREEN
            function adaptiveCycle() {{
                var greenTime = 40000;
                var redTime = 40000;

                if (state === "GREEN") {{
                    setTimeout(() => {{
                        state = "RED";
                        setSignal();
                        adaptiveCycle();
                    }}, greenTime);
                }} else {{
                    setTimeout(() => {{
                        state = "GREEN";
                        setSignal();
                        adaptiveCycle();
                    }}, redTime);
                }}
            }}

            setInterval(updateTraffic, 1000);
            setSignal();
            adaptiveCycle();

        }})();
        </script>
    </div>
    """

    boxes.append({"node": node, "lat": lat, "lon": lon, "html": html})

# --------------------------------------------------
# RELAX LABELS (unchanged)
# --------------------------------------------------
min_dist_m = 30.0
max_passes = 40
repel_strength = 0.5

for _ in range(max_passes):
    moved = False
    for i in range(len(boxes)):
        for j in range(i+1, len(boxes)):
            bi, bj = boxes[i], boxes[j]
            d = haversine_m(bi["lat"], bi["lon"], bj["lat"], bj["lon"])
            if d < min_dist_m and d > 0.1:
                mean_lat = (bi["lat"] + bj["lat"]) / 2
                m_per_lon = 111320 * math.cos(math.radians(mean_lat))

                dy = (bi["lat"] - bj["lat"]) * 111320
                dx = (bi["lon"] - bj["lon"]) * m_per_lon
                norm = math.hypot(dx, dy) or 1

                ux, uy = dx/norm, dy/norm
                push = (min_dist_m - d) * 0.5

                bi["lat"] += (uy * push / 111320) * repel_strength
                bi["lon"] += (ux * push / m_per_lon) * repel_strength
                bj["lat"] -= (uy * push / 111320) * repel_strength
                bj["lon"] -= (ux * push / m_per_lon) * repel_strength

                moved = True
    if not moved:
        break

# --------------------------------------------------
# PLACE BOXES
# --------------------------------------------------
for b in boxes:
    folium.map.Marker(
        [b["lat"], b["lon"]],
        icon=DivIcon(icon_size=(240, 140), icon_anchor=(0, 0), html=b["html"])
    ).add_to(m)

# --------------------------------------------------
# AMBULANCE PATH
# --------------------------------------------------
AntPath(route_coords, color="red", weight=6, delay=800).add_to(m)

folium.Marker(
    route_coords[0],
    icon=folium.Icon(color="green", icon="ambulance", prefix="fa"),
    tooltip="Ambulance Start"
).add_to(m)

folium.Marker(
    route_coords[-1],
    icon=folium.Icon(color="red", icon="hospital-o", prefix="fa"),
    tooltip="Destination"
).add_to(m)

# --------------------------------------------------
# SAVE MAP
# --------------------------------------------------
file_path = "india_ambulance_route_map.html"
m.save(file_path)
print("Map Created Successfully!")
webbrowser.open(file_path)

# --------------------------------------------------
# PRINT PATH INFO
# --------------------------------------------------
print("\nAmbulance Passing Road Segments:\n")
for i in range(len(route) - 1):
    u, v = route[i], route[i+1]
    ed = G.get_edge_data(u, v)
    name = "Unnamed Road"
    if ed:
        name = ed[list(ed.keys())[0]].get("name", "Unnamed Road")
    print(f"{u} → {v} | Road: {name}")
    time.sleep(0.25)
