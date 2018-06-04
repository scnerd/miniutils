from unittest import TestCase
from functools import lru_cache

import math

from miniutils import CachedProperty, LazyDictionary, FileCached, file_cached_decorator
from miniutils.progress_bar import progbar
from miniutils.timing import tic


class Primes:
    @LazyDictionary()
    def is_prime(self, i):
        if not isinstance(i, int) or i < 1:
            raise ValueError("Can only check if a positive integer is prime")
        elif i in [1, 2]:
            return True
        elif i % 2 == 0:
            return False
        else:
            return all(i % p != 0 for p in range(3, int(math.sqrt(i)) + 1, 2) if self.is_prime[p])


class PropertyComparison:
    @property
    def x(self):
        return 5

    @CachedProperty()
    def y(self):
        return 5


class TestCachedProperty(TestCase):
    def test_prime_correctness(self):
        p = Primes()
        n = 100000
        print("Computing number of primes under {}".format(n))
        self.assertEqual(sum(1 for i in progbar(range(2, n)) if p.is_prime[i]), 9592)

    def test_cache_speed(self):
        p = PropertyComparison()
        self.assertEqual(p.x, 5)
        self.assertEqual(p.y, 5)

        n = 1000000
        toc = tic()
        for _ in range(n):
            self.assertEqual(p.x, 5)
        toc("Time required to access a simple property {} times".format(n))
        for _ in range(n):
            self.assertEqual(p.y, 5)
        toc("Time required to access a cached property {} times".format(n))


class TestFileCachedCall(TestCase):
    def test_same_key(self):
        def f(x):
            return x + 1

        n = 10000

        cached_f = FileCached(f, auto_purge=True)
        lru_cached_f = lru_cache(maxsize=1)(cached_f)
        toc = tic()
        for _ in progbar(n):
            f(5)
        toc("Time required to call a simple function {} times".format(n))
        for _ in progbar(n):
            cached_f(5)
        toc("Time required to call a file-cached function {} times".format(n))
        for _ in progbar(n):
            lru_cached_f(5)
        toc("Time required to call a hybrid-cached function {} times (should be all LRU hits)".format(n))

    def test_random_keys(self):
        from random import randint

        def f(x):
            return x + 1

        n = 10000
        # The frequency at which we'll hit a given value in cache
        hit_ratio = 0.01
        # The rate of cache hits we should expect to hit in the LRU cache before passing to file cache
        hybrid_ratio = 0.5

        cached_f = FileCached(f, auto_purge=True)
        lru_cached_f = lru_cache(maxsize=int(1/hit_ratio * hybrid_ratio))(cached_f)

        ixs = [randint(1, int(1/hit_ratio)) for _ in range(n)]
        toc = tic()
        for i in progbar(ixs):
            f(i)
        toc("Time required to call a simple function {} times ({} cache hit rate)".format(n, hit_ratio))
        for i in progbar(ixs):
            cached_f(i)
        toc("Time required to call a file-cached function {} times ({} cache hit rate)".format(n, hit_ratio))
        for i in progbar(ixs):
            lru_cached_f(i)
        toc("Time required to call a hybrid-cached function {} times ({} cache hit rate, {} hit LRU rate)".format(n, hit_ratio, hybrid_ratio))
