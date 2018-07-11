import hashlib
import logging
import os
import re
import tempfile
from typing import BinaryIO, Optional

from redis import StrictRedis

from plz.controller.api.exceptions import IncorrectInputIDException
from plz.controller.api.types import InputMetadata

READ_BUFFER_SIZE = 16384
_INPUT_ID_KEY = f'{__name__}#input_id'

log = logging.getLogger(__name__)

InputID = str


class InputDataConfiguration:
    def __init__(self, redis: StrictRedis, input_dir: str, temp_data_dir: str):
        self.redis = redis
        self.input_dir = input_dir
        self.temp_data_dir = temp_data_dir

    def publish_input_data(
            self, expected_input_id: str, metadata: InputMetadata,
            input_data_stream: BinaryIO) -> None:
        input_file_path = self.input_file(expected_input_id)
        if os.path.exists(input_file_path):
            input_data_stream.close()
            return

        file_hash = hashlib.sha256()
        fd, temp_file_path = tempfile.mkstemp(dir=self.temp_data_dir)
        try:
            with os.fdopen(fd, 'wb') as f:
                bytes_read = 0
                while True:
                    data = input_data_stream.read(READ_BUFFER_SIZE)
                    bytes_read += len(data)
                    log.debug(f'{bytes_read} bytes of input read')
                    if not data:
                        break
                    f.write(data)
                    file_hash.update(data)

            input_id = file_hash.hexdigest()
            if input_id != expected_input_id:
                raise IncorrectInputIDException()

            os.rename(temp_file_path, input_file_path)
            if metadata.has_all_args():
                self._store_input_id(metadata, input_id)
            return
        except Exception:
            os.remove(temp_file_path)
            raise

    def get_input_id_from_metadata_or_none(self, metadata: InputMetadata) \
            -> Optional[str]:
        input_id_bytes = self.redis.hget(_INPUT_ID_KEY, metadata.redis_field())
        if not input_id_bytes:
            return None
        input_id = str(input_id_bytes, 'utf-8')
        # We have the metadata stored, but the file doesn't exist. I can
        # imagine this happening so let's make this cache mechanism resilient
        # to that.
        if not self._input_file_exists(input_id):
            return None
        else:
            return input_id

    def check_input_data(
            self, input_id: str, metadata: InputMetadata) -> bool:
        if self._input_file_exists(input_id):
            if metadata.has_all_args():
                # The reason to do this is that, if there's a blob that
                # changed timestamp but not hash (because of a `touch`, for
                # instance), the timestamp check will always return false and
                # the tarball will be constructed all the times on the client
                # side. It happened.
                self._store_input_id(metadata, input_id)
            return True
        else:
            return False

    def prepare_input_stream(self, execution_spec: dict) -> Optional[BinaryIO]:
        input_id: Optional[str] = execution_spec.get('input_id')
        if not input_id:
            return None
        try:
            input_file_path = self.input_file(input_id)
            return open(input_file_path, 'rb')
        except FileNotFoundError:
            raise IncorrectInputIDException()

    def input_file(self, input_id: str):
        if not re.match(r'^\w{64}$', input_id):
            raise IncorrectInputIDException()
        input_file_path = os.path.join(self.input_dir, input_id)
        return input_file_path

    def _store_input_id(
            self, metadata: InputMetadata, input_id: str) -> None:
        field = metadata.redis_field()
        self.redis.hset(_INPUT_ID_KEY, field, input_id)
        log.debug(field + ': ' +
                  str(self.get_input_id_from_metadata_or_none(metadata)))

    def _input_file_exists(self, input_id: str) -> bool:
        return os.path.exists(self.input_file(input_id))
