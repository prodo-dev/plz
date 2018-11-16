import json
from typing import Set, Optional

from redis import StrictRedis

from plz.controller.db_storage import DBStorage
from plz.controller.execution_composition import ExecutionComposition, \
    AtomicComposition, IndicesComposition


class RedisDBStorage(DBStorage):
    def __init__(self, redis: StrictRedis):
        super().__init__()
        self.redis = redis

    def store_start_metadata(
            self, execution_id: str, start_metadata: dict) -> None:
        self.redis.hset(
            'start_metadata', execution_id, json.dumps(start_metadata))

    def retrieve_start_metadata(self, execution_id: str) -> dict:
        start_metadata_bytes = self.redis.hget('start_metadata', execution_id)
        if start_metadata_bytes is None:
            raise ValueError(f'No start metadata available for {execution_id}')
        start_metadata = str(start_metadata_bytes, 'utf-8')
        return json.loads(str(start_metadata))

    def add_finished_execution_id(
            self, user: str, project: str, execution_id: str):
        self.redis.sadd(f'finished_execution_ids_for_user#{user}',
                        execution_id)
        self.redis.sadd(f'finished_execution_ids_for_project#{project}',
                        execution_id)

    def retrieve_finished_execution_ids(
            self, user: str, project: str) -> Set[str]:
        return {str(e, 'utf-8')
                for e in self.redis.sinter([
                    f'finished_execution_ids_for_user#{user}',
                    f'finished_execution_ids_for_project#{project}'])}

    def retrieve_execution_composition(self, execution_id: str) \
            -> ExecutionComposition:
        composition_bytes = self.redis.hget(
            'execution_composition', execution_id)
        # If there's nothing, assume it's a plain old atomic
        if composition_bytes is None:
            return AtomicComposition(execution_id)
        composition = str(composition_bytes, 'utf-8')
        if composition == 'atomic':
            return AtomicComposition(execution_id)
        elif composition.startswith('indices#'):
            index_bounds = composition[len('indices#'):].split('#')
            if len(index_bounds) != 2:
                raise ValueError(
                    f'Wrong composition for execution ID {execution_id}: '
                    f'{composition}')
            indices_to_execution_ids = {
                i: self.retrieve_execution_composition(
                    self.retrieve_execution_id_from_parent_and_index(
                        execution_id, i))
                for i in range(int(index_bounds[0]), int(index_bounds[1]))
            }
            return IndicesComposition(
                execution_id,
                indices_to_execution_ids,
                self.retrieve_tombstone_sub_execution_ids(execution_id))

    def retrieve_execution_id_from_parent_and_index(
                    self, execution_id: str, index: int) -> Optional[str]:
        execution_bytes = self.redis.hget(
            f'composition_index_to_execution#{execution_id}', index)
        if execution_bytes is None:
            return None
        return str(execution_bytes, 'utf-8')

    def retrieve_tombstone_sub_execution_ids(self, execution_id: str) -> set():
        execution_ids_bytes = self.redis.smembers(
            f'tombstone_executions#{execution_id}')
        if execution_ids_bytes is None:
            return set()
        return set(str(e, 'utf-8') for e in execution_ids_bytes)
