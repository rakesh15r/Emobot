import pygame, sys, time, random, paho.mqtt.client as mqtt
from roboeye import RoboEyes

BROKER_HOST = "localhost"   # same as in main
TOPIC = "roboeyes/emotion"

def on_message(client, userdata, msg):
    mood = msg.payload.decode()
    print(f"👁️ Emotion Received → {mood}")
    userdata['eyes'].setMood(mood)

def main():
    pygame.init()
    screen = pygame.display.set_mode((1024, 600), pygame.FULLSCREEN)
    eyes = RoboEyes(screen)
    eyes.setMood("default")

    userdata = {'eyes': eyes}

    client = mqtt.Client(userdata=userdata)
    client.on_message = on_message
    client.connect(BROKER_HOST, 1883, 60)
    client.subscribe(TOPIC)
    client.loop_start()

    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        eyes.update()
        clock.tick(60)

if __name__ == "__main__":
    main()
