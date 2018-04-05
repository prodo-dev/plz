import json

import requests
from datetime import datetime
from prettytable import PrettyTable

from plz.cli.operation import Operation, check_status


class ListCommandsOperation(Operation):
    @staticmethod
    def prepare_argument_parser(parser, args):
        pass

    def run(self):
        response = requests.get(self.url('commands', 'list'))
        check_status(response, requests.codes.ok)
        table = PrettyTable(['Execution Id', 'Running', 'Status',
                             'Type', 'Idle since', 'Disposal time'])
        for command in json.loads(response.content)['commands']:
            execution_id = command['execution_id']
            running = command['running']
            status = command['status']
            instance_type = command['instance_type']
            if status == 'idle':
                idle_since_timestamp = command['idle_since_timestamp']
                idle_since = _timestamp_to_string(idle_since_timestamp)
                disposal_time = _timestamp_to_string(
                    idle_since_timestamp + command['max_idle_seconds'])
            else:
                idle_since = ''
                disposal_time = ''
            table.add_row([execution_id, running, status, instance_type,
                           idle_since, disposal_time])
        print(table)


def _timestamp_to_string(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
