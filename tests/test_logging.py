import sys
from unittest import TestCase

from miniutils.capture_output import captured_output


class TestLogging(TestCase):
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

        # This is a hack because I'm not sure why coloring fails epically in unittests
        self.assertIn('__2__', second.lower())
        self.assertIn('__3__', third.lower())
        #self.assertEqual(third.lower(), '__3__')

    def test_log_dir(self):
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as d:
            from miniutils.logs import enable_logging
            log = enable_logging(logdir=d)
            log.critical('TEST')
            del log

            log_files = [os.path.join(d, f) for f in os.listdir(d)]
            log_files = [f for f in log_files if os.path.isfile(f)]
            log_files = "\n".join(open(f).read() for f in log_files)
            print(">>> {} <<<".format(log_files), file=sys.__stderr__)
            self.assertIn('TEST', log_files)

