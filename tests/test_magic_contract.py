from unittest import TestCase


import contracts
contracts.enable_all()
import functools
from miniutils.magic_contract import magic_contract
from contracts.interface import ContractNotRespected


@functools.lru_cache(3)
@magic_contract
def fib(n):
    """Computes the n'th fibonacci number. Tests basic contract functionality

    :param n: The number of fibonacci numbers to compute
    :type n: int,>=0
    :return: The fibonnaci number
    :rtype: int,>=0
    """
    assert n >= 0;
    if n == 0:
        return 0
    elif n == 1:
        return 1
    else:
        return fib(n-1) + fib(n-2)


class ObjA:
    pass


class ObjB:
    pass


@magic_contract
def sample_func(a):
    """A function that requires an A object

    :param a: A thing
    :type a: ObjA
    :return: What you gave it
    :rtype: ObjB
    """
    return ObjB()


class TestMagicContract(TestCase):
    def setUp(self):
        import contracts
        contracts.enable_all()

    def test_magic_contract_1(self):
        fib(3)
        fib(5)
        fib(10)
        self.assertRaises(ContractNotRespected, fib, -1)
        self.assertRaises(ContractNotRespected, fib, 2.1)
        self.assertRaises(ContractNotRespected, fib, ObjA())

    def test_magic_contract_2(self):
        sample_func(ObjA())
        self.assertRaises(ContractNotRespected, sample_func, ObjB())
