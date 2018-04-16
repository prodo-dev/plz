import sys


def log_debug(message):
    print('::', message)


def log_info(message):
    if sys.stdout.isatty():
        print('\x1b[33m', end='')
    print('=> ', end='')
    if sys.stdout.isatty():
        print('\x1b[0m', end='')
        print('\x1b[32m', end='')
    print(message, end='')
    if sys.stdout.isatty():
        print('\x1b[0m', end='')
    print()


def log_error(message):
    isatty = sys.stdout.isatty()
    if isatty:
        print('\x1b[31m', end='')
    print('!!', message, end='')
    if isatty:
        print('\x1b[0m', end='')
    print()
