from shared.constants import BlockType

class Inventory:
    def __init__(self, size=9):
        self.size = size
        self.hotbar = [BlockType.AIR] * size
        self.selected_slot = 0
        self._populate_defaults()

    def _populate_defaults(self):
        """Fills the hotbar with some default blocks for testing."""
        self.hotbar[0] = BlockType.STONE
        self.hotbar[1] = BlockType.DIRT
        self.hotbar[2] = BlockType.GRASS
        # Other slots remain AIR

    def next_slot(self):
        """Selects the next slot, wrapping around."""
        self.selected_slot = (self.selected_slot + 1) % self.size

    def prev_slot(self):
        """Selects the previous slot, wrapping around."""
        self.selected_slot = (self.selected_slot - 1 + self.size) % self.size
    
    def set_slot(self, slot_index):
        """Selects a specific slot by its index."""
        if 0 <= slot_index < self.size:
            self.selected_slot = slot_index

    def get_selected_item(self):
        """Returns the BlockType in the currently selected slot."""
        return self.hotbar[self.selected_slot] 