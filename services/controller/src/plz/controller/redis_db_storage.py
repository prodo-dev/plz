import json
from typing import Set

from redis import StrictRedis

from plz.controller.db_storage import DBStorage


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
