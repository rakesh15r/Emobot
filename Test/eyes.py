import pygame, math, random, time
from PIL import Image

pygame.init()
screen = pygame.display.set_mode((800, 480))
pygame.display.set_caption("Uncanny Robot Eyes")

clock = pygame.time.Clock()

# Load iris texture
iris = pygame.image.load("iris.jpg")
iris = pygame.transform.smoothscale(iris, (200, 200))

# Parameters
eye_radius = 150
pupil_radius = 30
eye_y = 240
left_eye_x = 250
right_eye_x = 600
blink_time = 0
blink_interval = random.uniform(3, 7)
lid_ratio = 0.0

def draw_eye(center, pupil_offset, pupil_size, eyelid):
    x, y = center
    # White background
    pygame.draw.circle(screen, (255, 255, 255), (x, y), eye_radius)
    # Iris (image texture)
    iris_pos = (x - 100 + pupil_offset[0] // 2, y - 100 + pupil_offset[1] // 2)
    screen.blit(iris, iris_pos)
    # Pupil
    pygame.draw.circle(screen, (0, 0, 0), (x + pupil_offset[0], y + pupil_offset[1]), pupil_size)
    # Eyelids
    if eyelid > 0:
        h = int(eye_radius * eyelid)
        pygame.draw.rect(screen, (0, 0, 0), (x - eye_radius, y - eye_radius, eye_radius*2, h))
        pygame.draw.rect(screen, (0, 0, 0), (x - eye_radius, y + eye_radius - h, eye_radius*2, h))

pupil_offset = [0, 0]
target_offset = [0, 0]
pupil_size = pupil_radius

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()

    # Random look
    for i in range(2):
        if abs(pupil_offset[i] - target_offset[i]) < 1:
            target_offset[i] = random.randint(-30, 30)
        pupil_offset[i] += (target_offset[i] - pupil_offset[i]) * 0.1

    # Pupil dilation
    pupil_size += (random.uniform(30, 60) - pupil_size) * 0.05

    # Blink
    if time.time() - blink_time > blink_interval:
        for phase in range(0, 20):
            screen.fill((0, 0, 0))
            lid = math.sin(phase / 20 * math.pi)
            draw_eye((left_eye_x, eye_y), pupil_offset, int(pupil_size), lid)
            draw_eye((right_eye_x, eye_y), pupil_offset, int(pupil_size), lid)
            pygame.display.flip()
            clock.tick(60)
        blink_time = time.time()
        blink_interval = random.uniform(3, 7)

    # Draw
    screen.fill((0, 0, 0))
    draw_eye((left_eye_x, eye_y), pupil_offset, int(pupil_size), lid_ratio)
    draw_eye((right_eye_x, eye_y), pupil_offset, int(pupil_size), lid_ratio)

    pygame.display.flip()
    clock.tick(60)