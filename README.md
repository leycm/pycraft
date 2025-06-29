# PyCraft

A simple Minecraft-like multiplayer game built with Python, Pygame, and OpenGL.

## Features

- Multiplayer support with client-server architecture
- 3D world rendering with OpenGL
- Block placement and destruction
- Player movement and rotation
- Real-time player synchronization
- Custom player skins support
- Hotbar inventory system

## Quick Start

### Using run.bat (Recommended)

The easiest way to start the game is using the provided `run.bat` file:

```bash
run.bat
```

This will:
1. Install dependencies
2. Start the server
3. Start two clients with predefined names:
   - Client 1: Steve
   - Client 2: Alex

### Manual Start

#### Start Server
```bash
python -m server.server
```

#### Start Client
```bash
# With default name "Player"
python -m client.client

# With custom name
python -m client.client Steve

# With custom name and host
python -m client.client Steve localhost
```

### Using run_client.bat

You can also use `run_client.bat` to start a single client:

```bash
# Default name "Player"
run_client.bat

# Custom name
run_client.bat Steve

# Custom name and host
run_client.bat Steve localhost
```

## Controls

- **WASD**: Move
- **Mouse**: Look around
- **Left Click**: Break blocks
- **Right Click**: Place blocks
- **Mouse Wheel**: Change selected block
- **1-9**: Select hotbar slot
- **F5**: Toggle third-person view
- **Escape**: Toggle mouse lock
- **Ctrl**: Sneak

## Configuration

### Player Names and Host

You can specify player names and server host via command line arguments:

```bash
python -m client.client [player_name] [host]
```

Examples:
- `python -m client.client Steve` - Connect as "Steve" to localhost
- `python -m client.client Alex 192.168.1.100` - Connect as "Alex" to server at 192.168.1.100

### Default Values

- **Player Name**: "Player" (fallback if not specified)
- **Server Host**: "localhost" (fallback if not specified)
- **Server Port**: 9999 (fixed)

## File Structure

```
pycraft/
├── assets/              # Game assets (textures, etc.)
├── client/              # Client-side code
│   ├── client.py        # Main client
│   ├── input.py         # Input handling
│   ├── inventory.py     # Inventory system
│   └── render.py        # OpenGL rendering
├── server/              # Server-side code
│   ├── server.py        # Main server
│   ├── player.py        # Player management
│   └── world.py         # World generation
├── shared/              # Shared code
│   ├── constants.py     # Game constants
│   └── packets.py       # Network packets
├── run.bat              # Start server + 2 clients
├── run_client.bat       # Start single client
└── generate_assets.py   # Asset generation
```

## Dependencies

Install required packages:

```bash
pip install -r requirements.txt
```

## Development

### Generating Assets

Assets are automatically generated when running the game, but you can also generate them manually:

```bash
python generate_assets.py
```

### Custom Player Skins

Place a custom skin file at `assets/player_custom.png` to use it instead of the default player texture.

## Network Protocol

The game uses a custom binary protocol for client-server communication. See `shared/packets.py` for packet definitions.

## License

This project is open source. See LICENSE file for details. 