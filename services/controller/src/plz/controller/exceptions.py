class JSONResponseException(Exception):
    def __init__(self, json_string: str):
        super().__init__(json_string)
