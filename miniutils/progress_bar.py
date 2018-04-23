import itertools
import multiprocessing as mp
from nose.plugins.multiprocess import TimedOutException
import random
import warnings

try:
    from tqdm import tqdm as _tqdm
    try:  # pragma: nocover
        # Check if we're in a Jupyter notebook... if so, use the ipywidgets progress bar instead
        from IPython import get_ipython
        if type(get_ipython()).__module__.startswith('ipykernel.'):
            from tqdm import tqdm_notebook as _tqdm
    except (ImportError, NameError):  # pragma: nocover
        # IPython isn't even installed, or we're not in it
        pass
except ImportError:  # pragma: nocover
    # noinspection PyUnusedLocal
    def _tqdm(iterable, *a, **kw):
        return iterable


def progbar(iterable, *a, verbose=True, **kw):
    """Prints a progress bar as the iterable is iterated over

    :param iterable: The iterator to iterate over
    :param a: Arguments to get passed to tqdm (or tqdm_notebook, if in a Jupyter notebook)
    :param verbose: Whether or not to print the progress bar at all
    :param kw: Keyword arguments to get passed to tqdm
    :return: The iterable that will report a progress bar
    """
    iterable = range(iterable) if isinstance(iterable, int) else iterable
    if verbose:
        return _tqdm(iterable, *a, **kw)
    else:
        return iterable


def _fun(f, q_in, q_out, flatten, star):  # pragma: no cover
    try:
        while True:
            i, x = q_in.get()
            if i is None:
                break
            out = f(*x) if star else f(x)
            if flatten:
                for j, o in enumerate(out):
                    q_out.put(((i, j), o))
                q_out.put((None, None))
            else:
                q_out.put((i, out))
    except BaseException as ex:
        q_out.put((None, ex))


def _parallel_progbar_launch(mapper, iterable, nprocs=None, starmap=False, flatmap=False, shuffle=False,
                             verbose=True, verbose_flatmap=None, max_cache=-1, **kwargs):

    # Shuffle the iterable if requested, to make the parallel execution potentially more uniform in runtime
    enumerated_iterable = enumerate(iterable)
    if shuffle:
        enumerated_iterable = list(enumerated_iterable)
        # ids = [i for i in sorted(range(len(iterable)), key=lambda x: random.random())]
        # iterable = (iterable[i] for i in ids)
        random.shuffle(enumerated_iterable)  # Is this going to be expensive for large lists of large objects?

    # Check that we don't launch more processes than there are elements to map (if that's knowable)
    nprocs = nprocs or mp.cpu_count()
    try:
        nprocs = max(1, min(len(iterable), nprocs))
    except TypeError:
        pass

    # Set up multiprocessing management for mapping
    q_in = mp.Queue()
    q_out = mp.Queue(max_cache)

    procs = [mp.Process(target=_fun, args=(mapper, q_in, q_out, flatmap, starmap)) for _ in range(nprocs)]
    for p in procs:
        p.daemon = True
        p.start()

    # Doing it this way prevents us from storing locally an entire list of the input values unnecessarily, and still
    # gets us the number of elements sent for processing
    sent = (q_in.put((i, x)) for i, x in enumerated_iterable)
    num_sent = sum(1 for _ in sent)
    for _ in range(nprocs):
        # Send out a flag for each process to terminate once all elements are processed
        q_in.put((None, None))

    # Fetch the mapped results from the output queue, printing a progress bar as you go
    if flatmap:
        # If we're flat mapping, then we'll keep separate progress of all returned results (an unknown number) and how
        # many inputs are complete (a known number). The outer loop will track the latter, and the inner loop the former
        results = (q_out.get() for _ in progbar(itertools.count(),
                                                verbose=verbose if verbose_flatmap is None else verbose_flatmap,
                                                **kwargs))
        for _ in progbar(num_sent, verbose=verbose):
            for i, x in results:
                # When we're flagged that an input is done being returned in the queue, break the inner loop to make
                # the "completed inputs" progress bar tick
                if i is None:
                    if x is None:
                        break
                    else:
                        raise x
                yield i, x
    else:
        for i, x in (q_out.get() for _ in progbar(num_sent, verbose=verbose, **kwargs)):
            if i is None:
                raise x
            yield i, x

    # Clean up
    for p in procs:
        try:
            p.join(1)
        except (TimeoutError, mp.TimeoutError, TimedOutException):  # pragma: nocover
            warnings.warn("parallel_progbar mapping process failed to close properly (check error output)")


def parallel_progbar(mapper, iterable, nprocs=None, starmap=False, flatmap=False, shuffle=False,
                     verbose=True, verbose_flatmap=None, **kwargs):
    """Performs a parallel mapping of the given iterable, reporting a progress bar as values get returned

    :param mapper: The mapping function to apply to elements of the iterable
    :param iterable: The iterable to map
    :param nprocs: The number of processes (defaults to the number of cpu's)
    :param starmap: If true, the iterable is expected to contain tuples and the mapper function gets each element of a
        tuple as an argument
    :param flatmap: If true, flatten out the returned values if the mapper function returns a list of objects
    :param shuffle: If true, randomly sort the elements before processing them. This might help provide more uniform
        runtimes if processing different objects takes different amounts of time.
    :param verbose: Whether or not to print the progress bar
    :param verbose_flatmap: If performing a flatmap, whether or not to report each object as it's returned
    :param kwargs: Any other keyword arguments to pass to the progress bar (see ``progbar``)
    :return: A list of the returned objects, in the same order as provided
    """

    results = _parallel_progbar_launch(mapper, iterable, nprocs, starmap, flatmap, shuffle, verbose, verbose_flatmap, **kwargs)
    return [x for i, x in sorted(results, key=lambda p: p[0])]


def iparallel_progbar(mapper, iterable, nprocs=None, starmap=False, flatmap=False, shuffle=False,
                      verbose=True, verbose_flatmap=None, max_cache=-1, **kwargs):
    """Performs a parallel mapping of the given iterable, reporting a progress bar as values get returned. Yields
    objects as soon as they're computed, but does not guarantee that they'll be in the correct order.

    :param mapper: The mapping function to apply to elements of the iterable
    :param iterable: The iterable to map
    :param nprocs: The number of processes (defaults to the number of cpu's)
    :param starmap: If true, the iterable is expected to contain tuples and the mapper function gets each element of a
        tuple as an argument
    :param flatmap: If true, flatten out the returned values if the mapper function returns a list of objects
    :param shuffle: If true, randomly sort the elements before processing them. This might help provide more uniform
        runtimes if processing different objects takes different amounts of time.
    :param verbose: Whether or not to print the progress bar
    :param verbose_flatmap: If performing a flatmap, whether or not to report each object as it's returned
    :param max_cache: Maximum number of mapped objects to permit in the queue at once
    :param kwargs: Any other keyword arguments to pass to the progress bar (see ``progbar``)
    :return: A list of the returned objects, in whatever order they're done being computed
    """

    results = _parallel_progbar_launch(mapper, iterable, nprocs, starmap, flatmap, shuffle, verbose,
                                       verbose_flatmap, max_cache, **kwargs)
    return (x for i, x in results)


