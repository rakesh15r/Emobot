import serial
import time
import json

# =====================================
# Serial Connection Setup
# =====================================
PORT = "com22"        # Change to your Arduino port
BAUD = 115200         # Must match Arduino Serial.begin()

try:
    arduino = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)  # Wait for Arduino reset
    print(f"✅ Connected to Arduino on {PORT}")
except serial.SerialException:
    print(f"❌ Failed to connect to {PORT}. Check USB cable or port.")
    exit()


# =====================================
# Helper function to send JSON commands
# =====================================
def send_command(cmd_dict):
    json_str = json.dumps(cmd_dict)
    arduino.write((json_str + "\n").encode())
    time.sleep(0.05)

    # Read Arduino feedback
    while arduino.in_waiting:
        line = arduino.readline().decode().strip()
        if line:
            print(f"🔁 Arduino: {line}")


# =====================================
# CLI Control Instructions
# =====================================
print("\n=== Arduino Motor Control CLI ===")
print("Commands:")
print(" forward  → Move both wheels forward")
print(" backward → Move both wheels backward")
print(" left     → Turn left")
print(" right    → Turn right")
print(" stop     → Stop both motors")
print(" custom   → Enter custom JSON")
print(" exit     → Quit program\n")

# Default drive params
DEFAULT_SPEED = 80       # PWM (0–255)
DEFAULT_STEPS = 2000     # Number of hall pulses


# =====================================
# CLI Loop
# =====================================
while True:

    command_input = input("Command> ").strip().lower()

    if command_input == "exit":
        print("👋 Exiting...")
        break

    # ==============================
    # Predefined Commands
    # ==============================
    if command_input == "forward":
        command = {
            "left":  {"direction": "forward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
            "right": {"direction": "forward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}
        }

    elif command_input == "backward":
        command = {
            "left":  {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
            "right": {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}
        }

    elif command_input == "left":
        command = {
            "left":  {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
            "right": {"direction": "forward",  "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}
        }

    elif command_input == "right":
        command = {
            "left":  {"direction": "forward",  "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED},
            "right": {"direction": "backward", "steps": DEFAULT_STEPS, "speed": DEFAULT_SPEED}
        }

    elif command_input == "stop":
        command = {
            "left":  {"direction": "stop", "steps": 0, "speed": 0},
            "right": {"direction": "stop", "steps": 0, "speed": 0}
        }

    elif command_input == "custom":
        print("Enter custom JSON:")
        raw = input("> ").strip()
        try:
            command = json.loads(raw)
        except json.JSONDecodeError:
            print("❌ Invalid JSON. Try again.")
            continue

    else:
        print("❌ Unknown command.")
        continue

    # ==============================
    # Send JSON to Arduino
    # ==============================
    send_command(command)

# =====================================
# Cleanup
# =====================================
arduino.close()
