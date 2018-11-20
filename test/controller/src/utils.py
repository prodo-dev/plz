import os
from typing import Tuple, Optional

from plz.cli.configuration import Configuration
from plz.cli.controller_proxy import ControllerProxy
from plz.cli.run_execution_operation import RunExecutionOperation, \
    create_instance_market_spec
from plz.cli.server import Server
from plz.controller.api import Controller

from plz.cli.snapshot import capture_build_context, submit_context_for_building

dir_of_this_script = os.path.dirname(os.path.abspath(__file__))


class TestingContext:
    def __init__(self,
                 configuration: Configuration,
                 controller: Controller,
                 snapshot_id: str):
        self.configuration = configuration
        self.controller = controller
        self.snapshot_id = snapshot_id


def create_context_for_example(
        example_type: str,
        example_name: str,
        is_end_to_end_path: bool) -> TestingContext:
    if is_end_to_end_path:
        path_to_example = ['..', '..', 'end-to-end']
    else:
        path_to_example = ['..', 'contexts']
    example_dir = os.path.join(
        dir_of_this_script, *path_to_example,
        example_type,
        example_name)
    configuration = Configuration.load(example_dir)
    configuration.context_path = example_dir
    # The default is None (by design, so that the user needs to specify it),
    # and it will break when running tests against a controller starting
    # AWS instances
    configuration.max_bid_price_in_dollars_per_hour = 0.1
    # The default in a configuration is 0. With that value, tests take ages to
    # run as instances are stopped and started again
    configuration.instance_max_idle_time_in_minutes = 3
    server = Server.from_configuration(configuration)
    controller = ControllerProxy(server)
    with capture_build_context(
        image=configuration.image,
        image_extensions=configuration.image_extensions,
        command=configuration.command,
        context_path=configuration.context_path,
        excluded_paths=configuration.excluded_paths,
        included_paths=configuration.included_paths,
        exclude_gitignored_files=configuration.exclude_gitignored_files,
    ) as build_context:
        snapshot_id = submit_context_for_building(
            user=configuration.user,
            project=configuration.project,
            controller=controller,
            build_context=build_context,
            quiet_build=True)
        return TestingContext(
            configuration=configuration,
            controller=ControllerProxy(server),
            snapshot_id=snapshot_id)


def run_example(
        example_type: str,
        example_name: str,
        is_end_to_end_path: bool,
        context: Optional[TestingContext] = None,
        input_id: Optional[str] = None,
        parameters: Optional[dict] = None,
        start_metadata: Optional[dict] = None,
        parallel_indices_range: Optional[Tuple[int, int]] = None) \
        -> Tuple[TestingContext, str]:
    parameters = parameters if parameters is not None else {}
    start_metadata = start_metadata if start_metadata is not None else {}
    if context is None:
        context = create_context_for_example(
            example_type, example_name, is_end_to_end_path)
    instance_market_spec = create_instance_market_spec(context.configuration)
    execution_spec = RunExecutionOperation.create_execution_spec(
        context.configuration, input_id)
    response_dicts = context.controller.run_execution(
        context.configuration.command,
        context.snapshot_id,
        parameters=parameters,
        instance_market_spec=instance_market_spec,
        execution_spec=execution_spec,
        start_metadata=start_metadata,
        parallel_indices_range=parallel_indices_range)

    execution_id, _ = \
        RunExecutionOperation.get_execution_id_from_start_response(
            response_dicts)
    return context, execution_id


def rerun_execution(
        controller: Controller,
        user: str,
        project: str,
        previous_execution_id: str,
        instance_market_spec: dict,
        override_parameters: Optional[dict] = None,
        instance_max_uptime_in_minutes: Optional[int] = None) \
        -> Tuple[Controller, str]:
    response_dicts = controller.rerun_execution(
        user=user,
        project=project,
        instance_max_uptime_in_minutes=instance_max_uptime_in_minutes,
        override_parameters=override_parameters,
        previous_execution_id=previous_execution_id,
        instance_market_spec=instance_market_spec)

    execution_id, _ = \
        RunExecutionOperation.get_execution_id_from_start_response(
            response_dicts)
    return controller, execution_id


def harvest():
    # The environment should have everything we need to create a controller
    # during a testing run: host and port for the controller
    configuration = Configuration.from_env(Configuration.PROPERTIES)
    server = Server.from_configuration(configuration)
    controller = ControllerProxy(server)
    controller.harvest()
