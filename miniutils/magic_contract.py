from contracts import contract, new_contract
from contracts.library import Extension as _Ext
from miniutils.opt_decorator import optional_argument_decorator


@optional_argument_decorator
def magic_contract(*args, **kwargs):
    """Drop-in replacement for ``pycontracts.contract`` decorator, except that it supports locally-visible types

    :param args: Arguments to pass to the ``contract`` decorator
    :param kwargs: Keyword arguments to pass to the ``contract`` decorator
    :return: The contracted function
    """
    def inner_decorator(f):
        for name, val in f.__globals__.items():
            if not name.startswith('_') and name not in _Ext.registrar and isinstance(val, type):
                new_contract(name, val)
        return contract(*args, **kwargs)(f)

    return inner_decorator
