from unittest import TestCase

import math
import itertools

from miniutils.caching import CachedProperty, LazyDictionary
from miniutils.progress_bar import progbar


class Primes:
    @LazyDictionary()
    def primes_under(self, i):
        if i == 0:
            return []
        else:
            return self.primes_under[i-1] + ([i] if self.is_prime[i] else [])

    @LazyDictionary()
    def is_prime(self, i):
        if not isinstance(i, int) or i < 1:
            raise ValueError("Can only check if a positive integer is prime")
        elif i in [1, 2]:
            return True
        elif i % 2 == 0:
            return False
        else:
            return all(i % p != 0 for p in self.primes_under[math.sqrt(i)])


class TestCachedProperty(TestCase):
    def test_prime_cache(self):
        p = Primes()
        primes = [j for j in progbar(range(1, 1000000 + 1)) if p.is_prime[j]]
        print(len(primes))
