#!/usr/bin/env python3
"""
rover_record_and_send_mqtt.py

- Records a CHUNK (default 3s) from I2S mic
- Encodes the chunk as WAV (PCM16) in-memory
- Base64-encodes the WAV bytes and publishes JSON to MQTT topic "emobot/rover/audio"
- Subscribes to "emobot/rover/command" to receive responses (TTS + command)

Edit DEVICE, BROKER if needed.
"""

import io
import os
import json
import time
import base64
import threading
import uuid
from pathlib import Path

# audio libs
import sounddevice as sd
import soundfile as sf
import numpy as np

# mqtt
import paho.mqtt.client as mqtt

# ====== Configuration ======
SAMPLE_RATE = 16000        # Matches model expectation
CHANNELS = 1               # Mono
DEVICE = 'hw:1,0'          # I2S microphone device (change if different)
DTYPE = 'int32'            # Your mic returns S32_LE; we normalize to float then save as PCM16
CHUNK_DURATION = 3         # seconds per chunk to record & send (you used 3)
# MQTT broker details (from mentor)
BROKER = "13.232.191.178"
PORT = 1883
AUDIO_TOPIC = "emobot/rover/audio"
CMD_TOPIC = "emobot/rover/command"
CLIENT_ID = f"rover-{uuid.uuid4().hex[:8]}"

# Motor/TTS stubs (replace set_velocity with real API)
def set_velocity(left: float, right: float, duration: float = None):
    left = max(-1.0, min(1.0, float(left)))
    right = max(-1.0, min(1.0, float(right)))
    print(f"[MOTOR-STUB] L={left:.2f} R={right:.2f} dur={duration}")
    if duration and duration > 0:
        time.sleep(duration)
        print("[MOTOR-STUB] stopped")

def speak(text: str):
    if not text:
        return
    threading.Thread(target=lambda t: os.system(f'espeak "{t}" >/dev/null 2>&1'), args=(text,), daemon=True).start()

# ====== MQTT client setup ======
client = mqtt.Client(client_id=CLIENT_ID)
# Optional: set username/password if broker needs it
# client.username_pw_set("user", "pass")

def on_connect(c, userdata, flags, rc):
    print(f"[MQTT] Connected to broker {BROKER}:{PORT} (rc={rc})")
    # subscribe to command topic so laptop can send responses
    c.subscribe(CMD_TOPIC)
    print(f"[MQTT] Subscribed to {CMD_TOPIC}")

def on_message(c, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8')
        print(f"\n[MQTT] Message on {msg.topic}: {payload}")
        data = json.loads(payload)
        # speak response_text if present
        text = data.get("response_text") or data.get("text")
        if text:
            print("[TTS] ", text)
            speak(text)
        # execute movement command if any (in background)
        cmd = data.get("command")
        if cmd:
            threading.Thread(target=execute_command_from_msg, args=(cmd,), daemon=True).start()
    except Exception as e:
        print("[MQTT] on_message error:", e)

def execute_command_from_msg(cmd):
    """Interprets the command dict and calls set_velocity (replace if you have different API)"""
    try:
        if not isinstance(cmd, dict):
            print("[CMD] invalid command format")
            return
        action = cmd.get("action", "move")
        if action == "stop":
            set_velocity(0.0, 0.0)
            return
        direction = str(cmd.get("direction", "forward")).lower()
        speed = float(cmd.get("speed", 0.5))
        duration = float(cmd.get("duration", 0.0))
        speed = max(0.0, min(1.0, speed))
        if direction == "forward":
            l, r = speed, speed
        elif direction == "backward":
            l, r = -speed, -speed
        elif direction == "left":
            l, r = -speed * 0.6, speed * 0.6
        elif direction == "right":
            l, r = speed * 0.6, -speed * 0.6
        else:
            # allow explicit speeds
            l = cmd.get("left_speed", 0.0)
            r = cmd.get("right_speed", 0.0)
            l, r = float(l), float(r)
        print(f"[CMD] Executing: dir={direction} speed={speed} dur={duration}")
        set_velocity(l, r, duration if duration > 0 else None)
    except Exception as e:
        print("[CMD] execution error:", e)

client.on_connect = on_connect
client.on_message = on_message

# connect now (non-blocking loop_start)
def start_mqtt():
    try:
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_start()
    except Exception as e:
        print("[MQTT] connection error:", e)
        raise

# ====== Recording + publish logic ======
def record_chunk_seconds(duration=CHUNK_DURATION):
    """Record a numpy array chunk from your I2S mic and return float32 normalized audio."""
    print(f"🎙 Recording {duration}s...")
    data = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS,
                  dtype=DTYPE, device=DEVICE)
    sd.wait()
    # convert int32 -> float32 in -1..1
    if data.dtype == np.int32:
        audio_float = data.astype(np.float32) / np.iinfo(np.int32).max
    elif data.dtype == np.int16:
        audio_float = data.astype(np.float32) / np.iinfo(np.int16).max
    else:
        audio_float = data.astype(np.float32)
    # ensure shape = (N, ) or (N,1)
    if audio_float.ndim > 1 and audio_float.shape[1] == 1:
        audio_float = audio_float[:, 0]
    return audio_float

def wav_bytes_from_float_audio(audio_float, samplerate=SAMPLE_RATE):
    """Write audio_float (float32 -1..1) into an in-memory WAV (PCM16) and return bytes."""
    bio = io.BytesIO()
    # soundfile expects shape (frames, channels). For mono convert to (n,1)
    arr = audio_float
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    sf.write(bio, arr, samplerate, format='WAV', subtype='PCM_16')
    bio.seek(0)
    return bio.read()

def publish_audio_chunk():
    """Record one chunk, build JSON with base64-encoded WAV, and publish to AUDIO_TOPIC."""
    try:
        audio_float = record_chunk_seconds(CHUNK_DURATION)
    except Exception as e:
        print("[REC] record failed:", e)
        return False
    try:
        wav_bytes = wav_bytes_from_float_audio(audio_float, SAMPLE_RATE)
    except Exception as e:
        print("[REC] failed to convert to WAV:", e)
        return False

    b64 = base64.b64encode(wav_bytes).decode('ascii')
    req_id = str(uuid.uuid4())
    payload = {
        "req_id": req_id,
        "wav_b64": b64,
        "meta": {"rate": SAMPLE_RATE, "channels": CHANNELS, "seconds": CHUNK_DURATION}
    }
    try:
        client.publish(AUDIO_TOPIC, json.dumps(payload), qos=1)
        print(f"[MQTT] Published audio req_id={req_id} to {AUDIO_TOPIC} (size={len(b64)} bytes base64)")
        return True
    except Exception as e:
        print("[MQTT] publish error:", e)
        return False

# ====== MAIN ======
def main_loop():
    print("ROVER RECORD->MQTT starting. Press Ctrl+C to quit.")
    start_mqtt()
    try:
        while True:
            input("Press ENTER to record a chunk and send via MQTT...")
            ok = publish_audio_chunk()
            if not ok:
                print("[MAIN] publish failed, retrying after 1s")
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n[MAIN] Exiting by user")
    finally:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass

if __name__ == "__main__":
    # quick checks
    try:
        sd.check_input_settings(device=DEVICE, samplerate=SAMPLE_RATE, channels=CHANNELS)
    except Exception as e:
        print("[INIT] sounddevice check failed:", e)
        print("Make sure DEVICE string is correct for your I2S mic. Use `arecord -l` to list devices.")
    main_loop()
