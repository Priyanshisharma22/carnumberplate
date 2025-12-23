import folium
import osmnx as ox
import networkx as nx
from folium.plugins import AntPath
import webbrowser
import time

# --------------------------------------------------
# 1) INDIA MAP BASE
# --------------------------------------------------
india_center = [22.3511148, 78.6677428]
m = folium.Map(location=india_center, zoom_start=5, control_scale=True)
print("🌍 India basemap loaded.\n")


# --------------------------------------------------
# 2) USER INPUT
# --------------------------------------------------
def get_coordinates(text):
    raw = input(text).replace(",", " ").split()
    return float(raw[0]), float(raw[1])

print("Enter coordinates (Example: 28.6139 77.2090):")
sx, sy = get_coordinates("\nSource (lat lon): ")
dx, dy = get_coordinates("Destination (lat lon): ")

print(f"\n📌 Source: {sx}, {sy}")
print(f"📌 Destination: {dx}, {dy}\n")


# --------------------------------------------------
# 3) BOUNDING BOX FOR ROAD NETWORK
# --------------------------------------------------
north = max(sx, dx) + 0.05
south = min(sx, dx) - 0.05
east = max(sy, dy) + 0.05
west = min(sy, dy) - 0.05

print("📥 Downloading required road network...")
G = ox.graph_from_bbox(north, south, east, west, network_type='drive')
G = ox.utils_graph.get_undirected(G)
print("✔ Road network downloaded!\n")


# --------------------------------------------------
# 4) SHORTEST ROUTE
# --------------------------------------------------
source = ox.distance.nearest_nodes(G, sy, sx)
destination = ox.distance.nearest_nodes(G, dy, dx)

print("🛣 Calculating shortest path...")
route = nx.shortest_path(G, source, destination, weight="length")
print("✔ Shortest route found!\n")

route_coords = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in route]


# --------------------------------------------------
# 5) DRAW MAP (SHOW FIRST)
# --------------------------------------------------
nodes_gdf, edges_gdf = ox.graph_to_gdfs(G)

# full road network
folium.GeoJson(
    edges_gdf.__geo_interface__,
    name="Roads",
    style_function=lambda x: {"color": "#999", "weight": 1}
).add_to(m)

# ANIMATED AMBULANCE PATH
AntPath(
    locations=route_coords,
    color="red",
    weight=6,
    delay=800
).add_to(m)

# Start marker
folium.Marker(
    route_coords[0],
    icon=folium.Icon(color='green', icon='ambulance', prefix='fa'),
    tooltip="Ambulance Start"
).add_to(m)

# End marker
folium.Marker(
    route_coords[-1],
    icon=folium.Icon(color='red', icon='hospital-o', prefix='fa'),
    tooltip="Destination"
).add_to(m)

# SAVE MAP
file_path = "india_ambulance_route_map.html"
m.save(file_path)

print("🎉 Map Created Successfully!")
print("➡ Opening map in browser...\n")

# OPEN MAP FIRST
webbrowser.open(file_path)

# SMALL DELAY TO LET BROWSER OPEN
time.sleep(3)


# --------------------------------------------------
# 6) AFTER MAP OPENS → PRINT PASSED INTERSECTIONS
# --------------------------------------------------
print("🚑 Ambulance Passing Intersections:\n")

for node in route:
    print("➡ Passed:", node)
    time.sleep(0.2)  # Slow printing for effect
