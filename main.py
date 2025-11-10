import time, serial, json, pyttsx3, os
import sounddevice as sd
import soundfile as sf
import numpy as np
from emotionResponse import stt, emotion_classification, response_llama

# ===============================
# Configuration
# ===============================
PORT = "com22"          # Arduino serial port on Jetson Nano
BAUD = 115200           # Must match Arduino Serial.begin()
SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = 'hw:1,0'
DTYPE = 'int32'
DEFAULT_SPEED = 20
DEFAULT_STEPS = 2000

arduino = None
reply = None
emotion = None

# ===============================
# Movement Commands
# ===============================
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


# ===============================
# Helper Functions
# ===============================
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
    """Send JSON command to Arduino."""
    json_str = json.dumps(cmd_dict)
    arduino.write((json_str + "\n").encode())  # newline signals end of command
    time.sleep(0.05)
    while arduino.in_waiting:
        response = arduino.readline().decode().strip()
        if response:
            print(f"🔁 Arduino: {response}")


def process_audio(filename="user_voice.wav"):
    """Perform speech-to-text, emotion detection, and LLM reply."""
    global reply, emotion

    transcript = stt(filename)
    if not transcript:
        print("❌ Could not understand voice.")
        return None, None

    print(f"🗣 Transcript: {transcript}")
    emotion = emotion_classification(filename, transcript)
    print(f"😃 Emotion Detected: {emotion}")

    reply = response_llama(transcript, emotion)
    print(f"🤖 LLM Reply: {reply}")

    return transcript.lower(), emotion.lower()


# ===============================
# Conversation Logic
# ===============================
def handle_movement_commands(transcript):
    """Move rover if user gives movement command."""
    if "forward" in transcript:
        send_command(movement["forward"])
        speak_text("Moving forward.")
    elif "backward" in transcript:
        send_command(movement["backward"])
        speak_text("Moving backward.")
    elif "left" in transcript:
        send_command(movement["left"])
        speak_text("Turning left.")
    elif "right" in transcript:
        send_command(movement["right"])
        speak_text("Turning right.")
    elif "stop" in transcript:
        send_command(movement["stop"])
        speak_text("Stopping.")


def main_loop():
    """Main conversation + movement loop."""
    while True:
        speak_text("Hi, how are you doing?")
        conversation_active = True

        while conversation_active:
            record_audio()
            transcript, detected_emotion = process_audio()

            if not transcript:
                continue

            # User says 'thank you for conversation' → end loop
            if "thank you for conversation" in transcript:
                speak_text("It was nice talking to you. Goodbye!")
                send_command(movement["forward"])
                time.sleep(2)
                send_command(movement["stop"])
                conversation_active = False
                break

            # User says 'go away' + emotion = angry → move forward (leave)
            elif "go away" in transcript and "angry" in detected_emotion:
                speak_text("Okay, I'm leaving.")
                send_command(movement["forward"])
                time.sleep(2)
                send_command(movement["stop"])
                conversation_active = False
                break

            # If user commands rover movement mid-conversation
            elif any(word in transcript for word in ["forward", "backward", "left", "right", "stop"]):
                handle_movement_commands(transcript)
                continue

            # Normal reply
            speak_text(reply)

        # After ending conversation, wait and start again
        time.sleep(3)
        print("🔄 Restarting conversation loop...\n")


# ===============================
# Main Execution
# ===============================
if __name__ == "__main__":
    try:
        print("[System] Connecting to Arduino...")
        arduino = serial.Serial(PORT, BAUD, timeout=1)
        time.sleep(2)
        print(f"✅ Connected to Arduino on {PORT}")
    except serial.SerialException:
        print(f"❌ Failed to connect to {PORT}. Check USB cable or permissions.")
        exit()

    # Start looping conversation
    main_loop()
