import json
import os
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar

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
    }

    # noinspection PyShadowingBuiltins
    def __init__(self,
                 name: str,
                 type: Type[T] = str,
                 required: bool = False,
                 default: T = None):
        self.name = name
        self.type = type
        self.required = required
        self.default = default

    def required_error(self) -> ValidationError:
        return ValidationError(f'The property "{self.name}" is required.')

    def type_error(self, value) -> ValidationError:
        return ValidationError(
            f'The property "{self.name}" '
            f'must be {self.TYPE_DESCRIPTIONS[self.type]}.\n'
            f'Invalid value: {repr(value)}')


class Configuration:
    PROPERTIES = {
        prop.name: prop for prop in [
            Property('host', default='localhost'),
            Property('port', type=int, default=80),
            Property('quiet_build', type=bool, default=False),
            Property('user', required=True),
            Property('instance_type', default='t2.micro'),
            Property('project', required=True),
            Property('image', type=str, required=True),
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
            Property('workarounds', type=dict,
                     default={'docker_build_retrials': 3}),
        ]
    }

    DEFAULT_CONFIGURATION_FILE_NAME = 'plz.config.json'
    MISSING_CONFIGURATION_FILE_ERROR = ValidationError(
        f'You must create a {DEFAULT_CONFIGURATION_FILE_NAME} file, '
        f'or specify a path to it with -c')

    @staticmethod
    def load(configuration_path: Optional[str] = None) -> 'Configuration':
        config_file_name = Configuration._configuration_file_from_path(
            configuration_path)

        configuration = Configuration.defaults(Configuration.PROPERTIES)
        configuration, user_level_config_was_read = \
            Configuration._override_with_user_level_config(configuration)

        configuration, file_config_was_read = \
            Configuration._override_with_file_configs(
                config_file_name, configuration,
                plz_config_set_explicitly=configuration_path is not None)

        if not (user_level_config_was_read or file_config_was_read):
            raise ValidationException(
                [Configuration.MISSING_CONFIGURATION_FILE_ERROR])

        env_configuration = Configuration.from_env(Configuration.PROPERTIES)

        return configuration.override_with(env_configuration).validate()

    @staticmethod
    def _override_with_file_configs(
            config_file_name: str, configuration: 'Configuration',
            plz_config_set_explicitly: bool) -> Tuple['Configuration', bool]:
        config_was_read = False
        # Load all plz.config.json in parent directories since the mount point
        path_fragments = config_file_name.split(os.path.sep)[:-1]
        mount_index = len(path_fragments) - 1
        # Stopping at 0. The empty path is the first entry, if we consider
        # path_fragments[:0] it'd be duplicated
        for n in range(len(path_fragments), 0, -1):
            mount_index = n
            if os.path.ismount(os.path.join('/', *path_fragments[:n])):
                break

        for n in range(mount_index, len(path_fragments) + 1):
            if n < len(path_fragments) - 1:
                file_name = Configuration.DEFAULT_CONFIGURATION_FILE_NAME
            else:
                _, file_name = os.path.split(config_file_name)
            file_configuration = Configuration.from_file(
                os.path.join('/', *path_fragments[:n], file_name),
                Configuration.PROPERTIES,
                fail_on_read_error=config_was_read)
            if file_configuration is not None:
                config_was_read = True
                configuration = configuration.override_with(file_configuration)
            else:
                if n == len(path_fragments) - 1 and plz_config_set_explicitly:
                    raise ValidationException([
                        ValidationError(
                            f'Couldn\'t read from {config_file_name}')])
        return configuration, config_was_read

    @staticmethod
    def _override_with_user_level_config(configuration) \
            -> Tuple['Configuration', bool]:
        user_level_config_file = os.path.expanduser(
            os.path.join('~', '.config', 'plz',
                         Configuration.DEFAULT_CONFIGURATION_FILE_NAME))
        # We expect to be able to read the home directory, wrt to permissions
        user_level_config = Configuration.from_file(
            user_level_config_file, Configuration.PROPERTIES,
            fail_on_read_error=True)
        config_was_read = False
        if user_level_config is not None:
            configuration = configuration.override_with(user_level_config)
            config_was_read = True
        return configuration, config_was_read

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
                    try:
                        # noinspection PyCallingNonCallable
                        data[name] = prop.type(value)
                    except ValueError:
                        data[name] = value
        return Configuration(properties, data)

    def __init__(self, properties: Dict[str, Property], data: Dict[str, Any]):
        self.properties = properties
        self.data = data

    def override_with(self, other: 'Configuration') -> 'Configuration':
        return Configuration(self.properties, {**self.data, **other.data})

    def validate(self) -> 'Configuration':
        errors = []
        for prop in self.properties.values():
            value = self.data.get(prop.name)
            if value is None and prop.required:
                errors.append(prop.required_error())
            elif value is not None and not isinstance(value, prop.type):
                errors.append(prop.type_error(value))
        if errors:
            raise ValidationException(errors)
        return self

    def __getattr__(self, name):
        if name in self.properties:
            return self.data.get(name, self.properties[name].default)
        else:
            raise KeyError(name)

    def as_dict(self):
        return {name: getattr(self, name) for name in self.properties}
