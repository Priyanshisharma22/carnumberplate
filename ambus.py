import folium
import os
import time
import math
import osmnx as ox
import networkx as nx
from folium.features import DivIcon
import webbrowser
import random
import pickle
import requests

# --------------------------------------------------
# GEOCODING: Place Name → Coordinates
# --------------------------------------------------
def geocode_place(place):
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={place}"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    data = r.json()

    if len(data) == 0:
        print(f"⚠ Could not find: {place}")
        return None, None, place

    lat = float(data[0]["lat"])
    lon = float(data[0]["lon"])
    name = data[0]["display_name"]

    return lat, lon, name


# --------------------------------------------------
# UTIL: Haversine distance
# --------------------------------------------------
def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return 2 * R * math.asin(math.sqrt(a))


# --------------------------------------------------
# 1) DELHI BASE MAP
# --------------------------------------------------
delhi_center = [28.6139, 77.2090]
m = folium.Map(location=delhi_center, zoom_start=12, control_scale=True)
print("✔ Delhi basemap loaded.\n")


# --------------------------------------------------
# 2) USER INPUT — Place Names (NOT Coordinates)
# --------------------------------------------------
src_text = input("Enter Source Place Name: ")
dst_text = input("Enter Destination Place Name: ")

sx, sy, src_name = geocode_place(src_text)
dx, dy, dst_name = geocode_place(dst_text)

print("\n✔ Geocoded Results:")
print("Source:", src_name, "→", (sx, sy))
print("Destination:", dst_name, "→", (dx, dy), "\n")


# --------------------------------------------------
# 3) LOAD OR DOWNLOAD DELHI NETWORK (Cached)
# --------------------------------------------------
CACHE_FILE = "delhi_road_cache.pkl"

if os.path.exists(CACHE_FILE):
    print("✔ Loading Delhi road network from cache...")
    with open(CACHE_FILE, "rb") as f:
        G = pickle.load(f)
    print("✔ Loaded.\n")

else:
    print("⚠ Downloading Delhi NCR road network (one-time)...")

    north = 29.0
    south = 28.3
    east = 77.5
    west = 76.7

    G = ox.graph_from_bbox(north, south, east, west, network_type="drive")
    G = ox.utils_graph.get_undirected(G)

    print("✔ Download complete. Saving cache...")
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(G, f)
    print("✔ Saved as delhi_road_cache.pkl\n")


# --------------------------------------------------
# 4) COMPUTE SHORTEST ROUTE
# --------------------------------------------------
print("Finding nearest graph nodes...")
source = ox.distance.nearest_nodes(G, sy, sx)
destination = ox.distance.nearest_nodes(G, dy, dx)

print("Calculating shortest route...")
route = nx.shortest_path(G, source, destination, weight="length")
print("✔ Route computed.\n")

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
# 6) TRAFFIC BOXES
# --------------------------------------------------
boxes = []

for i, node in enumerate(route):
    lat = G.nodes[node]['y']
    lon = G.nodes[node]['x']

    if i < len(route) - 1:
        nxt = route[i + 1]
        ed = G.get_edge_data(node, nxt)
        road_name = ed[list(ed.keys())[0]].get("name", "Unnamed Road") if ed else "Unnamed Road"
    else:
        road_name = "Destination"

    cars = random.randint(8, 26)
    buses = random.randint(3, 18)
    bikes = random.randint(15, 40)

    html = f"""
    <div style="background-color: yellow; border: 2px solid black; padding: 6px; font-size: 12px;">
        <b>Node:</b> {node}<br>
        <b>Road:</b> {road_name}<br>
        <b>Signal:</b> <span id='sig_{node}'>GREEN</span><br>
        <b>Cars:</b> <span id='c_{node}'>{cars}</span><br>
        <b>Buses:</b> <span id='b_{node}'>{buses}</span><br>
        <b>Bikes:</b> <span id='k_{node}'>{bikes}</span><br>

        <script>
        (function(){{
            var state = "GREEN";

            function updateTraffic() {{
                var c = document.getElementById("c_{node}");
                var b = document.getElementById("b_{node}");
                var k = document.getElementById("k_{node}");

                var cv = parseInt(c.innerText);
                var bv = parseInt(b.innerText);
                var kv = parseInt(k.innerText);

                if (state === "RED") {{
                    c.innerText = cv + 2;
                    b.innerText = bv + 1;
                    k.innerText = kv + 3;
                }} else {{
                    c.innerText = Math.max(1, cv - 1);
                    b.innerText = Math.max(1, bv - 1);
                    k.innerText = Math.max(1, kv - 2);
                }}
            }}

            function changeSignal() {{
                var sig = document.getElementById("sig_{node}");
                if (state === "GREEN") {{
                    state = "RED";
                    sig.innerText = "RED";
                    sig.style.background = "red";
                    sig.style.color = "white";
                    setTimeout(changeSignal, 40000);
                }} else {{
                    state = "GREEN";
                    sig.innerText = "GREEN";
                    sig.style.background = "green";
                    sig.style.color = "white";
                    setTimeout(changeSignal, 40000);
                }}
            }}

            setInterval(updateTraffic, 1000);
            changeSignal();

        }})();
        </script>
    </div>
    """

    boxes.append({"lat": lat, "lon": lon, "html": html})


# Add boxes to map
for b in boxes:
    folium.Marker(
        [b["lat"], b["lon"]],
        icon=DivIcon(icon_size=(230, 140), icon_anchor=(0, 0), html=b["html"])
    ).add_to(m)


# --------------------------------------------------
# 7) DRAW ROUTE
# --------------------------------------------------
folium.PolyLine(route_coords, color="red", weight=5).add_to(m)


# --------------------------------------------------
# 8) SOURCE & DESTINATION MARKERS (WITH NAME)
# --------------------------------------------------
folium.Marker(
    [sx, sy],
    tooltip=f"Source:\n{src_name}",
    icon=folium.Icon(color="green", icon="home")
).add_to(m)

folium.Marker(
    [dx, dy],
    tooltip=f"Destination:\n{dst_name}",
    icon=folium.Icon(color="red", icon="flag")
).add_to(m)


# --------------------------------------------------
# 9) MOVING AMBULANCE (ANIMATION)
# --------------------------------------------------
move_js = f"""
<script>
var route = {route_coords};

var ambIcon = L.icon({{
    iconUrl: 'https://cdn-icons-png.flaticon.com/512/2965/2965567.png',
    iconSize: [32, 32]
}});

var amb = null;
var i = 0;

function startAmb() {{
    if (amb === null) {{
        amb = L.marker(route[0], {{icon: ambIcon}}).addTo({m.get_name()});
        move();
    }}
}}

function move() {{
    if (i >= route.length) return;
    amb.setLatLng(route[i]);
    i++;
    setTimeout(move, 700);
}}

document.addEventListener("DOMContentLoaded", startAmb);
</script>
"""

m.get_root().html.add_child(folium.Element(move_js))


# --------------------------------------------------
# 10) SAVE FILE
# --------------------------------------------------
file_path = "delhi_ambulance_route_map.html"
m.save(file_path)
print("\n✔ Map saved! Opening in browser...")
webbrowser.open(file_path)


# --------------------------------------------------
# 11) PRINT ROUTE SEGMENTS
# --------------------------------------------------
print("\nAmbulance Path (Road Names):\n")
for i in range(len(route) - 1):
    u, v = route[i], route[i + 1]
    ed = G.get_edge_data(u, v)
    name = ed[list(ed.keys())[0]].get("name", "Unnamed Road") if ed else "Unnamed Road"
    print(f"{u} → {v} | Road: {name}")
    time.sleep(0.1)
