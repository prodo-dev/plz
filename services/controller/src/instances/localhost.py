import logging
from typing import Iterator, Optional

import invocations
from instances.instance_base import Instance

log = logging.getLogger('localhost')


class LocalhostInstance(Instance):
    def __init__(self, execution_id: str):
        self.execution_id = execution_id

    def run(self, command: str, snapshot_id: str):
        """
        Runs a command on the instance.
        """
        invocations.docker_run(self.execution_id, snapshot_id, command)

    def logs(self):
        return invocations.docker_logs(self.execution_id, ['sh', '-c'])

    def cleanup(self):
        invocations.docker_rm(self.execution_id)


class Localhost:
    def __init__(self):
        self.execution_ids = set()

    def acquire_instance(self, execution_id: str) -> Iterator[str]:
        """
        "Acquires" an instance.

        As we're dealing with `localhost` here, it's always the same instance.
        """
        self.execution_ids.add(execution_id)
        return iter([])

    def release_instance(self, execution_id: str):
        """
        "Releases" an instance.

        As we're dealing with `localhost` here, this doesn't do much.
        """
        self.instance_for(execution_id).cleanup()
        self.execution_ids.remove(execution_id)

    def instance_for(self, execution_id: str) -> Optional[LocalhostInstance]:
        """
        "Gets" the instance assigned to the execution ID.

        As we're dealing with `localhost` here, it's always the same instance.
        """
        if execution_id in self.execution_ids:
            return LocalhostInstance(execution_id)
        else:
            return None
