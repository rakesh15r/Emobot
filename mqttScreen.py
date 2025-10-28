import pygame
import time
import random
import threading
import sys
import math
import paho.mqtt.client as mqtt

# ======================================
# RoboEyes (with MQTT Emotion Control)
# ======================================

BLACK = (10, 10, 20)
NEON_CYAN = (0, 255, 255)

DEFAULT, TIRED, ANGRY, HAPPY = 0, 1, 2, 3


class RoboEyes:
    def __init__(self, screen):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.frameInterval = 20
        self.fpsTimer = 0

        # Eye geometry
        self.eyeW = 300
        self.eyeH = 280
        self.space = 130
        self.eyeOpenAmount = 1.0

        # Eye positions
        self.eyeLx = self.w // 2 - self.eyeW - self.space // 2
        self.eyeLy = self.h // 2 - self.eyeH // 2 - 100
        self.eyeRx = self.w // 2 + self.space // 2
        self.eyeRy = self.eyeLy

        # Blinking
        self.blinking = False
        self.blinkStart = 0
        self.blinkDuration = 0.25
        self.lastBlink = 0
        self.blinkInterval = 10

        # Mood
        self.mood = DEFAULT

    def millis(self):
        return time.time() * 1000

    def setMood(self, mood_name: str):
        mood_name = mood_name.lower().strip()
        if mood_name == "tired":
            self.mood = TIRED
        elif mood_name == "angry":
            self.mood = ANGRY
        elif mood_name == "happy":
            self.mood = HAPPY
        else:
            self.mood = DEFAULT
        print(f"👉 Mood set to: {mood_name.upper()}")

    # ------------------------------ BLINK ------------------------------
    def blink(self):
        self.blinking = True
        self.blinkStart = time.time()

    def updateBlink(self):
        self.blinkInterval = 2.25
        now = time.time()
        if now - self.lastBlink > self.blinkInterval and not self.blinking:
            self.blink()
            self.lastBlink = now
            self.blinkInterval = 3 + random.random() * 3

        if self.blinking:
            elapsed = now - self.blinkStart
            if elapsed < self.blinkDuration / 2:
                self.eyeOpenAmount = 1.0 - (elapsed / (self.blinkDuration / 2))
            elif elapsed < self.blinkDuration:
                self.eyeOpenAmount = (elapsed - self.blinkDuration / 2) / (self.blinkDuration / 2)
            else:
                self.eyeOpenAmount = 1.0
                self.blinking = False

    # ------------------------------ GLOW ------------------------------
    def draw_glow(self, surf, draw_func, color, intensity=6, **kwargs):
        for i in range(intensity, 0, -1):
            alpha = 15 * i
            glow_color = (*color, alpha)
            glow_surface = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            draw_func(glow_surface, glow_color, grow=i * 3, **kwargs)
            surf.blit(glow_surface, (0, 0))

    # ------------------------------ SHAPES ------------------------------
    def draw_tired_eye(self, surf, color, grow=0, mirror=False):
        w, h = surf.get_size()
        h_eff = int(h * self.eyeOpenAmount)
        if h_eff < 60:
            return

        x1, x2 = 10 + grow, w - 10 - grow
        y_bottom = h_eff - 10 - grow
        y_top_high = 10 + grow
        y_top_low = 60 + grow
        radius = 40

        if mirror:
            points = [(x1, y_top_high), (x2, y_top_low), (x2, y_bottom - radius), (x1, y_bottom - radius)]
        else:
            points = [(x1, y_top_low), (x2, y_top_high), (x2, y_bottom - radius), (x1, y_bottom - radius)]

        pygame.draw.polygon(surf, color, points)
        pygame.draw.rect(surf, color, (x1, y_bottom - radius, x2 - x1, radius))
        bottom_rect = (x1, y_bottom - radius * 2, x2 - x1, radius * 2)
        pygame.draw.rect(surf, color, bottom_rect,
                         border_bottom_left_radius=radius,
                         border_bottom_right_radius=radius)

    def draw_angry_eye(self, surf, color, grow=0, mirror=False):
        w, h = surf.get_size()
        h_eff = int(h * self.eyeOpenAmount)
        if h_eff < 60:
            return

        x1, x2 = 10 + grow, w - 10 - grow
        y_bottom = h_eff - 10 - grow
        y_top_high = 10 + grow
        y_top_low = 60 + grow
        radius = 40

        if mirror:
            points = [(x1, y_top_low), (x2, y_top_high), (x2, y_bottom - radius), (x1, y_bottom - radius)]
        else:
            points = [(x1, y_top_high), (x2, y_top_low), (x2, y_bottom - radius), (x1, y_bottom - radius)]

        pygame.draw.polygon(surf, color, points)
        pygame.draw.rect(surf, color, (x1, y_bottom - radius, x2 - x1, radius))
        bottom_rect = (x1, y_bottom - radius * 2, x2 - x1, radius * 2)
        pygame.draw.rect(surf, color, bottom_rect,
                         border_bottom_left_radius=radius,
                         border_bottom_right_radius=radius)

    def draw_happy_eye(self, surf, color, grow=0):
        w, h = surf.get_size()
        h_eff = int(h * self.eyeOpenAmount)
        if h_eff < 20:
            return
        rect = pygame.Rect(10 + grow, 10 + grow, w - 20 - grow * 2, (h_eff * 3) - grow * 2)
        pygame.draw.rect(surf, color, rect,
                         border_top_left_radius=80,
                         border_top_right_radius=80,
                         border_bottom_left_radius=80,
                         border_bottom_right_radius=80)
        mask = pygame.Surface((w, h_eff), pygame.SRCALPHA)
        cut_radius = int((w - 20) * 1)
        cut_center_y = h_eff + int(cut_radius * 0.75)
        pygame.draw.circle(mask, (0, 0, 0, 255), (w // 2, cut_center_y), cut_radius)
        surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)

    def draw_default_eye(self, surf, color, grow=0):
        w, h = surf.get_size()
        h_eff = int(h * self.eyeOpenAmount)
        if h_eff < 20:
            return
        rect = pygame.Rect(10 + grow, 10 + grow, w - 20 - grow * 2, h_eff - 20 - grow * 2)
        pygame.draw.rect(surf, color, rect, border_radius=60)

    def draw_eye_shape(self, surface, mood, color, mirror=False):
        h = int(surface.get_height() * self.eyeOpenAmount)
        if h <= 0:
            return
        cropped = pygame.Surface((surface.get_width(), h), pygame.SRCALPHA)
        if mood == TIRED:
            self.draw_glow(cropped, self.draw_tired_eye, color, mirror=mirror)
            self.draw_tired_eye(cropped, color, mirror=mirror)
        elif mood == ANGRY:
            self.draw_glow(cropped, self.draw_angry_eye, color, mirror=mirror)
            self.draw_angry_eye(cropped, color, mirror=mirror)
        elif mood == HAPPY:
            self.draw_glow(cropped, self.draw_happy_eye, color)
            self.draw_happy_eye(cropped, color)
        else:
            self.draw_glow(cropped, self.draw_default_eye, color)
            self.draw_default_eye(cropped, color)
        surface.blit(cropped, (0, 0))

    def drawEyes(self):
        self.screen.fill(BLACK)
        color = NEON_CYAN
        if self.mood == TIRED or self.mood == ANGRY:
            eye_surface_l = pygame.Surface((self.eyeW, self.eyeH), pygame.SRCALPHA)
            self.draw_eye_shape(eye_surface_l, self.mood, color, mirror=False)
            self.screen.blit(eye_surface_l, (self.eyeLx, self.eyeLy))
            eye_surface_r = pygame.Surface((self.eyeW, self.eyeH), pygame.SRCALPHA)
            self.draw_eye_shape(eye_surface_r, self.mood, color, mirror=True)
            self.screen.blit(eye_surface_r, (self.eyeRx, self.eyeRy))
        else:
            eye_surface = pygame.Surface((self.eyeW, self.eyeH), pygame.SRCALPHA)
            self.draw_eye_shape(eye_surface, self.mood, color, mirror=False)
            self.screen.blit(eye_surface, (self.eyeLx, self.eyeLy))
            self.screen.blit(eye_surface, (self.eyeRx, self.eyeRy))
        pygame.display.flip()

    def update(self):
        now = self.millis()
        if now - self.fpsTimer >= self.frameInterval:
            self.updateBlink()
            self.drawEyes()
            self.fpsTimer = now


# ----------------------- MQTT HANDLER -----------------------
class MQTTHandler:
    def __init__(self, eyes, server, port, topic):
        self.eyes = eyes
        self.client = mqtt.Client()
        self.server = server
        self.port = port
        self.topic = topic

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        print(f"[MQTT] Connected with result code {rc}")
        client.subscribe(self.topic)
        print(f"[MQTT] Subscribed to topic: {self.topic}")

    def on_message(self, client, userdata, msg):
        emotion = msg.payload.decode().strip()
        print(f"[MQTT] Received: {emotion}")
        self.eyes.setMood(emotion)

    def start(self):
        threading.Thread(target=self.client.loop_forever, daemon=True).start()
        print("[MQTT] Loop started in background.")
        self.client.connect(self.server, self.port, 60)


# ---------------------------- MAIN ----------------------------
def main():
    pygame.init()
    screen = pygame.display.set_mode((1024, 600))
    pygame.display.set_caption("RoboEyes - MQTT Emotion Controlled")

    eyes = RoboEyes(screen)
    eyes.setMood("default")

    # MQTT Configuration
    server = "13.232.191.178"
    port = 1883
    topic = "emobot/screen/command"

    mqtt_handler = MQTTHandler(eyes, server, port, topic)
    mqtt_handler.start()

    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        eyes.update()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
