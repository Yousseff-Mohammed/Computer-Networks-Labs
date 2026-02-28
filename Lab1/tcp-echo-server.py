#!/usr/bin/env python3
import socket, threading

HOST = '127.0.0.1' # Loopback interface (localhost)
PORT = 5001 # Port to listen on

class Client(threading.Thread):
    def __init__(self, client_conn, client_addr):
        threading.Thread.__init__(self)
        self.client_conn = client_conn
        self.client_addr = client_addr
    def run(self):
        print(f"connected to {self.client_addr}")
        try:
            while True:
                data = self.client_conn.recv(1024)
                if not data:
                    break # Client disconnected
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
                self.client_conn.sendall(response.encode())
        except Exception as e:
            print(f"Error with {self.client_addr}: {e}")
        finally:
            self.client_conn.close()
            print(f"Connection closed: {self.client_addr}")

# Create a TCP socket
tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Socket object
# Allow the server to reuse the same address and port immediately after it closes.
# Normally, after a TCP socket closes, the OS keeps the port in TIME_WAIT state
tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
tcp_socket.bind((HOST, PORT))
tcp_socket.listen(10)
threads = []

print(f"TCP server listening on {HOST}:{PORT}")

try:
    while True:
        conn, addr = tcp_socket.accept()
        newthread = Client(conn, addr)
        newthread.start()
        threads.append(newthread)
except KeyboardInterrupt:
        print("\nServer shutting down...")
finally:
        tcp_socket.close()
        for t in threads:
            t.join()
        print("Server has closed all connections and exited.")