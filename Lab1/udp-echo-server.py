#!/usr/bin/env python3
import socket

HOST = '127.0.0.1'  # Loopback interface (localhost)
PORT = 5002         # UDP port to listen on

# Create a UDP socket
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_socket.bind((HOST, PORT))

print(f"UDP server listening on {HOST}:{PORT}")

try:
    while True:
        try:
            data, client_addr = udp_socket.recvfrom(1024)  # Blocking call
        except KeyboardInterrupt:
            print("\nServer shutting down...")
            break  # Exit the main loop
        message = data.decode('utf-8').strip()
        if not message:
            continue
        first_char = message[0]
        rest = message[1:]
        if first_char == 'A':
            response = ''.join(sorted(rest, reverse=True))
        elif first_char == 'C':
            response = ''.join(sorted(rest))
        elif first_char == 'D':
            response = rest.upper()
        else:
            response = message

        # Send response back to the client
        udp_socket.sendto(response.encode(), client_addr)
except Exception as e:
    print(f"Unexpected error: {e}")
finally:
    udp_socket.close()
    print("UDP server socket closed.")