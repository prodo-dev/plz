import json
from typing import Any, Dict, List, Type, TypeVar

import os

T = TypeVar('T')


class ValidationError:
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


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
    PROPERTY_OBJECTS = [
        Property('host', default='localhost'),
        Property('port', type=int, default=80),
        Property('user', required=True),
        Property('project', required=True),
    ]
    PROPERTIES = {prop.name: prop for prop in PROPERTY_OBJECTS}

    CONFIGURATION_FILE = 'batman.config'

    @staticmethod
    def load() -> 'Configuration':
        try:
            file_configuration = \
                Configuration.from_file(Configuration.CONFIGURATION_FILE)
        except FileNotFoundError:
            file_configuration = Configuration({})
        return Configuration.defaults() \
            .override_with(file_configuration) \
            .override_with(Configuration.from_env()) \
            .validate()

    @staticmethod
    def defaults() -> 'Configuration':
        data = {prop.name: prop.default
                for prop in Configuration.PROPERTY_OBJECTS}
        return Configuration(data)

    @staticmethod
    def from_file(filepath: str) -> 'Configuration':
        with open(filepath, 'r') as f:
            data = json.load(f)
        return Configuration(data)

    @staticmethod
    def from_env() -> 'Configuration':
        data = {}
        for key, value in os.environ.items():
            if key.startswith('BATMAN_'):
                name = key[len('BATMAN_'):].lower()
                prop = Configuration.PROPERTIES.get(name)
                if prop:
                    try:
                        data[name] = prop.type(value)
                    except ValueError:
                        data[name] = value
        return Configuration(data)

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def override_with(self, other: 'Configuration') -> 'Configuration':
        return Configuration({**self.data, **other.data})

    def validate(self) -> 'Configuration':
        errors = []
        for prop in self.PROPERTY_OBJECTS:
            value = self.data.get(prop.name)
            if value is None and prop.required:
                errors.append(prop.required_error())
            elif not isinstance(value, prop.type):
                errors.append(prop.type_error(value))
        if errors:
            raise ValidationException(errors)
        return self

    def __getattr__(self, item):
        return self.data[item]
