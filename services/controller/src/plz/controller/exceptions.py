class ResponseHandledException(Exception):
    def __init__(self, response_code):
        self.response_code = response_code


class JSONResponseException(Exception):
    def __init__(self, json_string: str):
        super().__init__(json_string)
