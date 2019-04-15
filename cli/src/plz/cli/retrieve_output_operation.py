import os
import shutil
import tarfile
import tempfile
from typing import Any, IO, Iterator, List, Optional, Tuple

from plz.cli.composition_operation import CompositionOperation, \
    create_path_string_prefix
from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException
from plz.cli.log import log_info
from plz.cli.operation import add_output_dir_arg, on_exception_reraise
from plz.controller.api.exceptions import InstanceStillRunningException


class RetrieveOutputOperation(CompositionOperation):
    """Download output for an execution"""

    @classmethod
    def name(cls):
        return 'output'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        cls.maybe_add_execution_id_arg(parser, args)
        add_output_dir_arg(parser)
        parser.add_argument(
            '--force-if-running',
            '-f',
            action='store_true',
            default=False,
            help='Download output even if the process is still running. '
            'Discouraged as the output might be in an inconsistent '
            'state. If the output directory is present it\'ll be '
            'overwritten')
        parser.add_argument(
            '--path',
            '-p',
            type=str,
            default=None,
            help='Download only the path specified')
        parser.add_argument(
            '--rewrite-subexecutions',
            action='store_true',
            default=False,
            help='When downloading output of subexecutions, ')

    def __init__(
            self,
            configuration: Configuration,
            output_dir: str,
            force_if_running: bool,
            path: Optional[str],
            rewrite_subexecutions: bool,
            execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.output_dir = output_dir
        self.force_if_running = force_if_running
        self.path = path
        self.rewrite_subexecutions = rewrite_subexecutions
        self.execution_id = execution_id

    def harvest(
            self,
            atomic_execution_id: Optional[str] = None,
            composition_path: Optional[List[Tuple[str,
                                                  Any]]] = None):
        if atomic_execution_id is None:
            atomic_execution_id = self.get_execution_id()
        if composition_path is None:
            composition_path = []
        try:
            self.controller.delete_execution(
                execution_id=atomic_execution_id,
                fail_if_running=True,
                fail_if_deleted=False)
        except InstanceStillRunningException:
            if self.force_if_running or len(composition_path) > 0:
                log_info('Process is still running')
                return
            else:
                raise CLIException(
                    'Process is still running, run `plz stop` if you want to '
                    'terminate it, \nor use --force-if-running (discouraged)')

    @on_exception_reraise('Retrieving the output failed.')
    def retrieve_output(
            self,
            atomic_execution_id: Optional[str] = None,
            composition_path: Optional[List[Tuple[str,
                                                  Any]]] = None):
        if atomic_execution_id is None:
            atomic_execution_id = self.get_execution_id()
        if composition_path is None:
            composition_path = []

        if len(composition_path) > 0:
            index = int(composition_path[-1][1])
        else:
            index = None
        output_tarball_bytes = self.controller.get_output_files(
            atomic_execution_id,
            path=self.path,
            index=index)
        formatted_output_dir = \
            self.output_dir.replace('%e', self.get_execution_id())
        formatted_output_dir = os.path.join(
            formatted_output_dir,
            *('-'.join(node) for node in composition_path),
            self.path if self.path is not None else '')
        try:
            os.makedirs(formatted_output_dir)
        except FileExistsError:
            if len(composition_path) > 0 and not self.rewrite_subexecutions:
                log_info('Output directory already present')
                return
            if self.force_if_running or len(composition_path) > 0:
                log_info('Removing existing output directory')
                shutil.rmtree(formatted_output_dir)
                os.makedirs(formatted_output_dir)
            else:
                raise CLIException(
                    f'The output directory "{formatted_output_dir}" '
                    'already exists.')
        for path in untar(output_tarball_bytes, formatted_output_dir):
            print(path)

    def run_atomic(
            self,
            atomic_execution_id: str,
            composition_path: [(str,
                                Any)]):
        string_prefix = create_path_string_prefix(composition_path)
        if len(string_prefix) > 0:
            message_suffix = f' for {string_prefix[:-1]}'
        else:
            message_suffix = ''
        log_info(f'Harvesting the output{message_suffix}...')
        self.harvest(atomic_execution_id, composition_path)
        log_info(f'Retrieving the output{message_suffix}...')
        self.retrieve_output(atomic_execution_id, composition_path)


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
                    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
                    with open(absolute_path, 'wb') as dest:
                        shutil.copyfileobj(source, dest)
