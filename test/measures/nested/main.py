#!/usr/bin/env python3

import json
import os.path
import time

with open(os.environ['CONFIGURATION_FILE']) as c:
    config = json.load(c)

summary_measures_path = config["summary_measures_path"]

for i in range(4):
    os.makedirs(os.path.join(summary_measures_path, str(i)))

for i in range(11):
    with open(os.path.join(
            summary_measures_path, str(i%4), str(i)), 'w') as f:
        json.dump({'loss': 42 - i}, f)

