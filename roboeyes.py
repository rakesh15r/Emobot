import pygame
import time
import random
import threading
import sys
import math

# ======================================
# RoboEyes (Exact Shape-Matched Version)
# Matches uploaded reference shapes visually
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
        self.eyeW = 200
        self.eyeH = 180
        self.space = 130
        self.eyeOpenAmount = 1.0

        # Eye positions
        self.eyeLx = self.w // 2 - self.eyeW - self.space // 2
        self.eyeLy = self.h // 2 - self.eyeH // 2
        self.eyeRx = self.w // 2 + self.space // 2
        self.eyeRy = self.eyeLy

        # Blinking
        self.blinking = False
        self.blinkStart = 0
        self.blinkDuration = 0.25
        self.lastBlink = 0
        self.blinkInterval = 3 + random.random() * 3

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
    def draw_glow(self, surf, draw_func, color, intensity=6):
        for i in range(intensity, 0, -1):
            alpha = 15 * i
            glow_color = (*color, alpha)
            glow_surface = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            draw_func(glow_surface, glow_color, grow=i * 3)
            surf.blit(glow_surface, (0, 0))

    # ------------------------------ SHAPES ------------------------------
    def draw_tired_eye(self, surf, color, grow=0):
        """Teardrop shape (upper-left diagonal cut)"""
        w, h = surf.get_size()
        h = int(h * self.eyeOpenAmount)
        points = [
            (10 + grow, 40 + grow),
            (w - 20 - grow, 10 + grow),
            (w - 20 - grow, h - 10 - grow),
            (10 + grow, h - 10 - grow),
        ]
        pygame.draw.polygon(surf, color, points, 0)
        pygame.draw.arc(surf, color, (0, 0, w, h), math.pi, math.pi * 2, 5)

    def draw_angry_eye(self, surf, color, grow=0):
        """V-shaped inward top edges"""
        w, h = surf.get_size()
        h = int(h * self.eyeOpenAmount)
        points = [
            (10 + grow, 20 + grow),
            (w // 2, 40 + grow),
            (w - 10 - grow, 20 + grow),
            (w - 10 - grow, h - 10 - grow),
            (10 + grow, h - 10 - grow),
        ]
        pygame.draw.polygon(surf, color, points, 0)

    def draw_happy_eye(self, surf, color, grow=0):
        """Flat top, smiling bottom cut"""
        w, h = surf.get_size()
        h = int(h * self.eyeOpenAmount)
        base_rect = pygame.Rect(10 + grow, 10 + grow, w - 20 - grow * 2, h - 20 - grow * 2)
        pygame.draw.rect(surf, color, base_rect, border_radius=60)

        # Carve out upward curve (smile)
        mask = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        pygame.draw.circle(mask, BLACK, (w // 2, h - 20), w // 2, 0)
        surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)

    def draw_default_eye(self, surf, color, grow=0):
        """Simple rounded rectangle"""
        w, h = surf.get_size()
        h = int(h * self.eyeOpenAmount)
        rect = pygame.Rect(10 + grow, 10 + grow, w - 20 - grow * 2, h - 20 - grow * 2)
        pygame.draw.rect(surf, color, rect, border_radius=60)

    # ------------------------------ MAIN DRAW ------------------------------
    def draw_eye_shape(self, surface, mood, color):
        h = int(surface.get_height() * self.eyeOpenAmount)
        cropped = pygame.Surface((surface.get_width(), h), pygame.SRCALPHA)

        if mood == TIRED:
            self.draw_glow(cropped, self.draw_tired_eye, color)
            self.draw_tired_eye(cropped, color)
        elif mood == ANGRY:
            self.draw_glow(cropped, self.draw_angry_eye, color)
            self.draw_angry_eye(cropped, color)
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

        for (x, y) in [(self.eyeLx, self.eyeLy), (self.eyeRx, self.eyeRy)]:
            eye_surface = pygame.Surface((self.eyeW, self.eyeH), pygame.SRCALPHA)
            self.draw_eye_shape(eye_surface, self.mood, color)
            self.screen.blit(eye_surface, (x, y))

        pygame.display.flip()

    def update(self):
        now = self.millis()
        if now - self.fpsTimer >= self.frameInterval:
            self.updateBlink()
            self.drawEyes()
            self.fpsTimer = now


# CLI Thread
def cli_input(eyes):
    while True:
        try:
            mood = input("\nEnter mood (tired / angry / happy / default): ").strip()
            eyes.setMood(mood)
        except KeyboardInterrupt:
            print("\nExiting...")
            pygame.quit()
            sys.exit()


# MAIN
def main():
    pygame.init()
    screen = pygame.display.set_mode((1024, 600))
    pygame.display.set_caption("RoboEyes - Shape-Matched Reference Version")

    eyes = RoboEyes(screen)
    eyes.setMood("default")

    threading.Thread(target=cli_input, args=(eyes,), daemon=True).start()

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
