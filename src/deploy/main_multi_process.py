import time, serial, json, pyttsx3, os, threading, sys
import sounddevice as sd
import soundfile as sf
import numpy as np
import pygame
from emotionResponse import stt, emotion_classification, response_llama
from multiprocessing import Process, Queue
from roboeye import RoboEyes

# ======================================
# Configurations
# ======================================
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


# ======================================
# RoboEyes Process
# ======================================
def roboeyes_process(queue):
    """Runs RoboEyes in its own process and listens for emotion updates."""
    pygame.init()
    screen = pygame.display.set_mode((1024, 600), pygame.FULLSCREEN)
    pygame.display.set_caption("RoboEyes - Process Mode")
    eyes = RoboEyes(screen)
    eyes.setMood("default")

    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        if not queue.empty():
            mood = queue.get()
            eyes.setMood(mood)

        eyes.update()
        clock.tick(60)


# ======================================
# Helper Functions
# ======================================
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
# Main Conversation Loop
# ======================================
def conversation_loop(arduino, queue):
    while True:
        send_command(arduino, movement["forward"])
        send_command(arduino, movement["stop"])
        speak_text("Hi, how are you doing?")
        while True:
            record_audio()
            transcript, emotion, reply = process_audio()
            if not transcript:
                continue

            # 🚀 Send emotion to RoboEyes process
            if emotion:
                queue.put(emotion)

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

    # Start RoboEyes in a new process with shared queue
    q = Queue()
    p = Process(target=roboeyes_process, args=(q,), daemon=True)
    p.start()
    print("👁️ RoboEyes running in separate process.")

    # Start main control loop
    conversation_loop(arduino, q)
