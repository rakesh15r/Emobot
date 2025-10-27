from dronekit import connect, VehicleMode, LocationGlobalRelative
from rplidar import RPLidar
import math
import time
import threading
import serial
import json
import pvporcupine
import sounddevice as sd
import soundfile as sf
import io
import speech_recognition as sr
import webrtcvad
import numpy as np

# =================== CONSTANTS ===================
LIDAR_PORT = '/dev/ttyUSB0'     # Lidar port
PIXHAWK_PORT = '/dev/ttyACM0'   # Pixhawk serial port
DDSM_PORT = '/dev/ttyACM1'
SERIAL_BAUDRATE = 115200
BAUDRATE = 57600
MIN_DISTANCE = 500  # mm (obstacle avoidance threshold)
TARGET_LAT = 17.3973234  # Replace with your target latitude
TARGET_LON = 78.4899548 # Replace with your target longitude
ALTITUDE = 0.0    
WAYPOINT_REACHED_RADIUS = 0.5      # For rovers, altitude is 0
FILE_NAME = "logged_coordinates.txt"
TURN_SPEED = 30
FORWARD_SPEED = 40
WAKE_WORD = "jarvis"
SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = 'hw:1,0'         # Check with `python3 -m sounddevice`
DTYPE = 'float32'         # Jetson I²S mics usually output float32
FRAME_DURATION = 30       # 10, 20, or 30 ms
VAD_SENSITIVITY = 2       # 0–3 (3 = most sensitive)
SILENCE_LIMIT = 1.0       # seconds of silence before stop
SAVE_PATH = "command.wav" # File to overwrite for every command

arrived = False
latest_scan = None  # Global Lidar scan storage
latest_servo1_value = None
latest_servo3_value = None
path = []

ddsm_ser = serial.Serial(DDSM_PORT, baudrate=SERIAL_BAUDRATE)
ddsm_ser.setRTS(False)
ddsm_ser.setDTR(False)
print("[System] DDSM Connected")

# =================== FUNCTIONS ===================

# def input_listener():
#     global arrived
#     while True:
#         user_input = input("Press 'm' to confirm it reached waypoint")
#         if user_input == "m":
#             arrived = True

# =========  Wake word  ==========
# ====== INITIALIZE ======
recognizer = sr.Recognizer()
porcupine = pvporcupine.create(
    access_key="6ZxVPO4M7eURSKhjbfUVBKzCYQHEPEUAvh+zkaFQsUr5mSfkMcrF1w==",
    keywords=["jarvis"]
)
FRAME_LENGTH = porcupine.frame_length
vad = webrtcvad.Vad(VAD_SENSITIVITY)

print(f"🎧 Listening for wake word: '{WAKE_WORD}'... (Frame length: {FRAME_LENGTH})")

# ====== FUNCTION: AUTO GAIN CONTROL ======
def auto_gain(audio_float):
    rms = np.sqrt(np.mean(audio_float ** 2))
    target_rms = 0.1  # target loudness level
    if rms > 0:
        gain = target_rms / rms
        gain = np.clip(gain, 1.0, 4.0)  # prevent overboost
        audio_float *= gain
    return np.clip(audio_float, -1.0, 1.0)

# ====== FUNCTION: RECORD UNTIL SILENCE ======
def record_until_silence():
    print("🎙 Wake word detected! Listening to your speech...")

    frame_size = int(SAMPLE_RATE * FRAME_DURATION / 1000)
    voiced_frames = []
    recording = False
    silence_counter = 0

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        device=DEVICE,
        blocksize=frame_size
    ) as stream:
        while True:
            frame, _ = stream.read(frame_size)

            # Convert safely to int16
            if frame.dtype != np.int16:
                pcm16 = np.int16(np.clip(frame.flatten() * 32767, -32768, 32767))
            else:
                pcm16 = frame.flatten()

            raw_bytes = pcm16.tobytes()
            is_speech = vad.is_speech(raw_bytes, SAMPLE_RATE)

            if is_speech:
                if not recording:
                    recording = True
                voiced_frames.append(raw_bytes)
                silence_counter = 0
            elif recording:
                silence_counter += FRAME_DURATION / 1000
                if silence_counter > SILENCE_LIMIT:
                    break

    pcm_concat = b''.join(voiced_frames)
    if not pcm_concat:
        print("⚠️ No speech detected.")
        return None

    # --- Convert and apply soft gain boost ---
    audio_np_int16 = np.frombuffer(pcm_concat, dtype=np.int16)
    audio_np_float = audio_np_int16.astype(np.float32) / 32767.0
    audio_np_float = auto_gain(audio_np_float)
    audio_np_int16 = np.int16(audio_np_float * 32767)

    # --- Normalize volume before saving ---
    max_val = np.max(np.abs(audio_np_int16))
    if max_val > 0:
        audio_np_int16 = np.int16(audio_np_int16 / max_val * 30000)

    sf.write(SAVE_PATH, audio_np_int16, SAMPLE_RATE, format='WAV', subtype='PCM_16')
    print(f"✅ Saved command to '{SAVE_PATH}' (normalized and gain-adjusted)")

    return audio_np_float

# ====== FUNCTION: SPEECH TO TEXT ======
def audio_to_text(audio_float):
    # Normalize amplitude before STT
    max_val = np.max(np.abs(audio_float))
    if max_val > 0:
        audio_float = audio_float / max_val

    buf = io.BytesIO()
    sf.write(buf, audio_float, SAMPLE_RATE, format='WAV', subtype='PCM_16')
    buf.seek(0)
    with sr.AudioFile(buf) as source:
        audio = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio)
        print(f"💬 You said: {text}")
        return text
    except sr.UnknownValueError:
        print("🤔 Could not understand your speech.")
    except sr.RequestError as e:
        print(f"⚠️ STT request failed: {e}")

def wakeword_main():
    stream = None
    try:
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=FRAME_LENGTH,
            dtype=DTYPE,
            channels=CHANNELS,
            device=DEVICE
        )
        stream.start()

        while True:
            pcm, _ = stream.read(FRAME_LENGTH)

            # Convert float → int16 for Porcupine
            if pcm.dtype != np.int16:
                pcm16 = np.int16(np.clip(pcm.flatten() * 32767, -32768, 32767))
            else:
                pcm16 = pcm.flatten()

            # Normalize quiet audio for better detection
            if np.mean(np.abs(pcm16)) < 1000:
                pcm16 = np.int16(pcm16 * 5)

            keyword_index = porcupine.process(pcm16)

            if keyword_index >= 0:
                print("💡 Wake word detected!")

                # --- Close wakeword stream ---
                stream.close()

                # --- Record user speech ---
                audio_data = record_until_silence()

                # --- Convert to text ---
                if audio_data is not None and len(audio_data) > 0:
                    audio_to_text(audio_data)

                # --- Reopen wakeword stream ---
                print(f"\n🎧 Listening again for wake word: '{WAKE_WORD}'...\n")
                time.sleep(0.2)
                stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    blocksize=FRAME_LENGTH,
                    dtype=DTYPE,
                    channels=CHANNELS,
                    device=DEVICE
                )
                stream.start()

    except KeyboardInterrupt:
        print("\n🛑 Keyboard Interrupt received — releasing microphone...")
    finally:
        if stream is not None:
            try:
                stream.stop()
                stream.close()
                print("🎤 Microphone released successfully.")
            except Exception as e:
                print(f"⚠️ Error while closing stream: {e}")
        porcupine.delete()
        print("✅ Porcupine deleted. Exiting gracefully.")


def read_coordinates_from_file(filename):
    coordinates = []

    try:
        with open(filename, 'r') as file:
            print(file)
            for line in file:
                line = line.replace(" ", "")
                parts = line.strip().split(',')
                if True:
                    try:
                        lat = float(parts[0])
                        lon = float(parts[1])
                        coordinates.append((lat, lon))
                    except ValueError:
                        print(f"Skipping invalid line: {line.strip()}")
    except FileNotFoundError:
        print(f"File not found: {filename}")
    
    coordinates.reverse()
    return coordinates

def get_haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two GPS coordinates in meters"""
    R = 6371000  # Radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def lidar_thread_func(lidar):
    """Lidar scanning in a background thread"""
    global latest_scan
    for scan in lidar.iter_scans():
        latest_scan = scan

def is_front_clear():
    global latest_scan
    scan_data = latest_scan
    for (_, angle, dist) in scan_data:
        if (angle >= 340 or angle <= 20) and dist < MIN_DISTANCE and dist > 0:
            return False
    return True

def is_left_clear():
    global latest_scan
    scan_data = latest_scan
    for (_, angle, dist) in scan_data:
        if (angle >= 270 or angle <= 340) and dist < MIN_DISTANCE+100 and dist > 0:
            return False
    return True

def scale_servo_to_speed(servo_value):
    if servo_value is None:
        return 0
    # Map servo PWM (1000-2000 µs) to speed (-100 to 100)
    return int((servo_value - 1500) / 500 * 100)

# def get_sector_distance(scan_data, min_angle, max_angle):
#     """Get average distance in a sector"""
#     distances = [dist for (_, angle, dist) in scan_data
#                  if min_angle <= angle <= max_angle and dist > 0]
#     if len(distances) == 0:
#         return float('inf')
#     return sum(distances) / len(distances)

# def decide_turn_direction(scan_data):
#     """Decide whether to turn left or right based on clearance"""
#     left_clearance = get_sector_distance(scan_data, 60, 120)    # left sector
#     right_clearance = get_sector_distance(scan_data, 240, 300)  # right sector
#     print(f"[Decision] Left clearance: {left_clearance:.2f} mm, Right clearance: {right_clearance:.2f} mm")
#     return 'left' if left_clearance > right_clearance else 'right'

def avoid_obstacle():   
    """Perform an obstacle avoidance maneuver"""
    motor_control(0,0) # stop 
    time.sleep(0.3)
    while not is_front_clear():
        print("[OBSTACLE DETECTED] Avoiding...")
        motor_control(20,-20) # turn right
        time.sleep(0.5)

    motor_control(20 , 20) # move forward
    time.sleep(1.5)

def follow_obstacle():
    while True:
        if not is_front_clear():
            motor_control(TURN_SPEED, -TURN_SPEED)
            print("[OBSTACLE DETECTED] -> turn right")
        elif not is_left_clear():
            motor_control(FORWARD_SPEED, FORWARD_SPEED)
            print("[OBSTACLE DETECTED] -> move forward")
        else:
            break

def goto_position(vehicle, target_location):
    global  latest_servo1_value, latest_servo3_value, arrived
    print(f"[Navigation] Moving to target: {target_location.lat}, {target_location.lon}")
    vehicle.simple_goto(target_location)

    while True:
        current_location = vehicle.location.global_relative_frame
        dist_to_target = get_haversine_distance(current_location.lat, current_location.lon , target_location.lat, target_location.lon)
        print(f"[Navigation] Distance to target: {dist_to_target:.2f} meters")

        if dist_to_target <= WAYPOINT_REACHED_RADIUS or arrived: # Arrived
            arrived = False
            print("[Navigation] Target Reached!")
            break

        while not is_front_clear():
            print("[Warning] Obstacle detected ahead!")
            motor_control(0,0)
            time.sleep(0.2)
            #follow_obstacle()
            # avoid_obstacle()  # perform avoidance

        servo1 = latest_servo1_value
        servo3 = latest_servo3_value
        speed_left = scale_servo_to_speed(servo1)
        speed_right = scale_servo_to_speed(servo3)
        motor_control(speed_left, speed_right)
        time.sleep(0.1)

def motor_control(left, right):
    global ddsm_ser
    command_right = {
        "T": 10010,
        "id": 2,
        "cmd": -right,  # reverse polarity for right wheel
        "act": 3
    }
    command_left = {
        "T": 10010,
        "id": 1,
        "cmd": left,
        "act": 3
    }
    ddsm_ser.write((json.dumps(command_right) + '\n').encode())
    time.sleep(0.01)
    ddsm_ser.write((json.dumps(command_left) + '\n').encode())

# =================== MAIN ===================

def main():
    global latest_scan, path
    path = read_coordinates_from_file(FILE_NAME)
    print(f"[System] Coordinates {path}")

    print("[System] Starting LIDAR...")
    lidar = RPLidar(LIDAR_PORT)
    threading.Thread(target=lidar_thread_func, args=(lidar,), daemon=True).start()
    threading.Thread(target=wakeword_main, deamon=True).start()
    while True:
        if latest_scan is None:
            print("Waiting for LIDAR data...")
            time.sleep(1)
            continue 
        else:
            print("Lidar started...")
            break

    print("[System] Connecting to Pixhawk...")
    vehicle = connect(PIXHAWK_PORT, baud=BAUDRATE, wait_ready=False)
    print("[System] Connection success...")
    # threading.Thread(target=input_listener, daemon=True).start()


    @vehicle.on_message('SERVO_OUTPUT_RAW')
    def servo_listener(self, name, message):
        global latest_servo1_value, latest_servo3_value
        latest_servo1_value = message.servo1_raw
        latest_servo3_value = message.servo3_raw
        # print(f"[SERVO] Servo1: {latest_servo1_value}, Servo3: {latest_servo3_value}")

    @vehicle.on_message('MISSION_ITEM_REACHED')
    def item_reached(self, name, message):
      global arrived
      arrived = True
      print(f"[MESSAGE]Reached waypoint: {message.seq}")


    print("[System] Arming vehicle...")
    vehicle.armed = True
    while not vehicle.armed:
        print("[System] Waiting for arming...")
        time.sleep(1)
    print("[System] Vehicle Armed.")

    print("[System] Setting GUIDED mode...")
    vehicle.mode = VehicleMode("GUIDED")
    while vehicle.mode.name != "GUIDED":
        print("[System] Waiting for GUIDED mode...")
        time.sleep(1)
    print(f"[System] Vehicle Mode --> {vehicle.mode.name}")

    try:
        for index, x in enumerate(path):
            target_location = LocationGlobalRelative(x[0], x[1], ALTITUDE)
            goto_position(vehicle, target_location)
            print(f"[System] Reached waypoint {index+1} --> {x[0]}, {x[1]}")
            time.sleep(0.5)
        print("[System] Reached destination")
        motor_control(0,0)

    except KeyboardInterrupt:
        print("[System] Stopping test...")
        motor_control(0,0)

    finally:
        vehicle.channels.overrides = {}
        # vehicle.armed = False
        vehicle.close()
        lidar.stop()
        lidar.stop_motor()
        lidar.disconnect()
        ddsm_ser.close()

main()
