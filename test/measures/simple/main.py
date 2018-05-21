#!/usr/bin/env python3

import json
import os.path

with open(os.environ['CONFIGURATION_FILE']) as c:
    config = json.load(c)

summary_measures_file_name = config["summary_measures_file_name"]
with open(summary_measures_file_name, 'w') as f:
    json.dump({'loss': 0.42}, f)

