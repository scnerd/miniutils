import functools


def optional_argument_decorator(_decorator):
    """Decorate your decorator with this to allow it to always receive *args and **kwargs, making @deco equivalent to
    @deco()"""

    @functools.wraps(_decorator)
    def inner_decorator_make(*args, **kwargs):
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            func = args[0]
            args = tuple()
            kwargs = dict()
        else:
            func = None

        decorator = _decorator(*args, **kwargs)

        if func:
            return decorator(func)
        else:
            return decorator

    return inner_decorator_make


# class PipedFunction:
#     def __init__(self, f, *args, reversed_args=[]):
#         self.f = f
#         self.args = args
#         self.reversed_args = reversed_args
#
#     def __ror__(self, other):
#         return PipedFunction(f, self.args, self.reversed_args + [other])
#
#
# def function_piping(func)
