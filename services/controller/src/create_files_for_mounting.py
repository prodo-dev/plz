#!/usr/bin/env python3

import json
import os
import os.path
import sys
import tempfile
from typing import Dict

tmp = os.path.join(os.environ['HOME'], '.batman', 'tmp')


def create_files_for_mounting(files: Dict[str, str]) -> Dict[str, str]:
    volume_mounts = {}
    os.makedirs(tmp, exist_ok=True)
    for container_path, file_contents in files.items():
        with tempfile.NamedTemporaryFile(
                mode='w+', dir=tmp, delete=False) as f:
            f.write(file_contents)
            host_path = f.name
            volume_mounts[host_path] = container_path
    return volume_mounts


def main():
    files = json.load(sys.stdin)
    volume_mounts = create_files_for_mounting(files)
    json.dump(volume_mounts, sys.stdout, indent=2)


if __name__ == '__main__':
    main()
