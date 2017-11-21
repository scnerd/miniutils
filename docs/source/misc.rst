Miscellaneous
=============

Code Contracts
++++++++++++++

Code contracting seems like a great way to define and document your code's expected behavior, easily integrate bounds checking, and just generally write code that tries to avoid bugs. The `pycontracts <https://andreacensi.github.io/contracts/>`_ package provides this capability within python, but as soon as I started using it I realized that it was meant primarily to be robust, not concise. For example, consider the following code::

    class ObjA:
        pass

    class ObjB:
        pass

    @contract
    def sample_func(a):
        """A function that requires an A object

        :param a: A thing
        :type a: ObjA
        :return: What you gave it
        :rtype: ObjB
        """
        return ObjB()

This seems intuitive what should happen--you're not using any complex attributes of the types, merely indicating that is should be of that type--but ``pycontracts`` will croak on this because you haven't explicitly told it about your two new types.

``miniutils.magic_contract`` is a little wrapper around the ``contract`` decorator that looks through the function's local namespace, finds types that aren't already registered with ``pycontracts``, and adds them as a simple ``isinstance`` check. Using it, we can write almost the exact same code::

    class ObjA:
        pass


    class ObjB:
        pass


    @magic_contract  # Uses the magic contract
    def sample_func(a):
        """A function that requires an A object

        :param a: A thing
        :type a: ObjA
        :return: What you gave it
        :rtype: ObjB
        """
        return ObjB()

And now the function works like you'd expect. If you want to do something more complex when adding an object as a contractable type, just use ``contracts.new_contract`` like you normally would, and ``magic_contract`` won't clobber your definition. Also, since this decorator is just a wrapper around ``contracts.contract``, you can continue using ``pycontracts`` as always, and the magic contract won't affect any of the rest of your code.

.. autofunction:: miniutils.magic_contract.magic_contract

Simplifying Decorators
++++++++++++++++++++++

When writing a decorator that could be used like ``@deco`` or ``@deco()``, there's a little code I've found necessary in order to make both cases function identically. I've isolated this code into another decorator (meta-decorator?) to keep my other decorators simple (since, let's be honest, decorators are usually convoluted enough as is).

Consider the following decorator definition::

    def deco(return_name=False):
        def inner_deco(func):
            def inner(*a, **kw):
                if return_name:
                    return func.__name__, func(*a, **kw)
                else:
                    return func(*a, **kw)
            return inner
        return inner_deco

    @deco()  # Works correctly
    def g(i):
        return i

    @deco(True)  # Works correctly
    def h(i):
        return i

    @deco(return_name=True)  # Works correctly
    def k(i):
        return i

    @deco  # Fails, since f gets assigned to return_names instead of func
    def f(i):
        return i

This makes sense, but is somewhat annoying when parameters aren't required, such as is the case in several built-in Python decorators. To make this last case work like the first, we can simply decorate our decorator::

    @optional_argument_decorator
    def deco(return_name=False):
        def inner_deco(func):
            def inner(*a, **kw):
                if return_name:
                    return func.__name__, func(*a, **kw)
                else:
                    return func(*a, **kw)
            return inner
        return inner_deco

    @deco()  # Works correctly
    def g(i):
        return i

    @deco(True)  # This still works
    def h(i):
        return i

    @deco(return_name=True)  # As does this
    def k(i):
        return i

    @deco  # Now this works too!
    def f(i):
        return i

.. autofunction:: miniutils.opt_decorator.optional_argument_decorator

Logging Made Easy
+++++++++++++++++

The standard ``logging`` module provides a lot of great functionality, but there are a few simplifications missing:

1. Intuitive colored logging to terminal
2. Fallback logging utilities when "logging" should only be enabled in certain contexts
3. "One-click" logging setup

As a slight simplification, ``miniutils`` provides a wrapper around the ``logging`` module to provide these features.

Usage
-----

To use the logging features listed below, just import the logger::

    from miniutils.logs import logger

If you want to use logging when available, but fall back to simply ``print`` to ``stderr`` when the logger isn't initialized elsewhere (for example, if you're writing a helper module that shouldn't dictate the logging format used in the user code), you can obtain a proxy logger object::

    from miniutils import logs_base as logger

This module has ``info``, ``warn``, ``warning``, ``error``, ``critical``, and ``log`` calls that use the logger when available, or fall back to a simple ``print`` statement otherwise. If the logger gets loaded from ``miniutils.logs`` later, these calls get swapped out automatically for their full-featured logger alternatives.

To change the logger's configuration, do something like the following::

    from miniutils.logs import enable_logging
    enable_logging(fmt_str='$(asctime) ( %(levelname) ) - $(message)')

This will swap out the logger and handlers that the rest of the logging utilities use.

.. autofunction:: miniutils.logs.enable_logging

Colored Logging
---------------

The ``coloredlogs`` module didn't quite work as expected when I tried to use it. It provides lots of handles and controls, but wasn't quite as intuitive as I expected it to be. To provide this more intuitive functionality, I wrap ``coloredlogs`` with a custom formatter that behaves more like expected:

- Don't assume the foreground color (it assumes black-on-white by default; I switch this to pulling the foreground color from the currently active color swatch)
- Uses case-sensitive match for level names (e.g., 'DEBUG', 'INFO', etc.), which seems silly. I monkey-patch this to be case insensitive
- Doesn't color aliases properly, even though it nominally supports name aliases


Timing
++++++

Simple ``printf``-like timing utilities when proper profiling won't quite work.

Timing Functions
----------------

To make a timed call to a function::

    from time import sleep
    from miniutils.timing import timed_call

    def f(a, *, x=1, sleep_dur=0.1):
        sleep(sleep_dur)
        return a * x

    result = timed_call(f, 2, x=3, sleep_dur=0.11)
    # "Call to 'f' took 0.110240s"

To make all calls to a function timed::

    from time import sleep
    from miniutils.timing import make_timed

    @make_timed
    def g(a, *, x=1, sleep_dur=0.1):
        sleep(sleep_dur)
        return a * x

    g(2, x=3, sleep_dur=0.11)
    # "Call to 'g' took 0.110242s"

.. autofunction:: miniutils.timing.timed_call

.. autofunction:: miniutils.timing.make_timed

Timing Blocks
-------------

Use ``tic``/``toc`` to time and report the run times of different chunks of code::

    from time import sleep
    from miniutils.timing import tic

    toc = tic()  # Just marks start time
    sleep(0.2)
    toc('Slept for 0.2 seconds')
    # "sample_timing.py:6 - Slept for 0.2 seconds - 0.200329s (total=0.2s)"
    sleep(.1)
    toc('Slept for 0.1 seconds')
    # "sample_timing.py:8 - Slept for 0.1 seconds - 0.100217s (total=0.3s)"

This utility is just less verbose than tracking various times yourself. The output is printed to the log for later review. It can also accept a custom print format string, including information about the code calling ``toc()`` and runtimes since the last ``tic``/``toc``.

.. autofunction:: miniutils.timing.tic