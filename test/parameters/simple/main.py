#!/usr/bin/env python3

import json
import os.path

with open(os.environ['CONFIGURATION_FILE']) as c:
    config = json.load(c)
parameters = config["parameters"]

output_file = f'{config["output_directory"]}/foo/bar'
os.makedirs(os.path.dirname(output_file))
with open(output_file, 'w') as f:
    f.write(f'foo = {parameters.get("foo")}\n'
            f'bar = {parameters.get("bar")}\n')


summary_measures_file_name = config["summary_measures_file_name"]
with open(summary_measures_file_name, 'w') as f:
    json.dump({'loss': 0.42}, f)
