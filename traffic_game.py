import pygame, sys, csv, random
from dataclasses import dataclass
from typing import List, Tuple

# ---------------------------------
# CONFIG
# ---------------------------------
PPM = 5
WIDTH, HEIGHT = 1920, 1080
ROAD_THICK = 12 * PPM
X1, X2 = int(WIDTH / 3), int(WIDTH * 2 / 3)
Y1, Y2 = int(HEIGHT / 3), int(HEIGHT * 2 / 3)
INTER_SIZE = 120
INTER_HALF = INTER_SIZE // 2
SAFE_GAP = 35
STOP_BUFFER = 10
LANE_OFFSET = ROAD_THICK // 4
FPS = 60

# Vehicle sizes and colors
S_BIKE = (1 * PPM, 5 * PPM)
S_CAR = (3 * PPM, 5 * PPM)
S_BUS = (5 * PPM, 8 * PPM)
V_BIKE, V_CAR, V_BUS = 7.5 * PPM, 7.5 * PPM, 7.0 * PPM
CLR_BIKE, CLR_CAR, CLR_BUS = (30,144,255), (34,139,34), (128,0,128)
CLR_BG, CLR_ROAD, CLR_INTER, CLR_STOP, CLR_TEXT = (220,220,220), (0,0,0), (200,40,40), (255,255,255), (255,255,255)

# Intersections and rectangles
INTERS = [(X1, Y1), (X2, Y1), (X1, Y2), (X2, Y2)]
INTER_RECTS = [pygame.Rect(ix - INTER_HALF, iy - INTER_HALF, INTER_SIZE, INTER_SIZE) for (ix, iy) in INTERS]

# Stop line helpers
def stop_x_for_east(ix): return ix - INTER_HALF - STOP_BUFFER
def stop_x_for_west(ix): return ix + INTER_HALF + STOP_BUFFER
def stop_y_for_south(iy): return iy - INTER_HALF - STOP_BUFFER
def stop_y_for_north(iy): return iy + INTER_HALF + STOP_BUFFER

# ---------------------------------
# VEHICLE CLASS
# ---------------------------------
@dataclass
class Vehicle:
    kind: str
    dir: str
    pos: pygame.Vector2
    speed: float
    size_ns: Tuple[int, int]
    color: Tuple[int, int, int]
    stop_coord: float
    lane_fix: float
    target_inters: Tuple[int, int]

    def oriented_size(self):
        if self.dir in ("N", "S"): return self.size_ns
        w,h=self.size_ns; return (h,w)

    def bbox(self):
        w,h=self.oriented_size()
        return pygame.Rect(int(self.pos.x - w/2), int(self.pos.y - h/2), w, h)

    def forward(self):
        return {"E":pygame.Vector2(1,0),"W":pygame.Vector2(-1,0),"S":pygame.Vector2(0,1),"N":pygame.Vector2(0,-1)}[self.dir]

    def half_len(self):
        w,h=self.oriented_size()
        return (w/2) if self.dir in("E","W") else (h/2)

    def update(self, dt:float, same_lane:List["Vehicle"]):
        v = self.forward() * self.speed * dt
        if self.dir in ("E","W"): self.pos.y = self.lane_fix
        else: self.pos.x = self.lane_fix
        next_pos = self.pos + v
        h = self.half_len()
        stop = self.stop_coord

        # Stop before white line
        if self.dir=="E" and (next_pos.x+h)>=stop: next_pos.x=stop-h-1
        elif self.dir=="W" and (next_pos.x-h)<=stop: next_pos.x=stop+h+1
        elif self.dir=="S" and (next_pos.y+h)>=stop: next_pos.y=stop-h-1
        elif self.dir=="N" and (next_pos.y-h)<=stop: next_pos.y=stop+h+1

        # Prevent crossing red area
        rect_front=None
        if self.dir=="E": rect_front=next_pos.x+h
        elif self.dir=="W": rect_front=next_pos.x-h
        elif self.dir=="S": rect_front=next_pos.y+h
        elif self.dir=="N": rect_front=next_pos.y-h

        for r in INTER_RECTS:
            if self.dir=="E" and rect_front>=r.left: next_pos.x=min(next_pos.x,r.left-h-2)
            elif self.dir=="W" and rect_front<=r.right: next_pos.x=max(next_pos.x,r.right+h+2)
            elif self.dir=="S" and rect_front>=r.top: next_pos.y=min(next_pos.y,r.top-h-2)
            elif self.dir=="N" and rect_front<=r.bottom: next_pos.y=max(next_pos.y,r.bottom+h+2)

        # Maintain safe gap
        leads=[u for u in same_lane if u is not self]
        if leads:
            if self.dir=="E":
                ahead=[u for u in leads if u.pos.x>self.pos.x]
                if ahead:
                    lead=min(ahead,key=lambda u:u.pos.x)
                    next_pos.x=min(next_pos.x,lead.pos.x-lead.half_len()-SAFE_GAP-h)
            elif self.dir=="W":
                ahead=[u for u in leads if u.pos.x<self.pos.x]
                if ahead:
                    lead=max(ahead,key=lambda u:u.pos.x)
                    next_pos.x=max(next_pos.x,lead.pos.x+lead.half_len()+SAFE_GAP+h)
            elif self.dir=="S":
                ahead=[u for u in leads if u.pos.y>self.pos.y]
                if ahead:
                    lead=min(ahead,key=lambda u:u.pos.y)
                    next_pos.y=min(next_pos.y,lead.pos.y-lead.half_len()-SAFE_GAP-h)
            elif self.dir=="N":
                ahead=[u for u in leads if u.pos.y<self.pos.y]
                if ahead:
                    lead=max(ahead,key=lambda u:u.pos.y)
                    next_pos.y=max(next_pos.y,lead.pos.y+lead.half_len()+SAFE_GAP+h)

        self.pos = next_pos

    def draw(self,surf): pygame.draw.rect(surf,self.color,self.bbox(),0)

# ---------------------------------
# VEHICLE SPAWNING
# ---------------------------------
def veh_spec(k):
    return {"bike":(S_BIKE,V_BIKE,CLR_BIKE),
            "car":(S_CAR,V_CAR,CLR_CAR),
            "bus":(S_BUS,V_BUS,CLR_BUS)}[k]

def lane_y_east(y): return y - LANE_OFFSET
def lane_y_west(y): return y + LANE_OFFSET
def lane_x_south(x): return x - LANE_OFFSET
def lane_x_north(x): return x + LANE_OFFSET

def spawn_vehicle(k, dir, inter, offset=0):
    size, speed, color = veh_spec(k)
    ix, iy = inter
    spacing = 100 + offset * 140
    if dir == "E": y = lane_y_east(iy); pos = pygame.Vector2(0 - spacing, y); stop = stop_x_for_east(ix)
    elif dir == "W": y = lane_y_west(iy); pos = pygame.Vector2(WIDTH + spacing, y); stop = stop_x_for_west(ix)
    elif dir == "S": x = lane_x_south(ix); pos = pygame.Vector2(x, 0 - spacing); stop = stop_y_for_south(iy)
    else: x = lane_x_north(ix); pos = pygame.Vector2(x, HEIGHT + spacing); stop = stop_y_for_north(iy)
    return Vehicle(k, dir, pos, speed, size, color, stop, (y if dir in ("E","W") else x), inter)

# ---------------------------------
# RANDOM VEHICLE GENERATION
# ---------------------------------
def generate_random_phase_traffic():
    vehs = []
    for inter in INTERS:  # each phase
        for dir in ["N","S","E","W"]:
            # random count for each type
            cars = random.randint(1,3)
            bikes = random.randint(1,4)
            buses = random.randint(0,2)
            types = (["car"]*cars) + (["bike"]*bikes) + (["bus"]*buses)
            random.shuffle(types)
            for i, t in enumerate(types):
                vehs.append(spawn_vehicle(t, dir, inter, i))
    return vehs

# ---------------------------------
# SETUP
# ---------------------------------
vehicles = generate_random_phase_traffic()

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("🚦 Random Traffic per Phase/Direction")
font = pygame.font.SysFont(None, 36)
clock = pygame.time.Clock()

# ---------------------------------
# CSV SETUP
# ---------------------------------
CSV_FILE = "vehicle_type_counts.csv"
headers = ["Phase"]
for d in ["N", "S", "E", "W"]:
    for t in ["Car", "Bike", "Bus"]:
        headers.append(f"{d}_{t}")
with open(CSV_FILE, 'w', newline='') as f:
    csv.writer(f).writerow(headers)

def count_vehicles_by_type():
    counts = {i+1: {d: {"car":0,"bike":0,"bus":0} for d in ["N","S","E","W"]} for i in range(4)}
    for v in vehicles:
        if v.target_inters in INTERS:
            pid = INTERS.index(v.target_inters) + 1
            counts[pid][v.dir][v.kind] += 1
    return counts

# ---------------------------------
# DRAW SCENE
# ---------------------------------
def draw_scene(s):
    s.fill(CLR_BG)
    for y in [Y1,Y2]:
        pygame.draw.rect(s, CLR_ROAD, (0, y - ROAD_THICK//2, WIDTH, ROAD_THICK))
    for x in [X1,X2]:
        pygame.draw.rect(s, CLR_ROAD, (x - ROAD_THICK//2, 0, ROAD_THICK, HEIGHT))
    for i, (ix, iy) in enumerate(INTERS):
        pygame.draw.rect(s, CLR_INTER, (ix - INTER_HALF, iy - INTER_HALF, INTER_SIZE, INTER_SIZE))
        pygame.draw.line(s, CLR_STOP, (stop_x_for_east(ix), iy - 30), (stop_x_for_east(ix), iy + 30), 4)
        pygame.draw.line(s, CLR_STOP, (stop_x_for_west(ix), iy - 30), (stop_x_for_west(ix), iy + 30), 4)
        pygame.draw.line(s, CLR_STOP, (ix - 30, stop_y_for_south(iy)), (ix + 30, stop_y_for_south(iy)), 4)
        pygame.draw.line(s, CLR_STOP, (ix - 30, stop_y_for_north(iy)), (ix + 30, stop_y_for_north(iy)), 4)
        text = font.render(f"Phase {i+1}", True, CLR_TEXT)
        s.blit(text, text.get_rect(center=(ix, iy)))
    for v in vehicles:
        v.draw(s)

# ---------------------------------
# MAIN LOOP
# ---------------------------------
def main():
    run = True
    log_timer = 0
    while run:
        dt = clock.tick(FPS)/1000.0
        log_timer += dt

        for e in pygame.event.get():
            if e.type==pygame.QUIT or (e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE):
                run=False

        for v in vehicles:
            same = [u for u in vehicles if u.dir==v.dir and abs(u.lane_fix - v.lane_fix)<1]
            v.update(dt, same)

        draw_scene(screen)
        pygame.display.flip()

        # log CSV every 3 sec
        if log_timer>=3.0:
            counts = count_vehicles_by_type()
            with open(CSV_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                for pid in range(1,5):
                    row = [pid]
                    for d in ["N","S","E","W"]:
                        row += [counts[pid][d]["car"], counts[pid][d]["bike"], counts[pid][d]["bus"]]
                    writer.writerow(row)
            log_timer = 0

    pygame.quit(); sys.exit()

if __name__ == "__main__":
    main()
