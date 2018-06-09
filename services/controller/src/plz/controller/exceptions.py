import requests


class ResponseHandledException(Exception):
    def __init__(self, response_code):
        self.response_code = response_code


class JSONResponseException(Exception):
    def __init__(self, json_string: str):
        super().__init__(json_string)


class WorkerUnreachableException(ResponseHandledException):
    def __init__(self, execution_id: str):
        super().__init__(response_code=requests.codes.unavailable)
        self.execution_id = execution_id


class AbortedExecutionException(ResponseHandledException):
    def __init__(self, forensics: dict):
        super().__init__(response_code=requests.codes.gone)
        self.forensics = forensics
