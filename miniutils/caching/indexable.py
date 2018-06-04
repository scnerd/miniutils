import functools
from functools import partial


class _LazyDictionary:
    def __init__(self, getter_closure, on_modified, settable=False, values=None):
        self._known = dict(values or {})
        self._cache = {}
        self._key_errors = {}
        self._closure = getter_closure
        self._on_modified = on_modified
        self.settable = settable

    def __getitem__(self, item):
        if item in self._known:
            return self._known[item]

        if item in self._key_errors:
            raise KeyError(*self._key_errors[item])

        if item not in self._cache:
            try:
                self._cache[item] = self._closure(item)
            except KeyError as e:
                self._key_errors[item] = e.args
                raise e

        return self._cache[item]

    def __setitem__(self, key, value):
        if not self.settable:
            raise AttributeError("{} is not settable".format(self))
        self._known[key] = value
        if key in self._cache and self._cache[key] is not value:
            self._on_modified()

    def __delitem__(self, key):
        if key in self._known:
            del self._known[key]
        if key in self._cache:  # Not elif, we want to purge all knowledge about this key
            del self._cache[key]
        if key in self._key_errors:
            del self._key_errors[key]
        self._on_modified()

    @property
    def __doc__(self):
        return self._closure.__doc__

    def get(self, key, default):
        try:
            return self[key]
        except KeyError:
            return default

    def update(self, new_values):
        if not self.settable:
            raise AttributeError("{} is not settable".format(self))
        self._known.update(new_values)
        self._on_modified()


class LazyDictionary:
    caches = []

    def __init__(self, *affects, allow_collection_mutation=False):
        """Marks this indexable property to be a cached dictionary. Delete this property to remove the cached value and force it to be rerun.

        :param affects: Strings that list the names of the other properties in this class that are directly invalidated
         when this property's value is altered
        :param allow_collection_mutation: Whether or not the returned collection should allow its values to be altered
        """
        self.affected_properties = affects
        self.allow_mutation = allow_collection_mutation

    def __call__(self, f, name=None):
        self.f = f
        self.name = name = name or f.__name__
        cache_name = '_' + name

        def reset_dependents(inner_self):
            for affected in self.affected_properties:
                delattr(inner_self, affected)

        @functools.wraps(f)
        def inner_getter(inner_self):
            if not hasattr(inner_self, cache_name):
                new_indexable = _LazyDictionary(functools.wraps(f)(partial(f, inner_self)),
                                                partial(reset_dependents, inner_self),
                                                self.allow_mutation)
                setattr(inner_self, cache_name, new_indexable)
            return getattr(inner_self, cache_name)

        def inner_deleter(inner_self):
            if hasattr(inner_self, cache_name):
                delattr(inner_self, cache_name)
                # If we make this recursion conditional on the cache existing, we prevent dependency cycles from
                # breaking the code
                reset_dependents(inner_self)

        return property(fget=inner_getter, fdel=inner_deleter, doc=self.f.__doc__)