```python
import pygame
import math
import numpy as np
import sys
import random
import json
import os
from pygame.locals import *
from OpenGL.GL import *

# ==========================================
# 1. 基础配置与音效引擎
# ==========================================
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
pygame.font.init()

WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT), DOUBLEBUF | OPENGL)
pygame.display.set_caption("Doom FPS - The Ultimate Edition")
pygame.event.set_grab(True)
pygame.mouse.set_visible(False)

def make_sfx(kind='pistol'):
    sr = 44100
    if kind == 'pistol':
        t = np.linspace(0, 0.1, int(sr * 0.1))
        wave = np.sin(2 * np.pi * 800 * np.exp(-15 * t) * t)
    elif kind == 'dead':
        t = np.linspace(0, 0.2, int(sr * 0.2))
        wave = np.random.uniform(-1, 1, len(t)) * np.exp(-12 * t)
    elif kind == 'hurt':
        t = np.linspace(0, 0.1, int(sr * 0.1))
        wave = np.random.uniform(-1, 1, len(t)) * 0.3
    elif kind == 'jump':
        t = np.linspace(0, 0.15, int(sr * 0.15))
        wave = np.sin(2 * np.pi * (300 + 500 * t) * t) * np.exp(-10 * t)
    else: # step
        t = np.linspace(0, 0.08, int(sr * 0.08))
        wave = np.sin(2 * np.pi * 60 * t) * np.exp(-10 * t)
    audio = (wave * 8000).astype(np.int16)
    return pygame.sndarray.make_sound(np.stack((audio, audio), axis=-1))

SFX = {
    'pistol': make_sfx('pistol'), 'dead': make_sfx('dead'),
    'hurt': make_sfx('hurt'), 'step': make_sfx('step'),
    'jump': make_sfx('jump')
}

# ==========================================
# 2. 纹理、文字引擎与资源
# ==========================================
def surface_to_texture(surface):
    tex_data = pygame.image.tostring(surface, "RGBA", True)
    w, h = surface.get_size()
    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, tex_data)
    return tex_id

def gen_pixel_sprite(ascii_art, color_map):
    lines = ascii_art.strip().split('\n')
    h, w = len(lines), len(lines[0])
    surf = pygame.Surface((w, h), SRCALPHA)
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            if char in color_map: surf.set_at((x, y), color_map[char])
    return surface_to_texture(surf)

def gen_wall_texture(base_color, dark_color, is_exit=False):
    surf = pygame.Surface((64, 64))
    surf.fill(base_color)
    if is_exit:
        for _ in range(20): pygame.draw.circle(surf, dark_color, (random.randint(0, 64), random.randint(0, 64)), 3)
        return surface_to_texture(surf)
    for y in range(0, 64, 16):
        offset = 8 if (y // 16) % 2 == 0 else 0
        for x in range(-offset, 64, 16): pygame.draw.rect(surf, dark_color, (x, y, 15, 15))
    return surface_to_texture(surf)

COLOR_PALETTE = {
    '.': (0,0,0,0), 'K': (20,20,20,255), 'M': (100,100,100,255),
    'W': (255,255,255,255), 'Y': (255,200,0,255), 'R': (255,50,50,255),
    'G': (50,180,50,255), 'D': (20,100,20,255)
}

TEX_GUN = gen_pixel_sprite("""
.......KK.......
......KMMK......
......KMMK......
......KMMK......
.....KMMMMK.....
....KMMMMMMK....
....KMMMMMMK....
...KMMMMMMMMK...
...KK......KK...
..KKKK....KKKK..
""", COLOR_PALETTE)

TEX_FLASH = gen_pixel_sprite("""
.......YY.......
......YYYY......
.....YYWWYY.....
....YYWWWYYY....
.....YYWWYY.....
......YYYY......
.......YY.......
""", COLOR_PALETTE)

TEX_ENEMY = gen_pixel_sprite("""
......KKKK......
.....KGGGGK.....
.....KGRRGK.....
......KGGK......
....KKGGGGKK....
...KG.GGGG.GK...
...K..GGGG..K...
......KKKK......
.....KD..DK.....
....KD....DK....
""", COLOR_PALETTE)

TEX_WALLS = {
    1: gen_wall_texture((150, 50, 50), (100, 30, 30)),
    2: gen_wall_texture((50, 150, 50), (30, 100, 30)),
    3: gen_wall_texture((100, 100, 150), (50, 50, 100)),
    9: gen_wall_texture((200, 50, 255), (255, 255, 255), True) # 出口传送门
}

# 文字纹理缓存
TEXT_CACHE = {}
def get_text_tex(text, size=32, color=(255, 255, 255)):
    key = (text, size, color)
    if key in TEXT_CACHE: return TEXT_CACHE[key]
    
    # 修复 1：更严谨的字体匹配机制，确保无论如何都能找到支持中文的字体
    font_list = ['microsoftyahei', 'msyh', 'simhei', 'simsun', 'arial']
    try:
        font = pygame.font.SysFont(font_list, size)
    except:
        font = pygame.font.Font(None, size)
        
    surf = font.render(text, True, color).convert_alpha() # 增加显式转换透明通道
    tex = surface_to_texture(surf)
    TEXT_CACHE[key] = (tex, surf.get_width(), surf.get_height())
    return TEXT_CACHE[key]

# ==========================================
# 3. 关卡数据与实体类
# ==========================================
TILE_SIZE = 100
LEVELS = [
    {
        "name": "第 1 关：觉醒",
        "story": "你在一座废弃的火星设施中醒来。\n空气中弥漫着危险的气息。\n找到紫色的能量传送门（数字9），逃离这里！\n\n[点击鼠标 或 按空格键 开始]",
        "map": [
            [1, 1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 2, 0, 9, 1],
            [1, 0, 1, 0, 2, 0, 0, 1],
            [1, 0, 1, 0, 0, 0, 2, 1],
            [1, 1, 1, 1, 1, 1, 1, 1]
        ],
        "enemies": 2
    },
    {
        "name": "第 2 关：深渊迷宫",
        "story": "干得漂亮，但危机才刚刚开始。\n怪物越来越多，利用你的跳跃能力（空格键）躲避攻击！\n\n[点击鼠标 或 按空格键 继续]",
        "map": [
            [3, 3, 3, 3, 3, 3, 3, 3, 3, 3],
            [3, 0, 0, 0, 0, 3, 0, 0, 9, 3],
            [3, 0, 2, 2, 0, 3, 0, 3, 3, 3],
            [3, 0, 0, 2, 0, 0, 0, 0, 0, 3],
            [3, 3, 0, 2, 2, 2, 2, 0, 2, 3],
            [3, 0, 0, 0, 0, 0, 0, 0, 0, 3],
            [3, 3, 3, 3, 3, 3, 3, 3, 3, 3]
        ],
        "enemies": 5
    },
    {
        "name": "终章：胜利逃脱",
        "story": "你找到了最终的逃生舱。\n你安全了！游戏通关！\n\n[点击鼠标 或 按 ESC 返回主菜单]",
        "map": [
            [1, 1, 1, 1, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 1, 1, 1, 1]
        ],
        "enemies": 0
    }
]

class Enemy:
    def __init__(self, x, y):
        self.x, self.y, self.alive, self.dist = x, y, True, 999

class BulletHole:
    def __init__(self, x, y, hit_z, is_floor=False):
        self.x, self.y, self.z, self.is_floor = x, y, hit_z, is_floor

# ==========================================
# 4. 游戏引擎核心类
# ==========================================
class GameEngine:
    def __init__(self):
        self.state = "MENU" # MENU, STORY, PLAY
        self.level_idx = 0
        self.score, self.deaths = 0, 0
        
        # 物理与玩家属性
        self.px, self.py, self.pz = 150.0, 150.0, 0.0
        self.pa, self.pitch = 0.0, 0.0
        self.vz = 0.0 
        self.is_jumping = False
        self.health = 100.0
        
        self.enemies, self.bullet_holes = [], []
        self.fire_timer, self.hurt_timer, self.walk_timer = 0, 0, 0
        self.clock = pygame.time.Clock()
        self.FOV, self.num_rays = math.pi / 3, 300 
        
        self.stars = [(random.uniform(-math.pi, math.pi), random.uniform(20, 500), random.uniform(1, 3)) for _ in range(200)]
        
        self.menu_options = ["新游戏 (New Game)", "读档 (Load Game)", "退出 (Quit)"]
        self.menu_idx = 0

    def load_level(self, idx):
        if idx >= len(LEVELS):
            self.state = "MENU"; return
        self.level_idx = idx
        self.map_data = LEVELS[idx]["map"]
        self.px, self.py, self.pz = 150.0, 150.0, 0.0
        self.pa, self.pitch, self.vz = 0.0, 0.0, 0.0
        self.health = 100.0
        self.bullet_holes.clear()
        
        self.enemies.clear()
        empty_slots = [(c * TILE_SIZE + 50, r * TILE_SIZE + 50) for r in range(len(self.map_data)) for c in range(len(self.map_data[0])) if self.map_data[r][c] == 0]
        if empty_slots:
            for _ in range(LEVELS[idx]["enemies"]):
                pos = random.choice(empty_slots)
                self.enemies.append(Enemy(pos[0], pos[1]))
        
        self.state = "STORY"
        
    def save_game(self):
        data = {"level": self.level_idx, "score": self.score, "deaths": self.deaths}
        with open("save.json", "w") as f: json.dump(data, f)
            
    def load_game_data(self):
        if os.path.exists("save.json"):
            with open("save.json", "r") as f: data = json.load(f)
            self.score, self.deaths = data.get("score", 0), data.get("deaths", 0)
            self.load_level(data.get("level", 0))

    def is_wall(self, x, y):
        mx, my = int(x / TILE_SIZE), int(y / TILE_SIZE)
        if 0 <= mx < len(self.map_data[0]) and 0 <= my < len(self.map_data):
            return self.map_data[my][mx] > 0
        return True

    # ---------- 渲染辅助工具 ----------
    def draw_rect(self, x, y, w, h, color):
        glDisable(GL_TEXTURE_2D)
        glColor3f(*color)
        glBegin(GL_QUADS)
        x1, y1 = (x / WIDTH) * 2 - 1, (y / HEIGHT) * 2 - 1
        x2, y2 = ((x + w) / WIDTH) * 2 - 1, ((y + h) / HEIGHT) * 2 - 1
        glVertex2f(x1, -y1); glVertex2f(x2, -y1); glVertex2f(x2, -y2); glVertex2f(x1, -y2)
        glEnd()

    def draw_tex_quad(self, tex_id, x, y, w, h, shade=1.0, tex_coords=(0,1,0,1)):
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glColor4f(shade, shade, shade, 1.0)
        glBegin(GL_QUADS)
        x1, y1 = (x / WIDTH) * 2 - 1, (y / HEIGHT) * 2 - 1
        x2, y2 = ((x + w) / WIDTH) * 2 - 1, ((y + h) / HEIGHT) * 2 - 1
        tx1, tx2, ty1, ty2 = tex_coords
        glTexCoord2f(tx1, ty1); glVertex2f(x1, -y2)
        glTexCoord2f(tx2, ty1); glVertex2f(x2, -y2)
        glTexCoord2f(tx2, ty2); glVertex2f(x2, -y1)
        glTexCoord2f(tx1, ty2); glVertex2f(x1, -y1)
        glEnd()
        
    def draw_text(self, text, x, y, size=32, color=(255,255,255), center=False):
        tex_id, tw, th = get_text_tex(text, size, color)
        if center: x -= tw / 2
        self.draw_tex_quad(tex_id, x, y, tw, th)

    def draw_circle(self, x, y, radius, color):
        glDisable(GL_TEXTURE_2D)
        glColor3f(*color)
        glBegin(GL_POLYGON)
        for i in range(12):
            theta = i * (math.pi / 6)
            glVertex2f(((x + math.cos(theta)*radius)/WIDTH)*2-1, -(((y + math.sin(theta)*radius)/HEIGHT)*2-1))
        glEnd()

    # ---------- 核心逻辑与渲染 ----------
    def run(self):
        # 修复 2：全局开启混合模式，防止所有未指定时带 Alpha 通道的渲染变为纯色方块
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        while True:
            self.clock.tick(60)
            glClear(GL_COLOR_BUFFER_BIT)
            
            if self.state == "MENU": self.handle_menu()
            elif self.state == "STORY": self.handle_story()
            elif self.state == "PLAY": self.handle_play()
                
            pygame.display.flip()

    def handle_menu(self):
        pygame.mouse.set_visible(True)
        pygame.event.set_grab(False)
        self.draw_rect(0, 0, WIDTH, HEIGHT, (0.05, 0.05, 0.1)) # 背景
        self.draw_text("DOOM FPS - PYTHON 3D", WIDTH/2, 100, 60, (255, 50, 50), True)
        
        mx, my = pygame.mouse.get_pos()
        clicked = False
        
        for event in pygame.event.get():
            if event.type == QUIT: sys.exit()
            if event.type == MOUSEBUTTONDOWN and event.button == 1:
                clicked = True
            if event.type == KEYDOWN:
                if event.key == K_UP: self.menu_idx = (self.menu_idx - 1) % 3
                if event.key == K_DOWN: self.menu_idx = (self.menu_idx + 1) % 3
                if event.key == K_RETURN: self.execute_menu()
                    
        for i, opt in enumerate(self.menu_options):
            opt_y = 300 + i * 60
            
            # 修复 3：添加鼠标悬停和点击检测框，真正可以“点击选项”
            if WIDTH/2 - 150 < mx < WIDTH/2 + 150 and opt_y - 20 < my < opt_y + 20:
                self.menu_idx = i
                if clicked:
                    self.execute_menu()
                    
            color = (255, 255, 0) if i == self.menu_idx else (255, 255, 255)
            self.draw_text(opt, WIDTH/2, opt_y, 40, color, True)
            
    def execute_menu(self):
        if self.menu_idx == 0: 
            self.score, self.deaths = 0, 0
            self.load_level(0) # 新游戏
        elif self.menu_idx == 1: 
            self.load_game_data() # 读档
        elif self.menu_idx == 2: 
            sys.exit() # 退出

    def handle_story(self):
        pygame.mouse.set_visible(True)
        pygame.event.set_grab(False)
        self.draw_rect(0, 0, WIDTH, HEIGHT, (0, 0, 0))
        lines = LEVELS[self.level_idx]["story"].split('\n')
        for i, line in enumerate(lines):
            self.draw_text(line, WIDTH/2, 150 + i*40, 30, (200, 200, 200), True)
            
        for event in pygame.event.get():
            if event.type == QUIT: sys.exit()
            # 支持按下空格、ESC、或者点击鼠标左键继续
            if (event.type == KEYDOWN and (event.key == K_SPACE or event.key == K_ESCAPE)) or (event.type == MOUSEBUTTONDOWN):
                if self.level_idx < len(LEVELS) - 1:
                    pygame.mouse.set_visible(False)
                    pygame.event.set_grab(True)
                    self.state = "PLAY"
                else:
                    self.state = "MENU"

    def handle_play(self):
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        
        # 1. 物理引擎 (重力与跳跃)
        if self.pz > 0 or self.vz != 0:
            self.vz -= 1.2 # 重力
            self.pz += self.vz
            if self.pz <= 0: # 落地
                self.pz, self.vz = 0.0, 0.0
                self.is_jumping = False
                SFX['step'].play()

        # 2. 输入与射击
        for event in pygame.event.get():
            if event.type == QUIT: sys.exit()
            if event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    self.save_game(); self.state = "MENU" # ESC保存并退出
                if event.key == K_SPACE and not self.is_jumping: # 跳跃
                    self.vz = 15.0
                    self.is_jumping = True
                    SFX['jump'].play()
            
            if event.type == MOUSEBUTTONDOWN and event.button == 1 and self.fire_timer <= 0:
                self.fire_timer = 12
                SFX['pistol'].play()
                s_ray, c_ray = math.sin(self.pa), math.cos(self.pa)
                wall_hit_dist, hit_x, hit_y = 9999, self.px, self.py
                
                for d in range(1, 800, 2):
                    tx, ty = self.px - s_ray * d, self.py + c_ray * d
                    if self.is_wall(tx, ty):
                        wall_hit_dist, hit_x, hit_y = d, tx + s_ray*2, ty - c_ray*2
                        break
                
                hit_list = []
                for en in self.enemies:
                    if en.alive:
                        dx, dy = en.x - self.px, en.y - self.py
                        err = (math.atan2(-dx, dy) - self.pa + math.pi) % (2 * math.pi) - math.pi
                        e_h = 15000 / (en.dist + 1)
                        if abs(err) < 0.15 and en.dist < 600 and abs(self.pitch + (self.pz * 300 / (en.dist+1))) < e_h / 2:
                            hit_list.append(en)
                
                if hit_list:
                    hit_list.sort(key=lambda e: e.dist)
                    if hit_list[0].dist < wall_hit_dist:
                        hit_list[0].alive = False
                        self.score += 1
                        SFX['dead'].play()
                else:
                    wall_render_h = 18000 / (wall_hit_dist + 1)
                    hit_z = self.pz - (self.pitch * wall_hit_dist / 300)
                    if abs(self.pitch) < wall_render_h / 2:
                        self.bullet_holes.append(BulletHole(hit_x, hit_y, hit_z))
                    elif self.pitch < -wall_render_h / 2:
                        floor_dist = 9000 / max(1, abs(self.pitch))
                        if floor_dist < 600:
                            self.bullet_holes.append(BulletHole(self.px - s_ray*floor_dist, self.py + c_ray*floor_dist, 0, True))
                    if len(self.bullet_holes) > 40: self.bullet_holes.pop(0)

        # 3. 移动与视角
        m_dx, m_dy = pygame.mouse.get_rel()
        self.pa = (self.pa + m_dx * 0.003 + math.pi) % (2 * math.pi) - math.pi
        self.pitch = max(-250, min(250, self.pitch - m_dy * 1.5))
        
        keys = pygame.key.get_pressed()
        nx, ny, moving = self.px, self.py, False
        if keys[K_w]: nx -= math.sin(self.pa)*4.0; ny += math.cos(self.pa)*4.0; moving = True
        if keys[K_s]: nx += math.sin(self.pa)*4.0; ny -= math.cos(self.pa)*4.0; moving = True
        if keys[K_d]: nx -= math.cos(self.pa)*4.0; ny -= math.sin(self.pa)*4.0; moving = True
        if keys[K_a]: nx += math.cos(self.pa)*4.0; ny += math.sin(self.pa)*4.0; moving = True
        
        if not self.is_wall(nx, self.py): self.px = nx
        if not self.is_wall(self.px, ny): self.py = ny
        if moving and not self.is_jumping and self.walk_timer % 18 == 0: SFX['step'].play()
        if moving: self.walk_timer += 1
        
        # 4. 终点检测 (传送门)
        if self.map_data[int(self.py / TILE_SIZE)][int(self.px / TILE_SIZE)] == 9:
            self.load_level(self.level_idx + 1)
            return

        # 5. 敌人 AI
        for en in self.enemies:
            if not en.alive: continue
            dx, dy = self.px - en.x, self.py - en.y
            en.dist = math.sqrt(dx*dx + dy*dy)
            if en.dist > 55:
                vx, vy = (dx/en.dist)*1.5, (dy/en.dist)*1.5
                if not self.is_wall(en.x + vx, en.y): en.x += vx
                if not self.is_wall(en.x, en.y + vy): en.y += vy
            else:
                self.health -= 0.6
                if pygame.time.get_ticks() % 500 < 30: SFX['hurt'].play(); self.hurt_timer = 5

        if self.health <= 0:
            self.deaths += 1; self.load_level(self.level_idx) 

        # ---------------- 渲染 ----------------
        self.draw_rect(0, 0, WIDTH, HEIGHT/2 + self.pitch, (0.02, 0.02, 0.05)) 
        for sa, sy, sz in self.stars:
            err = (sa - self.pa + math.pi) % (2 * math.pi) - math.pi
            if abs(err) < self.FOV:
                sx = (err / (self.FOV/2)) * (WIDTH/2) + (WIDTH/2)
                star_y = HEIGHT/2 - sy + self.pitch + (self.pz * 0.5) 
                if 0 <= star_y <= HEIGHT/2 + self.pitch: self.draw_rect(sx, star_y, sz, sz, (0.7, 0.7, 0.8))

        self.draw_rect(0, HEIGHT/2 + self.pitch, WIDTH, HEIGHT/2 - self.pitch, (0.08, 0.08, 0.08)) 
        
        z_buffer = [9999.0] * self.num_rays
        muzzle_flash = (self.fire_timer / 12.0) * 0.4 
        
        for i in range(self.num_rays):
            ra = self.pa - (self.FOV/2) + (i * (self.FOV/self.num_rays))
            s, c = math.sin(ra), math.cos(ra)
            
            for d in range(1, 800, 1): 
                tx, ty = self.px - s * d, self.py + c * d
                if self.is_wall(tx, ty):
                    dist = d * math.cos(self.pa - ra)
                    z_buffer[i] = dist
                    
                    offset_x, offset_y = tx % TILE_SIZE, ty % TILE_SIZE
                    hit_side = 1 if abs(offset_x - 50) > abs(offset_y - 50) else 0
                    tex_x = (offset_y if hit_side else offset_x) / TILE_SIZE
                    
                    shade = (1.5 / (1 + dist * 0.004)) * (math.cos(self.pa - ra) ** 2)
                    if hit_side == 1: shade *= 0.7
                    shade = min(1.0, shade + muzzle_flash / (1 + dist * 0.002))
                    
                    h = 18000 / (dist + 1)
                    block = self.map_data[int(ty/TILE_SIZE)][int(tx/TILE_SIZE)]
                    tex_id = TEX_WALLS.get(block, TEX_WALLS[1])
                    
                    wall_y = HEIGHT/2 - h/2 + self.pitch + (self.pz * 300 / (dist + 1))
                    self.draw_tex_quad(tex_id, i*(WIDTH/self.num_rays), wall_y, (WIDTH/self.num_rays)+1, h, shade, (tex_x, tex_x, 0, 1))
                    break

        for hole in self.bullet_holes:
            dx, dy = hole.x - self.px, hole.y - self.py
            dist = math.sqrt(dx*dx + dy*dy)
            err = (math.atan2(-dx, dy) - self.pa + math.pi) % (2 * math.pi) - math.pi
            if abs(err) < self.FOV:
                screen_x = (err / (self.FOV/2)) * (WIDTH/2) + (WIDTH/2)
                if hole.is_floor: screen_y = HEIGHT/2 + self.pitch + (9000 / dist) + (self.pz * 300 / (dist+1))
                else: screen_y = HEIGHT/2 + self.pitch + ((self.pz - hole.z) * 300 / (dist+1))
                
                idx = int(screen_x / (WIDTH/self.num_rays))
                if 0 <= idx < self.num_rays and dist <= z_buffer[idx] + 20:
                    self.draw_circle(screen_x, screen_y, 500 / (dist + 1), (0.05 + muzzle_flash*0.5,)*3)

        for en in self.enemies:
            if not en.alive: continue
            dx, dy = en.x - self.px, en.y - self.py
            err = (math.atan2(-dx, dy) - self.pa + math.pi) % (2 * math.pi) - math.pi
            if abs(err) < self.FOV:
                screen_x = (err / (self.FOV/2)) * (WIDTH/2) + (WIDTH/2)
                e_size = 15000 / (en.dist + 1)
                idx = int(screen_x / (WIDTH/self.num_rays))
                if 0 <= idx < self.num_rays and en.dist < z_buffer[idx] + 25:
                    e_shade = min(1.0, (1.0 / (1 + en.dist * 0.003)) + muzzle_flash)
                    e_y = HEIGHT/2 - e_size/2 + self.pitch + (self.pz * 300 / (en.dist+1))
                    self.draw_tex_quad(TEX_ENEMY, screen_x - e_size/2, e_y, e_size, e_size, e_shade)

        # UI & 武器
        gun_w, gun_h = 240, 240
        gun_y = HEIGHT - gun_h + math.sin(self.fire_timer * 0.5) * 30 + 20
        gun_y += min(15, max(-15, self.vz * 2)) 
        self.draw_tex_quad(TEX_GUN, WIDTH/2 - gun_w/2, gun_y, gun_w, gun_h)

        if self.fire_timer > 8:
            self.draw_tex_quad(TEX_FLASH, WIDTH/2 - 75, gun_y - 120, 150, 150)

        # 屏幕信息叠加
        self.draw_rect(WIDTH/2-10, HEIGHT/2-1, 20, 2, (0, 1, 0))
        self.draw_rect(WIDTH/2-1, HEIGHT/2-10, 2, 20, (0, 1, 0))
        self.draw_rect(20, 20, 300, 15, (0.2, 0, 0))
        self.draw_rect(20, 20, max(0, self.health) * 2, 15, (1, 0, 0))
        
        self.draw_text(f"杀敌数 (KILLS): {self.score}", WIDTH - 200, 20, 24, (0, 255, 0))
        self.draw_text(f"阵亡数 (DEATHS): {self.deaths}", WIDTH - 200, 50, 24, (100, 150, 255))
        self.draw_text(f"当前关卡: {self.level_idx + 1}", 20, 50, 20, (255, 255, 0))

        if self.hurt_timer > 0:
            glDisable(GL_TEXTURE_2D)
            glColor4f(1.0, 0.0, 0.0, 0.4)
            glBegin(GL_QUADS)
            glVertex2f(-1, -1); glVertex2f(1, -1); glVertex2f(1, 1); glVertex2f(-1, 1)
            glEnd()
            self.hurt_timer -= 1
            
        if self.fire_timer > 0: self.fire_timer -= 1

if __name__ == "__main__":
    game = GameEngine()
    game.run()


```
