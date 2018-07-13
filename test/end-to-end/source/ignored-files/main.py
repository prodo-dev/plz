#!/usr/bin/env python3

import glob

for file_name in glob.glob('file_*'):
    print(file_name)
    with open(file_name) as f:
        print(f.read(), end='')
