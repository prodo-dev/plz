import json
import os
from typing import Any, Dict, List, Type, TypeVar

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
            Property('user', required=True),
            Property('instance_type', default='t2.micro'),
            Property('project', required=True),
            Property('image', type=str, required=True),
            Property('command', type=list),
            Property('excluded_paths', type=list, default=[]),
            Property('debug', type=bool, default=False),
        ]
    }

    CONFIGURATION_FILE = 'plz.config.json'
    MISSING_CONFIGURATION_FILE_ERROR = ValidationError(
        f'You must create a {CONFIGURATION_FILE} file.')

    @staticmethod
    def load() -> 'Configuration':
        default_configuration = Configuration.defaults(
            Configuration.PROPERTIES)
        try:
            file_configuration = Configuration.from_file(
                Configuration.CONFIGURATION_FILE, Configuration.PROPERTIES)
        except FileNotFoundError:
            raise ValidationException(
                [Configuration.MISSING_CONFIGURATION_FILE_ERROR])
        env_configuration = Configuration.from_env(Configuration.PROPERTIES)

        return default_configuration \
            .override_with(file_configuration) \
            .override_with(env_configuration) \
            .validate()

    @staticmethod
    def defaults(properties: Dict[str, Property]) -> 'Configuration':
        data = {prop.name: prop.default for prop in properties.values()}
        return Configuration(properties, data)

    @staticmethod
    def from_file(filepath: str, properties: Dict[str, Property]) \
            -> 'Configuration':
        with open(filepath, 'r') as f:
            data = json.load(f)
        return Configuration(properties, data)

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
