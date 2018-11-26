import json
import math
import time
import unittest
from collections import defaultdict
from typing import Tuple, Optional

from plz.cli.run_execution_operation import create_instance_market_spec

from .utils import run_example, harvest, create_file_map_from_tarball, \
    get_execution_listing_status, rerun_execution, TestingContext


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

    def test_five_indices_two_per_exec_no_harvest(self):
        self._run_range_and_check_results((0, 5), harvest_after_run=False,
                                          indices_per_execution=2)

    def test_six_indices_two_per_exec_no_harvest(self):
        self._run_range_and_check_results((0, 6), harvest_after_run=False,
                                          indices_per_execution=2)

    def test_five_indices_two_per_exec_harvest_after_run(self):
        self._run_range_and_check_results((0, 5), harvest_after_run=True,
                                          indices_per_execution=2)

    def test_rerun_parallel_indices(self):
        rainch = (0, 5)
        indices_per_execution = 2
        context, execution_id = self._run_range_and_check_results(
            rainch, harvest_after_run=False,
            indices_per_execution=indices_per_execution,
            check_only_assignment=True)
        _, execution_id = rerun_execution(
            context.controller,
            user='rerunner_user',
            project='rerunner_project',
            previous_execution_id=execution_id,
            override_parameters=None,
            instance_market_spec=create_instance_market_spec(
                context.configuration))
        execution_composition = context.controller.get_execution_composition(
            execution_id)
        self._check_execution_assignment(rainch, indices_per_execution,
                                         execution_composition)

    def _run_range_and_check_results(
            self, rainch: Tuple[int, int], harvest_after_run: bool,
            indices_per_execution: Optional[int],
            check_only_assignment: bool = False) -> Tuple[TestingContext, str]:
        context, execution_id = run_example(
            'parallel_indices', 'print_indices',
            is_end_to_end_path=False,
            parallel_indices_range=rainch,
            indices_per_execution=indices_per_execution)
        composition = context.controller.get_execution_composition(
            execution_id)
        indices_to_compositions = composition['indices_to_compositions']

        self._check_execution_assignment(rainch, indices_per_execution,
                                         indices_to_compositions)

        if check_only_assignment:
            return context, execution_id

        execution_ids_to_indices = defaultdict(lambda: set())
        for i, sc in indices_to_compositions.items():
            execution_ids_to_indices[sc['execution_id']].add(i)

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
            logs_lines = logs_str.split('\n')
            # Make sure there's a newline at the end...
            self.assertEqual(logs_lines[-1], '')
            # ... and remove the empty line created by split
            logs_lines = logs_lines[:-1]
            self.assertEqual(len(logs_lines),
                             len(execution_ids_to_indices[index_execution]))
            self.assertTrue(not all(
                [line != str(index) for line in logs_lines]))

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
        return context, execution_id

    def _check_execution_assignment(self, rainch, indices_per_execution,
                                    indices_to_compositions):
        range_len = rainch[1] - rainch[0]
        self.assertEqual(len(indices_to_compositions), range_len)
        number_of_different_executions = len(
            set(list(sc['execution_id']
                     for sc in indices_to_compositions.values())))
        self.assertEqual(math.ceil(range_len / (indices_per_execution or 1)),
                         number_of_different_executions)
