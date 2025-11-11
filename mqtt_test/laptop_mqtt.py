# #!/usr/bin/env python3
# """
# laptop_mqtt_processor.py

# - Subscribes to emobot/rover/audio
# - Decodes Base64 WAV and saves a temp file
# - Runs your model pipeline on the WAV (stubbed)
# - Publishes JSON response to emobot/rover/command
# - Optionally publishes a correlated reply to emobot/rover/response/<req_id>
# """

# import os
# import json
# import base64
# import tempfile
# import threading
# import time
# from pathlib import Path

# import paho.mqtt.client as mqtt
# import soundfile as sf  # used only if you want to read/verify WAV

# # ---------------- CONFIG ----------------
# BROKER = "13.232.191.178"
# PORT = 1883
# AUDIO_TOPIC = "emobot/rover/audio"
# COMMAND_TOPIC = "emobot/rover/command"
# RESPONSE_TOPIC_PREFIX = "emobot/rover/response"   # publish to RESPONSE_TOPIC_PREFIX/<req_id> (optional)
# CLIENT_ID = "model-server-" + str(int(time.time()))
# # ----------------------------------------

# client = mqtt.Client(client_id=CLIENT_ID)

# def run_models_on_wav(wav_path):
#     """
#     REPLACE THIS with your actual model pipeline:
#       1) ASR -> transcript (string)
#       2) Emotion classifier -> tag (string)
#       3) Policy / response generator -> response_text (string) and command dict

#     Return a dict like:
#       {
#         "transcript": "...",
#         "emotion": "neutral",
#         "response_text": "Okay, moving forward.",
#         "command": {"action":"move","direction":"forward","speed":0.6,"duration":2.0}
#       }
#     """
#     # ---------- STUB (demo) ----------
#     # optionally read info about file:
#     try:
#         info = sf.info(wav_path)
#         print(f"[MODEL] WAV info: {info}")
#     except Exception:
#         pass

#     # TODO: implement real inference here
#     transcript = "simulated transcription"
#     emotion = "neutral"
#     response_text = "Okay, moving forward."
#     command = {"action": "move", "direction": "forward", "speed": 0.6, "duration": 2.0}

#     # Simulate processing delay
#     time.sleep(0.5)

#     return {
#         "transcript": transcript,
#         "emotion": emotion,
#         "response_text": response_text,
#         "command": command
#     }

# def publish_command_response(result_dict, req_id=None):
#     """
#     Publish reply to COMMAND_TOPIC so rover receives.
#     Optionally publish per-request response to RESPONSE_TOPIC_PREFIX/<req_id>
#     """
#     payload = {
#         "response_text": result_dict.get("response_text", ""),
#         "command": result_dict.get("command")
#     }
#     # Publish to shared command topic
#     client.publish(COMMAND_TOPIC, json.dumps(payload), qos=1)
#     print(f"[PUB] Published to {COMMAND_TOPIC}: {payload}")

#     # Optionally publish to a per-request topic so the requesting rover can correlate responses
#     if req_id:
#         topic_resp = f"{RESPONSE_TOPIC_PREFIX}/{req_id}"
#         client.publish(topic_resp, json.dumps(payload), qos=1)
#         print(f"[PUB] Published to {topic_resp} (per-request)")

# def process_audio_message(req_id, wav_bytes):
#     """Save wav_bytes to temp file, run models, publish responses."""
#     tmp = None
#     try:
#         tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
#         tmp.write(wav_bytes)
#         tmp.flush()
#         tmp.close()
#         wav_path = tmp.name
#         print(f"[PROC] Saved incoming audio to {wav_path} (req_id={req_id})")

#         # Run ML pipeline (replace with real models)
#         result = run_models_on_wav(wav_path)

#         # Publish results
#         publish_command_response(result, req_id=req_id)

#     except Exception as e:
#         print("[PROC] Error processing audio:", e)
#     # finally:
#     #     # cleanup temp file
#     #     if tmp is not None:
#     #         try:
#     #             os.remove(tmp.name)
#     #         except Exception:
#     #             pass

# def on_connect(client, userdata, flags, rc):
#     if rc == 0:
#         print(f"[MQTT] Connected to broker {BROKER}:{PORT}")
#         client.subscribe(AUDIO_TOPIC, qos=1)
#         print(f"[MQTT] Subscribed to {AUDIO_TOPIC}")
#     else:
#         print(f"[MQTT] Connection failed with rc={rc}")

# def on_message(client, userdata, msg):
#     """Called in MQTT network loop thread — offload heavy work to worker threads."""
#     try:
#         payload = msg.payload.decode('utf-8')
#         data = json.loads(payload)
#     except Exception as e:
#         print("[MQTT] Invalid JSON on audio topic:", e)
#         return

#     req_id = data.get("req_id")
#     wav_b64 = data.get("wav_b64")
#     if not wav_b64:
#         print("[MQTT] message missing wav_b64; ignoring")
#         return

#     try:
#         wav_bytes = base64.b64decode(wav_b64)
#     except Exception as e:
#         print("[MQTT] base64 decode failed:", e)
#         return

#     # offload processing to background thread
#     threading.Thread(target=process_audio_message, args=(req_id, wav_bytes), daemon=True).start()

# def main():
#     client.on_connect = on_connect
#     client.on_message = on_message
#     print("[SYSTEM] Connecting to MQTT broker...", BROKER, PORT)
#     client.connect(BROKER, PORT, keepalive=60)
#     try:
#         client.loop_forever()
#     except KeyboardInterrupt:
#         print("[SYSTEM] Interrupted, exiting")
#     finally:
#         try:
#             client.disconnect()
#         except Exception:
#             pass

# if __name__ == "__main__":
#     main()

#!/usr/bin/env python3
"""
laptop_mqtt_pipeline.py

MQTT-based model pipeline for EMOBOT:

- Subscribes to: emobot/rover/audio
- For each incoming WAV (base64):
    1) Emotion classification (stub)
    2) Speech-to-text (STT) (stub)
    3) Dialogue intent/command detection (simple rule-based)
    4) Response generation (stub)
- Publishes:
    - emobot/rover/command  <-- broadcast reply (response_text + optional command)
    - emobot/rover/response/<req_id>  <-- per-request reply (optional)
- Keeps received WAVs in ./received_wavs/ for debugging
- Replace the stub functions (emotion_classify, run_stt, generate_response) with real models later.
"""

import os
import json
import base64
import tempfile
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt
import soundfile as sf  # for WAV info (optional)

# -------- CONFIG --------
BROKER = "13.232.191.178"
PORT = 1883
AUDIO_TOPIC = "emobot/rover/audio"
COMMAND_TOPIC = "emobot/rover/command"
RESPONSE_TOPIC_PREFIX = "emobot/rover/response"
SAVE_DIR = "received_wavs"   # permanent storage for debugging
CLIENT_ID = "model-pipeline-" + str(int(time.time()))
# ------------------------

os.makedirs(SAVE_DIR, exist_ok=True)

client = mqtt.Client(client_id=CLIENT_ID)

# ---------- STUB / MODEL BLOCKS (replace these) ----------
def emotion_classify(wav_path):
    """
    Emotion classifier stub.
    Input: wav_path (file)
    Return: one of: 'neutral', 'happy', 'sad', 'angry', 'surprised', etc.
    Currently returns a deterministic example for testing.
    Replace this with your emotion model inference.
    """
    # Example deterministic stub: choose emotion based on filename hash (for variation)
    h = hash(wav_path) % 5
    mapping = {0: "neutral", 1: "happy", 2: "sad", 3: "angry", 4: "calm"}
    emotion = mapping.get(h, "neutral")
    print(f"[EMOTION] (stub) -> {emotion}")
    return emotion

def run_stt(wav_path):
    """
    STT stub.
    Input: wav_path
    Return: plain text (transcript)
    Replace this with real ASR model inference (Whisper / Kaldi / Cloud ASR, etc.)
    """
    # Deterministic stub: choose text based on filename to allow different test cases,
    # but also look for a small set of words to simulate commands.
    # For easier testing, you can manually edit returned_text below.
    # Example variations:
    sample_texts = [
        "move forward",
        "turn left",
        "please tell me a joke",
        "stop",
        "move backward",
        "what is your name",
        "go right",
        "move forward two meters"
    ]
    idx = hash(wav_path) % len(sample_texts)
    transcript = sample_texts[idx]
    print(f"[STT] (stub) -> {transcript}")
    return transcript

def detect_command_and_parse(transcript, emotion):
    """
    Decide if the transcript is a command or generic dialogue and, if command, produce a command dict.
    Returns: (is_command:bool, command_dict_or_None)
    command_dict format:
      {"action":"move", "direction":"forward", "speed":0.6, "duration":2.0}
    Heuristic rule-based parsing implemented here (simple).
    Replace with your dialogue / intent parser for production.
    """
    t = transcript.lower()
    words = t.split()

    # simple command keywords
    if any(k in words for k in ["move", "go", "forward", "backward", "back", "left", "right", "stop", "turn"]):
        # parse direction
        if "stop" in words:
            return True, {"action": "stop"}

        # direction mapping
        if "forward" in words or "move forward" in t or "go forward" in t:
            direction = "forward"
        elif "backward" in words or "move back" in t or "go back" in t or "back" in words:
            direction = "backward"
        elif "left" in words or "turn left" in t:
            direction = "left"
        elif "right" in words or "turn right" in t:
            direction = "right"
        else:
            # default to forward if contains move/go but no direction
            direction = "forward"

        # crude speed/duration extraction (look for numbers)
        # default speed/duration
        speed = 0.6
        duration = 2.0
        # look for numeric tokens (e.g., "2", "two", "3 seconds", "2 meters")
        for w in words:
            try:
                v = float(w)
                # if a number present, map it to duration in seconds (simple)
                # e.g., "move forward 3" -> 3 seconds
                duration = max(0.5, min(10.0, v))
            except:
                # handle words like "two" (very small mapping)
                word_to_num = {"one":1, "two":2, "three":3, "four":4, "five":5}
                if w in word_to_num:
                    duration = float(word_to_num[w])
        # If user said "meters" we might want to convert distance to duration, but here keep simple.

        cmd = {"action":"move", "direction": direction, "speed": speed, "duration": duration}
        print(f"[INTENT] Detected command -> {cmd}")
        return True, cmd

    # otherwise not a movement command -> treat as normal dialogue
    print("[INTENT] No command detected; treating as dialogue.")
    return False, None

def generate_response(transcript, emotion, is_command):
    """
    Response generation stub.
    - If it's a command, produce an acknowledgement.
    - If it's dialogue, produce a conversational reply.
    Replace with real response-generation model (chatbot) as needed.
    """
    if is_command:
        # Acknowledge the command (include detected direction if possible)
        # simple templating
        # try to pick direction word if present
        dir_words = ["forward","backward","left","right","stop"]
        found = None
        for d in dir_words:
            if d in transcript.lower():
                found = d; break
        if found:
            response = f"Okay, executing {found}."
        else:
            response = "Okay, executing your command."
    else:
        # generic reply based on emotion (very simple)
        if emotion == "happy":
            response = "I'm glad to hear that!"
        elif emotion == "sad":
            response = "I'm sorry to hear that. I'm here for you."
        elif emotion == "angry":
            response = "I understand you're upset. How can I help?"
        else:
            response = "Thanks for sharing. What else would you like to do?"

    print(f"[RESP] (stub) -> {response}")
    return response
# ---------------- END STUBS ----------------

# ---------- Pipeline processing ----------
def publish_command_response(result_dict, req_id=None):
    """
    Publish reply to COMMAND_TOPIC and optional per-request topic.
    result_dict should contain at least 'response_text' and optional 'command'
    """
    payload = {
        "response_text": result_dict.get("response_text", ""),
        "command": result_dict.get("command")
    }
    client.publish(COMMAND_TOPIC, json.dumps(payload), qos=1)
    print(f"[PUB] Published to {COMMAND_TOPIC}: {payload}")

    if req_id:
        topic_resp = f"{RESPONSE_TOPIC_PREFIX}/{req_id}"
        client.publish(topic_resp, json.dumps(payload), qos=1)
        print(f"[PUB] Published to {topic_resp} (per-request)")

def process_audio_message(req_id, wav_bytes, meta=None):
    """
    Full pipeline for a single audio message.
    Saves WAV to SAVE_DIR, runs emotion->stt->intent->response, publishes reply.
    """
    tmp = None
    saved_path = None
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp.write(wav_bytes)
        tmp.flush()
        tmp.close()
        wav_path = tmp.name

        # move to permanent folder with req_id prefix for debugging
        base = os.path.basename(wav_path)
        saved_path = os.path.join(SAVE_DIR, f"{req_id}_{base}")
        os.replace(wav_path, saved_path)
        print(f"[PROC] Saved incoming audio to {saved_path} (req_id={req_id})")

        # optional: print wav info
        try:
            info = sf.info(saved_path)
            print(f"[MODEL] WAV info: {saved_path}\n{info}")
        except Exception:
            pass

        # 1) Emotion classification
        emotion = emotion_classify(saved_path)

        # 2) Speech-to-text
        transcript = run_stt(saved_path)

        # 3) Dialogue intent / command detection
        is_cmd, cmd = detect_command_and_parse(transcript, emotion)

        # 4) Response generation (acknowledge + dialogue)
        response_text = generate_response(transcript, emotion, is_cmd)

        # 5) Build result and publish
        result = {
            "transcript": transcript,
            "emotion": emotion,
            "response_text": response_text,
            "command": cmd
        }
        publish_command_response(result, req_id=req_id)

    except Exception as e:
        print("[PROC] Error processing audio:", e)
    # do not delete saved wavs so you can inspect them for debugging

# ---------- MQTT callbacks ----------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to broker {BROKER}:{PORT}")
        client.subscribe(AUDIO_TOPIC, qos=1)
        print(f"[MQTT] Subscribed to {AUDIO_TOPIC}")
    else:
        print(f"[MQTT] Connection failed with rc={rc}")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8')
        data = json.loads(payload)
    except Exception as e:
        print("[MQTT] Invalid JSON on audio topic:", e)
        return

    req_id = data.get("req_id") or str(int(time.time()*1000))
    wav_b64 = data.get("wav_b64")
    if not wav_b64:
        print("[MQTT] No wav_b64 in payload; ignoring")
        return

    try:
        wav_bytes = base64.b64decode(wav_b64)
    except Exception as e:
        print("[MQTT] base64 decode failed:", e)
        return

    # offload processing to a background thread
    threading.Thread(target=process_audio_message, args=(req_id, wav_bytes, data.get("meta")), daemon=True).start()

# ---------- main ----------
def main():
    client.on_connect = on_connect
    client.on_message = on_message
    print("[SYSTEM] Connecting to MQTT broker...", BROKER, PORT)
    client.connect(BROKER, PORT, keepalive=60)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("[SYSTEM] Interrupted, exiting")
    finally:
        try:
            client.disconnect()
        except:
            pass

if __name__ == "__main__":
    import tempfile
    main()

