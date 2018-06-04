from functools import wraps
from glob import glob
import shelve
import os

from miniutils.opt_decorator import optional_argument_decorator


class FileCached:
    def __init__(self, fn, cache_path=None, files_used=None, auto_purge=False):
        """Caches function results to a file to save re-computation of highly expensive calls

        :param fn: The functions whose result should be cached
        :param cache_path: No-extension file path where cache should be kept
        :param files_used: List of files that could effect the result of this function; cache results are invalidated if any of these files are updated since the last function call
        :param auto_purge: If True, deletes the file cache when this cache object passes out of scope
        """
        self.fn = fn
        self.path = cache_path or '.__cache_{}'.format(fn.__name__)
        self.files_used = tuple(sorted([os.path.abspath(os.path.expanduser(p)) for p in (files_used or [])]))
        self.shelf = shelve.open(self.path)
        self._auto_purge = auto_purge

    def __call__(self, *args, **kwargs):
        key = ':'.join(self.files_used) + ':' + hex(hash((args, tuple(sorted(kwargs.items())))))

        if key in self.shelf:
            file_update_times, result = self.shelf[key]
            for file in self.files_used:
                if not os.path.exists(file) or os.path.getmtime(file) > file_update_times[file]:
                    break
            else:
                return result

        file_update_times = {file: os.path.getmtime(file) for file in self.files_used}
        result = self.fn(*args, **kwargs)

        self.shelf[key] = (file_update_times, result)

        return result

    def __del__(self):
        if self._auto_purge:
            self.purge(create_new_shelf=False)

    def purge(self, create_new_shelf=True):
        """Deletes

        :return:
        """
        del self.shelf
        for path in glob(self.path + '.*'):
            os.remove(path)

        if create_new_shelf:
            self.shelf = shelve.open(self.path)


@optional_argument_decorator
def file_cached_decorator(*args, **kwargs):
    @wraps(FileCached.__init__)
    def decorator(fn):
        return FileCached(fn, *args, **kwargs)

    return decorator
