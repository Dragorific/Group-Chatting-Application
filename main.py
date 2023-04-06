import socket
import argparse
import json
import struct
import datetime
import keyboard
from random import randint
from threading import Thread
from collections import defaultdict

def time():
    return (datetime.datetime.now()).strftime("%H:%M:%S")

class Server:
    def __init__(self, host='127.0.0.1', port=8080):
        self.chat_rooms = defaultdict(list)
        self.chat_room_multicast_ips = {}
        self.host = host
        self.port = port
        self.start()

    # Add this method to generate a unique multicast IP for each chat room
    def generate_multicast_ip(self) -> str:
        while True:
            new_multicast_ip = f"239.{randint(0, 255)}.{randint(0, 255)}.{randint(0, 255)}"
            if new_multicast_ip not in self.chat_room_multicast_ips.values():
                return new_multicast_ip

    def start(self):
        # Set up server socket 
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        
        print(f'{time()}: Chat Room Directory Server listening for connections on {self.host}:{self.port}')
        
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
                    print(f"{time()}: Client closed the connection.")
                    break

                request = json.loads(data.decode('utf-8'))
                action = request.get('action')
                chat_room = request.get('chat_room')

                if action == 'makeroom':
                    print(f"{time()}: Received 'makeroom' command.")
                    self.create_chat_room(chat_room)
                elif action == 'deleteroom':
                    print(f"{time()}: Received 'deleteroom' command.")
                    self.delete_chat_room(chat_room)
                elif action == 'chat':
                    print(f"{time()}: Received 'chat' command.")
                    self.join_chat_room(chat_room, client_socket)
                elif action == 'getdir':
                    print(f"{time()}: Received 'getdir' command.")
                    self.send_chat_rooms_list(client_socket)
                elif action == 'get_multicast_ip':
                    print(f"{time()}: Received 'get multicast ip' command.")
                    self.send_multicast_ip(chat_room, client_socket)

        except Exception as e:
            print(f'Error handling client {client_address}: {e}')

        finally:
            client_socket.close()

    def send_multicast_ip(self, chat_room: str, client_socket: socket.socket):
        if chat_room in self.chat_room_multicast_ips:
            multicast_ip = self.chat_room_multicast_ips[chat_room]
            response = json.dumps({"multicast_ip": multicast_ip}).encode('utf-8')
            client_socket.sendall(response)
        else:
            response = json.dumps({"multicast_ip": None}).encode('utf-8')
            client_socket.sendall(response)
    
    def create_chat_room(self, chat_room: str):
        if chat_room not in self.chat_rooms:
            self.chat_rooms[chat_room] = []
            multicast_ip = self.generate_multicast_ip()
            self.chat_room_multicast_ips[chat_room] = multicast_ip  # Store the multicast IP for the chat room
            print(f'{time()}: Chat room "{chat_room}" created with multicast IP: {multicast_ip}')
        else:
            print(f'{time()}: Chat room "{chat_room}" already exists.')

    def delete_chat_room(self, chat_room: str):
        if chat_room in self.chat_rooms:
            del self.chat_rooms[chat_room]
            del self.chat_room_multicast_ips[chat_room]
            print(f'{time()}: Chat room "{chat_room}" deleted.')
        else:
            print(f'{time()}: Chat room "{chat_room}" doesnt exist.')

    def join_chat_room(self, chat_room: str, client_socket: socket.socket):
        if chat_room in self.chat_rooms:
            self.chat_rooms[chat_room].append(client_socket)
            multicast_ip = self.chat_room_multicast_ips[chat_room]
            response = json.dumps({"status": "success", "multicast_ip": multicast_ip}).encode("utf-8")
            client_socket.sendall(response)
            print(f'{time()}: Client joined chat room "{chat_room}".')
        else:
            print(f'{time()}: Chat room "{chat_room}" doesnt exist.')

    def send_chat_rooms_list(self, client_socket: socket.socket):
        chat_rooms_list = list(self.chat_rooms.keys())
        response = json.dumps(chat_rooms_list).encode('utf-8')
        client_socket.sendall(response)

class Client:
    def __init__(self, host='127.0.0.1', port=8080, multicast_port=5007):
        self.host = host
        self.port = port
        self.chat_room = None
        self.user_name = "Guest"
        self.server_socket = None
        self.multicast_socket = None
        self.multicast_group = None
        self.multicast_port = multicast_port
        self.handle_user_input()

    def connect_to_server(self) -> socket.socket:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect((self.host, self.port))
        print(f'{time()}: Connected to server at {self.host}:{self.port}')
        return server_socket

    def setup_multicast_socket(self, multicast_ip: str) -> socket.socket:
        multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        multicast_socket.bind(("", self.multicast_port))
        multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                                    struct.pack("4sl", socket.inet_aton(multicast_ip), socket.INADDR_ANY))
        return multicast_socket
    
    def get_multicast_ip(self, chat_room: str) -> str:
        self.send_request_to_server('get_multicast_ip', chat_room)
        response = self.server_socket.recv(1024)
        data = json.loads(response.decode('utf-8'))
        multicast_ip = data.get("multicast_ip")
        return multicast_ip


    def send_request_to_server(self, action: str, chat_room: str = None):
        request = {'action': action, 'chat_room': chat_room}
        self.server_socket.sendall(json.dumps(request).encode('utf-8'))

    def handle_user_input(self):
        while True:
            command = input(f'{time()}: Enter a command (getdir/makeroom/connect/deleteroom/bye): ').strip().lower()
            if command == 'connect':
                self.server_socket = self.connect_to_server()
            elif command == 'name':
                self.user_name = input('Enter your display name: ').strip()
            elif command == 'getdir':
                if self.server_socket:
                    self.send_request_to_server('getdir')
                    data = self.handle_server_response()
                    print(f"{time()}: List of chatrooms: {data}")
                else:
                    print(f"{time()}: Please connect to the server first.")
            elif command == 'makeroom':
                if self.server_socket:
                    chat_room = input(f'{time()}: Enter a chat room name: ').strip()
                    self.send_request_to_server('makeroom', chat_room)
                else:
                    print(f"{time()}: Please connect to the server first.")
            elif command == 'deleteroom':
                if self.server_socket:
                    chat_room = input('Enter a chat room name: ').strip()
                    self.send_request_to_server('deleteroom', chat_room)
                else:
                    print("Please connect to the server first.")
            elif command == 'chat':
                if self.server_socket:
                    chat_room = input('Enter a chat room name: ').strip()
                    self.send_request_to_server('chat', chat_room)
                    response = self.handle_server_response()
                    if response["status"] == "success":
                        self.join_chat_room(chat_room)
                    else:
                        print(f"{time()}: Error joining chat room.")
                else:
                    print(f"{time()}: Please connect to the server first.")
            elif command == 'bye':
                break

    def handle_server_response(self):
        response = self.server_socket.recv(1024)
        data = json.loads(response.decode('utf-8'))
        return data

    def join_chat_room(self, chat_room: str):
        self.chat_room = chat_room
        multicast_ip = self.get_multicast_ip(chat_room)
        self.multicast_group = multicast_ip
        print(f'Joined chat room: {self.chat_room}')

        self.multicast_socket = self.setup_multicast_socket(multicast_ip)

        receive_thread = Thread(target=self.receive_messages)
        receive_thread.start()

        send_thread = Thread(target=self.send_messages)
        send_thread.start()

        receive_thread.join()
        send_thread.join()

    def send_messages(self):
        while self.chat_room:
            try:
                message = input()
                data = f'{self.user_name}: {message}'.encode('utf-8')
                self.multicast_socket.sendto(data, (self.multicast_group, self.multicast_port))
            except EOFError:
                self.leave_chat_room()
                break

    def receive_messages(self):
        while self.chat_room:
            try:
                data, addr = self.multicast_socket.recvfrom(1024)
                print(data.decode('utf-8'))
            except socket.error:
                break

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