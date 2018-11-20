import unittest

from .utils import run_example, harvest


class TestParallelIndices(unittest.TestCase):
    def setUp(self):
        harvest()

    @classmethod
    def tearDownClass(cls):
        harvest()
        super().tearDownClass()

    def test_five_separate_indices(self):
        context, execution_id = run_example(
            'parallel_indices', 'print_indices',
            is_end_to_end_path=False,
            parallel_indices_range=(0, 5))
        composition = context.controller.get_execution_composition(
            execution_id)
        indices_to_compositions = composition['indices_to_compositions']
        for index, subcomp in indices_to_compositions.items():
            logs_bytes = context.controller.get_logs(
                subcomp['execution_id'], since=None)
            logs_str = str(b''.join(logs_bytes), 'utf-8')
            self.assertEqual(logs_str, index + '\n')
