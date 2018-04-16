import io
import os
import shutil
import tarfile
import tempfile
from typing import Iterator, Optional

import requests

from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException
from plz.cli.log import log_info
from plz.cli.operation import Operation, check_status, on_exception_reraise
from plz.cli.show_status_operation import ShowStatusOperation


class RetrieveOutputOperation(Operation):
    @staticmethod
    def prepare_argument_parser(parser, args):
        if len(args) > 1:
            # Execution ID was specified
            parser.add_argument(dest='execution_id')
        cwd = os.getcwd()
        parser.add_argument('-o', '--output-dir',
                            type=str,
                            default=os.path.join(cwd, 'output'))

    def __init__(self, configuration: Configuration,
                 output_dir: str,
                 execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.output_dir = output_dir
        self.execution_id = execution_id

    def harvest(self):
        log_info('Harvesting the output...')
        response = requests.delete(
            self.url('executions', self.get_execution_id()))
        check_status(response, requests.codes.no_content)

    @on_exception_reraise('Retrieving the output failed.')
    def retrieve_output(self):
        execution_id = self.get_execution_id()
        log_info('Retrieving the output...')
        response = requests.get(
            self.url('executions', execution_id, 'output', 'files'),
            stream=True)
        check_status(response, requests.codes.ok)
        try:
            os.makedirs(self.output_dir)
        except FileExistsError:
            raise CLIException(
                f'The output directory "{self.output_dir}" already exists.')
        for path in untar(response.raw, self.output_dir):
            print(path)

    def run(self):
        show_status_operation = ShowStatusOperation(
            self.configuration, self.get_execution_id())
        if show_status_operation.get_status().running:
            raise CLIException(
                'Process is still running. Use `plz stop` if '
                'you want to terminate it')
        self.harvest()
        self.retrieve_output()


def untar(stream: io.RawIOBase, output_dir: str) -> Iterator[str]:
    # The response is a tarball we need to extract into `output_dir`.
    with tempfile.TemporaryFile() as tarball:
        # `tarfile.open` needs to read from a real file, so we copy to one.
        shutil.copyfileobj(stream, tarball)
        # And rewind to the start.
        tarball.seek(0)
        tar = tarfile.open(fileobj=tarball)
        for tarinfo in tar.getmembers():
            # Drop the first segment, because it's just the name of the
            # directory that was tarred up, and we don't care.
            path_segments = tarinfo.name.split(os.sep)[1:]
            if path_segments:
                # Unfortunately we can't just pass `*path_segments`
                # because `os.path.join` explicitly expects an argument
                # for the first parameter.
                path = os.path.join(path_segments[0], *path_segments[1:])
                # Just because it's nice, yield the file to be extracted.
                yield path
                source: io.BufferedReader = tar.extractfile(tarinfo.name)
                if source:
                    # Finally, write the file.
                    absolute_path = os.path.join(output_dir, path)
                    os.makedirs(os.path.dirname(absolute_path),
                                exist_ok=True)
                    with open(absolute_path, 'wb') as dest:
                        shutil.copyfileobj(source, dest)
