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
        g.a = [1, 2, 3]
        g.b = 6

        @pragma.unroll(return_source=True)
        def f(x):
            y = 5
            a = range(3)
            b = [1, 2, 4]
            c = (1, 2, 5)
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

    def test_unroll_2list_source(self):
        @pragma.unroll(return_source=True)
        def f():
            for i in [[1, 2, 3], [4, 5], [6]]:
                for j in i:
                    yield j

        result = dedent('''
        def f():
            yield 1
            yield 2
            yield 3
            yield 4
            yield 5
            yield 6
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_external_definition(self):
        # Known bug: this works when defined as a kwarg, but not as an external variable, but ONLY in unittests...
        # External variables work in practice
        @pragma.unroll(return_source=True, a=range)
        def f():
            for i in a(3):
                print(i)

        result = dedent('''
        def f():
            print(0)
            print(1)
            print(2)
        ''')
        self.assertEqual(f.strip(), result.strip())


class TestCollapseLiterals(TestCase):
    def test_full_run(self):
        def f(y):
            x = 3
            r = 1 + x
            for z in range(2):
                r *= 1 + 2 * 3
                for abc in range(x):
                    for a in range(abc):
                        for b in range(y):
                            r += 1 + 2 + y
            return r

        import inspect
        print(inspect.getsource(f))
        print(pragma.collapse_literals(return_source=True)(f))
        deco_f = pragma.collapse_literals(f)
        self.assertEqual(f(0), deco_f(0))
        self.assertEqual(f(1), deco_f(1))
        self.assertEqual(f(5), deco_f(5))
        self.assertEqual(f(-1), deco_f(-1))

        import inspect
        print(inspect.getsource(f))
        print(pragma.collapse_literals(return_source=True)(pragma.unroll(f)))
        deco_f = pragma.collapse_literals(pragma.unroll(f))
        self.assertEqual(f(0), deco_f(0))
        self.assertEqual(f(1), deco_f(1))
        self.assertEqual(f(5), deco_f(5))
        self.assertEqual(f(-1), deco_f(-1))

    def test_basic(self):
        @pragma.collapse_literals(return_source=True)
        def f():
            return 1 + 1

        result = dedent('''
        def f():
            return 2
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_vars(self):
        @pragma.collapse_literals(return_source=True)
        def f():
            x = 3
            y = 2
            return x + y

        result = dedent('''
        def f():
            x = 3
            y = 2
            return 5
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_partial(self):
        @pragma.collapse_literals(return_source=True)
        def f(y):
            x = 3
            return x + 2 + y

        result = dedent('''
        def f(y):
            x = 3
            return 5 + y
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_constant_index(self):
        @pragma.collapse_literals(return_source=True)
        def f():
            x = [1,2,3]
            return x[0]

        result = dedent('''
        def f(y):
            x = [1, 2, 3]
            return 1
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_with_unroll(self):
        @pragma.collapse_literals(return_source=True)
        @pragma.unroll
        def f():
            for i in range(3):
                print(i + 2)

        result = dedent('''
        def f():
            print(2)
            print(3)
            print(4)
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
