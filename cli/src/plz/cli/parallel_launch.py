import json
import os
import subprocess

with open(os.environ['CONFIGURATION_FILE'], 'r') as f:
    config = json.load(f)

start, end = config['indices']['range']
index_to_output_directory = config['index_to_output_directory']
input_directory = config['input_directory']

with open(os.path.join(input_directory, 'repo_list.json')) as f:
    repo_list = json.load(f)

for i in range(start, end):
    print('Processing:', repo_list[i])
    process = subprocess.Popen(
        ['node', 'main.js', repo_list[i]],
        stdout=subprocess.PIPE,
        universal_newlines=True)
    output, error = process.communicate()
    print('====Out====')
    for l in output.splitlines():
        print('[' + str(i) + ']: ' + l)
    print('====Error====')
    for l in error.splitlines():
            print('[' + str(i) + ']: ' + l)
