import unittest

from .utils import run_example, harvest


class TestRun(unittest.TestCase):
    def setUp(self):
        harvest()

    @classmethod
    def tearDownClass(cls):
        harvest()
        super().tearDownClass()

    def test_run(self):
        context, execution_id = run_example('logs', 'simple')
        output = b''.join(context.controller.get_logs(
            execution_id, since=None))
        self.assertEqual('foo\nbar\nbaz\n', str(output, 'utf-8'))
