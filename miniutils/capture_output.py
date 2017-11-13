from contextlib import contextmanager
import sys
from io import StringIO
import logging


@contextmanager
def captured_output():
    # https://stackoverflow.com/questions/4219717/how-to-assert-output-with-nosetest-unittest-in-python
    no, ne, nl = StringIO(), StringIO(), StringIO()
    oo, oe = sys.stdout, sys.stderr
    log_handler = logging.StreamHandler(nl)
    logging.getLogger().addHandler(log_handler)
    try:
        sys.stdout, sys.stderr = no, ne
        yield lambda: no.getvalue(), lambda: ne.getvalue(), lambda: nl.getvalue()
    finally:
        sys.stdout, sys.stderr = oo, oe
        logging.getLogger().removeHandler(log_handler)
