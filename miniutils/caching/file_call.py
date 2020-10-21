import os
import shelve
from collections import namedtuple
from functools import wraps
from glob import glob

from miniutils.opt_decorator import optional_argument_decorator
from miniutils.logs_base import debug


class FileCached:
    def __init__(self, fn, cache_path=None, files_used=None, auto_purge=False):
        """Caches function results to a file to save re-computation of highly expensive calls

        :param fn: The functions whose result should be cached
        :type fn: function
        :param cache_path: No-extension file path where cache should be kept
        :type cache_path: str
        :param files_used: List of files that could effect the result of this function; cache results are invalidated if any of these files are updated since the last function call
        :type files_used: Iterable
        :param auto_purge: If True, deletes the file cache when this cache object passes out of scope
        :type: auto_purge: bool
        """
        self.__wrapped__ = fn
        self.path = cache_path or '.__cache_{}'.format(fn.__name__)
        self.files_used = tuple(sorted([os.path.abspath(os.path.expanduser(p)) for p in (files_used or [])]))
        self._shelf = shelve.open(self.path)
        self._auto_purge = auto_purge
        self._hits = 0
        self._misses = 0

    def __call__(self, *args, **kwargs):
        key = ':'.join(self.files_used) + ':' + hex(hash((args, tuple(sorted(kwargs.items())))))

        if key in self._shelf:
            file_update_times, result = self._shelf[key]
            for file in self.files_used:
                if not os.path.exists(file) or os.path.getmtime(file) > file_update_times[file]:
                    break
            else:
                self._hits += 1
                return result

        self._misses += 1
        file_update_times = {file: os.path.getmtime(file) for file in self.files_used}
        result = self.__wrapped__(*args, **kwargs)

        self._shelf[key] = (file_update_times, result)

        return result

    def __del__(self):
        if self._auto_purge:
            self.cache_clear(create_new_shelf=False)

    def cache_clear(self, create_new_shelf=True):
        """Deletes the underlying cache"""
        # TODO: Remove these debug loops
        debug("Clearing shelf: directory starts with the following files:")
        for path in glob(os.path.dirname(self.path)):
            debug(path)

        del self._shelf
        for path in glob(self.path + '*'):
            os.remove(path)

        debug("Clearing shelf: directory ends with the following files:")
        for path in glob(os.path.dirname(self.path)):
            debug(path)

        if create_new_shelf:
            self._shelf = shelve.open(self.path)

    def cache_info(self):
        """Gets information about this cache.

        :return: A named tuple containing the number of cache ``hits`` and ``misses``
        """
        return namedtuple('CacheInfo', ('hits', 'misses'))(self._hits, self._misses)


@optional_argument_decorator
def file_cached_decorator(*args, **kwargs):
    """A decorator version of ``FileCached``

    :param cache_path: No-extension file path where cache should be kept
    :type cache_path: str
    :param files_used: List of files that could effect the result of this function; cache results are invalidated if any of these files are updated since the last function call
    :type files_used: Iterable
    :param auto_purge: If True, deletes the file cache when this cache object passes out of scope
    :type: auto_purge: bool
    :return: A decorator for a function
    :rtype: function
    """

    @wraps(FileCached.__init__)
    def decorator(fn):
        """
        :rtype: FileCached
        """
        return FileCached(fn, *args, **kwargs)

    return decorator
