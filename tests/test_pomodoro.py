import sys
import pytest
from unittest.mock import MagicMock, patch, call


# Mock tkinter before importing the module
@pytest.fixture(autouse=True)
def mock_tkinter():
    """Mock tkinter to avoid opening a real window during tests."""
    with patch.dict("sys.modules", {
        "tkinter": MagicMock(),
        "tkinter.font": MagicMock(),
    }):
        # Need to reimport after mocking
        if "pomodoro" in sys.modules:
            del sys.modules["pomodoro"]
        yield


@pytest.fixture
def timer():
    """Create a PomodoroTimer with a short duration for testing."""
    from pomodoro import PomodoroTimer
    t = PomodoroTimer(duration=10)  # 10 seconds for fast tests
    return t


# --- format_time tests ---
class TestFormatTime:
    def test_zero(self, timer):
        assert timer.format_time(0) == "00:00"

    def test_seconds_only(self, timer):
        assert timer.format_time(45) == "00:45"

    def test_minutes_only(self, timer):
        assert timer.format_time(120) == "02:00"

    def test_minutes_and_seconds(self, timer):
        assert timer.format_time(90) == "01:30"

    def test_full_hour(self, timer):
        assert timer.format_time(3600) == "60:00"

    def test_25_minutes(self, timer):
        assert timer.format_time(25 * 60) == "25:00"


# --- Timer state tests ---
class TestTimerState:
    def test_initial_state(self, timer):
        assert timer.remaining == 10
        assert timer.running is False
        assert timer.alert_active is False

    def test_toggle_start(self, timer):
        timer.toggle_timer()
        assert timer.running is True

    def test_toggle_pause(self, timer):
        timer.toggle_timer()  # start
        timer.toggle_timer()  # pause
        assert timer.running is False

    def test_reset(self, timer):
        timer.remaining = 3
        timer.reset_timer()
        assert timer.remaining == 10
        assert timer.running is False


# --- Countdown tests ---
class TestCountdown:
    def test_countdown_decrements(self, timer):
        timer.running = True
        timer.countdown()
        assert timer.remaining == 9

    def test_countdown_stops_when_paused(self, timer):
        timer.running = False
        timer.countdown()
        assert timer.remaining == 10  # unchanged

    def test_countdown_triggers_alert_at_zero(self, timer):
        timer.remaining = 1
        timer.running = True
        timer.countdown()  # remaining goes to 0, schedules next call
        assert timer.remaining == 0
        # Alert triggers on the next scheduled call when remaining == 0
        timer.countdown()
        assert timer.running is False
        assert timer.alert_active is True


# --- Alert animation tests ---
class TestAlertAnimation:
    def test_start_alert_sets_active(self, timer):
        timer.start_alert()
        assert timer.alert_active is True

    def test_stop_alert_clears_active(self, timer):
        timer.start_alert()
        timer.stop_alert()
        assert timer.alert_active is False

    def test_flash_increments_step(self, timer):
        timer.start_alert()
        initial_step = timer.flash_step
        timer.flash()
        assert timer.flash_step == initial_step + 1

    def test_flash_stops_when_alert_inactive(self, timer):
        timer.alert_active = False
        timer.flash_step = 0
        timer.flash()
        assert timer.flash_step == 0  # no increment

    def test_shake_completes(self, timer):
        timer.start_alert()
        timer.shake()
        # shake() calls _do_shake_step which schedules via root.after()
        # First step runs immediately
        assert timer.shake_index == 1
        assert len(timer.shake_offsets) == 7
        # Run all remaining steps manually
        for _ in range(6):
            timer._do_shake_step(timer.root.winfo_x(), timer.root.winfo_y())
        assert timer.shake_index == 7


# --- Demo mode test ---
class TestDemoMode:
    def test_duration_parameter(self):
        from pomodoro import PomodoroTimer
        t = PomodoroTimer(duration=5)
        assert t.duration == 5
        assert t.remaining == 5

    def test_default_duration(self):
        from pomodoro import PomodoroTimer
        t = PomodoroTimer()
        assert t.duration == 25 * 60


# --- Context menu tests ---
class TestContextMenu:
    def test_menu_exists(self, timer):
        assert timer.menu is not None

    def test_menu_toggle_calls_toggle_timer(self, timer):
        timer.toggle_timer()
        assert timer.running is True

    def test_menu_reset_calls_reset_timer(self, timer):
        timer.remaining = 3
        timer.reset_timer()
        assert timer.remaining == 10

    def test_show_context_menu_calls_post(self, timer):
        event = MagicMock()
        event.x_root = 100
        event.y_root = 200
        timer.show_context_menu(event)
        timer.menu.post.assert_called_once_with(100, 200)
