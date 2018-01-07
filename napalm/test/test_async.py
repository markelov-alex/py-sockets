import time
from unittest import TestCase

from napalm.async import Signal, Timer


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

        print("test_add_remove_during_dispatch")
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

        print("test_add_remove_all_during_dispatch")
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
class TestTimer(TestCase):

    def setUp(self):
        super().setUp()

        self.DELAY_SEC = .1
        self.DELAY_SEC_MULT = 1.05
        self.REPEAT_COUNT = 2
        self.TIMER_NAME = "some name"

        self.timer_dispatched_count = 0
        self.timer_complete_dispatched_count = 0

    def test_start_reset_stop_dispose_signals(self):
        self.timer = Timer(self.DELAY_SEC, self.REPEAT_COUNT, is_dispose_on_complete=False, name=self.TIMER_NAME)

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
        print("--AFTER SLEEP--", self.DELAY_SEC * .5)

        # Test start-stop-start
        self.timer.stop()
        # Check there is nothing bad to call stop twice
        self.timer.stop()

        time.sleep(self.DELAY_SEC * self.DELAY_SEC_MULT)
        print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

        # Assert changes
        self.assertEqual(self.timer.running, False)

        # Start!
        self.timer.start()
        self.assertEqual(self.timer.running, True)
        self.assertEqual(self.timer.current_count, 0)
        self.assertEqual(self.timer_dispatched_count, 0)
        self.assertEqual(self.timer_complete_dispatched_count, 0)

        time.sleep(self.DELAY_SEC * self.DELAY_SEC_MULT)
        print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

        # Assert timer_signal
        self.assertEqual(self.timer.running, True)
        self.assertEqual(self.timer.current_count, 1)
        self.assertEqual(self.timer_dispatched_count, 1)
        self.assertEqual(self.timer_complete_dispatched_count, 0)

        time.sleep(self.DELAY_SEC * self.DELAY_SEC_MULT)
        print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

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
        print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

        # Assert not started on reset
        self.assertEqual(self.timer.running, False)
        self.assertEqual(self.timer.current_count, 0)

        # Start again!
        self.timer.start()
        self.assertEqual(self.timer.running, True)
        self.assertEqual(self.timer.current_count, 0)

        time.sleep(self.DELAY_SEC * self.DELAY_SEC_MULT)
        print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

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
        print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

        # Assert timer_signal
        self.assertEqual(self.timer.running, True)
        self.assertEqual(self.timer.current_count, 1)
        self.assertEqual(self.timer_dispatched_count, 4)
        self.assertEqual(self.timer_complete_dispatched_count, 1)

        time.sleep(self.DELAY_SEC * self.DELAY_SEC_MULT)
        print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

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
        print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

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
        self.timer = Timer(self.DELAY_SEC, self.REPEAT_COUNT, self._timer_handler, self._timer_complete_handler)

        self.assertEqual(len(self.timer.timer_signal), 1)
        self.assertEqual(len(self.timer.timer_complete_signal), 1)

        with self.assertRaises(Exception):
            self.timer = Timer(0)

        with self.assertRaises(Exception):
            self.timer = Timer(-1)

    def test_infinite_timer(self):
        self.DELAY_SEC = .05
        self.timer = Timer(self.DELAY_SEC)

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
            print("--AFTER SLEEP--", self.DELAY_SEC * self.DELAY_SEC_MULT)

            # Assert timer_signal
            self.assertEqual(self.timer.running, True)
            self.assertEqual(self.timer.current_count, i + 1)
            self.assertEqual(self.timer_dispatched_count, i + 1)
            self.assertEqual(self.timer_complete_dispatched_count, 0)
        # and so on...

        self.timer.dispose()

    def test_dispose_on_complete(self):
        self.REPEAT_COUNT = 3
        # self.timer = Timer(self.DELAY_SEC, self.REPEAT_COUNT, is_dispose_on_complete=True, name=self.TIMER_NAME)
        # Default: is_dispose_on_complete=True
        self.timer = Timer(self.DELAY_SEC, self.REPEAT_COUNT, name=self.TIMER_NAME)

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
            print("--AFTER SLEEP--", i,  self.DELAY_SEC * self.DELAY_SEC_MULT)

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
