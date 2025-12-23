import pygame
import sys
import random
import math
from dataclasses import dataclass
from typing import List, Tuple

PPM = 5
WIDTH, HEIGHT = 1280, 720
ROAD_THICK = 12 * PPM
INTER_SIZE = 120
INTER_HALF = INTER_SIZE // 2
SAFE_GAP = 35
STOP_BUFFER = 10
LANE_OFFSET = ROAD_THICK // 3
FPS = 60
SPAWN_INTERVAL = 1.5

S_BIKE = (int(0.6 * PPM), int(3 * PPM))
S_CAR  = (int(1.2 * PPM), int(4 * PPM))
S_BUS  = (int(2 * PPM), int(7 * PPM))
S_AMB  = (int(1.4 * PPM), int(5 * PPM))

V_BIKE, V_CAR, V_BUS, V_AMB = 7 * PPM, 7 * PPM, 6.5 * PPM, 9 * PPM

CLR_BIKE = (30,144,255)
CLR_CAR  = (34,139,34)
CLR_BUS  = (128,0,128)
CLR_AMB  = (255,50,50)
CLR_BG, CLR_ROAD = (220,220,220),(40,40,40)
CLR_INTER = (200,40,40)
CLR_TEXT = (255,255,255)
CLR_BTN_BG = (50,50,50)
CLR_BTN_ACTIVE = (80,160,80)

pygame.init()
font = pygame.font.SysFont(None,22)

def choose_turn_direction(d):
    r = random.random()
    if d == "W":
        options = ["E", "S"]
    elif d == "E":
        options = ["W", "N"]
    elif d == "N":
        options = ["S", "E"]
    else:
        options = ["N", "W"]
    if r < 0.7:
        return options[0]
    return options[1]

def resolve_overlap(v1, v2):
    r1 = v1.bbox()
    r2 = v2.bbox()
    if not r1.colliderect(r2):
        return
    dx = min(r1.right - r2.left, r2.right - r1.left)
    dy = min(r1.bottom - r2.top, r2.bottom - r1.top)
    if dx < dy:
        if r1.centerx < r2.centerx:
            v1.pos.x -= dx / 2
            v2.pos.x += dx / 2
        else:
            v1.pos.x += dx / 2
            v2.pos.x -= dx / 2
    else:
        if r1.centery < r2.centery:
            v1.pos.y -= dy / 2
            v2.pos.y += dy / 2
        else:
            v1.pos.y += dy / 2
            v2.pos.y -= dy / 2

PIXELS_PER_KM = 100
ROAD_LENGTHS = {
    (0,1):3,
    (2,3):5,
    (0,2):4,
    (1,3):5
}

x0, y0 = 300, 300
INTERS = [
    (x0, y0),
    (x0 + ROAD_LENGTHS[(0,1)] * PIXELS_PER_KM, y0),
    (x0, y0 + ROAD_LENGTHS[(0,2)] * PIXELS_PER_KM),
    (x0 + ROAD_LENGTHS[(2,3)] * PIXELS_PER_KM,
     y0 + ROAD_LENGTHS[(0,2)] * PIXELS_PER_KM)
]

INTER_RECTS = [
    pygame.Rect(ix - INTER_HALF, iy - INTER_HALF, INTER_SIZE, INTER_SIZE)
    for ix, iy in INTERS
]

user_roads = []
intersections = []
next_user_inter_id = 5
drawing_mode = False
placing_intersection = False
current_poly = []
temp_intersections = []

def stop_x_for_e(ix): return ix - INTER_HALF - STOP_BUFFER
def stop_x_for_w(ix): return ix + INTER_HALF + STOP_BUFFER
def stop_y_for_s(iy): return iy - INTER_HALF - STOP_BUFFER
def stop_y_for_n(iy): return iy + INTER_HALF + STOP_BUFFER

def line_intersection(p1,p2,p3,p4):
    x1,y1 = p1
    x2,y2 = p2
    x3,y3 = p3
    x4,y4 = p4
    d = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
    if abs(d) < 1e-9:
        return None
    px = ((x1*y2 - y1*x2)*(x3-x4) - (x1-x2)*(x3*y4 - y3*x4)) / d
    py = ((x1*y2 - y1*x2)*(y3-y4) - (y1-y2)*(x3*y4 - y3*x4)) / d
    if (min(x1,x2)-1e-6 <= px <= max(x1,x2)+1e-6 and
        min(y1,y2)-1e-6 <= py <= max(y1,y2)+1e-6 and
        min(x3,x4)-1e-6 <= px <= max(x3,x4)+1e-6 and
        min(y3,y4)-1e-6 <= py <= max(y3,y4)+1e-6):
        return (px, py)
    return None

def angle_between_segments(a1,a2,b1,b2):
    x1,y1 = a2[0]-a1[0], a2[1]-a1[1]
    x2,y2 = b2[0]-b1[0], b2[1]-b1[1]
    m1 = math.hypot(x1,y1)
    m2 = math.hypot(x2,y2)
    if m1 == 0 or m2 == 0:
        return 0
    c = (x1*x2 + y1*y2) / (m1*m2)
    c = max(-1,min(1,c))
    return math.degrees(math.acos(c))

def is_nearby_existing(pt, tol=12):
    for inter in intersections:
        ix, iy = inter["pos"]
        if math.hypot(ix-pt[0], iy-pt[1]) < tol:
            return True
    return False

def detect_4way_intersection(p1,p2,q1,q2):
    pt = line_intersection(p1,p2,q1,q2)
    if not pt:
        return None
    ang = angle_between_segments(p1,p2,q1,q2)
    if 70 <= ang <= 110:
        return pt
    tol = 10
    def proj(px,py,a,b):
        ax,ay = a
        bx,by = b
        dx,dy = bx-ax, by-ay
        dd = dx*dx + dy*dy
        if dd == 0: return 0
        return ((px-ax)*dx + (py-ay)*dy)/dd
    t1 = proj(q1[0], q1[1], p1, p2)
    t2 = proj(q2[0], q2[1], p1, p2)
    if t1 >= -0.05 and t1 <= 1.05 and t2 >= -0.05 and t2 <= 1.05 and 45 <= ang <= 135:
        return pt
    return None

def detect_intersections_for_segment(p1,p2):
    found = []
    for old in user_roads:
        q1,q2 = old
        pt = line_intersection(p1,p2,q1,q2)
        if pt and not is_nearby_existing(pt,15):
            found.append(pt)
    INF = 100000
    xs = sorted({ix for ix,iy in INTERS})
    ys = sorted({iy for ix,iy in INTERS})
    for ix in xs:
        pt = line_intersection(p1,p2,(ix,-INF),(ix,INF))
        if pt and not is_nearby_existing(pt,15):
            found.append(pt)
    for iy in ys:
        pt = line_intersection(p1,p2,(-INF,iy),(INF,iy))
        if pt and not is_nearby_existing(pt,15):
            found.append(pt)
    return found

def compute_lane_fix(direction, inter_index):
    ix, iy = INTERS[inter_index]
    if direction == "E":
        return iy - LANE_OFFSET
    if direction == "W":
        return iy + LANE_OFFSET
    if direction == "N":
        return ix + LANE_OFFSET
    if direction == "S":
        return ix - LANE_OFFSET
    return iy

@dataclass
class Vehicle:
    kind: str
    dir: str
    pos: pygame.Vector2
    speed: float
    size_ns: tuple
    color: tuple
    stop: float
    lane_fix: float
    inter_index: int
    entered: bool = False
    emergency: bool = False

    def oriented_size(self):
        if self.dir in ("N","S"):
            return self.size_ns
        w,h = self.size_ns
        return (h,w)

    def bbox(self):
        w,h = self.oriented_size()
        return pygame.Rect(int(self.pos.x - w/2),
                           int(self.pos.y - h/2),
                           w,h)

    def fwd(self):
        return {
            "E": pygame.Vector2(1,0),
            "W": pygame.Vector2(-1,0),
            "S": pygame.Vector2(0,1),
            "N": pygame.Vector2(0,-1)
        }[self.dir]

    def half_len(self):
        w,h = self.oriented_size()
        return w/2 if self.dir in ("E","W") else h/2

    def update(self, dt, same_lane, states):
        if self.dir in ("E","W"):
            self.pos.y = self.lane_fix
        else:
            self.pos.x = self.lane_fix
        v = self.fwd() * self.speed * dt
        next_pos = self.pos + v
        h = self.half_len()
        ow,oh = self.oriented_size()
        next_box = pygame.Rect(int(next_pos.x - ow/2),
                               int(next_pos.y - oh/2), ow, oh)
        hit = self.inter_index
        if 0 <= hit < len(INTERS):
            ix,iy = INTERS[hit]
            green_dir = states[hit]["green"]
            entering = next_box.colliderect(INTER_RECTS[hit])
            if green_dir != self.dir and not self.emergency:
                if self.dir=="E" and next_pos.x+h>=self.stop:
                    next_pos.x = self.stop - h - 1
                elif self.dir=="W" and next_pos.x-h<=self.stop:
                    next_pos.x = self.stop + h + 1
                elif self.dir=="S" and next_pos.y+h>=self.stop:
                    next_pos.y = self.stop - h - 1
                elif self.dir=="N" and next_pos.y-h<=self.stop:
                    next_pos.y = self.stop + h + 1
                self.entered = False
            else:
                if entering:
                    if not self.entered:
                        self.entered = True
                else:
                    if self.entered:
                        new_dir = choose_turn_direction(self.dir)
                        self.dir = new_dir
                        self.lane_fix = compute_lane_fix(new_dir, self.inter_index)
                        if new_dir in ("E","W"):
                            self.pos.y = self.lane_fix
                        else:
                            self.pos.x = self.lane_fix
                        self.entered = False
        for u in same_lane:
            if u is self: continue
            if self.dir=="E" and u.pos.x > self.pos.x:
                next_pos.x = min(next_pos.x, u.pos.x - u.half_len() - SAFE_GAP - h)
            elif self.dir=="W" and u.pos.x < self.pos.x:
                next_pos.x = max(next_pos.x, u.pos.x + u.half_len() + SAFE_GAP + h)
            elif self.dir=="S" and u.pos.y > self.pos.y:
                next_pos.y = min(next_pos.y, u.pos.y - u.half_len() - SAFE_GAP - h)
            elif self.dir=="N" and u.pos.y < self.pos.y:
                next_pos.y = max(next_pos.y, u.pos.y + u.half_len() + SAFE_GAP + h)
        self.pos = next_pos

    def draw(self, s, zoom, off):
        r = self.bbox()
        sr = pygame.Rect(
            int((r.x - off[0]) * zoom),
            int((r.y - off[1]) * zoom),
            int(r.width * zoom),
            int(r.height * zoom)
        )
        pygame.draw.rect(s, self.color, sr)

def veh(k):
    if k=="bike": return S_BIKE, V_BIKE, CLR_BIKE, False
    if k=="car":  return S_CAR,  V_CAR,  CLR_CAR,  False
    if k=="bus":  return S_BUS,  V_BUS,  CLR_BUS,  False
    return S_AMB, V_AMB, CLR_AMB, True

def spawn(k, d, i, emergency=False):
    size,spd,color,em_flag = veh(k) if not emergency else (S_AMB, V_AMB, CLR_AMB, True)
    ix,iy = INTERS[i]
    if d == "E":
        lane_fix = iy - LANE_OFFSET
        pos = pygame.Vector2(ix - 850, lane_fix)
        stop = stop_x_for_e(ix)
    elif d == "W":
        lane_fix = iy + LANE_OFFSET
        pos = pygame.Vector2(ix + 850, lane_fix)
        stop = stop_x_for_w(ix)
    elif d == "S":
        lane_fix = ix - LANE_OFFSET
        pos = pygame.Vector2(lane_fix, iy - 850)
        stop = stop_y_for_s(iy)
    else:
        lane_fix = ix + LANE_OFFSET
        pos = pygame.Vector2(lane_fix, iy + 850)
        stop = stop_y_for_n(iy)
    return Vehicle(k, d, pos, spd, size, color, stop, lane_fix, i, entered=False, emergency=em_flag)

screen = pygame.display.set_mode((WIDTH,HEIGHT))
clock = pygame.time.Clock()
vehicles = []
zoom = 1.0
offset = [0,0]
spawn_timer = 0
dragging = False
drag_start = (0,0)
offset_start = (0,0)

states = []
for i in range(4):
    states.append({
        "green":"E",
        "timer":0.0,
        "min_green":2.5,
        "max_green":10.0
    })

DIRS = ["E","W","N","S"]

BTN_W, BTN_H = 130, 28
BTN_PAD = 6
buttons = []

def make_buttons():
    global buttons
    buttons = []
    x,y = 10,10
    def add(label,key):
        nonlocal x,y
        rect = pygame.Rect(x,y,BTN_W,BTN_H)
        buttons.append({"rect":rect,"label":label,"key":key})
        y += BTN_H + BTN_PAD
    add("Draw Road","draw_road")
    add("Add Intersection","add_inter")
    add("Pan Mode","pan_mode")
    add("Clear Roads","clear_roads")

make_buttons()

flags = {
    "draw_road": False,
    "add_inter": False,
    "pan_mode": True,
    "clear_roads": False
}

def draw_all(s):
    s.fill(CLR_BG)
    INF = 10000
    thick = int(ROAD_THICK * zoom)
    xs = sorted({ix for ix,iy in INTERS})
    ys = sorted({iy for ix,iy in INTERS})
    for iy in ys:
        pygame.draw.rect(
            s, CLR_ROAD,
            pygame.Rect(
                int((-INF - offset[0]) * zoom),
                int((iy - ROAD_THICK//2 - offset[1]) * zoom),
                int((WIDTH + INF*2) * zoom),
                thick
            )
        )
    for ix in xs:
        pygame.draw.rect(
            s, CLR_ROAD,
            pygame.Rect(
                int((ix - ROAD_THICK//2 - offset[0]) * zoom),
                int((-INF - offset[1]) * zoom),
                thick,
                int((HEIGHT + INF*2) * zoom)
            )
        )
    for poly in user_roads:
        if len(poly)<2: continue
        pts = [(int((x-offset[0])*zoom), int((y-offset[1])*zoom)) for x,y in poly]
        pygame.draw.lines(s, CLR_ROAD, False, pts, max(4, int(ROAD_THICK*zoom)))
    for inter in intersections:
        ix,iy = inter["pos"]
        rect = pygame.Rect(
            int((ix - INTER_HALF - offset[0])*zoom),
            int((iy - INTER_HALF - offset[1])*zoom),
            int(INTER_SIZE * zoom),
            int(INTER_SIZE * zoom)
        )
        pygame.draw.rect(s, (255,0,0), rect)
    for pt in temp_intersections:
        ix,iy = pt
        rect = pygame.Rect(
            int((ix-12-offset[0])*zoom),
            int((iy-12-offset[1])*zoom),
            int(24*zoom),
            int(24*zoom)
        )
        pygame.draw.rect(s, (255,0,0), rect, 2)
    for i,(ix,iy) in enumerate(INTERS):
        st = states[i]
        rect = pygame.Rect(
            int((ix - INTER_HALF - offset[0]) * zoom),
            int((iy - INTER_HALF - offset[1]) * zoom),
            int(INTER_SIZE * zoom),
            int(INTER_SIZE * zoom)
        )
        pygame.draw.rect(s, CLR_INTER, rect)
        txt = font.render(f"Int {i+1} [{st['green']}] t={int(st['timer'])}", True, CLR_TEXT)
        s.blit(txt, (int((ix-offset[0])*zoom - 30), int((iy-offset[1])*zoom - 40)))
    for v in vehicles:
        v.draw(s, zoom, offset)
    for b in buttons:
        pygame.draw.rect(s, CLR_BTN_BG, b["rect"])
        if flags.get(b["key"],False):
            pygame.draw.rect(s, CLR_BTN_ACTIVE, b["rect"], 3)
        s.blit(font.render(b["label"], True, CLR_TEXT),
               (b["rect"].x+6, b["rect"].y+4))

def vehicle_before_intersection_for(v, i):
    ix, iy = INTERS[i]
    if v.inter_index != i:
        return False
    if v.dir == "E":
        return v.pos.x < ix - INTER_HALF
    if v.dir == "W":
        return v.pos.x > ix + INTER_HALF
    if v.dir == "S":
        return v.pos.y < iy - INTER_HALF
    if v.dir == "N":
        return v.pos.y > iy + INTER_HALF
    return False

def compute_queues():
    queues = [{"E":0,"W":0,"N":0,"S":0,"amb_present":False} for _ in INTERS]
    for v in vehicles:
        i = v.inter_index
        if not (0 <= i < len(queues)):
            continue
        if v.emergency:
            queues[i]["amb_present"] = True
        if vehicle_before_intersection_for(v, i):
            queues[i][v.dir] += 1
    return queues

def adaptive_signal_control(dt):
    queues = compute_queues()
    for i in range(len(states)):
        st = states[i]
        st["timer"] += dt
        if queues[i]["amb_present"]:
            for v in vehicles:
                if v.inter_index == i and v.emergency:
                    if st["green"] != v.dir:
                        st["green"] = v.dir
                        st["timer"] = 0.0
                    break
            continue
        total_wait = sum(queues[i][d] for d in ("E","W","N","S"))
        if total_wait == 0:
            if st["timer"] >= st["min_green"]:
                st["green"] = random.choice(DIRS)
                st["timer"] = 0.0
            continue
        preferred = max(("E","W","N","S"), key=lambda d: queues[i][d])
        if st["green"] == preferred:
            if st["timer"] >= st["max_green"]:
                second = sorted(("E","W","N","S"), key=lambda d: queues[i][d], reverse=True)[1]
                st["green"] = second
                st["timer"] = 0.0
        else:
            if st["timer"] >= st["min_green"]:
                st["green"] = preferred
                st["timer"] = 0.0

def spawn_mixed(i):
    num = random.choice([1,2,2,3])
    for _ in range(num):
        if random.random() < 0.82:
            d = random.choice(["E","W","N","S"])
            k = random.choices(["car","bike","bus"], weights=[60,25,15])[0]
            if random.random() < 0.03:
                k = "amb"
            vehicles.append(spawn(k, d, i))

def main():
    global zoom, offset, spawn_timer, dragging, drag_start, offset_start
    global drawing_mode, current_poly, next_user_inter_id, placing_intersection, temp_intersections
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        spawn_timer += dt
        temp_intersections = []
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.MOUSEBUTTONDOWN:
                mx, my = e.pos
                wx = mx / zoom + offset[0]
                wy = my / zoom + offset[1]
                if e.button == 1:
                    clicked = False
                    for b in buttons:
                        if b["rect"].collidepoint(e.pos):
                            clicked = True
                            key = b["key"]
                            if key == "draw_road":
                                flags["draw_road"] = not flags["draw_road"]
                                flags["add_inter"] = False
                                flags["pan_mode"] = not flags["draw_road"]
                                drawing_mode = flags["draw_road"]
                                current_poly = []
                            elif key == "add_inter":
                                flags["add_inter"] = not flags["add_inter"]
                                flags["draw_road"] = False
                                flags["pan_mode"] = not flags["add_inter"]
                                placing_intersection = flags["add_inter"]
                            elif key == "pan_mode":
                                flags["pan_mode"] = not flags["pan_mode"]
                                flags["draw_road"] = False
                                flags["add_inter"] = False
                                placing_intersection = False
                            elif key == "clear_roads":
                                user_roads.clear()
                                intersections.clear()
                                next_user_inter_id = 5
                            break
                    if not clicked:
                        if flags["draw_road"]:
                            drawing_mode = True
                            current_poly = [(wx, wy)]
                        elif flags["add_inter"]:
                            intersections.append({"pos":(wx,wy),"id":next_user_inter_id})
                            next_user_inter_id += 1
                        else:
                            dragging = True
                            drag_start = e.pos
                            offset_start = offset.copy()
            elif e.type == pygame.MOUSEBUTTONUP:
                if e.button == 1:
                    if drawing_mode and len(current_poly) == 2:
                        p1, p2 = current_poly
                        user_roads.append([p1, p2])
                        for old in user_roads[:-1]:
                            q1, q2 = old
                            pt = detect_4way_intersection(p1, p2, q1, q2)
                            if pt and not is_nearby_existing(pt, 15):
                                intersections.append({"pos":pt,"id":next_user_inter_id})
                                next_user_inter_id += 1
                        new_pts = detect_intersections_for_segment(p1, p2)
                        for pt in new_pts:
                            if not is_nearby_existing(pt, 15):
                                intersections.append({"pos":pt,"id":next_user_inter_id})
                                next_user_inter_id += 1
                        current_poly = []
                        drawing_mode = False
                    dragging = False
            elif e.type == pygame.MOUSEMOTION:
                if drawing_mode and pygame.mouse.get_pressed()[0]:
                    mx, my = e.pos
                    wx = mx / zoom + offset[0]
                    wy = my / zoom + offset[1]
                    if len(current_poly) == 0:
                        current_poly.append((wx, wy))
                    elif len(current_poly) == 1:
                        current_poly.append((wx, wy))
                    else:
                        current_poly[1] = (wx, wy)
                    if len(current_poly) == 2:
                        p1, p2 = current_poly
                        temp_pts = detect_intersections_for_segment(p1, p2)
                        for old in user_roads:
                            q1, q2 = old
                            pt = detect_4way_intersection(p1, p2, q1, q2)
                            if pt and not is_nearby_existing(pt, 15):
                                temp_pts.append(pt)
                        seen = set()
                        dedup = []
                        for (xx, yy) in temp_pts:
                            k = (round(xx,2), round(yy,2))
                            if k not in seen:
                                seen.add(k)
                                dedup.append((xx,yy))
                        temp_intersections = dedup
                elif dragging:
                    mx, my = e.pos
                    dx = (drag_start[0] - mx) / zoom
                    dy = (drag_start[1] - my) / zoom
                    offset[0] = offset_start[0] + dx
                    offset[1] = offset_start[1] + dy
            elif e.type == pygame.MOUSEWHEEL:
                old_zoom = zoom
                zoom *= 1.1 if e.y > 0 else 0.9
                zoom = max(0.05, min(20, zoom))
                mx, my = pygame.mouse.get_pos()
                wx = mx / old_zoom + offset[0]
                wy = my / old_zoom + offset[1]
                offset[0] = wx - mx / zoom
                offset[1] = wy - my / zoom
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            offset[0] -= 300 * dt
        if keys[pygame.K_RIGHT]:
            offset[0] += 300 * dt
        if keys[pygame.K_UP]:
            offset[1] -= 300 * dt
        if keys[pygame.K_DOWN]:
            offset[1] += 300 * dt
        adaptive_signal_control(dt)
        if spawn_timer >= SPAWN_INTERVAL:
            for i in range(4):
                if random.random() < 0.75:
                    spawn_mixed(i)
            spawn_timer = 0
        for v in vehicles:
            same = [u for u in vehicles if u is not v and u.dir == v.dir and u.lane_fix == v.lane_fix and u.inter_index == v.inter_index]
            v.update(dt, same, states)
        for i in range(len(vehicles)):
            for j in range(i+1, len(vehicles)):
                resolve_overlap(vehicles[i], vehicles[j])
        to_remove = []
        for v in vehicles:
            x,y = v.pos.x, v.pos.y
            if x < -2000 or x > 5000 or y < -2000 or y > 5000:
                to_remove.append(v)
        for v in to_remove:
            try:
                vehicles.remove(v)
            except ValueError:
                pass
        draw_all(screen)
        pygame.display.flip()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
