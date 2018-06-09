#!/usr/bin/env python3

import glob

for file_name in sorted(glob.glob('**/file*', recursive=True)):
    print(file_name)
