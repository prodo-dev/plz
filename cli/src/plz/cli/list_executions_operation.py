import json
from datetime import datetime

import requests
from prettytable import PrettyTable

from plz.cli.operation import Operation, check_status


class ListExecutionsOperation(Operation):
    @staticmethod
    def prepare_argument_parser(parser, args):
        pass

    def run(self):
        response = self.server.get('executions', 'list')
        check_status(response, requests.codes.ok)
        table = PrettyTable(['Execution Id', 'Running', 'Status',
                             'Type', 'Idle since', 'Disposal time'])
        for execution in json.loads(response.content)['executions']:
            execution_id = execution['execution_id']
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
            table.add_row([execution_id, running, status, instance_type,
                           idle_since, disposal_time])
        print(table)


def _timestamp_to_string(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
