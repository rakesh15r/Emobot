from dronekit import connect, VehicleMode, LocationGlobalRelative
from rplidar import RPLidar
import math, time, threading, serial, json, socket, pyttsx3
import sounddevice as sd
import soundfile as sf
import numpy as np

# =================== CONFIG ===================
LIDAR_PORT = '/dev/ttyUSB0'
PIXHAWK_PORT = '/dev/ttyACM0'
DDSM_PORT = '/dev/ttyACM1'
SERIAL_BAUDRATE = 115200
BAUDRATE = 57600
SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = 'hw:1,0'
DTYPE = 'int32'
SERVER_IP = '192.168.1.100'   # Change this to your server’s IP
SERVER_PORT = 6000
WAYPOINT_DISTANCE = 5.0       # meters to move each time

latest_servo1_value = None
latest_servo3_value = None

ddsm_ser = serial.Serial(DDSM_PORT, baudrate=SERIAL_BAUDRATE)
ddsm_ser.setRTS(False)
ddsm_ser.setDTR(False)
print("[System] DDSM Connected")

# =================== BASIC FUNCTIONS ===================

def get_haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = map(math.radians, [lat1, lat2])
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def scale_servo_to_speed(servo_value):
    if servo_value is None:
        return 0
    return int((servo_value - 1500) / 500 * 100)

def motor_control(left, right):
    global ddsm_ser
    command_right = {"T": 10010, "id": 2, "cmd": -right, "act": 3}
    command_left  = {"T": 10010, "id": 1, "cmd": left, "act": 3}
    ddsm_ser.write((json.dumps(command_right) + '\n').encode())
    time.sleep(0.01)
    ddsm_ser.write((json.dumps(command_left) + '\n').encode())

# =================== AUDIO FUNCTIONS ===================

def record_audio(filename, duration=3):
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

def send_audio_to_server(filename):
    """Send WAV file to server and get transcription"""
    print(f"[Socket] Connecting to {SERVER_IP}:{SERVER_PORT}")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((SERVER_IP, SERVER_PORT))

    # Send filename length and file size
    with open(filename, 'rb') as f:
        data = f.read()
    filesize = len(data)
    s.sendall(str(filesize).encode() + b'\n')
    s.sendall(data)
    print("[Socket] File sent. Waiting for transcription...")

    # Receive transcription
    transcription = s.recv(1024).decode().strip()
    print(f"[Socket] Received transcription: {transcription}")
    s.close()
    return transcription

# =================== MOVEMENT ===================

def move_forward_distance(vehicle, distance_m):
    """Moves rover by approximate distance (based on GPS)"""
    start = vehicle.location.global_relative_frame
    print(f"[Move] Starting from: {start.lat}, {start.lon}")
    motor_control(40, 40)

    while True:
        current = vehicle.location.global_relative_frame
        dist = get_haversine_distance(start.lat, start.lon, current.lat, current.lon)
        print(f"[Move] Distance traveled: {dist:.2f} m")
        if dist >= distance_m:
            motor_control(0, 0)
            print("[Move] Reached 5 meters.")
            break
        time.sleep(0.5)

# =================== MAIN ===================

def main():
    print("[System] Connecting to Pixhawk...")
    vehicle = connect(PIXHAWK_PORT, baud=BAUDRATE, wait_ready=False)
    print("[System] Connected to Pixhawk")

    @vehicle.on_message('SERVO_OUTPUT_RAW')
    def servo_listener(self, name, message):
        global latest_servo1_value, latest_servo3_value
        latest_servo1_value = message.servo1_raw
        latest_servo3_value = message.servo3_raw

    vehicle.armed = True
    while not vehicle.armed:
        print("Arming...")
        time.sleep(1)

    vehicle.mode = VehicleMode("GUIDED")
    while vehicle.mode.name != "GUIDED":
        print("Setting GUIDED mode...")
        time.sleep(1)
    print("[System] Vehicle Ready")

    while True:
        move_forward_distance(vehicle, WAYPOINT_DISTANCE)

        # Rover speaks
        speak_text("Hi, how are you doing")

        # Record voice from user
        record_audio("user_voice.wav", duration=4)

        # Send audio to server and get text
        transcription = send_audio_to_server("user_voice.wav")

        # Speak it back
        speak_text(transcription)

        # If user said thanks, move again
        if "thanks" in transcription.lower():
            speak_text("You're welcome! Moving ahead.")
            continue
        else:
            speak_text("Let's continue our chat!")

main()
