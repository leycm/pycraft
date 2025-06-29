import socketserver
import random
import threading
import time
import struct
import uuid

from shared.packets import (
    Packet, PlayerMoveRequestPacket, PlaceBlockRequestPacket, BreakBlockRequestPacket, LoginRequestPacket,
    FeedbackPlayerMovePacket, FeedbackBlockChangePacket, FeedbackLoginPacket,
    InfoPlayerMovePacket, InfoBlockChangePacket, InfoPlayerJoinPacket, InfoPlayerLeavePacket, InfoChunkDataPacket
)

from server.player import Player
from server.world import World
from shared.constants import BlockType, CHUNK_WIDTH, CHUNK_DEPTH

CLIENTS_LOCK = threading.Lock()

def generate_uuid():
    """Generate a proper UUID for players."""
    return str(uuid.uuid4())

def generate_name():
    """Generates a random player name."""
    adjectives = ["Happy", "Sad", "Crazy", "Lazy", "Quick"]
    nouns = ["Llama", "Panda", "Tiger", "Eagle", "Wolf"]
    return f"{random.choice(adjectives)}{random.choice(nouns)}{random.randint(10,99)}"


class TCPHandler(socketserver.BaseRequestHandler):
    """
    The request handler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """
    def setup(self):
        """Called before the handle() method."""
        super().setup()
        self.player = None
        # self.server is the ThreadingTCPServer instance
        self.clients = self.server.clients
        self.world = self.server.world

    def handle(self):
        # self.request is the TCP socket connected to the client
        print(f"Client connected: {self.client_address[0]}")
        try:
            data = Packet.recv_full_packet(self.request)
            if not data:
                return

            packet = Packet.unpack(data)
            if not isinstance(packet, LoginRequestPacket):
                print(f"Client {self.client_address[0]} sent wrong first packet. Disconnecting.")
                return

            uuid = generate_uuid()
            name = packet.name or generate_name()
            self.player = Player(uuid, name, self.request, self.client_address)

            with CLIENTS_LOCK:
                self.server.clients[uuid] = self.player

            print(f"Player {name} (uuid: {uuid}) logged in from {self.client_address[0]}")

            feedback = FeedbackLoginPacket(1, uuid, name, packet_id=packet.packet_id)
            self.request.sendall(feedback.pack())

            join_packet = InfoPlayerJoinPacket(uuid=uuid, name=name)
            packed_join_packet = join_packet.pack()
            with CLIENTS_LOCK:
                for client_player in self.server.clients.values():
                    if client_player is not self.player:
                        try:
                            client_player.client_socket.sendall(packed_join_packet)
                        except Exception as e:
                            print(f"Error sending join info to {client_player.name}: {e}")

            # 3. Send the initial world state (spawn chunk) to the new client
            print(f"Sending spawn chunk to {self.player.name}...")
            spawn_chunk = self.world.get_chunk(0, 0)
            for x in range(spawn_chunk.blocks.shape[0]):
                for y in range(spawn_chunk.blocks.shape[1]):
                    for z in range(spawn_chunk.blocks.shape[2]):
                        block_type = spawn_chunk.blocks[x, y, z]
                        if block_type != BlockType.AIR:
                            # Convert local chunk coords to world coords
                            world_x = 0 * CHUNK_WIDTH + x
                            world_z = 0 * CHUNK_DEPTH + z
                            pos = (world_x, y, world_z)
                            change_packet = InfoBlockChangePacket(position=pos, block_type=block_type)
                            self.request.sendall(change_packet.pack())
            print(f"Finished sending spawn chunk to {self.player.name}.")

            # Main loop for this client
            while True:
                data = Packet.recv_full_packet(self.request)
                if not data:
                    break
                packet = Packet.unpack(data)
                self.handle_packet(packet)

        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            print(f"An error occurred with client {self.client_address[0]}: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Removes the player and notifies others."""
        if self.player:
            print(f"Player {self.player.name} disconnected.")
            with CLIENTS_LOCK:
                if self.player.uuid in self.server.clients:
                    del self.server.clients[self.player.uuid]
            # TODO: Broadcast InfoPlayerLeave
        else:
            print(f"Client {self.client_address[0]} disconnected before login.")
        self.request.close()

    def handle_packet(self, packet):
        """Processes a received packet."""
        print(f"Received packet {type(packet).__name__} from {self.player.name}")

        if isinstance(packet, PlaceBlockRequestPacket):
            # Beispiel: Block setzen nur erlaubt, wenn Feld leer ist
            pos = packet.position
            block_type = packet.block_type
            allowed = self.world.get_block(*pos) == BlockType.AIR
            if allowed:
                self.world.set_block(*pos, block_type)
                feedback = FeedbackBlockChangePacket(1, pos, block_type, packet_id=packet.packet_id)
            else:
                feedback = FeedbackBlockChangePacket(0, pos, block_type, packet_id=packet.packet_id)
            self.request.sendall(feedback.pack())
            if allowed:
                change_packet = InfoBlockChangePacket(position=pos, block_type=block_type)
                self.broadcast(change_packet)

        elif isinstance(packet, BreakBlockRequestPacket):
            pos = packet.position
            allowed = self.world.get_block(*pos) != BlockType.AIR
            if allowed:
                self.world.set_block(*pos, BlockType.AIR)
                feedback = FeedbackBlockChangePacket(1, pos, BlockType.AIR, packet_id=packet.packet_id)
            else:
                feedback = FeedbackBlockChangePacket(0, pos, BlockType.AIR, packet_id=packet.packet_id)
            self.request.sendall(feedback.pack())
            if allowed:
                change_packet = InfoBlockChangePacket(position=pos, block_type=BlockType.AIR)
                self.broadcast(change_packet)

        elif isinstance(packet, PlayerMoveRequestPacket):
            pos = packet.position
            yaw = packet.yaw
            pitch = packet.pitch
            sneaking = getattr(packet, 'sneaking', False)
            self.player.position = pos
            self.player.yaw = yaw
            self.player.pitch = pitch
            self.player.sneaking = sneaking
            feedback = FeedbackPlayerMovePacket(1, pos, packet_id=packet.packet_id)
            self.request.sendall(feedback.pack())

    def broadcast(self, packet, exclude=None):
        """Sends a packet to all connected clients, optionally excluding some by uuid."""
        packed_packet = packet.pack()
        if exclude is None:
            exclude = []
        with CLIENTS_LOCK:
            for client_player in self.server.clients.values():
                if hasattr(client_player, 'uuid') and client_player.uuid in exclude:
                    continue
                try:
                    client_player.client_socket.sendall(packed_packet)
                except Exception as e:
                    print(f"Error broadcasting to {client_player.name}: {e}")


class ThreadingTCPServer(socketserver.ThreadingTCPServer):
    """A ThreadingTCPServer that holds a list of clients."""
    def __init__(self, server_address, RequestHandlerClass, world):
        super().__init__(server_address, RequestHandlerClass)
        self.clients = {}
        self.world = world
        self.daemon_threads = True
        self._broadcast_thread = threading.Thread(target=self.broadcast_player_positions_loop, daemon=True)
        self._broadcast_thread.start()

    def broadcast_player_positions_loop(self):
        while True:
            with CLIENTS_LOCK:
                for player in self.clients.values():
                    packet = InfoPlayerMovePacket(player.uuid, player.name, player.position, getattr(player, 'yaw', 0.0), getattr(player, 'pitch', 0.0))
                    packed = packet.pack()
                    for other in self.clients.values():
                        try:
                            other.client_socket.sendall(packed)
                        except Exception:
                            pass
            time.sleep(0.1)


if __name__ == "__main__":
    HOST, PORT = "localhost", 9999

    print("Initializing world...")
    world = World()
    world.get_chunk(0, 0)

    print(f"Starting server on {HOST}:{PORT}")
    with ThreadingTCPServer((HOST, PORT), TCPHandler, world) as server:
        server.serve_forever() 