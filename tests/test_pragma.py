from unittest import TestCase
from miniutils import pragma
from textwrap import dedent


class TestUnroll(TestCase):
    def test_unroll_range(self):
        @pragma.unroll
        def f():
            for i in range(3):
                yield i

        self.assertEqual(list(f()), [0, 1, 2])

    def test_unroll_various(self):
        g = lambda: None
        g.a = [1,2,3]
        g.b = 6

        @pragma.unroll(return_source=True)
        def f(x):
            y = 5
            a = range(3)
            b = [1,2,4]
            c = (1,2,5)
            d = reversed(a)
            e = [x, x, x]
            f = [y, y, y]
            for i in a:
                yield i
            for i in b:
                yield i
            for i in c:
                yield i
            for i in d:
                yield i
            for i in e:
                yield i
            for i in f:
                yield i
            for i in g.a:
                yield i
            for i in [g.b + 0, g.b + 1, g.b + 2]:
                yield i

        result = dedent('''
        def f(x):
            y = 5
            a = range(3)
            b = [1, 2, 4]
            c = 1, 2, 5
            d = reversed(a)
            e = [x, x, x]
            f = [y, y, y]
            yield 0
            yield 1
            yield 2
            yield 1
            yield 2
            yield 4
            yield 1
            yield 2
            yield 5
            for i in d:
                yield i
            yield x
            yield x
            yield x
            yield 5
            yield 5
            yield 5
            for i in g.a:
                yield i
            yield g.b + 0
            yield g.b + 1
            yield g.b + 2
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_unroll_const_list(self):
        @pragma.unroll
        def f():
            for i in [1, 2, 4]:
                yield i

        self.assertEqual(list(f()), [1, 2, 4])

    def test_unroll_const_tuple(self):
        @pragma.unroll
        def f():
            for i in (1, 2, 4):
                yield i

        self.assertEqual(list(f()), [1, 2, 4])

    def test_unroll_range_source(self):
        @pragma.unroll(return_source=True)
        def f():
            for i in range(3):
                yield i

        result = dedent('''
        def f():
            yield 0
            yield 1
            yield 2
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_unroll_list_source(self):
        @pragma.unroll(return_source=True)
        def f():
            for i in [1, 2, 4]:
                yield i

        result = dedent('''
        def f():
            yield 1
            yield 2
            yield 4
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_unroll_dyn_list_source(self):
        @pragma.unroll(return_source=True)
        def f():
            x = 3
            a = [x, x, x]
            for i in a:
                yield i
            x = 4
            a = [x, x, x]
            for i in a:
                yield i

        result = dedent('''
        def f():
            x = 3
            a = [x, x, x]
            yield 3
            yield 3
            yield 3
            x = 4
            a = [x, x, x]
            yield 4
            yield 4
            yield 4
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_unroll_dyn_list(self):
        def summation(x=0):
            a = [x, x, x]
            v = 0
            for _a in a:
                v += _a
            return v

        summation_source = pragma.unroll(return_source=True)(summation)
        summation = pragma.unroll(summation)

        code = dedent('''
        def summation(x=0):
            a = [x, x, x]
            v = 0
            v += x
            v += x
            v += x
            return v
        ''')
        self.assertEqual(summation_source.strip(), code.strip())
        self.assertEqual(summation(), 0)
        self.assertEqual(summation(1), 3)
        self.assertEqual(summation(5), 15)

    def test_unroll_2range_source(self):
        @pragma.unroll(return_source=True)
        def f():
            for i in range(3):
                for j in range(3):
                    yield i + j

        result = dedent('''
        def f():
            yield 0 + 0
            yield 0 + 1
            yield 0 + 2
            yield 1 + 0
            yield 1 + 1
            yield 1 + 2
            yield 2 + 0
            yield 2 + 1
            yield 2 + 2
        ''')
        self.assertEqual(f.strip(), result.strip())



class TestDictStack(TestCase):
    def test_most(self):
        stack = pragma.DictStack()
        stack.push({'x': 3})
        stack.push()
        stack['x'] = 4
        self.assertEqual(stack['x'], 4)
        res = stack.pop()
        self.assertEqual(res['x'], 4)
        self.assertEqual(stack['x'], 3)
        self.assertIn('x', stack)
        stack.items()
        stack.keys()
        del stack['x']
        self.assertNotIn('x', stack)
