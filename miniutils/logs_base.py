import logging
import sys
from functools import partial

logger = None


def proxy_log(msg, *args, **kwargs):
    if logger is None:
        print(msg, file=sys.stderr, flush=True)
    else:
        lvl = kwargs.pop('log_level', 'INFO')
        if isinstance(lvl, str):
            lvl = logging._nameToLevel[lvl]
        logger.log(lvl, msg, *args, **kwargs)


debug = partial(proxy_log, log_level='DEBUG')
info = partial(proxy_log, log_level='INFO')
warn = partial(proxy_log, log_level='WARNING')
warning = partial(proxy_log, log_level='WARNING')
error = partial(proxy_log, log_level='ERROR')
critical = partial(proxy_log, log_level='CRITICAL')
fatal = partial(proxy_log, log_level='FATAL')


def log(log_level, msg, *args, **kwargs):
    proxy_log(msg, *args, log_level=log_level, **kwargs)
