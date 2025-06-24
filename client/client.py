import socket
import threading
import random
import queue
import pygame

from shared.packets import (
    Packet, PlayerMoveRequestPacket, PlaceBlockRequestPacket, BreakBlockRequestPacket, LoginRequestPacket,
    FeedbackPlayerMovePacket, FeedbackBlockChangePacket, FeedbackLoginPacket,
    InfoPlayerMovePacket, InfoBlockChangePacket, InfoPlayerJoinPacket, InfoPlayerLeavePacket, InfoChunkDataPacket
)
from shared.constants import BlockType
from client.render import Renderer
from client.input import InputHandler
from client.inventory import Inventory

class NetworkThread(threading.Thread):
    def __init__(self, host, port, packet_queue):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.packet_queue = packet_queue
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.running = False
        self.player_uuid = None
        self.player_name = None

    def run(self):
        try:
            self.sock.connect((self.host, self.port))
            print(f"Connected to {self.host}:{self.port}")
            self.running = True

            # Send login request
            name = f"Player{random.randint(100,999)}"
            login_packet = LoginRequestPacket(name=name)
            print(f"Requesting login with name: {name}")
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
    def __init__(self, width=1024, height=768):
        self.width = width
        self.height = height
        self.packet_queue = queue.Queue()
        
        # Initialize subsystems
        self.renderer = Renderer(width, height)
        self.input_handler = InputHandler(width, height)
        self.inventory = Inventory()
        
        # Initialize network thread
        self.network = NetworkThread("localhost", 9999, self.packet_queue)
        
        # World state
        self.blocks = {}  # (x, y, z) -> block_type
        self.other_players = {}  # uuid -> {'name': str, 'position': (x, y, z)}
        self.running = True
        self.pending_move = None  # Store pending move position

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
                            'pitch': packet.pitch
                        }
                
                self.packet_queue.task_done()
        
        except queue.Empty:
            pass  # No more packets to process

    def render(self):
        """Render the current frame."""
        self.renderer.clear()

        # Render all blocks with basic culling
        for pos, block_type in self.blocks.items():
            if block_type == BlockType.AIR:
                continue
            faces_to_render = {
                'top':    self.blocks.get((pos[0], pos[1] + 1, pos[2]), BlockType.AIR) == BlockType.AIR,
                'bottom': self.blocks.get((pos[0], pos[1] - 1, pos[2]), BlockType.AIR) == BlockType.AIR,
                'left':   self.blocks.get((pos[0] - 1, pos[1], pos[2]), BlockType.AIR) == BlockType.AIR,
                'right':  self.blocks.get((pos[0] + 1, pos[1], pos[2]), BlockType.AIR) == BlockType.AIR,
                'front':  self.blocks.get((pos[0], pos[1], pos[2] + 1), BlockType.AIR) == BlockType.AIR,
                'back':   self.blocks.get((pos[0], pos[1], pos[2] - 1), BlockType.AIR) == BlockType.AIR,
            }
            if any(faces_to_render.values()):
                self.renderer.render_block(pos, block_type, faces_to_render)

        # Render other players
        for player in self.other_players.values():
            self.renderer.render_player(player['position'], player['name'], yaw=player.get('yaw', 0.0))
        
        # Render test blocks if no blocks exist yet
        if not self.blocks:
            for x in range(-8, 8):
                for z in range(-8, 8):
                    self.renderer.render_block((x, 63, z), BlockType.GRASS, {'top': True})

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

        pos = self.renderer.camera.position.copy()
        
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
        packet = PlayerMoveRequestPacket(pos, yaw, pitch)
        self.network.send(packet)
        self.pending_move = pos

if __name__ == "__main__":
    game = Game()
    game.start() 