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
        self.blinkInterval = 1.5
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
        """Helper to draw the glow effect, now passes mirror flag"""
        for i in range(intensity, 0, -1):
            alpha = 15 * i
            glow_color = (*color, alpha)
            glow_surface = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            # Pass 'mirror' kwarg to the drawing function
            draw_func(glow_surface, glow_color, grow=i * 3, **kwargs)
            surf.blit(glow_surface, (0, 0))

    # ------------------------------ SHAPES (NEW) ------------------------------

    # --- MAPPING SWAPPED: This is now TIRED (Inward "V") ---
    def draw_tired_eye(self, surf, color, grow=0, mirror=False):
        """
        Shape 1 (Tired): Inward "V" (slopes down towards the inside)
        - Left Eye (mirror=False): Low-left, High-right
        - Right Eye (mirror=True): High-left, Low-right
        """
        w, h = surf.get_size()
        h_eff = int(h * self.eyeOpenAmount)
        if h_eff < 60: return

        x1, x2 = 10 + grow, w - 10 - grow
        y_bottom = h_eff - 10 - grow
        y_top_high = 10 + grow
        y_top_low = 60 + grow
        radius = 40

        if mirror:
            # Right Eye: high on left (inner), low on right (outer)
            points = [(x1, y_top_high), (x2, y_top_low), (x2, y_bottom - radius), (x1, y_bottom - radius)]
        else:
            # Left Eye: low on left (outer), high on right (inner)
            points = [(x1, y_top_low), (x2, y_top_high), (x2, y_bottom - radius), (x1, y_bottom - radius)]

        # Draw the main sloped top
        pygame.draw.polygon(surf, color, points)
        
        # Draw a rect to fill the space above the rounded corners
        pygame.draw.rect(surf, color, (x1, y_bottom - radius, x2 - x1, radius))

        # Draw the rounded bottom
        bottom_rect = (x1, y_bottom - radius * 2, x2 - x1, radius * 2)
        pygame.draw.rect(surf, color, bottom_rect, 
                         border_bottom_left_radius=radius, 
                         border_bottom_right_radius=radius)

    # --- MAPPING SWAPPED: This is now ANGRY (Outward Droop) ---
    def draw_angry_eye(self, surf, color, grow=0, mirror=False):
        """
        Shape 2 (Angry): Outward droop (slopes down towards the outside)
        - Left Eye (mirror=False): High-left, Low-right
        - Right Eye (mirror=True): Low-left, High-right
        """
        w, h = surf.get_size()
        h_eff = int(h * self.eyeOpenAmount)
        if h_eff < 60: return  # Need some height for the slant

        x1, x2 = 10 + grow, w - 10 - grow
        y_bottom = h_eff - 10 - grow
        y_top_high = 10 + grow
        y_top_low = 60 + grow  # How much to droop
        radius = 40  # Bottom corner radius

        if mirror:
            # Right Eye: low on left (inner), high on right (outer)
            points = [(x1, y_top_low), (x2, y_top_high), (x2, y_bottom - radius), (x1, y_bottom - radius)]
        else:
            # Left Eye: high on left (outer), low on right (inner)
            points = [(x1, y_top_high), (x2, y_top_low), (x2, y_bottom - radius), (x1, y_bottom - radius)]

        # Draw the main sloped top
        pygame.draw.polygon(surf, color, points)
        
        # Draw a rect to fill the space above the rounded corners
        pygame.draw.rect(surf, color, (x1, y_bottom - radius, x2 - x1, radius))

        # Draw the rounded bottom
        bottom_rect = (x1, y_bottom - radius * 2, x2 - x1, radius * 2)
        pygame.draw.rect(surf, color, bottom_rect, 
                         border_bottom_left_radius=radius, 
                         border_bottom_right_radius=radius)

    # --- SHAPE IMPROVED: This is now HAPPY (Smile Cutout) ---
    def draw_happy_eye(self, surf, color, grow=0):
        """
        Shape 3 (Happy): Rounded rect with a "smile" cut from the bottom.
        This is symmetrical, so no mirror flag is needed.
        """
        w, h = surf.get_size()
        h_eff = int(h * self.eyeOpenAmount)
        if h_eff < 20: return

        # 1. Draw the base shape (flat top, rounded bottom corners)
        rect = pygame.Rect(10 + grow, 10 + grow, w - 20 - grow * 2, (h_eff * 3) - grow * 2)
        # --- FIX: Use individual border radii for a flatter top ---
        pygame.draw.rect(surf, color, rect, 
                         border_top_left_radius=80, 
                         border_top_right_radius=80, 
                         border_bottom_left_radius=80, 
                         border_bottom_right_radius=80)

        # 2. Create a transparent mask for the cutout
        # We must use the effective height (h_eff) for the mask surface
        mask = pygame.Surface((w, h_eff), pygame.SRCALPHA)
        
        # 3. Draw the cutout shape (a circle) onto the mask
        # We want the circle to cut from the bottom, so its center should be *below* the eye
        cut_radius = int((w - 20) * 1) # A large radius
        # --- ADJUSTMENT: Make smile cut less deep to "increase length" ---
        # Was 0.65, a higher number moves the circle down, cutting less.
        cut_center_y = h_eff + int(cut_radius * 0.75) 
        
        pygame.draw.circle(mask, (0, 0, 0, 255), (w // 2, cut_center_y), cut_radius)

        # 4. Blit the mask using subtraction
        surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)

    def draw_default_eye(self, surf, color, grow=0):
        """Simple rounded rectangle (Unchanged)"""
        w, h = surf.get_size()
        h_eff = int(h * self.eyeOpenAmount)
        if h_eff < 20: return
        
        rect = pygame.Rect(10 + grow, 10 + grow, w - 20 - grow * 2, h_eff - 20 - grow * 2)
        pygame.draw.rect(surf, color, rect, border_radius=60)

    # ------------------------------ MAIN DRAW (UPDATED) ------------------------------
    def draw_eye_shape(self, surface, mood, color, mirror=False):
        """Main dispatcher, passes the mirror flag to the drawing funcs"""
        h = int(surface.get_height() * self.eyeOpenAmount)
        if h <= 0: return # Don't draw if closed
        
        # Create a surface with the correct blinked height
        cropped = pygame.Surface((surface.get_width(), h), pygame.SRCALPHA)

        if mood == TIRED:
            self.draw_glow(cropped, self.draw_tired_eye, color, mirror=mirror)
            self.draw_tired_eye(cropped, color, mirror=mirror)
        elif mood == ANGRY:
            self.draw_glow(cropped, self.draw_angry_eye, color, mirror=mirror)
            self.draw_angry_eye(cropped, color, mirror=mirror)
        elif mood == HAPPY:
            # Symmetrical, no mirror flag needed
            self.draw_glow(cropped, self.draw_happy_eye, color)
            self.draw_happy_eye(cropped, color)
        else:
            # Symmetrical, no mirror flag needed
            self.draw_glow(cropped, self.draw_default_eye, color)
            self.draw_default_eye(cropped, color)

        # Blit the final shape (at its correct vertical position)
        surface.blit(cropped, (0, 0))

    def drawEyes(self):
        """
        Main drawing loop.
        Handles symmetrical and asymmetrical moods differently.
        """
        self.screen.fill(BLACK)
        color = NEON_CYAN

        if self.mood == TIRED or self.mood == ANGRY:
            # Asymmetrical: draw left and right eyes separately
            
            # Left Eye (mirror=False)
            eye_surface_l = pygame.Surface((self.eyeW, self.eyeH), pygame.SRCALPHA)
            self.draw_eye_shape(eye_surface_l, self.mood, color, mirror=False)
            self.screen.blit(eye_surface_l, (self.eyeLx, self.eyeLy))
            
            # Right Eye (mirror=True)
            eye_surface_r = pygame.Surface((self.eyeW, self.eyeH), pygame.SRCALPHA)
            self.draw_eye_shape(eye_surface_r, self.mood, color, mirror=True)
            self.screen.blit(eye_surface_r, (self.eyeRx, self.eyeRy))
        else:
            # Symmetrical (DEFAULT, HAPPY): draw one and blit twice
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


# CLI Thread
def cli_input(eyes):
    """Runs in a separate thread to get user input without blocking pygame."""
    while True:
        try:
            mood = input("\nEnter mood (tired / angry / happy / default): ").strip()
            eyes.setMood(mood)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting CLI thread...")
            return


# MAIN
def main():
    pygame.init()
    screen = pygame.display.set_mode((1024, 600))
    pygame.display.set_caption("RoboEyes - Shape-Matched Reference Version")

    eyes = RoboEyes(screen)
    eyes.setMood("default")

    # Start the CLI input thread
    threading.Thread(target=cli_input, args=(eyes,), daemon=True).start()

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

