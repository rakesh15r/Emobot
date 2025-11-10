import time, serial, json, pyttsx3, os
import sounddevice as sd
import soundfile as sf
import numpy as np
import base64
from emotionResponse import (
    stt,
    emotion_classification,
    response_llama
)

PORT = "com22"   # Arduino serial port on Jetson Nano
BAUD = 115200            # Must match Arduino Serial.begin()
arduino = None

SERIAL_BAUDRATE = 115200
BAUDRATE = 57600
SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = 'hw:1,0'
DTYPE = 'int32'
DEFAULT_SPEED = 20
DEFAULT_STEPS = 2000

reply = None
emotion = None

movement = {
    "forward": {
        "left":  {"direction": "forward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
        "right": {"direction": "forward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}
    },
    "backward": {
        "left":  {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
        "right": {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}
    },
    "left": {
        "left":  {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
        "right": {"direction": "forward",  "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}
    },
    "right": {
        "left":  {"direction": "forward",  "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
        "right": {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}
    },
    "stop": {
        "left":  {"direction": "stop", "steps": 0, "speed": 0},
        "right": {"direction": "stop", "steps": 0, "speed": 0}
    }
}

def record_audio(filename="user_voice.wav", duration=3):
    print(f"🎙 Recording {duration}s...")
    audio_data = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        device=DEVICE
    )
    sd.wait()
    audio_float = audio_data.astype(np.float32) / np.iinfo(np.int32).max
    sf.write(filename, audio_float, SAMPLE_RATE)
    print(f"[Audio] Saved: {filename}")

def speak_text(text):
    print(f"[TTS] Speaking: {text}")
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()

def send_command(cmd_dict):
    """Send a JSON command to Arduino."""
    json_str = json.dumps(cmd_dict)
    arduino.write((json_str + "\n").encode())  # newline signals end of command
    time.sleep(0.05)

    # Read any Arduino response
    while arduino.in_waiting:
        response = arduino.readline().decode().strip()
        if response:
            print(f"🔁 Arduino: {response}")

def process_audio(filename="user_voice.wav"):
    global reply, emotion

    transcript = stt(filename)
    if not transcript:
        error_msg = "Sorry, I could not understand your voice."
        print(error_msg)
        return
    print(f"Transcript: {transcript}")

    emotion = emotion_classification("received.wav", transcript)
    print(f"Emotion Detected: {emotion}")

    reply = response_llama(transcript, emotion)
    print(f"LLM reply: {reply}")



if __name__ == "__main__":
    try:
        print("[System] Connecting to Arduino...")
        arduino = serial.Serial(PORT, BAUD, timeout=1)
        time.sleep(2)  # Allow Arduino to reset
        print(f"✅ Connected to Arduino on {PORT}")
    except serial.SerialException:
        print(f"❌ Failed to connect to {PORT}. Check USB cable or permissions.")
        exit()
    
    # Moving forward for a while 

    send_command(movement["forward"])
    speak_text("Hi, how are you doing?") # Greeting word
    # Rover conversation
    record_audio()
    process_audio()
    speak_text(reply)