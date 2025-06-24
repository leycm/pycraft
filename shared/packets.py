import struct
from enum import IntEnum

PACKET_REGISTRY = {}

def register_packet(cls):
    """A class decorator to register packet types."""
    if hasattr(cls, 'PACKET_TYPE') and cls.PACKET_TYPE != -1:
        PACKET_REGISTRY[cls.PACKET_TYPE] = cls
    return cls

class PacketType(IntEnum):
    # C -> S
    C_S_PLAYER_MOVE_REQUEST = 1
    C_S_PLACE_BLOCK_REQUEST = 2
    C_S_BREAK_BLOCK_REQUEST = 3
    C_S_LOGIN_REQUEST = 4

    # S -> C
    S_C_FEEDBACK_PLAYER_MOVE = 101
    S_C_FEEDBACK_BLOCK_CHANGE = 102
    S_C_FEEDBACK_LOGIN = 103

    # S -> C (Broadcast)
    S_C_INFO_PLAYER_MOVE = 201
    S_C_INFO_BLOCK_CHANGE = 202
    S_C_INFO_PLAYER_JOIN = 203
    S_C_INFO_PLAYER_LEAVE = 204
    S_C_INFO_CHUNK_DATA = 205

def pack_string(s):
    encoded = s.encode('utf-8')
    return struct.pack(f'!H{len(encoded)}s', len(encoded), encoded)

def unpack_string(data):
    length = struct.unpack('!H', data[:2])[0]

    s = struct.unpack(f'!{length}s', data[2:2+length])[0]

    return s.decode('utf-8'), data[2+length:]

class Packet:
    """Base class for all packets."""
    HEADER_FORMAT = '!Bq'  # Unsigned Char (1 byte), Long Long (8 bytes)
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    PACKET_TYPE = -1

    def __init__(self, packet_id=0):
        self.packet_id = packet_id

    def pack(self):
        """Packs the entire packet (header + body) into bytes, with a 4-byte length prefix."""
        header = struct.pack(self.HEADER_FORMAT, self.PACKET_TYPE, self.packet_id)
        body = self._pack_body()
        packet = header + body
        length_prefix = struct.pack('!I', len(packet))  # 4-byte unsigned int, big-endian
        return length_prefix + packet

    def _pack_body(self):
        """
        Packs the packet-specific data (body).
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement _pack_body")

    @staticmethod
    def recv_full_packet(sock):
        """Receives a full packet from the socket, using the 4-byte length prefix."""
        # Read 4 bytes for the length
        length_data = b''
        while len(length_data) < 4:
            more = sock.recv(4 - len(length_data))
            if not more:
                raise ConnectionError("Socket closed while reading packet length")
            length_data += more
        packet_length = struct.unpack('!I', length_data)[0]
        # Now read the full packet
        packet_data = b''
        while len(packet_data) < packet_length:
            more = sock.recv(packet_length - len(packet_data))
            if not more:
                raise ConnectionError("Socket closed while reading packet data")
            packet_data += more
        return packet_data

    @staticmethod
    def unpack(data):
        """
        Unpacks raw bytes into a specific Packet object.
        This acts as a factory.
        """
        if len(data) < Packet.HEADER_SIZE:
            raise ValueError("Data too short for packet header")

        packet_type_id, packet_id = struct.unpack(Packet.HEADER_FORMAT, data[:Packet.HEADER_SIZE])
        
        packet_class = PACKET_REGISTRY.get(packet_type_id)
        if not packet_class:
            raise ValueError(f"Unknown packet type ID: {packet_type_id}")

        body_data = data[Packet.HEADER_SIZE:]
        return packet_class._unpack_body(body_data, packet_id)

    @classmethod
    def _unpack_body(cls, body_data, packet_id):
        """
        Creates a packet instance from the body data.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement _unpack_body")

# --- C -> S Packets ---

@register_packet
class PlayerMoveRequestPacket(Packet):
    """Client sends this to request a move (player position update)."""
    PACKET_TYPE = PacketType.C_S_PLAYER_MOVE_REQUEST

    def __init__(self, position, yaw, pitch, packet_id=0):
        super().__init__(packet_id)
        self.position = position  # (x, y, z)
        self.yaw = yaw
        self.pitch = pitch

    def _pack_body(self):
        return struct.pack('fff', *self.position) + struct.pack('ff', self.yaw, self.pitch)

    @classmethod
    def _unpack_body(cls, body_data, packet_id):
        x, y, z, yaw, pitch = struct.unpack('fff' + 'ff', body_data)
        return cls((x, y, z), yaw, pitch, packet_id=packet_id)

@register_packet
class PlaceBlockRequestPacket(Packet):
    """Client sends this to try to place a block."""
    PACKET_TYPE = PacketType.C_S_PLACE_BLOCK_REQUEST
    BODY_FORMAT = '!iiiB' # x, y, z (int), block_type (byte)

    def __init__(self, position, block_type, packet_id=0):
        super().__init__(packet_id)
        self.position = position
        self.block_type = block_type

    def _pack_body(self):
        return struct.pack(self.BODY_FORMAT, self.position[0], self.position[1], self.position[2], self.block_type)

    @classmethod
    def _unpack_body(cls, body_data, packet_id):
        x, y, z, block_type = struct.unpack(cls.BODY_FORMAT, body_data)
        return cls(position=(x, y, z), block_type=block_type, packet_id=packet_id)

@register_packet
class BreakBlockRequestPacket(Packet):
    """Client sends this to try to break a block."""
    PACKET_TYPE = PacketType.C_S_BREAK_BLOCK_REQUEST
    BODY_FORMAT = '!iii' # x, y, z (int)

    def __init__(self, position, packet_id=0):
        super().__init__(packet_id)
        self.position = position

    def _pack_body(self):
        return struct.pack(self.BODY_FORMAT, self.position[0], self.position[1], self.position[2])

    @classmethod
    def _unpack_body(cls, body_data, packet_id):
        x, y, z = struct.unpack(cls.BODY_FORMAT, body_data)
        return cls(position=(x, y, z), packet_id=packet_id)

@register_packet
class LoginRequestPacket(Packet):
    """Client sends this to request login."""
    PACKET_TYPE = PacketType.C_S_LOGIN_REQUEST

    def __init__(self, name, packet_id=0):
        super().__init__(packet_id)
        self.name = name

    def _pack_body(self):
        return pack_string(self.name)

    @classmethod
    def _unpack_body(cls, body_data, packet_id):
        name, _ = unpack_string(body_data)
        return cls(name=name, packet_id=packet_id)

# --- S -> C Packets ---

@register_packet
class FeedbackPlayerMovePacket(Packet):
    """Server feedback for player move (accept/reject)."""
    PACKET_TYPE = PacketType.S_C_FEEDBACK_PLAYER_MOVE
    BODY_FORMAT = '!Bfff'  # success (byte), x, y, z (float)

    def __init__(self, success, position, packet_id=0):
        super().__init__(packet_id)
        self.success = success  # 1 = erlaubt, 0 = abgelehnt
        self.position = position  # (x, y, z)

    def _pack_body(self):
        return struct.pack(self.BODY_FORMAT, self.success, *self.position)

    @classmethod
    def _unpack_body(cls, body_data, packet_id):
        success, x, y, z = struct.unpack(cls.BODY_FORMAT, body_data)
        return cls(success, (x, y, z), packet_id=packet_id)

@register_packet
class FeedbackBlockChangePacket(Packet):
    """Server feedback for block change (accept/reject)."""
    PACKET_TYPE = PacketType.S_C_FEEDBACK_BLOCK_CHANGE
    BODY_FORMAT = '!BiiiB'  # success (byte), x, y, z (int), block_type (byte)

    def __init__(self, success, position, block_type, packet_id=0):
        super().__init__(packet_id)
        self.success = success
        self.position = position
        self.block_type = block_type

    def _pack_body(self):
        return struct.pack(self.BODY_FORMAT, self.success, self.position[0], self.position[1], self.position[2], self.block_type)

    @classmethod
    def _unpack_body(cls, body_data, packet_id):
        success, x, y, z, block_type = struct.unpack(cls.BODY_FORMAT, body_data)
        return cls(success, (x, y, z), block_type, packet_id=packet_id)

@register_packet
class FeedbackLoginPacket(Packet):
    """Server feedback for login (accept/reject)."""
    PACKET_TYPE = PacketType.S_C_FEEDBACK_LOGIN

    def __init__(self, success, uuid='', name='', packet_id=0):
        super().__init__(packet_id)
        self.success = success
        self.uuid = uuid
        self.name = name

    def _pack_body(self):
        packed_success = struct.pack('!B', self.success)
        packed_uuid = pack_string(self.uuid)
        packed_name = pack_string(self.name)
        return packed_success + packed_uuid + packed_name

    @classmethod
    def _unpack_body(cls, body_data, packet_id):
        success = struct.unpack('!B', body_data[:1])[0]
        uuid, rest = unpack_string(body_data[1:])
        name, _ = unpack_string(rest)
        return cls(success, uuid, name, packet_id=packet_id)

# --- S -> C (Broadcast) Packets ---

@register_packet
class InfoPlayerMovePacket(Packet):
    """Server broadcast: player moved."""
    PACKET_TYPE = PacketType.S_C_INFO_PLAYER_MOVE

    def __init__(self, uuid, name, position, yaw, pitch, packet_id=0):
        super().__init__(packet_id)
        self.uuid = uuid
        self.name = name
        self.position = position  # (x, y, z)
        self.yaw = yaw
        self.pitch = pitch

    def _pack_body(self):
        packed_uuid = pack_string(self.uuid)
        packed_name = pack_string(self.name)
        packed_pos = struct.pack('fff', *self.position)
        packed_rot = struct.pack('ff', self.yaw, self.pitch)
        return packed_uuid + packed_name + packed_pos + packed_rot

    @classmethod
    def _unpack_body(cls, body_data, packet_id):
        uuid, rest = unpack_string(body_data)
        name, rest = unpack_string(rest)
        x, y, z, yaw, pitch = struct.unpack('fff' + 'ff', rest)
        return cls(uuid=uuid, name=name, position=(x, y, z), yaw=yaw, pitch=pitch, packet_id=packet_id)

@register_packet
class InfoBlockChangePacket(Packet):
    """Server broadcast: block changed."""
    PACKET_TYPE = PacketType.S_C_INFO_BLOCK_CHANGE
    BODY_FORMAT = '!iiiB' # x, y, z (int), block_type (byte)

    def __init__(self, position, block_type, packet_id=0):
        super().__init__(packet_id)
        self.position = position
        self.block_type = block_type

    def _pack_body(self):
        return struct.pack(self.BODY_FORMAT, self.position[0], self.position[1], self.position[2], self.block_type)

    @classmethod
    def _unpack_body(cls, body_data, packet_id):
        x, y, z, block_type = struct.unpack(cls.BODY_FORMAT, body_data)
        return cls(position=(x, y, z), block_type=block_type, packet_id=packet_id)

@register_packet
class InfoPlayerJoinPacket(Packet):
    """Server broadcast: player joined."""
    PACKET_TYPE = PacketType.S_C_INFO_PLAYER_JOIN

    def __init__(self, uuid, name, packet_id=0):
        super().__init__(packet_id)
        self.uuid = uuid
        self.name = name

    def _pack_body(self):
        packed_uuid = pack_string(self.uuid)
        packed_name = pack_string(self.name)
        return packed_uuid + packed_name

    @classmethod
    def _unpack_body(cls, body_data, packet_id):
        uuid, remaining_data = unpack_string(body_data)
        name, _ = unpack_string(remaining_data)
        return cls(uuid=uuid, name=name, packet_id=packet_id)

@register_packet
class InfoPlayerLeavePacket(Packet):
    """Server broadcast: player left."""
    PACKET_TYPE = PacketType.S_C_INFO_PLAYER_LEAVE

    def __init__(self, uuid, name, packet_id=0):
        super().__init__(packet_id)
        self.uuid = uuid
        self.name = name

    def _pack_body(self):
        packed_uuid = pack_string(self.uuid)
        packed_name = pack_string(self.name)
        return packed_uuid + packed_name

    @classmethod
    def _unpack_body(cls, body_data, packet_id):
        uuid, remaining_data = unpack_string(body_data)
        name, _ = unpack_string(remaining_data)
        return cls(uuid=uuid, name=name, packet_id=packet_id)

@register_packet
class InfoChunkDataPacket(Packet):
    """Server broadcast: chunk data."""
    PACKET_TYPE = PacketType.S_C_INFO_CHUNK_DATA
    # Hier ggf. noch die Struktur für Chunkdaten ergänzen
    def __init__(self, chunk_data, packet_id=0):
        super().__init__(packet_id)
        self.chunk_data = chunk_data
    def _pack_body(self):
        # TODO: Implementieren
        return self.chunk_data
    @classmethod
    def _unpack_body(cls, body_data, packet_id):
        # TODO: Implementieren
        return cls(chunk_data=body_data, packet_id=packet_id)

def handle_packet(self, packet):
    if hasattr(packet, 'position') and not hasattr(packet, 'block_type') and not hasattr(packet, 'name'):
        # PlayerMovePacket
        self.player.position = packet.position