from abc import ABC, abstractmethod
from io import BytesIO
from typing import BinaryIO, Iterator, List, Optional

from plz.controller.api.exceptions import ResponseHandledException
from plz.controller.api.types import InputMetadata, JSONString


class Controller(ABC):
    @classmethod
    @abstractmethod
    def handle_exception(cls, exception: ResponseHandledException):
        pass

    @abstractmethod
    def ping(self, ping_timeout: int) -> dict:
        pass

    @abstractmethod
    def run_execution(self, command: [str], snapshot_id: str, parameters: dict,
                      instance_market_spec: dict, execution_spec: dict,
                      start_metadata: dict) -> Iterator[dict]:
        """:raises IncorrectInputIDException:"""
        pass

    @abstractmethod
    def rerun_execution(
            self, user: str, project: str, previous_execution_id: str,
            instance_market_spec: dict) -> Iterator[dict]:
        pass

    @abstractmethod
    def list_executions(self) -> [dict]:
        pass

    @abstractmethod
    def get_status(self, execution_id: str) -> dict:
        pass

    @abstractmethod
    def get_logs(self, execution_id: str, since: Optional[int]) \
            -> Iterator[bytes]:
        pass

    @abstractmethod
    def get_output_files(self, execution_id: str) -> Iterator[bytes]:
        pass

    @abstractmethod
    def get_measures(
            self, execution_id: str, summary: bool) -> Iterator[JSONString]:
        pass

    @abstractmethod
    def delete_execution(self, execution_id: str, fail_if_running: bool,
                         fail_if_deleted: bool) -> None:
        """:raises InstanceStillRunningException:
           :raises ExecutionAlreadyHarvestedException:"""
        pass

    @abstractmethod
    def get_history(self, user: str, project: str) -> Iterator[JSONString]:
        pass

    @abstractmethod
    def create_snapshot(self, image_metadata: dict, context: BytesIO) \
            -> Iterator[JSONString]:
        pass

    @abstractmethod
    def put_input(self, input_id: str, input_metadata: InputMetadata,
                  input_data_stream: BinaryIO) -> None:
        pass

    @abstractmethod
    def check_input_data(
            self, input_id: str, metadata: InputMetadata) -> bool:
        pass

    @abstractmethod
    def get_input_id_or_none(self, metadata: InputMetadata) -> Optional[str]:
        pass

    @abstractmethod
    def delete_input_data(self, input_id: str):
        pass

    @abstractmethod
    def get_user_last_execution_id(self, user: str) -> Optional[str]:
        pass

    @abstractmethod
    def kill_instances(
            self, instance_ids: Optional[List[str]], force_if_not_idle: bool) \
            -> bool:
        """:raises ProviderKillingInstancesException:

           :returns bool: false if there are no instances to kill
        """
        pass

    @abstractmethod
    def describe_execution_entrypoint(self, execution_id: str) -> dict:
        pass
