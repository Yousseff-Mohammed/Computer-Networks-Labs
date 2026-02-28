#!/usr/bin/env python3
import socket

HOST = '127.0.0.1' # Server's hostname or IP address
PORT = 5001 # Port that the server listens on

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    try:
        while True:
            clientInput = input("Enter your message (or 'exit' to quit): ")
            if clientInput == 'exit':
                break
            s.sendall(clientInput.encode())
            print("Server response: ",s.recv(1024).decode())
    except KeyboardInterrupt:
        print("\nYou have pressed Ctrl+C")
    finally:
        print("Connection closed")