import json
import os
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from plz.cli.exceptions import CLIException
from plz.cli.log import format_warning

T = TypeVar('T')


class ValidationError:
    def __init__(self, message):
        self.message = message

    def __eq__(self, other):
        return self.message == other.message

    def __str__(self):
        return self.message

    def __repr__(self):
        return f'ValidationError({repr(self.message)})'


class ValidationException(Exception):
    def __init__(self, errors: List[ValidationError]):
        self.errors = errors

    def print(self):
        for error in self.errors:
            print(str(error))


class Property:
    TYPE_DESCRIPTIONS = {
        str: 'a string',
        int: 'an integer',
        bool: 'true or false',
        list: 'a list',
        float: 'a float number'
    }

    SUBTYPES = defaultdict(lambda: [])
    SUBTYPES[float] = [int]
    SUBTYPES[Optional[int]] = [int, None]

    # noinspection PyShadowingBuiltins
    def __init__(
            self,
            name: str,
            type: Type[T] = str,
            required: bool = False,
            default: T = None,
            validations: [
                Callable[
                    ['Configuration', List[ValidationError]], None]] = None):
        self.name = name
        self.type = type
        self.required = required
        self.default = default
        self.validations = validations or []

    def required_error(self) -> ValidationError:
        return ValidationError(f'The property "{self.name}" is required.')

    def type_error(self, value) -> ValidationError:
        return ValidationError(
            f'The property "{self.name}" '
            f'must be {self.TYPE_DESCRIPTIONS[self.type]}.\n'
            f'Invalid value: {repr(value)}')


def _validate_market_spec(configuration, errors, operation: Optional[str]):
    if operation not in {'run', 'rerun'}:
        return
    if configuration.instance_market_type not in {'spot', 'on_demand'}:
        errors.append(['Possible values for `instance_market_type` are '
                       '`spot` or `on_demand`'])
    if configuration.instance_market_type == 'spot' \
            and configuration.max_bid_price_in_dollars_per_hour is None:
        errors.append(
            'In order to use spot instances, in your plz.config.json file '
            'please set `\n'
            '"max_bid_price_in_dollars_per_hour": N\n'
            '` for some N (or set `"instance_market_type": "on_demand"`, '
            'which will be more expensive than any bid price you use)')
    if configuration.instance_market_type == 'on_demand' and \
            configuration.max_bid_price_in_dollars_per_hour is not None:
        # The logger is not ready yet as it depends on the configuration,
        # using the same method the logger uses
        print(
            format_warning(
                'You\'re not asking for a spot instance '
                '(`instance_market_type` is set to '
                f'{configuration.instance_market_type}), yet you\'re '
                'specifying a bid price (`max_bid_price_in_dollars_per_hour`).'
                ' Ignoring the bid price',
                use_emojis=False))


def _warn_about_instance_max_uptime(
        configuration, _, operation: Optional[str]):
    if operation not in {'run', 'rerun'}:
        return
    if configuration.instance_max_uptime_in_minutes:
        print(
            format_warning(
                f'Your instance is going to shutdown after '
                f'{configuration.instance_max_uptime_in_minutes} minutes '
                'since started. You can set: `\n'
                '"instance_max_uptime_in_minutes": null,\n'
                '` in your plz.config.json if you don\'t want this limit',
                use_emojis=False))


class Configuration:
    PROPERTIES = {
        prop.name: prop for prop in [
            Property('host', default='localhost'),
            Property('port', type=int, default=80),
            Property('quiet_build', type=bool, default=False),
            Property('user', required=True),
            Property('instance_type', default='t2.micro'),
            Property('project', required=True),
            Property('image', type=str),
            Property('image_extensions', type=list, default=[]),
            Property('command', type=list),
            Property('input', type=str),
            # Paths to exclude when creating a snapshot. List of python globs
            Property('excluded_paths', type=list, default=[]),
            # Whether to consider the files ignored by git as excluded,
            # (save for when they are included explicitly).
            # Value of None means "use git if available"
            Property('exclude_gitignored_files',
                     type=bool, default=None),
            # Paths to include, as to override exclusion (must be paths under
            # the current work directory)
            Property('included_paths', type=list, default=[]),
            Property('debug', type=bool, default=False),
            Property('docker_run_args', type=dict, default={}),
            Property('connection_info', type=dict, default={}),
            Property('context_path', type=str, default='.'),
            # Default is info, unless debug is enabled, in which case default
            # is debug
            Property('log_level', type=str, default=None),
            Property('use_emojis', type=bool, default=True),
            Property('workarounds', type=dict,
                     default={'docker_build_retries': 3}),
            Property('instance_market_type', type=str, default='on_demand',
                     validations=[_validate_market_spec]),
            Property('instance_max_uptime_in_minutes',
                     type=Optional[int],
                     default=60,
                     validations=[_warn_about_instance_max_uptime]),
            Property('instance_max_idle_time_in_minutes', type=int,
                     default=0),
            Property('max_bid_price_in_dollars_per_hour', type=float,
                     default=None),
        ]
    }

    DEFAULT_CONFIGURATION_FILE_NAME = 'plz.config.json'
    MISSING_CONFIGURATION_FILE_ERROR = ValidationError(
        f'You must create a {DEFAULT_CONFIGURATION_FILE_NAME} file, '
        f'or specify a path to it with -c')

    @staticmethod
    def load(configuration_path: Optional[str] = None,
             operation: Optional[str] = None) -> 'Configuration':
        config_file_name = Configuration._configuration_file_from_path(
            configuration_path)

        file_configurations = [
            Configuration._get_user_level_config(),
            *Configuration._get_parent_dirs_configs(config_file_name),
            Configuration._get_top_level_config(
                config_file_name,
                config_set_explicitly=configuration_path is not None)]

        file_configurations = [c for c in file_configurations if c is not None]
        if file_configurations is []:
            raise ValidationException(
                [Configuration.MISSING_CONFIGURATION_FILE_ERROR])

        configurations = [*file_configurations,
                          Configuration.from_env(Configuration.PROPERTIES)]
        configuration = Configuration.defaults(Configuration.PROPERTIES)
        for c in configurations:
            configuration = configuration.override_with(c)
        return configuration.validate(operation)

    @staticmethod
    def defaults(properties: Dict[str, Property]) -> 'Configuration':
        data = {prop.name: prop.default for prop in properties.values()}
        return Configuration(properties, data)

    @staticmethod
    def from_file(filepath: str, properties: Dict[str, Property],
                  fail_on_read_error: bool) -> Optional['Configuration']:
        try:
            if not os.path.exists(filepath):
                return None
            with open(filepath, 'r') as f:
                file_content = f.read()
        except Exception as e:
            if fail_on_read_error:
                raise e
            return None

        return Configuration(properties, json.loads(file_content))

    @staticmethod
    def from_env(properties: Dict[str, Property]) -> 'Configuration':
        data = {}
        for key, value in os.environ.items():
            if key.startswith('PLZ_'):
                name = key[len('PLZ_'):].lower()
                prop = properties.get(name)
                if prop:
                    for t in [prop.type, *Property.SUBTYPES[prop.type]]:
                        data[name] = Configuration._typed_value_from_string(
                            value, t)
                        if data[name] is not None:
                            break
                    if data[name] is None:
                        data[name] = value
        return Configuration(properties, data)

    @staticmethod
    def _typed_value_from_string(string_value, typ):
        try:
            return typ(string_value)
        except (ValueError, TypeError):
            return None

    def __init__(self, properties: Dict[str, Property], data: Dict[str, Any]):
        self.properties = properties
        self.data = data

    def override_with(self, other: 'Configuration') -> 'Configuration':
        return Configuration(self.properties, {**self.data, **other.data})

    def validate(self, operation: Optional[str] = None) -> 'Configuration':
        errors = []
        for prop in self.properties.values():
            value = self.data.get(prop.name)
            if value is None and prop.required:
                errors.append(prop.required_error())
            elif value is not None and \
                    not type(value) in Property.SUBTYPES[prop.type] and \
                    not isinstance(value, prop.type):
                errors.append(Property.type_error(prop, value))
        for prop in self.properties.values():
            for validation in prop.validations:
                validation(self, errors, operation)
        if errors:
            raise ValidationException(errors)
        return self

    @staticmethod
    def _get_top_level_config(config_file_name, config_set_explicitly: bool):
        config = Configuration.from_file(
            config_file_name, Configuration.PROPERTIES,
            fail_on_read_error=True)
        # The user provided a configuration file explicitly, but we couldn't
        # read a configuration from it
        if config_set_explicitly and config is None:
            raise CLIException(
                f'Couldn\'t read a configuration from {config_file_name}')
        return config

    @staticmethod
    def _get_parent_dirs_configs(config_file_name: str) -> ['Configuration']:
        """Return configurations in parent directories.

           Starting from the mount point onwards.
        """
        configurations = []
        # Load all plz.config.json in parent directories since the mount point
        path_fragments = config_file_name.split(os.path.sep)[:-1]
        mount_index = Configuration._get_mount_index(path_fragments)

        # Iterating until `len(path_fragments)` we don't consider the top-level
        # directory, this is strictly for parents
        for n in range(mount_index, len(path_fragments)):
            configuration = Configuration.from_file(
                os.path.join(
                    '/', *path_fragments[:n],
                    Configuration.DEFAULT_CONFIGURATION_FILE_NAME),
                Configuration.PROPERTIES,
                # If we can read a configuration at some point, we don't
                # expect to have any permissions problems/filesystem problems
                # upwards
                fail_on_read_error=len(configurations) > 0)
            if configuration is not None:
                configurations.append(configuration)
        return configurations

    @staticmethod
    def _get_user_level_config() -> 'Configuration':
        user_level_config_file = os.path.expanduser(
            os.path.join('~', '.config', 'plz',
                         Configuration.DEFAULT_CONFIGURATION_FILE_NAME))

        return Configuration.from_file(
            user_level_config_file, Configuration.PROPERTIES,
            # We expect to be able to read a file the home directory
            fail_on_read_error=True)

    @staticmethod
    def _get_mount_index(path_fragments):
        """Return largest n such that `os.path.join('/', *path_fragments[:n])`
           is a mount point"""
        mount_index = len(path_fragments) - 1
        # Stopping at 0. The empty path is the first entry, if we consider
        # path_fragments[:0] it'd be duplicated
        for n in range(len(path_fragments), 0, -1):
            mount_index = n
            if os.path.ismount(os.path.join('/', *path_fragments[:n])):
                break
        return mount_index

    @staticmethod
    def _configuration_file_from_path(configuration_path: str) -> str:
        if configuration_path is None:
            config_file_name = os.path.abspath(
                Configuration.DEFAULT_CONFIGURATION_FILE_NAME)
        elif os.path.isdir(configuration_path):
            config_file_name = os.path.abspath(os.path.join(
                configuration_path,
                Configuration.DEFAULT_CONFIGURATION_FILE_NAME))
        else:
            config_file_name = os.path.abspath(
                os.path.join(configuration_path))
        return config_file_name

    def __getattr__(self, name):
        if name in self.properties:
            return self.data.get(name, self.properties[name].default)
        else:
            raise KeyError(name)

    def as_dict(self):
        return {name: getattr(self, name) for name in self.properties}
