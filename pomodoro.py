"""Pomodoro-Tamagotchi — timer Pomodoro em Pygame com um monstrengo fofo.

O bichinho e pixel art desenhada em tempo real (sem sprites externos). Ele
comeca fofo e vai virando um demoniozinho conforme o cansaco aumenta: chifres
crescem, os olhos ficam afiados, a boca vira um grin com presas e nasce uma
cauda pontuda. Quando o tempo acaba, ele NAO troca de fase sozinho: voce marca
que a pausa comecou, ele comemora (animacao de alegria) e entao se recupera.

Controles:
    Clique esquerdo .... botao de acao (iniciar / pausar / comecar fase)
    Arrastar (topo) .... mover a janela
    Clique direito ..... nova sessao (reset)
    ESPACO / ENTER ..... botao de acao
    S .................. pular fase
    R .................. reset
    ESC ................ sair
"""

import array
import io
import math
import os
import sys
import wave

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from pet import (
    PomodoroPet, FOCUS, BREAK,
    FOCUS_DONE, BREAK_DONE, BREAK_STARTED,
)

WIDTH, HEIGHT = 240, 168
FPS = 60

SPRITE = 64          # resolucao logica do bichinho (pixel art)
SCALE = 2            # ampliacao com nearest-neighbor

MAGIC = (255, 0, 255)     # cor-chave: vira 100% transparente (Windows)
REVEAL_SPEED = 6.0        # velocidade da transicao compacto <-> expandido
ALPHA_IDLE = 120          # opacidade no repouso (0-255)
ALPHA_ACTIVE = 240        # opacidade com o mouse em cima
REVEAL_THRESHOLD = 0.4

# Layout compacto (so bichinho + timer)
COMPACT_PET = (62, 88)
COMPACT_TIMER = (178, 88)

# Layout expandido (painel com tudo)
PANEL_RECT = pygame.Rect(3, 3, WIDTH - 6, HEIGHT - 6)
EXPANDED_PET = (50, 88)
EXPANDED_TIMER = (168, 50)
ENERGY_BAR = pygame.Rect(104, 80, 116, 11)
CYCLES_Y = 102
BTN_MAIN = pygame.Rect(104, 112, 120, 22)
BTN_SKIP = pygame.Rect(104, 138, 38, 20)
BTN_RESET = pygame.Rect(145, 138, 38, 20)
BTN_EXIT = pygame.Rect(186, 138, 38, 20)

# Paleta
BG = (26, 28, 35)
PANEL = (40, 43, 53)
TEXT = (236, 239, 246)
MUTED = (140, 148, 166)
FOCUS_ACCENT = (255, 96, 96)
BREAK_ACCENT = (86, 220, 140)
EYE_WHITE = (250, 250, 253)
INK = (30, 22, 38)          # contorno do bichinho
DEMON_EYE = (255, 214, 96)
SWEAT = (150, 205, 255)
SPARK = (255, 226, 120)
TOOTH = (250, 250, 255)

# Cores da energia: 0.0 = exausto/demonio, 1.0 = fofo
ENERGY_STOPS = (
    (0.0, (168, 40, 62)),
    (0.25, (216, 92, 74)),
    (0.55, (238, 170, 100)),
    (1.0, (122, 214, 150)),
)

JOY_TIME = 1.8
ALERT_TIME = 1.6


def clamp(value, low, high):
    return max(low, min(high, value))


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(c1, c2))


def energy_color(energy):
    level = clamp(energy / 100.0, 0.0, 1.0)
    for (p0, c0), (p1, c1) in zip(ENERGY_STOPS, ENERGY_STOPS[1:]):
        if level <= p1:
            span = (p1 - p0) or 1.0
            return mix(c0, c1, (level - p0) / span)
    return ENERGY_STOPS[-1][1]


def shade(color, factor):
    return tuple(int(round(c * factor)) for c in color)


RATE = 22050
CUE_NAMES = ("demon", "recharge", "ready")

# recarga: tres notas subindo (o que ja estava audivel)
_RECHARGE = (
    (0.20, 349, 349, "tone", 0.28),
    (0.06, 0, 0, "rest", 0),
    (0.20, 440, 440, "tone", 0.30),
    (0.06, 0, 0, "rest", 0),
    (0.26, 554, 659, "tone", 0.32),
)


def _silence(dur, rate):
    return [0.0] * int(rate * dur)


def _segments(segments, rate):
    out = []
    phase = 0.0
    for dur, f0, f1, kind, vol in segments:
        n = max(1, int(rate * dur))
        for i in range(n):
            k = i / (n - 1) if n > 1 else 0.0
            env = math.sin(math.pi * k) ** 0.85
            phase += 2 * math.pi * (f0 + (f1 - f0) * k) / rate
            if kind == "rest":
                out.append(0.0)
            else:
                out.append(vol * env * math.sin(phase))
    return out


def _tom(rate, vol=0.78):
    """Batida 'tam': tom curto caindo de tom."""
    dur = 0.30
    n = int(rate * dur)
    phase = 0.0
    out = []
    for i in range(n):
        t = i / rate
        f = 220 * math.exp(-7.0 * t) + 75
        phase += 2 * math.pi * f / rate
        env = math.exp(-7.5 * t)
        s = math.sin(phase) * 0.8 + math.sin(2 * phase) * 0.2
        out.append(vol * env * s)
    return out


def _giggle(rate):
    """Risadinha rouca, subindo: he-he-he-he-he."""
    out = []
    for i, f0 in enumerate((220, 270, 330, 400, 480)):
        n = int(rate * 0.12)
        phase = 0.0
        for j in range(n):
            k = j / n
            env = math.sin(math.pi * k) ** 0.55
            phase += 2 * math.pi * f0 / rate
            s = math.tanh(2.8 * math.sin(phase)) + 0.3 * math.sin(phase * 2.4)
            if j < int(rate * 0.018):
                noise = ((j * 1103515245 + i * 97) % 1000) / 500.0 - 1.0
                s = 0.5 * s + 0.5 * noise
            out.append(0.48 * env * s)
        out.extend(_silence(0.07, rate))
    return out


def _demon_cue(rate):
    out = []
    for _ in range(3):
        out.extend(_tom(rate))
        out.extend(_silence(0.14, rate))
    out.extend(_silence(0.10, rate))
    out.extend(_giggle(rate))
    return out


def _pam(freq, dur, rate, vol=0.5, decay=6.0, harmony=0.0):
    """Nota de fanfarra, quadrada e curta, no estilo som de jogo."""
    n = int(rate * dur)
    phase = 0.0
    fifth = 0.0
    out = []
    for i in range(n):
        t = i / rate
        env = math.exp(-decay * t) * (t / 0.006 if t < 0.006 else 1.0)
        phase += 2 * math.pi * freq / rate
        fifth += 2 * math.pi * freq * 1.5 / rate
        sq = 1.0 if math.sin(phase) >= 0 else -1.0
        s = 0.62 * sq + 0.38 * math.sin(phase)
        if harmony:
            sq5 = 1.0 if math.sin(fifth) >= 0 else -1.0
            s = (s + harmony * sq5) / (1.0 + harmony)
        out.append(vol * env * s)
    return out


def _victory_cue(rate):
    """pam, pam-pam-pam, pam, pammmm."""
    c, e, g, c6 = 523.25, 659.25, 783.99, 1046.5
    parts = (
        _pam(c, 0.22, rate, decay=7),
        _silence(0.07, rate),
        _pam(e, 0.12, rate, decay=11),
        _pam(g, 0.12, rate, decay=11),
        _pam(c6, 0.14, rate, decay=9),
        _silence(0.06, rate),
        _pam(g, 0.22, rate, decay=6),
        _silence(0.05, rate),
        _pam(c6, 0.78, rate, vol=0.58, decay=1.5, harmony=0.45),
    )
    out = []
    for part in parts:
        out.extend(part)
    return out


def cue_samples(name, rate=RATE):
    if name == "demon":
        return _demon_cue(rate)
    if name == "ready":
        return _victory_cue(rate)
    if name == "recharge":
        return _segments(_RECHARGE, rate)
    raise KeyError(name)


def _sound_from_samples(samples, rate=RATE):
    pcm = array.array("h", (int(max(-1.0, min(1.0, s)) * 32000) for s in samples))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.tobytes())
    return pygame.mixer.Sound(buffer=buf.getvalue())


def load_cues():
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(RATE, -16, 1, 512)
        return {name: _sound_from_samples(cue_samples(name)) for name in CUE_NAMES}
    except (pygame.error, OSError):
        return {}


class _WindowDrag:
    """Mover/sempre-no-topo para janela sem bordas (somente Windows)."""

    HWND_TOPMOST = -1

    def __init__(self):
        self.ok = False
        self.transparent = False
        self._colorkey = 0
        self._last_alpha = None
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes

            self._ctypes = ctypes
            self._wintypes = wintypes
            self._user32 = ctypes.windll.user32
            info = pygame.display.get_wm_info()
            self.hwnd = info.get("window")
            self.ok = bool(self.hwnd)
            if self.ok:
                self._configure()
        except Exception:
            self.ok = False

    def _configure(self):
        """Define argtypes para os handles de 64 bits nao serem truncados."""
        c = self._ctypes
        w = self._wintypes
        u = self._user32
        u.GetWindowLongW.argtypes = [w.HWND, c.c_int]
        u.GetWindowLongW.restype = c.c_long
        u.SetWindowLongW.argtypes = [w.HWND, c.c_int, c.c_long]
        u.SetWindowLongW.restype = c.c_long
        u.SetWindowPos.argtypes = [w.HWND, w.HWND, c.c_int, c.c_int,
                                   c.c_int, c.c_int, c.c_uint]
        u.SetLayeredWindowAttributes.argtypes = [w.HWND, c.c_uint32,
                                                 c.c_ubyte, c.c_uint32]
        u.MoveWindow.argtypes = [w.HWND, c.c_int, c.c_int, c.c_int,
                                 c.c_int, w.BOOL]
        u.GetCursorPos.argtypes = [c.POINTER(w.POINT)]
        u.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]

    def set_topmost(self):
        if not self.ok:
            return
        SWP_NOSIZE, SWP_NOMOVE = 0x0001, 0x0002
        self._user32.SetWindowPos(
            self.hwnd, self.HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE
        )

    def cursor_pos(self):
        pt = self._wintypes.POINT()
        self._user32.GetCursorPos(self._ctypes.byref(pt))
        return pt.x, pt.y

    def move_to(self, x, y):
        if not self.ok:
            return
        self._user32.MoveWindow(self.hwnd, x, y, WIDTH, HEIGHT, True)

    def top_left(self):
        rect = self._wintypes.RECT()
        self._user32.GetWindowRect(self.hwnd, self._ctypes.byref(rect))
        return rect.left, rect.top

    def enable_transparency(self, key=MAGIC):
        """Ativa janela em camadas com fundo transparente por cor-chave."""
        if not self.ok:
            return
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_FRAMECHANGED = (
            0x0001, 0x0002, 0x0004, 0x0020)
        style = self._user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
        self._user32.SetWindowLongW(
            self.hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
        self._user32.SetWindowPos(
            self.hwnd, 0, 0, 0, 0, 0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED)
        self._colorkey = key[0] | (key[1] << 8) | (key[2] << 16)  # COLORREF
        self.transparent = True

    def set_alpha(self, alpha):
        """Opacidade da janela (0-255); a cor-chave fica sempre transparente."""
        if not self.ok or not self.transparent:
            return
        alpha = int(clamp(alpha, 0, 255))
        if alpha == self._last_alpha:
            return
        self._last_alpha = alpha
        LWA_COLORKEY, LWA_ALPHA = 0x00000001, 0x00000002
        self._user32.SetLayeredWindowAttributes(
            self.hwnd, self._colorkey, alpha, LWA_COLORKEY | LWA_ALPHA)


class PetWindow:
    def __init__(self, focus_duration=25 * 60, break_duration=5 * 60,
                 opaque=False):
        pygame.mixer.pre_init(RATE, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("Pomodoro Pet")
        self.cues = load_cues()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME)
        self.clock = pygame.time.Clock()
        self.base = BG if opaque else MAGIC

        self.pet = PomodoroPet(focus_duration=focus_duration,
                               break_duration=break_duration)

        self.font_compact = pygame.font.SysFont("consolas", 34, bold=True)
        self.font_timer = pygame.font.SysFont("consolas", 26, bold=True)
        self.font_label = pygame.font.SysFont("consolas", 12, bold=True)
        self.font_button = pygame.font.SysFont("consolas", 13, bold=True)
        self.font_small = pygame.font.SysFont("consolas", 12)
        self.font_tiny = pygame.font.SysFont("consolas", 11)

        self.drag = _WindowDrag()
        self.drag.set_topmost()
        if not opaque:
            self.drag.enable_transparency()

        self.pressed = False
        self.drag_cursor = (0, 0)
        self.drag_origin = (0, 0)
        self.drag_moved = False
        self.look = (0.0, 0.0)

        self.running = True
        self.joy = 0.0       # animacao de alegria ao comecar a pausa
        self.alert = 0.0     # pulso quando uma fase termina
        self.reveal = 0.0    # 0 = compacto, 1 = expandido

    @property
    def expanded(self):
        return self.reveal > REVEAL_THRESHOLD

    def _pet_center(self):
        return EXPANDED_PET if self.expanded else COMPACT_PET

    # --- eventos ---
    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._on_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._on_mouse_down(event)
            elif event.type == pygame.MOUSEBUTTONUP:
                self._on_mouse_up(event)
            elif event.type == pygame.MOUSEMOTION:
                self._on_motion()

    def _on_key(self, key):
        if key == pygame.K_ESCAPE:
            self.running = False
        elif key in (pygame.K_SPACE, pygame.K_RETURN):
            self._primary_action()
        elif key == pygame.K_r:
            self.pet.reset()
        elif key == pygame.K_s:
            self._skip()

    def _on_mouse_down(self, event):
        if event.button == 1:
            self.pressed = True
            self.drag_moved = False
            self.drag_cursor = self.drag.cursor_pos()
            self.drag_origin = self.drag.top_left()
        elif event.button == 3:
            self.pet.reset()

    def _on_mouse_up(self, event):
        if event.button != 1:
            return
        was_drag = self.drag_moved
        self.pressed = False
        self.drag_moved = False
        if was_drag:
            return
        if self.expanded:
            if BTN_SKIP.collidepoint(event.pos):
                self._skip()
            elif BTN_RESET.collidepoint(event.pos):
                self.pet.reset()
            elif BTN_EXIT.collidepoint(event.pos):
                self.running = False
            elif (BTN_MAIN.collidepoint(event.pos)
                  or self._pet_rect().collidepoint(event.pos)):
                self._primary_action()
        else:
            self._primary_action()

    def _on_motion(self):
        if not self.pressed or not self.drag.ok:
            return
        cx, cy = self.drag.cursor_pos()
        dx = cx - self.drag_cursor[0]
        dy = cy - self.drag_cursor[1]
        if not self.drag_moved and (abs(dx) > 3 or abs(dy) > 3):
            self.drag_moved = True
        if self.drag_moved:
            self.drag.move_to(self.drag_origin[0] + dx, self.drag_origin[1] + dy)

    def _pet_rect(self):
        size = SPRITE * SCALE
        return pygame.Rect(0, 0, size, size).move(
            self._pet_center()[0] - size // 2,
            self._pet_center()[1] - size // 2)

    def _play(self, name):
        sound = self.cues.get(name)
        if sound is not None:
            sound.play()

    def _on_phase(self, event):
        if event == FOCUS_DONE:
            self.alert = ALERT_TIME
            self._play("demon")
        elif event == BREAK_STARTED:
            self.joy = JOY_TIME
            self._play("recharge")
        elif event == BREAK_DONE:
            self.alert = ALERT_TIME
            self._play("ready")

    def _primary_action(self):
        """Botao unico: inicia/pausa ou marca o inicio da proxima fase."""
        self._on_phase(self.pet.toggle())

    def _skip(self):
        self._on_phase(self.pet.skip())

    # --- loop ---
    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self._handle_events()
            self._update(dt)
            self._draw()
            pygame.display.flip()
        pygame.quit()

    def _update(self, dt):
        for event in self.pet.tick(dt):
            self._on_phase(event)
        self.joy = max(0.0, self.joy - dt)
        self.alert = max(0.0, self.alert - dt)

        target = 1.0 if pygame.mouse.get_focused() else 0.0
        step = REVEAL_SPEED * dt
        if self.reveal < target:
            self.reveal = min(target, self.reveal + step)
        else:
            self.reveal = max(target, self.reveal - step)

        cx, cy = self._pet_center()
        mx, my = pygame.mouse.get_pos()
        self.look = (clamp((mx - cx) / (WIDTH / 2), -1.0, 1.0),
                     clamp((my - cy) / (HEIGHT / 2), -1.0, 1.0))

    # --- expressoes ---
    def _expression(self):
        if self.joy > 0:
            return "happy"
        if self.pet.phase == BREAK and self.pet.running:
            return "happy" if self.pet.energy >= 70 else "resting"
        return self.pet.mood

    def _action_label(self):
        p = self.pet
        if p.awaiting:
            return "comecar pausa" if p.phase == FOCUS else "iniciar foco"
        if p.running:
            return "pausar"
        if p.progress > 0:
            return "retomar"
        return "iniciar foco" if p.phase == FOCUS else "iniciar pausa"

    # --- desenho ---
    def _draw(self):
        t = pygame.time.get_ticks() / 1000.0
        self.screen.fill(self.base)
        if self.expanded:
            self._draw_expanded(t)
        else:
            self._draw_compact(t)
        self.drag.set_alpha(lerp(ALPHA_IDLE, ALPHA_ACTIVE, self.reveal))

    def _accent(self):
        return BREAK_ACCENT if self.pet.phase == BREAK else FOCUS_ACCENT

    def _timer_color(self):
        return self._accent() if self.pet.awaiting else TEXT

    def _draw_compact(self, t):
        self._draw_pet(t, *COMPACT_PET)
        text = self.font_compact.render(
            PomodoroPet.format_time(self.pet.remaining), False, self._timer_color())
        self.screen.blit(text, text.get_rect(center=COMPACT_TIMER))
        if self.alert > 0:
            self._draw_alert(COMPACT_PET[0], COMPACT_PET[1] - 58)

    def _draw_expanded(self, t):
        pygame.draw.rect(self.screen, PANEL, PANEL_RECT, border_radius=10)
        pygame.draw.rect(self.screen, shade(PANEL, 1.6), PANEL_RECT, 2,
                         border_radius=10)

        label = self.font_label.render(self.pet.phase_label, False, (20, 22, 28))
        pill = pygame.Rect(0, 0, label.get_width() + 18, 18)
        pill.topleft = (PANEL_RECT.x + 8, PANEL_RECT.y + 7)
        pygame.draw.rect(self.screen, self._accent(), pill, border_radius=9)
        self.screen.blit(label, label.get_rect(center=pill.center))

        status = ("aguardando" if self.pet.awaiting
                  else "rodando" if self.pet.running else "pausado")
        txt = self.font_tiny.render(status, False, MUTED)
        self.screen.blit(txt, txt.get_rect(midright=(PANEL_RECT.right - 8,
                                                     pill.centery)))

        self._draw_pet(t, *EXPANDED_PET)
        self._draw_timer(*EXPANDED_TIMER)
        self._draw_energy()
        self._draw_cycles()
        self._button(BTN_MAIN, self._action_label(), primary=True)
        self._button(BTN_SKIP, "pular")
        self._button(BTN_RESET, "reset")
        self._button(BTN_EXIT, "sair")
        if self.alert > 0:
            self._draw_alert(EXPANDED_PET[0], EXPANDED_PET[1] - 58)

    def _button(self, rect, label, primary=False):
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        active = primary and (self.pet.awaiting or not self.pet.running)
        base = self._accent() if active else shade(PANEL, 1.35)
        color = mix(base, (255, 255, 255), 0.25 if hovered else 0.0)
        pygame.draw.rect(self.screen, color, rect, border_radius=5)
        pygame.draw.rect(self.screen, shade(PANEL, 1.9), rect, 1, border_radius=5)
        txt = self.font_button.render(label, False,
                                      (20, 22, 28) if active else TEXT)
        self.screen.blit(txt, txt.get_rect(center=rect.center))

    def _draw_alert(self, x, y):
        pulse = 1.0 + 0.4 * abs(math.sin(pygame.time.get_ticks() / 130.0))
        mark = self.font_button.render("!", False, self._accent())
        mark = pygame.transform.scale(
            mark, (int(mark.get_width() * pulse),
                   int(mark.get_height() * pulse)))
        self.screen.blit(mark, mark.get_rect(center=(int(x), int(y))))

    def _draw_pet(self, t, cx, cy):
        expr = self._expression()
        resting = expr == "resting"

        if self.joy > 0:
            bob = -abs(math.sin(t * 7.0)) * 12 * min(1.0, self.joy / 1.2)
        else:
            speed = 1.1 if resting else 2.4
            amp = 2 if expr == "exhausted" else 4
            bob = math.sin(t * speed) * amp

        # sombra no chao (so no painel; no modo flutuante fica estranha)
        if self.expanded:
            shadow_w = int(SPRITE * SCALE * 0.6)
            pygame.draw.ellipse(self.screen, (18, 19, 24),
                                pygame.Rect(cx - shadow_w // 2, cy + 30,
                                            shadow_w, 13))

        sprite = self._sprite(expr, t)
        scaled = pygame.transform.scale(sprite, (SPRITE * SCALE, SPRITE * SCALE))
        rect = scaled.get_rect(center=(cx, int(cy + bob)))
        self.screen.blit(scaled, rect)

    def _menace(self):
        """0 = fofinho, 1 = demoniozinho. Demoniza conforme a energia cai."""
        return clamp((0.7 - self.pet.energy / 100.0) / 0.7, 0.0, 1.0)

    def _sprite(self, expr, t):
        """Desenha o monstrengo numa superficie 64x64 (ampliada depois)."""
        s = pygame.Surface((SPRITE, SPRITE), pygame.SRCALPHA)
        bx, by, radius = 32, 33, 17
        men = self._menace()
        if self.joy > 0:
            men *= 0.6      # na comemoracao ele fica mais fofo que demonio
        body = energy_color(self.pet.energy)
        dark = shade(body, 0.52)
        resting = expr == "resting"

        self._sprite_tail(s, bx, by, radius, men, dark)
        self._sprite_horns(s, bx, by, radius, men, body)

        pygame.draw.circle(s, body, (bx, by), radius)
        pygame.draw.ellipse(s, mix(body, (255, 255, 255), 0.20),
                            pygame.Rect(bx - 9, by + 1, 18, 13))
        if men < 0.6:
            pygame.draw.ellipse(s, shade(body, 0.88),
                                pygame.Rect(bx - 14, by - 8, 7, 5))
            pygame.draw.ellipse(s, shade(body, 0.88),
                                pygame.Rect(bx + 6, by - 4, 5, 4))
        pygame.draw.circle(s, INK, (bx, by), radius, 2)

        for dx in (-6, 6):
            foot = pygame.Rect(bx + dx - 4, by + radius - 3, 8, 6)
            pygame.draw.ellipse(s, dark, foot)
            pygame.draw.ellipse(s, INK, foot, 1)

        self._sprite_arms(s, bx, by, radius, men, body)

        if expr in ("happy", "ok") or resting:
            for dx in (-11, 11):
                pygame.draw.circle(s, (255, 140, 150), (bx + dx, by + 4), 2)

        self._sprite_face(s, bx, by, men, expr, t)

        if expr in ("tired", "exhausted") and self.pet.running:
            self._sprite_sweat(s, bx, by, t)
        if resting:
            self._sprite_zzz(s, bx, by, t)
        if self.joy > 0:
            self._sprite_joy(s, bx, by, radius, t)
        return s

    def _sprite_tail(self, s, bx, by, radius, men, color):
        if men <= 0.2:
            return
        k = (men - 0.2) / 0.8
        start = (bx + radius - 2, by + radius - 5)
        mid = (bx + radius + 6, by + radius - 7)
        tip = (bx + radius + 8, by + 2 - int(7 * k))
        pygame.draw.lines(s, color, False, [start, mid, tip], 3)
        pygame.draw.polygon(s, color, [(tip[0] - 3, tip[1] + 1),
                                       (tip[0] + 3, tip[1] + 1),
                                       (tip[0], tip[1] - 6)])

    def _sprite_horns(self, s, bx, by, radius, men, body):
        lit = mix(body, (255, 255, 255), 0.35)
        color = mix(lit, (104, 62, 120), men)
        length = int(lerp(5, 15, men))
        curve = int(lerp(1, 5, men))
        base_y = by - radius + 3
        for side in (-1, 1):
            base_x = bx + side * 9
            tip = (int(bx + side * (9 + curve)), base_y - length)
            points = [(base_x - 3, base_y), (base_x + 3, base_y), tip]
            pygame.draw.polygon(s, color, points)
            pygame.draw.polygon(s, INK, points, 1)

    def _sprite_arms(self, s, bx, by, radius, men, body):
        arm = shade(body, 0.90)
        raised = self.joy > 0
        for side in (-1, 1):
            ax = int(bx + side * (radius - 2))
            ay = int(by + (-2 if raised else 4))
            rect = pygame.Rect(0, 0, 7, 10)
            rect.center = (ax, ay)
            pygame.draw.ellipse(s, arm, rect)
            pygame.draw.ellipse(s, INK, rect, 1)

    def _sprite_face(self, s, bx, by, men, expr, t):
        dark = INK
        if expr == "resting":
            for side in (-1, 1):
                x = bx + side * 7
                y = by - 4
                pygame.draw.lines(s, dark, False,
                                  [(x - 4, y), (x, y + 2), (x + 4, y)], 2)
            self._sprite_mouth(s, bx, by + 8, 0.0, "smile")
            return
        if expr == "exhausted":
            for side in (-1, 1):
                x = bx + side * 7
                y = by - 4
                pygame.draw.lines(s, dark, False,
                                  [(x - 4, y + 1), (x, y - 2), (x + 4, y + 1)], 2)
            self._sprite_mouth(s, bx, by + 8, 1.0, "pant")
            return

        blink = (t % 3.6) < 0.11
        eye_w = int(lerp(8, 11, men))
        eye_h = int(lerp(9, 5, men))
        sclera = mix(EYE_WHITE, DEMON_EYE, men)
        for side in (-1, 1):
            x = bx + side * 7
            y = by - 4
            if blink:
                pygame.draw.line(s, dark,
                                 (x - eye_w // 2, y), (x + eye_w // 2, y), 2)
                continue
            rect = pygame.Rect(0, 0, eye_w, eye_h)
            rect.center = (x, y)
            pygame.draw.ellipse(s, sclera, rect)
            pygame.draw.ellipse(s, dark, rect, 1)
            px = x + int(self.look[0] * 1.5)
            py = y + int(self.look[1] * 1.5)
            if expr == "focus":
                py = y + 1
            pupil_w = int(lerp(3, 2, men))
            pupil_h = int(lerp(4, eye_h - 1, men))
            prect = pygame.Rect(0, 0, max(2, pupil_w), max(3, pupil_h))
            prect.center = (px, py)
            pygame.draw.ellipse(s, dark, prect)
            if men < 0.7:
                pygame.draw.rect(s, EYE_WHITE, (x - 2, y - 2, 1, 1))

            brow = max(men, 0.45 if expr == "focus" else 0.0)
            if brow > 0.12:
                outer = (x + side * (eye_w // 2), y - eye_h // 2 - 1)
                inner = (x - side * (eye_w // 2),
                         y - eye_h // 2 - 1 + int(4 * brow))
                pygame.draw.line(s, dark, outer, inner, 2)

        if expr == "focus":
            self._sprite_mouth(s, bx, by + 8, men, "flat")
        elif expr == "tired":
            self._sprite_mouth(s, bx, by + 8, men, "tired")
        else:
            self._sprite_mouth(s, bx, by + 8, men, "smile")

    def _sprite_mouth(self, s, mx, my, men, style):
        if men >= 0.5 and style != "pant":
            k = (men - 0.5) / 0.5
            gw = int(lerp(8, 20, k))
            gh = int(lerp(3, 7, k))
            pygame.draw.ellipse(s, INK,
                                pygame.Rect(mx - gw // 2, my - gh // 2, gw, gh))
            teeth = 2 + int(3 * k)
            for i in range(teeth):
                fx = mx - gw // 2 + 2 + i * (gw - 4) // max(1, teeth - 1)
                pygame.draw.polygon(s, TOOTH, [(fx - 1, my - gh // 2),
                                               (fx + 1, my - gh // 2),
                                               (fx, my - gh // 2 + 3)])
                pygame.draw.polygon(s, TOOTH, [(fx - 1, my + gh // 2),
                                               (fx + 1, my + gh // 2),
                                               (fx, my + gh // 2 - 3)])
            return
        if style == "flat":
            pygame.draw.line(s, INK, (mx - 5, my), (mx + 5, my), 2)
        elif style == "tired":
            pygame.draw.line(s, INK, (mx - 4, my), (mx + 4, my - 1), 2)
        elif style == "pant":
            pygame.draw.ellipse(s, INK, pygame.Rect(mx - 3, my - 2, 6, 6))
        else:
            curve = 3 if style == "smile" else 1
            pygame.draw.lines(s, INK, False,
                              [(mx - 5, my), (mx, my + curve), (mx + 5, my)], 2)
            if style == "smile":
                pygame.draw.polygon(s, TOOTH, [(mx + 2, my - 1),
                                               (mx + 4, my - 1),
                                               (mx + 3, my + 2)])

    def _sprite_sweat(self, s, bx, by, t):
        for i, dx in enumerate((-14, 14)):
            phase = (t * 0.9 + i * 0.5) % 1.0
            x = bx + dx
            y = int(by - 8 + phase * 16)
            pygame.draw.polygon(s, SWEAT, [(x, y - 3), (x - 2, y), (x + 2, y)])

    def _sprite_zzz(self, s, bx, by, t):
        for i in range(3):
            phase = (t * 0.6 + i / 3.0) % 1.0
            size = 4 + i
            x = bx + 12 + int(phase * 8) + i * 4
            y = by - 12 - int(phase * 18) - i * 8
            col = (170 + i * 20, 210, 255)
            pygame.draw.line(s, col, (x, y), (x + size, y), 2)
            pygame.draw.line(s, col, (x + size, y), (x, y + size), 2)
            pygame.draw.line(s, col, (x, y + size), (x + size, y + size), 2)

    def _sprite_joy(self, s, bx, by, radius, t):
        pygame.draw.circle(s, self._accent(), (bx, by), radius + 4, 2)
        for i in range(6):
            angle = t * 2.2 + i * math.pi / 3
            rr = radius + 5 + 3 * math.sin(t * 3 + i)
            x = int(bx + math.cos(angle) * rr)
            y = int(by + math.sin(angle) * rr * 0.8)
            pygame.draw.rect(s, SPARK, (x - 1, y - 3, 2, 6))
            pygame.draw.rect(s, SPARK, (x - 3, y - 1, 6, 2))

    def _draw_timer(self, x, y):
        text = self.font_timer.render(
            PomodoroPet.format_time(self.pet.remaining), False,
            self._timer_color())
        self.screen.blit(text, text.get_rect(center=(x, y)))

    def _draw_energy(self):
        pygame.draw.rect(self.screen, shade(PANEL, 0.8), ENERGY_BAR,
                         border_radius=5)
        fill_w = int(ENERGY_BAR.width * clamp(self.pet.energy / 100.0, 0, 1))
        if fill_w > 0:
            pygame.draw.rect(self.screen, energy_color(self.pet.energy),
                             pygame.Rect(ENERGY_BAR.x, ENERGY_BAR.y, fill_w,
                                         ENERGY_BAR.height), border_radius=5)
        pygame.draw.rect(self.screen, shade(PANEL, 1.8), ENERGY_BAR, 1,
                         border_radius=5)
        label = self.font_tiny.render(
            f"energia {int(self.pet.energy)}%", False, MUTED)
        self.screen.blit(label, (ENERGY_BAR.x, ENERGY_BAR.y - 12))

    def _draw_cycles(self):
        label = self.font_tiny.render("ciclos", False, MUTED)
        self.screen.blit(label, label.get_rect(midleft=(ENERGY_BAR.x, CYCLES_Y)))
        for i in range(min(self.pet.cycles, 6)):
            pygame.draw.circle(self.screen, BREAK_ACCENT,
                               (ENERGY_BAR.x + 52 + i * 14, CYCLES_Y), 4)
        if self.pet.cycles > 6:
            extra = self.font_tiny.render(
                f"+{self.pet.cycles - 6}", False, MUTED)
            self.screen.blit(extra, (ENERGY_BAR.x + 52 + 6 * 14, CYCLES_Y - 6))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    demo = "--demo" in argv
    opaque = "--opaque" in argv
    if demo:
        window = PetWindow(focus_duration=6, break_duration=4, opaque=opaque)
        window.pet.start()
    else:
        window = PetWindow(opaque=opaque)
    window.run()


if __name__ == "__main__":
    main()
