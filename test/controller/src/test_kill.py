import unittest
from typing import Set

import time

from plz.controller.api import Controller
from plz.controller.api.exceptions import ProviderKillingInstancesException
from src.utils import get_execution_listing_status, harvest, run_example


class TestKill(unittest.TestCase):
    def setUp(self):
        harvest()

    @classmethod
    def tearDownClass(cls):
        harvest()
        super().tearDownClass()

    def test_kill_all_force_non_idle(self):
        context, execution_id1 = run_example(
            'common', 'run_forever', is_end_to_end_path=False)
        context, execution_id2 = run_example(
            'common', 'run_forever', context=context, is_end_to_end_path=False)

        infos = context.controller.list_executions(
            context.configuration.user,
            list_for_all_users=False)
        self.assertSetEqual({execution_id1,
                             execution_id2},
                            {i['execution_id'] for i in infos})

        context.controller.kill_instances(
            user=context.configuration.user,
            instance_ids=None,
            force_if_not_idle=True)

        infos = context.controller.list_executions(
            context.configuration.user,
            list_for_all_users=False)

        self.assertListEqual([], infos)

    def test_kill_all_fail_because_non_idle(self):
        context, execution_id1 = run_example(
            'common', 'run_forever', is_end_to_end_path=False)
        context, execution_id2 = run_example(
            'common', 'run_forever', context=context, is_end_to_end_path=False)

        infos = context.controller.list_executions(
            context.configuration.user,
            list_for_all_users=False)
        self.assertSetEqual({execution_id1,
                             execution_id2},
                            {i['execution_id'] for i in infos})

        with self.assertRaises(ProviderKillingInstancesException):
            context.controller.kill_instances(
                instance_ids=None,
                force_if_not_idle=False,
                user=context.configuration.user)

        infos = context.controller.list_executions(
            context.configuration.user,
            list_for_all_users=False)

        self.assertSetEqual({execution_id1,
                             execution_id2},
                            {i['execution_id'] for i in infos})
        self._cleanup_instances(
            context.controller,
            context.configuration.user,
            {execution_id1, execution_id2})

    def test_exited_is_not_idle(self):
        context, finished_execution_id = run_example(
            'logs', 'simple', is_end_to_end_path=True)

        infos = context.controller.list_executions(
            context.configuration.user,
            list_for_all_users=False)
        self.assertSetEqual({finished_execution_id},
                            {i['execution_id'] for i in infos})

        execution_listing_status = None
        while execution_listing_status != 'exited':
            execution_listing_status = get_execution_listing_status(
                context.configuration.user,
                context.controller,
                finished_execution_id)
            time.sleep(0.1)

        with self.assertRaises(ProviderKillingInstancesException):
            context.controller.kill_instances(
                instance_ids=None,
                force_if_not_idle=False,
                user=context.configuration.user)

        infos = context.controller.list_executions(
            context.configuration.user,
            list_for_all_users=False)
        self.assertSetEqual({finished_execution_id},
                            {i['execution_id'] for i in infos})
        self._cleanup_instances(
            context.controller,
            context.configuration.user,
            {finished_execution_id})

    def _cleanup_instances(
            self, controller: Controller, user: str, execution_ids: Set[str]) \
            -> None:
        infos = controller.list_executions(user, list_for_all_users=False)

        try:
            controller.kill_instances(
                instance_ids=[i['instance_id']
                              for i in infos
                              if i['execution_id'] in execution_ids],
                user=user,
                force_if_not_idle=True)
        except ProviderKillingInstancesException as e:
            print(e.failed_instance_ids_to_messages)
            raise

        infos = controller.list_executions(user, list_for_all_users=False)
        self.assertListEqual(infos, [])
