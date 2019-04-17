import io
import json
import unittest

from plz.cli import parameters
from plz.cli.exceptions import CLIException


class ParametersTest(unittest.TestCase):
    def test_reads_parameters_from_io(self):
        expected_parameters = {'foo': 1, 'bar': 2, 'baz': 'three'}
        f = io.StringIO(json.dumps(expected_parameters))
        actual_parameters = parameters.parse_io(f, 'parameters.json')
        self.assertEqual(actual_parameters, expected_parameters)

    def test_reports_when_the_parameters_are_not_valid_JSON(self):
        f = io.StringIO('{this: is, not: json}')
        with self.assertRaises(CLIException) as cm:
            parameters.parse_io(f, 'parameters.json')
        self.assertEqual(
            cm.exception.args[0],
            'There was an error parsing "parameters.json".')

    def test_reports_when_the_parameters_are_not_a_JSON_object(self):
        f = io.StringIO('42')
        with self.assertRaises(CLIException) as cm:
            parameters.parse_io(f, 'parameters.json')
        self.assertEqual(
            cm.exception.args[0],
            'The parameters in "parameters.json" must be a JSON object.')
