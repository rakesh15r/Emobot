from dronekit import connect, VehicleMode
import time, serial, json, pyttsx3, os
import sounddevice as sd
import soundfile as sf
import numpy as np
import paho.mqtt.client as mqtt
import base64

# =================== CONFIG ===================
PIXHAWK_PORT = '/dev/ttyACM0'
DDSM_PORT = '/dev/ttyACM1'
SERIAL_BAUDRATE = 115200
BAUDRATE = 57600
SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = 'hw:1,0'
DTYPE = 'int32'
MOVE_DURATION = 5

BROKER = "13.232.191.178"
PORT = 1883
TOPIC_SEND = "emobot/rover/command"
TOPIC_REPLY = "emobot/rover/reply"

latest_servo1_value = None
latest_servo3_value = None
received_reply = None  # Store latest reply from MQTT

# =================== MQTT SETUP ===================
def on_connect(client, userdata, flags, rc):
    print("[MQTT] Connected to broker.")
    client.subscribe(TOPIC_REPLY)

def on_message(client, userdata, msg):
    global received_reply
    try:
        data = json.loads(msg.payload.decode())
        emotion = data.get("emotion", "unknown")
        reply = data.get("reply", "")
        print(f"[MQTT] Emotion: {emotion}")
        print(f"[MQTT] Reply: {reply}")
        received_reply = reply
    except Exception as e:
        print("[MQTT] Error parsing message:", e)

mqtt_client = mqtt.Client("Client1_Rover")
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(BROKER, PORT, 60)
mqtt_client.loop_start()

# =================== SERIAL SETUP ===================
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

# =================== FILE SEND VIA MQTT ===================
def send_audio_file(filepath):
    if not os.path.exists(filepath):
        print("[Audio] File not found:", filepath)
        return
    with open(filepath, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    mqtt_client.publish(TOPIC_SEND, encoded)
    print("[MQTT] Sent audio file to Client-2")

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
        send_audio_file("user_voice.wav")

        print("[System] Waiting for response from Client-2...")
        start_time = time.time()
        global received_reply
        received_reply = None

        while received_reply is None:
            if time.time() - start_time > 30:
                print("[System] Timeout waiting for reply.")
                break
            time.sleep(1)

        if not received_reply:
            speak_text("Sorry, I couldn't understand that.")
            continue

        speak_text(received_reply)

        if "stop" in received_reply.lower():
            speak_text("Okay, stopping the conversation.")
            mqtt_client.publish(TOPIC_SEND, "stop")
            break

        if "thanks" in received_reply.lower():
            speak_text("You're welcome! Moving ahead.")
        else:
            speak_text("Let's continue our chat!")

if __name__ == "__main__":
    main()
