#!/usr/bin/env python3
"""
nano_client.py  -- Rover (Jetson Nano) main process

Flow:
1. Play initial greeting (TTS).
2. Record WAV for RECORD_SECONDS (5s).
3. Send WAV to Xavier and wait for result (short timeout).
   - If Xavier returns a result: use it (speak + execute commands).
4. If no speech detected on first recording (or Xavier didn't respond):
   - Play follow-up prompt: "Are you not in the mood to talk today?"
   - Record 5s again.
   - Send second WAV to Xavier.
   - If user replies "yes" (intent) or is still silent -> leave (speak leave and run leave command).
   - Else -> continue normal flow (Xavier will produce response + commands).
Notes:
- Uses length-prefixed JSON (4-byte big-endian length) framing.
- For audio transfer, sends header JSON with encoding "audio/wav" then the raw WAV bytes immediately.
- Replace placeholder functions (TTS, execute_motion) with your production implementations.
"""

import socket, struct, json, time, os
import sounddevice as sd
import soundfile as sf

# ---------- CONFIG ----------
XAVIER_HOST = "xavier.local"   # change to Xavier IP
XAVIER_PORT = 6000
SESSION_PREFIX = "sess_rover1"
RECORD_SECONDS = 5.0           # 5 seconds recording as you specified
SAMPLE_RATE = 16000
CHANNELS = 1
WAV_TMP = "/tmp/nano_last.wav"

# TTS text
GREETING_TEXT = "Hello! I have arrived. Do you want to talk?"
FOLLOWUP_TEXT = "Are you not in the mood to talk today?"
LEAVE_TEXT = "Okay, I will leave. Take care."

# Timeouts
XAVIER_REPLY_TIMEOUT = 6.0     # seconds to wait for Xavier's JSON reply
CONNECT_TIMEOUT = 5.0

# Thresholds (used if Xavier returns stt/intent fields for local decisions)
STT_CONF_THRESHOLD = 0.60
INTENT_LEAVE_LABELS = {"affirm_not_mood", "not_mood", "leave_me", "i_am_not_in_mood", "yes"}

# ---------- helpers ----------

def send_json(sock, obj):
    data = json.dumps(obj).encode('utf-8')
    sock.sendall(struct.pack("!I", len(data)))
    sock.sendall(data)

def recv_json(sock, timeout=None):
    sock.settimeout(timeout)
    try:
        raw_len = sock.recv(4)
        if len(raw_len) < 4:
            return None
        (l,) = struct.unpack("!I", raw_len)
        payload = b""
        while len(payload) < l:
            chunk = sock.recv(l - len(payload))
            if not chunk:
                return None
            payload += chunk
        return json.loads(payload.decode('utf-8'))
    except socket.timeout:
        return None
    finally:
        sock.settimeout(None)

def play_tts(text):
    """Simple blocking TTS call. Replace with your playback if needed."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print("[Nano] TTS failed:", e)

def record_wav(path, seconds=5.0, sr=16000, ch=1):
    """Record `seconds` to a WAV file at `path`. Returns path."""
    print(f"[Nano] Recording {seconds}s -> {path}")
    rec = sd.rec(int(seconds * sr), samplerate=sr, channels=ch, dtype='int16')
    sd.wait()
    sf.write(path, rec, sr, subtype='PCM_16')
    print("[Nano] Recording saved.")
    return path

def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()

def execute_motion(cmd):
    """
    Execute motion command.
    This is a stub — replace with your motion controller interface.
    Expect cmd to be dict: { "cmd_id":..., "type":"leave_area"/"move"/..., "params":{...} }
    """
    print("[Nano] execute_motion() called with:", cmd)
    typ = cmd.get("type")
    params = cmd.get("params", {})
    # Example: leave_area -> perform backward motion for distance_m at speed
    if typ == "leave_area":
        distance = params.get("distance_m", 2.0)
        speed = params.get("speed", 0.3)
        direction = params.get("direction", "backward")
        # TODO: plug your motor calls here
        print(f"[Nano] Motion: {direction} {distance}m at speed {speed}")
        # simulate execution time (remove in real code)
        time.sleep(max(0.5, min(2.0, distance / max(0.1, speed))))
        return {"cmd_id": cmd.get("cmd_id"), "status": "done"}
    # Other command types -> implement
    time.sleep(0.2)
    return {"cmd_id": cmd.get("cmd_id"), "status": "unknown_command"}

# ---------- main comms flow ----------

def send_wav_and_get_result(wav_path, session, timeout=XAVIER_REPLY_TIMEOUT):
    """
    Connect to Xavier, send header JSON and WAV bytes, wait for JSON reply.
    Returns parsed JSON or None on timeout/error.
    """
    try:
        wav_bytes = read_bytes(wav_path)
        header = {
            "type": "audio_upload",
            "session": session,
            "encoding": "audio/wav",
            "samplerate": SAMPLE_RATE,
            "channels": CHANNELS,
            "duration": RECORD_SECONDS,
            "bytes": len(wav_bytes),
            "timestamp": time.time()
        }
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(CONNECT_TIMEOUT)
            s.connect((XAVIER_HOST, XAVIER_PORT))
            s.settimeout(None)
            send_json(s, header)
            s.sendall(wav_bytes)  # send raw WAV bytes right after header
            # wait for Xavier's JSON reply
            reply = recv_json(s, timeout=timeout)
            return reply
    except Exception as e:
        print("[Nano] send_wav_and_get_result exception:", e)
        return None

def handle_xavier_result(result):
    """
    Handle the JSON returned by Xavier.
    Expected result structure (example):
    {
      "type":"xavier_out",
      "session":"sess_...",
      "response_text":"...",
      "commands":[ {...}, ... ],
      "meta": { ... }
    }
    """
    if not result:
        return False
    # If Xavier returned a processing result with response_text and commands:
    resp_text = result.get("response_text", "")
    commands = result.get("commands", [])
    meta = result.get("meta", {})

    # Speak the response if present
    if resp_text:
        print("[Nano] Xavier response:", resp_text)
        play_tts(resp_text)

    # Execute commands sequentially
    if commands:
        for c in commands:
            res = execute_motion(c)
            print("[Nano] command exec result:", res)
    return True

def decide_leave_from_result(result):
    """
    Decide whether to leave based on Xavier's `meta` or `intent`.
    This is an optional local check; Xavier could already include a leave command.
    """
    if not result:
        return False
    # If Xavier suggests leave via a command
    cmds = result.get("commands", [])
    if any(c.get("type") in ("leave_area", "leave", "go_home") for c in cmds):
        return True
    # Or check meta.intent / stt_text if provided
    meta = result.get("meta", {})
    intent = meta.get("intent", "") or result.get("intent", "")
    intent_conf = float(meta.get("intent_conf", 0.0) or result.get("intent_conf", 0.0) or 0.0)
    stt_text = (meta.get("stt_text","") or "").lower().strip()
    stt_conf = float(meta.get("stt_conf", 0.0) or result.get("stt_conf", 0.0) or 0.0)

    if intent and intent in INTENT_LEAVE_LABELS and intent_conf >= STT_CONF_THRESHOLD:
        return True
    if stt_text in ("yes","yeah","yup","i'm not","i am not") and stt_conf >= STT_CONF_THRESHOLD:
        return True
    return False

# ---------- session-level flow implementing the two-step check ----------

def run_session():
    session = f"{SESSION_PREFIX}_{int(time.time())}"
    # 1) Greeting
    print("[Nano] Playing initial greeting...")
    play_tts(GREETING_TEXT)

    # 2) First recording & send
    wav1 = record_wav(WAV_TMP, RECORD_SECONDS, SAMPLE_RATE, CHANNELS)
    result1 = send_wav_and_get_result(wav1, session)

    if result1:
        # If Xavier replied immediately, handle result and exit or continue
        print("[Nano] Received immediate result from Xavier.")
        handled = handle_xavier_result(result1)
        # If Xavier included a leave command, will be executed inside handle_xavier_result
        return

    # If no result OR Xavier didn't indicate speech/intent -> we need second prompt
    # Reasoning: no reply often means silence or timeout.
    print("[Nano] No reply from Xavier or no speech detected. Asking follow-up.")
    play_tts(FOLLOWUP_TEXT)

    # 3) Second recording & send
    wav2 = record_wav(WAV_TMP, RECORD_SECONDS, SAMPLE_RATE, CHANNELS)
    result2 = send_wav_and_get_result(wav2, session + "_2")

    # If still no reply -> leave
    if not result2:
        print("[Nano] No reply from Xavier after follow-up. Default: leave.")
        play_tts(LEAVE_TEXT)
        # Issue local leave command (execute_motion stub)
        leave_cmd = {"cmd_id": f"leave_local_{int(time.time())}", "type": "leave_area", "params": {"speed":0.3, "distance_m":2.0}}
        execute_motion(leave_cmd)
        return

    # If result returned, check whether to leave or continue
    if decide_leave_from_result(result2):
        print("[Nano] Decision: leave based on Xavier result.")
        # speak Xavier response if present and execute any leave commands included
        handle_xavier_result(result2)
        return

    # Otherwise continue with normal flow (speak response + execute commands)
    print("[Nano] Continuing conversation per Xavier output.")
    handle_xavier_result(result2)
    return

if __name__ == "__main__":
    run_session()
