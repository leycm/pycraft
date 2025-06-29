import moderngl
import numpy as np
import pygame
from PIL import Image, ImageDraw, ImageFont
import math
import os

from shared.constants import BlockType, CHUNK_WIDTH, CHUNK_DEPTH

# Matrix Utility Functions

def perspective(fov, aspect, near, far):
    """Creates a perspective projection matrix (column-major)."""
    f = 1.0 / math.tan(math.radians(fov) / 2.0)
    return np.array([
        [f / aspect, 0, 0, 0],
        [0, f, 0, 0],
        [0, 0, (far + near) / (near - far), -1],
        [0, 0, (2 * far * near) / (near - far), 0]
    ], dtype='f4')

def look_at(eye, target, up):
    """Creates a view matrix (column-major)."""
    f = target - eye
    f /= np.linalg.norm(f)
    
    s = np.cross(f, up)
    s /= np.linalg.norm(s)
    
    u = np.cross(s, f)
    
    return np.array([
        [s[0], u[0], -f[0], 0],
        [s[1], u[1], -f[1], 0],
        [s[2], u[2], -f[2], 0],
        [-np.dot(s, eye), -np.dot(u, eye), np.dot(f, eye), 1]
    ], dtype='f4')

def model_matrix(position=(0, 0, 0)):
    """Creates a model matrix to position an object in the world."""
    return np.array([
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [position[0], position[1], position[2], 1]
    ], dtype='f4')

# Shaders

VERTEX_SHADER = '''
    #version 330
    in vec3 in_position;
    in vec2 in_texcoord;
    uniform mat4 projection;
    uniform mat4 view;
    uniform mat4 model;
    out vec2 v_texcoord;
    void main() {
        gl_Position = projection * view * model * vec4(in_position, 1.0);
        v_texcoord = in_texcoord;
    }
'''

FRAGMENT_SHADER = '''
    #version 330
    uniform sampler2D u_texture;
    in vec2 v_texcoord;
    out vec4 fragColor;
    void main() {
        fragColor = texture(u_texture, v_texcoord);
    }
'''

UI_VERTEX_SHADER = '''
    #version 330
    in vec2 in_vert;
    in vec2 in_texcoord;
    out vec2 v_texcoord;
    uniform vec2 u_position;
    uniform vec2 u_size;
    uniform vec2 u_screen_size;
    void main() {
        vec2 pos = (in_vert * u_size + u_position) / (u_screen_size / 2.0) - 1.0;
        pos.y = -pos.y;
        gl_Position = vec4(pos, 0.0, 1.0);
        v_texcoord = in_texcoord;
    }
'''

UI_FRAGMENT_SHADER = '''
    #version 330
    in vec2 v_texcoord;
    uniform sampler2D u_texture;
    out vec4 f_color;
    void main() {
        vec4 tex_color = texture(u_texture, v_texcoord);
        if(tex_color.a < 0.1) discard;
        f_color = tex_color;
    }
'''

# Texture Atlas

class TextureAtlas:
    def __init__(self, path, texture_pixel_size=16):
        self.texture = load_texture(path, nearest=True)
        self.atlas_width_px = self.texture.width
        self.texture_width_px = texture_pixel_size
        self.num_textures = self.atlas_width_px // self.texture_width_px

    def get_uv_range(self, block_type):
        """Returns (u_min, u_max) for block type."""
        block_id = int(block_type) - 1
        u_min = block_id / self.num_textures
        u_max = (block_id + 1) / self.num_textures
        return u_min, u_max

# Camera

class Camera:
    def __init__(self):
        self.position = np.array([0.0, 70.0, 0.0], dtype=np.float32)
        self.yaw = 0.0  # Start facing forward (Z+ direction)
        self.pitch = 0.0
        self.eyeh = 1.62  # Eye height like Minecraft
        self.third_person = False
        self.third_person_dist = 4.0
        self.update_vectors()

    def update_vectors(self):
        # Vector calculation
        self.front = np.array([
            math.cos(math.radians(self.yaw)) * math.cos(math.radians(self.pitch)),
            math.sin(math.radians(self.pitch)),
            math.sin(math.radians(self.yaw)) * math.cos(math.radians(self.pitch))
        ], dtype=np.float32)
        self.front /= np.linalg.norm(self.front)
        
        # Right vector (perpendicular to front and world up)
        world_up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        self.right = np.cross(self.front, world_up)
        self.right /= np.linalg.norm(self.right)
        
        # Up vector (perpendicular to front and right)
        self.up = np.cross(self.right, self.front)
        self.up /= np.linalg.norm(self.up)

    def get_eye_position(self):
        # Eye height
        if self.third_person:
            # Camera behind player
            offset = -self.front * self.third_person_dist
            return self.position + np.array([0, self.eyeh, 0]) + offset
        else:
            return self.position + np.array([0, self.eyeh, 0])

    def get_view_matrix(self):
        eye = self.get_eye_position()
        target = eye + self.front
        return look_at(eye, target, self.up)

    def process_mouse(self, xoffset, yoffset, sensitivity=0.1):
        # Mouse movement
        self.yaw += xoffset * sensitivity
        self.pitch -= yoffset * sensitivity  # Invert Y for natural mouse movement
        self.pitch = max(-89.0, min(89.0, self.pitch))  # Clamp pitch
        self.update_vectors()

    def move(self, direction, speed):
        # Movement
        if direction == 'FORWARD': 
            self.position += self.front * speed
        elif direction == 'BACKWARD': 
            self.position -= self.front * speed
        elif direction == 'LEFT': 
            self.position -= self.right * speed
        elif direction == 'RIGHT': 
            self.position += self.right * speed
        elif direction == 'UP': 
            self.position[1] += speed
        elif direction == 'DOWN': 
            self.position[1] -= speed

# Renderer

class Renderer:
    def __init__(self, width, height):
        pygame.init()
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
        
        self.width = width
        self.height = height
        self.display = pygame.display.set_mode((width, height), pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE)
        
        global ctx 
        ctx = moderngl.create_context()
        ctx.enable(moderngl.DEPTH_TEST)
        ctx.enable(moderngl.CULL_FACE)
        
        self.camera = Camera()

        # World Rendering Program
        self.prog = ctx.program(vertex_shader=VERTEX_SHADER, fragment_shader=FRAGMENT_SHADER)
        proj = perspective(45.0, width / height, 0.1, 100.0)
        self.prog['projection'].write(proj.tobytes())
        
        # UI Rendering Program
        self.ui_prog = ctx.program(vertex_shader=UI_VERTEX_SHADER, fragment_shader=UI_FRAGMENT_SHADER)
        self.ui_prog['u_screen_size'].value = (width, height)
        
        # Load Textures
        terrain_img = Image.open('assets/terrain.png')
        block_size = terrain_img.height
        self.block_atlas = TextureAtlas('assets/terrain.png', texture_pixel_size=block_size)
        # Player Skin: custom or fallback
        custom_skin_path = 'assets/player_custom.png'
        if os.path.exists(custom_skin_path):
            print(f"Loading custom player skin: {custom_skin_path}")
            self.player_texture = load_texture(custom_skin_path)
        else:
            self.player_texture = load_texture('assets/player.png')
        self.hotbar_texture = load_texture('assets/hotbar.png')
        self.hotbar_selection_texture = load_texture('assets/hotbar_selection.png')
        
        # World VAO (simple cube)
        self.ibo = ctx.buffer(np.array([
             0,  1,  2,  0,  2,  3, # Quad indices
        ], dtype='i4').tobytes())

        # Create VAO for each block type per face with proper texcoords
        self.block_vaos = {}
        for block_type in BlockType:
            if block_type == BlockType.AIR:
                continue
            u_min, u_max = self.block_atlas.get_uv_range(block_type)
            self.block_vaos[block_type] = {}
            for face, verts in self._face_vertices().items():
                self.block_vaos[block_type][face] = self._create_face_vao_with_uv(verts, u_min, u_max)
        
        # UI VAO
        ui_quad = np.array([0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.0], dtype='f4')
        ui_vbo = ctx.buffer(ui_quad.tobytes())
        self.ui_vao = ctx.vertex_array(self.ui_prog, [(ui_vbo, '2f 2f', 'in_vert', 'in_texcoord')], mode=moderngl.TRIANGLE_STRIP)

        # Entity VAOs for player.png (3x2 grid)
        self.entity_vaos = self._create_entity_vaos()

    def _face_vertices(self):
        return {
            'front':  [ -0.5, -0.5,  0.5,   0.5, -0.5,  0.5,   0.5,  0.5,  0.5,  -0.5,  0.5,  0.5 ],
            'back':   [  0.5, -0.5, -0.5,  -0.5, -0.5, -0.5,  -0.5,  0.5, -0.5,   0.5,  0.5, -0.5 ],
            'top':    [ -0.5,  0.5,  0.5,   0.5,  0.5,  0.5,   0.5,  0.5, -0.5,  -0.5,  0.5, -0.5 ],
            'bottom': [ -0.5, -0.5, -0.5,   0.5, -0.5, -0.5,   0.5, -0.5,  0.5,  -0.5, -0.5,  0.5 ],
            'right':  [  0.5, -0.5,  0.5,   0.5, -0.5, -0.5,   0.5,  0.5, -0.5,   0.5,  0.5,  0.5 ],
            'left':   [ -0.5, -0.5, -0.5,  -0.5, -0.5,  0.5,  -0.5,  0.5,  0.5,  -0.5,  0.5, -0.5 ],
        }

    def _create_face_vao_with_uv(self, vertices, u_min, u_max, v_min=0.0, v_max=1.0):
        v = np.array(vertices, dtype='f4').reshape((4, 3))
        texcoords = np.array([
            [u_min, v_min],
            [u_max, v_min],
            [u_max, v_max],
            [u_min, v_max],
        ], dtype='f4')
        data = np.hstack([v, texcoords]).astype('f4').flatten()
        vbo = ctx.buffer(data.tobytes())
        return ctx.vertex_array(self.prog, [(vbo, '3f 2f', 'in_position', 'in_texcoord')], self.ibo)

    def _create_entity_vaos(self):
        # Simple Minecraft player proportions
        # Head: 0.5x0.5x0.5, Body: 0.5x0.75x0.25, Arms/Legs: 0.25x0.75x0.25
        def box_vertices(w, h, d):
            # Centered at origin
            x, y, z = w/2, h/2, d/2
            return {
                'front':  [ -x, -y,  z,   x, -y,  z,   x,  y,  z,  -x,  y,  z ],
                'back':   [  x, -y, -z,  -x, -y, -z,  -x,  y, -z,   x,  y, -z ],
                'top':    [ -x,  y,  z,   x,  y,  z,   x,  y, -z,  -x,  y, -z ],
                'bottom': [ -x, -y, -z,   x, -y, -z,   x, -y,  z,  -x, -y,  z ],
                'right':  [  x, -y,  z,   x, -y, -z,   x,  y, -z,   x,  y,  z ],
                'left':   [ -x, -y, -z,  -x, -y,  z,  -x,  y,  z,  -x,  y, -z ],
            }
        
        # Simple UV coordinates for player.png (3x2 grid)
        u = [0.0, 1/3, 2/3, 1.0]
        v = [0.0, 0.5, 1.0]
        
        vaos = {}
        
        # Head (top left corner)
        head_faces = box_vertices(0.5, 0.5, 0.5)
        vaos['head'] = {face: self._create_face_vao_with_uv(head_faces[face], u[0], u[1], v[0], v[1]) for face in head_faces}
        
        # Body (middle top half)
        body_faces = box_vertices(0.5, 0.75, 0.25)
        vaos['body'] = {face: self._create_face_vao_with_uv(body_faces[face], u[1], u[2], v[0], v[1]) for face in body_faces}
        
        # Arms (right top half)
        arm_faces = box_vertices(0.25, 0.75, 0.25)
        vaos['left_arm'] = {face: self._create_face_vao_with_uv(arm_faces[face], u[2], u[3], v[0], v[1]) for face in arm_faces}
        vaos['right_arm'] = {face: self._create_face_vao_with_uv(arm_faces[face], u[2], u[3], v[0], v[1]) for face in arm_faces}
        
        # Legs (bottom half - head texture)
        leg_faces = box_vertices(0.25, 0.75, 0.25)
        vaos['left_leg'] = {face: self._create_face_vao_with_uv(leg_faces[face], u[0], u[1], v[1], v[2]) for face in leg_faces}
        vaos['right_leg'] = {face: self._create_face_vao_with_uv(leg_faces[face], u[0], u[1], v[1], v[2]) for face in leg_faces}
        
        return vaos

    def render_block(self, position, block_type, faces_to_render=None):
        if faces_to_render is None:
            faces_to_render = {'top': True, 'bottom': True, 'left': True, 'right': True, 'front': True, 'back': True}
        model = model_matrix(position)
        self.prog['model'].write(model.tobytes())
        vaos = self.block_vaos.get(block_type)
        if vaos is None:
            return
        for face, is_visible in faces_to_render.items():
            if is_visible:
                vaos[face].render()

    def render_ui(self, inventory):
        ctx.disable(moderngl.DEPTH_TEST)
        self.ui_prog['u_texture'].value = 0

        # Hotbar
        hotbar_width, hotbar_height = 364, 44
        hotbar_x = (self.width - hotbar_width) / 2
        hotbar_y = self.height - hotbar_height - 10
        self.hotbar_texture.use(0)
        self.ui_prog['u_position'].value = (hotbar_x, hotbar_y)
        self.ui_prog['u_size'].value = (hotbar_width, hotbar_height)
        self.ui_vao.render()
        
        # Selection
        selection_size, slot_size = 48, 40
        selection_x = hotbar_x - 2 + (inventory.selected_slot * slot_size)
        selection_y = hotbar_y - 2
        self.hotbar_selection_texture.use(0)
        self.ui_prog['u_position'].value = (selection_x, selection_y)
        self.ui_prog['u_size'].value = (selection_size, selection_size)
        self.ui_vao.render()

        ctx.enable(moderngl.DEPTH_TEST)

    def clear(self):
        ctx.clear(0.5, 0.7, 1.0)
        view_matrix = self.camera.get_view_matrix()
        self.prog['view'].write(view_matrix.tobytes())
        
        # Activate block texture
        self.block_atlas.texture.use(0)
        self.prog['u_texture'].value = 0

    def render_player(self, position, name, yaw=0.0, pitch=0.0, body_yaw=0.0, skin_data=None):
        """
        Render a player - WITH SIMPLE ROTATION
        """
        # Simple body yaw delay (like Minecraft) - player specific
        if not hasattr(self, '_player_body_yaws'):
            self._player_body_yaws = {}
        
        if name not in self._player_body_yaws:
            self._player_body_yaws[name] = yaw
        
        # Smooth body rotation following head for this player
        delta_yaw = yaw - self._player_body_yaws[name]
        
        # Correct angle difference (solve 180° problem)
        if delta_yaw > 180:
            delta_yaw -= 360
        elif delta_yaw < -180:
            delta_yaw += 360
            
        # Faster adjustment (40% per frame instead of 15%)
        self._player_body_yaws[name] += delta_yaw * 0.4
        
        # Limit head-body rotation difference (max 75°)
        max_diff = 75.0
        if abs(yaw - self._player_body_yaws[name]) > max_diff:
            if yaw > self._player_body_yaws[name]:
                self._player_body_yaws[name] = yaw - max_diff
            else:
                self._player_body_yaws[name] = yaw + max_diff
        
        # Set skin texture
        texture = self.player_texture
        if skin_data:
            try:
                import base64
                from io import BytesIO
                from PIL import Image
                img = Image.open(BytesIO(base64.b64decode(skin_data)))
                texture = ctx.texture(img.size, 4, img.convert('RGBA').tobytes())
                texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
                texture.repeat_x = False
                texture.repeat_y = False
            except Exception as e:
                print(f"Failed to load player skin: {e}")
                texture = self.player_texture
        
        # Render the complete player model with rotation
        self.render_entity_simple(position, yaw=yaw, pitch=pitch, body_yaw=self._player_body_yaws[name], texture=texture)
        
        # Render nametag
        player_screen = self.world_to_screen_simple((position[0], position[1] + 2.2, position[2]))
        if player_screen is not None:
            self.draw_nametag(player_screen, name)

    def render_entity_simple(self, position, yaw=0.0, pitch=0.0, body_yaw=0.0, texture=None):
        """
        Simple player rendering WITH ROTATION around Y-axis and pitch for head
        """
        from math import radians, cos, sin
        px, py, pz = position
        
        if texture is None:
            texture = self.player_texture
        texture.use(0)

        # Body center (player is 1.8 blocks tall)
        body_center = [px, py + 1, pz]
        
        def make_rotated_model(pos, offset_x=0.0, offset_z=0.0, offset_y=0.0, use_head_yaw=False):
            if use_head_yaw:
                angle = radians(yaw + 90)  # Head uses normal yaw
            else:
                angle = radians(body_yaw + 90)  # Rest uses body_yaw
                
            cos_a = cos(angle)
            sin_a = sin(angle)
            
            rotated_x = offset_x * cos_a - offset_z * sin_a
            rotated_z = offset_x * sin_a + offset_z * cos_a
            
            return np.array([
                [cos_a, 0, sin_a, 0],
                [0, 1, 0, 0],
                [-sin_a, 0, cos_a, 0],
                [pos[0] + rotated_x, pos[1] + offset_y, pos[2] + rotated_z, 1]
            ], dtype='f4')

        # Simple model matrix with Yaw AND Pitch for head
        def make_head_model(pos, offset_x=0.0, offset_z=0.0, offset_y=0.0):
            # Yaw rotation (left/right)
            yaw_rad = radians(yaw + 90)
            cos_yaw = cos(yaw_rad)
            sin_yaw = sin(yaw_rad)
            
            # Pitch rotation (up/down) - around X-axis
            pitch_rad = radians(pitch)
            cos_pitch = cos(pitch_rad)
            sin_pitch = sin(pitch_rad)
            
            # Combined rotation: first Yaw, then Pitch
            # Yaw rotation around Y-axis
            yaw_matrix = np.array([
                [cos_yaw, 0, sin_yaw, 0],
                [0, 1, 0, 0],
                [-sin_yaw, 0, cos_yaw, 0],
                [0, 0, 0, 1]
            ], dtype='f4')
            
            # Pitch rotation around X-axis (after Yaw rotation) - CORRECTED: sign changed
            pitch_matrix = np.array([
                [1, 0, 0, 0],
                [0, cos_pitch, sin_pitch, 0],
                [0, -sin_pitch, cos_pitch, 0],
                [0, 0, 0, 1]
            ], dtype='f4')
            
            # Combined rotation
            rotation_matrix = pitch_matrix @ yaw_matrix
            
            # Add translation
            return np.array([
                [rotation_matrix[0,0], rotation_matrix[0,1], rotation_matrix[0,2], 0],
                [rotation_matrix[1,0], rotation_matrix[1,1], rotation_matrix[1,2], 0],
                [rotation_matrix[2,0], rotation_matrix[2,1], rotation_matrix[2,2], 0],
                [pos[0] + offset_x, pos[1] + offset_y, pos[2] + offset_z, 1]
            ], dtype='f4')

        # Head - WITH YAW AND PITCH
        head_pos = [body_center[0], body_center[1] + 0.625, body_center[2]]  # 0.5 above body
        head_model = make_head_model(head_pos)
        self.prog['model'].write(head_model.tobytes())
        for face in self.entity_vaos['head']:
            self.entity_vaos['head'][face].render()

        # Body - ONLY YAW
        body_model = make_rotated_model(body_center)
        self.prog['model'].write(body_model.tobytes())
        for face in self.entity_vaos['body']:
            self.entity_vaos['body'][face].render()

        # Arms - ONLY YAW
        left_arm_model = make_rotated_model(body_center, offset_x=-0.375, offset_z=0.0)
        self.prog['model'].write(left_arm_model.tobytes())
        for face in self.entity_vaos['left_arm']:
            self.entity_vaos['left_arm'][face].render()
            
        right_arm_model = make_rotated_model(body_center, offset_x=0.375, offset_z=0.0)
        self.prog['model'].write(right_arm_model.tobytes())
        for face in self.entity_vaos['right_arm']:
            self.entity_vaos['right_arm'][face].render()

        # Legs - ONLY YAW
        left_leg_model = make_rotated_model(body_center, offset_x=-0.125, offset_z=0.0, offset_y=-0.75)
        self.prog['model'].write(left_leg_model.tobytes())
        for face in self.entity_vaos['left_leg']:
            self.entity_vaos['left_leg'][face].render()
            
        right_leg_model = make_rotated_model(body_center, offset_x=0.125, offset_z=0.0, offset_y=-0.75)
        self.prog['model'].write(right_leg_model.tobytes())
        for face in self.entity_vaos['right_leg']:
            self.entity_vaos['right_leg'][face].render()

        # Reset to block texture
        self.block_atlas.texture.use(0)

    def world_to_screen_simple(self, world_pos):
        """
        Simple 3D to 2D conversion without matrix reading
        """
        # Use current matrices
        proj = perspective(45.0, self.width / self.height, 0.1, 100.0)
        view = self.camera.get_view_matrix()
        
        # 3D position to 2D screen
        pos = np.array([*world_pos, 1.0], dtype='f4')
        clip = proj @ view @ pos
        
        if clip[3] == 0:
            return None
            
        ndc = clip[:3] / clip[3]
        x = int((ndc[0] * 0.5 + 0.5) * self.width)
        y = int((1.0 - (ndc[1] * 0.5 + 0.5)) * self.height)
        
        if 0 <= x < self.width and 0 <= y < self.height:
            return (x, y)
        return None

    def draw_nametag(self, screen_pos, name):
        # Draw nametag as 2D overlay with pygame
        # CORRECTED: Use current display surface
        surface = pygame.display.get_surface()
        if surface is not None:
            font = pygame.font.SysFont('Arial', 18, bold=True)
            text_surf = font.render(name, True, (255,255,255))
            text_rect = text_surf.get_rect(center=screen_pos)
            surface.blit(text_surf, text_rect)

    def render_debug_info(self, lines):
        # Draw title and list of strings as OpenGL overlay
        text = '[DEBUG] Players on Server:\n' + '\n'.join(lines)
        self.render_text_overlay(text)

    def render_text_overlay(self, text):
        # Create RGBA image with Pillow
        width, height = self.width, self.height
        img = Image.new('RGBA', (width, height), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        try:
            font_title = ImageFont.truetype('arial.ttf', 22)
            font = ImageFont.truetype('arial.ttf', 16)
        except Exception:
            font_title = ImageFont.load_default()
            font = ImageFont.load_default()
        # Title
        y = 8
        draw.text((8, y), '[DEBUG] Players on Server:', font=font_title, fill=(255,255,255,255))
        bbox = font_title.getbbox('[DEBUG] Players on Server:')
        title_height = bbox[3] - bbox[1]
        y += title_height + 4
        # Entries
        for line in text.split('\n')[1:]:
            draw.text((8, y), line, font=font, fill=(255,255,0,255))
            bbox = font.getbbox(line)
            line_height = bbox[3] - bbox[1]
            y += line_height + 2
        # Pillow -> moderngl texture
        data = img.tobytes()
        tex = ctx.texture((width, height), 4, data)
        tex.use(0)
        # Enable blending
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
        # 2D quad for overlay
        prog = ctx.program(
            vertex_shader='''#version 330\nin vec2 in_vert; in vec2 in_tex; out vec2 v_tex; void main() { gl_Position = vec4(in_vert, 0.0, 1.0); v_tex = in_tex; }''',
            fragment_shader='''#version 330\nin vec2 v_tex; uniform sampler2D tex; out vec4 f_color; void main() { f_color = texture(tex, v_tex); }'''
        )
        quad = np.array([
            -1,  1, 0, 0,
            -1, -1, 0, 1,
             1,  1, 1, 0,
             1, -1, 1, 1,
        ], dtype='f4')
        vbo = ctx.buffer(quad.tobytes())
        vao = ctx.vertex_array(prog, [(vbo, '2f 2f', 'in_vert', 'in_tex')])
        prog['tex'].value = 0
        vao.render(moderngl.TRIANGLE_STRIP)
        # Blending wieder deaktivieren
        ctx.disable(moderngl.BLEND)
        tex.release()
        vbo.release()
        vao.release()
        prog.release()

    def resize(self, width, height):
        self.width = width
        self.height = height
        ctx.viewport = (0, 0, width, height)
        proj = perspective(45.0, width / height, 0.1, 100.0)
        self.prog['projection'].write(proj.tobytes())
        self.ui_prog['u_screen_size'].value = (width, height)

# --- Standalone Helper Functions ---

def load_texture(path, nearest=False):
    try:
        img = Image.open(path).convert('RGBA')
        texture = ctx.texture(img.size, 4, img.tobytes())
        if nearest:
            texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        texture.repeat_x = False
        texture.repeat_y = False
        return texture
    except FileNotFoundError:
        print(f"Warning: Texture '{path}' not found. Creating dummy texture.")
        return ctx.texture((64, 64), 4, np.random.rand(64, 64, 4).astype('f4').tobytes()) 