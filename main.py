import socket
import argparse
import json
import struct
import datetime
from threading import Thread
from collections import defaultdict

def time():
    return (datetime.datetime.now()).strftime("%H:%M:%S")

class Server:
    def __init__(self, host='127.0.0.1', port=8080):
        self.chat_rooms = defaultdict(list)
        self.host = host
        self.port = port
        self.start()

    def start(self):
        # Set up server socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        
        print(f'{time()}: Server listening for connections on {self.host}:{self.port}')
        
        server_socket.listen(5)

        print(f'{time()}: Server started on {self.host}:{self.port}')

        while True:
            # Listen for and handle client requests
            client_socket, client_address = server_socket.accept()
            print(f'{time()}: Connection from {client_address}')
            thread = Thread(target=self.handle_client, args=(client_socket, client_address))
            thread.start()

    def handle_client(self, client_socket, client_address):
        try:
            while True:
                data = client_socket.recv(1024)
                if not data:
                    break

                request = json.loads(data.decode('utf-8'))
                action = request.get('action')
                chat_room = request.get('chat_room')

                if action == 'create':
                    self.create_chat_room(chat_room)
                elif action == 'delete':
                    self.delete_chat_room(chat_room)
                elif action == 'join':
                    self.join_chat_room(chat_room, client_socket)
                elif action == 'list':
                    self.send_chat_rooms_list(client_socket)

        except Exception as e:
            print(f'Error handling client {client_address}: {e}')

        finally:
            client_socket.close()

    def create_chat_room(self, chat_room: str):
        if chat_room not in self.chat_rooms:
            self.chat_rooms[chat_room] = []
            print(f'{time()}: Chat room "{chat_room}" created.')

    def delete_chat_room(self, chat_room: str):
        if chat_room in self.chat_rooms:
            del self.chat_rooms[chat_room]
            print(f'{time()}: Chat room "{chat_room}" deleted.')

    def join_chat_room(self, chat_room: str, client_socket: socket.socket):
        if chat_room in self.chat_rooms:
            self.chat_rooms[chat_room].append(client_socket)
            print(f'{time()}: Client joined chat room "{chat_room}".')

    def send_chat_rooms_list(self, client_socket: socket.socket):
        chat_rooms_list = list(self.chat_rooms.keys())
        response = json.dumps(chat_rooms_list).encode('utf-8')
        client_socket.sendall(response)

class Client:
    def __init__(self, host='127.0.0.1', port=8080, multicast_group='224.0.0.1', multicast_port=5007):
        self.host = host
        self.port = port
        self.multicast_group = multicast_group
        self.multicast_port = multicast_port
        self.chat_room = None
        self.start()

    def start(self):
        self.server_socket = self.connect_to_server()
        self.multicast_socket = self.setup_multicast_socket()
        self.handle_user_input()

    def connect_to_server(self) -> socket.socket:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect((self.host, self.port))
        print(f'{time()}: Connected to server at {self.host}:{self.port}')
        return server_socket

    def setup_multicast_socket(self) -> socket.socket:
        multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return multicast_socket

    def send_request_to_server(self, action: str, chat_room: str = None):
        request = {'action': action, 'chat_room': chat_room}
        self.server_socket.sendall(json.dumps(request).encode('utf-8'))

    def handle_user_input(self):
        while True:
            command = input(f'{time()}: Enter a command (list/create/join/delete/quit): ').strip().lower()
            if command == 'list':
                self.send_request_to_server('list')
                self.handle_server_response()
            elif command == 'create':
                chat_room = input('Enter a chat room name: ').strip()
                self.send_request_to_server('create', chat_room)
            elif command == 'delete':
                chat_room = input('Enter a chat room name: ').strip()
                self.send_request_to_server('delete', chat_room)
            elif command == 'join':
                chat_room = input('Enter a chat room name: ').strip()
                self.send_request_to_server('join', chat_room)
                self.join_chat_room(chat_room)
            elif command == 'quit':
                break

    def handle_server_response(self):
        response = self.server_socket.recv(1024)
        data = json.loads(response.decode('utf-8'))
        print(f'Chat rooms: {", ".join(data)}')

    def join_chat_room(self, chat_room: str):
        self.chat_room = chat_room
        print(f'Joined chat room: {self.chat_room}')
        self.multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                                         struct.pack("4sl", socket.inet_aton(self.multicast_group), socket.INADDR_ANY))
        self.multicast_socket.bind(("", self.multicast_port))

        receive_thread = Thread(target=self.receive_messages)
        receive_thread.start()

        send_thread = Thread(target=self.send_messages)
        send_thread.start()

        receive_thread.join()
        send_thread.join()

    def send_messages(self):
        while self.chat_room:
            message = input()
            data = f'{self.chat_room}: {message}'.encode('utf-8')
            self.multicast_socket.sendto(data, (self.multicast_group, self.multicast_port))
    
    def receive_messages(self):
        while self.chat_room:
            try:
                data, addr = self.multicast_socket.recvfrom(1024)
                print(data.decode('utf-8'))
            except socket.error:
                pass

    def leave_chat_room(self):
        if self.chat_room:
            self.multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP,
                                            struct.pack("4sl", socket.inet_aton(self.multicast_group), socket.INADDR_ANY))
            self.chat_room = None


if __name__ == '__main__':
    
    roles = {'client': Client,'server': Server}
    parser = argparse.ArgumentParser()

    parser.add_argument('-r', '--role',
                        choices=roles, 
                        help='server or client role',
                        required=True, type=str)

    args = parser.parse_args()
    roles[args.role]()