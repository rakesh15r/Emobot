import time, serial, json, pyttsx3, os, threading, sys
import sounddevice as sd
import soundfile as sf
import numpy as np
import pygame
from emotionResponse import stt, emotion_classification, response_llama

# ======================================
# Configurations
# ======================================
PORT = "/dev/ttyACM0"
BAUD = 115200
SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = 'hw:1,0'
DTYPE = 'int32'
DEFAULT_SPEED = 20
DEFAULT_STEPS = 2000

# ======================================
# Colors and Constants (from RoboEyes)
# ======================================
BLACK = (10, 10, 20)
NEON_CYAN = (0, 255, 255)
DEFAULT, TIRED, ANGRY, HAPPY = 0, 1, 2, 3

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
# RoboEyes Class
# ======================================
class RoboEyes:
    def __init__(self, screen):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.frameInterval = 20
        self.fpsTimer = 0
        self.eyeW = 300
        self.eyeH = 280
        self.space = 130
        total_width = self.eyeW * 2 + self.space
        self.eyeLx = (self.w - total_width) // 2
        self.eyeRx = self.eyeLx + self.eyeW + self.space
        self.eyeLy = (self.h - self.eyeH) // 2 - 10
        self.eyeRy = self.eyeLy
        self.eyeOpenAmount = 1.0
        self.mood = DEFAULT
        self.blinking = False
        self.blinkStart = 0
        self.blinkDuration = 0.25
        self.lastBlink = 0
        self.blinkInterval = 3

    def millis(self): return time.time() * 1000

    def setMood(self, mood_name: str):
        mood_name = mood_name.lower().strip()
        if mood_name == "tired":
            self.mood = TIRED
        elif mood_name == "angry":
            self.mood = ANGRY
        elif mood_name == "happy":
            self.mood = HAPPY
        else:
            self.mood = DEFAULT
        print(f"👉 Mood set to: {mood_name.upper()}")

    def blink(self):
        self.blinking = True
        self.blinkStart = time.time()

    def updateBlink(self):
        now = time.time()
        if now - self.lastBlink > self.blinkInterval and not self.blinking:
            self.blink()
            self.lastBlink = now
            self.blinkInterval = 3 + np.random.random() * 3
        if self.blinking:
            elapsed = now - self.blinkStart
            if elapsed < self.blinkDuration / 2:
                self.eyeOpenAmount = 1.0 - (elapsed / (self.blinkDuration / 2))
            elif elapsed < self.blinkDuration:
                self.eyeOpenAmount = (elapsed - self.blinkDuration / 2) / (self.blinkDuration / 2)
            else:
                self.eyeOpenAmount = 1.0
                self.blinking = False

    def drawEyes(self):
        self.screen.fill(BLACK)
        color = NEON_CYAN
        mood = self.mood

        # Draw simple shape variations
        left_eye = pygame.Rect(self.eyeLx, self.eyeLy, self.eyeW, int(self.eyeH * self.eyeOpenAmount))
        right_eye = pygame.Rect(self.eyeRx, self.eyeRy, self.eyeW, int(self.eyeH * self.eyeOpenAmount))

        if mood == ANGRY:
            pygame.draw.polygon(self.screen, color, [
                (left_eye.left, left_eye.top + 50),
                (left_eye.right, left_eye.top + 10),
                (left_eye.right, left_eye.bottom),
                (left_eye.left, left_eye.bottom)
            ])
            pygame.draw.polygon(self.screen, color, [
                (right_eye.left, right_eye.top + 10),
                (right_eye.right, right_eye.top + 50),
                (right_eye.right, right_eye.bottom),
                (right_eye.left, right_eye.bottom)
            ])
        elif mood == HAPPY:
            pygame.draw.ellipse(self.screen, color, left_eye)
            pygame.draw.ellipse(self.screen, color, right_eye)
        elif mood == TIRED:
            pygame.draw.rect(self.screen, color, left_eye, border_radius=30)
            pygame.draw.rect(self.screen, color, right_eye, border_radius=30)
        else:
            pygame.draw.ellipse(self.screen, color, left_eye)
            pygame.draw.ellipse(self.screen, color, right_eye)

        pygame.display.flip()

    def update(self):
        now = self.millis()
        if now - self.fpsTimer >= self.frameInterval:
            self.updateBlink()
            self.drawEyes()
            self.fpsTimer = now


# ======================================
# Helper Functions
# ======================================
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
        return None, None
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
# Threads
# ======================================
def roboeyes_loop(eyes):
    """Keep updating RoboEyes display forever."""
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
        eyes.update()
        clock.tick(60)


def conversation_loop(eyes, arduino):
    """Main emotion + movement loop."""
    while True:
        speak_text("Hi, how are you doing?")
        while True:
            record_audio()
            transcript, emotion, reply = process_audio()
            if not transcript:
                continue

            eyes.setMood(emotion)  # 👀 Change eye expression based on emotion

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
# Main
# ======================================
if __name__ == "__main__":
    try:
        arduino = serial.Serial(PORT, BAUD, timeout=1)
        time.sleep(2)
        print(f"✅ Connected to Arduino on {PORT}")
    except serial.SerialException:
        print(f"❌ Failed to connect to {PORT}")
        sys.exit(1)

    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("EmoBot Eyes")

    eyes = RoboEyes(screen)

    # Start eyes animation in a background thread
    threading.Thread(target=roboeyes_loop, args=(eyes,), daemon=True).start()

    # Start conversation and emotion control
    conversation_loop(eyes, arduino)
