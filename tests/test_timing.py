from time import sleep
from unittest import TestCase
import sys

from miniutils.capture_output import captured_output
from miniutils.timing import timed_call, make_timed, tic


class TestTiming(TestCase):
    def test_timed_call(self):
        def f(a, *, x=1, sleep_dur=0.1):
            sleep(sleep_dur)
            return a * x

        with captured_output() as (out, err, log):
            self.assertEqual(timed_call(f, 2, x=3, sleep_dur=0.11), 6)
        out = log()
        print("<test_err>\n{}\n</test_err>".format(out), sys.stderr)
        self.assertRegex(err, r'0\.1\d+s')

    def test_make_timed(self):
        @make_timed
        def g(a, *, x=1, sleep_dur=0.1):
            sleep(sleep_dur)
            return a * x

        with captured_output() as (out, err, log):
            self.assertEqual(g(2, x=3, sleep_dur=0.11), 6)
        out = log()
        print("<test_err>\n{}\n</test_err>".format(out), sys.stderr)
        self.assertRegex(err, r'0\.1\d+s')

    def test_tic(self):
        with captured_output() as (out, err, log):
            toc = tic(fmt='__{message}:{diff:0.1f}:{total:0.1f}__')
            sleep(0.201)
            toc('1')
            sleep(.101)
            toc('2')
        out = log()
        print("<test_err>\n{}\n</test_err>".format(out), sys.stderr)
        err_lines = err.strip().split('\n')
        self.assertEqual(len(err_lines), 2)
        first, second = err_lines
        self.assertRegex(first, r'__1:0\.2:0\.2__')
        self.assertRegex(second, r'__2:0\.1:0\.3__')
