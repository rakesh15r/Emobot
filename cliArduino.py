import serial
import time
import json

# =====================================
# Serial Connection Setup
# =====================================
PORT = "com22"   # Arduino serial port on Jetson Nano
BAUD = 115200            # Must match Arduino Serial.begin()

try:
    arduino = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)  # Allow Arduino to reset
    print(f"✅ Connected to Arduino on {PORT}")
except serial.SerialException:
    print(f"❌ Failed to connect to {PORT}. Check USB cable or permissions.")
    exit()

# =====================================
# Helper function to send JSON command
# =====================================
def send_command(cmd_dict):
    """Send a JSON command to Arduino."""
    json_str = json.dumps(cmd_dict)
    arduino.write((json_str + "\n").encode())  # newline signals end of command
    time.sleep(0.05)

    # Read any Arduino response
    while arduino.in_waiting:
        response = arduino.readline().decode().strip()
        if response:
            print(f"🔁 Arduino: {response}")

# =====================================
# CLI Control Loop
# =====================================
print("\n=== Arduino Motor Control ===")
print("Enter one of the following commands:")
print(" forward  → Move both wheels forward")
print(" backward → Move both wheels backward")
print(" left     → Turn left")
print(" right    → Turn right")
print(" stop     → Stop both wheels")
print(" custom   → Enter full JSON manually")
print(" exit     → Quit the program\n")

# Default parameters
DEFAULT_SPEED = 20
DEFAULT_STEPS = 2000

while True:
    cmd = input("Command> ").strip().lower()

    if cmd == "exit":
        print("👋 Exiting...")
        break

    # ==============================
    # Predefined Commands
    # ==============================
    if cmd == "forward":
        command = {
            "left":  {"direction": "forward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
            "right": {"direction": "forward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}
        }

    elif cmd == "backward":
        command = {
            "left":  {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
            "right": {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}
        }

    elif cmd == "left":
        command = {
            "left":  {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
            "right": {"direction": "forward",  "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}
        }

    elif cmd == "right":
        command = {
            "left":  {"direction": "forward",  "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
            "right": {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}
        }

    elif cmd == "stop":
        command = {
            "left":  {"direction": "stop", "steps": 0, "speed": 0},
            "right": {"direction": "stop", "steps": 0, "speed": 0}
        }

    elif cmd == "custom":
        print("Enter full JSON command:")
        raw = input("> ").strip()
        try:
            command = json.loads(raw)
        except json.JSONDecodeError:
            print("❌ Invalid JSON format. Try again.")
            continue

    else:
        print("❌ Unknown command. Try again.")
        continue

    # ==============================
    # Send to Arduino
    # ==============================
    send_command(command)

# =====================================
# Cleanup
# =====================================
arduino.close()
