import pytest

from pet import (
    PomodoroPet, FOCUS,
    FOCUS_DONE, BREAK_DONE, BREAK_STARTED,
)


@pytest.fixture
def pet():
    return PomodoroPet(focus_duration=100, break_duration=40,
                       start_energy=85, focus_cost=40, break_restore=40)


class TestSkipWhileAwaiting:
    def test_skip_while_awaiting_is_noop(self, pet):
        assert pet.skip() == FOCUS_DONE
        assert pet.cycles == 1
        # The phase already finished: skipping again must not finish it
        # a second time (no duplicate event, no extra cycle).
        assert pet.skip() is None
        assert pet.awaiting is True
        assert pet.cycles == 1

    def test_skip_while_awaiting_break_is_noop(self, pet):
        pet.skip()
        pet.advance()
        assert pet.skip() == BREAK_DONE
        assert pet.skip() is None

    def test_skip_after_advance_still_works(self, pet):
        pet.skip()
        assert pet.skip() is None
        assert pet.advance() == BREAK_STARTED
        assert pet.phase != FOCUS
