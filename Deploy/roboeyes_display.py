import pygame, sys, time, random

BLACK = (10, 10, 20)
NEON_CYAN = (0, 255, 255)
DEFAULT, TIRED, ANGRY, HAPPY = 0, 1, 2, 3


class RoboEyes:
    def __init__(self):
        """Initialize RoboEyes in fullscreen mode."""
        pygame.init()
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.display.set_caption("RoboEyes Display (Fullscreen)")

        # Get screen dimensions
        self.w, self.h = self.screen.get_size()

        # Eye geometry
        self.eyeW = 300
        self.eyeH = 280
        self.space = 130
        total_width = self.eyeW * 2 + self.space
        self.eyeLx = (self.w - total_width) // 2
        self.eyeRx = self.eyeLx + self.eyeW + self.space
        self.eyeLy = (self.h - self.eyeH) // 2 - 10
        self.eyeRy = self.eyeLy

        # Animation parameters
        self.mood = DEFAULT
        self.eyeOpenAmount = 1.0
        self.blinking = False
        self.blinkStart = 0
        self.blinkDuration = 0.25
        self.lastBlink = 0
        self.blinkInterval = 3
        self.frameInterval = 20
        self.fpsTimer = 0

        print("✅ RoboEyes display initialized in fullscreen mode")

    def millis(self): 
        return time.time() * 1000

    def setMood(self, mood_name: str):
        """Change the eye mood dynamically based on emotion."""
        mood_name = mood_name.lower().strip()
        if mood_name == "tired":
            self.mood = TIRED
        elif mood_name == "angry":
            self.mood = ANGRY
        elif mood_name == "happy":
            self.mood = HAPPY
        else:
            self.mood = DEFAULT
        print(f"👉 Eyes mood changed to: {mood_name.upper()}")

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

    def drawEyes(self):
        self.screen.fill(BLACK)
        color = NEON_CYAN
        mood = self.mood

        left_eye = pygame.Rect(self.eyeLx, self.eyeLy, self.eyeW, int(self.eyeH * self.eyeOpenAmount))
        right_eye = pygame.Rect(self.eyeRx, self.eyeRy, self.eyeW, int(self.eyeH * self.eyeOpenAmount))

        if mood == ANGRY:
            pygame.draw.polygon(self.screen, color, [
                (left_eye.left, left_eye.top + 50),
                (left_eye.right, left_eye.top + 10),
                (left_eye.right, left_eye.bottom),
                (left_eye.left, left_eye.bottom)
            ])
            pygame.draw.polygon(self.screen, color, [
                (right_eye.left, right_eye.top + 10),
                (right_eye.right, right_eye.top + 50),
                (right_eye.right, right_eye.bottom),
                (right_eye.left, right_eye.bottom)
            ])
        elif mood == HAPPY:
            pygame.draw.ellipse(self.screen, color, left_eye)
            pygame.draw.ellipse(self.screen, color, right_eye)
        elif mood == TIRED:
            pygame.draw.rect(self.screen, color, left_eye, border_radius=30)
            pygame.draw.rect(self.screen, color, right_eye, border_radius=30)
        else:
            pygame.draw.ellipse(self.screen, color, left_eye)
            pygame.draw.ellipse(self.screen, color, right_eye)

        pygame.display.flip()

    def update(self):
        now = self.millis()
        if now - self.fpsTimer >= self.frameInterval:
            self.updateBlink()
            self.drawEyes()
            self.fpsTimer = now

    def run_forever(self):
        """Continuously update eyes on screen."""
        clock = pygame.time.Clock()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    pygame.quit()
                    sys.exit()
            self.update()
            clock.tick(60)
