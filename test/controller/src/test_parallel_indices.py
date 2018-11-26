import json
import time
import unittest
from typing import Tuple, Optional

from .utils import run_example, harvest, create_file_map_from_tarball, \
    get_execution_listing_status


class TestParallelIndices(unittest.TestCase):
    def setUp(self):
        harvest()

    @classmethod
    def tearDownClass(cls):
        harvest()
        super().tearDownClass()

    def test_five_separate_indices_no_harvest(self):
        self._run_range_and_check_results((0, 5),
                                          harvest_after_run=False,
                                          indices_per_execution=None)

    def test_five_separate_indices_harvest_after_run(self):
        self._run_range_and_check_results((0, 5), harvest_after_run=True,
                                          indices_per_execution=None)

    def _run_range_and_check_results(
            self, rainch: Tuple[int, int], harvest_after_run: bool,
            indices_per_execution: Optional[int]):
        context, execution_id = run_example(
            'parallel_indices', 'print_indices',
            is_end_to_end_path=False,
            parallel_indices_range=rainch,
            indices_per_execution=indices_per_execution)
        composition = context.controller.get_execution_composition(
            execution_id)
        indices_to_compositions = composition['indices_to_compositions']
        for index, subcomp in indices_to_compositions.items():
            # Json indices are always strings...
            index = int(index)

            index_execution = subcomp['execution_id']

            execution_listing_status = get_execution_listing_status(
                context.controller, index_execution)
            while harvest_after_run and execution_listing_status is not None:
                if execution_listing_status is not 'running':
                    context.controller.harvest()
                time.sleep(0.1)
                execution_listing_status = get_execution_listing_status(
                    context.controller, index_execution)

            logs_bytes = context.controller.get_logs(
                index_execution, since=None)
            logs_str = str(b''.join(logs_bytes), 'utf-8')
            self.assertEqual(logs_str, str(index) + '\n')

            file_map = create_file_map_from_tarball(
                context.controller.get_output_files(
                    index_execution, index=index, path=None))

            self.assertDictEqual(file_map, {'the_file': f'index is: {index}'})

            measures = json.loads(''.join(context.controller.get_measures(
                index_execution, summary=False, index=index)))
            self.assertDictEqual(measures, {
                'accuracy': index,
                'summary': {
                    'time': index
                }})

            summary_measures = json.loads(
                ''.join(context.controller.get_measures(
                    index_execution, summary=True, index=index)))
            self.assertDictEqual(summary_measures, {'time': index})

            # When not harvesting after run, check that the history works
            history = context.controller.get_history(
                user=context.configuration.user,
                project=context.configuration.project)
            # If we harvested, the execution is in the history, we can check
            # the metadata
            if harvest_after_run:
                metadata = json.loads(''.join(history))[index_execution]

                self.assertDictEqual(metadata['measures'],
                                     {
                                         str(index): {
                                             'accuracy': index,
                                             'summary': {
                                                 'time': index
                                             }
                                         }
                                     })
