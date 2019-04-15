import time
import traceback
from queue import Queue
from threading import Thread
from typing import Optional

import dateutil.parser

from plz.cli.composition_operation import get_all_atomic
from plz.cli.configuration import Configuration
from plz.cli.log import log_info
from plz.cli.operation import Operation, on_exception_reraise
from plz.controller.api import Controller


class LogsOperation(Operation):
    """Output logs for a given execution"""

    @classmethod
    def name(cls):
        return 'logs'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        cls.maybe_add_execution_id_arg(parser, args)
        parser.add_argument(
            '-s',
            '--since',
            help='Specify a start time for the log output. Unfilled fields are'
            'assumed to be same as of current time: `10:30` is today\'s '
            '10:30. Use `start` to print all logs')

    def __init__(
            self,
            configuration: Configuration,
            since: Optional[str],
            execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.execution_id = execution_id
        self.since = since

    @on_exception_reraise("Displaying the logs failed.")
    def display_logs(self, execution_id: str, print_interrupt_message=False):
        log_info('Streaming logs...')
        since_timestamp = self._compute_since_timestamp()

        composition = self.controller.get_execution_composition(execution_id)
        atomic_executions = get_all_atomic(composition)

        try:
            if len(atomic_executions) == 1:
                byte_lines = self.controller.get_logs(
                    self.get_execution_id(),
                    since=since_timestamp)
                for byte_line in byte_lines:
                    print(byte_line.decode('utf-8'), end='', flush=True)
            else:
                self._print_logs_for_composite(
                    atomic_executions,
                    since_timestamp)
        except KeyboardInterrupt:
            print()
            if print_interrupt_message:
                log_info(
                    'Your program is still running. '
                    'To stream the logs, type:\n\n'
                    f'        plz logs {self.get_execution_id()}\n')
            raise
        print()

    def _print_logs_for_composite(
            self, atomic_executions: [str], since_timestamp: Optional[str]) \
            -> None:
        lines_queue = Queue()
        for e in atomic_executions:
            t = Thread(
                target=_queue_log_lines,
                args=(
                    self.controller,
                    lines_queue,
                    e,
                    since_timestamp,
                    self.configuration.debug))
            t.start()
        end_signals = 0
        while end_signals < len(atomic_executions):
            lines = lines_queue.get()
            if lines is None:
                end_signals += 1
            else:
                print(lines, end='', flush=True)

    def _compute_since_timestamp(self) -> Optional[str]:
        # For the since argument, pass an integer to the backend. Or nothing
        # in case we want to log from the start (so the default is different
        # in the cli --current time-- and the backend --start time--). That's
        # the easiest way to code it, as passing a datetime time object to the
        # backend would require to pass the timezone and doing timezone
        # calculations in the backend. This way all calculations
        # timezone-dependent calculations are done in in the cli and the
        # backend uses whatever timestamp we pass.
        if self.since is None:
            # Default: show since the current time
            since_timestamp = str(int(time.time()))
        elif self.since == 'start':
            # Log from the beginning, that's the default for the backend
            since_timestamp = None
        else:
            try:
                since_timestamp = str(int(self.since))
            except ValueError:
                since_timestamp = str(
                    int(
                        time.mktime(
                            dateutil.parser.parse(self.since).timetuple())))
        return since_timestamp

    def run(self):
        try:
            self.display_logs(self.get_execution_id())
        except KeyboardInterrupt:
            pass


def _queue_log_lines(
        controller: Controller,
        lines_queue: Queue,
        execution_id: str,
        since_timestamp: Optional[str],
        debug: bool) -> None:
    # noinspection PyBroadException
    try:
        byte_lines = controller.get_logs(execution_id, since_timestamp)
        incomplete_line = ''
        for byte_line in byte_lines:
            str_line = byte_line.decode('utf-8')
            if '\n' in str_line:
                lines, new_incomplete_line = \
                    str_line.rsplit('\n', 1)
                lines_queue.put(incomplete_line + lines + '\n')
                incomplete_line = new_incomplete_line
            else:
                incomplete_line += str_line
        lines_queue.put(incomplete_line)
    except KeyboardInterrupt:
        pass
    except Exception:
        # Do not mind exceptions in the thread.
        if debug:
            traceback.print_exc()
    finally:
        lines_queue.put(None)
