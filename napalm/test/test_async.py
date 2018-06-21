import threading
import time
from unittest import TestCase
from unittest.mock import Mock

from twisted.internet import reactor

from napalm.async import Signal, Timeout, AbstractTimer, ThreadedTimer, TwistedTimer


class TestSignal(TestCase):

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
    timer = None

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
        # self.timer = Timeout(self.DELAY_SEC, self.REPEAT_COUNT, is_dispose_on_complete=True, name=self.TIMER_NAME)
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
    DELAY_SEC = .2
    DELAY_SEC_MULT_BEFORE = .5
    DELAY_SEC_MULT_AFTER = 1.5
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

    # Time line: [start] delay [before][timer][after] delay [before][timer][after] ...
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
        return cls.DELAY_SEC * (cls.DELAY_SEC_MULT_AFTER - 1)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # print("=setUpClass", threading.active_count())

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # print("=tearDownClass", threading.active_count())

    def setUp(self):
        # print("SETUP", threading.active_count(), threading.enumerate())

        self.callback = Mock()
        self.timer_handler = Mock()
        self.timer_complete_handler = Mock()

        AbstractTimer.resolution_sec = self.RESOLUTION_SEC
        self.timer = self.timer_class(self.callback, self.DELAY_SEC)
        self.timer.timer_signal.add(self.timer_handler)
        self.timer.timer_complete_signal.add(self.timer_complete_handler)
        # print("  SETUP")
        self.assertEqual(self.timer._timers, [])
        self.assertFalse(self.timer._is_ticking)

    def tearDown(self):
        # print("TEARDOWN")
        self.timer.dispose()
        self.timer._timers = []
        # print("  TEARDOWN", threading.active_count(), threading.enumerate())

    def test_simple_simulatation_for_2_repeat_counts(self):
        self.timer.repeat_count = 2
        
        self.assertFalse(self.timer.running)
        self.assertEqual(self.timer.current_count, 0)
        self.assertEqual(self.timer.get_elapsed_time(), 0)

        # Start-stop (no time elapsed)
        self.timer.start()
        # print("$$$$ before $$$$", self.timer.get_elapsed_time())
        self.timer.stop()
        # print("$$$$ before $$$$", self.timer.get_elapsed_time())
        self.assertFalse(self.timer.running)
        time.sleep(self.DELAY_SEC)

        # Start
        # t = time.time()
        # print("$$$$ before $$$$", time.time() - t, self.timer.get_elapsed_time())
        self.timer.start()
        # print("DELAYS:", self.DELAY_SEC, self.delay_before(), self.delay_after())
        # print("$$$$ Starting overwork $$$$", time.time() - t, self.timer.get_elapsed_time())

        self.assertTrue(self.timer.running)

        # (Before timer event)
        # time.sleep(self.delay_before())
        time.sleep(max((0, self.delay_before() - self.timer.get_elapsed_time())))

        # print("$$$1$", time.time() - t, self.timer.get_elapsed_time())
        self.assert_before_timer_event(0)

        # (After timer event)
        time.sleep(self.between_before_and_after())

        # print("$$$2$", time.time() - t, self.timer.get_elapsed_time())
        self.assert_after_timer_event(1)

        # (After second timer event - complete)
        time.sleep(self.DELAY_SEC)
        # print("$$$3$", time.time() - t, self.timer.get_elapsed_time())

        self.assert_after_timer_event(2, is_completed=True)

    def test_simulation_of_repeat_counts_and_reset_after_complete(self):
        self.timer.repeat_count = self.REPEAT_COUNT

        # Start
        self.timer.start()

        # (Initial time shift)
        time.sleep(self.between_timer_and_after())

        for i in range(self.REPEAT_COUNT):
            # (After timer event)
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

        # (Before timer event)
        time.sleep(self.delay_before())
        self.assert_before_timer_event(0)

        # (After timer event)
        time.sleep(self.between_before_and_after())
        self.assert_after_timer_event(1, True)

    def test_simulation_of_restart(self):
        # Start
        self.timer.restart()

        # (Before timer event)
        time.sleep(self.delay_before(2))
        self.assert_before_timer_event(1)

        # Restart just before timer event
        self.timer.restart()
        self.callback.reset_mock()
        self.timer_handler.reset_mock()

        # (Still before timer event)
        time.sleep(self.delay_before())
        self.assert_before_timer_event(0)

        # (After timer event)
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
        self.assertEqual(self.timer.current_count, 0)
        self.assertEqual(self.timer.get_elapsed_time(), 0)
        self.assertTrue(self.timer.is_start_zero_delay)

        # Start disposed timer
        self.timer.start()

        time.sleep(self.delay_after())

        self.assertFalse(self.timer.running)
        # self.assertGreater(self.timer.current_count, 1)
        # self.assertEqual(self.timer.current_count, 0)
        self.assertEqual(self.timer.current_count, 1)
        # self.assertGreater(self.timer.get_elapsed_time(), 0)
        # self.assertLess(self.timer.get_elapsed_time(), self.DELAY_SEC)
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
        self.timer._timer = Mock()  # (Mocking of _timer() method)
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

        # Tear down
        self.timer._timers.remove(self.timer)
        self.timer._stop_ticking()

    def test_tick(self):
        timer1 = self.timer_class(delay_sec=self.DELAY_SEC)
        timer1._timer = Mock()
        timer2 = self.timer_class(delay_sec=self.DELAY_SEC)
        timer2._timer = Mock()
        self.timer._timers.extend([timer1, timer2])

        # elapsed_time = 0
        self.timer._tick()

        timer1._timer.assert_not_called()
        timer2._timer.assert_not_called()

        # 0 < elapsed_time < delay
        timer1._start_time = time.time()
        timer1.elapsed_time = self.delay_before()
        timer2._start_time = time.time() - self.delay_before()
        timer2.elapsed_time = 0

        self.timer._tick()

        timer1._timer.assert_not_called()
        timer2._timer.assert_not_called()

        # 0 < elapsed_time < delay in one more combination
        timer1._start_time = time.time() - self.DELAY_SEC / 2
        timer1.elapsed_time = self.delay_before() / 2
        timer2._start_time = time.time() - self.delay_before() / 2
        timer2.elapsed_time = self.DELAY_SEC / 2

        self.timer._tick()

        timer1._timer.assert_not_called()
        timer2._timer.assert_not_called()

        # elapsed_time > delay
        # timer1._start_time = time.time()
        timer1.elapsed_time = self.delay_after()
        # timer2._start_time = time.time() - self.delay_after()
        # timer2.elapsed_time = 0
        timer2.elapsed_time = time.time() - self.delay_after()

        self.timer._tick()

        timer1._timer.assert_called_once()
        timer2._timer.assert_called_once()

        # elapsed_time >= delay
        # timer1._start_time = time.time() - self.delay_after() / 3 * 2
        # timer1.elapsed_time = self.delay_after() / 3
        # timer2._start_time = time.time() - self.delay_after() / 2
        # timer2.elapsed_time = self.delay_after() / 2
        timer1.elapsed_time = self.delay_after()
        timer2.elapsed_time = self.delay_after() * 2

        self.timer._tick()

        self.assertEqual(timer1._timer.call_count, 2)
        self.assertEqual(timer2._timer.call_count, 2)

        timer1.dispose()
        timer2.dispose()
        self.timer._timers.remove(timer1)
        self.timer._timers.remove(timer2)
        self.assertEqual(self.timer._timers, [])

    def test_elapsed_time(self):
        self.assertEqual(self.timer.delay_sec, self.DELAY_SEC)
        self.timer.repeat_count = 1
        self.timer.start()

        time.sleep(self.DELAY_SEC / 2)

        self.assertEqualRound(self.timer.elapsed_time, self.DELAY_SEC / 2)
        self.callback.assert_not_called()

        self.timer.elapsed_time = 0
        time.sleep(self.DELAY_SEC * 3 / 4)

        self.assertEqualRound(self.timer.elapsed_time, self.DELAY_SEC * 3 / 4)
        self.callback.assert_not_called()

        time.sleep(self.DELAY_SEC / 2)

        self.assertFalse(self.timer.running)
        self.assertEqualRound(self.timer.elapsed_time, self.DELAY_SEC)
        self.callback.assert_called_once()

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
        self.timer = self.timer_class(Mock(), 5, 7)
        self.timer.start()
        self.timer.timer_signal.add(Mock())
        self.timer.timer_complete_signal.add(Mock())

        self.assertTrue(self.timer.running)
        self.assertIn(self.timer, self.timer._timers)
        self.assertIsNotNone(self.timer.callback)
        self.assertEqual(self.timer.delay_sec, 5)
        self.assertEqual(self.timer.repeat_count, 7)
        self.assertEqual(len(self.timer.timer_signal), 1)
        self.assertEqual(len(self.timer.timer_complete_signal), 1)

        self.timer.dispose()

        self.assertFalse(self.timer.running)
        self.assertNotIn(self.timer, self.timer._timers)
        self.assertIsNone(self.timer.callback)
        self.assertEqual(self.timer.delay_sec, 0)
        self.assertEqual(self.timer.repeat_count, 0)
        self.assertEqual(len(self.timer.timer_signal), 0)
        self.assertEqual(len(self.timer.timer_complete_signal), 0)

    def test_get_elapsed_time(self):
        self.timer = self.timer_class(delay_sec=1)

        # (Timer started (_start_time > 0) and never yet stopped (elapsed_time > 0))
        self.timer.elapsed_time = 0
        self.timer._start_time = time.time() - 3

        self.assertEqual(round(self.timer.get_elapsed_time() * 100), 3 * 100)

        # (Timer stopped)
        self.timer.elapsed_time = 4
        self.timer._start_time = 0

        self.assertEqual(round(self.timer.get_elapsed_time() * 100), 4 * 100)

        # (Timer just started after stop)
        self.timer.elapsed_time = 4
        self.timer._start_time = time.time() - 0

        self.assertEqual(round(self.timer.get_elapsed_time() * 100), 4 * 100)

        # (Timer was started 3 sec ago after stop)
        self.timer.elapsed_time = 4
        self.timer._start_time = time.time() - 3

        self.assertEqual(round(self.timer.get_elapsed_time() * 100), 7 * 100)

    def test_start(self):
        # (Create - without params)
        self.timer = self.timer_class()

        self.assertFalse(self.timer.is_async_zero_delay)
        self.assertFalse(self.timer.running)
        self.assertNotIn(self.timer, self.timer._timers)
        self.assertEqual(self.timer.callback, None)
        self.assertEqual(self.timer.delay_sec, 0)
        self.assertEqual(self.timer.repeat_count, 0)
        self.assertEqualRound(self.timer.get_elapsed_time(), 0)

        # Start without params
        self.timer.start()

        self.assertFalse(self.timer.running)
        self.assertNotIn(self.timer, self.timer._timers)
        self.assertEqual(self.timer.callback, None)
        self.assertEqual(self.timer.delay_sec, 0)
        self.assertEqual(self.timer.repeat_count, 0)

        # Start with params
        callback = Mock()
        self.timer.start(callback, 5, 7)

        self.assertTrue(self.timer.running)
        self.assertIn(self.timer, self.timer._timers)
        self.assertEqual(self.timer.callback, callback)
        self.assertEqual(self.timer.delay_sec, 5)
        self.assertEqual(self.timer.repeat_count, 7)

        # Start without params again
        self.timer.start()

        self.assertTrue(self.timer.running)
        self.assertIn(self.timer, self.timer._timers)
        self.assertEqual(self.timer.callback, callback)
        self.assertEqual(self.timer.delay_sec, 5)
        self.assertEqual(self.timer.repeat_count, 7)

    def test_start_with_different_delay_sec(self):
        callback = Mock()
        self.timer = self.timer_class(callback)

        # delay_sec=0
        self.assertFalse(self.timer.running)
        self.assertFalse(self.timer.is_async_zero_delay)
        self.assertEqual(self.timer.delay_sec, 0)

        self.timer.start()

        self.assertFalse(self.timer.running)
        callback.assert_called_once()
        callback.reset_mock()

        # With repeat_count
        self.timer.reset()

        self.timer.start(repeat_count=3)

        self.assertFalse(self.timer.running)
        self.assertEqual(self.timer.repeat_count, 3)
        self.assertEqual(callback.call_count, 3)
        callback.reset_mock()
        self.timer.repeat_count = 0  # Default

        # delay_sec=0, is_async_zero_delay=True
        self.timer.reset()
        self.timer.is_async_zero_delay = True
        self.assertFalse(self.timer.running)
        self.assertEqual(self.timer.delay_sec, 0)
        self.assertEqual(self.timer.repeat_count, 0)
        # self.timer.resolution_sec = 1

        self.timer.start()

        # (Not stable - depends on environment)
        # self.assertTrue(self.timer.running)
        # callback.assert_not_called()
        # self.timer.resolution_sec = self.RESOLUTION_SEC

        time.sleep(self.timer.resolution_sec * 5)

        callback.assert_called_once()
        self.assertFalse(self.timer.running)
        callback.reset_mock()

        # delay_sec=0, is_start_zero_delay=False
        self.timer.stop()
        self.timer.is_start_zero_delay = False
        self.timer.start()

        self.assertFalse(self.timer.running)
        callback.assert_not_called()

        # Never start if delay_sec < -1
        # (is_start_zero_delay=False)
        self.timer.stop()
        self.timer.delay_sec = -1
        self.timer.start()

        self.assertFalse(self.timer.running)
        callback.assert_not_called()

        # (is_start_zero_delay=True)
        self.timer.stop()
        self.timer.is_start_zero_delay = True
        self.timer.start()

        self.assertFalse(self.timer.running)
        callback.assert_not_called()

    def test_start_after_complete(self):
        self.timer = self.timer_class(delay_sec=self.DELAY_SEC, repeat_count=1)

        # Start
        self.timer.start()
        time.sleep(self.delay_after() * 2)

        self.assertFalse(self.timer.running)
        self.assertNotIn(self.timer, self.timer._timers)
        self.assertEqualRound(self.timer.get_elapsed_time(), self.DELAY_SEC)
        # self.assertEqualRound(self.timer.get_elapsed_time(), 0)

        # Start after timer completed
        self.timer.start()

        self.assertFalse(self.timer.running)
        self.assertNotIn(self.timer, self.timer._timers)

    def test_start_stop_and_get_elapsed_time(self):
        self.timer = self.timer_class(delay_sec=self.delay_before() * 3)

        self.assertFalse(self.timer.running)
        self.assertNotIn(self.timer, self.timer._timers)
        self.assertEqualRound(self.timer.get_elapsed_time(), 0)

        # Start
        self.timer.start()
        time.sleep(self.delay_before())

        self.assertTrue(self.timer.running)
        self.assertIn(self.timer, self.timer._timers)
        self.assertEqualRound(self.timer.get_elapsed_time(), self.delay_before(), 2)

        # Stop (elapsed_time is not changing)
        self.timer.stop()
        time.sleep(self.delay_before())

        self.assertFalse(self.timer.running)
        self.assertNotIn(self.timer, self.timer._timers)
        self.assertEqualRound(self.timer.get_elapsed_time(), self.delay_before(), 2)

        # Start again - continue
        self.timer.start()
        time.sleep(self.delay_before())

        self.assertTrue(self.timer.running)
        self.assertIn(self.timer, self.timer._timers)
        self.assertGreater(self.timer.get_elapsed_time(), self.delay_before() * 2, 2)

        # Reset elapsed_time on timer event reached
        time.sleep(self.DELAY_SEC)
        self.assertEqualRound(self.timer.get_elapsed_time(), self.DELAY_SEC - self.delay_before(), 2)

    def test_stop(self):
        self.timer = self.timer_class(delay_sec=self.DELAY_SEC)

        # Stop not running timer
        time.sleep(self.DELAY_SEC / 4)
        self.timer.stop()
        time.sleep(self.DELAY_SEC / 4)

        self.assertFalse(self.timer.running)
        self.assertNotIn(self.timer, self.timer._timers)
        self.assertEqualRound(self.timer.elapsed_time, 0)
        self.assertEqual(self.timer._start_time, 0)

        # (Start)
        self.timer.start()

        self.assertTrue(self.timer.running)
        self.assertIn(self.timer, self.timer._timers)
        self.assertEqualRound(self.timer.elapsed_time, 0)
        self.assertEqualRound(self.timer._start_time, time.time())

        # Stop running timer
        time.sleep(self.DELAY_SEC / 2)
        self.timer.stop()
        time.sleep(self.DELAY_SEC / 4)

        self.assertFalse(self.timer.running)
        self.assertNotIn(self.timer, self.timer._timers)
        self.assertEqualRound(self.timer.elapsed_time, self.DELAY_SEC / 2)
        self.assertEqual(self.timer._start_time, 0)

    def test_reset(self):
        callback = Mock()
        self.timer = self.timer_class(callback, 5, 7)
        self.timer.stop = Mock()
        self.timer.current_count = 6
        self.timer.elapsed_time = 3
        self.timer._start_time = time.time() + 1

        self.assertEqual(self.timer.callback, callback)
        self.assertEqual(self.timer.delay_sec, 5)
        self.assertEqual(self.timer.repeat_count, 7)

        self.timer.reset()

        self.timer.stop.assert_called_once()
        self.assertEqual(self.timer.callback, callback)
        self.assertEqual(self.timer.delay_sec, 5)
        self.assertEqual(self.timer.repeat_count, 7)
        self.assertEqual(self.timer.current_count, 0)
        self.assertEqual(self.timer.elapsed_time, 0)
        self.assertEqual(self.timer._start_time, 0)

    def test_restart(self):
        self.timer = self.timer_class()
        self.timer.stop = Mock()
        self.timer.start = Mock()

        # Restart without params
        self.timer.restart()

        self.timer.start.assert_called_once_with(None, -1, -1)
        self.timer.stop.assert_called_once()

        # Restart with params
        callback = Mock()
        self.timer.restart(callback, 5, 7)

        self.timer.start.assert_called_with(callback, 5, 7)
        
    def test_pause_resume(self):
        self.timer = self.timer_class(delay_sec=1)
        
        self.assertFalse(self.timer.running)
        self.assertFalse(self.timer.paused)

        # Pause not running
        self.timer.pause()

        self.assertFalse(self.timer.running)
        self.assertFalse(self.timer.paused)
        
        # (Start)
        self.timer.start()
        
        self.assertTrue(self.timer.running)
        self.assertFalse(self.timer.paused)
        
        # Pause running
        self.timer.pause()
        
        self.assertFalse(self.timer.running)
        self.assertTrue(self.timer.paused)
        
        # Resume by start
        self.timer.start()
        
        self.assertTrue(self.timer.running)
        self.assertFalse(self.timer.paused)

        # Resume
        self.timer.pause()
        self.timer.resume()
        
        self.assertTrue(self.timer.running)
        self.assertFalse(self.timer.paused)
        
        # Call again
        self.timer.start = Mock()
        self.timer.resume()
        
        self.timer.start.assert_not_called()
        
        self.timer.pause()
        self.timer.stop = Mock()
        self.timer.pause()
        
        self.timer.stop.assert_not_called()

    def test_timer(self):
        callback = Mock()
        timer_handler = Mock()
        timer_complete_handler = Mock()
        self.timer = self.timer_class(callback, 5, 2)
        self.timer.timer_signal.add(timer_handler)
        self.timer.timer_complete_signal.add(timer_complete_handler)
        self.timer.stop = Mock()

        self.assertEqual(self.timer.current_count, 0)

        self.timer._timer()

        self.assertEqual(self.timer.current_count, 1)
        self.assertEqual(callback.call_count, 1)
        self.assertEqual(timer_handler.call_count, 1)
        self.assertEqual(timer_complete_handler.call_count, 0)
        self.timer.stop.assert_not_called()

        self.timer._timer()

        self.assertEqual(self.timer.current_count, 2)
        self.assertEqual(callback.call_count, 2)
        self.assertEqual(timer_handler.call_count, 2)
        self.assertEqual(timer_complete_handler.call_count, 1)
        self.timer.stop.assert_called_once()

        # Timer completed - No changes
        self.timer._timer()

        self.assertEqual(self.timer.current_count, 2)
        self.assertEqual(callback.call_count, 2)
        self.assertEqual(timer_handler.call_count, 2)
        self.assertEqual(timer_complete_handler.call_count, 1)
        self.timer.stop.assert_called_once()

    def test_callback_and_signals_with_args(self):
        callback = Mock()
        timer_handler = Mock()
        timer_complete_handler = Mock()
        self.timer = self.timer_class(callback, self.DELAY_SEC, 2, ["a", 5])
        self.assertEqual(self.timer.args, ["a", 5])
        self.timer.timer_signal.add(timer_handler)
        self.timer.timer_complete_signal.add(timer_complete_handler)

        # t = time.time()
        self.timer.start(args=[self.timer, "a", 5])
        # print("$$$", time.time() - t)

        self.assertEqual(self.timer.args, [self.timer, "a", 5])
        self.assertEqual(self.timer.current_count, 0)

        # print("$$$", time.time() - t)
        time.sleep(self.delay_before())
        # print("$$$", time.time() - t)

        self.assertEqual(self.timer.current_count, 0)
        callback.assert_not_called()
        timer_handler.assert_not_called()
        timer_complete_handler.assert_not_called()

        time.sleep(self.between_before_and_after())

        # 1
        self.assertEqual(self.timer.running, True)
        self.assertEqual(self.timer.current_count, 1)
        callback.assert_called_once_with(self.timer, "a", 5)
        timer_handler.assert_called_once_with(self.timer, "a", 5)
        timer_complete_handler.assert_not_called()

        self.timer.args = [self.timer, "a"]
        time.sleep(self.DELAY_SEC)

        # 2 - complete
        self.assertEqual(self.timer.running, False)
        self.assertEqual(self.timer.current_count, 2)
        callback.assert_called_with(self.timer, "a")
        timer_handler.assert_called_with(self.timer, "a")
        timer_complete_handler.assert_called_once_with(self.timer, "a")

    # Utility

    def assertEqualRound(self, value, expected, ndigits=2):
        # self.assertEqual(round(value * (10 ** ndigits)), round(expected * (10 ** ndigits)))
        self.assertLess(abs(value - expected), self.RESOLUTION_SEC * 2, str(value) + "<>" + str(expected))

    def assert_before_timer_event(self, current_count=0):
        self.assertEqual(self.timer.current_count, current_count)
        # self.assertEqual(round(self.timer.get_elapsed_time(), 2), round(self.delay_before(), 2))
        self.assertLess(abs(self.timer.get_elapsed_time() - self.delay_before()), self.timer.resolution_sec,
                        str(self.timer.get_elapsed_time()) + "<>" + str(self.delay_before()))
        self.assertEqual(self.callback.call_count, current_count)
        self.assertEqual(self.timer_handler.call_count, current_count)

        self.assertTrue(self.timer.running)
        self.timer_complete_handler.assert_not_called()

    def assert_after_timer_event(self, current_count=1, is_completed=False):
        self.assertEqual(self.timer.current_count, current_count)
        self.assertEqual(self.callback.call_count, current_count)
        self.assertEqual(self.timer_handler.call_count, current_count)

        if is_completed:
            self.assertFalse(self.timer.running)
            # self.assertEqual(round(self.timer.get_elapsed_time(), 1), self.timer.delay_sec * current_count)
            self.assertEqualRound(self.timer.get_elapsed_time(), self.DELAY_SEC)
            self.timer_complete_handler.assert_called_once_with()
        else:
            self.assertTrue(self.timer.running)
            # self.assertEqual(round(self.timer.get_elapsed_time(), 1), round(self.between_timer_and_after(), 1))
            self.assertLess(
                abs(self.timer.get_elapsed_time() - self.between_timer_and_after()), self.timer.resolution_sec,
                str(self.timer.get_elapsed_time()) + "<>" + str(self.between_timer_and_after()))
            self.timer_complete_handler.assert_not_called()


class TestThreadedTimer(TestCase, BaseTestTimer):
    timer_class = ThreadedTimer

    def setUp(self):
        BaseTestTimer.setUp(self)
        super().setUp()

    def tearDown(self):
        BaseTestTimer.tearDown(self)
        super().setUp()


class TestTwistedTimer(TestCase, BaseTestTimer):
    timer_class = TwistedTimer

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        if not reactor.running:
            thread = threading.Thread(target=reactor.run, name="twisted-reactor")
            thread.start()

    def setUp(self):
        BaseTestTimer.setUp(self)
        super().setUp()

    def tearDown(self):
        BaseTestTimer.tearDown(self)
        super().setUp()


# Slow - comment

class TestThreadedTimerWithBigResolution(TestThreadedTimer):
    RESOLUTION_SEC = .1
    DELAY_SEC = 1


class TestTwistedTimerWithBigResolution(TestTwistedTimer):
    RESOLUTION_SEC = .1
    DELAY_SEC = 1
