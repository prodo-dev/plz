#!/usr/bin/env python3

import json
import os.path

with open(os.environ['CONFIGURATION_FILE']) as c:
    config = json.load(c)

input_directory = config['input_directory']
output_directory = config['output_directory']

for filename in os.listdir(input_directory):
    with open(os.path.join(input_directory, filename)) as input_file:
        with open(os.path.join(output_directory, filename)) as output_file:
            contents: str = input_file.read()
            output_file.write(contents.upper())
