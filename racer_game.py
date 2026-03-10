import math
import os
import sys
from dataclasses import dataclass

import pygame
import pymunk
from pymunk import Vec2d

# -----------------------------
# Config
# -----------------------------
WIDTH, HEIGHT = 1280, 720
FPS = 120
TITLE = "Neo Circuit Racer"

TRACK_RECT_OUTER = pygame.Rect(100, 80, 1080, 560)
TRACK_RECT_INNER = pygame.Rect(300, 220, 680, 280)
START_LINE_X = 320

CAR_MASS = 1200
CAR_SIZE = (52, 28)
ENGINE_FORCE = 14500
BRAKE_FORCE = 22000
MAX_STEER_ANGLE = math.radians(36)
DRAG_COEFF = 0.0014
ROLL_RESIST = 15

LAPS_TO_WIN = 3

def force_safe_font_mode():
    """Monkey-patch SysFont to always fallback to default pygame font on unstable Windows envs."""
    allow_sys = os.getenv("NCR_ALLOW_SYSFONT", "0") == "1"
    if allow_sys:
        return

    def _safe_sysfont(_name, size, bold=False, italic=False):
        font = pygame.font.Font(None, size)
        font.set_bold(bold)
        font.set_italic(italic)
        return font

    pygame.font.SysFont = _safe_sysfont


def safe_sys_font(name: str, size: int, bold: bool = False):
    """Safe font loader. Uses patched SysFont (default font) unless NCR_ALLOW_SYSFONT=1."""
    try:
        return pygame.font.SysFont(name, size, bold=bold)
    except Exception:
        font = pygame.font.Font(None, size)
        font.set_bold(bold)
        return font


@dataclass
class Button:
    rect: pygame.Rect
    text: str

    def draw(self, surface, font, hovered=False):
        bg = (40, 75, 130) if hovered else (30, 48, 82)
        pygame.draw.rect(surface, bg, self.rect, border_radius=12)
        pygame.draw.rect(surface, (130, 190, 255), self.rect, 2, border_radius=12)
        label = font.render(self.text, True, (235, 245, 255))
        surface.blit(label, label.get_rect(center=self.rect.center))


class Car:
    def __init__(self, space):
        moment = pymunk.moment_for_box(CAR_MASS, CAR_SIZE)
        self.body = pymunk.Body(CAR_MASS, moment)
        self.body.position = (START_LINE_X + 30, HEIGHT // 2)
        self.shape = pymunk.Poly.create_box(self.body, CAR_SIZE, radius=3)
        self.shape.friction = 1.2
        self.shape.elasticity = 0.1
        self.shape.collision_type = 2
        space.add(self.body, self.shape)

        self.steer_input = 0.0
        self.throttle = 0.0
        self.brake = False

    def reset(self):
        self.body.position = (START_LINE_X + 30, HEIGHT // 2)
        self.body.angle = 0
        self.body.velocity = (0, 0)
        self.body.angular_velocity = 0

    def update(self, dt):
        forward = Vec2d(1, 0).rotated(self.body.angle)
        right = Vec2d(0, 1).rotated(self.body.angle)

        vel = self.body.velocity
        forward_speed = vel.dot(forward)
        lateral_speed = vel.dot(right)

        # Lateral grip to avoid ice-like drift
        lateral_impulse = -lateral_speed * 12.0
        self.body.apply_impulse_at_local_point((0, lateral_impulse * self.body.mass * dt), (0, 0))

        force = forward * (self.throttle * ENGINE_FORCE)
        if self.brake:
            brake_dir = -1 if forward_speed > 0 else 1
            force += forward * (brake_dir * BRAKE_FORCE)

        # Rolling + aerodynamic drag
        drag = -vel * (vel.length * DRAG_COEFF)
        rolling = -vel * ROLL_RESIST
        total_force = force + drag + rolling
        self.body.apply_force_at_world_point(total_force, self.body.position)

        # Steering scales down at high speed for stability
        speed_factor = max(0.22, 1.0 - min(abs(forward_speed) / 650, 0.78))
        target_ang_vel = self.steer_input * MAX_STEER_ANGLE * speed_factor * 7.5
        self.body.angular_velocity = target_ang_vel

    @property
    def speed_kmh(self):
        # Pymunk units interpreted as pixels/sec; scale chosen for game feel
        return self.body.velocity.length * 0.36


class RaceGame:
    def __init__(self):
        pygame.init()
        force_safe_font_mode()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()

        self.font_xl = safe_sys_font("segoeui", 56, bold=True)
        self.font_lg = safe_sys_font("segoeui", 34, bold=True)
        self.font_md = safe_sys_font("segoeui", 24)
        self.font_sm = safe_sys_font("consolas", 20)

        self.space = pymunk.Space()
        self.space.gravity = (0, 0)
        self.create_track_boundaries()

        self.car = Car(self.space)

        self.state = "menu"  # menu | countdown | race | paused | finished
        self.countdown = 3.0
        self.time_elapsed = 0.0
        self.best_lap = None
        self.current_lap_start = 0.0
        self.lap_times = []
        self.laps = 0
        self.was_left_of_line = False

        self.play_btn = Button(pygame.Rect(WIDTH // 2 - 130, HEIGHT // 2 + 40, 260, 58), "开始比赛")
        self.restart_btn = Button(pygame.Rect(WIDTH // 2 - 130, HEIGHT // 2 + 130, 260, 58), "重新开始")
        self.quit_btn = Button(pygame.Rect(WIDTH // 2 - 130, HEIGHT // 2 + 205, 260, 58), "退出")

    def create_track_boundaries(self):
        static = self.space.static_body
        outlines = [
            TRACK_RECT_OUTER,
            TRACK_RECT_INNER,
        ]
        for rect in outlines:
            pts = [rect.topleft, rect.topright, rect.bottomright, rect.bottomleft]
            for i in range(4):
                a = pts[i]
                b = pts[(i + 1) % 4]
                seg = pymunk.Segment(static, a, b, 6)
                seg.friction = 1.0
                seg.elasticity = 0.35
                seg.collision_type = 1
                self.space.add(seg)

    def reset_race(self):
        self.car.reset()
        self.countdown = 3.0
        self.time_elapsed = 0.0
        self.current_lap_start = 0.0
        self.lap_times.clear()
        self.best_lap = None
        self.laps = 0
        self.was_left_of_line = False
        self.state = "countdown"

    def handle_events(self):
        mouse = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == "race":
                        self.state = "paused"
                    elif self.state == "paused":
                        self.state = "race"

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.state == "menu":
                    if self.play_btn.rect.collidepoint(mouse):
                        self.reset_race()
                    elif self.quit_btn.rect.collidepoint(mouse):
                        return False
                elif self.state == "finished":
                    if self.restart_btn.rect.collidepoint(mouse):
                        self.reset_race()
                    elif self.quit_btn.rect.collidepoint(mouse):
                        return False
                elif self.state == "paused":
                    if self.restart_btn.rect.collidepoint(mouse):
                        self.reset_race()
        return True

    def process_input(self):
        keys = pygame.key.get_pressed()
        self.car.throttle = 1.0 if keys[pygame.K_w] or keys[pygame.K_UP] else 0.0
        self.car.brake = keys[pygame.K_s] or keys[pygame.K_DOWN]
        steer_left = keys[pygame.K_a] or keys[pygame.K_LEFT]
        steer_right = keys[pygame.K_d] or keys[pygame.K_RIGHT]
        self.car.steer_input = float(steer_right) - float(steer_left)

    def update_lap_logic(self):
        x = self.car.body.position.x
        if x < START_LINE_X - 10:
            self.was_left_of_line = True
        if self.was_left_of_line and x > START_LINE_X + 10 and self.car.speed_kmh > 20:
            lap_time = self.time_elapsed - self.current_lap_start
            self.current_lap_start = self.time_elapsed
            self.was_left_of_line = False

            if lap_time > 1.5:
                self.lap_times.append(lap_time)
                self.laps += 1
                if self.best_lap is None or lap_time < self.best_lap:
                    self.best_lap = lap_time

                if self.laps >= LAPS_TO_WIN:
                    self.state = "finished"

    def update(self, dt):
        if self.state == "countdown":
            self.countdown -= dt
            if self.countdown <= 0:
                self.state = "race"
                self.countdown = 0
        elif self.state == "race":
            self.process_input()
            self.car.update(dt)
            self.space.step(dt)
            self.time_elapsed += dt
            self.update_lap_logic()

    def draw_track(self):
        self.screen.fill((11, 17, 25))

        # Track body
        pygame.draw.rect(self.screen, (48, 58, 70), TRACK_RECT_OUTER, border_radius=20)
        pygame.draw.rect(self.screen, (11, 17, 25), TRACK_RECT_INNER, border_radius=16)

        # Curbs
        pygame.draw.rect(self.screen, (200, 60, 70), TRACK_RECT_OUTER, 10, border_radius=20)
        pygame.draw.rect(self.screen, (200, 60, 70), TRACK_RECT_INNER, 10, border_radius=16)

        # Start line
        pygame.draw.line(self.screen, (255, 255, 255), (START_LINE_X, TRACK_RECT_OUTER.top), (START_LINE_X, TRACK_RECT_OUTER.bottom), 5)
        for i in range(TRACK_RECT_OUTER.top, TRACK_RECT_OUTER.bottom, 20):
            color = (10, 10, 10) if (i // 20) % 2 == 0 else (235, 235, 235)
            pygame.draw.rect(self.screen, color, (START_LINE_X - 5, i, 10, 10))

    def draw_car(self):
        car_surf = pygame.Surface(CAR_SIZE, pygame.SRCALPHA)
        pygame.draw.rect(car_surf, (70, 160, 250), (0, 0, *CAR_SIZE), border_radius=7)
        pygame.draw.rect(car_surf, (18, 35, 58), (8, 6, CAR_SIZE[0]-16, CAR_SIZE[1]-12), border_radius=5)
        pygame.draw.rect(car_surf, (250, 240, 120), (CAR_SIZE[0]-8, 6, 5, 6), border_radius=2)
        pygame.draw.rect(car_surf, (250, 120, 120), (3, 6, 5, 6), border_radius=2)

        rotated = pygame.transform.rotate(car_surf, -math.degrees(self.car.body.angle))
        pos = self.car.body.position
        rect = rotated.get_rect(center=(pos.x, pos.y))
        self.screen.blit(rotated, rect)

    def draw_hud(self):
        panel = pygame.Rect(20, 18, 290, 140)
        pygame.draw.rect(self.screen, (17, 27, 40, 215), panel, border_radius=12)
        pygame.draw.rect(self.screen, (110, 180, 255), panel, 2, border_radius=12)

        speed_txt = self.font_lg.render(f"{int(self.car.speed_kmh):03d} km/h", True, (230, 245, 255))
        lap_txt = self.font_md.render(f"圈数: {self.laps}/{LAPS_TO_WIN}", True, (185, 230, 255))
        time_txt = self.font_md.render(f"总时间: {self.time_elapsed:05.2f}s", True, (185, 230, 255))
        best_txt = self.font_md.render(
            f"最佳: {self.best_lap:05.2f}s" if self.best_lap else "最佳: --",
            True,
            (185, 230, 255),
        )

        self.screen.blit(speed_txt, (35, 28))
        self.screen.blit(lap_txt, (35, 75))
        self.screen.blit(time_txt, (35, 102))
        self.screen.blit(best_txt, (35, 129))

        hint = self.font_sm.render("WASD/方向键驾驶 | ESC 暂停", True, (178, 198, 220))
        self.screen.blit(hint, (WIDTH - hint.get_width() - 20, HEIGHT - 30))

    def draw_center_overlay(self, title, subtitle=None):
        card = pygame.Rect(WIDTH // 2 - 260, HEIGHT // 2 - 150, 520, 320)
        pygame.draw.rect(self.screen, (15, 22, 34, 235), card, border_radius=18)
        pygame.draw.rect(self.screen, (110, 180, 255), card, 2, border_radius=18)

        t = self.font_xl.render(title, True, (235, 245, 255))
        self.screen.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 75)))

        if subtitle:
            s = self.font_md.render(subtitle, True, (185, 215, 245))
            self.screen.blit(s, s.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 25)))

    def draw_menu(self):
        self.draw_track()
        self.draw_center_overlay("NEO CIRCUIT RACER", "带简化物理引擎的 2D 赛车")
        mouse = pygame.mouse.get_pos()
        self.play_btn.draw(self.screen, self.font_md, self.play_btn.rect.collidepoint(mouse))
        self.quit_btn.draw(self.screen, self.font_md, self.quit_btn.rect.collidepoint(mouse))

    def draw(self):
        if self.state == "menu":
            self.draw_menu()
        else:
            self.draw_track()
            self.draw_car()
            self.draw_hud()

            if self.state == "countdown":
                n = max(1, math.ceil(self.countdown))
                self.draw_center_overlay(str(n), "准备出发")
            elif self.state == "paused":
                self.draw_center_overlay("已暂停", "点击下方按钮重新开始，或按 ESC 继续")
                mouse = pygame.mouse.get_pos()
                self.restart_btn.draw(self.screen, self.font_md, self.restart_btn.rect.collidepoint(mouse))
            elif self.state == "finished":
                subtitle = f"完赛时间: {self.time_elapsed:.2f}s"
                self.draw_center_overlay("比赛完成", subtitle)
                mouse = pygame.mouse.get_pos()
                self.restart_btn.draw(self.screen, self.font_md, self.restart_btn.rect.collidepoint(mouse))
                self.quit_btn.draw(self.screen, self.font_md, self.quit_btn.rect.collidepoint(mouse))

        pygame.display.flip()

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            running = self.handle_events()
            self.update(dt)
            self.draw()

        pygame.quit()
        sys.exit(0)


def main():
    RaceGame().run()


if __name__ == "__main__":
    main()
