import time, serial, json, pyttsx3, os, sys
import sounddevice as sd
import soundfile as sf
import numpy as np
import paho.mqtt.client as mqtt
from emotionResponse import stt, emotion_classification, response_llama

# Your existing MQTT host (same as before)
BROKER_HOST = "localhost"     # or your Jetson Nano IP if remote
BROKER_PORT = 1883
TOPIC = "roboeyes/emotion"

PORT = "/dev/ttyACM0"
BAUD = 115200
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = 'int16'
DEFAULT_SPEED = 30
DEFAULT_STEPS = 1000

engine = pyttsx3.init()
engine.setProperty('rate', 150)

movement = {
    "forward": {"left": {"direction": "forward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
                "right": {"direction": "forward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}},
    "backward": {"left": {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
                 "right": {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}},
    "left": {"left": {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
             "right": {"direction": "forward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}},
    "right": {"left": {"direction": "forward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
              "right": {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}},
    "stop": {"left": {"direction": "stop", "steps": 0, "speed": 0},
             "right": {"direction": "stop", "steps": 0, "speed": 0}}
}


def send_command(arduino, cmd_dict):
    json_str = json.dumps(cmd_dict)
    arduino.write((json_str + "\n").encode())
    time.sleep(0.05)
    while arduino.in_waiting:
        response = arduino.readline().decode().strip()
        if response:
            print(f"🔁 Arduino: {response}")


def record_audio(filename="user_voice.wav", duration=5):
    frames = int(duration * SAMPLE_RATE)
    audio_data = sd.rec(frames, samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE)
    sd.wait()
    if np.issubdtype(audio_data.dtype, np.integer):
        maxval = np.iinfo(audio_data.dtype).max
        audio_float = audio_data.astype(np.float32) / float(maxval)
    else:
        audio_float = audio_data.astype(np.float32)
    sf.write(filename, audio_float, SAMPLE_RATE, format='WAV')
    return filename


def speak_text(text):
    print(f"[TTS] {text}")
    global engine
    engine.say(text)
    engine.runAndWait()


def process_audio(filename="user_voice.wav"):
    transcript = stt(filename)
    if not transcript:
        return None, None, None
    emotion = emotion_classification(filename, transcript)
    reply = response_llama(transcript, emotion)
    return transcript.lower(), emotion.lower(), reply


def handle_movement(transcript, arduino):
    if "forward" in transcript:
        send_command(arduino, movement["forward"])
    elif "backward" in transcript:
        send_command(arduino, movement["backward"])
    elif "left" in transcript:
        send_command(arduino, movement["left"])
    elif "right" in transcript:
        send_command(arduino, movement["right"])
    elif "stop" in transcript:
        send_command(arduino, movement["stop"])


# ======================================
# MQTT Setup
# ======================================
client = mqtt.Client()

def connect_mqtt():
    try:
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        print(f"✅ Connected to MQTT broker at {BROKER_HOST}:{BROKER_PORT}")
    except Exception as e:
        print("❌ MQTT connection failed:", e)
        sys.exit(1)


def publish_emotion(emotion):
    client.publish(TOPIC, emotion)
    print(f"📡 Published emotion → {emotion}")


# ======================================
# Main Conversation Loop
# ======================================
def conversation_loop(arduino):
    while True:
        send_command(arduino, movement["forward"])
        send_command(arduino, movement["stop"])
        speak_text("Hi, how are you doing?")
        while True:
            record_audio()
            transcript, emotion, reply = process_audio()
            if not transcript:
                continue

            if emotion:
                publish_emotion(emotion)

            if "thank you for conversation" in transcript:
                speak_text("It was nice talking to you. Goodbye!")
                send_command(arduino, movement["forward"])
                time.sleep(2)
                send_command(arduino, movement["stop"])
                break
            elif "go away" in transcript and emotion == "angry":
                speak_text("Okay, I'm leaving.")
                send_command(arduino, movement["forward"])
                time.sleep(2)
                send_command(arduino, movement["stop"])
                break
            elif any(cmd in transcript for cmd in ["forward", "backward", "left", "right", "stop"]):
                handle_movement(transcript, arduino)
                continue

            speak_text(reply)
        time.sleep(3)


# ======================================
# Entry Point
# ======================================
if __name__ == "__main__":
    try:
        arduino = serial.Serial(PORT, BAUD, timeout=1)
        time.sleep(2)
        print(f"✅ Connected to Arduino on {PORT}")
    except serial.SerialException:
        print(f"❌ Failed to connect to {PORT}")
        sys.exit(1)

    connect_mqtt()
    conversation_loop(arduino)
