import threading
from threading import Thread

import time

from twisted.internet import reactor
from twisted.internet.task import deferLater


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


class Timer:

    # DEFAULT_SLEEP_SEC = 0.1

    @property
    def current_count(self):
        return self._iterations

    @property
    def running(self):
        return self._running

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

    def start(self):
        if self._running or self._iterations >= self.repeat_count > 0:
            return

        self._running = True
        # print("(start)", "self._running:", self._running, "time:", time.time() - self._create_time)
        self._thread = Thread(target=self._run, name=self.name, daemon=True)
        self._thread.start()

    def stop(self):
        if not self._running:
            return

        self._running = False
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


class TwistedTimer(Timer):
    """ Adapter to Deferred.
    Timer functionality implemented upon Twisted's Deferred.
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
        print("TwTimer (dispose)", "self._running:", self._running,
              "time:", time.time() - self._create_time, "name:", self.name)

    def reset(self):
        self.stop()
        self._iterations = 0
        print("TwTimer (reset)", "__running:", self._running,
              "time:", time.time() - self._create_time, "name:", self.name)

    def start(self):
        if self._running or self._iterations >= self.repeat_count > 0:
            return

        self._running = True
        print("TwTimer (start)", "__running:", self._running,
              "time:", time.time() - self._create_time, "name:", self.name)
        self._delayedCall = reactor.callLater(self.delay_sec, self._iteration_complete)

    def stop(self):
        if not self._running:
            return

        self._running = False
        print("TwTimer (stop)", "__running:", self._running,
              "time:", time.time() - self._create_time, "name:", self.name)
        if self._delayedCall.active():
            self._delayedCall.cancel()
        self._delayedCall = None

    def _iteration_complete(self):
        print("TwTimer (_iteration_complete)", "__running:", self._running, "__iterations:", self._iterations,
              "repeat_count:", self.repeat_count, "time:", time.time() - self._create_time, "name:", self.name)
        if self._running:
            if self.repeat_count <= 0 or self._iterations < self.repeat_count:
                print("TwTimer   (_iteration_complete) timer_signal.dispatch")
                self.timer_signal.dispatch()
                self._iterations += 1
                if self._iterations == self.repeat_count:
                    # print("           (__run) timer_complete_signal-dispatch")
                    self.timer_complete_signal.dispatch()
                    print("TwTimer     (_iteration_complete) timer_complete_signal.dispatch")
                    if self.is_dispose_on_complete:
                        self.dispose()
                    else:
                        self.stop()
            else:
                self.stop()


# temp
class TwistedDeferredTimer(Timer):
    """ Adapter to Deferred.
    Timer functionality implemented upon Twisted's Deferred.
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
        print("TwTimer (dispose)", "self._running:", self._running,
              "time:", time.time() - self._create_time, "name:", self.name)

    def reset(self):
        self.stop()
        self._iterations = 0
        print("TwTimer (reset)", "__running:", self._running,
              "time:", time.time() - self._create_time, "name:", self.name)

    def start(self):
        if self._running or self._iterations >= self.repeat_count > 0:
            return

        self._running = True
        print("TwTimer (start)", "__running:", self._running,
              "time:", time.time() - self._create_time, "name:", self.name)
        self._deferred = deferLater(reactor, self.delay_sec, self._iteration_complete)

    def stop(self):
        if not self._running:
            return

        self._running = False
        print("TwTimer (stop)", "__running:", self._running,
              "time:", time.time() - self._create_time, "name:", self.name)
        self._deferred.cancel()
        self._deferred = None

    def _iteration_complete(self):
        print("TwTimer (_iteration_complete)", "__running:", self._running, "__iterations:", self._iterations,
              "repeat_count:", self.repeat_count, "time:", time.time() - self._create_time, "name:", self.name)
        if self._running:
            if self.repeat_count <= 0 or self._iterations < self.repeat_count:
                print("TwTimer   (_iteration_complete) timer_signal.dispatch")
                self.timer_signal.dispatch()
                self._iterations += 1
                if self._iterations == self.repeat_count:
                    # print("           (__run) timer_complete_signal-dispatch")
                    self.timer_complete_signal.dispatch()
                    print("TwTimer     (_iteration_complete) timer_complete_signal.dispatch")
                    if self.is_dispose_on_complete:
                        self.dispose()
                    else:
                        self.stop()
            else:
                self.stop()

