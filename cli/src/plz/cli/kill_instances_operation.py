import requests

from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException
from plz.cli.log import log_error, log_info, log_warning
from plz.cli.operation import Operation


class KillInstancesOperation(Operation):
    """Kill instances by instance ID"""

    @classmethod
    def name(cls):
        return 'kill'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        parser.add_argument(
            '--all-of-them-plz', action='store_true', default=False,
            help='Kills all instances for all users and projects. Y\'know... '
            'Be careful...')
        parser.add_argument('-i', '--instance-ids', nargs='+', type=str,
                            help='IDs of the instances to kill')
        parser.add_argument('--force-if-not-idle', action='store_true',
                            default=False,
                            help='Kills all instances for all users and '
                                 'projects. Y\'know... Be careful...')
        parser.add_argument('--oh-yeah', action='store_true',
                            default=False,
                            help='Do not ask use')

    def __init__(self, configuration: Configuration, all_of_them_plz: bool,
                 force_if_not_idle: bool, instance_ids: [str], oh_yeah: bool):
        super().__init__(configuration)
        self.all_of_them_plz = all_of_them_plz
        self.instance_ids = instance_ids
        self.force_if_not_idle = force_if_not_idle
        self.oh_yeah = oh_yeah

    def run(self):
        if self.all_of_them_plz:
            log_warning('Killing all instances for all users and projects')
            if not self.oh_yeah:
                answer = input('Are you sure? (yeah/Nope): ')
                if answer != 'yeah':
                    raise CLIException('Cancelled by user')
        else:
            log_info('Killing instances: ' + ' '.join(self.instance_ids))
        if not self.all_of_them_plz and not self.instance_ids:
            raise CLIException('No instance IDs specified')

        response = self.server.post('instances', 'kill', json={
            'all_of_them_plz': self.all_of_them_plz,
            'instance_ids': self.instance_ids,
            'force_if_not_idle': self.force_if_not_idle
        })

        response_json = response.json()
        if 'warning_message' in response_json:
            log_warning(response_json['warning_message'])

        if response.status_code != requests.codes.ok:
            if 'failed_instance_ids_to_messages' in response_json:
                fails = response_json['failed_instance_ids_to_messages']
                log_error(
                    'Error terminating instances: \n' + ''.join(
                        [f'{instance_id}: {message}\n'
                         for instance_id, message in fails.items()]))
            raise CLIException(
                'Couldn\'t terminate all instances. You can use '
                '--force-if-not-idle for non-idle instances')

        log_info('It was a clean job')
