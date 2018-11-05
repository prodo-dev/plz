import json
import os

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
        print('Running with plz!', flush=True)
        with open(configuration_file) as c:
            config = json.load(c)
        return config[key]
    else:
        return non_plz_value


# Parameters when not running via plz (here we just hardcode them, one could
# read them from the command line instead, or whatever other way)
NON_PLZ_PARAMETERS = {
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
    cl_args_parser.add_argument('--verbose', action='store_true',
                                help='Print progress messages')
    cl_args = cl_args_parser.parse_args()
    return cl_args.verbose


def write_measures(
        measures_directory: str, epoch: int, training_loss: float,
        accuracy: float):
    measures_directory


def main():
    is_verbose = is_verbose_from_cl_args()

    is_cuda_available = torch.cuda.is_available()

    input_directory = get_from_plz_config('input_directory', '../data')
    output_directory = get_from_plz_config('output_directory', 'models')
    parameters = get_from_plz_config('parameters', NON_PLZ_PARAMETERS)

    device = torch.device('cuda' if is_cuda_available else 'cpu')

    if is_verbose:
        print(f'Using device: {device}')

    training_loader = create_loader(
        input_directory, parameters['batch_size'],
        pin_memory=is_cuda_available,
        is_training=True)
    eval_loader = create_loader(
        input_directory, parameters['eval_batch_size'],
        pin_memory=is_cuda_available,
        is_training=False)

    model = LeNet(
        device,
        learning_rate=parameters['learning_rate'],
        momentum=parameters['momentum']).to(device)

    max_accuracy = 0
    for epoch in range(1, parameters['epochs'] + 1):
        loss = model.epoch(training_loader)

        accuracy = model.evaluation(eval_loader)
        if is_verbose:
            print(f'Epoch: {epoch} Traning loss: {loss:.6f}')
            print(
                f'Evaluation accuracy: {accuracy:.2f} '
                f'(max {max_accuracy:.2f})')
        if accuracy > max_accuracy:
            max_accuracy = accuracy
            print(f'Best model found at epoch {epoch}, '
                  f'with accurary {accuracy:.2f}')
            torch.save(model.state_dict(),
                       os.path.join(output_directory, 'le_net.pth'))


if __name__ == '__main__':
    main()
