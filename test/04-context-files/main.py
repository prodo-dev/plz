#!/usr/bin/env python3

with open('file_ignored_by_git') as f:
    print(f.read(), end='')

try:
    with open('file_managed_by_git') as f:
        raise Exception('This file shouldn\'t be here')
except FileNotFoundError:
    pass
