from unittest import TestCase
from miniutils.opt_decorator import optional_argument_decorator


class TestOptionalArgumentDecorator(TestCase):
    def test_optional_argument_decorator(self):
        @optional_argument_decorator
        def deco(return_name=False):
            def inner_deco(func):
                def inner(*a, **kw):
                    if return_name:
                        return func.__name__, func(*a, **kw)
                    else:
                        return func(*a, **kw)
                return inner
            return inner_deco

        @deco
        def f(i):
            return i

        @deco()
        def g(i):
            return i

        @deco(True)
        def h(i):
            return i

        @deco(return_name=True)
        def k(i):
            return i

        self.assertEqual(f(3), 3)
        self.assertEqual(g(3), 3)
        self.assertEqual(h(3), ('h', 3))
        self.assertEqual(k(3), ('k', 3))
