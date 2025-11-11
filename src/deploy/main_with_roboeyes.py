import time, serial, json, pyttsx3, os, threading, sys
import sounddevice as sd
import soundfile as sf
import numpy as np
import pygame
from roboeye import RoboEyes
from emotionResponse import stt, emotion_classification, response_llama

# ======================================
# Configurations
# ======================================
PORT = "/dev/ttyACM0"
BAUD = 115200
SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = None
DTYPE = 'int16'
DEFAULT_SPEED = 30
DEFAULT_STEPS = 1000
engine = pyttsx3.init()
engine.setProperty('rate', 150)

# ======================================
# Movement commands
# ======================================
movement = {
    "forward": {
        "left": {"direction": "forward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
        "right": {"direction": "forward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}
    },
    "backward": {
        "left": {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
        "right": {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}
    },
    "left": {
        "left": {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
        "right": {"direction": "forward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}
    },
    "right": {
        "left": {"direction": "forward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
        "right": {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}
    },
    "stop": {
        "left": {"direction": "stop", "steps": 0, "speed": 0},
        "right": {"direction": "stop", "steps": 0, "speed": 0}
    }
}


# ======================================
# Helper Functions
# ======================================
def record_audio(filename="user_voice.wav", duration=5):
    """Record audio to `filename` with configured SAMPLE_RATE and CHANNELS."""
    print(f"[Audio] Recording {duration}s -> {filename}")
    try:
        frames = int(duration * SAMPLE_RATE)
        audio_data = sd.rec(frames, samplerate=SAMPLE_RATE, channels=CHANNELS,
                            dtype=DTYPE, device=DEVICE)
        sd.wait()

        if np.issubdtype(audio_data.dtype, np.integer):
            maxval = np.iinfo(audio_data.dtype).max
            audio_float = audio_data.astype(np.float32) / float(maxval)
        else:
            audio_float = audio_data.astype(np.float32)

        sf.write(filename, audio_float, SAMPLE_RATE, format='WAV')
        print("[Audio] Saved:", filename)
    except Exception as e:
        print("[Audio] Recording failed:", e)
        raise


def speak_text(text):
    print(f"[TTS] Speaking: {text}")
    global engine
    engine.say(text)
    engine.runAndWait()


def send_command(arduino, cmd_dict):
    json_str = json.dumps(cmd_dict)
    arduino.write((json_str + "\n").encode())
    time.sleep(0.05)
    while arduino.in_waiting:
        response = arduino.readline().decode().strip()
        if response:
            print(f"🔁 Arduino: {response}")


def process_audio(filename="user_voice.wav"):
    transcript = stt(filename)
    if not transcript:
        print("❌ Could not understand voice.")
        return None, None, None
    print(f"🗣 Transcript: {transcript}")
    emotion = emotion_classification(filename, transcript)
    print(f"😃 Emotion Detected: {emotion}")
    reply = response_llama(transcript, emotion)
    print(f"🤖 LLM Reply: {reply}")
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
# RoboEyes Integration
# ======================================
def start_roboeyes():
    """Start RoboEyes in fullscreen mode in a background thread."""
    pygame.init()
    screen = pygame.display.set_mode((1024, 600), pygame.FULLSCREEN)
    pygame.display.set_caption("RoboEyes Display")
    eyes = RoboEyes(screen)
    eyes.setMood("default")

    def eye_loop():
        clock = pygame.time.Clock()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
            eyes.update()
            clock.tick(60)

    threading.Thread(target=eye_loop, daemon=True).start()
    return eyes


# ======================================
# Main Conversation + Emotion Loop
# ======================================
def conversation_loop(arduino, eyes):
    """Main emotion + movement loop."""
    while True:
        send_command(arduino, movement["forward"])
        send_command(arduino, movement["stop"])
        speak_text("Hi, how are you doing?")
        while True:
            record_audio()
            transcript, emotion, reply = process_audio()
            if not transcript:
                continue

            # 👁️ Update RoboEyes based on detected emotion
            if eyes and emotion:
                eyes.setMood(emotion)

            # Conversation-based actions
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
        print("🔄 Restarting conversation loop...\n")


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

    # Start RoboEyes thread
    eyes = start_roboeyes()
    print("👁️ RoboEyes display started (fullscreen mode).")

    # Start rover + emotion loop
    conversation_loop(arduino, eyes)
