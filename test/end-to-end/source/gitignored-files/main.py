#!/usr/bin/env python3

import os

for file_name in [
        'file_ignored_by_git_included_explicitly', 'file_managed_by_git'
]:
    with open(file_name) as f:
        print(f.read(), end='')

for path in ['file_managed_by_git_excluded', 'file_ignored_by_git', '.git/']:
    if os.path.exists(path):
        raise Exception(f'File {path} shouldn\'t be here')
