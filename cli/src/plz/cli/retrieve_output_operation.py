import os
import shutil
import tarfile
import tempfile
from typing import IO, Iterator, Optional

from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException
from plz.cli.log import log_info
from plz.cli.operation import Operation, add_output_dir_arg, \
    on_exception_reraise
from plz.controller.api.exceptions import InstanceStillRunningException


class RetrieveOutputOperation(Operation):
    """Download output for an execution"""

    @classmethod
    def name(cls):
        return 'output'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        cls.maybe_add_execution_id_arg(parser, args)
        add_output_dir_arg(parser)
        parser.add_argument(
            '--force-if-running', '-f', action='store_true', default=False,
            help='Download output even if the process is still running. '
                 'Discouraged as the output might be in an inconsistent '
                 'state. If the output directory is present it\'ll be '
                 'overwritten')

    def __init__(self, configuration: Configuration,
                 output_dir: str,
                 force_if_running: bool,
                 execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.output_dir = output_dir
        self.force_if_running = force_if_running
        self.execution_id = execution_id

    def harvest(self):
        try:
            self.controller.delete_execution(
                execution_id=self.get_execution_id(),
                fail_if_running=True,
                fail_if_deleted=False)
        except InstanceStillRunningException:
            if self.force_if_running:
                log_info('Process is still running')
                return
            else:
                raise CLIException(
                    'Process is still running, run `plz stop` if you want to '
                    'terminate it, \nor use --force-if-running (discouraged)')

    @on_exception_reraise('Retrieving the output failed.')
    def retrieve_output(self):
        execution_id = self.get_execution_id()
        output_tarball_bytes = self.controller.get_output_files(
            self.get_execution_id())
        formatted_output_dir = self.output_dir.replace('%e', execution_id)
        try:
            os.makedirs(formatted_output_dir)
        except FileExistsError:
            if self.force_if_running:
                log_info('Removing existing output directory')
                shutil.rmtree(formatted_output_dir)
                os.makedirs(formatted_output_dir)
            else:
                raise CLIException(
                    f'The output directory "{formatted_output_dir}" '
                    'already exists.')
        for path in untar(output_tarball_bytes, formatted_output_dir):
            print(path)

    def run(self):
        log_info('Harvesting the output...')
        self.harvest()
        log_info('Retrieving the output...')
        self.retrieve_output()


def untar(tarball_bytes: Iterator[bytes], formatted_output_dir: str) \
        -> Iterator[str]:
    # The first parameter is a tarball we need to extract into `output_dir`.
    with tempfile.TemporaryFile() as tarball:
        # `tarfile.open` needs to read from a real file, so we copy to one.
        for bs in tarball_bytes:
            tarball.write(bs)
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
                source: IO = tar.extractfile(tarinfo.name)
                if source:
                    # Finally, write the file.
                    absolute_path = os.path.join(formatted_output_dir, path)
                    os.makedirs(os.path.dirname(absolute_path),
                                exist_ok=True)
                    with open(absolute_path, 'wb') as dest:
                        shutil.copyfileobj(source, dest)
