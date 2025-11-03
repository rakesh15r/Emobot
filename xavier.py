# import socket
# import os

# HOST = '0.0.0.0'   # Listen on all interfaces
# PORT = 5001

# def receive_file(conn):
#     filename = conn.recv(1024).decode()
#     if not filename:
#         return False
#     print(f"[SERVER] Receiving file: {filename}")
#     conn.sendall(b'OK')

#     filesize = int(conn.recv(1024).decode())
#     conn.sendall(b'OK')

#     with open(filename, 'wb') as f:
#         bytes_received = 0
#         while bytes_received < filesize:
#             data = conn.recv(4096)
#             if not data:
#                 break
#             f.write(data)
#             bytes_received += len(data)

#     print(f"[SERVER] File {filename} received ({filesize} bytes).")
#     return True

# def receive_text(conn):
#     text = conn.recv(1024).decode()
#     if not text:
#         return False
#     print(f"[SERVER] Received text: {text}")
#     return True

# def main():
#     with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#         s.bind((HOST, PORT))
#         s.listen()
#         print(f"[SERVER] Listening on {HOST}:{PORT}...")

#         conn, addr = s.accept()
#         print(f"[SERVER] Connected by {addr}")

#         while True:
#             try:
#                 mode = conn.recv(1024).decode()
#                 if not mode:
#                     print("[SERVER] Client disconnected.")
#                     break

#                 conn.sendall(b'OK')

#                 if mode == 'FILE':
#                     if not receive_file(conn):
#                         break
#                 elif mode == 'TEXT':
#                     if not receive_text(conn):
#                         break
#                 else:
#                     print("[SERVER] Unknown mode received.")
#             except Exception as e:
#                 print(f"[SERVER] Error: {e}")
#                 break

#         conn.close()
#         print("[SERVER] Connection closed.")

# if __name__ == "__main__":
#     main()

 #!/usr/bin/env python3
"""
xavier_server.py  -- Processor (Jetson Xavier)

Listens for WAV uploads (length-prefixed JSON header + WAV bytes), runs:
  preprocessing -> emotion -> response generation -> command extraction
Sends a JSON response (xavier_out) back to Nano on the same socket.

Replace placeholders:
 - run_stt() -> your ASR (whisper/faster-whisper/whisper.cpp)
 - run_emotion() -> your emotion classifier
 - generate_response() -> your response generator (LLM or templates)
"""

import socket, struct, json, threading, os, time
import numpy as np
import soundfile as sf

# ---------- CONFIG ----------
HOST = "0.0.0.0"
PORT = 6000
WORKDIR = "/tmp/xavier_audio"
os.makedirs(WORKDIR, exist_ok=True)

# Tunables (adjust per environment)
VAD_ENERGY_THRESHOLD = 200
VAD_SPEECH_FRAC = 0.02

# ---------- util helpers ----------

def recv_all(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data

def recv_json(sock):
    raw = recv_all(sock, 4)
    if not raw:
        return None
    (l,) = struct.unpack("!I", raw)
    payload = recv_all(sock, l)
    if not payload:
        return None
    return json.loads(payload.decode('utf-8'))

def send_json(sock, obj):
    data = json.dumps(obj).encode('utf-8')
    sock.sendall(struct.pack("!I", len(data)))
    sock.sendall(data)

# ---------- pipeline placeholders (replace with real models) ----------

def preprocessing(wav_path, header):
    """
    - compute simple VAD (energy-based)
    - optionally run a quick STT (can be replaced by full ASR)
    Return dict: session, wav_path, vad_activity, stt_text, stt_conf, audio_notes
    """
    session = header.get("session", f"session_{int(time.time())}")
    samplerate = header.get("samplerate", 16000)

    # Load audio (soundfile handles WAV headers)
    data, sr = sf.read(wav_path, dtype='int16')
    arr = np.array(data).astype(np.int16)

    # compute energies across 20ms frames
    frame_len = int(0.02 * sr)
    energies = []
    for i in range(0, len(arr), frame_len):
        frame = arr[i:i+frame_len]
        if frame.size == 0: break
        energies.append(np.mean(np.abs(frame)))
    energies = np.array(energies) if energies else np.array([0.0])
    speech_frames = (energies > VAD_ENERGY_THRESHOLD).sum()
    vad_frac = float(speech_frames) / max(1, len(energies))
    vad_activity = vad_frac > VAD_SPEECH_FRAC

    audio_notes = {
        "avg_energy": float(np.mean(energies)),
        "speech_frac": float(vad_frac),
        "frames": int(len(energies))
    }

    # QUICK STT placeholder (replace with actual model)
    stt_text, stt_conf = run_stt(wav_path)

    return {
        "session": session,
        "wav_path": wav_path,
        "samplerate": sr,
        "vad_activity": bool(vad_activity),
        "stt_text": stt_text,
        "stt_conf": float(stt_conf),
        "audio_notes": audio_notes
    }

def run_stt(wav_path):
    """
    Placeholder STT: replace with your model (Whisper, faster-whisper, etc.)
    Should return (transcript_str, confidence_float)
    """
    # Naive heuristic: if file energy large -> return "yes" (simulate short reply)
    data, sr = sf.read(wav_path, dtype='int16')
    mean_energy = float(np.mean(np.abs(np.array(data).astype(np.float32))))
    if mean_energy > 300:
        return "yes", 0.85
    return "", 0.0

def run_emotion(preproc):
    """
    Placeholder emotion classifier. Replace with your audio/text-based emotion model.
    Return dict: { 'emotion': 'sad'|'neutral'|'happy', 'emotion_conf': float }
    """
    txt = (preproc.get("stt_text") or "").lower()
    if "not in the mood" in txt or "i'm not" in txt or "i am not" in txt or "don't want" in txt or "dont want" in txt:
        return {"emotion":"sad", "emotion_conf":0.9}
    return {"emotion":"neutral", "emotion_conf":0.5}

def generate_response(preproc, emotion):
    """
    Generate response_text and a list of canonical commands.
    Return dict: { 'response_text':..., 'response_conf':..., 'actions': [ {...} ] }
    Replace with your LLM or template-based generator + command extractor.
    """
    stt = (preproc.get("stt_text","") or "").lower().strip()
    session = preproc.get("session", f"session_{int(time.time())}")

    # If user said yes or indicates not in mood -> leave command
    if stt in ("yes","yeah","yup") or "not in the mood" in stt or not preproc.get("vad_activity", True):
        resp = "Okay, I understand. I will leave you alone. Take care."
        action = {
            "cmd_id": f"leave_{session}_{int(time.time())}",
            "type": "leave_area",
            "params": {"speed": 0.3, "distance_m": 2.0, "direction": "backward"},
            "confidence": 0.95
        }
        return {"response_text": resp, "response_conf": 0.95, "actions": [action]}

    # Else produce a conversational reply (template based)
    emo = emotion.get("emotion","neutral")
    if emo == "sad":
        resp = "I hear you. If you'd like I can come back later. For now I'll hang back."
    elif emo == "happy":
        resp = "Great, I'm glad to hear that! Do you need anything from me?"
    else:
        resp = "Nice to chat. How can I help you today?"

    return {"response_text": resp, "response_conf": 0.7, "actions": []}

# ---------- connection handler ----------

def handle_conn(conn, addr):
    print("[Xavier] New connection from", addr)
    try:
        header = recv_json(conn)
        if not header:
            print("[Xavier] No header received; closing.")
            conn.close()
            return

        if header.get("type") != "audio_upload":
            # Unsupported message type
            send_json(conn, {"type":"error", "message":"unsupported_type", "session": header.get("session")})
            conn.close()
            return

        expected = int(header.get("bytes", 0))
        wav_bytes = recv_all(conn, expected)
        if wav_bytes is None:
            print("[Xavier] Failed to read full WAV bytes.")
            conn.close()
            return

        session = header.get("session", f"session_{int(time.time())}")
        wav_path = os.path.join(WORKDIR, f"{session}.wav")
        with open(wav_path, "wb") as f:
            f.write(wav_bytes)
        print(f"[Xavier] Saved WAV -> {wav_path} ({expected} bytes)")

        # Pipeline: preprocessing -> emotion -> response gen
        preproc = preprocessing(wav_path, header)
        print("[Xavier] Preproc:", preproc)
        emotion = run_emotion(preproc)
        print("[Xavier] Emotion:", emotion)
        response = generate_response(preproc, emotion)
        print("[Xavier] Response:", response)

        # Build xavier_out JSON to send back to Nano
        xavier_out = {
            "type": "xavier_out",
            "session": session,
            "response_text": response.get("response_text",""),
            "response_conf": response.get("response_conf", 0.0),
            "commands": response.get("actions", []),
            "meta": {
                "emotion": emotion.get("emotion"),
                "emotion_conf": emotion.get("emotion_conf"),
                "stt_text": preproc.get("stt_text"),
                "stt_conf": preproc.get("stt_conf"),
                "vad_activity": preproc.get("vad_activity"),
                "timestamp": time.time()
            }
        }

        # Send result back to Nano (same socket)
        send_json(conn, xavier_out)
        print("[Xavier] Sent xavier_out back to Nano.")

    except Exception as e:
        print("[Xavier] Exception:", e)
    finally:
        try:
            conn.close()
        except:
            pass
        # optional cleanup: os.remove(wav_path)

# ---------- server loop ----------

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen(5)
    print(f"[Xavier] Listening on {HOST}:{PORT}")
    while True:
        conn, addr = s.accept()
        t = threading.Thread(target=handle_conn, args=(conn, addr), daemon=True)
        t.start()

if __name__ == "__main__":
    main()
