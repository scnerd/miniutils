import functools
from contextlib import contextmanager
from threading import RLock
import inspect


@contextmanager
def empty_context_manager():
    yield


class CachedCollection:
    IGNORED_GETS = ['get', 'union', 'intersection', 'difference', 'copy']

    def __init__(self, value, on_update, container_self, allow_update):
        self.collection = value
        self.on_update = lambda: on_update(container_self)
        self.allow_update = allow_update

    def __getitem__(self, item):
        return self.collection[item]

    def __missing__(self, key):
        return self.collection.__missing__(key)

    def __setitem__(self, key, value):
        if not self.allow_update:
            raise AttributeError("Attempted to set value in an immutable cached collection")
        self.collection[key] = value
        self.on_update()

    def __delitem__(self, key):
        if not self.allow_update:
            raise AttributeError("Attempted to delete item from an immutable cached collection")
        del self.collection[key]
        self.on_update()

    def __iter__(self):
        return iter(self.collection)

    def __reversed__(self):
        return reversed(self.collection)

    def __contains__(self, item):
        return item in self.collection

    def __len__(self):
        return len(self.collection)

    def __str__(self):
        return str(self.collection)

    def __repr__(self):
        return "<Cached {}>".format(repr(self.collection))

    def __getattr__(self, item):
        res = getattr(self.collection, item)

        # TODO: make this more robust somehow... but how without deep copy and equality compare?
        # e.g., how to detect that dict().update changes its underlying data?
        # For now, manually annotate methods which are incapable of changing underlying data, and assume all others do
        if item in self.IGNORED_GETS:
            return res
        else:
            @functools.wraps(res)
            def wrapped_res(*args, **kwargs):
                if not self.allow_update:
                    raise AttributeError("Attempted to modify an immutable cached collection (in call to {})"
                                         .format(res.__name__))
                r = res(*args, **kwargs)
                self.on_update()
                return r

            return wrapped_res


# TODO: Created a CachedAttribute/functional version of this, e.g. to use in the constructor
# def __init__(self):
#     self.attribute = CachedAttribute(lambda: something_slow(self))
# You'll need to pull in the 'self' from the frame in which CachedAttribute gets called
# The upside is that you shrink essentially a 3-liner into a 1-liner for simple cases

# TODO: Create a general purpose decorator that just allows other properties or methods to fit into the dependency chain

class CachedProperty:
    caches = []

    def __init__(self, *affects, settable=False, threadsafe=True, is_collection=False, allow_collection_mutation=True):
        """Marks this property to be cached. Delete this property to remove the cached value and force it to be rerun.

        :param affects: Strings that list the names of the other properties in this class that are directly invalidated
         when this property's value is altered
        :param settable: Whether or not to allow this property to have values assigned directly to it
        :param threadsafe: Whether or not to restrict execution of this property's code to a single thread at a time
         (safe for recursive calls)
        :param is_collection: Whether or not this property returns a collection (currently supports lists, sets, and
         dictionaries; others might not work exactly as expected)
        :param allow_collection_mutation: Whether or not the returned collection should allow its values to be altered
        """
        self.affected_properties = affects
        self.settable = settable
        self.threadsafe = threadsafe
        self.is_collection = is_collection
        self.allow_collection_mutation = allow_collection_mutation
        self.name = '???'
        self.f = None
        CachedProperty.caches.append(self)

    def __call__(self, f):
        self.f = f
        self.name = name = f.__name__
        flag_name = '_need_' + name
        cache_name = '_' + name

        def reset_dependents(inner_self):
            for affected in self.affected_properties:
                delattr(inner_self, affected)

        if self.is_collection:
            orig_f = f

            @functools.wraps(orig_f)
            def f(inner_self):
                return CachedCollection(orig_f(inner_self), reset_dependents, inner_self,
                                        self.allow_collection_mutation)

        if self.threadsafe:
            lock_name = '_lock_' + name

            @functools.wraps(f)
            def inner_getter(inner_self):
                if not hasattr(inner_self, lock_name):
                    setattr(inner_self, lock_name, RLock())
                with getattr(inner_self, lock_name):
                    if getattr(inner_self, flag_name, True):
                        setattr(inner_self, cache_name, f(inner_self))
                        setattr(inner_self, flag_name, False)
                return getattr(inner_self, cache_name)

        else:
            @functools.wraps(f)
            def inner_getter(inner_self):
                if getattr(inner_self, flag_name, True):
                    setattr(inner_self, cache_name, f(inner_self))
                    setattr(inner_self, flag_name, False)
                return getattr(inner_self, cache_name)

        def inner_deleter(inner_self):
            assert getattr(inner_self, flag_name, True) or hasattr(inner_self, cache_name)
            setattr(inner_self, flag_name, True)
            if hasattr(inner_self, cache_name):
                delattr(inner_self, cache_name)
                # If we make this recursion conditional on the cache existing, we prevent dependency cycles from
                # breaking the code
                reset_dependents(inner_self)

        if not self.settable:
            return property(fget=inner_getter, fdel=inner_deleter, doc=self.f.__doc__)
        else:
            # TODO: allow custom setter (preferably using the property.setter decorator)
            def inner_setter(inner_self, value):
                setattr(inner_self, cache_name, value)
                setattr(inner_self, flag_name, False)
                reset_dependents(inner_self)

            return property(fget=inner_getter, fset=inner_setter, fdel=inner_deleter, doc=self.f.__doc__)


def _get_class_that_defined_method(method):
    """https://stackoverflow.com/questions/3589311/get-defining-class-of-unbound-method-object-in-python-3"""
    if inspect.ismethod(method):
        for cls in inspect.getmro(method.__self__.__class__):
            if cls.__dict__.get(method.__name__) is method:
                return cls
        method = method.__func__  # fallback to __qualname__ parsing
    if inspect.isfunction(method):
        cls = getattr(inspect.getmodule(method),
                      method.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0])
        if isinstance(cls, type):
            return cls
    return getattr(method, '__objclass__', None)  # handle special descriptor objects
