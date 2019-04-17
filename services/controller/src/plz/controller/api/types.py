from typing import Optional


class InputMetadata:
    def __init__(self):
        self.user: Optional[str] = None
        self.project: Optional[str] = None
        self.path: Optional[str] = None
        self.timestamp_millis: Optional[int] = None

    @staticmethod
    def of(user: str, project: str, path: str, timestamp_millis: int):
        input_metadata = InputMetadata()
        input_metadata.user: Optional[str] = user
        input_metadata.project: Optional[str] = project
        input_metadata.path: Optional[str] = path
        input_metadata.timestamp_millis: Optional[int] = timestamp_millis
        return input_metadata

    def has_all_args(self) -> bool:
        return all(self.__dict__.values())

    def has_all_args_or_none(self) -> bool:
        return self.has_all_args() or not any(self.__dict__.values())

    def redis_field(self) -> str:
        return (
            f'{self.user}#{self.project}#{self.path}'
            f'#{self.timestamp_millis}')


JSONString = str
