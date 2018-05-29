from plz.cli.configuration import Configuration
from plz.cli.operation import Operation
from plz.cli.snapshot import get_context_files, get_matching_excluded_paths


class ListContextOperation(Operation):
    @classmethod
    def name(cls):
        return 'list-context'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        parser.add_argument(
            '-e', '--excluded-paths', action='store_const', const=True,
            default=False)

    def __init__(self, configuration: Configuration, excluded_paths: bool):
        self.excluded_paths = excluded_paths
        super().__init__(configuration)

    def run(self):
        exclude_gitignored_files = \
            self.configuration.exclude_gitignored_files
        snapshot_path = '.'
        matching_excluded_paths = get_matching_excluded_paths(
            snapshot_path=snapshot_path,
            excluded_paths=self.configuration.excluded_paths,
            included_paths=self.configuration.included_paths,
            exclude_gitignored_files=exclude_gitignored_files)
        if self.excluded_paths:
            for p in sorted(list(set(matching_excluded_paths))):
                print(p)
            return
        for f in sorted(get_context_files(
                snapshot_path, matching_excluded_paths)):
            print(f)
