from unittest import TestCase
from miniutils.progress_bar import progbar, parallel_progbar, iparallel_progbar


class TestProgbar(TestCase):
    def test_progbar_list(self):
        lst = list(range(10))
        self.assertEqual(list(progbar(lst)), lst)

    def test_progbar_quiet(self):
        lst = list(range(10))
        self.assertEqual(list(progbar(lst, verbose=False)), lst)

    def test_progbar_int(self):
        n = 10
        lst = list(range(n))
        self.assertEqual(list(progbar(n)), lst)

    def test_parallel_progbar(self):
        def mapper(i):
            return i ** 2

        n = list(range(100))
        self.assertSequenceEqual(parallel_progbar(mapper, n), [i ** 2 for i in n])

    def test_parallel_generator(self):
        def gen(i):
            k = 0
            while k < i:
                yield k
                k += 1

        def mapper(i):
            return i ** 2

        n = gen(100)
        self.assertSequenceEqual(parallel_progbar(mapper, n), [i ** 2 for i in range(100)])

    def test_parallel_shuffle(self):
        def mapper(i):
            return i ** 2

        n = list(range(100))
        self.assertSequenceEqual(parallel_progbar(mapper, n, shuffle=True), [i ** 2 for i in n])

    def test_parallel_progbar_flatmap(self):
        def mapper(i):
            return range(i)

        n = list(range(100))
        self.assertSequenceEqual(parallel_progbar(mapper, n, flatmap=True),
                                 [k for i in n for k in range(i)])

    def test_parallel_progbar_starmap(self):
        def mapper(x, p):
            return x ** p

        n = [(1, 5), (2, 0), (3, 4), (0, 100)]
        self.assertSequenceEqual(parallel_progbar(mapper, n, starmap=True),
                                 [x ** p for x, p in n])

    def test_parallel_progbar_flatmap_starmap(self):
        def mapper(a, b):
            return range(a, b)

        n = [(1, 5), (2, 0), (3, 4), (0, 100)]
        self.assertSequenceEqual(parallel_progbar(mapper, n, flatmap=True, starmap=True),
                                 [k for a, b in n for k in range(a, b)])

    def test_iparallel_progbar(self):
        def mapper(i):
            return i ** 2

        n = list(range(100))
        self.assertSequenceEqual(list(sorted(iparallel_progbar(mapper, n))), [i ** 2 for i in n])

    def test_iparallel_progbar_flatmap(self):
        def mapper(i):
            return range(i)

        n = list(range(100))
        self.assertSequenceEqual(list(sorted(iparallel_progbar(mapper, n, flatmap=True))),
                                 list(sorted([k for i in n for k in range(i)])))

    def test_iparallel_progbar_flatmap_starmap(self):
        def mapper(a, b):
            return range(a, b)

        n = [(1, 5), (2, 0), (3, 4), (0, 100)]
        self.assertSequenceEqual(list(sorted(iparallel_progbar(mapper, n, flatmap=True, starmap=True))),
                                 list(sorted([k for a, b in n for k in range(a, b)])))

    def test_iparallel_progbar_starmap(self):
        def mapper(x, p):
            return x ** p

        n = [(1, 5), (2, 0), (3, 4), (0, 100)]
        self.assertSequenceEqual(list(sorted(iparallel_progbar(mapper, n, starmap=True))),
                                 list(sorted([x ** p for x, p in n])))

    def test_parallel_error(self):
        def f(lst):
            return parallel_progbar(lambda x: x ** 2, lst)

        self.assertSequenceEqual(f([1, 2, 3]), [1, 4, 9])
        self.assertRaises(TypeError, f, ['a', 'b', 'c'])

        def f_flat(lst):
            return parallel_progbar(range, lst, flatmap=True)

        self.assertSequenceEqual(f_flat([1, 2, 3]), [0, 0, 1, 0, 1, 2])
        self.assertRaises(TypeError, f_flat, ['a', 'b', 'c'])
