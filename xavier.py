import socket
import os

HOST = '0.0.0.0'   # Listen on all interfaces
PORT = 5001

def receive_file(conn):
    filename = conn.recv(1024).decode()
    if not filename:
        return False
    print(f"[SERVER] Receiving file: {filename}")
    conn.sendall(b'OK')

    filesize = int(conn.recv(1024).decode())
    conn.sendall(b'OK')

    with open(filename, 'wb') as f:
        bytes_received = 0
        while bytes_received < filesize:
            data = conn.recv(4096)
            if not data:
                break
            f.write(data)
            bytes_received += len(data)

    print(f"[SERVER] File {filename} received ({filesize} bytes).")
    return True

def receive_text(conn):
    text = conn.recv(1024).decode()
    if not text:
        return False
    print(f"[SERVER] Received text: {text}")
    return True

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"[SERVER] Listening on {HOST}:{PORT}...")

        conn, addr = s.accept()
        print(f"[SERVER] Connected by {addr}")

        while True:
            try:
                mode = conn.recv(1024).decode()
                if not mode:
                    print("[SERVER] Client disconnected.")
                    break

                conn.sendall(b'OK')

                if mode == 'FILE':
                    if not receive_file(conn):
                        break
                elif mode == 'TEXT':
                    if not receive_text(conn):
                        break
                else:
                    print("[SERVER] Unknown mode received.")
            except Exception as e:
                print(f"[SERVER] Error: {e}")
                break

        conn.close()
        print("[SERVER] Connection closed.")

if __name__ == "__main__":
    main()
