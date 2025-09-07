
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import random
import time
import math
from enemy_shark import draw_shark as draw_enemy_shark, init_shark_assets as init_enemy_shark_assets

# ===================== Game variables =====================
player_lane = 1  # 0=left, 1=middle, 2=right
player_dive_depth = 0  # Current dive depth
dive_in_progress = False
player_shark_type = 0  # 0=great_white, 1=hammerhead
score = 0
lives = 3
game_over = False
cheat_mode = False  # Special mode where player isn't affected by collisions
game_speed = 6  # Base game speed
game_speed_factor = 1.0  # Modifier for special mode

#
# Base game speed + score-based progression
BASE_GAME_SPEED = 6           # starting speed at score 0
game_speed = BASE_GAME_SPEED  # current speed (will increase as you score)

# Increase speed every N points
SPEED_STEP_POINTS    = 10     # ← bump speed every 10 total score
SPEED_INCREASE_MODE  = "add"  # "add" for +1.5 each step; use "mul" for ×1.5 each step
SPEED_INCREASE_VALUE = 1.5
GAME_SPEED_MAX       = 30.0   # safety cap (optional)
next_speedup_at      = SPEED_STEP_POINTS  # internal marker for the next threshold

#

animation_time = 0  # For swimming animation
seaweed = []
ocean_width = 500  # Ocean width
seaweed_spawn_time = time.time()
seaweed_positions = [-300,0,300]
bubbles = []
bubble_spawn_time = time.time()
first_person = True 
FPV_Y_OFFSET = +5.0      # a bit above the body centerline
FPV_Z_FROM_NOSE = -42.0  # put camera at/near the snout (negative because model is rotated 180°)
# --- Camera mode toggle ---
use_fps_cam = False     # press 'F' to toggle
hide_player_in_fps = True  # don't draw the 3D shark model in FPS to avoid seeing inside it
now = time.time()

# FPS camera offsets (tweak to taste)
FPS_EYE_HEIGHT   = 10.0   # lift camera a bit from the shark's body
FPS_EYE_FORWARDZ =  -150.0   # camera sits roughly at the shark's z (0=at body; positive moves back)
FPS_LOOK_AHEADZ  = -250.0 # look towards negative Z (forward into the scene)

# ---- Player shark grow / eggs (from player demo, adapted) ----
player_scale_init = 1.9
player_scale = player_scale_init
player_scale_step = 0.4
player_scale_max = 16.0          # lay eggs when reaching 3×
# SCORE-BASED egg laying (pick ONE; set the other to None)
EGG_SCORE_TRIGGER = None         # e.g., 20 → lay eggs once when you reach 20 total score
EGG_EVERY_N_POINTS = 10          # e.g., 10 → lay eggs every 10 points; set to None to disable

space_flash_until = 0            # small HUD flash after grow

# AUTO growth per point (fish=+1, enemy kill=+5 after we patch bullets)
SCORE_GROW_PER_POINT = 0.06      # tune: 0.04 slower, 0.08 faster

egg_particles = []               # {'pos':[x,y,z],'vel':[vx,vy,vz],'birth':t,'life':s,'size':r}
egg_lifetime = 1.6
egg_buoyancy = 18.0
egg_count = 22

# ---- Death animation / blood pool (from player demo, adapted) ----
is_dead = False
death_t0 = 0.0
death_roll = 0.0      # clockwise roll (around Z)
death_pitch = 0.0     # nose-down (around X)
death_duration = 1.2

blood_active = False
blood_t0 = 0.0
blood_duration = 2.5
blood_max_radius = 120.0
# --- Enemy shark state ---
enemy_active = False
enemy_z = -2000
enemy_lane = 1
enemy_speed = 12
enemy_alive = False

# --- Bullets (for hammerhead only) ---
bullets = []
bullet_speed = 40.0

game_paused = False

##_________________3n3my shark
ENEMY_SPAWN_EVERY_N_FISH = 5
AUTO_FIRE_COOLDOWN = 0.30        # seconds between shots in cheat mode
AUTO_FIRE_MAX_RANGE_Z = 2400      # only shoot when the enemy is within 600 units ahead
last_auto_fire_time = 0.0

# ===================== Game objects =====================
class GameObject:
    def __init__(self, z_pos, lane, obj_type):
        self.z_pos = z_pos
        self.lane = lane  # 0=left, 1=middle, 2=right
        self.obj_type = obj_type  # 0=fish, 1=volcano, 2=power-up
        self.collected = False

class Seaweed(GameObject):
    def __init__(self, z_pos, side):
        super().__init__(z_pos, 0, 3)  # Using obj_type 3 for seaweed
        self.side = side  # -1 for left side, 1 for right side
        self.sway_offset = random.uniform(0, math.pi * 2)  # Random phase for swaying

class Bubble:
    def __init__(self, x_pos, y_pos, z_pos):
        self.x_pos = x_pos
        self.y_pos = y_pos
        self.z_pos = z_pos
        self.size = random.uniform(3, 12)
        self.rise_speed = random.uniform(2, 6)
        self.sway_offset = random.uniform(0, math.pi * 2)

# Current streams (underwater effect)
class CurrentStream:
    def __init__(self, z_pos, is_strong=True):
        self.z_pos = z_pos
        self.is_strong = is_strong  # True for strong current, False for weak

small_fish = []
volcanos = []
powerups = []
current_streams_left = []   # Left side current markings
current_streams_right = []  # Right side current markings
last_spawn_time = time.time()
last_stream_spawn_time = time.time()  # New timer for current streams
last_dive_time = 0
last_animation_update = time.time()
last_update_time = time.time()   # for per-frame dt (eggs, death, etc.)
Q = None

# Lane positions (x-coordinates) - deeper lanes
lane_positions = [-150, 0, 150]

# Camera-related variables
camera_pos = (0, 0, 550)
fovY = 40  # Field of view
OCEAN_DEPTH = 2000  # Length of ocean view
STREAM_LENGTH = 0   # Length of current markings
STREAM_GAP = 50     # Gap between current markings

# ===================== GL helpers / assets =====================
def init_shark_assets():
    """Call once after your GL context is created."""
    global Q
    if Q is None:
        Q = gluNewQuadric()
        gluQuadricNormals(Q, GLU_SMOOTH)
        gluQuadricTexture(Q, GL_FALSE)
    glEnable(GL_NORMALIZE)  # keep lighting correct after non-uniform scales

def _sphere(r, sl=28, st=18):
    gluSphere(Q, r, sl, st)

def _cyl(r1, r2, h, sl=28, st=12):
    gluCylinder(Q, r1, r2, h, sl, st)

def gluCone(quadric, base, height, slices, stacks):
    gluCylinder(quadric, base, 0.0, height, slices, stacks)
    glPushMatrix()
    glRotatef(180, 1, 0, 0)   # flip to face the base
    gluDisk(quadric, 0.0, base, slices, 1)
    glPopMatrix()

# --- Drop-in replacement for draw_text ---
# --- Replace your draw_text with this safe, self-contained version ---
def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    # Save & isolate the HUD draw state
    glPushAttrib(GL_ENABLE_BIT | GL_COLOR_BUFFER_BIT)
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    # 2D orthographic pass over the fixed window size (0..1000, 0..800)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, 1000, 0, 800)  # left, right, bottom, top

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glColor3f(1.0, 1.0, 1.0)
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))

    # Restore matrices
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

    # Restore GL state exactly as it was
    glPopAttrib()


# ===================== Player drawing =====================
def draw_player():
    global animation_time
    glPushMatrix()
    # Position shark in the correct lane
    glTranslatef(lane_positions[player_lane], -30 - player_dive_depth, 0)
    glRotatef(180, 0, 1, 0)  
    # Death transform applied to the whole player
    if is_dead:
        glRotatef(-death_roll, 0, 0, 1)   # clockwise roll
        glRotatef( death_pitch, 1, 0, 0)  # nose-down

    # Scale (grow animation)
    glScalef(player_scale, player_scale, player_scale)

    # Select shark based on player_shark_type value
    if player_shark_type == 0:  # Great White shark (improved model)
        draw_great_white_shark(animation_time, scale=1.0)
    else:  # Hammerhead shark
        draw_hammerhead_shark(animation_time)

    glPopMatrix()
    

def draw_great_white_shark(swim_phase=0.0, scale=1.0,
                           shade_top=(0.70, 0.73, 0.78),
                           shade_bottom=(0.95, 0.95, 1.00)):
    p = {
        'body_len': 2.4,
        'head_size': 13.5,
        'snout_size': 8.5,
        'stalk_len': 20.0,
        'dorsal_base': 6.5,
        'dorsal_height': 16.0,
        'pectoral_size': 6.3,
        'tail_lobe_len': 16.0,
    }

    wag     = math.sin(swim_phase * 8.0) * 30.0
    fin_osc = math.sin(swim_phase * 5.0) * 20.0

    glPushMatrix()                        # S0 (whole shark)
    glScalef(scale, scale, scale)

    glPushMatrix()                        # S1 (body sway group)
    glRotatef(wag * 0.12, 0, 1, 0)

    # Body main
    glPushMatrix()                        # S2
    glColor3f(*shade_top)
    glScalef(0.6, 0.8, p['body_len'])
    _sphere(20)
    glPopMatrix()                         # /S2

    # Belly underlay
    glPushMatrix()                        # S3
    glColor3f(*shade_bottom)
    glTranslatef(0, -3.7, 2.0)
    glScalef(1.05, 0.70, p['body_len'] * 0.7)
    _sphere(17.3)
    glPopMatrix()                         # /S3

    # Head + snout
    glPushMatrix()                        # S4
    glColor3f(*shade_top)
    glTranslatef(0, 2.0, 37.0)
    glRotatef(wag * 0.08, 0, 1, 0)
    glScalef(2.18, 0.50, 0.95)
    _sphere(p['head_size'])
    glPopMatrix()                         # /S4

    glPushMatrix()                        # S5
    glTranslatef(0, 0.0, 40.0)
    glScalef(0.92, 0.78, 0.92)
    _sphere(p['snout_size'])
    glPopMatrix()                         # /S5

    # Eyes
    for sx in (-28.0, 28.0):
        glPushMatrix()                    # S6a/b
        glColor3f(0.06, 0.06, 0.06)
        glTranslatef(sx, 3.0, 40.0)
        _sphere(1.9, 14, 10)
        glPopMatrix()                     # /S6a/b

    # GILL SLITS (both sides)
    gill_count, gill_spacing = 5, 2.2
    gill_x, gill_y, gill_z0  = 10, 3.5, 25.0
    gill_len, gill_thin      = 3.0, 0.80
    gill_color               = (0.18, 0.2, 0.24)
    for side in (-1, 1):
        for i in range(gill_count):
            glPushMatrix()                # S7*
            glTranslatef(side * gill_x, gill_y, gill_z0 - i * gill_spacing)
            glColor3f(*gill_color)
            glRotatef(-90, 0, 0, 1)      # horizontal slit
            glScalef(gill_len, gill_thin, 0.5)
            _sphere(1, 15, 8)
            glPopMatrix()                 # /S7*

    # Dorsal fin (sleek, raked, sideways sway)
    glPushMatrix()                        # S8
    glColor3f(shade_top[0]*0.85, shade_top[1]*0.85, shade_top[2]*0.85)
    dorsal_offset = (0.0, 11.0, -7.0)
    glTranslatef(*dorsal_offset)
    glRotatef(math.sin(swim_phase * 4.0) * 6.0, 0, 1, 0)
    glRotatef(-90, 1, 0, 0)
    glRotatef(-30.0, 1, 0, 0)
    glScalef(0.32, 1.0, 0.9)
    glutSolidCone(p['dorsal_base'] * 1.50, p['dorsal_height'] * 1.72, 24, 1)
    glPopMatrix()                         # /S8

    glPushMatrix()                        # S9 (fillet)
    glTranslatef(*dorsal_offset)
    glScalef(1.0, 0.35, 0.9)
    _sphere(p['dorsal_base'] * 0.85, 18, 14)
    glPopMatrix()                         # /S9

    # Pectoral fins
    for side in (-1, 1):
        glPushMatrix()                    # S10a/b
        glTranslatef(12*side, -6.5, 8.0)
        glRotatef(45, 1, 0, 0)
        glRotatef(side*(1 + fin_osc*0.9), 0, 0, 1)
        glScalef(2.9, 0.30, 1.0)
        _sphere(p['pectoral_size'], 18, 12)
        glPopMatrix()                     # /S10a/b

    # Tail stalk (pivot at body joint)
    glPushMatrix()                        # S11
    glTranslatef(0, 0, -48)
    glRotatef(wag, 0, 1, 0)
    glTranslatef(0, 0, -18)
    glPushMatrix()                        # S11a
    glScalef(0.42, 1, 1.2)
    _cyl(9.0, 6.0, p['stalk_len'])
    glPopMatrix()                         # /S11a
    # (optional marker)
    # glDisable(GL_LIGHTING); glColor3f(1,0,0); glutSolidSphere(2,10,10); glEnable(GL_LIGHTING)
    glPopMatrix()                         # /S11

    # Caudal fin (pivot at tail tip)
    glPushMatrix()                        # S12
    glTranslatef(0, 0, -48)
    glRotatef(wag, 0, 1, 0)
    glTranslatef(0, 0, -18)
    glColor3f(shade_top[0]*0.9, shade_top[1]*0.9, shade_top[2]*0.9)
    R = 10.0; H = p['tail_lobe_len']
    def tail_lobe(tilt_deg, length_scale=1.0):
        glPushMatrix()                    # S12a/b
        glRotatef(180, 0, 1, 0)
        glRotatef(tilt_deg, 1, 0, 0)
        glScalef(0.35, 1.0, 2.6*length_scale)
        glutSolidCone(R, H*length_scale, 20, 1)
        glPopMatrix()                     # /S12a/b
    tail_lobe(+45, 1.00)
    tail_lobe(-45, 1.00)
    glPopMatrix()                         # /S12

    glPopMatrix()                         # /S1 (body sway)
    glPopMatrix()                         # /S0 (whole shark)


def draw_hammerhead_shark(swim_phase=0.0, scale=1.0,
                          shade_top=(0.55, 0.42, 0.32),    # brown top
                          shade_bottom=(0.93, 0.88, 0.80)): # warm tan belly
    # proportions similar to great white, slightly tweaked
    p = {
        'body_len': 2.35,
        'head_size': 12.5,     # a bit slimmer head base
        'snout_len': 12.0,     # pointy snout length (cone)
        'snout_base': 4.6,     # pointy snout base radius (at face)
        'stalk_len': 20.0,
        'dorsal_base': 6.3,
        'dorsal_height': 16.5,
        'pectoral_size': 6.1,
        'tail_lobe_len': 16.0,
    }

    wag     = math.sin(swim_phase * 8.0) * 30.0
    fin_osc = math.sin(swim_phase * 5.0) * 20.0

    glPushMatrix()                        # H0 (whole shark)
    glScalef(scale, scale, scale)

    glPushMatrix()                        # H1 (body sway group)
    glRotatef(wag * 0.12, 0, 1, 0)

    # --- BODY ---
    glPushMatrix()                        # H2
    glColor3f(*shade_top)
    glScalef(0.58, 0.80, p['body_len'])   # slightly slimmer than GW
    _sphere(20)
    glPopMatrix()                         # /H2

    # --- BELLY UNDERLAY ---
    glPushMatrix()                        # H3
    glColor3f(*shade_bottom)
    glTranslatef(0, -3.7, 2.0)
    glScalef(1.05, 0.68, p['body_len'] * 0.70)
    _sphere(17.3)
    glPopMatrix()                         # /H3

    # --- HEAD BASE (slimmer “face” area) ---
    glPushMatrix()                        # H4
    glColor3f(*shade_top)
    glTranslatef(0, 1.8, 36.5)
    glRotatef(wag * 0.08, 0, 1, 0)
    glScalef(1.65, 0.55, 0.95)            # narrower than GW head base
    _sphere(p['head_size'])
    glPopMatrix()                         # /H4

    # --- POINTY SNOUT (cone pointing forward +Z) ---
    glPushMatrix()                        # H5
    # place cone base just in front of the head base
    glTranslatef(0, 1.6, 42.0)
    # GLUT cone is along +Z, base at origin → perfect for forward snout
    glColor3f(*shade_top)
    glutSolidCone(p['snout_base'], p['snout_len'], 24, 1)
    glPopMatrix()                         # /H5

    # --- EYES (amber/brownish) ---
    for sx in (-23.0, 23.0):
        glPushMatrix()                    # H6a/b
        glColor3f(0.85, 0.45, 0.12)       # warm amber eye
        glTranslatef(sx, 2.5, 38.5)
        _sphere(2.2, 16, 12)
        glPopMatrix()                     # /H6a/b

    # --- GILL SLITS (same style as GW) ---
    gill_count, gill_spacing = 5, 2.2
    gill_x, gill_y, gill_z0  = 9.5, 3.2, 25.0
    gill_len, gill_thin      = 3.0, 0.80
    gill_color               = (0.18, 0.2, 0.24)
    for side in (-1, 1):
        for i in range(gill_count):
            glPushMatrix()                # H7*
            glTranslatef(side * gill_x, gill_y, gill_z0 - i * gill_spacing)
            glColor3f(*gill_color)
            glRotatef(-90, 0, 0, 1)      # horizontal slit
            glScalef(gill_len, gill_thin, 0.5)
            _sphere(1, 15, 8)
            glPopMatrix()                 # /H7*

    # --- DORSAL FIN (sleek + slight sway) ---
    glPushMatrix()                        # H8
    glColor3f(shade_top[0]*0.85, shade_top[1]*0.85, shade_top[2]*0.85)
    dorsal_offset = (0.0, 11.0, -7.0)
    glTranslatef(*dorsal_offset)
    glRotatef(math.sin(swim_phase * 4.0) * 6.0, 0, 1, 0)
    glRotatef(-90, 1, 0, 0)
    glRotatef(-28.0, 1, 0, 0)
    glScalef(0.30, 1.0, 0.9)
    glutSolidCone(p['dorsal_base'] * 1.45, p['dorsal_height'] * 1.70, 24, 1)
    glPopMatrix()                         # /H8

    # base fillet for dorsal
    glPushMatrix()                        # H9
    glTranslatef(*dorsal_offset)
    glScalef(1.0, 0.34, 0.9)
    _sphere(p['dorsal_base'] * 0.82, 18, 14)
    glPopMatrix()                         # /H9

    # --- PECTORAL FINS ---
    for side in (-1, 1):
        glPushMatrix()                    # H10a/b
        glTranslatef(12*side, -6.5, 8.0)
        glRotatef(45, 1, 0, 0)
        glRotatef(side*(1 + fin_osc*0.9), 0, 0, 1)
        glScalef(2.8, 0.28, 1.0)
        _sphere(p['pectoral_size'], 18, 12)
        glPopMatrix()                     # /H10a/b

    # --- TAIL STALK (pivot at body joint) ---
    glPushMatrix()                        # H11
    glTranslatef(0, 0, -48)
    glRotatef(wag, 0, 1, 0)
    glTranslatef(0, 0, -18)
    glPushMatrix()                        # H11a
    glScalef(0.42, 1, 1.2)
    _cyl(9.0, 6.0, p['stalk_len'])
    glPopMatrix()                         # /H11a
    glPopMatrix()                         # /H11

    # --- CAUDAL (tail) V fins (pivot at tip) ---
    glPushMatrix()                        # H12
    glTranslatef(0, 0, -48)
    glRotatef(wag, 0, 1, 0)
    glTranslatef(0, 0, -18)
    glColor3f(shade_top[0]*0.9, shade_top[1]*0.9, shade_top[2]*0.9)
    R = 10.0; H = p['tail_lobe_len']
    def _tail_lobe(tilt_deg, length_scale=1.0):
        glPushMatrix()
        glRotatef(180, 0, 1, 0)          # point back along -Z
        glRotatef(tilt_deg, 1, 0, 0)     # ±45°
        glScalef(0.35, 1.0, 2.6*length_scale)
        glutSolidCone(R, H*length_scale, 20, 1)
        glPopMatrix()
    _tail_lobe(+45, 1.00)
    _tail_lobe(-45, 1.00)
    glPopMatrix()   

    # --- Eye cannons (one per eye, NO SWAY) ---
    # Put this right after the Eyes loop and before the gill slits.
    cannon_len = 108.0
    cannon_rad = 4.2
    cannon_splay = 4.0   # slight outward yaw so they’re not perfectly parallel

    for sx in (-23.0, 23.0):
        glPushMatrix()
        glTranslatef(sx, 3.0, 40.0)       # same base position as the eyes

        # Cancel the parent's sway so barrels stay steady
        glRotatef(-wag * 0.12, 0, 1, 0)

        # Aim barrels roughly forward (+Z); splay them a touch outward
        glRotatef(cannon_splay if sx > 0 else -cannon_splay, 0, 1, 0)

        # Barrel (simple cylinder along +Z)
        glColor3f(0.55, 0.55, 0.58)       # metallic gray
        _cyl(cannon_rad, cannon_rad, cannon_len)

        # Muzzle (dark ring cap + short cone)
        glTranslatef(0.0, 0.0, cannon_len)
        glColor3f(0.20, 0.20, 0.22)
        gluDisk(Q, 0.0, cannon_rad, 20, 1)      # flat cap
        glColor3f(0.30, 0.30, 0.33)
        glutSolidCone(cannon_rad * 0.85, 4.0, 16, 1)

        glPopMatrix()
                    

    glPopMatrix() 
                            # /H1
    glPopMatrix()  
    
                           # /H0


# ===================== World / objects =====================
def draw_small_fish(lane, z_pos):
    tail_wag = math.sin(time.time() * 6 + z_pos * 0.05) * 15  # Tail sway
    fin_flap = math.sin(time.time() * 8 + z_pos * 0.03) * 10  # Fins flap

    glPushMatrix()
    # Position the fish
    glTranslatef(lane_positions[lane], -30, z_pos)
    glRotatef(tail_wag, 0, 1, 0)

    # Body (torpedo shape)
    glPushMatrix()
    glColor3f(0.9, 0.6, 0.2)  # Base orange
    glScalef(0.6, 0.5, 1.4)
    _sphere(10)
    glPopMatrix()

    # Belly (lighter tone)
    glPushMatrix()
    glColor3f(1.0, 0.85, 0.6)
    glTranslatef(0, -2, 0)
    glScalef(0.55, 0.35, 1.2)
    _sphere(9)
    glPopMatrix()

    # Head
    glPushMatrix()
    glColor3f(0.9, 0.55, 0.15)
    glTranslatef(0, 0, 10)
    glScalef(0.7, 0.5, 0.7)
    _sphere(8)
    glPopMatrix()

    # Eyes
    for sx in (-3.5, 3.5):
        glPushMatrix()
        glTranslatef(sx, 1.5, 12)
        glColor3f(0.05, 0.05, 0.05)
        _sphere(1.2, 12, 12)
        glPopMatrix()

    # Pectoral fins
    for side in (-1, 1):
        glPushMatrix()
        glTranslatef(side * 4, -1, 5)
        glRotatef(side * fin_flap, 1, 0, 0)
        glScalef(0.3, 0.05, 0.8)
        _sphere(5)
        glPopMatrix()

    # Dorsal fin
    glPushMatrix()
    glTranslatef(0, 4, 3)
    glRotatef(fin_flap, 1, 0, 0)
    glScalef(0.1, 0.5, 0.7)
    _sphere(4)
    glPopMatrix()

    # Tail (caudal fin)
    glPushMatrix()
    glTranslatef(0, 0, -12)
    glRotatef(tail_wag * 1.5, 0, 1, 0)
    # upper lobe
    glPushMatrix()
    glTranslatef(0, 2, 0)
    glScalef(0.1, 0.5, 0.8)
    _sphere(5)
    glPopMatrix()
    # lower lobe
    glPushMatrix()
    glTranslatef(0, -2, 0)
    glScalef(0.1, 0.5, 0.8)
    _sphere(5)
    glPopMatrix()
    glPopMatrix()  # tail

    glPopMatrix()

def draw_volcano(lane, z_pos):
    glPushMatrix()
    glTranslatef(lane_positions[lane], -100, z_pos)
    glColor3f(0.3, 0.2, 0.1)
    glRotatef(-90, 1, 0, 0)
    gluCone(gluNewQuadric(), 60, 120, 12, 12)
    glPushMatrix()
    glTranslatef(0, 0, 120)
    glColor3f(1.0, 0.3, 0.0)
    gluSphere(gluNewQuadric(), 15, 8, 8)
    glPopMatrix()
    glColor3f(0.4, 0.3, 0.2)
    glPushMatrix(); glTranslatef(20, 0, 40); gluCylinder(gluNewQuadric(), 15, 0, 30, 6, 6); glPopMatrix()
    glPushMatrix(); glTranslatef(-25, 0, 60); gluCylinder(gluNewQuadric(), 12, 0, 25, 6, 6); glPopMatrix()
    glPushMatrix(); glTranslatef(15, 0, 80); gluCylinder(gluNewQuadric(), 10, 0, 20, 6, 6); glPopMatrix()
    glPopMatrix()

def draw_powerup(lane, z_pos):
    glPushMatrix()
    # Position (same place as before)
    glTranslatef(lane_positions[lane], 20, z_pos)

    # Idle animation: gentle bob + spin + slight pulse
    t = time.time()
    bob = math.sin(t * 3.0 + z_pos * 0.02) * 2.5
    glTranslatef(0.0, bob, 0.0)
    glRotatef((t * 80.0) % 360.0, 0, 1, 0)
    pulse = 1.00 + 0.10 * math.sin(t * 4.0)
    glScalef(pulse, pulse, pulse)

    # Draw the heart itself (red)
    draw_heart(scale=1.0, color=(0.95, 0.10, 0.15))

    # Optional: soft glow halo for visibility (keeps state local)
    was_blend    = glIsEnabled(GL_BLEND)
    was_light    = glIsEnabled(GL_LIGHTING)
    glDisable(GL_LIGHTING)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(1.0, 0.2, 0.2, 0.18)
    glutSolidSphere(12.0, 16, 12)
    if not was_blend: glDisable(GL_BLEND)
    if was_light: glEnable(GL_LIGHTING)

    glPopMatrix()


def draw_bubble(bubble):
    glPushMatrix()
    sway = math.sin(time.time() * 2 + bubble.sway_offset) * 10
    glTranslatef(bubble.x_pos + sway, bubble.y_pos, bubble.z_pos)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(0.8, 0.9, 1.0, 0.3)
    gluSphere(gluNewQuadric(), bubble.size, 8, 8)
    glDisable(GL_BLEND)
    glPopMatrix()

def draw_current_stream(x_pos, z_pos, is_strong):
    glPushMatrix()
    glTranslatef(x_pos, -50, z_pos)
    glColor3f(0.0, 0.4, 0.8) if is_strong else glColor3f(0.3, 0.6, 0.9)
    glRotatef(-90, 1, 0, 0)
    gluCylinder(gluNewQuadric(), 4, 4, STREAM_LENGTH, 8, 4)
    glPopMatrix()

def draw_seaweed(side, z_pos):
    glPushMatrix()

    # choose x from (-1,0,+1) using the positions list
    if side == -1:
        x_pos = seaweed_positions[0]
    elif side == 0:
        x_pos = seaweed_positions[1]
    else:
        x_pos = seaweed_positions[2]

    glTranslatef(x_pos, -80, z_pos)  # rooted in the seafloor

    # stronger, slower sway for tall kelp
    sway_factor = math.sin(time.time() * 1.3 + z_pos * 0.03) * 22
    glRotatef(sway_factor, 0, 0, 1)

    # TALL main stalk
    stalk_height = 160.0   # was ~60; now really tall
    glColor3f(0.0, 0.42, 0.22)
    glRotatef(-90, 1, 0, 0)
    gluCylinder(gluNewQuadric(), 3.0, 2.0, stalk_height, 10, 6)

    # More & larger fronds up the stalk
    glColor3f(0.22, 0.72, 0.36)
    for i in range(10):  # more fronds
        height = 18 + i * (stalk_height / 10.0)
        glPushMatrix()
        glTranslatef(0, 0, height)
        glRotatef(i * 32, 0, 0, 1)  # spiral around stalk
        glScalef(2.4, 0.14, 1.1)    # larger leaf
        gluSphere(gluNewQuadric(), 9.0, 10, 8)
        glPopMatrix()

    glPopMatrix()

# === New: heart mesh (two lobes + bottom tip) ===
def draw_heart(scale=1.0, color=(0.95, 0.10, 0.15)):
    """
    Draws a simple stylized heart, centered roughly around the origin.
    scale=1.0 renders a heart ~26 units tall; raise/lower to taste.
    """
    glPushMatrix()
    glColor3f(*color)

    # Base shape numbers (feel free to tweak)
    r = 8.0 * scale      # lobe radius
    l = r * 0.85         # lobe horizontal offset
    top = r * 0.85       # lobe vertical offset
    tip_h = r * 2.2      # bottom tip (cone) height
    base = r * 1.6       # bottom tip base radius

    # Left lobe
    glPushMatrix()
    glTranslatef(-l, top, 0.0)
    glutSolidSphere(r, 20, 16)
    glPopMatrix()

    # Right lobe
    glPushMatrix()
    glTranslatef(+l, top, 0.0)
    glutSolidSphere(r, 20, 16)
    glPopMatrix()

    # Center fill to soften the valley between lobes
    glPushMatrix()
    glTranslatef(0.0, top * 0.55, 0.0)
    glScalef(1.4, 0.8, 1.0)
    glutSolidSphere(r * 0.7, 18, 14)
    glPopMatrix()

    # Bottom tip: a cone pointing down along -Y
    glPushMatrix()
    glTranslatef(0.0, top * 0.55, 0.0)
    glRotatef(+90.0, 1, 0, 0)     # +Z -> -Y
    glutSolidCone(base, tip_h, 24, 1)
    glPopMatrix()

    glPopMatrix()


def draw_game_objects():
    for fish in small_fish:
        if not fish.collected:
            draw_small_fish(fish.lane, fish.z_pos)
    for volcano in volcanos:
        draw_volcano(volcano.lane, volcano.z_pos)
    for powerup in powerups:
        if not powerup.collected:
            draw_powerup(powerup.lane, powerup.z_pos)
    for stream in current_streams_left:
        draw_current_stream(-75, stream.z_pos, stream.is_strong)
    for stream in current_streams_right:
        draw_current_stream(75, stream.z_pos, stream.is_strong)
    for weed in seaweed:
        draw_seaweed(weed.side, weed.z_pos)
    for bubble in bubbles:
        draw_bubble(bubble)
    # --- enemy shark ---
    if enemy_active and enemy_alive:
        glPushMatrix()
        glTranslatef(lane_positions[enemy_lane], -30, enemy_z)
        draw_enemy_shark(swim_phase=animation_time)
        glPopMatrix()

    # --- bullets ---
    draw_bullets()

def draw_ocean_floor():
    glBegin(GL_QUADS)
    glColor3f(0.8, 0.7, 0.5)
    glVertex3f(-ocean_width, -100, -OCEAN_DEPTH)
    glVertex3f(ocean_width, -100, -OCEAN_DEPTH)
    glVertex3f(ocean_width, -100, OCEAN_DEPTH)
    glVertex3f(-ocean_width, -100, OCEAN_DEPTH)
    glColor3f(0.6, 0.4, 0.3)
    glVertex3f(-ocean_width - 100, -80, -OCEAN_DEPTH)
    glVertex3f(-ocean_width, -80, -OCEAN_DEPTH)
    glVertex3f(-ocean_width, -80, OCEAN_DEPTH)
    glVertex3f(-ocean_width - 100, -80, OCEAN_DEPTH)
    glVertex3f(ocean_width, -80, -OCEAN_DEPTH)
    glVertex3f(ocean_width + 100, -80, -OCEAN_DEPTH)
    glVertex3f(ocean_width + 100, -80, OCEAN_DEPTH)
    glVertex3f(ocean_width, -80, OCEAN_DEPTH)
    glColor3f(0.0, 0.3, 0.8)
    glVertex3f(-ocean_width * 2, 200, -OCEAN_DEPTH)
    glVertex3f(ocean_width * 2, 200, -OCEAN_DEPTH)
    glVertex3f(ocean_width * 2, 200, OCEAN_DEPTH)
    glVertex3f(-ocean_width * 2, 200, OCEAN_DEPTH)
    glEnd()

# ===================== Player updates =====================
def update_player_dive():
    # Same timing/shape as before; we just flip the sign so it becomes a jump.
    # Peak at t = 0.5; duration = 1s; amplitude ≈ 80 (your original value).
    global player_dive_depth, dive_in_progress, last_dive_time
    if dive_in_progress:
        elapsed_time = time.time() - last_dive_time
        if elapsed_time < 1.0:
            jump = 4.0 * 80.0 * elapsed_time * (1.0 - elapsed_time)  # 0 → 80 → 0
            player_dive_depth = -jump  # NEGATIVE = up (since you do -30 - player_dive_depth)
        else:
            player_dive_depth = 0.0
            dive_in_progress = False

def update_animation():
    global animation_time, last_animation_update
    current_time = time.time()
    animation_time += (current_time - last_animation_update) * game_speed_factor
    last_animation_update = current_time

def on_points_scored(points):
    """Apply growth and egg logic whenever score increases by 'points'."""
    global player_scale, space_flash_until, score

    # 1) auto-grow by points
    player_scale = min(player_scale_max, player_scale + points * SCORE_GROW_PER_POINT)
    space_flash_until = time.time() + 0.3   # brief 'GROW +size' HUD flash

    # 2) lay eggs if scale cap reached
    if player_scale >= player_scale_max - 1e-6:
        spawn_tail_eggs_and_reset()        # resets scale back to player_scale_init
        return

    # 3) score-based egg triggers
    prev = score - points
    if (EGG_SCORE_TRIGGER is not None) and (prev < EGG_SCORE_TRIGGER <= score):
        spawn_tail_eggs_and_reset()
    elif (EGG_EVERY_N_POINTS is not None) and ((prev // EGG_EVERY_N_POINTS) != (score // EGG_EVERY_N_POINTS)):
        spawn_tail_eggs_and_reset()

    apply_speed_progression()


# ---- Eggs system ----
def spawn_eggs(origin, count=egg_count):
    now = time.time()
    for _ in range(count):
        theta = random.uniform(0.0, 2.0*math.pi)
        speed = random.uniform(5.0, 65.0)
        vx = math.cos(theta) * speed
        vz = math.sin(theta) * speed
        vy = random.uniform(20.0, 55.0)
        egg_particles.append({
            'pos': [origin[0], origin[1], origin[2]],
            'vel': [vx, vy, vz],
            'birth': now,
            'life': egg_lifetime,
            'size': random.uniform(10.0, 40.2)
        })

def spawn_tail_eggs_and_reset():
    """Spawn eggs from player tail (world coords) and reset scale."""
    global player_scale
    # Player world root is at (lane_x, -30 - dive, 0)
    lane_x = lane_positions[player_lane]
    root_y = -30 - player_dive_depth
    tail_z = 66.0 * player_scale    # model tail offset behind root
    origin = (lane_x, root_y, tail_z)
    spawn_eggs(origin)
    player_scale = player_scale_init

def update_eggs(dt):
    if not egg_particles:
        return
    drag = pow(0.92, dt*60.0)
    now = time.time()
    dead = []
    for e in egg_particles:
        e['vel'][1] += egg_buoyancy * dt
        e['vel'][0] *= drag; e['vel'][1] *= drag; e['vel'][2] *= drag
        e['pos'][0] += e['vel'][0] * dt
        e['pos'][1] += e['vel'][1] * dt
        e['pos'][2] += e['vel'][2] * dt
        if (now - e['birth']) > e['life']:
            dead.append(e)
    for e in dead:
        egg_particles.remove(e)

def draw_eggs():
    if not egg_particles:
        return

    # save/prepare states
    was_lighting = glIsEnabled(GL_LIGHTING)
    was_blend    = glIsEnabled(GL_BLEND)
    glDisable(GL_LIGHTING)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    now = time.time()
    for e in egg_particles:
        age   = (now - e['birth']) / e['life']
        alpha = max(0.0, 1.0 - age)
        glPushMatrix()
        glTranslatef(e['pos'][0], e['pos'][1], e['pos'][2])
        glColor4f(1.0, 0.95, 0.1, alpha)
        glutSolidSphere(e['size'], 10, 8)
        glPopMatrix()

    # restore states
    if not was_blend: glDisable(GL_BLEND)
    if was_lighting:  glEnable(GL_LIGHTING)
    else:             glDisable(GL_LIGHTING)


# ---- Death animation / blood pool ----
def trigger_death():
    """Start death animation and blood pool."""
    global is_dead, death_t0, death_roll, death_pitch, blood_active, blood_t0
    if is_dead:
        return
    is_dead = True
    death_t0 = time.time()
    death_roll = 0.0
    death_pitch = 0.0
    blood_active = True
    blood_t0 = death_t0

def update_death(dt):
    global death_roll, death_pitch, game_over
    if not is_dead:
        return

    # 0..1 over the animation duration
    t = min(1.0, (time.time() - death_t0) / max(0.001, death_duration))
    ease = 1.0 - (1.0 - t)**3  # smooth easing

    death_roll  = 180.0 * ease   # clockwise roll around Z
    death_pitch = 90.0  * ease   # nose-down around X

    # when the flip is finished, end the run
    if t >= 1.0:
        death_roll  = 180.0
        death_pitch = 90.0
        game_over   = True

def draw_blood_pool():
    global blood_active
    if not blood_active:
        return

    age = time.time() - blood_t0
    t = min(1.0, age / max(0.001, blood_duration))
    radius = 10.0 + blood_max_radius * t
    alpha  = max(0.0, 0.6 * (1.0 - t))
    if age >= blood_duration:
        blood_active = False

    # --- save states ---
    was_lighting = glIsEnabled(GL_LIGHTING)
    was_depth    = glIsEnabled(GL_DEPTH_TEST)
    was_blend    = glIsEnabled(GL_BLEND)

    # overlay needs blend, no depth/lighting
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    # draw “pool” as a disk on the floor
    glPushMatrix()
    glTranslatef(0.0, -100.01, 0.0)   # your floor is at -100
    glRotatef(-90, 1, 0, 0)
    glColor4f(0.7, 0.0, 0.0, alpha)
    quad = Q if Q is not None else gluNewQuadric()
    gluDisk(quad, 0.0, radius, 48, 1)
    glPopMatrix()

    # --- restore states exactly as they were ---
    if not was_blend: glDisable(GL_BLEND)
    if was_depth:     glEnable(GL_DEPTH_TEST)
    else:             glDisable(GL_DEPTH_TEST)
    if was_lighting:  glEnable(GL_LIGHTING)
    else:             glDisable(GL_LIGHTING)

# ===================== World updates =====================
def update_bubbles():
    global bubbles
    for bubble in bubbles[:]:
        bubble.y_pos += bubble.rise_speed
        bubble.z_pos += game_speed * game_speed_factor
        if bubble.y_pos > 150 or bubble.z_pos > 200:
            bubbles.remove(bubble)
    current_time = time.time()
    if current_time - bubble_spawn_time > 0.3:
        if random.random() < 0.7:
            x = random.uniform(-ocean_width, ocean_width)
            y = random.uniform(-100, -50)
            z = random.uniform(-OCEAN_DEPTH, -500)
            bubbles.append(Bubble(x, y, z))

def check_collisions():
    global score, lives, game_over
    player_z = 0
    player_y = -30 - player_dive_depth
    player_radius = 30

    # fish
    for fish in small_fish:
        if not fish.collected and abs(fish.z_pos) < 70:
            if player_lane == fish.lane:
                # fish are drawn at y = -30; accept a ±15 window around that
                fish_y_center = -30.0
                hit_half_height = 15.0
                if (player_y + player_radius > fish_y_center - hit_half_height and
                    player_y - player_radius < fish_y_center + hit_half_height):
                    fish.collected = True
                    score += 1
                    on_points_scored(1)
                    # spawn an enemy every N points (5, 10, 15, ...)
                    if score > 0 and (score % ENEMY_SPAWN_EVERY_N_FISH == 0) and not enemy_active:
                        spawn_enemy()


    # volcanos: SAFE if we jump high enough now
    if not cheat_mode:
        for volcano in volcanos[:]:
            if abs(volcano.z_pos) < 80 and player_lane == volcano.lane:
                jump_height = -player_dive_depth  # 0..80 (positive when up)
                if jump_height < 40.0:           # not high enough ⇒ hit
                    volcanos.remove(volcano)
                    lives -= 1
                    if lives <= 0 and not is_dead:
                        trigger_death()

    # powerups
    for powerup in powerups:
        if not powerup.collected and abs(powerup.z_pos) < 60:
            if player_lane == powerup.lane:
                if player_y + player_radius > -10 and player_y - player_radius < 50:
                    powerup.collected = True
                    if lives < 5:
                        lives += 1
    # --- enemy collision ---
    if enemy_active and enemy_alive:
        if abs(enemy_z) < 60 and player_lane == enemy_lane:
            if not cheat_mode:
                trigger_death()
                game_over = True                    

def spawn_objects():
    global last_spawn_time
    current_time = time.time()
    if current_time - last_spawn_time > 1.2 / game_speed_factor:
        last_spawn_time = current_time
        lane = random.randint(0, 2)
        if random.random() < 0.7:
            small_fish.append(GameObject(-OCEAN_DEPTH, lane, 0))
        if random.random() < 0.4:
            volcanos.append(GameObject(-OCEAN_DEPTH, random.randint(0, 2), 1))
        if random.random() < 0.15:
            powerups.append(GameObject(-OCEAN_DEPTH, random.randint(0, 2), 2))

def spawn_seaweed():
    global seaweed_spawn_time, seaweed

    current_time = time.time()
    # spawn a bit more often so the forest fills in (tweak if too dense)
    if current_time - seaweed_spawn_time > 1.2 / game_speed_factor:
        seaweed_spawn_time = current_time

        # pick -1 (left), 0 (middle), +1 (right)
        side = random.choice([-1, 0, 1])

        # 65% chance to spawn a tall kelp
        if random.random() < 0.65:
            seaweed.append(Seaweed(-OCEAN_DEPTH, side))
def spawn_enemy():
    """Spawn enemy shark on the opposite lane of the player."""
    global enemy_active, enemy_alive, enemy_z, enemy_lane
    enemy_active = True
    enemy_alive = True
    enemy_z = -2000  # start far away

    # Opposite side of the player
    if player_lane == 0:      # left → enemy on right
        enemy_lane = 2
    elif player_lane == 2:    # right → enemy on left
        enemy_lane = 0
    else:                     # player in middle → enemy randomly left or right
        enemy_lane = random.choice([0, 2])

def update_enemy():
    """Move the enemy shark toward the player."""
    global enemy_z, enemy_active, enemy_alive
    if not enemy_active or not enemy_alive:
        return
    enemy_z += enemy_speed
    if enemy_z > 200:  # passed player
        enemy_active = False
        enemy_alive = False

def fire_bullet():
    """Fire two bullets from hammerhead’s eyes."""
    if player_shark_type != 1:  # only hammerhead can fire
        return
    x_left = lane_positions[player_lane] - 23
    x_right = lane_positions[player_lane] + 23
    y = -30 - player_dive_depth + 3
    z = 40
    bullets.append([x_left, y, z])
    bullets.append([x_right, y, z])

def update_bullets():
    global bullets, enemy_alive, enemy_active, score
    speed = bullet_speed * game_speed_factor
    for b in bullets[:]:
        b[2] -= speed
        if b[2] < -OCEAN_DEPTH - 100:
            bullets.remove(b)
            continue

        # hit test: overlap in Z, plus lane alignment for fairness
        if enemy_active and enemy_alive and abs(b[2] - enemy_z) < 40:
            if abs(b[0] - lane_positions[enemy_lane]) < 35:
                enemy_alive = False
                enemy_active = False
                score += 5
                on_points_scored(5)     # <<< grow based on the 5-point kill
                bullets.remove(b)



def draw_bullets():
    glColor3f(1, 1, 0)
    for b in bullets:
        glPushMatrix()
        glTranslatef(b[0], b[1], b[2])
        glutSolidSphere(5, 10, 10)
        glPopMatrix()

def initialize_current_streams():
    global current_streams_left, current_streams_right
    current_streams_left = []
    current_streams_right = []
    total_stream_length = STREAM_LENGTH + STREAM_GAP
    if total_stream_length <= 0:
        return
    num_streams = int(OCEAN_DEPTH * 2 / total_stream_length) + 2
    for i in range(num_streams):
        z_pos = -OCEAN_DEPTH + i * total_stream_length
        is_strong = (i % 2 == 0)
        current_streams_left.append(CurrentStream(z_pos, is_strong))
        current_streams_right.append(CurrentStream(z_pos, is_strong))

def spawn_current_streams():
    global current_streams_left, current_streams_right
    if not current_streams_left or not current_streams_right:
        return
    total_stream_length = STREAM_LENGTH + STREAM_GAP
    if total_stream_length <= 0:
        return
    farthest_left_z = min(stream.z_pos for stream in current_streams_left)
    farthest_right_z = min(stream.z_pos for stream in current_streams_right)
    if farthest_left_z > -OCEAN_DEPTH + total_stream_length:
        for stream in current_streams_left:
            if stream.z_pos == farthest_left_z:
                is_strong = not stream.is_strong
                current_streams_left.append(CurrentStream(farthest_left_z - total_stream_length, is_strong))
                break
    if farthest_right_z > -OCEAN_DEPTH + total_stream_length:
        for stream in current_streams_right:
            if stream.z_pos == farthest_right_z:
                is_strong = not stream.is_strong
                current_streams_right.append(CurrentStream(farthest_right_z - total_stream_length, is_strong))
                break

def update_objects():
    global small_fish, volcanos, powerups, current_streams_left, current_streams_right, game_speed
    speed = game_speed * game_speed_factor
    for fish in small_fish[:]:
        fish.z_pos += speed
        if fish.z_pos > 150:
            small_fish.remove(fish)
    for volcano in volcanos[:]:
        volcano.z_pos += speed
        if volcano.z_pos > 150:
            volcanos.remove(volcano)
    for powerup in powerups[:]:
        powerup.z_pos += speed
        if powerup.z_pos > 150:
            powerups.remove(powerup)
    for stream in current_streams_left[:]:
        stream.z_pos += 3
        if stream.z_pos > OCEAN_DEPTH:
            current_streams_left.remove(stream)
    for stream in current_streams_right[:]:
        stream.z_pos += 3
        if stream.z_pos > OCEAN_DEPTH:
            current_streams_right.remove(stream)
    for weed in seaweed[:]:
        weed.z_pos += speed
        if weed.z_pos > 150:
            seaweed.remove(weed)

def auto_collect_fish():
    """Cheat mode: auto-lane to nearest fish, but ONLY jump if a volcano is ahead."""
    global last_auto_fire_time
    global player_lane, dive_in_progress, last_dive_time


    # Prioritize enemy alignment over fish when an enemy is active
    if enemy_active and enemy_alive:
        if player_lane < enemy_lane:
            player_lane += 1
        elif player_lane > enemy_lane:
            player_lane -= 1
        # don't jump just for enemy alignment; keep volcano avoidance below
        # early return so we don't retarget to fish immediately
        return

    if not cheat_mode:
        return

    # 1) Lane aim: still target the nearest fish (no jumping here)
    nearest_fish = None
    nearest_distance = float('inf')
    for fish in small_fish:
        if not fish.collected and fish.z_pos < 0:            # only consider fish ahead (negative z)
            dist = abs(fish.z_pos)
            if dist < nearest_distance:
                nearest_fish = fish
                nearest_distance = dist

    if nearest_fish and nearest_distance < 1000:
        if player_lane < nearest_fish.lane:
            player_lane += 1
        elif player_lane > nearest_fish.lane:
            player_lane -= 1

    # 2) Hazard avoidance: jump only if a volcano is ahead in YOUR lane
    #    "Ahead" window: from ~260 units out to ~60 in front of you; tweak if you like.
    def volcano_ahead_in_lane(lane):
        for v in volcanos:
            if v.lane == lane and -260 <= v.z_pos <= -60:
                return True
        return False

    if (not dive_in_progress) and volcano_ahead_in_lane(player_lane):
        # start your existing jump/dive parabola (whatever you use now)
        dive_in_progress = True
        last_dive_time = time.time()



    # Only shoot if we're in the same lane and the enemy is in front within range
    if player_lane == enemy_lane and -AUTO_FIRE_MAX_RANGE_Z <= enemy_z <= 0:
        if now - last_auto_fire_time >= AUTO_FIRE_COOLDOWN:
            fire_bullet()
            last_auto_fire_time = now

def cheat_autofire(now):
    """Auto-shoot in cheat mode when lined up with the enemy and in range."""
    global last_auto_fire_time
    if not (cheat_mode and player_shark_type == 1):     # hammerhead only
        return
    if not (enemy_active and enemy_alive):
        return
    # same lane and enemy ahead within range
    if player_lane == enemy_lane and -AUTO_FIRE_MAX_RANGE_Z <= enemy_z <= 0:
        if now - last_auto_fire_time >= AUTO_FIRE_COOLDOWN:
            fire_bullet()
            last_auto_fire_time = now
          

# ===================== Input handlers =====================
def keyboardListener(key, x, y):
    global player_lane, dive_in_progress, last_dive_time, cheat_mode, player_shark_type
    global game_speed_factor, game_over, score, lives, small_fish, volcanos, powerups
    global current_streams_left, current_streams_right, seaweed, bubbles
    global player_scale, space_flash_until, game_paused

    # Allow pause/unpause even during game over
    if key in (b'p', b'P'):
        game_paused = not game_paused
        return

    if game_over:
        if key == b'r':
            # Reset
            reset_game()
        return

    # Don't process other keys when paused
    if game_paused:
        return

    if key == b'a':
        if player_lane > 0:
            player_lane -= 1
    if key == b'd':
        if player_lane < 2:
            player_lane += 1
    if key == b' ':
        if not dive_in_progress:
            dive_in_progress = True
            last_dive_time = time.time()
    if key == b'c':
        cheat_mode = not cheat_mode
        game_speed_factor = 2.0 if cheat_mode else 1.0
    if key == b'x':
        player_shark_type = (player_shark_type + 1) % 2
    if key == b'r':
        reset_game()
    # Grow on 'g' and trigger egg burst at 4×
    if key in (b'g', b'G'):
        player_scale = min(player_scale_max, player_scale + player_scale_step)
        space_flash_until = time.time() + 0.6
        if player_scale >= player_scale_max - 1e-6:
            spawn_tail_eggs_and_reset()
    # Death animation on 'd' (capital D to not collide with lane right)
    if key == b'D':
        trigger_death()
    if key == b'b':
        fire_bullet()
    #FPS toggle
    if key in (b'v', b'V'):
        global first_person
        first_person = not first_person
    if key in (b'f', b'F'):
        global use_fps_cam
        use_fps_cam = not use_fps_cam 
    if key in (b'e', b'E'):
        spawn_enemy() 

def reset_game():
    global player_lane, player_dive_depth, dive_in_progress, score, lives, game_over
    global cheat_mode, game_speed_factor, small_fish, volcanos, powerups
    global current_streams_left, current_streams_right, seaweed, bubbles
    global player_scale, is_dead, blood_active, game_paused
    global enemy_active, enemy_alive, enemy_z, enemy_lane, bullets
    
    player_lane = 1
    player_dive_depth = 0
    dive_in_progress = False
    score = 0
    lives = 3
    game_over = False
    game_paused = False  # Unpause when resetting
    cheat_mode = False
    game_speed_factor = 1.0
    small_fish = []
    volcanos = []
    powerups = []
    seaweed = []
    bubbles = []
    current_streams_left = []
    current_streams_right = []
    initialize_current_streams()
    player_scale = player_scale_init
    is_dead = False
    blood_active = False
    enemy_active = enemy_alive = False
    enemy_z = -2000
    enemy_lane = 1
    bullets = []
    game_speed = BASE_GAME_SPEED
    next_speedup_at = SPEED_STEP_POINTS

def specialKeyListener(key, x, y):
    global player_lane
    if game_over or game_paused:  # Don't process when paused
        return
    if key == GLUT_KEY_LEFT:
        if player_lane > 0:
            player_lane -= 1
    if key == GLUT_KEY_RIGHT:
        if player_lane < 2:
            player_lane += 1

def mouseListener(button, state, x, y):
    global dive_in_progress, last_dive_time
    if game_over or game_paused:  # Don't process when paused
        return
    if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
        if not dive_in_progress:
            dive_in_progress = True
            last_dive_time = time.time()


# ===================== Camera / frame loop =====================
def setupCamera():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(fovY, 1.25, 0.1, 2500)

    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    if use_fps_cam:
        # First-person: anchor to the player's position/orientation
        eye_x = lane_positions[player_lane]
        eye_y = -30.0 - player_dive_depth + FPS_EYE_HEIGHT
        eye_z = FPS_EYE_FORWARDZ  # z of player is 0; keep near it so speed feels consistent

        look_x = eye_x
        look_y = eye_y - 5.0            # tiny downward tilt feels natural under water
        look_z = FPS_LOOK_AHEADZ        # look forward along -Z

        gluLookAt(eye_x, eye_y, eye_z,  look_x, look_y, look_z,  0, 1, 0)
    else:
        # Original third-person camera (unchanged)
        x, y, z = camera_pos
        gluLookAt(x, y, z,  0, -50, -200,  0, 1, 0)

def apply_speed_progression():

    global game_speed, next_speedup_at
    # Catch up in case score jumped over several thresholds
    while score >= next_speedup_at:
        if SPEED_INCREASE_MODE == "mul":
            game_speed = min(GAME_SPEED_MAX, game_speed * SPEED_INCREASE_VALUE)
        else:  # additive
            game_speed = min(GAME_SPEED_MAX, game_speed + SPEED_INCREASE_VALUE)
        next_speedup_at += SPEED_STEP_POINTS


def idle():
    global last_update_time
    now = time.time()
    
    # When paused, don't update game time or game logic
    if game_paused:
        glutPostRedisplay()  # Still redraw the screen
        return
    
    dt = max(1e-3, now - last_update_time)
    last_update_time = now

    if not game_over:
        update_player_dive()
        update_animation()
        update_objects()
        update_enemy()
        update_bullets()
        update_bubbles()
        spawn_objects()
        spawn_current_streams()
        spawn_seaweed()
        update_eggs(dt)
        update_death(dt)
        check_collisions()
        if cheat_mode:
            auto_collect_fish()
            cheat_autofire(now) 

    glutPostRedisplay()



def showScreen():
    glViewport(0, 0, 1000, 800)
    glClearColor(0.0, 0.2, 0.5, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glEnable(GL_DEPTH_TEST)

    setupCamera()

    # --- 3D world ---
    draw_ocean_floor()
    draw_game_objects()
    draw_player()
    draw_blood_pool()
    draw_eggs()

    # --- HUD ---
    top = 680
    line = 24

    # Show pause overlay if paused
    if game_paused:
        # Semi-transparent overlay
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, 1000, 0, 800)
        
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        
        # Dark overlay
        glColor4f(0.0, 0.0, 0.0, 0.5)
        glBegin(GL_QUADS)
        glVertex2f(0, 0)
        glVertex2f(1000, 0)
        glVertex2f(1000, 800)
        glVertex2f(0, 800)
        glEnd()
        
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        
        # Pause text
        draw_text(450, 420, "PAUSED")
        draw_text(380, 390, "Press 'P' to resume")

    if game_over:
        draw_text(400, 420, "GAME OVER")
        draw_text(350, 390, f"Final Score: {score}")
        draw_text(300, 360, "Press 'R' to restart")
    else:
        # Left column
        y = top
        draw_text(10, y, f"Score: {score}"); y -= line
        draw_text(10, y, f"Lives: {lives}"); y -= line
        if cheat_mode:
            draw_text(10, y, "CHEAT MODE ACTIVE"); y -= line
            draw_text(10, y, "Auto-hunting fish"); y -= line
        if time.time() < space_flash_until:
            draw_text(10, y, "GROW +size"); y -= line

        # Right column
        x = 740
        y = top
        draw_text(x, y, "A/D or ←/→: Move"); y -= line
        draw_text(x, y, "Space: Jump"); y -= line
        draw_text(x, y, "P: Pause/Resume"); y -= line  # Add pause instruction
        draw_text(x, y, "G: Grow (egg burst at 4×)"); y -= line
        draw_text(x, y, "D: Die (flip + blood)"); y -= line
        draw_text(x, y, "C: Toggle Cheat  |  X: Switch Shark"); y -= line
        draw_text(x, y, f"Shark: {'Great White' if player_shark_type == 0 else 'Hammerhead'}")
        draw_text(x, y, f""); y -= line
        draw_text(x, y, f"Use FPS Cam: {'On' if use_fps_cam else 'Off'} (F to toggle)"); y -= line
        draw_text(x, y, f"press e to spawn enemy shark"); y -= line

    glutSwapBuffers()


# ===================== Main =====================
def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(1000, 800)
    glutInitWindowPosition(0, 0)
    wind = glutCreateWindow(b"Shark Feeding Frenzy")
    init_shark_assets()
    init_enemy_shark_assets() 
    initialize_current_streams()
    glutDisplayFunc(showScreen)
    glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener)
    glutMouseFunc(mouseListener)
    glutIdleFunc(idle)
    glutMainLoop()

if __name__ == "__main__":
    main()
