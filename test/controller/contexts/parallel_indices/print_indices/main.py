#!/usr/bin/env python3

import json
import os.path

with open(os.environ['CONFIGURATION_FILE']) as c:
    config = json.load(c)

index_start = config['index_start']
index_end = config['index_end']

for i in range(index_start, index_end):
    print(i)
