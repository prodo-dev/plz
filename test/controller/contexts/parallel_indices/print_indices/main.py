#!/usr/bin/env python3

import json
import os.path

with open(os.environ['CONFIGURATION_FILE']) as c:
    config = json.load(c)

if 'range' in config['indices']:
    start, end = config['indices']['range']
else:
    raise ValueError('Unknown range specification!: ' + config['indices'])

for i in range(start, end):
    print(i)
