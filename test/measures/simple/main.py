#!/usr/bin/env python3

import json
import os.path
import time

with open(os.environ['CONFIGURATION_FILE']) as c:
    config = json.load(c)

summary_measures_path = config["summary_measures_path"]
for i in range(1000):
    with open(summary_measures_path, 'w') as f:
        json.dump({'loss': 0.42 - i*0.0001}, f)
    time.sleep(1)

