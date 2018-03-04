import unittest

from configuration import Configuration, Property, ValidationError, \
    ValidationException


# noinspection PyMethodMayBeStatic
class ConfigurationTest(unittest.TestCase):
    def test_exposes_properties(self):
        properties = property_dict([
            Property('thing'),
            Property('entity'),
        ])
        data = {
            'thing': 'foo',
            'entity': 'bar',
        }
        configuration = Configuration(properties, data)
        self.assertEqual(configuration.thing, 'foo')
        self.assertEqual(configuration.entity, 'bar')

    def test_missing_values_have_defaults(self):
        properties = property_dict([
            Property('thing'),
            Property('entity', default='object'),
        ])
        data = {}
        configuration = Configuration(properties, data)
        self.assertEqual(configuration.thing, None)
        self.assertEqual(configuration.entity, 'object')

    def test_non_existent_properties_raise_errors(self):
        properties = property_dict([
            Property('thing'),
        ])
        data = {}
        configuration = Configuration(properties, data)
        with self.assertRaises(KeyError):
            # noinspection PyStatementEffect
            configuration.entity

    def test_values_are_checked_against_their_type(self):
        properties = property_dict([
            Property('thing', type=int),
            Property('entity', type=bool),
        ])
        data = {
            'thing': 3,
            'entity': False,
        }
        configuration = Configuration(properties, data)
        configuration.validate()

    def test_invalid_values_cause_a_validation_exception(self):
        properties = property_dict([
            Property('thing', type=int),
            Property('entity', type=bool),
        ])
        data = {
            'thing': 'three',
            'entity': False,
        }
        configuration = Configuration(properties, data)
        with self.assertRaises(ValidationException) as raises_context:
            configuration.validate()
        self.assertEqual(raises_context.exception.errors, [
            ValidationError(
                'The property "thing" must be an integer.\n'
                'Invalid value: \'three\'')])

    def test_some_values_are_required(self):
        properties = property_dict([
            Property('thing', required=True),
            Property('entity'),
        ])
        data = {
            'thing': 'ding',
            'entity': 'dong',
        }
        configuration = Configuration(properties, data)
        configuration.validate()

    def test_missing_required_values_cause_a_validation_exception(self):
        properties = property_dict([
            Property('thing', required=True),
            Property('entity'),
        ])
        data = {
            'entity': 'dong',
        }
        configuration = Configuration(properties, data)
        with self.assertRaises(ValidationException) as raises_context:
            configuration.validate()
        self.assertEqual(raises_context.exception.errors, [
            ValidationError('The property "thing" is required.')])

    def test_overriding_configuration_favours_the_latter(self):
        properties = property_dict([
            Property('thing'),
            Property('entity'),
        ])
        configuration_a = Configuration(properties, {
            'thing': 'foo',
            'entity': 'bar',
        })
        configuration_b = Configuration(properties, {
            'thing': 'baz',
        })
        configuration = configuration_a.override_with(configuration_b)
        self.assertEqual(configuration.thing, 'baz')
        self.assertEqual(configuration.entity, 'bar')


def property_dict(properties):
    return {prop.name: prop for prop in properties}
