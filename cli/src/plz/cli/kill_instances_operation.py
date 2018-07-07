from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException
from plz.cli.log import log_error, log_info, log_warning
from plz.cli.operation import Operation
from plz.controller.api.exceptions import ProviderKillingInstancesException


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
            instance_ids_for_controller = None
        else:
            if self.instance_ids is None or len(self.instance_ids) == 0:
                raise CLIException(
                    'You must specify a list of instance IDs with the -i '
                    'option. Use `plz list` to get instance IDs')
            log_info('Killing instances: ' + ' '.join(self.instance_ids))
            instance_ids_for_controller = self.instance_ids
        if not self.all_of_them_plz and not self.instance_ids:
            raise CLIException('No instance IDs specified')

        try:
            were_there_instances_to_kill = self.controller.kill_instances(
                instance_ids=instance_ids_for_controller,
                force_if_not_idle=self.force_if_not_idle)
        except ProviderKillingInstancesException as e:
            fails = e.failed_instance_ids_to_messages
            log_error(
                'Error terminating instances: \n' + ''.join(
                    [f'{instance_id}: {message}\n'
                     for instance_id, message in fails.items()]))
            raise CLIException(
                'Couldn\'t terminate all instances. You can use '
                '--force-if-not-idle for non-idle instances')

        if not were_there_instances_to_kill:
            log_warning(
                'Request to kill all instances, yet no instances were found.')

        log_info('It was a clean job')
