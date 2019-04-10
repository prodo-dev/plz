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

    def test_kill_all(self):
        context, execution_id1 = run_example(
            'common', 'run_forever', is_end_to_end_path=False)
        context, execution_id2 = run_example(
            'common', 'run_forever', context=context, is_end_to_end_path=False)

        self._assert_running_executions(
            context.controller,
            context.configuration.user,
            {execution_id1, execution_id2})

        context.controller.kill_instances(
            user=context.configuration.user,
            instance_ids=None,
            ignore_ownership=False,
            including_idle=False,
            force_if_not_idle=True)

        self._assert_running_executions(
            context.controller,
            context.configuration.user,
            execution_ids=set('1'))

    def test_kill_fail_because_non_idle(self):
        context, execution_id = run_example(
            'common', 'run_forever', is_end_to_end_path=False)

        infos = self._assert_running_executions(
            context.controller,
            context.configuration.user,
            execution_ids={execution_id})

        with self.assertRaises(ProviderKillingInstancesException):
            context.controller.kill_instances(
                instance_ids=[infos[0]['instance_id']],
                ignore_ownership=False,
                including_idle=None,
                force_if_not_idle=False,
                user=context.configuration.user)

        self._assert_and_cleanup_instances(
            context.controller,
            context.configuration.user,
            {execution_id})

    def test_do_not_kill_exited(self):
        context, finished_execution_id = run_example(
            'logs', 'simple', is_end_to_end_path=True)

        infos = self._assert_running_executions(
            context.controller,
            context.configuration.user,
            {finished_execution_id})

        execution_listing_status = None
        while execution_listing_status != 'exited':
            execution_listing_status = get_execution_listing_status(
                context.configuration.user,
                context.controller,
                finished_execution_id)
            time.sleep(0.1)

        # We are not forcing non-idle instances. Extted instances are not idle
        # (they're holding the data for harvesting). So an exception is raised
        # and the execution will still be there.
        with self.assertRaises(ProviderKillingInstancesException):
            context.controller.kill_instances(
                instance_ids=[infos[0]['instance_id']],
                ignore_ownership=False,
                including_idle=None,
                force_if_not_idle=False,
                user=context.configuration.user)

        self._assert_and_cleanup_instances(
            context.controller,
            context.configuration.user,
            {finished_execution_id})

    def test_kill_exited_if_forced(self):
        context, finished_execution_id = run_example(
            'logs', 'simple', is_end_to_end_path=True)

        infos = self._assert_running_executions(
            context.controller,
            context.configuration.user,
            {finished_execution_id})

        execution_listing_status = None
        while execution_listing_status != 'exited':
            execution_listing_status = get_execution_listing_status(
                context.configuration.user,
                context.controller,
                finished_execution_id)
            time.sleep(0.1)

        # Note we are forcing to kill non-idle instances, so it'll kill the
        # one with exited status
        context.controller.kill_instances(
            instance_ids=[infos[0]['instance_id']],
            ignore_ownership=False,
            including_idle=None,
            force_if_not_idle=True,
            user=context.configuration.user)

        self._assert_running_executions(
            context.controller,
            context.configuration.user,
            execution_ids=set())

    def test_kill_single_instance(self):
        context, execution_id1 = run_example(
            'common', 'run_forever', is_end_to_end_path=False)
        context, execution_id2 = run_example(
            'common', 'run_forever', context=context, is_end_to_end_path=False)

        infos = self._assert_running_executions(
            context.controller,
            context.configuration.user,
            {execution_id1, execution_id2})

        context.controller.kill_instances(
            instance_ids=[i['instance_id'] for i in infos
                          if i['execution_id'] == execution_id1],
            ignore_ownership=False,
            including_idle=None,
            force_if_not_idle=True,
            user=context.configuration.user)

        self._assert_and_cleanup_instances(
            context.controller,
            context.configuration.user,
            {execution_id2})

    def test_kill_fail_because_of_ownership(self):
        context, execution_id = run_example(
            'common', 'run_forever', is_end_to_end_path=False)

        infos = self._assert_running_executions(
            context.controller,
            context.configuration.user,
            {execution_id})

        first_user = context.configuration.user
        second_user = first_user + '_second'

        with self.assertRaises(ProviderKillingInstancesException):
            context.controller.kill_instances(
                instance_ids=[infos[0]['instance_id']],
                ignore_ownership=False,
                including_idle=None,
                force_if_not_idle=True,
                user=second_user)

        self._assert_and_cleanup_instances(
            context.controller, first_user, {execution_id})

    def test_kill_all_kills_only_user(self):
        context, first_user_execution_id = run_example(
            'common', 'run_forever', is_end_to_end_path=False)

        self._assert_running_executions(
            context.controller,
            context.configuration.user,
            {first_user_execution_id})

        first_user = context.configuration.user
        second_user = first_user + '_second'
        context.configuration.user = second_user

        context, second_user_execution_id = run_example(
            'common', 'run_forever', context=context, is_end_to_end_path=False)

        self._assert_running_executions(
            context.controller,
            second_user,
            {second_user_execution_id})

        context.controller.kill_instances(
            user=second_user,
            ignore_ownership=False,
            instance_ids=None,
            including_idle=None,
            force_if_not_idle=True)

        # Check the execution for the first user still exists
        self._assert_running_executions(
            context.controller,
            first_user,
            {first_user_execution_id})

        self._assert_running_executions(
            context.controller,
            second_user,
            execution_ids=set())

        self._assert_and_cleanup_instances(
            context.controller,
            first_user,
            {first_user_execution_id})

    def test_kill_all_berserk(self):
        context, first_user_execution_id = run_example(
            'common', 'run_forever', is_end_to_end_path=False)

        first_user = context.configuration.user
        second_user = first_user + '_second'
        context.configuration.user = second_user

        self._assert_running_executions(
            context.controller, first_user, {first_user_execution_id})

        context, second_user_execution_id = run_example(
            'common', 'run_forever', context=context, is_end_to_end_path=False)

        # The user doesn't really matter as we'll list for all users
        third_user = second_user + '_third'
        self._assert_running_executions(
            context.controller,
            third_user,
            {first_user_execution_id, second_user_execution_id},
            list_for_all_users=True)

        # Kill ignoring ownership
        context.controller.kill_instances(
            user=second_user,
            instance_ids=None,
            including_idle=None,
            ignore_ownership=True,
            force_if_not_idle=True)

        # Same listing as before but there's nothing there because
        # EVERYTHING WAS KILLED
        self._assert_running_executions(
            context.controller,
            third_user,
            execution_ids=set(),
            list_for_all_users=True)

    def _assert_running_executions(
            self,
            controller: Controller,
            user: str,
            execution_ids: Set[str],
            list_for_all_users: bool = False) -> [dict]:
        # Filter instances shutting down, as they appear in the listing when
        # running in AWS (either with an execution ID, or idle, with an
        # empty execution ID)
        infos = [
            i for i in controller.list_executions(
                user=user,
                list_for_all_users=list_for_all_users)
            if i['status'] not in {'shutting-down'}]
        self.assertSetEqual(execution_ids,
                            {i['execution_id'] for i in infos})
        return infos

    def _assert_and_cleanup_instances(
            self, controller: Controller, user: str, execution_ids: Set[str]) \
            -> None:
        infos = self._assert_running_executions(
            controller, user, execution_ids)
        try:
            controller.kill_instances(
                instance_ids=[i['instance_id']
                              for i in infos
                              if i['execution_id'] in execution_ids],
                user=user,
                force_if_not_idle=True,
                ignore_ownership=False,
                including_idle=None)
        except ProviderKillingInstancesException as e:
            print(e.failed_instance_ids_to_messages)
            raise
        self._assert_running_executions(controller, user, execution_ids=set())
