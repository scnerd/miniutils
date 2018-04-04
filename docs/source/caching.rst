Property Cache
==============

Basic Property
++++++++++++++

In some cases, an object has properties that don't need to be computed until necessary, and once computed are generally static and could just be cached. This could be accomplished using the following simple recipe::

    class Obj:
        def __init__(self):
            self._attribute = None
            ...

        @property
        def attribute(self):
            if self._attribute is None:
                self._attribute = some_slow_computation(self)
            return self._attribute

If you want to support re-computation (besides just setting the object to ``None`` again), it's not hard to add::

    class Obj:
        def __init__(self):
            self._attribute = None
            self._need_attribute = True
            ...

        @property
        def attribute(self):
            if self._need_attribute:
                self._attribute = some_slow_computation(self)
                self._need_attribute = False
            return self._attribute

    ...
    attr1 = my_obj.attribute
    my_obj._need_attribute = True
    attr2 = my_obj.attribute  # Re-computes attribute

Adding inter-dependence between such properties is not hard, but quickly becomes verbose. In fact, all of this code is verbose relative to the simple goal: for some property ``x``, define its value, but don't actually compute it until necessary, and allow the code to make it "necessary" again. This is easy to describe, and easy to think of, but just convoluted to code (but fortunately, easy to template).

To simplify this process, ``miniutils`` provides a ``CachedProperty`` decorator that's simple by default, and moderately powerful when necessary. Let's take a look at a simple use case first, then we'll examine its capabilities::

    class Obj:
        @CachedProperty()
        def attribute(self):
            return some_slow_computation(self)


That's all you need. No need to initialize, set up flags, or anything. It's all handled automatically. A use case like above might look like::

    attr1 = my_object.attribute  # Computed the first time
    attr2 = my_object.attribute  # Loaded from cache
    assert attr1 is attr2
    del my_object.attribute  # Deletes the cached object and marks for re-computation
    attr3 = my_object.attribute  # Re-computes the value

Despite being simple to use, it's still a fairly powerful decorator:

- Like ``@property``, this method is converted to a property (in fact, the ``property`` function is used under the hood, so you don't have any ``CachedProperty`` objects floating around)
- The result is lazy-computed, just like you'd expect from a property
- The result is cached and returned instantly if not marked for re-computation (note that the object doesn't have to be hashable since there's no lookup being performed)
- Its computation can affect the computation of other properties, and thus automatically mark those properties for re-computation when needed (i.e., it maintains a dependency chain amongst CachedProperties)
- A simple setter can be automatically defined which invalidates downstream properties without needing more code (note that, at this time, you can't safely define a custom setter, you can either use the default or let the property be unsettable)
- If the property returns a basic iterable (list, dictionary, set), it's wrapped so that modifications to its content (if permitted) invalidate downstream properties.

A key feature not yet demonstrated is the ability to add dependencies amongst properties. Essentially, this defines a directed graph where resetting, re-computing, or altering upstream properties marks all dependent downstream properties for re-computation. This can be seen in the following demonstration::

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

    p = Printer()
    p.a         # Computes A
    p.c         # Computes C, during which it computes B
    p.a = 3     # Sets A, invalidating B and C (and D, if it weren't already invalid)
    p.c         # Computes C, and thus B, again
    p.c         # Returns the cached value for C
    p.b[0] = 0  # Alters a value within B (not B itself), which correctly invalidates C
    p.c         # Computes C, using cached B
    del p.a     # Invalidates A, and therefore B and C
    p.d         # Computes D, and thus C, B, and A

This isn't the complete feature set of the decorator, but it's a good initial taste of what can be accomplished using it.

.. autoclass:: miniutils.caching.CachedProperty
    :members:

    .. automethod:: __init__

Indexed Property
++++++++++++++++

Even using the above tools, it is non-concise to allow indexing into a property where values are lazily computed.

The ``LazyDictionary`` decorator allows you to write a ``__getitem__`` style property that can be used like a dictionary and has its results cached::

    class Primes:
        @LazyDictionary('is_prime')
        def primes_under(self, i):
            if i == 0:
                return []
            else:
                return self.primes_under[i-1] + ([i] if self.is_prime[i] else [])

        @LazyDictionary('primes_under')
        def is_prime(self, i):
            if not isinstance(i, int) or i < 1:
                raise ValueError("Can only check if a positive integer is prime")
            elif i in [1, 2]:
                return True
            elif i % 2 == 0:
                return False
            else:
                return all(i % p != 0 for p in self.primes_under[min(i-1, math.sqrt(i))])

    p = Primes()
    p.is_prime[5] # True, caches the fact that 1, 2, and 3 are prime
    p.is_prime[500] # False, caches all primes up to sqrt(500)
    p.is_prime[501] # False, virtually instant since it uses the cached primes used to compute is_prime[500]

The indexing notation is used and preferred to make clear that this decorator only aims to support one hashable argument, and is meant to behave like a dictionary or list. It is not iterable, since the result of that would depend on whatever prior code happened to be executed. Instead, you should iterate through all desired keys, and simply index them; that way, any that need to be re-computed are, and those that can are loaded from cache.

This plugs cleanly into ``CachedProperty``, accepting a list of properties whose values are invalidated when this dictionary is modified. It also supports allowing or disallowing explicit assignment to certain indices::

    p.is_prime[3] = False
    p.is_prime[9] # This is now True, since there is no lesser known prime

This is meant to provide a slight additional feature to having a cached dictionary