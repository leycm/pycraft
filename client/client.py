import socket
import threading
import random
import queue
import pygame
import base64
import os
import numpy as np
import sys

from shared.packets import (
    Packet, PlayerMoveRequestPacket, PlaceBlockRequestPacket, BreakBlockRequestPacket, LoginRequestPacket,
    FeedbackPlayerMovePacket, FeedbackBlockChangePacket, FeedbackLoginPacket,
    InfoPlayerMovePacket, InfoBlockChangePacket, InfoPlayerJoinPacket, InfoPlayerLeavePacket, InfoChunkDataPacket
)
from shared.constants import BlockType
from client.render import Renderer
from client.input import InputHandler
from client.inventory import Inventory

class LoginScreen:
    def __init__(self, width=1024, height=768, default_name="Player", default_host="localhost"):
        self.width = width
        self.height = height
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        
        # Input fields with defaults from command line args
        self.player_name = default_name
        self.server_host = default_host
        self.server_port = "9999"
        
        # Active field (0=name, 1=host, 2=port)
        self.active_field = 0
        
        # Cursor position within each field
        self.cursor_positions = [len(self.player_name), len(self.server_host), len(self.server_port)]
        
        # Cursor state
        self.cursor_visible = True
        self.cursor_timer = 0
        self.cursor_blink_rate = 500  # milliseconds
        
        # Error message
        self.error_message = ""
        self.error_timer = 0
        self.error_duration = 3000  # 3 seconds
        
        # Colors
        self.bg_color = (50, 50, 50)
        self.field_color = (80, 80, 80)
        self.active_field_color = (100, 100, 100)
        self.text_color = (255, 255, 255)
        self.button_color = (0, 120, 0)
        self.button_hover_color = (0, 150, 0)
        self.cursor_color = (255, 255, 255)
        self.error_color = (255, 100, 100)
        
        # Button state
        self.connect_button_rect = pygame.Rect(width//2 - 100, height//2 + 100, 200, 40)
        self.button_hover = False

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    self.active_field = (self.active_field + 1) % 3
                    self.cursor_visible = True
                    self.cursor_timer = 0
                elif event.key == pygame.K_RETURN:
                    return self.try_connect()
                elif event.key == pygame.K_ESCAPE:
                    return False
                elif event.key == pygame.K_BACKSPACE:
                    self.handle_backspace()
                    self.cursor_visible = True
                    self.cursor_timer = 0
                elif event.key == pygame.K_LEFT:
                    self.move_cursor_left()
                    self.cursor_visible = True
                    self.cursor_timer = 0
                elif event.key == pygame.K_RIGHT:
                    self.move_cursor_right()
                    self.cursor_visible = True
                    self.cursor_timer = 0
                elif event.key == pygame.K_HOME:
                    self.cursor_positions[self.active_field] = 0
                    self.cursor_visible = True
                    self.cursor_timer = 0
                elif event.key == pygame.K_END:
                    self.cursor_positions[self.active_field] = self.get_current_field_length()
                    self.cursor_visible = True
                    self.cursor_timer = 0
                else:
                    self.handle_text_input(event)
                    self.cursor_visible = True
                    self.cursor_timer = 0
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    if self.connect_button_rect.collidepoint(event.pos):
                        return self.try_connect()
                    else:
                        # Check which field was clicked and set cursor position
                        self.handle_field_click(event.pos)
                        self.cursor_visible = True
                        self.cursor_timer = 0
            
            elif event.type == pygame.MOUSEMOTION:
                self.button_hover = self.connect_button_rect.collidepoint(event.pos)
        
        # Update cursor blink
        self.cursor_timer += 16  # Assuming 60 FPS
        if self.cursor_timer >= self.cursor_blink_rate:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0
        
        # Update error message timer
        if self.error_message:
            self.error_timer += 16
            if self.error_timer >= self.error_duration:
                self.error_message = ""
                self.error_timer = 0
        
        return None  # Continue showing login screen

    def get_current_field_length(self):
        if self.active_field == 0:
            return len(self.player_name)
        elif self.active_field == 1:
            return len(self.server_host)
        elif self.active_field == 2:
            return len(self.server_port)
        return 0

    def move_cursor_left(self):
        if self.cursor_positions[self.active_field] > 0:
            self.cursor_positions[self.active_field] -= 1

    def move_cursor_right(self):
        max_pos = self.get_current_field_length()
        if self.cursor_positions[self.active_field] < max_pos:
            self.cursor_positions[self.active_field] += 1

    def handle_backspace(self):
        if self.active_field == 0 and len(self.player_name) > 0:
            if self.cursor_positions[0] > 0:
                self.player_name = self.player_name[:self.cursor_positions[0]-1] + self.player_name[self.cursor_positions[0]:]
                self.cursor_positions[0] -= 1
        elif self.active_field == 1 and len(self.server_host) > 0:
            if self.cursor_positions[1] > 0:
                self.server_host = self.server_host[:self.cursor_positions[1]-1] + self.server_host[self.cursor_positions[1]:]
                self.cursor_positions[1] -= 1
        elif self.active_field == 2 and len(self.server_port) > 0:
            if self.cursor_positions[2] > 0:
                self.server_port = self.server_port[:self.cursor_positions[2]-1] + self.server_port[self.cursor_positions[2]:]
                self.cursor_positions[2] -= 1

    def handle_text_input(self, event):
        if event.unicode.isprintable():
            if self.active_field == 0:
                if len(self.player_name) < 20:  # Limit name length
                    self.player_name = self.player_name[:self.cursor_positions[0]] + event.unicode + self.player_name[self.cursor_positions[0]:]
                    self.cursor_positions[0] += 1
            elif self.active_field == 1:
                if len(self.server_host) < 50:  # Limit host length
                    self.server_host = self.server_host[:self.cursor_positions[1]] + event.unicode + self.server_host[self.cursor_positions[1]:]
                    self.cursor_positions[1] += 1
            elif self.active_field == 2:
                if event.unicode.isdigit() and len(self.server_port) < 5:  # Limit port length
                    self.server_port = self.server_port[:self.cursor_positions[2]] + event.unicode + self.server_port[self.cursor_positions[2]:]
                    self.cursor_positions[2] += 1

    def handle_field_click(self, pos):
        # Check if any field was clicked
        name_rect = pygame.Rect(self.width//2 - 150, self.height//2 - 50, 300, 40)
        host_rect = pygame.Rect(self.width//2 - 150, self.height//2, 300, 40)
        port_rect = pygame.Rect(self.width//2 - 150, self.height//2 + 50, 300, 40)
        
        if name_rect.collidepoint(pos):
            self.active_field = 0
            self.set_cursor_position_from_click(pos, name_rect, self.player_name)
        elif host_rect.collidepoint(pos):
            self.active_field = 1
            self.set_cursor_position_from_click(pos, host_rect, self.server_host)
        elif port_rect.collidepoint(pos):
            self.active_field = 2
            self.set_cursor_position_from_click(pos, port_rect, self.server_port)

    def set_cursor_position_from_click(self, click_pos, field_rect, text):
        # Calculate cursor position based on click position
        click_x = click_pos[0] - field_rect.x - 10  # 10 is padding
        if click_x < 0:
            self.cursor_positions[self.active_field] = 0
            return
        
        # Find the closest character position
        font = self.font
        best_pos = 0
        min_distance = float('inf')
        
        for i in range(len(text) + 1):
            test_text = text[:i]
            text_width = font.size(test_text)[0]
            distance = abs(text_width - click_x)
            if distance < min_distance:
                min_distance = distance
                best_pos = i
        
        self.cursor_positions[self.active_field] = best_pos

    def show_error(self, message):
        self.error_message = message
        self.error_timer = 0

    def try_connect(self):
        # Validate inputs
        if not self.player_name.strip():
            self.show_error("Please enter a player name!")
            return None
        
        if not self.server_host.strip():
            self.show_error("Please enter a server host!")
            return None
        
        try:
            port = int(self.server_port)
            if port < 1 or port > 65535:
                self.show_error("Port must be between 1 and 65535!")
                return None
        except ValueError:
            self.show_error("Port must be a valid number!")
            return None
        
        return {
            'player_name': self.player_name.strip(),
            'server_host': self.server_host.strip(),
            'server_port': port
        }

    def render(self, screen):
        screen.fill(self.bg_color)
        
        # Title
        title = self.font.render("PyCraft - Login", True, self.text_color)
        title_rect = title.get_rect(center=(self.width//2, self.height//2 - 150))
        screen.blit(title, title_rect)
        
        # Error message
        if self.error_message:
            error_text = self.small_font.render(self.error_message, True, self.error_color)
            error_rect = error_text.get_rect(center=(self.width//2, self.height//2 - 120))
            screen.blit(error_text, error_rect)
        
        # Player name field
        name_label = self.small_font.render("Player Name:", True, self.text_color)
        name_label_rect = name_label.get_rect(center=(self.width//2 - 200, self.height//2 - 30))
        screen.blit(name_label, name_label_rect)
        
        name_rect = pygame.Rect(self.width//2 - 150, self.height//2 - 50, 300, 40)
        name_color = self.active_field_color if self.active_field == 0 else self.field_color
        pygame.draw.rect(screen, name_color, name_rect)
        pygame.draw.rect(screen, self.text_color, name_rect, 2)
        
        name_text = self.font.render(self.player_name, True, self.text_color)
        name_text_rect = name_text.get_rect(midleft=(name_rect.x + 10, name_rect.centery))
        screen.blit(name_text, name_text_rect)
        
        # Draw cursor for player name field
        if self.active_field == 0 and self.cursor_visible:
            cursor_text = self.player_name[:self.cursor_positions[0]]
            cursor_width = self.font.size(cursor_text)[0]
            cursor_x = name_text_rect.x + cursor_width
            cursor_y = name_text_rect.centery
            pygame.draw.line(screen, self.cursor_color, 
                           (cursor_x, cursor_y - 15), (cursor_x, cursor_y + 15), 2)
        
        # Server host field
        host_label = self.small_font.render("Server Host:", True, self.text_color)
        host_label_rect = host_label.get_rect(center=(self.width//2 - 200, self.height//2 + 20))
        screen.blit(host_label, host_label_rect)
        
        host_rect = pygame.Rect(self.width//2 - 150, self.height//2, 300, 40)
        host_color = self.active_field_color if self.active_field == 1 else self.field_color
        pygame.draw.rect(screen, host_color, host_rect)
        pygame.draw.rect(screen, self.text_color, host_rect, 2)
        
        host_text = self.font.render(self.server_host, True, self.text_color)
        host_text_rect = host_text.get_rect(midleft=(host_rect.x + 10, host_rect.centery))
        screen.blit(host_text, host_text_rect)
        
        # Draw cursor for server host field
        if self.active_field == 1 and self.cursor_visible:
            cursor_text = self.server_host[:self.cursor_positions[1]]
            cursor_width = self.font.size(cursor_text)[0]
            cursor_x = host_text_rect.x + cursor_width
            cursor_y = host_text_rect.centery
            pygame.draw.line(screen, self.cursor_color, 
                           (cursor_x, cursor_y - 15), (cursor_x, cursor_y + 15), 2)
        
        # Server port field
        port_label = self.small_font.render("Server Port:", True, self.text_color)
        port_label_rect = port_label.get_rect(center=(self.width//2 - 200, self.height//2 + 70))
        screen.blit(port_label, port_label_rect)
        
        port_rect = pygame.Rect(self.width//2 - 150, self.height//2 + 50, 300, 40)
        port_color = self.active_field_color if self.active_field == 2 else self.field_color
        pygame.draw.rect(screen, port_color, port_rect)
        pygame.draw.rect(screen, self.text_color, port_rect, 2)
        
        port_text = self.font.render(self.server_port, True, self.text_color)
        port_text_rect = port_text.get_rect(midleft=(port_rect.x + 10, port_rect.centery))
        screen.blit(port_text, port_text_rect)
        
        # Draw cursor for server port field
        if self.active_field == 2 and self.cursor_visible:
            cursor_text = self.server_port[:self.cursor_positions[2]]
            cursor_width = self.font.size(cursor_text)[0]
            cursor_x = port_text_rect.x + cursor_width
            cursor_y = port_text_rect.centery
            pygame.draw.line(screen, self.cursor_color, 
                           (cursor_x, cursor_y - 15), (cursor_x, cursor_y + 15), 2)
        
        # Connect button
        button_color = self.button_hover_color if self.button_hover else self.button_color
        pygame.draw.rect(screen, button_color, self.connect_button_rect)
        pygame.draw.rect(screen, self.text_color, self.connect_button_rect, 2)
        
        connect_text = self.font.render("Connect", True, self.text_color)
        connect_text_rect = connect_text.get_rect(center=self.connect_button_rect.center)
        screen.blit(connect_text, connect_text_rect)
        
        # Instructions
        instructions = [
            "Tab: Switch between fields",
            "Arrow keys: Move cursor",
            "Home/End: Jump to start/end",
            "Enter: Connect to server",
            "Escape: Exit game",
            "Click to place cursor"
        ]
        
        for i, instruction in enumerate(instructions):
            inst_text = self.small_font.render(instruction, True, (150, 150, 150))
            inst_rect = inst_text.get_rect(center=(self.width//2, self.height//2 + 180 + i * 25))
            screen.blit(inst_text, inst_rect)

class NetworkThread(threading.Thread):
    def __init__(self, host, port, packet_queue, player_name=None):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.packet_queue = packet_queue
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.running = False
        self.player_uuid = None
        self.player_name = player_name or f"Player{random.randint(100,999)}"

    def run(self):
        try:
            self.sock.connect((self.host, self.port))
            print(f"Connected to {self.host}:{self.port}")
            self.running = True

            # Send login request with custom name
            login_packet = LoginRequestPacket(name=self.player_name)
            print(f"Requesting login with name: {self.player_name}")
            self.send(login_packet)

            while self.running:
                try:
                    data = Packet.recv_full_packet(self.sock)
                    if not data:
                        print("Connection lost.")
                        break

                    packet = Packet.unpack(data)
                    self.handle_packet(packet)

                except Exception as e:
                    print(f"Error while listening to server: {e}")
                    break

        except ConnectionRefusedError:
            print(f"Connection refused. Is the server running on {self.host}:{self.port}?")
        finally:
            self.stop()

    def handle_packet(self, packet):
        if isinstance(packet, FeedbackLoginPacket):
            if packet.success == 1:
                self.player_uuid = packet.uuid
                self.player_name = packet.name
                print(f"Login accepted! UUID: {self.player_uuid}, Name: {self.player_name}")
            else:
                print("[SERVER] Login abgelehnt!")
                self.running = False
        
        self.packet_queue.put(packet)

    def send(self, packet):
        if not self.running:
            return
        try:
            self.sock.sendall(packet.pack())
        except Exception as e:
            print(f"Failed to send packet: {e}")
            self.stop()

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.sock.close()
        print("Disconnected from server.")

class Game:
    def __init__(self, width=1024, height=768, connection_params=None):
        self.width = width
        self.height = height
        self.packet_queue = queue.Queue()
        
        # Initialize subsystems
        self.renderer = Renderer(width, height)
        self.input_handler = InputHandler(width, height)
        self.inventory = Inventory()
        
        # Initialize network thread with connection params
        if connection_params:
            self.network = NetworkThread(
                connection_params['server_host'], 
                connection_params['server_port'], 
                self.packet_queue,
                connection_params['player_name']
            )
        else:
            self.network = NetworkThread("localhost", 9999, self.packet_queue)
        
        # World state
        self.blocks = {}  # (x, y, z) -> block_type
        self.other_players = {}  # uuid -> {'name': str, 'position': (x, y, z)}
        self.running = True
        self.pending_move = None  # Store pending move position
        self.player_skins = {}  # uuid -> skin_data (base64 PNG)

    def start(self):
        # Start network thread
        self.network.start()
        
        # Main game loop
        clock = pygame.time.Clock()
        while self.running:
            # Handle window resize events
            for event in pygame.event.get(pump=False):
                if event.type == pygame.VIDEORESIZE:
                    self.renderer.resize(event.w, event.h)
            # Process network packets
            self.process_network_packets()
            
            # Handle input (returns False if should quit)
            if not self.input_handler.handle_events(
                self.renderer.camera, self.inventory, self.on_break, self.on_place
            ):
                self.running = False
                break
            
            # Sende aktuelle Position an den Server
            self.send_player_position()
            
            # Render frame
            self.render()
            
            # Cap at 60 FPS
            clock.tick(60)
        
        # Cleanup
        self.network.stop()
        pygame.quit()

    def process_network_packets(self):
        """Process all pending network packets."""
        try:
            while True:  # Process all packets in the queue
                packet = self.packet_queue.get_nowait()
                
                if isinstance(packet, InfoBlockChangePacket):
                    pos = packet.position
                    self.blocks[pos] = packet.block_type
                
                elif isinstance(packet, InfoPlayerJoinPacket):
                    if packet.uuid != self.network.player_uuid:
                        print(f"[SERVER INFO] Player {packet.name} joined the game")
                    if hasattr(packet, 'skin_data') and packet.skin_data:
                        self.player_skins[packet.uuid] = packet.skin_data
                
                elif isinstance(packet, FeedbackPlayerMovePacket):
                    # Nur wenn erlaubt, Position übernehmen
                    if packet.success == 1 and self.pending_move:
                        self.renderer.camera.position = list(self.pending_move)
                        self.pending_move = None
                    elif packet.success == 0:
                        print("[SERVER] Deine Bewegung wurde abgelehnt/gecancelt!")
                        self.pending_move = None
                
                elif isinstance(packet, FeedbackBlockChangePacket):
                    if packet.success == 1:
                        self.blocks[packet.position] = packet.block_type
                    else:
                        print("[SERVER] Block-Änderung nicht erlaubt/gecancelt!")
                
                elif isinstance(packet, InfoPlayerMovePacket):
                    # Update other players' positions und Rotation
                    if packet.uuid != self.network.player_uuid:
                        self.other_players[packet.uuid] = {
                            'name': packet.name,
                            'position': packet.position,
                            'yaw': packet.yaw,
                            'pitch': packet.pitch,
                            'skin_data': getattr(packet, 'skin_data', None)
                        }
                        if getattr(packet, 'skin_data', None):
                            self.player_skins[packet.uuid] = packet.skin_data
                
                self.packet_queue.task_done()
        
        except queue.Empty:
            pass  # No more packets to process

    def render(self):
        """Render the current frame."""
        self.renderer.clear()

        # Render all blocks with improved culling
        for pos, block_type in self.blocks.items():
            if block_type == BlockType.AIR:
                continue
            
            # Check which faces are visible (adjacent to air blocks)
            faces_to_render = {
                'top':    self.blocks.get((pos[0], pos[1] + 1, pos[2]), BlockType.AIR) == BlockType.AIR,
                'bottom': self.blocks.get((pos[0], pos[1] - 1, pos[2]), BlockType.AIR) == BlockType.AIR,
                'left':   self.blocks.get((pos[0] - 1, pos[1], pos[2]), BlockType.AIR) == BlockType.AIR,
                'right':  self.blocks.get((pos[0] + 1, pos[1], pos[2]), BlockType.AIR) == BlockType.AIR,
                'front':  self.blocks.get((pos[0], pos[1], pos[2] + 1), BlockType.AIR) == BlockType.AIR,
                'back':   self.blocks.get((pos[0], pos[1], pos[2] - 1), BlockType.AIR) == BlockType.AIR,
            }
            
            # Only render if at least one face is visible
            if any(faces_to_render.values()):
                self.renderer.render_block(pos, block_type, faces_to_render)

        # Render other players
        for player in self.other_players.values():
            skin_data = player.get('skin_data') or self.player_skins.get(player['name'])
            self.renderer.render_player(
                player['position'],
                player['name'],
                yaw=player.get('yaw', 0.0),
                pitch=player.get('pitch', 0.0),
                body_yaw=player.get('yaw', 0.0),
                skin_data=skin_data
            )
        
        # Render test blocks if no blocks exist yet
        if not self.blocks:
            for x in range(-8, 8):
                for z in range(-8, 8):
                    # Render all faces for test blocks to make them look like proper 3D cubes
                    self.renderer.render_block((x, 63, z), BlockType.GRASS, {
                        'top': True, 'bottom': True, 'left': True, 'right': True, 'front': True, 'back': True
                    })

        # Eigenen Spieler nur im Third-Person-Modus rendern
        if self.renderer.camera.third_person:
            self.renderer.render_player(
                self.renderer.camera.position,
                self.network.player_name or "Du",
                yaw=self.renderer.camera.yaw,
                pitch=self.renderer.camera.pitch,
                body_yaw=getattr(self.renderer, '_last_body_yaw', self.renderer.camera.yaw)
            )
        self.renderer.render_ui(self.inventory)
        
        # Debug-Overlay: Liste aller Spieler (jetzt GANZ am Ende!)
        player_list = []
        my_name = self.network.player_name or "Du"
        my_pos = tuple(round(float(x), 2) for x in self.renderer.camera.position)
        player_list.append(f"{my_name} (YOU): {my_pos}")
        for p in self.other_players.values():
            pos = tuple(round(float(x), 2) for x in p['position'])
            player_list.append(f"{p['name']}: {pos}")
        self.renderer.render_debug_info(player_list)
        
        pygame.display.flip()

    def get_targeted_block(self):
        """
        Performs a simple raycast to find the block the player is looking at.
        Returns (block_to_break, block_to_place_against).
        This is a simplified implementation.
        """
        reach = 5
        step = 0.1

        # Start raycast from the appropriate position
        if self.renderer.camera.third_person:
            # In third-person mode, start from player's actual position (not camera position)
            # This ensures block breaking/placing originates from the player's head
            player_eye_pos = self.renderer.camera.position + np.array([0, self.renderer.camera.eyeh, 0])
            pos = player_eye_pos.copy()
        else:
            # In first-person mode, use camera eye position as usual
            eye_pos = self.renderer.camera.get_eye_position()
            pos = eye_pos.copy()
        
        last_pos = None
        for _ in range(int(reach / step)):
            pos += self.renderer.camera.front * step
            
            # Round to get integer block coordinates
            block_pos = (round(pos[0]), round(pos[1]), round(pos[2]))
            
            # If we hit a block that exists in our world state
            if block_pos in self.blocks and self.blocks[block_pos] != BlockType.AIR:
                return block_pos, last_pos # (block_to_break, position_to_place)

            last_pos = block_pos
        
        return None, None

    def on_break(self):
        """Callback for when the user tries to break a block."""
        block_to_break, _ = self.get_targeted_block()
        if block_to_break:
            self.try_break_block(block_to_break)
    
    def on_place(self):
        """Callback for when the user tries to place a block."""
        _, block_to_place_against = self.get_targeted_block()
        selected_item = self.inventory.get_selected_item()
        
        if block_to_place_against and selected_item != BlockType.AIR:
            self.try_place_block(block_to_place_against, selected_item)

    def try_break_block(self, position):
        """Send a block break request to the server."""
        packet = BreakBlockRequestPacket(position=position)
        self.network.send(packet)

    def try_place_block(self, position, block_type):
        """Send a block place request to the server."""
        packet = PlaceBlockRequestPacket(position=position, block_type=block_type)
        self.network.send(packet)

    def send_player_position(self):
        # Sende die aktuelle Kameraposition und Rotation an den Server
        pos = tuple(float(x) for x in self.renderer.camera.position)
        yaw = float(self.renderer.camera.yaw)
        pitch = float(self.renderer.camera.pitch)
        sneaking = getattr(self.input_handler, 'sneaking', False)
        packet = PlayerMoveRequestPacket(pos, yaw, pitch, sneaking)
        self.network.send(packet)
        self.pending_move = pos

def test_server_connection(host, port, timeout=5):
    """Test if server is reachable before starting the game."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except Exception:
        return False

if __name__ == "__main__":
    # Parse command line arguments
    default_name = "Player"
    default_host = "localhost"
    
    if len(sys.argv) >= 2:
        default_name = sys.argv[1]
    if len(sys.argv) >= 3:
        default_host = sys.argv[2]
    
    print(f"Starting PyCraft client with name: {default_name}, host: {default_host}")
    
    # Initialize pygame
    pygame.init()
    screen = pygame.display.set_mode((1024, 768), pygame.RESIZABLE)
    pygame.display.set_caption(f"PyCraft - {default_name}")
    
    # Show login screen with defaults from command line args
    login_screen = LoginScreen(1024, 768, default_name, default_host)
    clock = pygame.time.Clock()
    
    connection_params = None
    while connection_params is None:
        result = login_screen.handle_events()
        if result is False:  # User wants to quit
            pygame.quit()
            exit()
        elif result is not None:  # User wants to connect
            # Test connection before starting game
            print(f"Testing connection to {result['server_host']}:{result['server_port']}...")
            if test_server_connection(result['server_host'], result['server_port']):
                connection_params = result
                print("Connection test successful!")
            else:
                login_screen.show_error(f"Cannot connect to {result['server_host']}:{result['server_port']}")
                print("Connection test failed!")
        
        # Render login screen
        login_screen.render(screen)
        pygame.display.flip()
        clock.tick(60)
    
    # Lade eigene Skin-Datei als base64
    skin_data = None
    skin_path = 'assets/player_custom.png'
    if os.path.exists(skin_path):
        with open(skin_path, 'rb') as f:
            skin_data = base64.b64encode(f.read()).decode('ascii')
    
    # Start game with connection parameters
    game = Game(connection_params=connection_params)
    
    # Patch network thread to send skin_data
    orig_login = game.network.send
    def send_with_skin(packet):
        if isinstance(packet, LoginRequestPacket):
            packet.skin_data = skin_data
        orig_login(packet)
    game.network.send = send_with_skin
    
    game.start() 