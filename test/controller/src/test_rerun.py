import unittest

from .utils import run_example, rerun_execution


class TestReRun(unittest.TestCase):
    def test_rerun(self):
        context, execution_id = run_example(
            'parameters', 'simple',
            parameters={
                "foo": 55,
                "bar": "zeppelin"
            })
        output = b''.join(context.controller.get_logs(
            execution_id, since=None))
        self.assertEqual(
            'foo = 55\n'
            'bar = zeppelin\n',
            str(output, 'utf-8'))

        # Rerun without overriding the parameters
        _, rerun_execution_id = rerun_execution(
            context.controller,
            user='rerunner_user',
            project='rerunner_project',
            previous_execution_id=execution_id,
            override_parameters=None)

        output = b''.join(context.controller.get_logs(
            rerun_execution_id, since=None))
        self.assertEqual(
            'foo = 55\n'
            'bar = zeppelin\n',
            str(output, 'utf-8'))

    def test_rerun_override_parameters(self):
        context, execution_id = run_example(
            'parameters', 'simple',
            parameters={
                "foo": 55,
                "bar": "zeppelin"
            })
        output = b''.join(context.controller.get_logs(
            execution_id, since=None))
        self.assertEqual(
            'foo = 55\n'
            'bar = zeppelin\n',
            str(output, 'utf-8'))

        # Rerun overriding the parameters
        _, rerun_execution_id = rerun_execution(
            context.controller,
            user='rerunner_user',
            project='rerunner_project',
            previous_execution_id=execution_id,
            override_parameters={
                "foo": 66,
                "bar": "zeppelin"
            })

        # Make sure we get the overridden the parameters
        output = b''.join(context.controller.get_logs(
            rerun_execution_id, since=None))
        self.assertEqual(
            'foo = 66\n'
            'bar = zeppelin\n',
            str(output, 'utf-8'))