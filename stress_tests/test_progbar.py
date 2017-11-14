from unittest import TestCase

from miniutils.progress_bar import parallel_progbar, iparallel_progbar
from miniutils.timing import tic


class TestProgbar(TestCase):
    def test_parallel_progbar_overhead(self):
        def mapper(i):
            return i ** 2
        n = list(range(100000))
        toc = tic()
        list_comp = [i**2 for i in n]
        time_lc = toc('List comprehension')
        par = parallel_progbar(mapper, n)
        time_par = toc('Parallel progbar')
        print("{}s / {}s = {}x slowdown".format(time_par, time_lc, time_par / time_lc))
        self.assertSequenceEqual(par, list_comp)

    def test_iparallel_progbar(self):
        def mapper(i):
            return i ** 2
        n = list(range(100000))
        toc = tic()
        list_comp = [i**2 for i in n]
        time_lc = toc('List comprehension')
        par = list(iparallel_progbar(mapper, n))
        time_par = toc('iParallel progbar')
        print("{}s / {}s = {}x slowdown".format(time_par, time_lc, time_par / time_lc))
        self.assertSequenceEqual(list(sorted(par)), list(sorted(list_comp)))
