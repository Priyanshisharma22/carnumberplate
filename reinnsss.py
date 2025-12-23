import pygame
import sys
import random
import math

WIDTH, HEIGHT = 1400, 1000
FPS = 60

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
pygame.display.set_caption("4 Intersection KM Network — Accurate Distances")

font_small = pygame.font.SysFont(None, 20)
font_med = pygame.font.SysFont(None, 24)
font_big = pygame.font.SysFont(None, 28)

KM = 80

D_I1_I2 = 4 * KM
D_I1_I3 = 6 * KM
D_I2_I4 = 5 * KM
D_I3_I4 = 6 * KM

INT_SIZE = 160
ROAD_WIDTH = 56

BG = (24, 24, 24)
BLOCK_BG = (34, 139, 34)
ROAD = (36, 36, 36)
LINE = (220, 220, 220)
SIGNAL_GREEN = (0, 200, 0)
SIGNAL_RED = (200, 0, 0)
TEXT_COLOR = (245, 245, 245)

BOX_BG = (255, 215, 0)
BOX_BORDER = (0, 0, 0)
BOX_TEXT = (0, 0, 0)

class Intersection:
    def __init__(self, name, cx, cy):
        self.name = name
        self.cx = int(cx)
        self.cy = int(cy)
        self.rect = pygame.Rect(self.cx - INT_SIZE//2, self.cy - INT_SIZE//2, INT_SIZE, INT_SIZE)

        self.traffic = {
            "N": {"car": random.randint(8,16), "bike": random.randint(10,22), "bus": random.randint(1,4)},
            "E": {"car": random.randint(8,16), "bike": random.randint(10,22), "bus": random.randint(1,4)},
            "S": {"car": random.randint(8,16), "bike": random.randint(10,22), "bus": random.randint(1,4)},
            "W": {"car": random.randint(8,16), "bike": random.randint(10,22), "bus": random.randint(1,4)}
        }

        self.order = ["N","E","S","W"]
        self.green_index = 0
        self.green = "N"
        self.green_timer = 0
        self.current_green_duration = self.calc_green_duration(
            sum(self.traffic["N"].values())
        )
        self.spawn_timer = 0

    @staticmethod
    def calc_green_duration(v):
        if v<=5: return 20000
        elif v<=9: return 30000
        elif v<=14: return 40000
        else: return 45000

    def dashed(self, surf, color, p1, p2, width=2, dash=12, gap=8):
        x1,y1 = p1; x2,y2 = p2
        length = math.hypot(x2-x1, y2-y1)
        if length <= 0: return
        dx = (x2-x1)/length
        dy = (y2-y1)/length
        d = 0
        while d < length:
            seg = min(dash, length-d)
            sx = x1 + dx*d
            sy = y1 + dy*d
            ex = x1 + dx*(d+seg)
            ey = y1 + dy*(d+seg)
            pygame.draw.line(surf, color, (sx,sy), (ex,ey), width)
            d += seg + gap

    def draw(self, surf, world_to_surf):
        rx,ry = world_to_surf(self.rect.left, self.rect.top)
        surf_rect = pygame.Rect(rx, ry, self.rect.width, self.rect.height)

        pygame.draw.rect(surf, BLOCK_BG, surf_rect)
        pygame.draw.rect(surf, ROAD, (surf_rect.left, surf_rect.centery-ROAD_WIDTH//2, surf_rect.width, ROAD_WIDTH))
        pygame.draw.rect(surf, ROAD, (surf_rect.centerx-ROAD_WIDTH//2, surf_rect.top, ROAD_WIDTH, surf_rect.height))

        self.dashed(surf, LINE, (surf_rect.left, surf_rect.centery), (surf_rect.right, surf_rect.centery), 3)
        self.dashed(surf, LINE, (surf_rect.centerx, surf_rect.top), (surf_rect.centerx, surf_rect.bottom), 3)

        sz=18; pad=8
        pygame.draw.rect(surf, SIGNAL_GREEN if self.green=="N" else SIGNAL_RED,
                         (surf_rect.centerx-sz//2, surf_rect.top+pad, sz, sz))
        pygame.draw.rect(surf, SIGNAL_GREEN if self.green=="S" else SIGNAL_RED,
                         (surf_rect.centerx-sz//2, surf_rect.bottom-pad-sz, sz, sz))
        pygame.draw.rect(surf, SIGNAL_GREEN if self.green=="E" else SIGNAL_RED,
                         (surf_rect.right-pad-sz, surf_rect.centery-sz//2, sz, sz))
        pygame.draw.rect(surf, SIGNAL_GREEN if self.green=="W" else SIGNAL_RED,
                         (surf_rect.left+pad, surf_rect.centery-sz//2, sz, sz))

        surf.blit(font_big.render(self.name, True, TEXT_COLOR),
                  (surf_rect.left+8, surf_rect.top+8))

        remaining = max(0, self.current_green_duration - self.green_timer)
        sec = math.ceil(remaining/1000)
        dir_text = f"GREEN → {self.green}"
        sec_text = f"{sec} sec left"

        box_w=260; box_h=84
        box_x = surf_rect.left + (surf_rect.width-box_w)//2
        box_y = surf_rect.top + (surf_rect.height-box_h)//2

        box_s = pygame.Surface((box_w,box_h), pygame.SRCALPHA)
        box_s.fill((10,10,10,160))
        pygame.draw.rect(box_s, (230,230,230), (0,0,box_w,box_h), 2)
        surf.blit(box_s, (box_x, box_y))

        d_s = font_med.render(dir_text, True, TEXT_COLOR)
        s_s = font_med.render(sec_text, True, TEXT_COLOR)
        surf.blit(d_s, d_s.get_rect(center=(box_x+box_w//2, box_y+box_h//2-10)))
        surf.blit(s_s, s_s.get_rect(center=(box_x+box_w//2, box_y+box_h//2+18)))

    def update(self, dt):
        total = sum(self.traffic[self.green].values())
        self.current_green_duration = self.calc_green_duration(total)

        self.green_timer += dt
        self.spawn_timer += dt

        if self.spawn_timer >= 1000:
            self.spawn_timer=0
            for d in self.order:
                t=self.traffic[d]
                t["car"]+=random.randint(0,3)
                t["bike"]+=random.randint(0,4)
                t["bus"]+=random.randint(0,1)

        side = self.traffic[self.green]
        side["car"] = max(1, side["car"]-random.randint(1,3))
        side["bike"] = max(1, side["bike"]-random.randint(1,4))
        if side["bus"]>1: side["bus"]-=1

        if self.green_timer >= self.current_green_duration:
            self.green_timer=0
            self.green_index=(self.green_index+1)%4
            self.green=self.order[self.green_index]

START_X, START_Y = 200, 200

I1_cx, I1_cy = START_X, START_Y
I2_cx, I2_cy = I1_cx + INT_SIZE + D_I1_I2, I1_cy
I3_cx, I3_cy = I1_cx, I1_cy + INT_SIZE + D_I1_I3
I4_cx, I4_cy = I2_cx, I3_cy + 0

I1=Intersection("Intersection 1", I1_cx, I1_cy)
I2=Intersection("Intersection 2", I2_cx, I2_cy)
I3=Intersection("Intersection 3", I3_cx, I3_cy)
I4=Intersection("Intersection 4", I4_cx, I4_cy)

intersections=[I1,I2,I3,I4]

min_x=min(it.cx for it in intersections)-300
min_y=min(it.cy for it in intersections)-300
max_x=max(it.cx for it in intersections)+300
max_y=max(it.cy for it in intersections)+300

WORLD_W=max_x-min_x
WORLD_H=max_y-min_y
world_origin_x=min_x
world_origin_y=min_y

world_surface=pygame.Surface((WORLD_W, WORLD_H)).convert_alpha()

cam_x=(WIDTH-WORLD_W)//2
cam_y=(HEIGHT-WORLD_H)//2
zoom=1.0
ZOOM_MIN=0.3
ZOOM_MAX=2.5

panning=False
pan_last=(0,0)

def world_to_surf(px,py):
    return int(px-world_origin_x), int(py-world_origin_y)

def draw_exact_road(surface, p1, p2):
    x1,y1=world_to_surf(*p1)
    x2,y2=world_to_surf(*p2)

    if x1==x2:
        pygame.draw.rect(surface, ROAD, (x1-ROAD_WIDTH//2, y1, ROAD_WIDTH, y2-y1))
        pygame.draw.line(surface, LINE, (x1, y1), (x1, y2), 3)
    else:
        pygame.draw.rect(surface, ROAD, (x1, y1-ROAD_WIDTH//2, x2-x1, ROAD_WIDTH))
        pygame.draw.line(surface, LINE, (x1, y1), (x2, y1), 3)

def draw_distance_text(surface, p1, p2, text):
    x1,y1=world_to_surf(*p1)
    x2,y2=world_to_surf(*p2)
    mx=(x1+x2)//2
    my=(y1+y2)//2
    surface.blit(font_small.render(text, True, TEXT_COLOR), (mx-20, my-15))

def draw_box(surface, text, wx, wy):
    sx,sy = world_to_surf(wx,wy)
    r=font_small.render(text, True, BOX_TEXT)
    w,h=r.get_size()
    rect=pygame.Rect(sx-w//2-8, sy-h//2-8, w+16, h+16)
    pygame.draw.rect(surface, BOX_BG, rect)
    pygame.draw.rect(surface, BOX_BORDER, rect, 2)
    surface.blit(r, (rect.x+8, rect.y+8))

def main():
    global cam_x,cam_y,zoom,panning,pan_last

    running=True
    while running:
        dt=clock.tick(FPS)

        for ev in pygame.event.get():
            if ev.type==pygame.QUIT:
                running=False

            elif ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_EQUALS or ev.key==pygame.K_PLUS:
                    old=zoom; zoom=min(ZOOM_MAX, zoom*1.15)
                    if zoom!=old:
                        mx,my=WIDTH//2,HEIGHT//2
                        c=zoom/old
                        cam_x=mx-(mx-cam_x)*c
                        cam_y=my-(my-cam_y)*c

                elif ev.key==pygame.K_MINUS or ev.key==pygame.K_UNDERSCORE:
                    old=zoom; zoom=max(ZOOM_MIN, zoom/1.15)
                    if zoom!=old:
                        mx,my=WIDTH//2,HEIGHT//2
                        c=zoom/old
                        cam_x=mx-(mx-cam_x)*c
                        cam_y=my-(my-cam_y)*c

                elif ev.key==pygame.K_LEFT: cam_x+=80
                elif ev.key==pygame.K_RIGHT: cam_x-=80
                elif ev.key==pygame.K_UP: cam_y+=80
                elif ev.key==pygame.K_DOWN: cam_y-=80

            elif ev.type==pygame.MOUSEBUTTONDOWN:
                if ev.button==1:
                    panning=True
                    pan_last=ev.pos
                elif ev.button==4:
                    mx,my=ev.pos
                    old=zoom; zoom=min(ZOOM_MAX, zoom*1.15)
                    if zoom!=old:
                        c=zoom/old
                        cam_x=mx-(mx-cam_x)*c
                        cam_y=my-(my-cam_y)*c
                elif ev.button==5:
                    mx,my=ev.pos
                    old=zoom; zoom=max(ZOOM_MIN, zoom/1.15)
                    if zoom!=old:
                        c=zoom/old
                        cam_x=mx-(mx-cam_x)*c
                        cam_y=my-(my-cam_y)*c

            elif ev.type==pygame.MOUSEBUTTONUP:
                if ev.button==1: panning=False

            elif ev.type==pygame.MOUSEMOTION:
                if panning:
                    mx,my=ev.pos
                    lx,ly=pan_last
                    cam_x+=mx-lx
                    cam_y+=my-ly
                    pan_last=(mx,my)

        for it in intersections:
            it.update(dt)

        world_surface.fill(BG)

        draw_exact_road(world_surface, (I1.cx, I1.cy), (I2.cx, I2.cy))
        draw_distance_text(world_surface, (I1.cx,I1.cy), (I2.cx,I2.cy), "4 km")

        draw_exact_road(world_surface, (I3.cx,I3.cy), (I4.cx,I4.cy))
        draw_distance_text(world_surface, (I3.cx,I3.cy), (I4.cx,I4.cy), "6 km")

        draw_exact_road(world_surface, (I1.cx,I1.cy), (I3.cx,I3.cy))
        draw_distance_text(world_surface, (I1.cx,I1.cy), (I3.cx,I3.cy), "6 km")

        draw_exact_road(world_surface, (I2.cx,I2.cy), (I4.cx,I4.cy))
        draw_distance_text(world_surface, (I2.cx,I2.cy), (I4.cx,I4.cy), "5 km")

        for it in intersections:
            it.draw(world_surface, world_to_surf)

        for it in intersections:
            draw_box(world_surface,
                     f"N: Cars {it.traffic['N']['car']} Bikes {it.traffic['N']['bike']} Bus {it.traffic['N']['bus']}",
                     it.cx, it.rect.top-40)

            draw_box(world_surface,
                     f"S: Cars {it.traffic['S']['car']} Bikes {it.traffic['S']['bike']} Bus {it.traffic['S']['bus']}",
                     it.cx, it.rect.bottom+40)

            draw_box(world_surface,
                     f"W: Cars {it.traffic['W']['car']} Bikes {it.traffic['W']['bike']} Bus {it.traffic['W']['bus']}",
                     it.rect.left-140, it.cy)

            draw_box(world_surface,
                     f"E: Cars {it.traffic['E']['car']} Bikes {it.traffic['E']['bike']} Bus {it.traffic['E']['bus']}",
                     it.rect.right+140, it.cy)

        scaled = pygame.transform.smoothscale(world_surface,
                                              (int(WORLD_W*zoom), int(WORLD_H*zoom)))

        screen.fill((10,10,10))
        screen.blit(scaled, (cam_x,cam_y))

        screen.blit(font_small.render(
            f"Zoom: {zoom:.2f} | Drag to pan | Wheel or +/- to zoom",
            True, (220,220,220)), (10,10))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
