import paho.mqtt.client as mqtt

server = "13.232.191.178"
port = 1883
topic = "emobot/screen/command"

def main():
    client = mqtt.Client()
    client.connect(server, port, 60)
    print(f"[MQTT] Connected to {server}:{port}")
    print(f"[MQTT] Publishing to topic: {topic}\n")

    while True:
        try:
            emotion = input("Enter emotion (happy / angry / tired / default / exit): ").strip().lower()
            if emotion == "exit":
                print("👋 Exiting publisher...")
                break
            client.publish(topic, emotion)
            print(f"[MQTT] Sent → '{emotion}'")
        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user. Exiting...")
            break

    client.disconnect()

if __name__ == "__main__":
    main()
