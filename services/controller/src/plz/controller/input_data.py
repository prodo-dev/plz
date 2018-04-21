import hashlib
import logging
import os
import re
import tempfile
from typing import Optional

import requests
from flask import abort, jsonify, request, Response
from redis import StrictRedis

READ_BUFFER_SIZE = 16384
_INPUT_ID_KEY = f'{__name__}#input_id'

log = logging.getLogger(__name__)


class InputDataConfiguration:
    def __init__(self, redis: StrictRedis, input_dir: str, temp_data_dir: str):
        self.redis = redis
        self.input_dir = input_dir
        self.temp_data_dir = temp_data_dir

    def publish_input_data(self, expected_input_id: str):
        metadata: _InputMetadata = _InputMetadata.from_request()
        input_file_path = self.input_file(expected_input_id)
        if os.path.exists(input_file_path):
            request.stream.close()
            return jsonify({
                'id': expected_input_id,
            })

        file_hash = hashlib.sha256()
        fd, temp_file_path = tempfile.mkstemp(dir=self.temp_data_dir)
        try:
            with os.fdopen(fd, 'wb') as f:
                bytes_read = 0
                while True:
                    data = request.stream.read(READ_BUFFER_SIZE)
                    bytes_read += len(data)
                    log.debug(f'{bytes_read} bytes of input read')
                    if not data:
                        break
                    f.write(data)
                    file_hash.update(data)

            input_id = file_hash.hexdigest()
            if input_id != expected_input_id:
                abort(
                    requests.codes.bad_request, 'The input ID was incorrect.')

            os.rename(temp_file_path, input_file_path)
            if metadata.has_all_args():
                self._store_input_id(metadata, input_id)
            return jsonify({
                'id': input_id,
            })
        except Exception:
            os.remove(temp_file_path)
            raise

    def get_input_id_from_metadata_or_none(
            self,
            metadata: Optional['_InputMetadata'] = None) -> Response:
        try:
            metadata = metadata or _InputMetadata.from_request()
        except ValueError:
            abort(requests.codes.bad_request)
            # Make static analyser happy by having this return statement...
            return Response()
        input_id_bytes = self.redis.hget(_INPUT_ID_KEY, metadata.redis_field())
        if not input_id_bytes:
            return jsonify({'id': None})
        input_id = str(input_id_bytes, 'utf-8')
        # We have the metadata stored, but the file doesn't exist. I can
        # imagine this happening so let's make this cache mechanism resilient
        # to that.
        if not self._input_file_exists(input_id):
            input_id = None
        else:
            input_id = str(input_id_bytes, 'utf-8')
        return jsonify({'id': input_id})

    def check_input_data(self, input_id: str):
        metadata = _InputMetadata.from_request()
        if self._input_file_exists(input_id):
            if metadata.has_all_args():
                # The reason to do this is that, if there's a blob that
                # changed timestamp but not hash (because of a `touch`, for
                # instance), the timestamp check will always return false and
                # the tarball will be constructed all the times on the client
                # side. It happened.
                self._store_input_id(metadata, input_id)
            return jsonify({
                'id': input_id,
            })
        else:
            abort(requests.codes.not_found)

    def prepare_input_stream(self, execution_spec: dict):
        input_id: Optional[str] = execution_spec.get('input_id')
        if not input_id:
            return None
        try:
            input_file_path = self.input_file(input_id)
            return open(input_file_path, 'rb')
        except FileNotFoundError:
            abort(requests.codes.bad_request, 'Invalid input ID.')

    def input_file(self, input_id: str):
        if not re.match(r'^\w{64}$', input_id):
            abort(requests.codes.bad_request, 'Invalid input ID.')
        input_file_path = os.path.join(self.input_dir, input_id)
        return input_file_path

    def _store_input_id(
            self, metadata: '_InputMetadata', input_id: str) -> None:
        field = metadata.redis_field()
        self.redis.hset(_INPUT_ID_KEY, field, input_id)
        log.debug(field + ': ' +
                  str(self.get_input_id_from_metadata_or_none(metadata)))

    def _input_file_exists(self, input_id: str) -> bool:
        return os.path.exists(self.input_file(input_id))


class _InputMetadata:
    def __init__(self):
        self.user: Optional[str] = None
        self.project: Optional[str] = None
        self.path: Optional[str] = None
        self.timestamp_millis: Optional[int] = None

    @staticmethod
    def from_request() -> '_InputMetadata':
        metadata: _InputMetadata = _InputMetadata()
        metadata.user = request.args.get('user', default=None, type=str)
        metadata.project = request.args.get(
            'project', default=None, type=str)
        metadata.path = request.args.get(
            'path', default=None, type=str)
        metadata.timestamp_millis = request.args.get(
            'timestamp_millis', default=None, type=str)
        if not metadata._has_all_args_or_none():
            abort(request.codes.bad_request)
        return metadata

    def has_all_args(self) -> bool:
        return all(self.__dict__.values())

    def _has_all_args_or_none(self) -> bool:
        return self.has_all_args() or not any(self.__dict__.values())

    def redis_field(self) -> str:
        return (f'{self.user}#{self.project}#{self.path}'
                f'#{self.timestamp_millis}')
