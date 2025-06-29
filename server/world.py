import numpy as np
from shared.constants import CHUNK_WIDTH, CHUNK_HEIGHT, CHUNK_DEPTH, BlockType

class Chunk:
    """Manages the blocks within a 16x16x256 area."""
    def __init__(self, position):
        self.position = position

        self.blocks = np.zeros((CHUNK_WIDTH, CHUNK_HEIGHT, CHUNK_DEPTH), dtype=np.uint8)

    def set_block(self, x, y, z, block_type):
        """Sets a block's type at a local chunk coordinate."""
        if 0 <= x < CHUNK_WIDTH and 0 <= y < CHUNK_HEIGHT and 0 <= z < CHUNK_DEPTH:
            self.blocks[x, y, z] = block_type
        else:
            print(f"Warning: Block coordinates ({x},{y},{z}) are out of chunk bounds.")

    def get_block(self, x, y, z):
        """Gets a block's type at a local chunk coordinate."""
        if 0 <= x < CHUNK_WIDTH and 0 <= y < CHUNK_HEIGHT and 0 <= z < CHUNK_DEPTH:
            return self.blocks[x, y, z]
        return BlockType.AIR

class World:
    """Manages all chunks and the world generation."""
    def __init__(self):
        self.chunks = {}

    def get_chunk(self, chunk_x, chunk_z):
        """Gets a chunk, generating it if it doesn't exist."""
        if (chunk_x, chunk_z) not in self.chunks:
            self.chunks[(chunk_x, chunk_z)] = self._generate_chunk(chunk_x, chunk_z)
        return self.chunks[(chunk_x, chunk_z)]

    def _generate_chunk(self, chunk_x, chunk_z):
        """Generates a simple flat-world chunk."""
        chunk = Chunk(position=(chunk_x, chunk_z))
        
        surface_y = 64
        
        for x in range(CHUNK_WIDTH):
            for z in range(CHUNK_DEPTH):
                for y in range(surface_y - 3):
                    chunk.set_block(x, y, z, BlockType.STONE)
                for y in range(surface_y - 3, surface_y):
                    chunk.set_block(x, y, z, BlockType.DIRT)
                chunk.set_block(x, surface_y, z, BlockType.GRASS)
        
        print(f"Generated chunk at ({chunk_x}, {chunk_z})")
        return chunk

    def set_block(self, world_x, world_y, world_z, block_type):
        """Sets a block at a global world coordinate."""
        chunk_x = world_x // CHUNK_WIDTH
        chunk_z = world_z // CHUNK_DEPTH
        
        local_x = world_x % CHUNK_WIDTH
        local_z = world_z % CHUNK_DEPTH

        chunk = self.get_chunk(chunk_x, chunk_z)
        chunk.set_block(local_x, world_y, local_z, block_type)

    def get_block(self, world_x, world_y, world_z):
        """Gets a block at a global world coordinate."""
        chunk_x = world_x // CHUNK_WIDTH
        chunk_z = world_z // CHUNK_DEPTH

        local_x = world_x % CHUNK_WIDTH
        local_z = world_z % CHUNK_DEPTH
        
        chunk = self.get_chunk(chunk_x, chunk_z)
        return chunk.get_block(local_x, world_y, local_z) 