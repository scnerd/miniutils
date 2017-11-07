Miscellaneous
+++++++++++++

Code Contracts
==============

Code contracting seems like a great way to define and document your code's expected behavior, easily integrate bounds checking, and just generally write code that tries to avoid bugs. The `pycontracts <https://andreacensi.github.io/contracts/>`_ package provides this capability within python, but as soon as I started using it I realized that it was meant primarily to be robust, not concise. For example, consider the following code::

    class ObjA:
        pass

    class ObjB:
        pass

    @contract
    def sample_func(a):
        """A function that requires an A object

        :param a: A thing
        :type a: ObjA
        :return: What you gave it
        :rtype: ObjB
        """
        return ObjB()

This seems intuitive what should happen--you're not using any complex attributes of the types, merely indicating that is should be of that type--but ``pycontracts`` will croak on this because you haven't explicitly told it about your two new types.

``miniutils.magic_contract`` is a little wrapper around the ``contract`` decorator that looks through the function's local namespace, finds types that aren't already registered with ``pycontracts``, and adds them as a simple ``isinstance`` check. Using it, we can write almost the exact same code::

    class ObjA:
        pass


    class ObjB:
        pass


    @magic_contract  # Uses the magic contract
    def sample_func(a):
        """A function that requires an A object

        :param a: A thing
        :type a: ObjA
        :return: What you gave it
        :rtype: ObjB
        """
        return ObjB()

And now the function works like you'd expect. If you want to do something more complex when adding an object as a contractable type, just use ``contracts.new_contract`` like you normally would, and ``magic_contract`` won't clobber your definition. Also, since this decorator is just a wrapper around ``contracts.contract``, you can continue using ``pycontracts`` as always, and the magic contract won't affect any of the rest of your code.

.. autofunction:: miniutils.magic_contract.magic_contract

Simplifying Decorators
======================

When writing a decorator that could be used like ``@deco`` or ``@deco()``, there's a little code I've found necessary in order to make both cases function identically. I've isolated this code into another decorator (meta-decorator?) to keep my other decorators simple (since, let's be honest, decorators are usually convoluted enough as is).

Consider the following decorator definition::

    def deco(return_name=False):
        def inner_deco(func):
            def inner(*a, **kw):
                if return_name:
                    return func.__name__, func(*a, **kw)
                else:
                    return func(*a, **kw)
            return inner
        return inner_deco

    @deco()  # Works correctly
    def g(i):
        return i

    @deco(True)  # Works correctly
    def h(i):
        return i

    @deco(return_name=True)  # Works correctly
    def k(i):
        return i

    @deco  # Fails, since f gets assigned to return_names instead of func
    def f(i):
        return i

This makes sense, but is somewhat annoying when parameters aren't required, such as is the case in several built-in Python decorators. To make this last case work like the first, we can simply decorate our decorator::

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

    @deco()  # Works correctly
    def g(i):
        return i

    @deco(True)  # This still works
    def h(i):
        return i

    @deco(return_name=True)  # As does this
    def k(i):
        return i

    @deco  # Now this works too!
    def f(i):
        return i

.. autofunction:: miniutils.opt_decorator.optional_argument_decorator