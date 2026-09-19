import socket
import os

HOST = '0.0.0.0'   # Listen on all interfaces
PORT = 5001

def receive_file(conn):
    # Receive filename
    filename = conn.recv(1024).decode()
    if not filename:
        return
    print(f"[SERVER] Receiving file: {filename}")

    # Acknowledge filename
    conn.sendall(b'OK')

    # Receive file size
    filesize = int(conn.recv(1024).decode())
    conn.sendall(b'OK')

    # Receive file data
    with open(filename, 'wb') as f:
        bytes_received = 0
        while bytes_received < filesize:
            data = conn.recv(4096)
            if not data:
                break
            f.write(data)
            bytes_received += len(data)

    print(f"[SERVER] File {filename} received ({filesize} bytes).")

def receive_text(conn):
    text = conn.recv(1024).decode()
    print(f"[SERVER] Received text: {text}")

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"[SERVER] Listening on {HOST}:{PORT}...")

        while True:
            conn, addr = s.accept()
            with conn:
                print(f"[SERVER] Connected by {addr}")

                mode = conn.recv(1024).decode()  # 'TEXT' or 'FILE'
                conn.sendall(b'OK')

                if mode == 'FILE':
                    receive_file(conn)
                elif mode == 'TEXT':
                    receive_text(conn)

if __name__ == '__main__':
    main()
