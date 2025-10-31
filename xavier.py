import paho.mqtt.client as mqtt
import base64
import json
import os
import time

# === Import your existing modules ===
from emotionResponse import (
    stt,
    emotion_classification,
    response_llama
)

# =================== MQTT CONFIG ===================
BROKER = "13.232.191.178"
PORT = 1883

TOPIC_RECV_AUDIO = "emobot/rover/command"   # From Client-1
TOPIC_SEND_REPLY = "emobot/rover/reply"     # Back to Client-1
TOPIC_SCREEN_CMD = "emobot/screen/command"  # To Client-3 (RoboEyes)

print("🚀 Client-2: Emotion + LLM Response Engine starting...")

# =================== MQTT CALLBACKS ===================
def on_connect(client, userdata, flags, rc):
    print(f"✅ Connected to MQTT Broker: {BROKER}:{PORT}")
    client.subscribe(TOPIC_RECV_AUDIO)
    print(f"📡 Subscribed to: {TOPIC_RECV_AUDIO}")

def on_message(client, userdata, msg):
    print("🎧 Received data from Client-1")

    try:
        payload = msg.payload.decode().strip()

        # Stop signal
        if payload.lower() == "stop":
            print("🛑 Stop signal received from Client-1")
            client.publish(TOPIC_SEND_REPLY, json.dumps({"emotion": "neutral", "reply": "Stopping conversation."}))
            client.publish(TOPIC_SCREEN_CMD, "default")  # Reset RoboEyes
            client.loop_stop()
            return

        # Save received audio file
        audio_bytes = base64.b64decode(payload)
        with open("received.wav", "wb") as f:
            f.write(audio_bytes)
        print("💾 Saved received.wav")

        # --- STEP 1: STT ---
        transcript = stt("received.wav")
        if not transcript:
            error_msg = "Sorry, I could not understand your voice."
            client.publish(TOPIC_SEND_REPLY, json.dumps({"emotion": "unknown", "reply": error_msg}))
            client.publish(TOPIC_SCREEN_CMD, "tired")
            return

        print(f"🗣️ Transcript: {transcript}")

        # --- STEP 2: Emotion Classification ---
        emotion = emotion_classification("received.wav", transcript)
        print(f"💫 Emotion Detected: {emotion}")

        # --- STEP 3: Generate Response from LLM ---
        reply = response_llama(transcript, emotion)
        print(f"🤖 LLM Reply: {reply}")

        # --- STEP 4: Publish Back to Client-1 ---
        response_data = {"emotion": emotion, "reply": reply}
        client.publish(TOPIC_SEND_REPLY, json.dumps(response_data))
        print("📤 Sent emotion + reply to Client-1")

        # --- STEP 5: Notify Client-3 (RoboEyes) ---
        emotion_clean = emotion.lower().strip()
        # Map LLM emotion to RoboEyes moods if needed
        emotion_map = {
            "happy": "happy",
            "excited": "happy",
            "angry": "angry",
            "frustrated": "angry",
            "tired": "tired",
            "sad": "tired",
            "neutral": "default"
        }
        mapped_emotion = emotion_map.get(emotion_clean, "default")

        client.publish(TOPIC_SCREEN_CMD, mapped_emotion)
        print(f"👁️ Sent emotion '{mapped_emotion}' to RoboEyes ({TOPIC_SCREEN_CMD})")

        # Optional cleanup
        if os.path.exists("received.wav"):
            os.remove("received.wav")

    except Exception as e:
        print(f"❌ Error processing message: {e}")
        client.publish(TOPIC_SEND_REPLY, json.dumps({"emotion": "error", "reply": str(e)}))
        client.publish(TOPIC_SCREEN_CMD, "default")


# =================== MAIN ===================
client = mqtt.Client("Client2_EmotionBot")
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)
client.loop_forever()
