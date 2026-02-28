#!/usr/bin/env python3
import socket

HOST = '127.0.0.1' # Server's hostname or IP address
PORT = 5002 # Port that the server listens on

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    try:
        while True:
            clientInput = input("Enter your message or 'exit' to quit: ")
            if clientInput == 'exit':
                break
            s.sendto(clientInput.encode(), (HOST, PORT)) # Send message to UDP server
            data, _ = s.recvfrom(1024) # Receive from server
            print("Server response: ", data.decode('utf-8'))
    except KeyboardInterrupt:
        print("\nYou have pressed Ctrl+C")
    finally:
        print("Connection closed")