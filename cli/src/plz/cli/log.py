import logging
import sys
from collections import defaultdict


def log_debug(message: str):
    logging.getLogger(__name__).debug(':: ' + message)


def log_info(message: str):
    logging.getLogger(__name__).info(message)


def _format_info(message: str, use_emojis: bool) -> str:
    is_a_tty = sys.stdout.isatty()
    message_frags = [
        # Change to yellow
        ('\x1b[33m', is_a_tty and not use_emojis),
        # OK emoji
        ('\U0001F44C ' if is_a_tty and use_emojis else '=> ', True),
        # End yellow
        ('\x1b[0m', is_a_tty and not use_emojis),
        # Change to green
        ('\x1b[32m', is_a_tty),
        (message, True),
        # End green
        ('\x1b[0m', is_a_tty)]
    return ''.join(f for f, show in message_frags if show)


def log_warning(message):
    logging.getLogger(__name__).warning(message)


def _format_warning(message: str, use_emojis: bool) -> str:
    is_a_tty = sys.stdout.isatty()
    message_frags = [
        # Change to yellow
        ('\x1b[33m', is_a_tty and not use_emojis),
        # Pensive emoji
        ('\U0001F914 ' if is_a_tty and use_emojis else '** ', True),
        # End yellow
        ('\x1b[0m', is_a_tty and not use_emojis),
        # Change to yellow
        ('\x1b[33m', is_a_tty),
        (message, True),
        # End yellow
        ('\x1b[0m', is_a_tty)]
    return ''.join(f for f, shown in message_frags if shown)


def log_error(message):
    logging.getLogger(__name__).error(message)


def _format_error(message, use_emojis):
    is_a_tty = sys.stdout.isatty()
    message_frags = [
        # Change to red
        ('\x1b[31m', is_a_tty and not use_emojis),
        # Flushed emoji
        ('\U0001F633 ' if is_a_tty and use_emojis else '!! ', True),
        # End red
        ('\x1b[0m', is_a_tty and not use_emojis),
        # Change to red
        ('\x1b[31m', is_a_tty),
        (message, True),
        # End red
        ('\x1b[0m', is_a_tty)]
    return ''.join(f for f, shown in message_frags if shown)


def setup_logger(configuration):
    level = configuration.log_level or (
        logging.INFO if not configuration.debug else logging.DEBUG)
    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    logger_handler = logging.StreamHandler(stream=sys.stdout)
    logger_handler.setFormatter(_LogFormatter(configuration.use_emojis))
    logger.addHandler(logger_handler)


class _LogFormatter(logging.Formatter):
    def __init__(self, use_emojis: bool):
        super().__init__()
        self.use_emojis = use_emojis
        self.formatter_map = defaultdict(lambda: lambda msg, _: msg)
        self.formatter_map.update({
            logging.INFO: _format_info,
            logging.WARNING: _format_warning,
            logging.ERROR: _format_error,
        })

    def format(self, record: logging.LogRecord):
        return self.formatter_map[record.levelno](
            record.getMessage(), self.use_emojis)
