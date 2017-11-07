import functools


def optional_argument_decorator(_decorator):
    """Decorate your decorator with this to allow it to always receive *args and **kwargs, making @deco equivalent to
    @deco()"""

    def inner_decorator_make(*args, **kwargs):
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            func = args[0]
            args = tuple()
            kwargs = dict()
        else:
            func = None

        decorator = _decorator(*args, **kwargs)

        def inner_decorator_maker(_func):
            return functools.wraps(_func)(decorator(_func))

        if func:
            return inner_decorator_maker(func)
        else:
            return inner_decorator_maker

    return inner_decorator_make
