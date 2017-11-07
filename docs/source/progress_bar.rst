Progress Bars
+++++++++++++

Three progress bar utilities are provided, all leveraging the excellent `tqdm <https://pypi.python.org/pypi/tqdm>` library.

progbar
=======

A simple iterable wrapper, much like the default ``tqdm`` wrapper. It can be used on any iterable to display a progress bar as it gets iterated::

    for x in progbar(my_list):
        do_something_slow(x)

However, unlike the standard ``tqdm`` function, this code has two additional, useful behaviors: first, it automatically leverages the ``ipywidgets`` progress bar when run inside a jupyter notebook; second, if given an integer, it automatically creates ``range(n)`` to iterate on. Both of these features are available in the ``tqdm`` library, but as separate functions. ``progbar`` wraps them all into a single intuitive call. It even includes a ``verbose`` flag that can be disabled to eliminate the progress bar based on runtime variables, if so desired.

.. autofunction:: miniutils.progress_bar.progbar

parallel_progbar
================

A parallel mapper based on ``multiprocessing`` that replaces ``Pool.map``. In attempting to use ``Pool.map``, I've had issues with unintuitive errors and, of course, wanting a progress bar of my map job's progress. Both of these are solved in ``parallel_progbar``::

    results = parallel_progbar(do_something_slow, my_list)
    # Equivalent to a parallel version of [do_something_slow(x) for x in my_list]

This produces a pool of processes, and performs a map function in parallel on the items of the provided list.

Starmap behavior::

    results = parallel_progbar(do_something_slow, my_list, starmap=True)
    # [do_something_slow(*x) for x in my_list]

And/or flatmap behavior::

    results = parallel_progbar(make_more_things, my_things, flatmap=True)
    # Equivalent to a parallel version of [y for x in my_things for y in make_more_things(x)]

It also supports runtime disabling, limited number of parallel processes, shuffling before mapping (in case the order of your list puts, say, a few slowest items near the end), and even an optional second progress bar when performing a flatmap. This second bar just reports the number of items output (``y`` in the case above), while the main progress bar counts down the number of finished inputs (``x``).

.. autofunction:: miniutils.progress_bar.parallel_progbar

iparallel_progbar
=================

This has the exact same behavior as ``parallel_progbar``, but produces an unordered generator instead of a list, yielding results as soon as they're available. It also permits a ``max_cache`` argument that allows you to limit the number of computed results available to the generator. ::

    for result in iparallel_progbar(do_something_slow, my_list):
        print("Result {} done!".format(result))

.. autofunction:: miniutils.progress_bar.iparallel_progbar
