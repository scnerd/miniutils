from unittest import TestCase
import numpy as np
from contextlib import contextmanager
from miniutils.caching import CachedProperty
from io import StringIO
import sys


@contextmanager
def captured_output():
    # https://stackoverflow.com/questions/4219717/how-to-assert-output-with-nosetest-unittest-in-python
    no, ne = StringIO(), StringIO
    oo, oe = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = no, ne
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = oo, oe


class Matrix:
    def __init__(self, array):
        self.array = np.array(array)

    @CachedProperty('eigen', 'covariance', settable=True)
    def array(self):
        return np.array([])

    @CachedProperty('eigenvalues', 'eigenvectors')
    def eigen(self):
        return np.linalg.eig(self.array)

    @CachedProperty()
    def eigenvalues(self):
        return self.eigen[0]

    @CachedProperty()
    def eigenvectors(self):
        return self.eigen[1]

    @CachedProperty('pca_basis')
    def covariance(self):
        return Matrix(self.array.T @ self.array)

    @CachedProperty()
    def pca_basis(self):
        return self.covariance.eigenvectors


class Printer:
    @CachedProperty('b', settable=True)
    def a(self):
        print("Running a")
        return 5

    @CachedProperty('c', is_collection=True)
    def b(self):
        print("Running b")
        return [self.a] * 100

    @CachedProperty('d')
    def c(self):
        print("Running c")
        return sum(self.b)

    @CachedProperty()
    def d(self):
        print("Running d")
        return str(self.c ** 2)


class ImmutableProperties:
    @CachedProperty()
    def immutable_property(self):
        return None

    @CachedProperty(is_collection=True, allow_collection_mutation=False)
    def immutable_list_property(self):
        return [1, 2, 3]


class TestCachedProperty(TestCase):
    def test_matrix(self):
        np.random.seed(0)
        m = Matrix(np.random.normal(size=(10, 10)))
        m.pca_basis
        self.assertFalse(m._need_pca_basis)
        del m.pca_basis
        self.assertTrue(m._need_pca_basis)
        self.assertFalse(m.covariance._need_eigen)
        m.array = np.random.normal(size=(10, 10))
        self.assertTrue(m.covariance._need_eigen)
        m.pca_basis
        self.assertFalse(m.covariance._need_eigen)

    def test_printer(self):
        with captured_output() as (out, err):
            p = Printer()
            p.a
            p.c
            p.a = 3
            p.c
            p.c
            p.b[0] = 0
            p.c
            del p.a
            p.d
        out = out.getvalue()
        self.assertEqual(out.strip(),
                         '\n'.join('Running {}'.format(s) for s in list('acbcbcdcba')))

    def test_unsettable(self):
        i = ImmutableProperties()

        def try_not_allowed():
            i.immutable_property = True

        self.assertRaises(AttributeError, try_not_allowed)

    def test_immutable_collection_1(self):
        i = ImmutableProperties()

        def try_not_allowed():
            i.immutable_list_property[0] = -1

        self.assertRaises(AttributeError, try_not_allowed)

    def test_immutable_collection_1(self):
        i = ImmutableProperties()

        def try_not_allowed():
            i.immutable_list_property.append(4)

        self.assertRaises(AttributeError, try_not_allowed)

    def test_immutable_collection_1(self):
        i = ImmutableProperties()

        def try_not_allowed():
            del i.immutable_list_property[1]

        self.assertRaises(AttributeError, try_not_allowed)
