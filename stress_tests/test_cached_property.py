from unittest import TestCase

import math

from miniutils.caching import CachedProperty, LazyDictionary
from miniutils.progress_bar import progbar


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
        n = 1000000
        print("Computing number of primes under {}".format(n))
        self.assertEqual(sum(1 for i in progbar(range(2, n)) if p.is_prime[i]), 78498)

    def test_cache_speed(self):
        p = PropertyComparison()
        self.assertEqual(p.x, 5)
        self.assertEqual(p.y, 5)

        from miniutils.timing import tic
        n = 1000000
        toc = tic()
        for _ in range(n):
            self.assertEqual(p.x, 5)
        toc("Time required to access a simple property {} times".format(n))
        for _ in range(n):
            self.assertEqual(p.y, 5)
        toc("Time required to access a cached property {} times".format(n))
