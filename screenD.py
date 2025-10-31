import paho.mqtt.client as mqtt
import base64
import speech_recognition as sr
import io

BROKER = "13.232.191.178"
PORT = 1883
TOPIC_SEND = "emobot/rover/command"
TOPIC_REPLY = "emobot/rover/reply"

def on_message(client, userdata, msg):
    print("🎧 Received audio data from Client-1")

    # Decode base64 -> wav
    audio_bytes = base64.b64decode(msg.payload)
    with open("received.wav", "wb") as f:
        f.write(audio_bytes)
    
    print("✅ Saved as received.wav")

    # Convert speech to text
    recognizer = sr.Recognizer()
    with sr.AudioFile("received.wav") as source:
        audio_data = recognizer.record(source)
        try:
            text = recognizer.recognize_google(audio_data)
            print(f"📝 Transcription: {text}")
            client.publish(TOPIC_REPLY, text)
        except sr.UnknownValueError:
            print("❌ Could not understand audio")
            client.publish(TOPIC_REPLY, "Sorry, I could not understand your voice.")
        except sr.RequestError:
            print("⚠️ STT service error")
            client.publish(TOPIC_REPLY, "Speech recognition service unavailable.")

client = mqtt.Client()
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.subscribe(TOPIC_SEND)
print("✅ Listening for audio...")
client.loop_forever()
