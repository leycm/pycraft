from enum import IntEnum

CHUNK_WIDTH = 16
CHUNK_HEIGHT = 256
CHUNK_DEPTH = 16
CHUNK_SIZE = (CHUNK_WIDTH, CHUNK_HEIGHT, CHUNK_DEPTH)

class BlockType(IntEnum):
    AIR = 0
    GRASS = 1
    DIRT = 2
    STONE = 3

class Block:
    def __init__(self, block_type):
        self.type = block_type
        # Add other properties like light level, etc. later 