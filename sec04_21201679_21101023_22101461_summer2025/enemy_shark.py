from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import time, math, sys

# ---------------- Globals ----------------
Q = None                 # shared GLU quadric
animation_phase = 0.0    # swim cycle
last_time = None
fovY = 55
win_w, win_h = 1000, 800

# Orbit camera state (POV)
cam_target = [0.0, -10.0, 0.0]  # look-at point (center of scene)
cam_radius = 260.0              # distance from target
cam_yaw = 0.0                   # degrees; 0 = along +Z
cam_pitch = -10.0               # degrees; up/down
mouse_sensitivity = 0.25        # deg per pixel
zoom_step = 10.0                # wheel zoom step
_is_dragging = False
_last_mouse = (0, 0)

# ------------- Shark helpers -------------
_enemy_slices = 28
_enemy_stacks = 18

def _sphere(r, sl=_enemy_slices, st=_enemy_stacks):
    gluSphere(Q, r, sl, st)

def _cyl(r1, r2, h, sl=_enemy_slices, st=12):
    gluCylinder(Q, r1, r2, h, sl, st)

# ------------- Initialization -------------

def init_shark_assets():
    """Call once AFTER glutCreateWindow()."""
    if glutGetWindow() == 0:
        raise RuntimeError("Call init_shark_assets() AFTER glutCreateWindow().")

    global Q
    if Q is None:
        Q = gluNewQuadric()
        gluQuadricNormals(Q, GLU_SMOOTH)
        gluQuadricTexture(Q, GL_FALSE)

    glEnable(GL_DEPTH_TEST)
    glEnable(GL_NORMALIZE)

    # Simple lighting
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL)
    glLightfv(GL_LIGHT0, GL_POSITION, (0.0, 80.0, 120.0, 1.0))
    glLightfv(GL_LIGHT0, GL_DIFFUSE,  (0.9, 0.9, 0.9, 1.0))
    glLightfv(GL_LIGHT0, GL_AMBIENT,  (0.18, 0.18, 0.22, 1.0))

    # Background
    glClearColor(0.0, 0.2, 0.5, 1.0)  # underwater blue

# --------------- Shark model ---------------

def draw_shark(swim_phase=0.0, scale=1.8,
               # >>> Villain red theme by default
               shade_top=(0.75, 0.08, 0.08),
               shade_bottom=(0.22, 0.03, 0.03),
               proportions=None):
    enemy_shape = {
        'body_len': 2.4,
        'head_size': 13.5,
        'snout_size': 8.5,
        'stalk_len': 20.0,
        'dorsal_base': 6.5,
        'dorsal_height': 16.0,
        'pectoral_size': 6.3,
        'tail_lobe_len': 16.0,
    }
    if proportions:
        enemy_shape.update(proportions)

    tail_wag   = math.sin(swim_phase * 8.0) * 30.0      # tail yaw
    fin_wiggle = math.sin(swim_phase * 5.0) * 20.0      # fin wiggle

    glPushMatrix()
    glScalef(scale, scale, scale)

    # Body main
    glPushMatrix()
    glRotatef(tail_wag * 0.12, 0, 1, 0)
    glColor3f(*shade_top)
    glPushMatrix()
    glScalef(0.6, 0.8, enemy_shape['body_len'])
    _sphere(20)
    glPopMatrix()

    # Belly underlay (dark crimson)
    glColor3f(*shade_bottom)
    glPushMatrix()
    glTranslatef(0, -3.7, 2.0)
    glScalef(1.05, 0.70, enemy_shape['body_len'] * 0.7)
    _sphere(17.3)
    glPopMatrix()

    # Head + snout
    glColor3f(*shade_top)
    glPushMatrix()
    glTranslatef(0, 2.0, 37.0)
    glRotatef(tail_wag * 0.08, 0, 1, 0)
    glScalef(2.18, 0.50, 0.95)
    _sphere(enemy_shape['head_size'])
    glPopMatrix()

    glPushMatrix()
    glTranslatef(0, 0.0, 40.0)
    glScalef(0.92, 0.78, 0.92)
    _sphere(enemy_shape['snout_size'])
    glPopMatrix()

    # Eyes — orange-red glow
    for sx in (-28.0, 28.0):
        glPushMatrix()
        glTranslatef(sx, 3.0, 40.0)
        # set emissive glow
        glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION, (1.0, 0.22, 0.06, 1.0))
        glColor3f(1.0, 0.35, 0.10)
        _sphere(1.9, 14, 10)
        # reset emission
        glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION, (0.0, 0.0, 0.0, 1.0))
        glPopMatrix()

    # ---------- GILL SLITS (both sides) ----------
    gill_count   = 5
    gill_spacing = 2.2
    gill_x       = 10
    gill_y       = 3.5
    gill_z0      = 25.0
    gill_len     = 3.0
    gill_thin    = 0.80
    gill_color   = (0.18, 0.2, 0.24)

    for side in (-1, 1):
        for i in range(gill_count):
            glPushMatrix()
            glTranslatef(side * gill_x, gill_y, gill_z0 - i * gill_spacing)
            glColor3f(*gill_color)
            glRotatef(-90, 0, 0, 1)          # horizontal slit
            glScalef(gill_len, gill_thin, 0.5)
            _sphere(1, 15, 8)
            glPopMatrix()

        # ---------- UPPER TEETH (tiny cones along an arc) ----------
        teeth_n            = 14
        arch_half_width    = 12.0
        arch_depth         = 1.2
        ridge_y            = -0.6
        ridge_z            = 47.0

        center_rad, side_rad = 0.80, 0.55
        center_h,   side_h   = 4.2,  3.0
        outward_tilt_max     = 10.0

        glPushMatrix()
        glTranslatef(0.0, ridge_y, ridge_z)
        glColor3f(1.0, 0.92, 0.25)   # >>> yellow villain teeth

        for i in range(teeth_n):
            t = (i / float(teeth_n - 1)) * 2.0 - 1.0
            x = t * arch_half_width
            z = (1.0 - t*t) * arch_depth
            w = abs(t)**1.2
            rad = center_rad * (1.0 - w) + side_rad * w
            h   = center_h   * (1.0 - w) + side_h   * w
            tilt_z = t * outward_tilt_max

            glPushMatrix()
            glTranslatef(x, 0.0, z)
            glRotatef(90.0, 1, 0, 0)      # +Z → −Y (down)
            glRotatef(tilt_z, 0, 0, 1)
            glRotatef(180.0, 0, 0, 1)
            glutSolidCone(rad, h, 10, 1)
            glPopMatrix()
        glPopMatrix()

    # ---------- LOWER TEETH (pivot above; base swings on an arc) ----------
    gum_y, gum_z = -32.6, 47.0
    pivot = (1.0, 20.0, 0)             # (keep as given)
    radius = gum_y - pivot[1]

    speed = 1.2
    ang_min, ang_max = -50.0, -40.0
    t = 0.5 * (1.0 - math.cos(2.0 * math.pi * speed * swim_phase))
    angle = ang_min - t * (ang_max - ang_min)

    glPushMatrix()
    glTranslatef(*pivot)
    glRotatef(angle, 1, 0, 0)
    glTranslatef(0, radius, 0)

    n          = 14
    half_w     = 11.0
    depth      = 1.2
    cen_rad, side_rad = 0.75, 0.50
    cen_h,   side_h   = 3.0,  2.7
    tilt_max          = 8.0

    glColor3f(1.0, 0.92, 0.25)         # >>> yellow villain teeth (lower)
    for i in range(n):
        u = (i/(n-1))*2.0 - 1.0
        x = u * half_w
        z = (1.0 - u*u) * depth
        w = abs(u)**1.2
        rad = cen_rad*(1.0 - w) + side_rad*w
        h   = cen_h  *(1.0 - w) + side_h  *w
        tilt = u * tilt_max

        glPushMatrix()
        glTranslatef(x, -z, 0)         # (keep your mechanism)
        glRotatef(0, 1, 0, 0)
        glRotatef(tilt, 0, 0, 1)
        glutSolidCone(rad, h, 20, 1)
        glPopMatrix()

    glPopMatrix()

    # ---------- DORSAL FIN (sleek, raked, sideways sway) ----------
    glColor3f(shade_top[0]*0.85, shade_top[1]*0.85, shade_top[2]*0.85)

    dorsal_offset = (0.0, 11.0, -7.0)
    dorsal_thin   = 0.32
    dorsal_rake   = -30.0
    dorsal_yawamp = 6.0

    glPushMatrix()
    glTranslatef(*dorsal_offset)
    glRotatef(math.sin(swim_phase * 4.0) * dorsal_yawamp, 0, 1, 0)
    glRotatef(-90, 1, 0, 0)
    glRotatef(dorsal_rake, 1, 0, 0)
    glScalef(dorsal_thin, 1.0, 0.9)
    glutSolidCone(enemy_shape['dorsal_base'] * 1.50, enemy_shape['dorsal_height'] * 1.72, 24, 1)
    glPopMatrix()

    glPushMatrix()
    glTranslatef(*dorsal_offset)
    glScalef(1.0, 0.35, 0.9)
    _sphere(enemy_shape['dorsal_base'] * 0.85, 18, 14)
    glPopMatrix()

    # Pectoral fins
    for side in (-1, 1):
        glPushMatrix()
        glTranslatef(12*side, -6.5, 8.0)
        glRotatef(45, 1, 0, 0)
        glRotatef(side*(1 + fin_wiggle*0.9), 0, 0, 1)
        glScalef(2.9, 0.30, 1.0)
        _sphere(enemy_shape['pectoral_size'], 18, 12)
        glPopMatrix()

    # ---------- TAIL STALK (pivot at body joint) ----------
    glPushMatrix()
    glTranslatef(0, 0, -48)
    glRotatef(tail_wag, 0, 1, 0)
    glTranslatef(0, 0, -18)

    glPushMatrix()
    glScalef(0.42, 1, 1.2)
    _cyl(9.0, 6.0, enemy_shape['stalk_len'])
    glPopMatrix()

    glDisable(GL_LIGHTING)
    glColor3f(1, 0, 0)
    glutSolidSphere(2, 10, 10)
    glEnable(GL_LIGHTING)
    glPopMatrix()

    # ---------- CAUDAL FIN (pivot at tail tip; V-shaped lobes) ----------
    glPushMatrix()
    glTranslatef(0, 0, -48)
    glRotatef(tail_wag, 0, 1, 0)
    glTranslatef(0, 0, -18)
    glColor3f(shade_top[0]*0.9, shade_top[1]*0.9, shade_top[2]*0.9)
    R = 10.0
    H = enemy_shape['tail_lobe_len']

    def tail_lobe(tilt_deg, length_scale=1.0):
        glPushMatrix()
        glRotatef(180, 0, 1, 0)
        glRotatef(tilt_deg, 1, 0, 0)
        glScalef(0.35, 1.0, 2.6*length_scale)
        glutSolidCone(R, H*length_scale, 20, 1)
        glPopMatrix()

    tail_lobe(+45, 1.00)
    tail_lobe(-45, 1.00)
    glPopMatrix()  # tail group
    glPopMatrix()  # body group
    glPopMatrix()

# --------------- Scene drawing ---------------

# def draw_floor():
#     glDisable(GL_LIGHTING)
#     glBegin(GL_QUADS)
#     glColor3f(0.80, 0.72, 0.55)  # sandy
#     glVertex3f(-220, -40, -220)
#     glVertex3f( 220, -40, -220)
#     glVertex3f( 220, -40,  220)
#     glVertex3f(-220, -40,  220)
#     glEnd()
#     glEnable(GL_LIGHTING)

# --------------- Camera helpers ---------------

def _compute_camera_pos():
    """Compute camera position from spherical (radius, yaw, pitch) around cam_target."""
    ry = math.radians(cam_yaw)
    rp = math.radians(cam_pitch)
    x = cam_target[0] + cam_radius * math.sin(ry) * math.cos(rp)
    y = cam_target[1] + cam_radius * math.sin(rp)
    z = cam_target[2] + cam_radius * math.cos(ry) * math.cos(rp)
    return (x, y, z)

def set_camera():
    # Rebuild projection with current fov & aspect
    aspect = max(0.1, win_w / float(max(1, win_h)))
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(fovY, aspect, 0.1, 2500)

    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    cx, cy, cz = _compute_camera_pos()
    gluLookAt(cx, cy, cz,
              cam_target[0], cam_target[1], cam_target[2],
              0, 1, 0)

# ----------------- GLUT callbacks -----------------

def display():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    set_camera()

    #draw_floor()

    # place shark slightly above the floor
    glPushMatrix()
    glTranslatef(0, -10, 0)
    draw_shark(swim_phase=animation_phase, scale=1.9)
    glPopMatrix()

    glutSwapBuffers()

def idle():
    global animation_phase, last_time
    now = time.time()
    if last_time is None:
        last_time = now
    dt = now - last_time
    last_time = now
    animation_phase += dt
    glutPostRedisplay()

def reshape(w, h):
    global win_w, win_h
    win_w, win_h = max(1, w), max(1, h)
    glViewport(0, 0, win_w, win_h)

def keyboard(key, x, y):
    global fovY
    if key in (b'\x1b',):  # ESC
        sys.exit(0)
    if key in (b'+', b'='):
        fovY = max(30, fovY - 5)
    elif key in (b'-', b'_'):
        fovY = min(100, fovY + 5)

def mouse(button, state, x, y):
    """Right button drag to orbit. Wheel to zoom."""
    global _is_dragging, _last_mouse, cam_radius
    if button == GLUT_RIGHT_BUTTON:
        _is_dragging = (state == GLUT_DOWN)
        _last_mouse = (x, y)
    # Mouse wheel (commonly 3 up, 4 down in GLUT)
    if state == GLUT_DOWN and button in (3, 4):
        if button == 3:    # wheel up -> zoom in
            cam_radius = max(60.0, cam_radius - zoom_step)
        elif button == 4:  # wheel down -> zoom out
            cam_radius = min(1000.0, cam_radius + zoom_step)
        glutPostRedisplay()

def motion(x, y):
    """Handle mouse movement while dragging (orbit)."""
    global _last_mouse, cam_yaw, cam_pitch
    if not _is_dragging:
        return
    dx = x - _last_mouse[0]
    dy = y - _last_mouse[1]
    _last_mouse = (x, y)

    cam_yaw = (cam_yaw + dx * mouse_sensitivity) % 360.0
    cam_pitch = max(-89.0, min(89.0, cam_pitch - dy * mouse_sensitivity))  # clamp
    glutPostRedisplay()

# ----------------- Main -----------------

def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(win_w, win_h)
    glutInitWindowPosition(100, 60)
    glutCreateWindow(b"Shark Demo - Mouse Orbit POV")

    init_shark_assets()  # safe now

    glutDisplayFunc(display)
    glutIdleFunc(idle)
    glutKeyboardFunc(keyboard)
    glutReshapeFunc(reshape)
    glutMouseFunc(mouse)
    glutMotionFunc(motion)

    glutMainLoop()

if __name__ == '__main__':
    main()
