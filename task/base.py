# import speech_recognition as sr
# import pyttsx3
# from transformers import pipeline
# from dronekit import connect, VehicleMode
# from pymavlink import mavutil
# import time

# # =====================================================
# # 🗣️ TEXT-TO-SPEECH (TTS)
# # =====================================================
# engine = pyttsx3.init()
# def speak(text):
#     print("Emobot:", text)
#     engine.say(text)
#     engine.runAndWait()

# # =====================================================
# # 🎙️ SPEECH-TO-TEXT (STT)
# # =====================================================
# def get_command():
#     r = sr.Recognizer()
#     with sr.Microphone() as source:
#         print("\nListening...")
#         r.adjust_for_ambient_noise(source, duration=0.5)
#         audio = r.listen(source, phrase_time_limit=5)
#     try:
#         command = r.recognize_google(audio)
#         print("You said:", command)
#         return command.lower()
#     except sr.UnknownValueError:
#         return ""
#     except sr.RequestError:
#         return ""

# # =====================================================
# # 😃 EMOTION CLASSIFIER (TEXT-BASED)
# # =====================================================
# emotion_analyzer = pipeline("text-classification", 
#                             model="j-hartmann/emotion-english-distilroberta-base")

# def get_emotion(text):
#     result = emotion_analyzer(text)[0]
#     label = result['label'].lower()
#     valid_emotions = ["joy", "anger", "sadness", "neutral"]
#     if label not in valid_emotions:
#         label = "neutral"
#     return label

# # =====================================================
# # 🚗 CONNECT TO PIXHAWK (Rover)
# # =====================================================
# print("[INFO] Connecting to Pixhawk Rover...")
# vehicle = connect('tcp:127.0.0.1:5762', wait_ready=True)  # replace with your telemetry port if needed

# while not vehicle.is_armable:
#     print("Waiting for vehicle to initialize...")
#     time.sleep(1)

# vehicle.mode = VehicleMode("GUIDED")
# vehicle.armed = True
# while not vehicle.armed:
#     print("Arming Pixhawk...")
#     time.sleep(1)

# print("[INFO] Rover armed and ready in GUIDED mode.")

# # =====================================================
# # ⚙️ MOVEMENT CONTROL USING NED VELOCITY (BODY FRAME)
# # =====================================================
# def send_ned_velocity(velocity_x, velocity_y, velocity_z, duration=1):
#     """
#     Send velocity commands in BODY_NED frame (relative to rover's heading)
#     velocity_x: forward/backward (m/s)
#     velocity_y: left/right (m/s)
#     velocity_z: up/down (not used for rover)
#     duration: seconds to send this command
#     """
#     msg = vehicle.message_factory.set_position_target_local_ned_encode(
#         0, 0, 0,
#         mavutil.mavlink.MAV_FRAME_BODY_NED,  # relative to rover's orientation
#         0b0000111111000111,  # enable velocity only
#         0, 0, 0,              # position (unused)
#         velocity_x, velocity_y, velocity_z,  # velocities in m/s
#         0, 0, 0,              # acceleration (unused)
#         0, 0                  # yaw, yaw_rate
#     )
#     for _ in range(duration):
#         vehicle.send_mavlink(msg)
#         vehicle.flush()
#         time.sleep(1)

# def rover_move(command, emotion):
#     """
#     Convert emotion + voice command into movement.
#     Emotion controls speed (m/s)
#     """
#     # Emotion-based velocity scaling
#     speed = 0.5
#     if emotion == "anger":
#         speed = 1.5
#     elif emotion == "joy":
#         speed = 1.0
#     elif emotion == "sadness":
#         speed = 0.3

#     if command == "forward":
#         send_ned_velocity(speed, 0, 0, 2)
#         return f"Moving forward at {speed} m/s"

#     elif command == "backward":
#         send_ned_velocity(-speed, 0, 0, 2)
#         return f"Moving backward at {speed} m/s"

#     elif command == "left":
#         send_ned_velocity(0, -speed, 0, 2)
#         return "Turning left"

#     elif command == "right":
#         send_ned_velocity(0, speed, 0, 2)
#         return "Turning right"

#     elif command == "stop":
#         send_ned_velocity(0, 0, 0, 1)
#         return "Stopping."

#     else:
#         return "Unknown command."

# # =====================================================
# #  GENERIC REPLIES
# # =====================================================
# def generic_reply(text, emotion):
#     if emotion == "anger":
#         return f"I sense anger. Responding quickly."
#     elif emotion == "joy":
#         return f"You sound happy. Let's go!"
#     elif emotion == "sadness":
#         return f"I sense sadness. Moving gently."
#     else:
#         return f"I heard you say: {text}"

# # =====================================================
# # 🧭 MOVEMENT COMMAND DETECTION
# # =====================================================
# movement_keywords = ["forward", "backward", "left", "right", "stop"]

# def is_movement_command(text):
#     for word in movement_keywords:
#         if word in text:
#             return word
#     return None

# # =====================================================
# # 🧠 MAIN LOOP
# # =====================================================
# if __name__ == "__main__":
#     try:
#         while True:
#             cmd = get_command()
#             if cmd == "":
#                 continue

#             # Detect emotion
#             emotion = get_emotion(cmd)
#             print(f"[INFO] Emotion detected: {emotion}")

#             # Detect movement
#             move = is_movement_command(cmd)
#             if move:
#                 response = rover_move(move, emotion)
#             else:
#                 response = generic_reply(cmd, emotion)

#             # Speak the response
#             speak(response)

#             # Emergency stop
#             if "stop" in cmd:
#                 rover_move("stop", "neutral")
#                 speak("Stopping immediately.")
#                 continue

#     except KeyboardInterrupt:
#         print("\n[INFO] Stopping rover and closing connection.")
#         send_ned_velocity(0, 0, 0, 1)
#         vehicle.close()

import speech_recognition as sr
import pyttsx3
import threading
from transformers import pipeline
from dronekit import connect, VehicleMode
from pymavlink import mavutil
import time


def speak(text):
    def _speak_thread(text):
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        engine.stop()

    print("Emobot:", text)
    # Launch a separate thread for each TTS call
    threading.Thread(target=_speak_thread, args=(text,), daemon=True).start()


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


emotion_analyzer = pipeline("text-classification",
                            model="j-hartmann/emotion-english-distilroberta-base")

def get_emotion(text):
    result = emotion_analyzer(text)[0]
    label = result['label'].lower()
    valid_emotions = ["joy", "anger", "sadness", "neutral"]
    return label if label in valid_emotions else "neutral"


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
        time.sleep(0.1)

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

def generic_reply(text, emotion):
    if emotion == "anger":
        return "I sense anger. Responding quickly."
    elif emotion == "joy":
        return "You sound happy. Let's go!"
    elif emotion == "sadness":
        return "I sense sadness. Moving gently."
    else:
        return f"I heard you say: {text}"


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

            if "stop" in cmd:
                rover_move("stop", "neutral")
                speak("Stopping immediately.")

    except KeyboardInterrupt:
        print("\n[INFO] Stopping rover and closing connection.")
        send_ned_velocity(0, 0, 0, 1)
        vehicle.close()
