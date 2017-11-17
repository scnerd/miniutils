import sys
from unittest import TestCase

from miniutils.capture_output import captured_output


class TestLogging(TestCase):
    def setUp(self):
        from miniutils.logs import disable_logging
        disable_logging()

    def test_logging_imports(self):
        from miniutils.logs import disable_logging
        disable_logging()

        with captured_output() as (out, err):
            import miniutils.logs_base as logger
            logger.logger = None  # This is default, but might be altered by another earlier test
            logger.critical('__1__')
            from miniutils.logs import enable_logging
            log = enable_logging(use_colors=False, format_str=r'%(levelname)s|%(message)s')
            log.critical('__2__')
            logger.critical('__3__')
        err_lines = err().strip().split('\n')
        if len(err_lines) != 3:
            raise Exception('\n'.join(err_lines))
        first, second, third = err_lines
        self.assertEqual(first, '__1__')
        self.assertEqual(second.lower(), 'critical|__2__')
        self.assertEqual(third.lower(), 'critical|__3__')

    def test_log_dir(self):
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as dir:
            from miniutils.logs import enable_logging
            log = enable_logging(logdir=dir)
            log.critical('TEST')
            import time
            time.sleep(1)

            #print("\n\n".join(open(f).read() for f in os.listdir(dir) if os.path.isfile(f)))
            self.assertTrue(any('TEST' in open(f).read() for f in os.listdir(dir) if os.path.isfile(f)))

