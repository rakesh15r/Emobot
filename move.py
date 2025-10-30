from dronekit import connect, VehicleMode
import time, serial, json, socket, pyttsx3, os
import sounddevice as sd
import soundfile as sf
import numpy as np

# =================== CONFIG ===================
PIXHAWK_PORT = '/dev/ttyACM0'
DDSM_PORT = '/dev/ttyACM1'
SERIAL_BAUDRATE = 115200
BAUDRATE = 57600
SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = 'hw:1,0'
DTYPE = 'int32'
SERVER_IP = '192.168.137.95'   # Change to your server’s IP
SERVER_PORT = 5001
MOVE_DURATION = 5

latest_servo1_value = None
latest_servo3_value = None

# =================== SETUP ===================
ddsm_ser = serial.Serial(DDSM_PORT, baudrate=SERIAL_BAUDRATE)
ddsm_ser.setRTS(False)
ddsm_ser.setDTR(False)
print("[System] DDSM Connected")

# =================== MOTOR CONTROL ===================
def motor_control(left, right):
    global ddsm_ser
    cmd_right = {"T": 10010, "id": 2, "cmd": -right, "act": 3}
    cmd_left  = {"T": 10010, "id": 1, "cmd": left, "act": 3}
    ddsm_ser.write((json.dumps(cmd_right) + '\n').encode())
    time.sleep(0.01)
    ddsm_ser.write((json.dumps(cmd_left) + '\n').encode())

def move_forward_time(seconds):
    print(f"[Move] Moving forward for {seconds} seconds...")
    motor_control(40, 40)
    time.sleep(seconds)
    motor_control(0, 0)
    print("[Move] Stopped.")

# =================== AUDIO ===================
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

# =================== FILE TRANSFER ===================
def send_wav_file(filepath):
    """Send WAV file to server using the tested protocol."""
    if not os.path.exists(filepath):
        print(f"[Error] File not found: {filepath}")
        return ""

    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        print(f"[Socket] Connecting to {SERVER_IP}:{SERVER_PORT} ...")
        s.connect((SERVER_IP, SERVER_PORT))

        # Step 1: Tell server we’re sending a file
        s.sendall(b'FILE')
        s.recv(1024)  # Wait for OK

        # Step 2: Send filename
        s.sendall(filename.encode())
        s.recv(1024)  # Wait for OK

        # Step 3: Send filesize
        s.sendall(str(filesize).encode())
        s.recv(1024)  # Wait for OK

        # Step 4: Send file data
        with open(filepath, 'rb') as f:
            while True:
                data = f.read(4096)
                if not data:
                    break
                s.sendall(data)
        print(f"[Socket] File '{filename}' sent successfully ({filesize} bytes).")

        # Step 5: Wait for transcription
        transcription = s.recv(4096).decode(errors='ignore').strip()
        print(f"[Socket] Received transcription: {transcription}")
        return transcription

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

    # Chat loop
    while True:
        move_forward_time(MOVE_DURATION)
        speak_text("Hi, how are you doing?")
        record_audio("user_voice.wav", duration=4)
        transcription = send_wav_file("user_voice.wav")

        if transcription:
            speak_text(transcription)
        else:
            speak_text("Sorry, I couldn't understand that.")
            continue

        if "thanks" in transcription.lower():
            speak_text("You're welcome! Moving ahead.")
            continue
        else:
            speak_text("Let's continue our chat!")

if __name__ == "__main__":
    main()
