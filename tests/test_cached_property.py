from collections import defaultdict
from unittest import TestCase

import numpy as np

from miniutils.caching import CachedProperty
from miniutils.capture_output import captured_output


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
        return Matrix(self.array.T.dot(self.array))

    @CachedProperty()
    def pca_basis(self):
        return self.covariance.eigenvectors


class Printer:
    @CachedProperty('b', settable=True)
    def a(self):
        print("Running a")
        return 5

    @CachedProperty('c', is_collection=True, settable=True)
    def b(self):
        print("Running b")
        return [self.a] * 100

    @CachedProperty('d', threadsafe=False)
    def c(self):
        print("Running c")
        return sum(self.b)

    @CachedProperty()
    def d(self):
        print("Running d")
        return str(self.c ** 2)


# noinspection PyArgumentList
class CollectionProperties:
    @CachedProperty('target', is_collection=True)
    def basic_list(self):
        return [1, 2, 3]

    @CachedProperty('target', settable=True, is_collection=True)
    def settable_list(self):
        return [1, 2, 3]

    @CachedProperty('target', settable=True, is_collection=True, allow_collection_mutation=False)
    def settable_immutable_list(self):
        return [1, 2, 3]

    @CachedProperty('target', is_collection=True)
    def basic_set(self):
        return {1, 2, 3}

    @CachedProperty('target', is_collection=True)
    def basic_dict(self):
        return dict(a=1, b=2, c=3)

    @CachedProperty('target', is_collection=True)
    def basic_defaultdict(self):
        return defaultdict(int, dict(a=1, b=2, c=3))

    @CachedProperty('target', is_collection=True, allow_collection_mutation=False)
    def locked_list(self):
        return [1, 2, 3]

    @CachedProperty('target', is_collection=True, allow_collection_mutation=False)
    def locked_set(self):
        return {1, 2, 3}

    @CachedProperty('target', is_collection=True, allow_collection_mutation=False)
    def locked_dict(self):
        return dict(a=1, b=2, c=3)

    @CachedProperty('target', is_collection=True, allow_collection_mutation=False)
    def locked_defaultdict(self):
        return defaultdict(int, dict(a=1, b=2, c=3))

    @CachedProperty()
    def target(self):
        return True


class TestCachedProperty(TestCase):
    def test_matrix(self):
        np.random.seed(0)
        m = Matrix(np.random.normal(size=(10, 10)))
        self.assertIsNotNone(m.pca_basis)
        self.assertFalse(m._need_pca_basis)
        del m.pca_basis
        self.assertTrue(m._need_pca_basis)
        self.assertFalse(m.covariance._need_eigen)
        m.array = np.random.normal(size=(10, 10))
        self.assertTrue(m.covariance._need_eigen)
        self.assertIsNotNone(m.pca_basis)
        self.assertFalse(m.covariance._need_eigen)

    def test_printer_assign_iterable(self):
        with captured_output() as (out, err):
            p = Printer()
            self.assertEqual(p.c, 500)
            p.b[0] = 0
            self.assertEqual(p.c, 495)
            self.assertEqual(p.c, 495)
            p.b = [1, 2, 3]
            self.assertEqual(p.c, 6)
            self.assertEqual(p.c, 6)
            del p.a
            self.assertEqual(p.d, '250000')
        out = out()
        self.assertEqual(out.strip(),
                         '\n'.join('Running {}'.format(s) for s in list('cbaccdcba')))

    def test_cached_collection_mutable(self):
        p = Printer()
        with captured_output():
            self.assertEqual(p.b[0], p.a)

    def test_unsettable(self):
        i = Printer()

        def try_not_allowed():
            i.c = True

        self.assertRaises(AttributeError, try_not_allowed)

    def test_mutable_collection_assign(self):
        i = CollectionProperties()

        def try_set(l, k, v):
            self.assertTrue(i.target)
            self.assertFalse(i._need_target)
            l[k] = v
            self.assertEqual(l[k], v)
            self.assertTrue(i._need_target)

        try_set(i.basic_list, 0, -1)
        try_set(i.basic_dict, 'a', -1)
        try_set(i.basic_dict, 'new_key', -1)
        try_set(i.basic_defaultdict, 'a', -1)
        try_set(i.basic_defaultdict, 'new_key', -1)

    def test_immutable_collection_assign(self):
        i = CollectionProperties()

        def try_set(l, k, v):
            l[k] = v

        self.assertRaises(AttributeError, try_set, i.locked_list, 0, -1)
        self.assertRaises(AttributeError, try_set, i.locked_dict, 'a', -1)
        self.assertRaises(AttributeError, try_set, i.locked_defaultdict, 'a', -1)
        self.assertRaises(AttributeError, try_set, i.locked_defaultdict, 'new_key', -1)
        self.assertRaises(AttributeError, i.locked_dict.update, {'a': -1})

    def test_mutable_collection_delete(self):
        i = CollectionProperties()

        def try_del(l, k):
            self.assertTrue(i.target)
            self.assertFalse(i._need_target)
            del l[k]
            self.assertTrue(i._need_target)

        try_del(i.basic_list, 0)
        try_del(i.basic_dict, 'a')
        try_del(i.basic_defaultdict, 'a')

    def test_immutable_collection_delete(self):
        i = CollectionProperties()

        def try_del(l, k):
            del l[k]

        self.assertRaises(AttributeError, try_del, i.locked_list, 0)
        self.assertRaises(AttributeError, try_del, i.locked_dict, 'a')
        self.assertRaises(AttributeError, try_del, i.locked_defaultdict, 'a')

    def test_dict_update(self):
        i = CollectionProperties()
        self.assertTrue(i.target)
        self.assertFalse(i._need_target)
        i.basic_dict.update({'a': -1, 'new_key': -1})
        self.assertEqual(i.basic_dict['a'], -1)
        self.assertEqual(i.basic_dict['new_key'], -1)
        self.assertTrue(i._need_target)

    def test_mutable_list_properties(self):
        i = CollectionProperties()
        self.assertTrue(i.target)
        self.assertFalse(i._need_target)

        reversed(i.basic_list)
        self.assertFalse(i._need_target)

        str(i.basic_list)
        self.assertFalse(i._need_target)

        repr(i.basic_list)
        self.assertFalse(i._need_target)

        self.assertTrue(1 in i.basic_list)
        self.assertFalse(i._need_target)

        len(i.basic_list)
        self.assertFalse(i._need_target)

        i.basic_dict.get('a', 0)
        self.assertFalse(i._need_target)

        i.basic_set.union(i.basic_set)
        self.assertFalse(i._need_target)

        i.basic_set.intersection(i.basic_set)
        self.assertFalse(i._need_target)

        i.basic_set.difference(i.basic_set)
        self.assertFalse(i._need_target)
