#!/usr/bin/env python3

for file_name in ['file_ignored_by_git_included_explicitly',
                  'file_managed_by_git']:
    with open(file_name) as f:
        print(f.read(), end='')

for file_name in ['file_managed_by_git_excluded', 'file_ignored_by_git']:
    try:
        with open(file_name) as f:
            raise Exception(f'File {file_name} shouldn\'t be here')
    except FileNotFoundError:
        pass
