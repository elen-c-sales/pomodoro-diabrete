import pytest

from pet import (
    PomodoroPet, FOCUS, BREAK,
    FOCUS_DONE, BREAK_DONE, BREAK_STARTED, FOCUS_STARTED,
)


@pytest.fixture
def pet():
    return PomodoroPet(focus_duration=100, break_duration=40,
                       start_energy=85, focus_cost=40, break_restore=40)


# --- format_time ---
class TestFormatTime:
    def test_zero(self):
        assert PomodoroPet.format_time(0) == "00:00"

    def test_seconds_only(self):
        assert PomodoroPet.format_time(45) == "00:45"

    def test_minutes_only(self):
        assert PomodoroPet.format_time(120) == "02:00"

    def test_minutes_and_seconds(self):
        assert PomodoroPet.format_time(90) == "01:30"

    def test_25_minutes(self):
        assert PomodoroPet.format_time(25 * 60) == "25:00"

    def test_negative_is_clamped(self):
        assert PomodoroPet.format_time(-5) == "00:00"


# --- estado inicial ---
class TestInitialState:
    def test_defaults(self):
        p = PomodoroPet()
        assert p.phase == FOCUS
        assert p.remaining == 25 * 60
        assert p.running is False
        assert p.awaiting is False
        assert p.cycles == 0
        assert p.energy == 85

    def test_starts_with_focus_face(self, pet):
        assert pet.mood == "focus"

    def test_next_phase(self, pet):
        assert pet.next_phase == BREAK
        pet.skip()
        pet.advance()
        assert pet.next_phase == FOCUS

    def test_phase_label(self, pet):
        assert pet.phase_label == "FOCO"
        pet.skip()
        pet.advance()
        assert pet.phase_label == "PAUSA"


# --- controles ---
class TestControls:
    def test_toggle_running(self, pet):
        assert pet.toggle() is None
        assert pet.running is True
        assert pet.toggle() is None
        assert pet.running is False

    def test_toggle_advances_when_awaiting(self, pet):
        pet.skip()  # foco encerrado -> aguardando
        assert pet.awaiting is True
        assert pet.toggle() == BREAK_STARTED
        assert pet.phase == BREAK
        assert pet.running is True
        assert pet.awaiting is False

    def test_advance_without_awaiting_is_noop(self, pet):
        assert pet.advance() is None
        assert pet.phase == FOCUS

    def test_advance_break_to_focus(self, pet):
        pet.skip()
        pet.advance()               # FOCO -> PAUSA
        pet.skip()                  # pausa encerrada -> aguardando
        assert pet.toggle() == FOCUS_STARTED
        assert pet.phase == FOCUS

    def test_reset_restores_everything(self, pet):
        pet.start()
        pet.remaining = 3
        pet.energy = 10
        pet.cycles = 4
        pet.awaiting = True
        pet.reset()
        assert pet.remaining == 100
        assert pet.energy == 85
        assert pet.cycles == 0
        assert pet.phase == FOCUS
        assert pet.running is False
        assert pet.awaiting is False

    def test_skip_finishes_focus(self, pet):
        assert pet.skip() == FOCUS_DONE
        assert pet.awaiting is True
        assert pet.running is False
        assert pet.remaining == 0
        assert pet.cycles == 1

    def test_skip_finishes_break(self, pet):
        pet.skip()
        pet.advance()
        assert pet.skip() == BREAK_DONE
        assert pet.awaiting is True


# --- simulacao ---
class TestTick:
    def test_paused_does_nothing(self, pet):
        pet.energy = 50
        assert pet.tick(10) == []
        assert pet.energy == 50
        assert pet.remaining == 100

    def test_focus_drains_energy(self, pet):
        pet.start()
        assert pet.tick(50) == []
        assert pet.energy == 65       # 85 - 40 * (50/100)
        assert pet.remaining == 50
        assert pet.phase == FOCUS

    def test_focus_end_awaits_does_not_auto_advance(self, pet):
        pet.start()
        pet.tick(50)
        events = pet.tick(50)
        assert events == [FOCUS_DONE]
        assert pet.phase == FOCUS      # ainda no foco, esperando o usuario
        assert pet.awaiting is True
        assert pet.running is False
        assert pet.energy == 45
        assert pet.cycles == 1

    def test_break_restores_energy(self, pet):
        pet.start()
        pet.tick(100)                 # encerra o foco
        pet.advance()                 # usuario marca a pausa
        pet.tick(40)
        assert pet.energy == 85       # 45 + 40
        assert pet.phase == BREAK

    def test_break_end_awaits(self, pet):
        pet.start()
        pet.tick(100)
        pet.advance()
        assert pet.tick(40) == [BREAK_DONE]
        assert pet.awaiting is True
        assert pet.cycles == 1

    def test_energy_is_clamped(self, pet):
        pet.energy = 95
        pet.start()
        pet.skip()
        pet.advance()
        pet.tick(40)
        assert pet.energy == 100

    def test_overshoot_only_drains_remaining_time(self, pet):
        pet.remaining = 10
        pet.start()
        pet.tick(1000)                # so 10s contam para a energia
        assert pet.energy == pytest.approx(85 - 40 * 0.1)
        assert pet.awaiting is True

    def test_tick_while_awaiting_does_nothing(self, pet):
        pet.skip()
        assert pet.tick(50) == []
        assert pet.remaining == 0


# --- consultas ---
class TestQueries:
    def test_progress(self, pet):
        pet.remaining = 25
        assert pet.progress == pytest.approx(0.75)

    def test_progress_full_when_awaiting(self, pet):
        pet.skip()
        assert pet.progress == 1.0

    def test_duration_follows_phase(self, pet):
        assert pet.duration == 100
        pet.skip()
        pet.advance()
        assert pet.duration == 40

    @pytest.mark.parametrize("energy,mood", [
        (0, "exhausted"),
        (20, "exhausted"),
        (21, "tired"),
        (45, "tired"),
    ])
    def test_low_moods_regardless_of_phase(self, pet, energy, mood):
        pet.energy = energy
        assert pet.mood == mood
        pet.skip()
        pet.advance()
        assert pet.mood == mood

    def test_focus_mood_while_working(self, pet):
        pet.energy = 90
        assert pet.mood == "focus"
        pet.energy = 60
        assert pet.mood == "focus"

    def test_break_mood_recovers(self, pet):
        pet.skip()
        pet.advance()
        pet.energy = 60
        assert pet.mood == "ok"
        pet.energy = 90
        assert pet.mood == "happy"

    def test_resting_only_during_running_break(self, pet):
        pet.skip()
        pet.advance()
        assert pet.phase == BREAK
        assert pet.resting is True
        pet.pause()
        assert pet.resting is False
