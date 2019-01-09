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
            help='Kills all instances that are running jobs for this user. '
                 'Implies --force-if-not-idle')
        parser.add_argument('-i', '--instance-ids', nargs='+', type=str,
                            help='IDs of the instances to kill')
        parser.add_argument('--force-if-not-idle', action='store_true',
                            default=False,
                            help='Kills instances even if they\'re not idle')
        parser.add_argument('--including-idle', action='store_true',
                            default=False,
                            help='When killing all user instances, kill idle '
                                 'ones as well')
        parser.add_argument('--berserk', action='store_true',
                            default=False,
                            help='Ignore user ownership when killing '
                                 'instances. Easy with this one, mate.')
        parser.add_argument('--oh-yeah', action='store_true',
                            default=False,
                            help='Do not ask user for confirmation when '
                                 'killing all instances')

    def __init__(self, configuration: Configuration, all_of_them_plz: bool,
                 force_if_not_idle: bool, instance_ids: [str], oh_yeah: bool,
                 including_idle: bool, berserk: bool):
        super().__init__(configuration)
        self.all_of_them_plz = all_of_them_plz
        self.ignore_ownership = berserk
        self.including_idle = including_idle
        self.instance_ids = instance_ids
        # If the user has set all_of_them_plz, set force_if_not_idle, as
        # (unless including_idle is set) instances will be
        # non-idle
        self.force_if_not_idle = force_if_not_idle or all_of_them_plz
        self.oh_yeah = oh_yeah

    def run(self):
        user = self.configuration.user
        if self.all_of_them_plz:
            if self.instance_ids is not None:
                raise CLIException('Can\'t specify both a list of instances '
                                   'and --all-of-them-plz')
            user_in_message = 'all users' if self.ignore_ownership else user
            log_warning(
                f'Killing all instances running jobs of {user_in_message} '
                'for all projects')
            if not self.oh_yeah:
                answer = input('Are you sure? (yeah/Nope): ')
                if answer != 'yeah':
                    raise CLIException('Cancelled by user')
        else:
            if self.instance_ids is None or len(self.instance_ids) == 0:
                raise CLIException(
                    'You must specify a list of instance IDs with the -i '
                    'option. Use `plz list` to get instance IDs')
            if self.including_idle:
                raise CLIException(
                    'Option --including-idle only makes sense together with '
                    '--all-of-them-plz')
            # The way the API likes it in this case
            self.including_idle = None
            log_info('Killing instances: ' + ' '.join(self.instance_ids))
        if not self.all_of_them_plz and not self.instance_ids:
            raise CLIException('No instance IDs specified')

        try:
            were_there_instances_to_kill = self.controller.kill_instances(
                instance_ids=self.instance_ids,
                force_if_not_idle=self.force_if_not_idle,
                ignore_ownership=self.ignore_ownership,
                including_idle=self.including_idle,
                user=user)
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
            if not self.including_idle:
                log_warning('Maybe you forgot --including-idle ?')

        log_info('It was a clean job')
