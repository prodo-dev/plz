#!/usr/bin/env python3

import json
import os.path

with open(os.environ['CONFIGURATION_FILE']) as c:
    config = json.load(c)

summary_measures_path = config["summary_measures_path"]
with open(summary_measures_path, 'w') as f:
    json.dump({'loss': 0.42}, f)
