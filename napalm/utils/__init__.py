import logging

import sys


def default_logging_setup(level=logging.DEBUG):
    stream = logging.StreamHandler(sys.stdout)
    stream.terminator = "\n\r"
    logging.basicConfig(level=level, handlers=[stream])


class PrintLogging:
    """
    PrintLogging can be used for more speed of logging, lack of which could distort logs when threading.
    """
    def __init__(self, channel=None):
        self.channel = channel + ":" if channel else ""

    def _log(self, message, *args):
        print(message % args)

    def debug(self, message, *args):
        self._log("DEBUG:" + self.channel + message, *args)

    def info(self, message, *args):
        self._log("INFO:" + self.channel + message, *args)

    def warning(self, message, *args):
        self._log("WARNING:" + self.channel + message, *args)

    def error(self, message, *args):
        self._log("ERROR:" + self.channel + message, *args)

    def critical(self, message, *args):
        self._log("CRITICAL:" + self.channel + message, *args)
