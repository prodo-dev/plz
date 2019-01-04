from datetime import datetime

from prettytable import PrettyTable

from plz.cli.configuration import Configuration
from plz.cli.operation import Operation


class ListExecutionsOperation(Operation):
    """List all current executions"""

    @classmethod
    def name(cls):
        return 'list'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        parser.add_argument(
            '-a', '--all-users', action='store_const', const=True,
            default=False, help='List executions for all users')

    def __init__(self, configuration: Configuration, all_users: bool):
        self.all_users = all_users
        super().__init__(configuration)

    def run(self):
        table = PrettyTable(['Execution Id', 'Instance Id', 'Running',
                             'Status', 'Type', 'Idle since', 'Disposal time'])
        executions = self.controller.list_executions(
            self.configuration.user, self.all_users)
        for execution in executions:
            execution_id = execution['execution_id']
            instance_id = execution['instance_id']
            running = execution['running']
            status = execution['status']
            instance_type = execution['instance_type']
            if status == 'idle':
                idle_since_timestamp = execution['idle_since_timestamp']
                idle_since = _timestamp_to_string(idle_since_timestamp)
                disposal_time = _timestamp_to_string(
                    idle_since_timestamp + execution['max_idle_seconds'])
            else:
                idle_since = ''
                disposal_time = ''
            table.add_row([execution_id, instance_id, running, status,
                           instance_type, idle_since, disposal_time])
        print(table)


def _timestamp_to_string(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
