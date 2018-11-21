#!/usr/bin/env python3

import json
import os.path

with open(os.environ['CONFIGURATION_FILE']) as c:
    config = json.load(c)

if 'range' in config['indices']:
    start, end = config['indices']['range']
else:
    raise ValueError('Unknown range specification!: ' + config['indices'])

index_to_output_directory = config['index_to_output_directory']
index_to_measures_directory = config['index_to_measures_directory']

for i in range(start, end):
    file_name = os.path.join(
        index_to_output_directory[str(i)], 'the_file')
    with open(file_name, 'w') as f:
        f.write(f'index is: {i}')
    print(i)
