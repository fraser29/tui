import logging

# Add a NullHandler to prevent "No handlers could be found" warnings
# when tui is used as a library without logging configured.
logging.getLogger(__name__).addHandler(logging.NullHandler())


def set_log_level(level):
    """Set the log level for all tui package loggers.

    Args:
        level: A logging level constant (e.g. ``logging.DEBUG``,
               ``logging.INFO``, ``logging.WARNING``) or its integer
               equivalent.

    Example::

        import tui, logging
        tui.set_log_level(logging.INFO)
    """
    logging.getLogger('tui').setLevel(level)


def configure_logging(level=logging.INFO, fmt=None):
    """Attach a :class:`logging.StreamHandler` to the tui package logger.

    Call this once at the start of your application to enable console output
    from tui.  If your application already configures Python logging globally
    you do not need this; just call :func:`set_log_level` instead.

    Args:
        level: Logging level to apply (default: ``logging.INFO``).
        fmt:   Format string for log records.  Defaults to a format that
               includes timestamp, logger name and level.

    Example::

        import tui
        tui.configure_logging()          # INFO and above
        tui.configure_logging(level=logging.DEBUG)
    """
    if fmt is None:
        fmt = '%(asctime)s  %(name)-35s  %(levelname)-8s  %(message)s'
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))
    tui_logger = logging.getLogger('tui')
    tui_logger.addHandler(handler)
    tui_logger.setLevel(level)
