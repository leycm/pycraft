class Player:
    def __init__(self, uuid, name, client_socket, client_address):
        self.uuid = uuid
        self.name = name
        self.client_socket = client_socket
        self.client_address = client_address
        self.position = (0.0, 65.0, 0.0)
        self.yaw = 0.0
        self.pitch = 0.0

    def __repr__(self):
        return f"Player(uuid='{self.uuid}', name='{self.name}', address='{self.client_address}')" 

    def get_camera_position(self):
        position = self.position
        return (position[0], position[1] + 1.8, position[2])
    
    def get_position(self):
        return self.position
    