#!/usr/bin/env python3

import json
import os
import sys
from typing import Iterable


def delete_files(files: Iterable[str]):
    for host_path in files:
        os.remove(host_path)


def main():
    files = json.load(sys.stdin)
    delete_files(files)


if __name__ == '__main__':
    main()
