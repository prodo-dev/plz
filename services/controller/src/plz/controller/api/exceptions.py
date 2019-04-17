from typing import Dict

import requests


class ResponseHandledException(Exception):
    def __init__(self, response_code, **kwargs):
        self.response_code = response_code
        for k in kwargs:
            setattr(self, k, kwargs[k])


class JSONResponseException(Exception):
    def __init__(self, json_string: str):
        super().__init__(json_string)


class AbortedExecutionException(ResponseHandledException):
    def __init__(self, tombstone: object, **kwargs):
        super().__init__(response_code=requests.codes.gone, **kwargs)
        self.tombstone = tombstone


class BadInputMetadataException(ResponseHandledException):
    def __init__(self, input_metadata: dict, **kwargs):
        super().__init__(response_code=requests.codes.bad_request, **kwargs)
        self.input_metadata = input_metadata


class ExecutionAlreadyHarvestedException(ResponseHandledException):
    def __init__(self, execution_id: str, **kwargs):
        super().__init__(response_code=requests.codes.expectation_failed,
                         **kwargs)
        self.execution_id = execution_id


class ExecutionNotFoundException(ResponseHandledException):
    def __init__(self, execution_id: str, **kwargs):
        super().__init__(response_code=requests.codes.not_found, **kwargs)
        self.execution_id = execution_id


class IncorrectInputIDException(ResponseHandledException):
    def __init__(self, **kwargs):
        super().__init__(requests.codes.bad_request, **kwargs)


class InstanceNotRunningException(ResponseHandledException):
    def __init__(self, forensics: dict, **kwargs):
        super().__init__(response_code=requests.codes.gone, **kwargs)
        self.forensics = forensics


class InstanceStillRunningException(ResponseHandledException):
    def __init__(self, execution_id: str, **kwargs):
        super().__init__(response_code=requests.codes.conflict, **kwargs)
        self.execution_id = execution_id


class NotImplementedControllerException(ResponseHandledException):
    def __init__(self, message: str, **kwargs):
        super().__init__(response_code=requests.codes.not_implemented,
                         **kwargs)
        self.message = message


class ProviderKillingInstancesException(ResponseHandledException):
    def __init__(self,
                 failed_instance_ids_to_messages: Dict[str, str],
                 **kwargs):
        super().__init__(requests.codes.conflict, **kwargs)
        self.failed_instance_ids_to_messages = failed_instance_ids_to_messages


class WorkerUnreachableException(ResponseHandledException):
    def __init__(self, execution_id: str, **kwargs):
        super().__init__(response_code=requests.codes.unavailable, **kwargs)
        self.execution_id = execution_id


EXCEPTION_NAMES_TO_CLASSES = {
    e.__name__: e
    for e in (
        AbortedExecutionException,
        BadInputMetadataException,
        ExecutionAlreadyHarvestedException,
        ExecutionNotFoundException,
        IncorrectInputIDException,
        InstanceNotRunningException,
        InstanceStillRunningException,
        NotImplementedControllerException,
        ProviderKillingInstancesException,
        WorkerUnreachableException,
    )
}
