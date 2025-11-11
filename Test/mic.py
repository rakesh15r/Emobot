import paho.mqtt.client as mqtt
import sounddevice as sd
from scipy.io.wavfile import write
import pyttsx3
import io
import base64
import time

BROKER = "13.232.191.178"
PORT = 1883
TOPIC_SEND = "emobot/rover/command"
TOPIC_REPLY = "emobot/rover/reply"

engine = pyttsx3.init()

def on_message(client, userdata, msg):
    text = msg.payload.decode()
    print(f"🗣️ Client-2 replied: {text}")
    engine.say(text)
    engine.runAndWait()

client = mqtt.Client()
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.subscribe(TOPIC_REPLY)
client.loop_start()

# Ask user
engine.say("Do you want to talk?")
engine.runAndWait()
ans = input("Do you want to talk? (y/n): ")

if ans.lower() == 'y':
    fs = 44100  # Sample rate
    seconds = 15
    print("🎙️ Recording for 5 seconds...")
    recording = sd.rec(int(seconds * fs), samplerate=fs, channels=2)
    sd.wait()
    write("voice.wav", fs, recording)
    print("✅ Saved voice.wav")

    # Encode file to base64
    with open("voice.wav", "rb") as f:
        data = base64.b64encode(f.read()).decode()

    client.publish(TOPIC_SEND, data)
    print("📤 Sent wav file to Client-2")

print("⏳ Waiting for response...")
while True:
    time.sleep(1)
