import json
import os
from typing import Tuple

import sys
import time

#######################################
# Minimal plz example using only python
#######################################
# We are trying to learn the value k for the function
# f(x) = k*x
# minimising
# (x - 3 * f(x))^2 .
# (Shhh, I'll tell you a secret: it's 1/3.)

num_iterations = int(sys.argv[1])

OutputDirectory = str
InputDirectory = str


# You need to read the input from where plz left it, and write to places where
# plz will pick it up.
#
# We write a function as to obtain the input and output dirs


def get_configuration() -> Tuple[InputDirectory, OutputDirectory]:
    """Return the configuration to use

       Where we read the input from, and where we write, depend on whether we
       use plz or not. Once this is obtained, we can abstract about whether
       we are running with plz or not."""

    configuration_file = os.environ.get('CONFIGURATION_FILE', None)
    if configuration_file is not None:
        print('Running with plz!', flush=True)
        with open(configuration_file) as c:
            config = json.load(c)
        input_directory = config['input_directory']
        output_directory = config['output_directory']
        return input_directory, output_directory
    else:
        return 'input', 'output'


def get_values_for_x(input_directory: InputDirectory) -> list:
    data_file_name = os.path.join(input_directory, 'values_for_x.json')
    with open(data_file_name) as f:
        return json.load(f)


def write_model(output_directory: OutputDirectory, k: float):
    """Write "our model" (which happens to be a single value).

       In real life it can be a neural network we obtained, or matrices, or
       whatever we want to save."""
    output_file = os.path.join(output_directory, 'model.json')
    with open(output_file, 'w') as f:
        json.dump({'k': k}, f)


def main():
    input_directory, output_directory = get_configuration()

    print('We are in the quest of finding a mysterious value for k.',
          flush=True)
    time.sleep(5)
    print('The value happens to be 1/3, but don\'t tell anyone.',
          flush=True)
    time.sleep(2)
    k = 0.0

    values_for_x = get_values_for_x(input_directory)

    best_loss_so_far = 1000
    for i in range(0, num_iterations):
        print(f'k: {k:.4}', flush=True)
        x = values_for_x[i % len(values_for_x)]
        loss = pow(x - 3 * k * x, 2)
        if loss < best_loss_so_far:
            print('Best model so far! Saving')
            best_loss_so_far = loss
            write_model(output_directory, k)
        update = -6 * pow(x, 2) + 18 * k * pow(x, 2)
        # Weigh the learning rate by x
        k = k - 0.0001/x * update
        # Simulate that this took some time
        time.sleep(0.5)


if __name__ == '__main__':
    main()
