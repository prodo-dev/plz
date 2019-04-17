import unittest

from src.utils import harvest, run_example


class TestParallelIndices(unittest.TestCase):
    def setUp(self):
        harvest()

    @classmethod
    def tearDownClass(cls):
        harvest()
        super().tearDownClass()

    def test_list_different_users(self):
        context, first_user_execution_id1 = run_example(
            'logs', 'simple', is_end_to_end_path=True)
        context, first_user_execution_id2 = run_example(
            'logs', 'simple', context=context, is_end_to_end_path=True)

        first_user = context.configuration.user

        infos = context.controller.list_executions(first_user,
                                                   list_for_all_users=False)
        self.assertSetEqual(
            {first_user_execution_id1,
             first_user_execution_id2},
            {i['execution_id']
             for i in infos})

        second_user = first_user + '_second'
        context.configuration.user = second_user

        # Nothing for the second user yet
        infos = context.controller.list_executions(second_user,
                                                   list_for_all_users=False)
        self.assertListEqual([], infos)

        context, second_user_execution_id = run_example(
            'logs', 'simple', context=context, is_end_to_end_path=True)

        # Check that the execution of the second user appears
        infos = context.controller.list_executions(second_user,
                                                   list_for_all_users=False)
        self.assertListEqual([second_user_execution_id],
                             [i['execution_id'] for i in infos])

        # Check that the executions of the first user are still the same
        infos = context.controller.list_executions(first_user,
                                                   list_for_all_users=False)
        self.assertSetEqual(
            {first_user_execution_id1,
             first_user_execution_id2},
            {i['execution_id']
             for i in infos})

        # Check that when requesting to list for all users, we get all of them
        infos = context.controller.list_executions(first_user,
                                                   list_for_all_users=True)
        self.assertSetEqual(
            {
                first_user_execution_id1,
                first_user_execution_id2,
                second_user_execution_id
            },
            {i['execution_id']
             for i in infos})
        # ...also for the second user
        infos = context.controller.list_executions(second_user,
                                                   list_for_all_users=True)
        self.assertSetEqual(
            {
                first_user_execution_id1,
                first_user_execution_id2,
                second_user_execution_id
            },
            {i['execution_id']
             for i in infos})
