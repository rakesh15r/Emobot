import speech_recognition as sr
import pyttsx3
from transformers import pipeline
from dronekit import connect, VehicleMode
from pymavlink import mavutil
import time

# -----------------------------
# TTS
# -----------------------------
def speak(text):
    print("Emobot:", text)
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()
    engine.stop()   # prevent blocking on next iteration

# -----------------------------
# STT (continuous)
# -----------------------------
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
    except sr.UnknownValueError:
        return ""
    except sr.RequestError:
        return ""

# -----------------------------
# Emotion classifier
# -----------------------------
emotion_analyzer = pipeline("text-classification", model="j-hartmann/emotion-english-distilroberta-base")
def get_emotion(text):
    result = emotion_analyzer(text)[0]
    return result['label'].lower()

# -----------------------------
# Connect to SITL Rover
# -----------------------------
print("[INFO] Connecting to SITL Rover...")
vehicle = connect('tcp:127.0.0.1:5762', wait_ready=True)

while not vehicle.is_armable:
    print("Waiting for vehicle to initialize...")
    time.sleep(1)

vehicle.mode = VehicleMode("GUIDED")
vehicle.armed = True

while not vehicle.armed:
    print("Arming...")
    time.sleep(1)

print("[INFO] Rover armed and ready.")

# -----------------------------
# Movement using velocity commands
# -----------------------------
def send_velocity(x, y, z, duration=2):
    """
    Send velocity command for given duration (in seconds).
    """
    msg = vehicle.message_factory.set_position_target_local_ned_encode(
        0, 0, 0,
        mavutil.mavlink.MAV_FRAME_BODY_NED,
        0b0000111111000111,
        0, 0, 0,
        x, y, z,
        0, 0, 0,
        0, 0
    )
    for _ in range(duration * 5):  # send at 5Hz
        vehicle.send_mavlink(msg)
        vehicle.flush()
        time.sleep(0.2)

def rover_move(command, emotion):
    # emotion-based speed scaling
    if emotion == "anger":
        speed = 1.5
    elif emotion == "joy":
        speed = 1.0
    elif emotion == "sadness":
        speed = 0.5
    else:
        speed = 0.8

    if command == "forward":
        send_velocity(speed, 0, 0)
        return f"Moving forward with speed {speed}"
    elif command == "backward":
        send_velocity(-speed, 0, 0)
        return f"Moving backward with speed {speed}"
    elif command == "left":
        send_velocity(0, -speed, 0)
        return "Turning left"
    elif command == "right":
        send_velocity(0, speed, 0)
        return "Turning right"
    elif command == "stop":
        send_velocity(0, 0, 0)
        return "Stopping"
    else:
        return "Unknown command."

# -----------------------------
# Generic Replies
# -----------------------------
def generic_reply(text, emotion):
    if emotion == "anger":
        return "I sense some anger in your voice."
    elif emotion == "joy":
        return "Glad you’re feeling happy!"
    elif emotion == "sadness":
        return "I’m here for you."
    else:
        return f"I heard you say: {text}"

# -----------------------------
# Movement Keywords
# -----------------------------
movement_keywords = ["forward", "backward", "left", "right", "stop"]
def is_movement_command(text):
    for word in movement_keywords:
        if word in text:
            return word
    return None

# -----------------------------
# Main Loop
# -----------------------------
if _name_ == "_main_":
    while True:
        cmd = get_command()
        if cmd == "":
            continue

        emotion = get_emotion(cmd)
        print(f"[INFO] Emotion detected: {emotion}")

        move = is_movement_command(cmd)
        if move:
            response = rover_move(move, emotion)
        else:
            response = generic_reply(cmd, emotion)

        speak(response)