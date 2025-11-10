import time, serial, json, pyttsx3, threading, sys
import sounddevice as sd
import soundfile as sf
import numpy as np
from emotionResponse import stt, emotion_classification, response_llama
from roboeyes_display import RoboEyes  # 👈 Importing RoboEyes (fullscreen display)

PORT = "/dev/ttyACM0"
BAUD = 115200
SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = 'hw:1,0'
DTYPE = 'int32'
DEFAULT_SPEED = 20
DEFAULT_STEPS = 2000

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

# ---------------- AUDIO & SERIAL HELPERS ---------------- #
def record_audio(filename="user_voice.wav", duration=3):
    print(f"🎙 Recording {duration}s...")
    audio_data = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                        channels=CHANNELS, dtype=DTYPE, device=DEVICE)
    sd.wait()
    audio_float = audio_data.astype(np.float32) / np.iinfo(np.int32).max
    sf.write(filename, audio_float, SAMPLE_RATE)
    print(f"[Audio] Saved: {filename}")


def speak_text(text):
    print(f"[TTS] Speaking: {text}")
    engine = pyttsx3.init()
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


# ---------------- MAIN LOGIC ---------------- #
def conversation_loop(eyes, arduino):
    while True:
        speak_text("Hi, how are you doing?")
        while True:
            record_audio()
            transcript, emotion, reply = process_audio()
            if not transcript:
                continue

            # 👀 Update eye emotion live
            eyes.setMood(emotion)

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


# ---------------- MAIN ENTRY ---------------- #
if __name__ == "__main__":
    try:
        arduino = serial.Serial(PORT, BAUD, timeout=1)
        time.sleep(2)
        print(f"✅ Connected to Arduino on {PORT}")
    except serial.SerialException:
        print(f"❌ Failed to connect to {PORT}")
        sys.exit(1)

    # Initialize RoboEyes (always fullscreen)
    eyes = RoboEyes()

    # Run eyes in background thread
    threading.Thread(target=eyes.run_forever, daemon=True).start()

    # Run main conversation loop
    conversation_loop(eyes, arduino)
