from typing import Optional


class InputMetadata:
    def __init__(self):
        self.user: Optional[str] = None
        self.project: Optional[str] = None
        self.path: Optional[str] = None
        self.timestamp_millis: Optional[int] = None

    def has_all_args(self) -> bool:
        return all(self.__dict__.values())

    def has_all_args_or_none(self) -> bool:
        return self.has_all_args() or not any(self.__dict__.values())

    def redis_field(self) -> str:
        return (f'{self.user}#{self.project}#{self.path}'
                f'#{self.timestamp_millis}')
