"""
A Toolbox of small shared utilities.
"""
import sys
import logging
from typing import TextIO


def configure_logging(
        verbosity: int,
        format: str = '%(asctime)s %(levelname)s: %(message)s',
        stream: TextIO = sys.stderr
) -> None:
    """Configure the root logger for the application.

    :param: verbosity: Verbosity level (0-3), where 0=ERROR, 1=WARNING, 2=INFO, 3=DEBUG.
    :param: format: Logging format string. Defaults to '%(asctime)s %(levelname)s: %(message)s'.
    :param: stream: Output stream for log messages. Defaults to sys.stderr.
    :return: None
    """
    levels = [logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
    logging.basicConfig(
        level=levels[min(verbosity, len(levels) - 1)],
        format=format,
        stream=stream
    )
