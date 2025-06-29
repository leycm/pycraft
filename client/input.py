import pygame
import numpy as np

class InputHandler:
    def __init__(self, window_width, window_height):
        self.window_width = window_width
        self.window_height = window_height
        
        # Don't auto-grab mouse - wait for click
        pygame.mouse.set_visible(True)
        pygame.event.set_grab(False)
        
        # Movement state
        self.movement = {
            'forward': False,
            'backward': False,
            'left': False,
            'right': False,
            'up': False,
            'down': False
        }
        
        # Mouse state
        self.last_mouse = (window_width // 2, window_height // 2)
        self.mouse_locked = False  # Start unlocked
        self.sneaking = False

    def handle_events(self, camera, inventory, on_break, on_place):
        """Process all input events and update camera and inventory."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.toggle_mouse_lock()
                elif event.key == pygame.K_F5:
                    camera.third_person = not camera.third_person
                elif event.key == pygame.K_LCTRL:
                    self.sneaking = True
                else:
                    self._handle_keydown(event.key, inventory)
            
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_LCTRL:
                    self.sneaking = False
                self._handle_keyup(event.key)
            
            elif event.type == pygame.MOUSEMOTION and self.mouse_locked:
                self._handle_mouse_motion(event, camera)

            elif event.type == pygame.MOUSEWHEEL:
                if event.y > 0: # Scroll up
                    inventory.prev_slot()
                elif event.y < 0: # Scroll down
                    inventory.next_slot()

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if not self.mouse_locked:
                    # Only grab mouse if clicking and not locked
                    self.toggle_mouse_lock()
                elif event.button == 1: # Left click
                    on_break()
                elif event.button == 3: # Right click
                    on_place()

            elif event.type == pygame.ACTIVEEVENT:
                if hasattr(event, 'gain') and event.gain == 1 and not self.mouse_locked:
                    # Don't auto-grab mouse on focus
                    pass

        # Update camera position based on movement state
        self._update_camera_position(camera)
        
        return True

    def _handle_keydown(self, key, inventory):
        """Handle key press events."""
        if key == pygame.K_w:
            self.movement['forward'] = True
        elif key == pygame.K_s:
            self.movement['backward'] = True
        elif key == pygame.K_a:
            self.movement['left'] = True
        elif key == pygame.K_d:
            self.movement['right'] = True
        elif key == pygame.K_SPACE:
            self.movement['up'] = True
        elif key == pygame.K_LSHIFT:
            self.movement['down'] = True
        
        # Hotbar selection
        if pygame.K_1 <= key <= pygame.K_9:
            inventory.set_slot(key - pygame.K_1)

    def _handle_keyup(self, key):
        """Handle key release events."""
        if key == pygame.K_w:
            self.movement['forward'] = False
        elif key == pygame.K_s:
            self.movement['backward'] = False
        elif key == pygame.K_a:
            self.movement['left'] = False
        elif key == pygame.K_d:
            self.movement['right'] = False
        elif key == pygame.K_SPACE:
            self.movement['up'] = False
        elif key == pygame.K_LSHIFT:
            self.movement['down'] = False

    def _handle_mouse_motion(self, event, camera):
        """Handle mouse movement for camera rotation."""
        if self.mouse_locked:
            x, y = event.pos
            dx = x - self.window_width // 2
            dy = y - self.window_height // 2
            
            camera.process_mouse(dx, dy)
            
            # Reset mouse to center
            pygame.mouse.set_pos(self.window_width // 2, self.window_height // 2)

    def _update_camera_position(self, camera):
        """Update camera position based on movement state."""
        speed = 0.1
        
        if self.movement['forward']:
            camera.move('FORWARD', speed)
        if self.movement['backward']:
            camera.move('BACKWARD', speed)
        if self.movement['left']:
            camera.move('LEFT', speed)
        if self.movement['right']:
            camera.move('RIGHT', speed)
        if self.movement['up']:
            camera.move('UP', speed)
        if self.movement['down']:
            camera.move('DOWN', speed)

    def toggle_mouse_lock(self):
        """Toggle mouse lock state."""
        self.mouse_locked = not self.mouse_locked
        pygame.event.set_grab(self.mouse_locked)
        pygame.mouse.set_visible(not self.mouse_locked)
        
        if self.mouse_locked:
            # Center mouse when locking
            pygame.mouse.set_pos(self.window_width // 2, self.window_height // 2) 