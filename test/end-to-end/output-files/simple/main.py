#!/usr/bin/env python3

import json
import os.path
import time

with open(os.environ['CONFIGURATION_FILE']) as c:
    config = json.load(c)

output_file = f'{config["output_directory"]}/foo/bar'
os.makedirs(os.path.dirname(output_file))
with open(output_file, 'w') as f:
    f.write('baz\n')
with open(output_file) as f:
    print(f.read(), end='')

output_file = f'{config["output_directory"]}/q/w/pee'
os.makedirs(os.path.dirname(output_file), exist_ok=True)
with open(output_file, 'w') as f:
    f.write('bee\n')
with open(output_file) as f:
    print(f.read(), end='')


time.sleep(100000)
