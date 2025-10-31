import paho.mqtt.client as mqtt
import base64
import json
import os
import time

# === Imports from your script ===
from emotionResponse import (
    stt,
    emotion_classification,
    response_llama
)

BROKER = "13.232.191.178"
PORT = 1883
TOPIC_SEND = "emobot/rover/command"
TOPIC_REPLY = "emobot/rover/reply"
SCREEN = "emobot/screen/command"

print("🚀 Client-2: Emotion + LLM Response Engine starting...")

# -----------------------
# MQTT CALLBACKS
# -----------------------
def on_connect(client, userdata, flags, rc):
    print("✅ Connected to MQTT Broker!")
    client.subscribe(TOPIC_SEND)
    print(f"📡 Subscribed to: {TOPIC_SEND}")

def on_message(client, userdata, msg):
    print("🎧 Received data from Client-1")

    try:
        # Decode incoming base64 message
        payload = msg.payload.decode()

        # Stop signal
        if payload.lower().strip() == "stop":
            print("🛑 Stop signal received from Client-1")
            client.publish(TOPIC_REPLY, json.dumps({"emotion": "neutral", "reply": "Stopping conversation."}))
            client.loop_stop()
            return

        # Save incoming audio
        audio_bytes = base64.b64decode(payload)
        with open("received.wav", "wb") as f:
            f.write(audio_bytes)
        print("💾 Saved received.wav")

        # --- STEP 1: Speech-to-Text ---
        transcript = stt("received.wav")
        if not transcript:
            reply_payload = {"emotion": "unknown", "reply": "Sorry, I couldn’t understand the audio."}
            client.publish(TOPIC_REPLY, json.dumps(reply_payload))
            return
        print(f"🗣️ Transcript: {transcript}")

        # --- STEP 2: Emotion Classification ---
        emotion = emotion_classification("received.wav", transcript)
        print(f"💫 Emotion detected: {emotion}")

        # --- STEP 3: Generate LLM Reply ---
        reply = response_llama(transcript, emotion)
        print(f"🤖 LLM Reply: {reply}")

        # --- STEP 4: Publish back to Client-1 ---
        response_data = {"emotion": emotion, "reply": reply}
        client.publish(TOPIC_REPLY, json.dumps(response_data))
        client.publish(SCREEN, emotion)
        print("📤 Sent emotion + reply back to Client-1")

        # Optional cleanup
        if os.path.exists("received.wav"):
            os.remove("received.wav")

    except Exception as e:
        print(f"❌ Error processing message: {e}")
        client.publish(TOPIC_REPLY, json.dumps({"emotion": "error", "reply": str(e)}))


# -----------------------
# MAIN MQTT LOOP
# -----------------------
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)
client.loop_forever()
