from PIL import Image, ImageDraw
import os

from shared.constants import BlockType

def generate_block_textures():
    """Creates a simple texture atlas for block types."""
    # Define colors for our simple blocks
    colors = {
        BlockType.STONE: (128, 128, 128),  # Grey
        BlockType.GRASS: (34, 139, 34),   # Forest Green
        BlockType.DIRT:  (139, 69, 19),    # Saddle Brown
    }
    
    # Create an atlas image. We'll make it 3x1 pixels.
    # We will map BlockType enum value to a position in the atlas.
    # STONE (3) -> (0,0), GRASS (1) -> (1,0), DIRT (2) -> (2,0)
    # We need to find the max block type value to determine atlas width
    max_id = max(colors.keys())
    atlas_width = int(max_id) + 1
    atlas_height = 1
    
    atlas = Image.new('RGB', (atlas_width, atlas_height))
    
    # Place colors in the atlas
    # Note: AIR (0) is not textured
    atlas.putpixel((BlockType.STONE - 1, 0), colors[BlockType.STONE])
    atlas.putpixel((BlockType.GRASS - 1, 0), colors[BlockType.GRASS])
    atlas.putpixel((BlockType.DIRT - 1, 0), colors[BlockType.DIRT])

    # Save the final atlas
    atlas.save('assets/terrain.png')
    print("Successfully created block texture atlas 'assets/terrain.png'.")


def generate_ui_assets():
    """Creates the hotbar and selection PNG files in the assets directory."""
    try:
        # Create assets directory if it doesn't exist
        os.makedirs('assets', exist_ok=True)

        # Create the hotbar background image
        # A semi-transparent dark grey bar, 9 slots * 40px + 4px padding
        hotbar_width = 364
        hotbar_height = 44
        hotbar = Image.new('RGBA', (hotbar_width, hotbar_height), (50, 50, 50, 180))
        hotbar.save('assets/hotbar.png')

        # Create the selection highlight image
        # A transparent square with a white border
        selection_size = 48
        selection = Image.new('RGBA', (selection_size, selection_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(selection)
        # Draw a 2px thick rectangle, so it's 4px total (inner+outer)
        draw.rectangle([(0, 0), (selection_size - 1, selection_size - 1)], outline='white', width=4)
        selection.save('assets/hotbar_selection.png')
        
        print("Successfully created UI assets in 'assets/' directory.")

    except Exception as e:
        print(f"An error occurred while generating assets: {e}")

def generate_player_texture():
    """Erzeugt eine 3x2-Textur für das Player-Modell im gewünschten Layout."""
    from PIL import Image
    block_size = 16
    width = 3 * block_size
    height = 2 * block_size
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    # Farben
    colors = {
        'front_top': (255, 255, 255, 255),    # weiß
        'front_bottom': (255, 0, 0, 255),     # rot
        'side_top': (0, 255, 0, 255),         # grün
        'side_bottom': (255, 255, 0, 255),    # gelb
        'top': (0, 0, 255, 255),              # blau
        'bottom': (0, 0, 0, 255),             # schwarz
    }
    # Zeile 0 (oben)
    img.paste(colors['front_top'], (0 * block_size, 0, 1 * block_size, block_size))
    img.paste(colors['side_top'], (1 * block_size, 0, 2 * block_size, block_size))
    img.paste(colors['top'], (2 * block_size, 0, 3 * block_size, block_size))
    # Zeile 1 (unten)
    img.paste(colors['front_bottom'], (0 * block_size, block_size, 1 * block_size, 2 * block_size))
    img.paste(colors['side_bottom'], (1 * block_size, block_size, 2 * block_size, 2 * block_size))
    img.paste(colors['bottom'], (2 * block_size, block_size, 3 * block_size, 2 * block_size))
    img.save('assets/player.png')
    print("Successfully created player texture 'assets/player.png'.")

if __name__ == "__main__":
    if not os.path.exists('assets'):
        generate_ui_assets()
        generate_block_textures()
        generate_player_texture()
        print("Assets-Ordner wurde erstellt und Texturen generiert.")
    else:
        print("Assets-Ordner existiert bereits, keine Texturen generiert.") 