from typing import Iterator, Optional


class Instance:
    def run(self, command: str, snapshot_id: str):
        pass

    def logs(self):
        pass

    def cleanup(self):
        pass


class InstanceProvider:
    def acquire_instance(self, execution_id: str) -> Iterator[str]:
        pass

    def release_instance(self, execution_id: str):
        pass

    def instance_for(self, execution_id: str) -> Optional[Instance]:
        pass

    def push(self, image_tag: str):
        pass
