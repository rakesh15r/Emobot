# # =============================
# # Emobot Main Script
# # Voice Command + Emotion + Rover Control (DroneKit)
# # =============================

# import speech_recognition as sr
# import pyttsx3
# from transformers import pipeline
# from dronekit import connect, VehicleMode
# import time

# # -----------------------------
# # Setup Text-to-Speech
# # -----------------------------
# engine = pyttsx3.init()

# def speak(text):
#     print("Emobot:", text)
#     engine.say(text)
#     engine.runAndWait()

# # -----------------------------
# # Speech-to-Text
# # -----------------------------
# def get_command():
#     r = sr.Recognizer()
#     with sr.Microphone() as source:
#         print("\nListening...")
#         audio = r.listen(source)
#     try:
#         command = r.recognize_google(audio)
#         print("You said:", command)
#         return command.lower()
#     except:
#         return ""

# # -----------------------------
# # Emotion Classifier (pretrained until SpeechCueLLM is ready)
# # -----------------------------
# emotion_analyzer = pipeline("text-classification", 
#                             model="j-hartmann/emotion-english-distilroberta-base")

# def get_emotion(text):
#     result = emotion_analyzer(text)[0]
#     return result['label'].lower()   # e.g. anger, joy, sadness, neutral

# # -----------------------------
# # Connect to Rover (DroneKit)
# # -----------------------------
# print("Connecting to rover...")
# # Change this depending on setup: SITL, real rover, etc.
# vehicle = connect('tcp:127.0.0.1:5762', wait_ready=True)

# def arm_rover():
#     print("Arming rover...")
#     vehicle.mode = VehicleMode("GUIDED")
#     vehicle.armed = True
#     while not vehicle.armed:
#         time.sleep(1)
#     print("Rover armed and ready!")

# # -----------------------------
# # Movement Commands
# # -----------------------------
# def send_ned_velocity(x, y, z, duration):
#     """
#     Send velocity commands in NED frame
#     x = forward/backward
#     y = left/right
#     z = up/down (not used for rover)
#     """
#     msg = vehicle.message_factory.set_position_target_local_ned_encode(
#         0, 0, 0,
#         0b0000111111000111,
#         0, 0, 0,
#         x, y, z,
#         0, 0, 0,
#         0, 0
#     )
#     for _ in range(duration):
#         vehicle.send_mavlink(msg)
#         time.sleep(1)

# def rover_move(command, emotion):
#     # Emotion affects speed
#     speed = 1.0
#     if emotion == "anger":
#         speed = 3.0
#     elif emotion == "joy":
#         speed = 2.0
#     elif emotion == "sadness":
#         speed = 0.5

#     if command == "forward":
#         send_ned_velocity(speed, 0, 0, 2)
#         return f"Moving forward at speed {speed}."
#     elif command == "backward":
#         send_ned_velocity(-speed, 0, 0, 2)
#         return f"Moving backward at speed {speed}."
#     elif command == "left":
#         send_ned_velocity(0, -speed, 0, 2)
#         return f"Turning left at speed {speed}."
#     elif command == "right":
#         send_ned_velocity(0, speed, 0, 2)
#         return f"Turning right at speed {speed}."
#     elif command == "stop":
#         send_ned_velocity(0, 0, 0, 1)
#         return "Stopping."
#     else:
#         return "Unknown movement."

# # -----------------------------
# # Generic Dialogue Replies
# # -----------------------------
# def generic_reply(text, emotion):
#     if emotion == "anger":
#         return "I can sense you’re upset."
#     elif emotion == "joy":
#         return "I’m glad you’re happy!"
#     elif emotion == "sadness":
#         return "I’m here with you."
#     else:
#         return f"I heard you say: {text}"

# # -----------------------------
# # Command Detection
# # -----------------------------
# movement_keywords = ["forward", "backward", "left", "right", "stop"]

# def is_movement_command(text):
#     for word in movement_keywords:
#         if word in text:
#             return word
#     return None

# # -----------------------------
# # Main Loop
# # -----------------------------
# if __name__ == "__main__":
#     arm_rover()

#     while True:
#         cmd = get_command()
#         if cmd == "":
#             continue

#         emotion = get_emotion(cmd)
#         print(f"Detected Emotion: {emotion}")

#         move = is_movement_command(cmd)
#         if move:
#             response = rover_move(move, emotion)
#         else:
#             response = generic_reply(cmd, emotion)

#         speak(response)
# =============================
# Emobot + Rover Control with NED Velocity
# =============================

import speech_recognition as sr
import pyttsx3
from transformers import pipeline
from dronekit import connect, VehicleMode
from pymavlink import mavutil
import time

# =====================================================
# 🗣️ TEXT-TO-SPEECH (TTS)
# =====================================================
engine = pyttsx3.init()

def speak(text):
    print("Emobot:", text)
    engine.say(text)
    engine.runAndWait()

# =====================================================
# 🎙️ SPEECH-TO-TEXT (STT)
# =====================================================
def get_command():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("\nListening...")
        r.adjust_for_ambient_noise(source, duration=0.5)
        audio = r.listen(source, phrase_time_limit=5)
    try:
        command = r.recognize_google(audio)
        print("You said:", command)
        return command.lower()
    except (sr.UnknownValueError, sr.RequestError):
        return ""

# =====================================================
# 😃 EMOTION CLASSIFIER
# =====================================================
emotion_analyzer = pipeline("text-classification",
                            model="j-hartmann/emotion-english-distilroberta-base")

def get_emotion(text):
    result = emotion_analyzer(text)[0]
    label = result['label'].lower()
    valid_emotions = ["joy", "anger", "sadness", "neutral"]
    return label if label in valid_emotions else "neutral"

# =====================================================
# 🚗 CONNECT TO PIXHAWK (Rover)
# =====================================================
print("[INFO] Connecting to Pixhawk Rover...")
vehicle = connect('tcp:127.0.0.1:5762', wait_ready=True)

while not vehicle.is_armable:
    print("Waiting for vehicle to initialize...")
    time.sleep(1)

vehicle.mode = VehicleMode("GUIDED")
vehicle.armed = True
while not vehicle.armed:
    print("Arming Pixhawk...")
    time.sleep(1)

print("[INFO] Rover armed and ready in GUIDED mode.")

# =====================================================
# ⚙️ MOVEMENT CONTROL (NED VELOCITY)
# =====================================================
def send_ned_velocity(velocity_x, velocity_y, velocity_z, duration=1):
    msg = vehicle.message_factory.set_position_target_local_ned_encode(
        0, 0, 0,
        mavutil.mavlink.MAV_FRAME_BODY_NED,
        0b0000111111000111,
        0, 0, 0,
        velocity_x, velocity_y, velocity_z,
        0, 0, 0,
        0, 0
    )

    start_time = time.time()
    while time.time() - start_time < duration:
        vehicle.send_mavlink(msg)
        vehicle.flush()
        time.sleep(0.1)  # 10 Hz update rate

def rover_move(command, emotion):
    speed = 0.5
    if emotion == "anger":
        speed = 1.5
    elif emotion == "joy":
        speed = 1.0
    elif emotion == "sadness":
        speed = 0.3

    if command == "forward":
        send_ned_velocity(speed, 0, 0, 2)
        return f"Moving forward at {speed} m/s"

    elif command == "backward":
        send_ned_velocity(-speed, 0, 0, 2)
        return f"Moving backward at {speed} m/s"

    elif command == "left":
        send_ned_velocity(0, -speed, 0, 2)
        return "Turning left"

    elif command == "right":
        send_ned_velocity(0, speed, 0, 2)
        return "Turning right"

    elif command == "stop":
        send_ned_velocity(0, 0, 0, 1)
        return "Stopping."

    else:
        return "Unknown command."

# =====================================================
# 💬 GENERIC REPLIES
# =====================================================
def generic_reply(text, emotion):
    if emotion == "anger":
        return "I sense anger. Responding quickly."
    elif emotion == "joy":
        return "You sound happy. Let's go!"
    elif emotion == "sadness":
        return "I sense sadness. Moving gently."
    else:
        return f"I heard you say: {text}"

# =====================================================
# 🧭 MOVEMENT COMMAND DETECTION (with synonyms)
# =====================================================
command_map = {
    "forward": "forward",
    "move forward": "forward",
    "go forward": "forward",
    "ahead": "forward",
    "backward": "backward",
    "go back": "backward",
    "move back": "backward",
    "reverse": "backward",
    "left": "left",
    "move left": "left",
    "turn left": "left",
    "right": "right",
    "move right": "right",
    "turn right": "right",
    "stop": "stop",
    "halt": "stop"
}

def is_movement_command(text):
    for phrase, action in command_map.items():
        if phrase in text:
            return action
    return None

# =====================================================
# 🧠 MAIN LOOP
# =====================================================
if __name__ == "__main__":
    try:
        while True:
            cmd = get_command()
            if not cmd:
                continue

            emotion = get_emotion(cmd)
            print(f"[INFO] Emotion detected: {emotion}")

            move = is_movement_command(cmd)
            if move:
                response = rover_move(move, emotion)
            else:
                response = generic_reply(cmd, emotion)

            speak(response)

            # Emergency stop
            if "stop" in cmd:
                rover_move("stop", "neutral")
                speak("Stopping immediately.")

    except KeyboardInterrupt:
        print("\n[INFO] Stopping rover and closing connection.")
        send_ned_velocity(0, 0, 0, 1)
        vehicle.close()
