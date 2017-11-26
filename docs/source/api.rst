API
+++

Caching
=======

.. autoclass:: miniutils.caching.CachedProperty
    :members:

    .. automethod:: __init__


Progress Bar
============

.. autofunction:: miniutils.progress_bar.progbar

.. autofunction:: miniutils.progress_bar.parallel_progbar

.. autofunction:: miniutils.progress_bar.iparallel_progbar


Python 2
========

.. autoclass:: miniutils.py2_wrap.MakePython2
    :members:

    .. automethod:: __init__


Pragma
======

.. autofunction:: miniutils.pragma.unroll

.. autofunction:: miniutils.pragma.collapse_literals

.. autofunction:: miniutils.pragma.deindex


Miscellaneous
=============

Magic Contracting
-----------------

.. autofunction:: miniutils.magic_contract.magic_contract

Simplifying Decorators
----------------------

.. autofunction:: miniutils.opt_decorator.optional_argument_decorator

Logging
-------

.. autofunction:: miniutils.logs.enable_logging

Timing
------

.. autofunction:: miniutils.timing.timed_call

.. autofunction:: miniutils.timing.make_timed

.. autofunction:: miniutils.timing.tic