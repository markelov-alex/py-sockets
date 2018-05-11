import threading
from threading import Thread

import time

from twisted.internet import reactor
from twisted.internet.task import deferLater, LoopingCall


# Signal

class Signal:

    def __init__(self):
        self.__listeners = []
        self.__after_dispatch_queue = []
        self.__is_dispatching = False

    def __len__(self):
        return len(self.__listeners)

    # def __iadd__(self, handler):
    #     self.__listeners.add(handler)
    #     return self
    #
    # def __isub__(self, handler):
    #     self.__listeners.remove(handler)
    #     return self

    def add(self, listener):
        if listener in self.__listeners:
            return
        # print("add")
        if self.__is_dispatching:
            self.__after_dispatch_queue.append((self.add, listener))
        else:
            self.__listeners.append(listener)

    def remove(self, listener):
        if listener not in self.__listeners:
            return
        # print("remove")
        if listener in self.__listeners:
            if self.__is_dispatching:
                self.__after_dispatch_queue.append((self.remove, listener))
            else:
                self.__listeners.remove(listener)

    def remove_all(self):
        # print("remove_all")
        if self.__is_dispatching:
            self.__after_dispatch_queue.append((self.remove_all, None))
        else:
            self.__listeners.clear()

    def dispatch(self, *args, **kwargs):
        # (To avoid RuntimeError: Set changed size during iteration)
        self.__is_dispatching = True
        for listener in self.__listeners:
            listener(*args, **kwargs)
        self.__is_dispatching = False

        # print("-after-dispatch")
        for method, listener in self.__after_dispatch_queue:
            method(listener) if listener else method()
        # print(" -after-dispatch")

    # __iadd__ = add
    # __isub__ = remove
    # __call__ = dispatch


# class Signal:
#     def __init__(self):
#         self.callbacks = []
#         self.r_lock = threading.RLock()
#
#     def connect(self, callback):
#         with self.r_lock:
#             callback = weak_ref(callback)
#             self.callbacks.append(callback)
#
#     def disconnect(self, callback):
#         with self.r_lock:
#             for index, weakref_callback in enumerate(self.callbacks):
#                 if callback == weakref_callback():
#                     del self.callbacks[index]
#                     break
#
#     def emit(self, *args, **kwargs):
#         with self.r_lock:
#             for weakref_callback in self.callbacks[:]:
#                 callback = weakref_callback()
#                 if callback is not None:
#                     callback(*args, **kwargs)
#                 else:  # lost reference
#                     self.callbacks.remove(weakref_callback)


# Timeout
# todo replace with timers!

class Timeout:

    # DEFAULT_SLEEP_SEC = 0.1

    # _start_time = 0
    # _stop_time = 0
    # _elapsed_time = 0
    # _finish_time = 0

    @property
    def current_count(self):
        return self._iterations

    @property
    def running(self):
        return self._running

    # @property
    # def time_elapsed(self):
    #     last_time = self._stop_time if self._stop_time else time.time()
    #     return last_time - self._start_time if self._start_time else 0
    #
    # @property
    # def time_left(self):
    #     last_time = self._stop_time if self._stop_time else time.time()
    #     return last_time - self._finish_time if self._finish_time else 0

    def __init__(self, delay_sec=1, repeat_count=0, callback=None, complete_callback=None,
                 is_dispose_on_complete=True, name=None):
        if delay_sec <= 0:
            raise Exception("Wrong delay_sec!")

        self.delay_sec = delay_sec
        self.repeat_count = repeat_count
        self.is_dispose_on_complete = is_dispose_on_complete
        self.name = name

        self.timer_signal = Signal()
        self.timer_complete_signal = Signal()
        if callback:
            self.timer_signal.add(callback)
        if complete_callback:
            self.timer_complete_signal.add(complete_callback)

        self._iterations = 0
        self._running = False
        # self._sleep_sec = min(self.DEFAULT_SLEEP_SEC, delay_sec)
        self._create_time = time.time()  # for logs

        self._thread = None

    def dispose(self):
        # Stop and reset
        self.reset()
        # Clear all listeners
        self.timer_signal.remove_all()
        self.timer_complete_signal.remove_all()

    def reset(self):
        self.stop()
        self._iterations = 0
        # self._start_time = 0
        # self._stop_time = 0

    def start(self):
        if self._running or self._iterations >= self.repeat_count > 0:
            return

        self._running = True
        # if not self._start_time:
        #     self._start_time = time.time()
        # self._stop_time = 0

        # print("(start)", "self._running:", self._running, "time:", time.time() - self._create_time)
        self._thread = Thread(target=self.__run, name=self.name, daemon=True)
        self._thread.start()

    # def restart(self):
    #     self.reset()
    #     self.start()

    def stop(self):
        if not self._running:
            return

        self._running = False
        # self._stop_time = time.time()

        # print("(stop)", "self._running:", self._running, "time:", time.time() - self._create_time)
        # -self.thread.join()
        self._thread = None

    def __run(self):
        # print(" (__run)")
        while self._running:
            # print("   (__run)", "self._running:", self._running, "self.delay_sec:", self.delay_sec,
            #       "self._iterations:", self._iterations, "self.repeat_count:", self.repeat_count,
            #       "time:", time.time() - self._create_time, threading.current_thread())
            if self.repeat_count <= 0 or self._iterations < self.repeat_count:
                # print("     (__run)", "sleep self.delay_sec:", self.delay_sec,
                #       "time:", time.time() - self._create_time, threading.current_thread())
                time.sleep(self.delay_sec)
                # print("       (__run)", "after-sleep self._running:", self._running,
                #       "self.delay_sec:", self.delay_sec,
                #       "time:", time.time() - self._create_time, threading.current_thread())

                # Check timer wasn't stopped during time.sleep()
                if not self._running or threading.current_thread() != self._thread:
                    break

                # print("         (__run) timer_signal-dispatch", "time:", time.time() - self._create_time)
                self.timer_signal.dispatch()
                self._iterations += 1
                if self._iterations == self.repeat_count:
                    # print("           (__run) timer_complete_signal-dispatch")
                    self.timer_complete_signal.dispatch()
                    if self.is_dispose_on_complete:
                        self.dispose()
            else:
                self.stop()


class TwistedTimeout(Timeout):
    """ Adapter to Deferred.
    Timeout functionality implemented upon Twisted's Deferred.
    """

    # def __init__(self, delay_sec=1, repeat_count=0, callback=None, complete_callback=None,
    #              is_dispose_on_complete=True, name=None):
    #     # --self.d = deferLater(reactor, delay_sec, )
    #     super().__init__(delay_sec, repeat_count, callback, complete_callback,
    #              is_dispose_on_complete, name)

    def dispose(self):
        # ? same in parent
        # Stop and reset
        self.reset()
        # Clear all listeners
        self.timer_signal.remove_all()
        self.timer_complete_signal.remove_all()
        print("TwTimeout (dispose)", "self._running:", self._running,
              "time:", time.time() - self._create_time, "name:", self.name)

    def reset(self):
        self.stop()
        self._iterations = 0
        print("TwTimeout (reset)", "__running:", self._running,
              "time:", time.time() - self._create_time, "name:", self.name)

    def start(self):
        if self._running or self._iterations >= self.repeat_count > 0:
            return

        self._running = True
        print("TwTimeout (start)", "__running:", self._running,
              "time:", time.time() - self._create_time, "name:", self.name)
        self._delayedCall = reactor.callLater(self.delay_sec, self._iteration_complete)

    def stop(self):
        if not self._running:
            return

        self._running = False
        print("TwTimeout (stop)", "__running:", self._running,
              "time:", time.time() - self._create_time, "name:", self.name)
        if self._delayedCall.active():
            self._delayedCall.cancel()
        self._delayedCall = None

    def _iteration_complete(self):
        print("TwTimeout (_iteration_complete)", "__running:", self._running, "__iterations:", self._iterations,
              "repeat_count:", self.repeat_count, "time:", time.time() - self._create_time, "name:", self.name)
        if self._running:
            if self.repeat_count <= 0 or self._iterations < self.repeat_count:
                print("TwTimeout   (_iteration_complete) timer_signal.dispatch")
                self.timer_signal.dispatch()
                self._iterations += 1
                if self._iterations == self.repeat_count:
                    # print("           (__run) timer_complete_signal-dispatch")
                    self.timer_complete_signal.dispatch()
                    print("TwTimeout     (_iteration_complete) timer_complete_signal.dispatch")
                    if self.is_dispose_on_complete:
                        self.dispose()
                    else:
                        self.stop()
            else:
                self.stop()


# temp
class TwistedDeferredTimeout(Timeout):
    """ Adapter to Deferred.
    Timeout functionality implemented upon Twisted's Deferred.
    """

    # def __init__(self, delay_sec=1, repeat_count=0, callback=None, complete_callback=None,
    #              is_dispose_on_complete=True, name=None):
    #     # --self.d = deferLater(reactor, delay_sec, )
    #     super().__init__(delay_sec, repeat_count, callback, complete_callback,
    #              is_dispose_on_complete, name)

    def dispose(self):
        # Stop and reset
        self.reset()
        # Clear all listeners
        self.timer_signal.remove_all()
        self.timer_complete_signal.remove_all()
        print("TwTimeout (dispose)", "self._running:", self._running,
              "time:", time.time() - self._create_time, "name:", self.name)

    def reset(self):
        self.stop()
        self._iterations = 0
        print("TwTimeout (reset)", "__running:", self._running,
              "time:", time.time() - self._create_time, "name:", self.name)

    def start(self):
        if self._running or self._iterations >= self.repeat_count > 0:
            return

        self._running = True
        print("TwTimeout (start)", "__running:", self._running,
              "time:", time.time() - self._create_time, "name:", self.name)
        self._deferred = deferLater(reactor, self.delay_sec, self._iteration_complete)

    def stop(self):
        if not self._running:
            return

        self._running = False
        print("TwTimeout (stop)", "__running:", self._running,
              "time:", time.time() - self._create_time, "name:", self.name)
        self._deferred.cancel()
        self._deferred = None

    def _iteration_complete(self):
        print("TwTimeout (_iteration_complete)", "__running:", self._running, "__iterations:", self._iterations,
              "repeat_count:", self.repeat_count, "time:", time.time() - self._create_time, "name:", self.name)
        if self._running:
            if self.repeat_count <= 0 or self._iterations < self.repeat_count:
                print("TwTimeout   (_iteration_complete) timer_signal.dispatch")
                self.timer_signal.dispatch()
                self._iterations += 1
                if self._iterations == self.repeat_count:
                    # print("           (__run) timer_complete_signal-dispatch")
                    self.timer_complete_signal.dispatch()
                    print("TwTimeout     (_iteration_complete) timer_complete_signal.dispatch")
                    if self.is_dispose_on_complete:
                        self.dispose()
                    else:
                        self.stop()
            else:
                self.stop()


# Timer

class AbstractTimer:

    # Class

    # Less resolution - more precise
    resolution_sec = .5

    _timers = []
    _is_ticking = False

    @classmethod
    def _add_timer(cls, timer):
        if timer not in cls._timers:
            cls._timers.append(timer)
        if not cls._is_ticking and cls._timers:
            cls._start_ticking()

    @classmethod
    def _remove_timer(cls, timer):
        if timer in cls._timers:
            cls._timers.remove(timer)
            if cls._is_ticking and not cls._timers:
                cls._stop_ticking()

    # Override
    @classmethod
    def _start_ticking(cls):
        if not cls._is_ticking:
            cls._is_ticking = True
            # Implement starting ticking in subclass

    # Override
    @classmethod
    def _stop_ticking(cls):
        if cls._is_ticking:
            cls._is_ticking = False
            # Implement stopping ticking in subclass

    @classmethod
    def _tick(cls):
        current_time = time.time()
        for timer in cls._timers:
            # elapsed_time = timer.elapsed_time + (current_time - timer._start_time if timer._start_time > 0 else 0)
            # if elapsed_time >= timer.delay_sec:
            if timer.get_elapsed_time() >= timer.delay_sec:
                timer._timer()

    # Object

    is_start_zero_delay = True

    _running = False

    @property
    def running(self):
        return self._running

    _paused = False

    @property
    def paused(self):
        return self._paused

    _start_time = 0
    # (Can be set on restoring saved game precisely from the place it was paused)
    elapsed_time = 0
    current_count = 0

    # ---
    # @property
    # def current_count(self):
    #     return self._current_count
    #
    # @property
    # def elapsed_time(self):
    #     return self._elapsed_time
    #
    # @elapsed_time.setter
    # def elapsed_time(self, value):
    #     self._elapsed_time = value

    def __init__(self, callback=None, delay_sec=0, repeat_count=0, name=""):
        self.callback = callback
        self.delay_sec = delay_sec
        # repeat_count=1 - for timeout mode
        self.repeat_count = repeat_count
        # (For debug needs)
        self.name = name

        self.timer_signal = Signal()
        self.timer_complete_signal = Signal()

    def dispose(self):
        self.reset()
        self.callback = None
        self.delay_sec = 0
        self.repeat_count = 0

        self.timer_signal.remove_all()
        self.timer_complete_signal.remove_all()

    def get_elapsed_time(self):
        return self.elapsed_time + (time.time() - self._start_time if self._start_time > 0 else 0)

    def start(self, callback=None, delay_sec=-1, repeat_count=-1):
        """Start or resume paused"""
        if callback:
            self.callback = callback
        if delay_sec >= 0:
            self.delay_sec = delay_sec
        if repeat_count >= 0:
            self.repeat_count = repeat_count

        if self.current_count >= self.repeat_count > 0 or self.delay_sec < 0:
            return

        if not self._running and (self.is_start_zero_delay or self.delay_sec):
            self._start_time = time.time()
            self._running = True
            self._paused = False
            self.__class__._add_timer(self)

    def stop(self):
        """Stop or pause"""
        if self._running:
            # (Save elapsed time since last start to variable)
            self.elapsed_time += time.time() - self._start_time
            self._start_time = 0
            self._running = False
            self.__class__._remove_timer(self)

    def reset(self):
        """Stop"""
        self.stop()
        # Reset
        self.current_count = 0
        self.elapsed_time = 0
        self._start_time = 0

    def restart(self, callback=None, delay_sec=-1, repeat_count=-1):
        """Start from zero"""
        self.reset()
        self.start(callback, delay_sec, repeat_count)

    def pause(self):
        # Can pause only running timer
        if self.running and not self._paused:
            self._paused = True
            self.stop()

    def resume(self):
        if self._paused:
            self._paused = False
            self.start()

    def _timer(self):
        # (Needed only for tests, because in real life it won't be called)
        if self.current_count >= self.repeat_count > 0:
            return

        self.current_count += 1
        self.elapsed_time = 0
        self._start_time = time.time()

        # Process timer event
        if self.callback:
            self.callback()
        self.timer_signal.dispatch()
        # Process timer complete event
        if self.current_count >= self.repeat_count > 0:
            self.stop()
            self.timer_complete_signal.dispatch()


class ThreadedTimer(AbstractTimer):

    _thread = None
    _lock = threading.RLock()

    @classmethod
    def _start_ticking(cls):
        with cls._lock:
            if not cls._is_ticking:
                cls._is_ticking = True
                cls._thread = Thread(target=cls.__ticking_thread, name="ThreadedTimer-ticker", daemon=True)
                cls._thread.start()

    @classmethod
    def _stop_ticking(cls):
        with cls._lock:
            if cls._is_ticking:
                cls._is_ticking = False
                print("ThreadedTimer.stop_ticking(), thread.join()...")
                cls._thread.join()

    @classmethod
    def __ticking_thread(cls):
        with cls._lock:
            while cls._is_ticking:
                # (Call tick() before sleep() to avoid processing timer after it was stopped)
                cls._tick()
                time.sleep(cls.resolution_sec)


class TwistedTimer(AbstractTimer):

    _task = None
    # _lock = threading.RLock()

    @classmethod
    def _start_ticking(cls):
        # with cls._lock:
            if not cls._is_ticking:
                cls._is_ticking = True
                cls._task = LoopingCall(cls._tick)
                cls._task.start(cls.resolution_sec)

    @classmethod
    def _stop_ticking(cls):
        # with cls._lock:
            if cls._is_ticking:
                cls._is_ticking = False
                cls._task.stop()
