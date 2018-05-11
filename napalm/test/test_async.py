import time
from unittest import TestCase
from unittest.mock import Mock, MagicMock

from twisted.internet import reactor

from napalm.async import Signal, Timeout, AbstractTimer, ThreadedTimer, TwistedTimer


class TestSignal:  # (TestCase):
    def setUp(self):
        super().setUp()

        self.signal = Signal()

    def test_add_remove_dispatch(self):
        # Test add
        self.signal.add(self._handler)
        self.signal.add(self._handler)
        self.assertEqual(len(self.signal), 1)

        # Test dispatch
        self.signal.dispatch(1, 2, 3)

        # Test remove
        self.signal.remove(self._handler)
        self.assertEqual(len(self.signal), 0)
        self.signal.remove(self._handler)
        self.assertEqual(len(self.signal), 0)

    def test_add_remove_order_dispatch(self):
        self.string = ""
        # Test add
        self.signal.add(self._handler_str1)
        self.signal.add(self._handler_str2)

        # Test dispatch
        self.signal.dispatch(1, 2, 3)

        self.assertEqual(self.string, "str1STR2")
        self.signal.remove_all()

        self.string = ""
        # Test add
        self.signal.add(self._handler_str2)
        self.signal.add(self._handler_str1)

        # Test dispatch
        self.signal.dispatch(1, 2, 3)

        self.assertEqual(self.string, "STR2str1")
        self.signal.remove_all()

    def test_add_remove_during_dispatch(self):
        # Test add
        self.signal.add(self._adding_handler)
        self.signal.add(self._adding_handler)
        self.signal.add(self._removing_handler)
        self.signal.add(self._removing_handler)
        self.assertEqual(len(self.signal), 2)

        # Test dispatch
        self.signal.dispatch(1, 2, 3)

        # Test remove
        self.assertEqual(len(self.signal), 2)
        self.signal.remove(self._handler)
        self.signal.remove(self._adding_handler)
        self.assertEqual(len(self.signal), 0)

    def test_add_remove_all_during_dispatch(self):
        # Test add
        self.signal.add(self._adding_handler)
        self.signal.add(self._adding_handler)
        self.signal.add(self._removing_handler)
        self.signal.add(self._removing_handler)
        self.signal.add(self._removing_all_handler)
        self.signal.add(self._removing_all_handler)
        self.assertEqual(len(self.signal), 3)

        # Test dispatch
        self.signal.dispatch(1, 2, 3)

        # Test remove
        self.assertEqual(len(self.signal), 0)

    def test_add_remove_all_during_dispatch_in_different_order(self):
        # Test add
        self.signal.add(self._removing_all_handler)
        self.signal.add(self._removing_handler)
        self.signal.add(self._adding_handler)
        self.assertEqual(len(self.signal), 3)

        # Test dispatch
        self.signal.dispatch(1, 2, 3)

        # Test remove
        self.assertEqual(len(self.signal), 1)
        self.signal.remove(self._handler)
        self.assertEqual(len(self.signal), 0)

    def _handler(self, arg1, arg2, arg3, arg4=5):
        self.assertEqual(arg1, 1)
        self.assertEqual(arg2, 2)
        self.assertEqual(arg3, 3)
        self.assertEqual(arg4, 5)

    def _handler_str1(self, arg1, arg2, arg3, arg4=5):
        self.string += "str1"

    def _handler_str2(self, arg1, arg2, arg3, arg4=5):
        self.string += "STR2"

    def _adding_handler(self, arg1, arg2, arg3, arg4=5):
        self.signal.add(self._handler)

    def _removing_handler(self, arg1, arg2, arg3, arg4=5):
        self.signal.remove(self._removing_handler)

    def _removing_all_handler(self, arg1, arg2, arg3, arg4=5):
        self.signal.remove_all()


# Note: ASYNC tests - with delays!
class TestTimeout:  # (TestCase):

    def setUp(self):
        super().setUp()

        self.DELAY_SEC = .1
        self.DELAY_SEC_MULT = 1.05
        self.REPEAT_COUNT = 2
        self.TIMER_NAME = "some name"

        self.timer_dispatched_count = 0
        self.timer_complete_dispatched_count = 0

    def test_start_reset_stop_dispose_signals(self):
        self.timer = Timeout(self.DELAY_SEC, self.REPEAT_COUNT, is_dispose_on_complete=False, name=self.TIMER_NAME)

        # Assert initial
        self.assertEqual(self.timer.current_count, 0)
        self.assertEqual(self.timer.running, False)
        self.assertEqual(self.timer.delay_sec, self.DELAY_SEC)
        self.assertEqual(self.timer.repeat_count, self.REPEAT_COUNT)
        self.assertEqual(self.timer.name, self.TIMER_NAME)
        self.assertIsNotNone(self.timer.timer_signal)
        self.assertEqual(len(self.timer.timer_signal), 0)
        self.assertIsNotNone(self.timer.timer_complete_signal)
        self.assertEqual(len(self.timer.timer_complete_signal), 0)

        self.timer.timer_signal.add(self._timer_handler)
        self.timer.timer_complete_signal.add(self._timer_complete_handler)

        # Assert changes
        self.assertEqual(len(self.timer.timer_signal), 1)
        self.assertEqual(len(self.timer.timer_complete_signal), 1)

        self.timer.start()
        # Check there is nothing bad to call start twice
        self.timer.start()

        # Assert changes
        self.assertEqual(self.timer.running, True)

        # Wait a half of iteration
        time.sleep(self.DELAY_SEC * .5)
        # print("--AFTER SLEEP--", self.DELAY_SEC * .5)

        # Test start-stop-start
        self.timer.stop()
        # Check there is nothing bad to call stop twice
        self.timer.stop()

        time.sleep(self.DELAY_SEC * self.DELAY_SEC_MULT)
        # print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

        # Assert changes
        self.assertEqual(self.timer.running, False)

        # Start!
        self.timer.start()
        self.assertEqual(self.timer.running, True)
        self.assertEqual(self.timer.current_count, 0)
        self.assertEqual(self.timer_dispatched_count, 0)
        self.assertEqual(self.timer_complete_dispatched_count, 0)

        time.sleep(self.DELAY_SEC * self.DELAY_SEC_MULT)
        # print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

        # Assert timer_signal
        self.assertEqual(self.timer.running, True)
        self.assertEqual(self.timer.current_count, 1)
        self.assertEqual(self.timer_dispatched_count, 1)
        self.assertEqual(self.timer_complete_dispatched_count, 0)

        time.sleep(self.DELAY_SEC * self.DELAY_SEC_MULT)
        # print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

        # Assert timer_signal
        self.assertEqual(self.timer.running, False)
        self.assertEqual(self.timer.current_count, 2)
        self.assertEqual(self.timer_dispatched_count, 2)
        self.assertEqual(self.timer_complete_dispatched_count, 1)

        # Try to start again
        self.timer.start()
        self.assertEqual(self.timer.running, False)
        self.assertEqual(self.timer.current_count, 2)
        self.assertEqual(self.timer_dispatched_count, 2)
        self.assertEqual(self.timer_complete_dispatched_count, 1)

        # Test reset!
        self.timer.reset()
        self.assertEqual(self.timer.running, False)
        self.assertEqual(self.timer.current_count, 0)

        time.sleep(self.DELAY_SEC * self.DELAY_SEC_MULT)
        # print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

        # Assert not started on reset
        self.assertEqual(self.timer.running, False)
        self.assertEqual(self.timer.current_count, 0)

        # Start again!
        self.timer.start()
        self.assertEqual(self.timer.running, True)
        self.assertEqual(self.timer.current_count, 0)

        time.sleep(self.DELAY_SEC * self.DELAY_SEC_MULT)
        # print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

        # Assert timer_signal
        self.assertEqual(self.timer.running, True)
        self.assertEqual(self.timer.current_count, 1)
        self.assertEqual(self.timer_dispatched_count, 3)
        self.assertEqual(self.timer_complete_dispatched_count, 1)

        # Test stop in reset!
        self.timer.reset()
        self.assertEqual(self.timer.running, False)
        self.assertEqual(self.timer.current_count, 0)

        # Start again
        self.timer.start()
        self.assertEqual(self.timer.running, True)
        self.assertEqual(self.timer.current_count, 0)

        time.sleep(self.DELAY_SEC * self.DELAY_SEC_MULT)
        # print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

        # Assert timer_signal
        self.assertEqual(self.timer.running, True)
        self.assertEqual(self.timer.current_count, 1)
        self.assertEqual(self.timer_dispatched_count, 4)
        self.assertEqual(self.timer_complete_dispatched_count, 1)

        time.sleep(self.DELAY_SEC * self.DELAY_SEC_MULT)
        # print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

        # Assert timer_signal
        self.assertEqual(self.timer.running, False)
        self.assertEqual(self.timer.current_count, 2)
        self.assertEqual(self.timer_dispatched_count, 5)
        self.assertEqual(self.timer_complete_dispatched_count, 2)

        # Start again to test dispose
        self.timer.reset()
        self.timer.start()
        self.assertEqual(self.timer.running, True)

        time.sleep(self.DELAY_SEC * self.DELAY_SEC_MULT)
        # print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

        # Assert timer_signal
        self.assertEqual(self.timer.running, True)
        self.assertEqual(self.timer.current_count, 1)
        self.assertEqual(self.timer_dispatched_count, 6)
        self.assertEqual(self.timer_complete_dispatched_count, 2)

        # Dispose!
        self.timer.dispose()
        # Assert dispose
        self.assertEqual(self.timer.running, False)
        self.assertEqual(self.timer.current_count, 0)
        self.assertEqual(self.timer.delay_sec, self.DELAY_SEC)  # ?
        self.assertEqual(self.timer.repeat_count, self.REPEAT_COUNT)  # ?
        self.assertEqual(self.timer.name, self.TIMER_NAME)  # ?
        self.assertIsNotNone(self.timer.timer_signal)
        self.assertEqual(len(self.timer.timer_signal), 0)
        self.assertIsNotNone(self.timer.timer_complete_signal)
        self.assertEqual(len(self.timer.timer_complete_signal), 0)
        # These not changed
        self.assertEqual(self.timer_dispatched_count, 6)
        self.assertEqual(self.timer_complete_dispatched_count, 2)

    def test_add_handlers_in_constructor(self):
        self.timer = Timeout(self.DELAY_SEC, self.REPEAT_COUNT, self._timer_handler, self._timer_complete_handler)

        self.assertEqual(len(self.timer.timer_signal), 1)
        self.assertEqual(len(self.timer.timer_complete_signal), 1)

        with self.assertRaises(Exception):
            self.timer = Timeout(0)

        with self.assertRaises(Exception):
            self.timer = Timeout(-1)

    def test_infinite_timer(self):
        self.DELAY_SEC = .05
        self.timer = Timeout(self.DELAY_SEC)

        # Assert initial
        self.assertEqual(self.timer.current_count, 0)
        self.assertEqual(self.timer.repeat_count, 0)
        self.assertIsNone(self.timer.name)
        self.assertEqual(len(self.timer.timer_signal), 0)
        self.assertEqual(len(self.timer.timer_complete_signal), 0)

        self.timer.timer_signal.add(self._timer_handler)
        self.timer.timer_complete_signal.add(self._timer_complete_handler)

        self.timer.start()

        # Assert changes
        self.assertEqual(self.timer.running, True)
        self.assertEqual(self.timer_dispatched_count, 0)
        self.assertEqual(self.timer_complete_dispatched_count, 0)

        for i in range(10):
            time.sleep(self.DELAY_SEC * self.DELAY_SEC_MULT)
            # print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

            # Assert timer_signal
            self.assertEqual(self.timer.running, True)
            self.assertEqual(self.timer.current_count, i + 1, 'Try to restart tests')
            self.assertEqual(self.timer_dispatched_count, i + 1)
            self.assertEqual(self.timer_complete_dispatched_count, 0)
        # and so on...

        self.timer.dispose()

    def test_dispose_on_complete(self):
        self.REPEAT_COUNT = 3
        # self.show_game_winner_timer = Timeout(self.DELAY_SEC, self.REPEAT_COUNT, is_dispose_on_complete=True, name=self.TIMER_NAME)
        # Default: is_dispose_on_complete=True
        self.timer = Timeout(self.DELAY_SEC, self.REPEAT_COUNT, name=self.TIMER_NAME)

        # Assert initial
        self.assertEqual(self.timer.current_count, 0)
        self.assertEqual(self.timer.repeat_count, self.REPEAT_COUNT)
        self.assertEqual(self.timer.name, self.TIMER_NAME)
        self.assertEqual(len(self.timer.timer_signal), 0)
        self.assertEqual(len(self.timer.timer_complete_signal), 0)

        self.timer.timer_signal.add(self._timer_handler)
        self.timer.timer_complete_signal.add(self._timer_complete_handler)

        self.timer.start()

        # Assert changes
        self.assertEqual(self.timer.running, True)
        self.assertEqual(self.timer_dispatched_count, 0)
        self.assertEqual(self.timer_complete_dispatched_count, 0)

        for i in range(self.REPEAT_COUNT):
            time.sleep(self.DELAY_SEC * self.DELAY_SEC_MULT)
            # print("--AFTER SLEEP--", i,  self.DELAY_SEC * self.DELAY_SEC_MULT)

            if i + 1 < self.REPEAT_COUNT:
                # Assert timer_signal
                self.assertEqual(self.timer.running, True)
                self.assertEqual(self.timer.current_count, i + 1)
                self.assertEqual(self.timer_dispatched_count, i + 1)
                self.assertEqual(self.timer_complete_dispatched_count, 0)
            else:
                # Assert disposed!
                self.assertEqual(self.timer.running, False)
                self.assertEqual(self.timer.current_count, 0)
                self.assertEqual(self.timer_dispatched_count, i + 1)
                self.assertEqual(self.timer_complete_dispatched_count, 1)

    def _timer_handler(self):
        self.timer_dispatched_count += 1

    def _timer_complete_handler(self):
        self.timer_complete_dispatched_count += 1


class BaseTestTimer:
    timer_class = AbstractTimer

    RESOLUTION_SEC = .01
    DELAY_SEC = .1
    DELAY_SEC_MULT_BEFORE = .95
    DELAY_SEC_MULT_AFTER = 1.05
    REPEAT_COUNT = 1

    timer = None
    callback = None
    timer_handler = None
    timer_complete_handler = None

    assertFalse = None
    assertTrue = None
    assertEqual = None
    assertGreater = None
    assertLess = None
    assertIsNone = None
    assertIsNotNone = None
    assertIn = None
    assertNotIn = None

    # Time line: [start] delay [before][show_game_winner_timer][after] delay [before][show_game_winner_timer][after] ...
    @classmethod
    def delay_before(cls, repeat_count=1):
        if repeat_count < 1:
            return 0
        return cls.DELAY_SEC * (repeat_count - 1) + cls.DELAY_SEC * cls.DELAY_SEC_MULT_BEFORE

    @classmethod
    def delay_after(cls, repeat_count=1):
        if repeat_count < 1:
            return 0
        return cls.DELAY_SEC * (repeat_count - 1) + cls.DELAY_SEC * cls.DELAY_SEC_MULT_AFTER

    @classmethod
    def between_before_and_after(cls):
        return cls.DELAY_SEC * (cls.DELAY_SEC_MULT_AFTER - cls.DELAY_SEC_MULT_BEFORE)

    @classmethod
    def between_timer_and_after(cls):
        return cls.DELAY_SEC * (1 - cls.DELAY_SEC_MULT_AFTER)

    def setUp(self):
        self.callback = Mock()
        self.timer_handler = Mock()
        self.timer_complete_handler = Mock()

        self.timer = self.timer_class(self.callback, self.DELAY_SEC)
        self.timer.timer_signal.add(self.timer_handler)
        self.timer.timer_complete_signal.add(self.timer_complete_handler)

    def tearDown(self):
        self.timer.dispose()

    def test_simple_simulatation_for_2_repeat_counts(self):
        self.timer.repeat_count = 2
        
        self.assertFalse(self.timer.running)
        self.assertEqual(self.timer.current_count, 0)
        self.assertEqual(self.timer.get_elapsed_time(), 0)

        # Start-stop (no time elapsed)
        self.timer.start()
        self.timer.stop()
        self.assertFalse(self.timer.running)
        time.sleep(self.DELAY_SEC)

        # Start
        self.timer.start()

        self.assertTrue(self.timer.running)

        # (Before show_game_winner_timer event)
        time.sleep(self.delay_before())

        self.assert_before_timer_event(0)

        # (After show_game_winner_timer event)
        time.sleep(self.between_before_and_after())

        self.assert_after_timer_event(1)

        # (After second show_game_winner_timer event - complete)
        time.sleep(self.DELAY_SEC)

        self.assert_after_timer_event(2, is_completed=True)

    def test_simulation_of_repeat_counts_and_reset_after_complete(self):
        self.timer.repeat_count = self.REPEAT_COUNT

        # Start
        self.timer.start()

        # (Initial time shift)
        time.sleep(self.between_timer_and_after())

        for i in range(self.REPEAT_COUNT):
            # (After show_game_winner_timer event)
            time.sleep(self.DELAY_SEC)
            current_count = i + 1
            self.assert_after_timer_event(current_count, current_count == self.REPEAT_COUNT)

        # Test after complete

        self.callback.reset_mock()
        self.timer_handler.reset_mock()
        self.timer_complete_handler.reset_mock()

        # Try to start after complete
        self.timer.start()

        self.assertFalse(self.timer.running)
        self.assertEqual(self.timer.current_count, self.REPEAT_COUNT)
        self.callback.assert_not_called()
        self.timer_handler.assert_not_called()
        self.timer_complete_handler.assert_not_called()

        # Reset after complete
        self.timer.reset()

        self.assertFalse(self.timer.running)
        self.assertEqual(self.timer.current_count, 0)
        self.assertEqual(round(self.timer.get_elapsed_time(), 2), 0)

        # Start after reset
        self.timer.repeat_count = 1
        self.timer.start()

        # (Before show_game_winner_timer event)
        time.sleep(self.delay_before())
        self.assert_before_timer_event(0)

        # (After show_game_winner_timer event)
        time.sleep(self.between_before_and_after())
        self.assert_after_timer_event(1, True)

    def test_simulation_of_restart(self):
        # Start
        self.timer.restart()

        # (Before show_game_winner_timer event)
        time.sleep(self.delay_before(2))
        self.assert_before_timer_event(1)

        # Restart just before show_game_winner_timer event
        self.timer.restart()

        # (Still before show_game_winner_timer event)
        time.sleep(self.delay_before())
        self.assert_before_timer_event(0)

        # (After show_game_winner_timer event)
        time.sleep(self.between_before_and_after())
        self.assert_after_timer_event(1)

    def test_simulation_after_dispose(self):
        # Start
        self.timer.start()
        self.assertTrue(self.timer.running)

        # Dispose
        self.timer.dispose()

        self.assertFalse(self.timer.running)
        self.assertEqual(self.timer.delay_sec, 0)
        self.assertEqual(self.timer.repeat_count, 0)

        # Start disposed show_game_winner_timer
        self.timer.start()

        time.sleep(self.delay_after())

        self.assertTrue(self.timer.running)
        self.assertGreater(self.timer.current_count, 100)
        self.assertLess(self.timer.get_elapsed_time(), self.timer.resolution_sec)
        self.callback.assert_not_called()
        self.timer_handler.assert_not_called()
        self.timer_complete_handler.assert_not_called()

    # Unittests

    def test_add_and_remove_timer(self):
        self.assertEqual(self.timer._timers, [])
        self.assertFalse(self.timer._is_ticking)

        # Add
        self.timer._add_timer(self.timer)
        self.timer._add_timer(self.timer)

        self.assertEqual(self.timer._timers, [self.timer])
        self.assertTrue(self.timer._is_ticking)

        # Remove
        self.timer._remove_timer(self.timer)
        self.timer._remove_timer(self.timer)

        self.assertEqual(self.timer._timers, [])
        self.assertFalse(self.timer._is_ticking)

    def test_start_and_stop_ticking(self):
        self.timer.delay_sec = 0
        self.timer._timer = Mock()
        self.timer._timers.append(self.timer)

        self.assertFalse(self.timer._is_ticking)
        time.sleep(self.DELAY_SEC / 2)
        self.timer._timer.assert_not_called()

        # Start
        self.timer._start_ticking()
        self.timer._start_ticking()

        self.assertTrue(self.timer._is_ticking)
        time.sleep(self.DELAY_SEC / 2)
        self.timer._timer.assert_called()

        # Stop
        self.timer._stop_ticking()
        self.timer._stop_ticking()

        self.assertFalse(self.timer._is_ticking)
        self.timer._timer.reset_mock()
        time.sleep(self.DELAY_SEC / 2)
        self.timer._timer.assert_not_called()

    def test_tick(self):
        timer1 = self.timer_class(delay_sec=self.DELAY_SEC)
        timer1._timer = Mock()
        timer2 = self.timer_class(delay_sec=self.DELAY_SEC)
        timer2._timer = Mock()
        self.timer._timers = [timer1, timer2]

        # elapsed_time = 0
        self.timer._tick()

        timer1._timer.assert_not_called()
        timer2._timer.assert_not_called()

        # 0 < elapsed_time < delay
        timer1.elapsed_time = self.delay_before()
        timer1._start_time = 0
        timer2.elapsed_time = 0
        timer2._start_time = time.time() + self.delay_before()

        self.timer._tick()

        timer1._timer.assert_not_called()
        timer2._timer.assert_not_called()

        # 0 < elapsed_time < delay in one more combination
        timer1.elapsed_time = self.delay_before() / 2
        timer1._start_time = time.time() + self.DELAY_SEC / 2
        timer2.elapsed_time = self.DELAY_SEC / 2
        timer2._start_time = time.time() + self.delay_before() / 2

        self.timer._tick()

        timer1._timer.assert_not_called()
        timer2._timer.assert_not_called()

        # elapsed_time > delay
        timer1.elapsed_time = self.delay_after()
        timer1._start_time = 0
        timer2.elapsed_time = 0
        timer2._start_time = time.time() + self.delay_after()

        self.timer._tick()

        timer1._timer.assert_called_once()
        timer2._timer.assert_called_once()

        # elapsed_time >= delay
        timer1.elapsed_time = self.DELAY_SEC / 3
        timer1._start_time = time.time() + self.DELAY_SEC / 3 * 2
        timer2.elapsed_time = self.DELAY_SEC / 2
        timer2._start_time = time.time() + self.DELAY_SEC / 2

        self.timer._tick()

        self.assertEqual(timer1._timer.call_count, 2)
        self.assertEqual(timer2._timer.call_count, 2)

    def test_constructor(self):
        timer = self.timer_class()

        self.assertIsNone(timer.callback)
        self.assertEqual(timer.callback, None)
        self.assertEqual(timer.delay_sec, 0)
        self.assertEqual(timer.repeat_count, 0)
        self.assertIsNotNone(timer.timer_signal)
        self.assertIsNotNone(timer.timer_complete_signal)

        callback = Mock()
        timer = self.timer_class(callback, 5, 7)

        self.assertEqual(timer.callback, callback)
        self.assertEqual(timer.delay_sec, 5)
        self.assertEqual(timer.repeat_count, 7)
        self.assertIsNotNone(timer.timer_signal)
        self.assertIsNotNone(timer.timer_complete_signal)

    def test_dispose(self):
        timer = self.timer_class(Mock(), 5, 7)
        timer.start()
        timer.timer_signal.add(Mock())
        timer.timer_complete_signal.add(Mock())

        self.assertTrue(timer.running)
        self.assertIn(timer, timer._timers)
        self.assertIsNotNone(timer.callback)
        self.assertEqual(timer.delay_sec, 5)
        self.assertEqual(timer.repeat_count, 7)
        self.assertEqual(len(timer.timer_signal), 1)
        self.assertEqual(len(timer.timer_complete_signal), 1)

        timer.dispose()

        self.assertFalse(timer.running)
        self.assertNotIn(timer, timer._timers)
        self.assertIsNone(timer.callback)
        self.assertEqual(timer.delay_sec, 0)
        self.assertEqual(timer.repeat_count, 0)
        self.assertEqual(len(timer.timer_signal), 0)
        self.assertEqual(len(timer.timer_complete_signal), 0)

    def test_getelapsed_time(self):
        timer = self.timer_class()

        # (Timer started (_start_time > 0) and never yet stopped (elapsed_time > 0))
        timer.elapsed_time = 0
        timer._start_time = time.time() + 3

        self.assertEqual(round(timer.get_elapsed_time() * 100), 3 * 100)

        # (Timer stopped)
        timer.elapsed_time = 4
        timer._start_time = 0

        self.assertEqual(round(timer.get_elapsed_time() * 100), 4 * 100)

        # (Timer just started after stop)
        timer.elapsed_time = 4
        timer._start_time = time.time() + 0

        self.assertEqual(round(timer.get_elapsed_time() * 100), 4 * 100)

        # (Timer was started 3 sec ago after stop)
        timer.elapsed_time = 4
        timer._start_time = time.time() + 3

        self.assertEqual(round(timer.get_elapsed_time() * 100), 7 * 100)

    def test_start(self):
        # (Create - without params)
        timer = self.timer_class()

        self.assertFalse(timer.running)
        self.assertNotIn(timer, timer._timers)
        self.assertEqual(timer.callback, None)
        self.assertEqual(timer.delay_sec, 0)
        self.assertEqual(timer.repeat_count, 0)
        self.assertEqualRound(timer.get_elapsed_time(), 0)

        # Start without params
        timer.start()

        self.assertTrue(timer.running)
        self.assertIn(timer, timer._timers)
        self.assertEqual(timer.callback, None)
        self.assertEqual(timer.delay_sec, 0)
        self.assertEqual(timer.repeat_count, 0)

        # Start with params
        callback = Mock()
        timer.start(callback, 5, 7)

        self.assertEqual(timer.callback, callback)
        self.assertEqual(timer.delay_sec, 5)
        self.assertEqual(timer.repeat_count, 7)

        # Start without params again
        timer.start()

        self.assertEqual(timer.callback, callback)
        self.assertEqual(timer.delay_sec, 5)
        self.assertEqual(timer.repeat_count, 7)

    def test_start_with_different_delay_sec(self):
        timer = self.timer_class()

        self.assertFalse(timer.running)
        self.assertEqual(timer.delay_sec, 0)

        timer.start()

        self.assertTrue(timer.running)

        timer.stop()
        timer.is_start_zero_delay = False
        timer.start()

        self.assertFalse(timer.running)

        # Never start if delay_sec < -1
        # (is_start_zero_delay=False)
        timer.stop()
        timer.delay_sec = -1
        timer.start()

        self.assertFalse(timer.running)

        # (is_start_zero_delay=True)
        timer.stop()
        timer.is_start_zero_delay = True
        timer.start()

        self.assertFalse(timer.running)

    def test_start_after_complete(self):
        timer = self.timer_class(delay_sec=self.DELAY_SEC, repeat_count=1)

        # Start
        timer.start()
        time.sleep(self.delay_after())

        self.assertFalse(timer.running)
        self.assertNotIn(timer, timer._timers)
        self.assertEqualRound(timer.get_elapsed_time(), self.DELAY_SEC)

        # Start after show_game_winner_timer completed
        timer.start()

        self.assertFalse(timer.running)
        self.assertNotIn(timer, timer._timers)

    def test_start_stop_and_getelapsed_time(self):
        timer = self.timer_class(delay_sec=self.delay_before() * 3)

        self.assertFalse(timer.running)
        self.assertNotIn(timer, timer._timers)
        self.assertEqualRound(timer.get_elapsed_time(), 0)

        # Start
        timer.start()
        time.sleep(self.delay_before())

        self.assertTrue(timer.running)
        self.assertIn(timer, timer._timers)
        self.assertEqualRound(timer.get_elapsed_time(), self.delay_before())

        # Stop (elapsed_time is not changing)
        timer.stop()
        time.sleep(self.delay_before())

        self.assertFalse(timer.running)
        self.assertNotIn(timer, timer._timers)
        self.assertEqualRound(timer.get_elapsed_time(), self.delay_before())

        # Start again - continue
        timer.start()
        time.sleep(self.delay_before())

        self.assertTrue(timer.running)
        self.assertIn(timer, timer._timers)
        self.assertEqualRound(timer.get_elapsed_time(), self.delay_before() * 2)

        # Reset elapsed_time on show_game_winner_timer event reached
        time.sleep(self.DELAY_SEC)
        self.assertEqualRound(timer.get_elapsed_time(), self.DELAY_SEC - self.delay_before())

    def test_stop(self):
        timer = self.timer_class(delay_sec=self.DELAY_SEC)

        # Stop not running show_game_winner_timer
        time.sleep(self.DELAY_SEC / 4)
        timer.stop()
        time.sleep(self.DELAY_SEC / 4)

        self.assertFalse(timer.running)
        self.assertNotIn(timer, timer._timers)
        self.assertEqualRound(timer.elapsed_time, 0)
        self.assertEqual(timer._start_time, 0)

        # (Start)
        timer.start()

        self.assertTrue(timer.running)
        self.assertIn(timer, timer._timers)
        self.assertEqual(timer.elapsed_time, 0)
        self.assertEqualRound(timer._start_time, time.time())

        # Stop running show_game_winner_timer
        time.sleep(self.DELAY_SEC / 2)
        timer.stop()
        time.sleep(self.DELAY_SEC / 4)

        self.assertFalse(timer.running)
        self.assertNotIn(timer, timer._timers)
        self.assertEqualRound(timer.elapsed_time, self.DELAY_SEC / 2)
        self.assertEqual(timer._start_time, 0)

    def test_reset(self):
        callback = Mock()
        timer = self.timer_class(callback, 5, 7)
        timer.stop = Mock()
        timer.current_count = 6
        timer.elapsed_time = 3
        timer._start_time = time.time() + 1

        self.assertEqual(timer.callback, callback)
        self.assertEqual(timer.delay_sec, 5)
        self.assertEqual(timer.repeat_count, 7)

        timer.reset()

        timer.stop.assert_called_once()
        self.assertEqual(timer.callback, callback)
        self.assertEqual(timer.delay_sec, 5)
        self.assertEqual(timer.repeat_count, 7)
        self.assertEqual(timer.current_count, 0)
        self.assertEqual(timer.elapsed_time, 0)
        self.assertEqual(timer._start_time, 0)

    def test_restart(self):
        timer = self.timer_class()
        timer.stop = Mock()
        timer.start = Mock()

        # Restart without params
        timer.restart()

        timer.start.assert_called_once_with(None, -1, -1)
        timer.stop.assert_called_once()

        # Restart with params
        callback = Mock()
        timer.restart(callback, 5, 7)

        timer.start.assert_called_with(callback, 5, 7)
        
    def test_pause_resume(self):
        timer = self.timer_class()
        
        self.assertFalse(timer.running)
        self.assertFalse(timer.paused)

        # Pause not running
        timer.pause()

        self.assertFalse(timer.running)
        self.assertFalse(timer.paused)
        
        # (Start)
        timer.start()
        
        self.assertTrue(timer.running)
        self.assertFalse(timer.paused)
        
        # Pause running
        timer.pause()
        
        self.assertFalse(timer.running)
        self.assertTrue(timer.paused)
        
        # Resume by start
        timer.start()
        
        self.assertTrue(timer.running)
        self.assertFalse(timer.paused)

        # Resume
        timer.pause()
        timer.resume()
        
        self.assertTrue(timer.running)
        self.assertFalse(timer.paused)
        
        # Call again
        timer.start = Mock()
        timer.resume()
        
        timer.start.assert_not_called()
        
        timer.pause()
        timer.stop = Mock()
        timer.pause()
        
        timer.stop.assert_not_called()

    def test_timer(self):
        callback = Mock()
        timer_handler = Mock()
        timer_complete_handler = Mock()
        timer = self.timer_class(callback, 5, 2)
        timer.timer_signal.add(timer_handler)
        timer.timer_complete_signal.add(timer_complete_handler)
        timer.stop = Mock()

        self.assertEqual(timer.current_count, 0)

        timer._timer()

        self.assertEqual(timer.current_count, 1)
        self.assertEqual(callback.call_count, 1)
        self.assertEqual(timer_handler.call_count, 1)
        self.assertEqual(timer_complete_handler.call_count, 0)
        timer.stop.assert_not_called()

        timer._timer()

        self.assertEqual(timer.current_count, 2)
        self.assertEqual(callback.call_count, 2)
        self.assertEqual(timer_handler.call_count, 2)
        self.assertEqual(timer_complete_handler.call_count, 1)
        timer.stop.assert_called_once()

        # Timer completed - No changes
        timer._timer()

        self.assertEqual(timer.current_count, 2)
        self.assertEqual(callback.call_count, 2)
        self.assertEqual(timer_handler.call_count, 2)
        self.assertEqual(timer_complete_handler.call_count, 1)
        timer.stop.assert_called_once()

    # Utility

    def assertEqualRound(self, value, expected, ndigits=2):
        self.assertEqual(round(value * (10 ** ndigits)), round(expected * (10 ** ndigits)))

    def assert_before_timer_event(self, current_count=0):
        self.assertEqual(self.timer.current_count, current_count)
        self.assertEqual(round(self.timer.get_elapsed_time(), 2), round(self.delay_before(), 2))
        self.assertEqual(self.callback.call_count, current_count)
        self.assertEqual(self.timer_handler.call_count, current_count)

        self.assertTrue(self.timer.running)
        self.timer_complete_handler.assert_not_called()

    def assert_after_timer_event(self, current_count=1, is_completed=False):
        self.assertEqual(self.timer.current_count, current_count)
        self.assertEqual(round(self.timer.get_elapsed_time(), 2), round(self.between_timer_and_after(), 2))
        self.assertEqual(self.callback.call_count, current_count)
        self.assertEqual(self.timer_handler.call_count, current_count)

        if is_completed:
            self.assertFalse(self.timer.running)
            self.timer_complete_handler.assert_called_once_with()
        else:
            self.assertTrue(self.timer.running)
            self.timer_complete_handler.assert_not_called()


class TestThreadedTimer(TestCase, BaseTestTimer):
    timer_class = ThreadedTimer

    def setUp(self):
        BaseTestTimer.setUp(self)
        super().setUp()

    def tearDown(self):
        BaseTestTimer.tearDown(self)
        super().setUp()


# class TestTwistedTimer(TestCase, BaseTestTimer):
#     timer_class = TwistedTimer
#
#     @classmethod
#     def setUpClass(cls):
#         super().setUpClass()
#
#         if not reactor.running:
#             reactor.run()
#
#     def setUp(self):
#         BaseTestTimer.setUp(self)
#         super().setUp()
#
#     def tearDown(self):
#         BaseTestTimer.tearDown(self)
#         super().setUp()


# Slow - comment

# class TestThreadedTimerWithBigResolution(TestThreadedTimer):
#     RESOLUTION_SEC = 1
#     DELAY_SEC = 1
#
#
# class TestTwistedTimerWithBigResolution(TestTwistedTimer):
#     RESOLUTION_SEC = 1
#     DELAY_SEC = 1
