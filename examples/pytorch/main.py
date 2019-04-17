import json
import os
import time

import argparse
import torch
from typing import TypeVar

from data_loading import create_loader
from le_net import LeNet

T = TypeVar


def get_from_plz_config(key: str, non_plz_value: T) -> T:
    """
    Get the value of a key from the configuration provided by plz

    Or a given value, if not running with plz

    :param key: the key to get, for instance `input_directory`
    :param non_plz_value: value to use when not running with plz
    :return: the value for the key
    """
    configuration_file = os.environ.get('CONFIGURATION_FILE', None)
    if configuration_file is not None:
        with open(configuration_file) as c:
            config = json.load(c)
        return config[key]
    else:
        return non_plz_value


# Default parameters. We use those parameters also when not running via plz
# (one could read them from the command line instead, etc.)
DEFAULT_PARAMETERS = {
    'epochs': 30,
    'batch_size': 32,
    'eval_batch_size': 32,
    'learning_rate': 0.01,
    'momentum': 0.5
}


def is_verbose_from_cl_args() -> bool:
    """
    Read verbosity from command-line arguments

    Just to illustrate that you can read command line arguments as well

    :return: `True` iff verbose
    """
    cl_args_parser = argparse.ArgumentParser(
        description='Plz PyTorch Example: digit recognition using MNIST')
    cl_args_parser.add_argument('--verbose',
                                action='store_true',
                                help='Print progress messages')
    cl_args = cl_args_parser.parse_args()
    return cl_args.verbose


def write_measures(measures_directory: str,
                   epoch: int,
                   training_loss: float,
                   accuracy: float):
    with open(os.path.join(measures_directory, f'epoch_{epoch:2d}'), 'w') as f:
        json.dump({'training_loss': training_loss, 'accuracy': accuracy}, f)


def main():
    is_verbose = is_verbose_from_cl_args()

    is_cuda_available = torch.cuda.is_available()

    input_directory = get_from_plz_config('input_directory',
                                          os.path.join('..', 'data'))
    output_directory = get_from_plz_config('output_directory', 'models')
    parameters = get_from_plz_config('parameters', DEFAULT_PARAMETERS)
    # If some parameters weren't passed, use default values for them
    for p in DEFAULT_PARAMETERS:
        if p not in parameters:
            parameters[p] = DEFAULT_PARAMETERS[p]
    measures_directory = get_from_plz_config('measures_directory', 'measures')
    summary_measures_path = get_from_plz_config(
        'summary_measures_path', os.path.join('measures', 'summary'))

    device = torch.device('cuda' if is_cuda_available else 'cpu')

    if is_verbose:
        print(f'Using device: {device}')

    training_loader = create_loader(input_directory,
                                    parameters['batch_size'],
                                    pin_memory=is_cuda_available,
                                    is_training=True)
    eval_loader = create_loader(input_directory,
                                parameters['eval_batch_size'],
                                pin_memory=is_cuda_available,
                                is_training=False)

    model = LeNet(device,
                  learning_rate=parameters['learning_rate'],
                  momentum=parameters['momentum']).to(device)

    training_time_start = time.time()

    max_accuracy = 0
    training_loss_at_max = 0
    epoch_at_max = 0
    for epoch in range(1, parameters['epochs'] + 1):
        loss = model.epoch(training_loader)

        accuracy = model.evaluation(eval_loader)
        if is_verbose:
            print(f'Epoch: {epoch}. Training loss: {loss:.6f}')
            print(f'Evaluation accuracy: {accuracy:.2f} '
                  f'(max {max_accuracy:.2f})')

        write_measures(measures_directory,
                       epoch=epoch,
                       training_loss=loss,
                       accuracy=accuracy)

        if accuracy > max_accuracy:
            max_accuracy = accuracy
            training_loss_at_max = loss
            epoch_at_max = epoch
            print(f'Best model found at epoch {epoch}, '
                  f'with accuracy {accuracy:.2f}')
            torch.save(model.state_dict(),
                       os.path.join(output_directory, 'le_net.pth'))

    with open(summary_measures_path, 'w') as f:
        json.dump(
            {
                'max_accuracy': max_accuracy,
                'training_loss_at_max': training_loss_at_max,
                'epoch_at_max': epoch_at_max,
                'training_time': time.time() - training_time_start
            },
            f)


if __name__ == '__main__':
    main()
