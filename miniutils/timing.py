import traceback
from functools import partial
from time import time

from miniutils.logs_base import log


def timed_call(func, *args, log_level='DEBUG', **kwargs):
    """Logs a function's run time

    :param func: The function to run
    :param args: The args to pass to the function
    :param kwargs: The keyword args to pass to the function
    :param log_level: The log level at which to print the run time
    :return: The function's return value
    """
    start = time()
    r = func(*args, **kwargs)
    t = time() - start
    log(log_level, "Call to '{}' took {:0.6f}s".format(func.__name__, t))
    return r


def make_timed(func):
    """A decorator to make a function print its execution time whenever it gets called"""
    return partial(timed_call, func)


def tic(log_level='DEBUG', fmt="{file}:{line} - {message} - {diff:0.6f}s (total={total:0.1f}s)", verbose=True):
    """A minimalistic ``printf``-type timing utility. Call this function to start timing individual sections of code

    :param log_level: The level at which to log block run times
    :param fmt: The format string to use when logging times. Available arguments include:

                - file, line, func, code_text: The stack frame information which called this timer
                - diff: The time since the last timer printout was called
                - total: The time since this timing block was started
                - message: The message passed to this timing printout
    :param verbose: If False, suppress printing messages
    :return: A function that reports run times when called
    """
    first_time = last_time = time()

    def toc(message=None):
        """A function that reports run times

        :param message: The message to print with this particular runtime
        :return: The time difference (in seconds) since the last tic or toc
        """
        nonlocal last_time

        now = time()
        diff = now - last_time
        total = now - first_time

        if verbose:
            file, line, func, code_text = traceback.extract_stack(limit=2)[0]
            log(log_level, fmt.format(**locals()))

        last_time = time()
        return diff

    return toc
