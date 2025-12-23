"""
traffic_sim.py

Pygame port of the Advanced Traffic Simulation (from provided HTML/JS).

Controls:
- Left click: depending on tool:
    * Draw mode: click to add point; press Enter to finish road (double-click detection is less reliable in pygame)
    * Select mode: click to select road/intersection
    * Intersection mode: click to add an intersection
    * Delete mode: click to delete selected object
- Middle mouse (or M key + drag): pan
- Arrow keys: pan
- Mouse wheel or +/- keys: zoom in/out
- Space: pause / resume
- R: reset simulation vehicles
- A: add random vehicles
- F: fit view (center/zoom)
- G: toggle snap-to-grid
- 1/2/3: switch tools (1: select, 2: draw road, 3: intersection, 4: delete)
- Enter: finish road when drawing
"""

import pygame
import sys
import math
import time
import random
from collections import deque

pygame.init()
pygame.font.init()

# ---------- Config ----------
PX_PER_METER = 10
PX_PER_KM = PX_PER_METER * 1000
WIDTH, HEIGHT = 1000, 700
ROAD_WIDTH_DEFAULT = 6  # meters
INTER_SIZE = 120  # pixels (visual size)
INTER_HALF = INTER_SIZE / 2
SAFE_GAP = 10 * PX_PER_METER
STOP_BUFFER = 10 * PX_PER_METER
LANE_OFFSET = ROAD_WIDTH_DEFAULT * PX_PER_METER / 4
SPAWN_INTERVAL = 1.5
GRID_SIZE = 5  # meters for snapping

# Colors
CLR_BG = (52,73,94)
CLR_ROAD = (44,62,80)
CLR_INTER = (192,57,43)
CLR_GRID = (255,255,255, 25)
CLR_TEXT = (255,255,255)
CLR_SELECTED = (52,152,219)
CLR_HOVER = (231,76,60)
CLR_BIKE = (30,144,255)
CLR_CAR = (34,139,34)
CLR_BUS = (128,0,128)

FONT = pygame.font.SysFont('Arial', 16)

# ---------- Utilities ----------
def distance(a,b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def line_segment_intersection(p1,p2,p3,p4):
    # p1..p4 are tuples (x,y)
    x1,y1 = p1; x2,y2 = p2; x3,y3 = p3; x4,y4 = p4
    denom = (y4-y3)*(x2-x1) - (x4-x3)*(y2-y1)
    if denom == 0:
        return None
    ua = ((x4-x3)*(y1-y3) - (y4-y3)*(x1-x3)) / denom
    ub = ((x2-x1)*(y1-y3) - (y2-y1)*(x1-x3)) / denom
    if 0 <= ua <= 1 and 0 <= ub <= 1:
        x = x1 + ua*(x2-x1)
        y = y1 + ua*(y2-y1)
        return (x,y)
    return None

def point_on_segment(pt, a, b, eps=1.0):
    # check if pt is on segment [a,b]
    return abs(distance(pt,a) + distance(pt,b) - distance(a,b)) < eps

def angle_to_dir(a,b):
    dx = b[0]-a[0]
    dy = b[1]-a[1]
    ang = math.degrees(math.atan2(dy, dx))
    if ang < 0: ang += 360
    # bucket into N,E,S,W (four major directions)
    if ang >= 315 or ang < 45: return 'E'
    if 45 <= ang < 135: return 'S'   # note: screen y positive is down, so 90 is down -> S
    if 135 <= ang < 225: return 'W'
    if 225 <= ang < 315: return 'N'
    return 'E'

# ---------- Data classes ----------
class Road:
    def __init__(self, points, width_m=ROAD_WIDTH_DEFAULT):
        self.points = [tuple(p) for p in points]
        self.width_m = width_m
        self.id = int(time.time()*1000) + random.randint(0,999)
    def segments(self):
        for i in range(len(self.points)-1):
            yield (self.points[i], self.points[i+1])

class Intersection:
    def __init__(self, x,y):
        self.x = x
        self.y = y
        self.id = int(time.time()*1000) + random.randint(0,999)
        self.connectedRoads = []
        self.directions = []  # list of directions (N,E,S,W) that have approaches
        self.phase = 0
        self.timer = 0.0
        self.greenTime = 15.0
    def pos(self):
        return (self.x, self.y)

class Vehicle:
    KIND_SPECS = {
        'bike': {'size':(0.6,2.0), 'speed':15.0, 'color':CLR_BIKE},
        'car' : {'size':(1.8,4.5), 'speed':20.0, 'color':CLR_CAR},
        'bus' : {'size':(2.5,12.0), 'speed':18.0, 'color':CLR_BUS}
    }
    def __init__(self, kind, dir, pos, inter_index, stop_coord, lane_fix):
        self.kind = kind
        self.dir = dir  # 'E','W','N','S'
        self.pos = list(pos)
        self.inter_index = inter_index
        spec = Vehicle.KIND_SPECS[kind]
        self.speed = spec['speed'] * PX_PER_METER
        self.color = spec['color']
        self.size_m = spec['size']
        # oriented sizes (px)
        self.size_px = (self.size_m[0]*PX_PER_METER, self.size_m[1]*PX_PER_METER)
        self.stop_coord = stop_coord
        self.lane_fix = lane_fix
        self.halfLen = (self.size_px[1]/2) if dir in ('E','W') else (self.size_px[1]/2)
    def forward_vec(self):
        if self.dir == 'E': return (1,0)
        if self.dir == 'W': return (-1,0)
        if self.dir == 'S': return (0,1)
        if self.dir == 'N': return (0,-1)
        return (0,0)
    def bbox(self):
        w,h = (self.size_px[1], self.size_px[0]) if self.dir in ('E','W') else (self.size_px[0], self.size_px[1])
        return (self.pos[0]-w/2, self.pos[1]-h/2, w, h)
    def inside_intersection(self, intersections):
        for inter in intersections:
            rect = (inter.x-INTER_HALF, inter.y-INTER_HALF, INTER_SIZE, INTER_SIZE)
            bx,by,w,h = self.bbox()
            if (bx < rect[0]+rect[2] and bx+w > rect[0] and by < rect[1]+rect[3] and by+h > rect[1]):
                return True
        return False
    def update(self, dt, same_lane, green_dir, intersections):
        vx,vy = self.forward_vec()
        dx = vx * self.speed * dt
        dy = vy * self.speed * dt
        # lock lane
        if self.dir in ('E','W'):
            self.pos[1] = self.lane_fix
        else:
            self.pos[0] = self.lane_fix
        nextx = self.pos[0] + dx
        nexty = self.pos[1] + dy
        allowed = (self.dir == green_dir) or self.inside_intersection(intersections)
        if not allowed:
            if self.dir == 'E' and (nextx + self.halfLen) >= self.stop_coord:
                nextx = self.stop_coord - self.halfLen - 1
            elif self.dir == 'W' and (nextx - self.halfLen) <= self.stop_coord:
                nextx = self.stop_coord + self.halfLen + 1
            elif self.dir == 'S' and (nexty + self.halfLen) >= self.stop_coord:
                nexty = self.stop_coord - self.halfLen - 1
            elif self.dir == 'N' and (nexty - self.halfLen) <= self.stop_coord:
                nexty = self.stop_coord + self.halfLen + 1
        # maintain safe gap
        leads = [u for u in same_lane if u is not self]
        if leads:
            if self.dir == 'E':
                ahead = [u for u in leads if u.pos[0] > self.pos[0]]
                if ahead:
                    lead = min(ahead, key=lambda u: u.pos[0])
                    nextx = min(nextx, lead.pos[0] - lead.halfLen - SAFE_GAP - self.halfLen)
            elif self.dir == 'W':
                ahead = [u for u in leads if u.pos[0] < self.pos[0]]
                if ahead:
                    lead = max(ahead, key=lambda u: u.pos[0])
                    nextx = max(nextx, lead.pos[0] + lead.halfLen + SAFE_GAP + self.halfLen)
            elif self.dir == 'S':
                ahead = [u for u in leads if u.pos[1] > self.pos[1]]
                if ahead:
                    lead = min(ahead, key=lambda u: u.pos[1])
                    nexty = min(nexty, lead.pos[1] - lead.halfLen - SAFE_GAP - self.halfLen)
            elif self.dir == 'N':
                ahead = [u for u in leads if u.pos[1] < self.pos[1]]
                if ahead:
                    lead = max(ahead, key=lambda u: u.pos[1])
                    nexty = max(nexty, lead.pos[1] + lead.halfLen + SAFE_GAP + self.halfLen)
        self.pos[0] = nextx
        self.pos[1] = nexty
    def draw(self, surf, offset, zoom):
        bx,by,w,h = self.bbox()
        rx = (bx - offset[0]) * zoom
        ry = (by - offset[1]) * zoom
        rw = w * zoom
        rh = h * zoom
        pygame.draw.rect(surf, self.color, (rx,ry,rw,rh))
        # small detail
        pygame.draw.rect(surf, (0,0,0,120), (rx+rw*0.2, ry+rh*0.3, rw*0.6, rh*0.3))

# ---------- Simulation ----------
class Simulation:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Advanced Traffic Simulation - Pygame")
        self.clock = pygame.time.Clock()
        self.zoom = 0.1
        self.offset = [0.0, 0.0]
        self.spawn_timer = 0.0
        self.paused = False
        self.is_panning = False
        self.last_mouse = (0,0)
        self.current_tool = 'select'  # select, road, intersection, delete
        self.road_points = []
        self.selected = None
        self.hover = None
        self.snap_to_grid = True
        self.roads = []
        self.intersections = []
        self.vehicles = []
        self.last_click_time = 0
        self.spawn_interval = SPAWN_INTERVAL
        self.init_default_map()
    def world_from_screen(self, sx, sy):
        return (sx / self.zoom + self.offset[0], sy / self.zoom + self.offset[1])
    def screen_from_world(self, wx, wy):
        return ((wx - self.offset[0]) * self.zoom, (wy - self.offset[1]) * self.zoom)
    def snap(self, p):
        if not self.snap_to_grid:
            return p
        gx = round(p[0] / (GRID_SIZE*PX_PER_METER)) * (GRID_SIZE*PX_PER_METER)
        gy = round(p[1] / (GRID_SIZE*PX_PER_METER)) * (GRID_SIZE*PX_PER_METER)
        return (gx,gy)
    def init_default_map(self):
        # create some large coordinate roads like the JS
        self.roads = []
        self.intersections = []
        hroad = Road([(2000*PX_PER_METER,3000*PX_PER_METER),(8000*PX_PER_METER,3000*PX_PER_METER)])
        vroad = Road([(5000*PX_PER_METER,1000*PX_PER_METER),(5000*PX_PER_METER,9000*PX_PER_METER)])
        droad = Road([(2000*PX_PER_METER,7000*PX_PER_METER),(8000*PX_PER_METER,7000*PX_PER_METER)])
        self.roads.extend([hroad,vroad,droad])
        self.create_intersections_from_roads()
        # set view to center
        self.fit_view()
    def create_intersections_from_roads(self):
        self.intersections = []
        # pairwise segment intersections
        for i in range(len(self.roads)):
            for j in range(i+1,len(self.roads)):
                r1 = self.roads[i]; r2 = self.roads[j]
                for (p1,p2) in r1.segments():
                    for (p3,p4) in r2.segments():
                        inter = line_segment_intersection(p1,p2,p3,p4)
                        if inter:
                            x,y = inter
                            # avoid duplicates
                            if not any(distance((x,y),(it.x,it.y))<1.0 for it in self.intersections):
                                obj = Intersection(x,y)
                                obj.connectedRoads = [r1.id, r2.id]
                                self.intersections.append(obj)
                            else:
                                # add connected roads to existing
                                existing = next(it for it in self.intersections if distance((x,y),(it.x,it.y))<1.0)
                                if r1.id not in existing.connectedRoads: existing.connectedRoads.append(r1.id)
                                if r2.id not in existing.connectedRoads: existing.connectedRoads.append(r2.id)
        # T-junctions (endpoint on other road)
        for i, r1 in enumerate(self.roads):
            for j, r2 in enumerate(self.roads):
                if i==j: continue
                for p in r1.points:
                    for (q1,q2) in r2.segments():
                        if point_on_segment(p,q1,q2):
                            if not any(distance(p,(it.x,it.y))<1.0 for it in self.intersections):
                                obj = Intersection(p[0],p[1])
                                obj.connectedRoads = [r1.id, r2.id]
                                self.intersections.append(obj)
                            else:
                                existing = next(it for it in self.intersections if distance(p,(it.x,it.y))<1.0)
                                if r1.id not in existing.connectedRoads: existing.connectedRoads.append(r1.id)
                                if r2.id not in existing.connectedRoads: existing.connectedRoads.append(r2.id)
        # update directions
        self.update_intersection_directions()
    def update_intersection_directions(self):
        for inter in self.intersections:
            inter.directions = []
            for rid in inter.connectedRoads:
                road = next((r for r in self.roads if r.id==rid), None)
                if not road: continue
                for p1,p2 in road.segments():
                    if distance(p1,(inter.x,inter.y))<1.0:
                        d = angle_to_dir(p1,p2)
                        if d not in inter.directions: inter.directions.append(d)
                    elif distance(p2,(inter.x,inter.y))<1.0:
                        d = angle_to_dir(p2,p1)
                        if d not in inter.directions: inter.directions.append(d)
                    elif point_on_segment((inter.x,inter.y), p1,p2):
                        d1 = angle_to_dir((inter.x,inter.y), p1)
                        d2 = angle_to_dir((inter.x,inter.y), p2)
                        if d1 not in inter.directions: inter.directions.append(d1)
                        if d2 not in inter.directions: inter.directions.append(d2)
            if not inter.directions:
                # fallback to cardinal directions
                inter.directions = ['E','W','N','S']
    def spawn_vehicle(self, kind, dir, inter_index):
        if inter_index < 0 or inter_index >= len(self.intersections): return
        inter = self.intersections[inter_index]
        ix,iy = inter.x, inter.y
        if dir == 'E':
            y = iy - LANE_OFFSET
            pos = (-random.uniform(50,250), y)
            stop = ix - INTER_HALF - STOP_BUFFER
            lane_fix = y
        elif dir == 'W':
            y = iy + LANE_OFFSET
            pos = (10000*PX_PER_METER + random.uniform(50,250), y)
            stop = ix + INTER_HALF + STOP_BUFFER
            lane_fix = y
        elif dir == 'S':
            x = ix - LANE_OFFSET
            pos = (x, -random.uniform(50,250))
            stop = iy - INTER_HALF - STOP_BUFFER
            lane_fix = x
        elif dir == 'N':
            x = ix + LANE_OFFSET
            pos = (x, 10000*PX_PER_METER + random.uniform(50,250))
            stop = iy + INTER_HALF + STOP_BUFFER
            lane_fix = x
        else:
            pos = (ix,iy); stop = ix; lane_fix = iy
        v = Vehicle(kind, dir, pos, inter_index, stop, lane_fix)
        self.vehicles.append(v)
    def update(self, dt):
        if self.paused: return
        # update lights
        for inter in self.intersections:
            inter.timer += dt
            if inter.timer >= inter.greenTime:
                if inter.directions:
                    inter.phase = (inter.phase + 1) % len(inter.directions)
                inter.timer = 0.0
        # spawn vehicles periodically
        self.spawn_timer += dt
        if self.spawn_timer >= self.spawn_interval and self.intersections:
            for i, inter in enumerate(self.intersections):
                if not inter.directions: continue
                kind = random.choice(['bike','car','bus'])
                dir = random.choice(inter.directions)
                try:
                    self.spawn_vehicle(kind, dir, i)
                except Exception:
                    pass
            self.spawn_timer = 0.0
        # update vehicles
        for v in list(self.vehicles):
            green_dir = 'E'
            if 0 <= v.inter_index < len(self.intersections):
                inter = self.intersections[v.inter_index]
                if inter.directions:
                    green_dir = inter.directions[inter.phase % len(inter.directions)]
            same = [u for u in self.vehicles if u.dir == v.dir and abs(u.lane_fix - v.lane_fix) < 1.0]
            v.update(dt, same, green_dir, self.intersections)
        # cleanup vehicles that left bounds
        self.vehicles = [v for v in self.vehicles if -2000 < v.pos[0] < 10000*PX_PER_METER+2000 and -2000 < v.pos[1] < 10000*PX_PER_METER+2000]
    def draw(self):
        surf = self.screen
        surf.fill(CLR_BG)
        # draw grid
        if self.snap_to_grid:
            step = GRID_SIZE*PX_PER_METER
            # draw a few grid lines within view
            left = int((self.offset[0] - WIDTH/(2*self.zoom))//step * step)
            right = int((self.offset[0] + WIDTH/(2*self.zoom))//step * step + step)
            top = int((self.offset[1] - HEIGHT/(2*self.zoom))//step * step)
            bottom = int((self.offset[1] + HEIGHT/(2*self.zoom))//step * step + step)
            for gx in range(left, right+step, step):
                sx = (gx - self.offset[0]) * self.zoom
                pygame.draw.line(surf, (200,200,200,20), (sx,0), (sx,HEIGHT), 1)
            for gy in range(top, bottom+step, step):
                sy = (gy - self.offset[1]) * self.zoom
                pygame.draw.line(surf, (200,200,200,20), (0,sy), (WIDTH,sy), 1)
        # draw roads
        for road in self.roads:
            for p1,p2 in road.segments():
                # polygon for width
                dx = p2[0]-p1[0]; dy = p2[1]-p1[1]
                L = math.hypot(dx,dy)
                if L == 0: continue
                nx = -dy / L; ny = dx / L
                width_px = road.width_m * PX_PER_METER
                hw = width_px/2
                p1l = (p1[0] + nx*hw, p1[1] + ny*hw)
                p1r = (p1[0] - nx*hw, p1[1] - ny*hw)
                p2l = (p2[0] + nx*hw, p2[1] + ny*hw)
                p2r = (p2[0] - nx*hw, p2[1] - ny*hw)
                poly = [self.screen_from_world(*pt) for pt in (p1l,p2l,p2r,p1r)]
                pygame.draw.polygon(surf, CLR_ROAD, poly)
                # lane center line
                sx1,sy1 = self.screen_from_world(p1[0],p1[1])
                sx2,sy2 = self.screen_from_world(p2[0],p2[1])
                pygame.draw.line(surf, (255,255,255), (sx1,sy1), (sx2,sy2), max(1,int(2*self.zoom)))
        # draw intersections & lights
        for inter in self.intersections:
            rx,ry = self.screen_from_world(inter.x - INTER_HALF, inter.y - INTER_HALF)
            r = INTER_SIZE * self.zoom
            pygame.draw.rect(surf, CLR_INTER, (rx,ry,r,r))
            pygame.draw.rect(surf, (0,0,0,80), (rx,ry,r,r), 2)
            # label
            label = FONT.render(f"Int {inter.id%1000}", True, CLR_TEXT)
            surf.blit(label, ( (inter.x - self.offset[0]) * self.zoom - 20, (inter.y - INTER_HALF - 10 - self.offset[1]) * self.zoom ) )
            # draw lights for N/E/S/W
            light_radius = max(3, int(8*self.zoom))
            directions = inter.directions or ['E','W','N','S']
            green_dir = directions[inter.phase % len(directions)] if directions else 'E'
            for d in directions:
                if d == 'E':
                    ex = (inter.x + INTER_HALF + 18 - self.offset[0]) * self.zoom
                    ey = (inter.y - self.offset[1]) * self.zoom
                elif d == 'W':
                    ex = (inter.x - INTER_HALF - 18 - self.offset[0]) * self.zoom
                    ey = (inter.y - self.offset[1]) * self.zoom
                elif d == 'N':
                    ex = (inter.x - self.offset[0]) * self.zoom
                    ey = (inter.y - INTER_HALF - 18 - self.offset[1]) * self.zoom
                elif d == 'S':
                    ex = (inter.x - self.offset[0]) * self.zoom
                    ey = (inter.y + INTER_HALF + 18 - self.offset[1]) * self.zoom
                color = (0,255,0) if d==green_dir else (255,0,0)
                pygame.draw.circle(surf, color, (int(ex),int(ey)), light_radius)
        # draw vehicles
        for v in self.vehicles:
            v.draw(surf, self.offset, self.zoom)
        # draw road draw preview
        if self.current_tool == 'road' and self.road_points:
            pts = [self.screen_from_world(*p) for p in self.road_points]
            if len(pts) > 1:
                pygame.draw.lines(surf, CLR_SELECTED, False, pts, max(2,int(2*self.zoom)))
            for p in pts:
                pygame.draw.circle(surf, CLR_SELECTED, (int(p[0]), int(p[1])), max(3, int(4*self.zoom)))
        # HUD
        hud_rect = pygame.Rect(8,8,360,80)
        pygame.draw.rect(surf, (0,0,0,150), hud_rect)
        info_lines = [
            f"Vehicles: {len(self.vehicles)}  |  Roads: {len(self.roads)}  |  Intersections: {len(self.intersections)}",
            f"Tool: {self.current_tool}  |  Snap: {'On' if self.snap_to_grid else 'Off'}  |  Zoom: {self.zoom:.2f}x",
            "Keys: 1-select 2-road 3-inter 4-delete | Space-pause | Enter-finish road | G-toggle grid"
        ]
        for i, line in enumerate(info_lines):
            surf.blit(FONT.render(line, True, CLR_TEXT), (12, 12 + i*20))
        # selected highlight
        if self.selected:
            if self.selected[0] == 'road':
                road = next((r for r in self.roads if r.id==self.selected[1]), None)
                if road:
                    for p1,p2 in road.segments():
                        sx1,sy1 = self.screen_from_world(p1[0],p1[1])
                        sx2,sy2 = self.screen_from_world(p2[0],p2[1])
                        pygame.draw.line(surf, CLR_SELECTED, (sx1,sy1),(sx2,sy2), max(3,int(3*self.zoom)))
            elif self.selected[0] == 'intersection':
                inter = next((it for it in self.intersections if it.id==self.selected[1]), None)
                if inter:
                    rx,ry = self.screen_from_world(inter.x-INTER_HALF, inter.y-INTER_HALF)
                    r = INTER_SIZE*self.zoom
                    pygame.draw.rect(surf, CLR_SELECTED, (rx,ry,r,r), 3)
        pygame.display.flip()
    def pick_object_at(self, world_pt):
        # intersections first
        for inter in self.intersections:
            rect = (inter.x-INTER_HALF, inter.y-INTER_HALF, INTER_SIZE, INTER_SIZE)
            if world_pt[0] >= rect[0] and world_pt[0] <= rect[0]+rect[2] and world_pt[1] >= rect[1] and world_pt[1] <= rect[1]+rect[3]:
                return ('intersection', inter.id)
        # roads
        for road in self.roads:
            for p1,p2 in road.segments():
                # distance from point to segment
                dx = p2[0]-p1[0]; dy = p2[1]-p1[1]
                L = math.hypot(dx,dy)
                if L == 0: continue
                t = ((world_pt[0]-p1[0])*dx + (world_pt[1]-p1[1])*dy) / (L*L)
                t = max(0,min(1,t))
                closest = (p1[0]+t*dx, p1[1]+t*dy)
                if distance(closest, world_pt) < (road.width_m*PX_PER_METER/2 + 10):
                    return ('road', road.id)
        return None
    def fit_view(self):
        # compute bbox
        minx = float('inf'); miny=float('inf'); maxx=-float('inf'); maxy=-float('inf')
        for r in self.roads:
            for p in r.points:
                minx=min(minx,p[0]); miny=min(miny,p[1]); maxx=max(maxx,p[0]); maxy=max(maxy,p[1])
        for it in self.intersections:
            minx=min(minx,it.x); miny=min(miny,it.y); maxx=max(maxx,it.x); maxy=max(maxy,it.y)
        if minx==float('inf'):
            minx=0;miny=0;maxx=10000*PX_PER_METER;maxy=10000*PX_PER_METER
        padding = 1000*PX_PER_METER
        minx -= padding; miny -= padding; maxx += padding; maxy += padding
        w = maxx-minx; h = maxy-miny
        if w==0 or h==0: return
        zoomx = WIDTH / w; zoomy = HEIGHT / h
        self.zoom = min(zoomx, zoomy) * 0.9
        cx = (minx+maxx)/2; cy = (miny+maxy)/2
        self.offset = [cx - (WIDTH/2)/self.zoom, cy - (HEIGHT/2)/self.zoom]
    # ---------- main loop ----------
    def run(self):
        running = True
        last_time = pygame.time.get_ticks()/1000.0
        while running:
            now = pygame.time.get_ticks()/1000.0
            dt = now - last_time
            last_time = now
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        self.current_tool = 'select'; self.road_points=[]
                    elif ev.key == pygame.K_SPACE:
                        self.paused = not self.paused
                    elif ev.key == pygame.K_g:
                        self.snap_to_grid = not self.snap_to_grid
                    elif ev.key == pygame.K_1:
                        self.current_tool = 'select'
                    elif ev.key == pygame.K_2:
                        self.current_tool = 'road'
                    elif ev.key == pygame.K_3:
                        self.current_tool = 'intersection'
                    elif ev.key == pygame.K_4:
                        self.current_tool = 'delete'
                    elif ev.key == pygame.K_RETURN:
                        if self.current_tool == 'road' and len(self.road_points) >= 2:
                            road = Road(self.road_points[:], ROAD_WIDTH_DEFAULT)
                            self.roads.append(road)
                            self.road_points = []
                            self.create_intersections_from_roads()
                    elif ev.key == pygame.K_r:
                        self.vehicles = []
                    elif ev.key == pygame.K_a:
                        # add some random vehicles
                        for i in range(len(self.intersections)):
                            inter = self.intersections[i]
                            if not inter.directions: continue
                            dir = random.choice(inter.directions)
                            kind = random.choice(['bike','car','bus'])
                            self.spawn_vehicle(kind, dir, i)
                    elif ev.key == pygame.K_f:
                        self.fit_view()
                    elif ev.key == pygame.K_PLUS or ev.key == pygame.K_EQUALS:
                        self.zoom = min(1.0, self.zoom * 1.1)
                    elif ev.key == pygame.K_MINUS:
                        self.zoom = max(0.02, self.zoom / 1.1)
                    elif ev.key in (pygame.K_LEFT, pygame.K_a):
                        self.offset[0] -= 300 * (1/self.zoom)
                    elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                        self.offset[0] += 300 * (1/self.zoom)
                    elif ev.key in (pygame.K_UP, pygame.K_w):
                        self.offset[1] -= 300 * (1/self.zoom)
                    elif ev.key in (pygame.K_DOWN, pygame.K_s):
                        self.offset[1] += 300 * (1/self.zoom)
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    mx,my = ev.pos
                    world = self.world_from_screen(mx,my)
                    if ev.button == 2:  # middle mouse
                        self.is_panning = True
                        self.last_mouse = (mx,my)
                    elif ev.button == 1:  # left click
                        if self.current_tool == 'select':
                            picked = self.pick_object_at(world)
                            if picked:
                                self.selected = picked
                            else:
                                self.selected = None
                        elif self.current_tool == 'road':
                            p = self.snap(world) if self.snap_to_grid else world
                            self.road_points.append(p)
                            # simple double-click detection -> if two clicks within small time at same place finish
                            nowt = pygame.time.get_ticks()
                            if nowt - self.last_click_time < 300 and len(self.road_points)>=2:
                                # consider it a finish
                                road = Road(self.road_points[:], ROAD_WIDTH_DEFAULT)
                                self.roads.append(road)
                                self.road_points=[]
                                self.create_intersections_from_roads()
                            self.last_click_time = nowt
                        elif self.current_tool == 'intersection':
                            p = self.snap(world) if self.snap_to_grid else world
                            newi = Intersection(p[0], p[1]); self.intersections.append(newi)
                            self.create_intersections_from_roads()
                        elif self.current_tool == 'delete':
                            picked = self.pick_object_at(world)
                            if picked:
                                typ, pid = picked
                                if typ == 'road':
                                    self.roads = [r for r in self.roads if r.id != pid]
                                    self.selected = None
                                    self.create_intersections_from_roads()
                                elif typ == 'intersection':
                                    self.intersections = [it for it in self.intersections if it.id != pid]
                                    self.selected = None
                    elif ev.button == 4:  # wheel up
                        self.zoom = min(1.0, self.zoom * 1.1)
                    elif ev.button == 5:  # wheel down
                        self.zoom = max(0.02, self.zoom / 1.1)
                elif ev.type == pygame.MOUSEBUTTONUP:
                    if ev.button == 2:
                        self.is_panning = False
                elif ev.type == pygame.MOUSEMOTION:
                    if self.is_panning:
                        mx,my = ev.pos
                        dx = (self.last_mouse[0] - mx) / self.zoom
                        dy = (self.last_mouse[1] - my) / self.zoom
                        self.offset[0] += dx
                        self.offset[1] += dy
                        self.last_mouse = (mx,my)
            # update + draw
            self.update(dt)
            self.draw()
            self.clock.tick(60)
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    sim = Simulation()
    sim.run()
