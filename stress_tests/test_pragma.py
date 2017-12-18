from unittest import TestCase
from miniutils import pragma
from textwrap import dedent
import inspect


class PragmaTest(TestCase):
    def setUp(self):
        pass
        # # This is a quick hack to disable contracts for testing if needed
        # import contracts
        # contracts.enable_all()


class TestUnroll(PragmaTest):
    def test_unroll_long_range(self):
        @pragma.unroll
        def f():
            for i in range(3):
                yield i

        self.assertEqual(list(f()), [0, 1, 2])


class TestCollapseLiterals(PragmaTest):
    pass


class TestDeindex(PragmaTest):
    pass


class TestInline(PragmaTest):
    def test_recursive(self):
        def fib(n):
            if n <= 0:
                return 1
            elif n == 1:
                return 1
            else:
                return fib(n-1) + fib(n-2)

        from miniutils import tic
        toc = tic()
        fib_code = pragma.inline(fib, max_depth=1, return_source=True)(fib)
        fib_code = pragma.inline(fib, max_depth=2, return_source=True)(fib)
        fib_code = pragma.inline(fib, max_depth=3, return_source=True)(fib)
        #fib_code = pragma.inline(fib, max_depth=4, return_source=True)(fib)
