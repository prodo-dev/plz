#!/usr/bin/env python3

import json
import os.path

with open(os.environ['CONFIGURATION_FILE']) as c:
    config = json.load(c)

input_directory = config['input_directory']
output_directory = config['output_directory']

files = (os.path.join(directory, file)
         for (directory, _, files) in os.walk(input_directory)
         for file in files)
for input_file_path in files:
    filename = os.path.relpath(input_file_path, input_directory)
    output_file_path = os.path.join(output_directory, filename)
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
    with open(input_file_path, 'r') as input_file:
        with open(output_file_path, 'w') as output_file:
            contents: str = input_file.read()
            output_file.write(contents.upper())
    print(filename)
