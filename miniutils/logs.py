from miniutils import logs_base


logger = logs_base.logger


def enable_logging(log_level='NOTSET', *, logdir=None, use_colors=True, capture_warnings=True,
                   format_str=r'%(asctime)s [%(launch_script)s | %(levelname)s]: %(message)s'):
    global logger

    import os
    import sys
    import logging.handlers

    if logdir is not None and not os.path.exists(logdir):
        os.makedirs(logdir)
    logs_base.logger = logging.getLogger()

    for handler in logs_base.logger.handlers:
        logs_base.logger.removeHandler(handler)

    logs_base.logger.setLevel(getattr(logging, log_level))

    logging.captureWarnings(capture_warnings)

    import __main__ as main
    launch_script = os.path.basename(getattr(main, '__file__', main.__name__))

    plain_formatter = logging.Formatter(fmt=format_str, style='{')
    if use_colors:
        try:
            import coloredlogs

            class SmarterColorer(coloredlogs.ColoredFormatter):
                """By default, the ColoredFormatter makes uncolored attributes into the background color. It also
                requires exact string matches for pre-named levels. This extension makes the formatter behave more
                intuitively. """

                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)

                    self.level_styles['info']['color'] = 'fore'
                    # Support upper-case colors to be equal to their lower-case default alternatives
                    self.level_styles.update({k.upper(): v for k, v in self.level_styles.items()})
                    # Make level aliases color the same as what they point to
                    aliases = coloredlogs.find_level_aliases()
                    self.level_styles.update({k.upper(): self.level_styles[v.lower()] for k, v in aliases.items()})
                    self.level_styles.update({k.lower(): self.level_styles[v.lower()] for k, v in aliases.items()})
                    # Don't assume that black is the foreground color... just find and use the foreground color
                    coloredlogs.ANSI_COLOR_CODES['fore'] = 9
                    self.field_styles['levelname']['color'] = 'fore'

                def format(self, record):
                    record.launch_script = launch_script
                    style = self.nn.get(self.level_styles, record.levelname)
                    if style:
                        record.levelname = coloredlogs.ansi_wrap(coloredlogs.coerce_string(record.levelname), **style)
                        record.msg = coloredlogs.ansi_wrap(coloredlogs.coerce_string(record.msg), **style)
                    return super().format(record)

            color_formatter = SmarterColorer(fmt=format_str)
        except ImportError:
            color_formatter = plain_formatter
    else:
        color_formatter = plain_formatter

    if logdir is not None:
        log_file_handler = logging.handlers.RotatingFileHandler(logdir, maxBytes=2e20, backupCount=10)
        log_file_handler.setFormatter(plain_formatter)
        log_file_handler.setLevel(logging.NOTSET)
        logs_base.logger.addHandler(log_file_handler)

    std_out_handler = logging.StreamHandler(sys.stderr)
    std_out_handler.setFormatter(color_formatter)
    std_out_handler.setLevel(logging.NOTSET)
    logs_base.logger.addHandler(std_out_handler)

    logger = logs_base.logger
    return logs_base.logger


enable_logging()
