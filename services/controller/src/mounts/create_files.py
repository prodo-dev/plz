#!/usr/bin/env python3

import json
import os
import os.path
import sys
import tempfile
from typing import Dict

tmp = os.path.join(os.environ['HOME'], '.batman', 'tmp')


def create_files_for_mounting(files: Dict[str, str]) \
        -> Dict[str, Dict[str, str]]:
    volumes = {}
    os.makedirs(tmp, exist_ok=True)
    for container_path, file_contents in files.items():
        with tempfile.NamedTemporaryFile(
                mode='w+', dir=tmp, delete=False) as f:
            f.write(file_contents)
            host_path = f.name
            volumes[host_path] = {'bind': container_path, 'mode': 'ro'}
    return volumes


def main():
    files = json.load(sys.stdin)
    volumes = create_files_for_mounting(files)
    json.dump(volumes, sys.stdout, indent=2)


if __name__ == '__main__':
    main()
