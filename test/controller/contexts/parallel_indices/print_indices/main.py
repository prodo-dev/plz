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
    # Note: keys in json objects are always strings, so this uses str(i)
    output_directory = index_to_output_directory[str(i)]
    file_name = os.path.join(output_directory, 'the_file')
    with open(file_name, 'w') as f:
        f.write(f'index is: {i}')
    print(i)

    measures_name = os.path.join(
        index_to_measures_directory[str(i)], 'accuracy')

    with open(measures_name, 'w') as f:
        json.dump(i, f)
