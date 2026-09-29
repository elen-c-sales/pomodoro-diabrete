"""Smoke tests do app Pygame rodando headless (driver de video dummy)."""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest

from pet import FOCUS, BREAK
from pomodoro import PetWindow, energy_color, clamp, mix, shade


@pytest.fixture
def window():
    w = PetWindow(focus_duration=2, break_duration=1)
    yield w
    w.running = False


class TestHelpers:
    def test_clamp(self):
        assert clamp(5, 0, 10) == 5
        assert clamp(-1, 0, 10) == 0
        assert clamp(99, 0, 10) == 10

    def test_mix(self):
        assert mix((0, 0, 0), (10, 20, 30), 0.5) == (5, 10, 15)

    def test_shade(self):
        assert shade((100, 100, 100), 0.5) == (50, 50, 50)

    def test_energy_color_greener_when_full(self):
        assert energy_color(100)[1] > energy_color(0)[1]


class TestExpression:
    def test_starts_focused(self, window):
        assert window._expression() == "focus"

    def test_tired_and_exhausted(self, window):
        window.pet.energy = 30
        assert window._expression() == "tired"
        window.pet.energy = 10
        assert window._expression() == "exhausted"

    def test_resting_during_break(self, window):
        window.pet.skip()
        window.pet.advance()
        window.pet.energy = 50
        assert window._expression() == "resting"

    def test_wakes_up_recovered(self, window):
        window.pet.skip()
        window.pet.advance()
        window.pet.energy = 80
        assert window._expression() == "happy"


class TestActionLabel:
    def test_start_focus(self, window):
        assert window._action_label() == "iniciar foco"

    def test_running(self, window):
        window.pet.start()
        assert window._action_label() == "pausar"

    def test_resume_when_paused(self, window):
        window.pet.start()
        window.pet.tick(0.5)
        window.pet.pause()
        assert window._action_label() == "retomar"

    def test_start_break(self, window):
        window.pet.skip()
        assert window._action_label() == "comecar pausa"


class TestJoyAnimation:
    def test_break_starts_with_joy(self, window):
        window.pet.skip()             # foco encerrado, aguardando
        window._primary_action()      # marca o inicio da pausa
        assert window.pet.phase == BREAK
        assert window.pet.running is True
        assert window.joy > 0

    def test_no_joy_when_starting_focus(self, window):
        window.pet.start()
        assert window.joy == 0

    def test_joy_decays(self, window):
        window.pet.skip()
        window._primary_action()
        window._update(0.5)
        assert 0 < window.joy < 1.8


class TestRender:
    def test_draw_runs_for_every_mood(self, window):
        for energy in (0, 15, 30, 50, 70, 90, 100):
            window.pet.energy = energy
            window._draw()

    def test_draw_during_break(self, window):
        window.pet.skip()
        window.pet.advance()
        window.pet.energy = 60
        window._draw()
        window.pet.energy = 90
        window._draw()

    def test_draw_awaiting_and_alert(self, window):
        window.pet.skip()
        window.alert = 1.6
        window._draw()

    def test_draw_with_joy(self, window):
        window.pet.skip()
        window._primary_action()
        window._draw()

    def test_draw_expanded_layout(self, window):
        window.reveal = 1.0
        window.pet.start()
        window.pet.energy = 60
        window._draw()

    def test_draw_expanded_awaiting(self, window):
        window.reveal = 1.0
        window.pet.skip()
        window.alert = 1.6
        window._draw()

    def test_update_awaits_after_focus(self, window):
        window.pet.start()
        for _ in range(130):          # 2s de foco + folga
            window._update(1 / 60)
        assert window.pet.awaiting is True
        assert window.pet.phase == FOCUS   # nao troca sozinho
        assert window.alert > 0


class TestOverlay:
    def test_expanded_threshold(self, window):
        window.reveal = 0.0
        assert window.expanded is False
        window.reveal = 1.0
        assert window.expanded is True

    def test_reveal_clamped_by_update(self, window):
        for _ in range(200):
            window._update(1 / 60)
        assert 0.0 <= window.reveal <= 1.0

    def test_pet_rect_follows_layout(self, window):
        window.reveal = 0.0
        compact = window._pet_rect().center
        window.reveal = 1.0
        assert window._pet_rect().center != compact

    def test_opaque_mode_uses_solid_background(self):
        from pomodoro import BG
        w = PetWindow(focus_duration=2, break_duration=1, opaque=True)
        assert w.base == BG
        w.running = False
