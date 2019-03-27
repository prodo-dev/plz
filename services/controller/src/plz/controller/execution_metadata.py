import base64
import io
import json
import os
import shutil
import tarfile
import tempfile
from copy import deepcopy
from json import JSONDecodeError
from typing import IO, Iterator, Optional, Tuple

from werkzeug.contrib.iterio import IterIO


def convert_measures_to_dict(measures_tarball: Iterator[bytes]) -> dict:
    measures_dict = {}
    for path, file_content in _tar_iterator(measures_tarball):

        content = file_content.read()
        content_as_json = None
        try:
            content_as_json = json.load(io.BytesIO(content))
        except JSONDecodeError or UnicodeDecodeError:
            pass
        # Treat directories as nested dictionaries
        obj, key = _container_object_and_key_from_path(measures_dict, path)
        if content_as_json is not None:
            obj[key] = content_as_json
        else:
            obj[key] = {
                'base64_bytes': base64.encodebytes(content).decode('ascii')
            }
    return measures_dict


def _container_object_and_key_from_path(measures_dict: dict, path: str):
    fragments = [f for f in path.split(os.path.sep) if f]
    obj = measures_dict
    for f in fragments[:-1]:
        if f not in obj:
            obj[f] = {}
        obj = obj[f]
    return obj, fragments[-1]


def compile_metadata_for_storage(
        start_metadata: dict,
        finish_timestamp: int) -> dict:
    # This function doesn't do much for now, but having it is a way to
    # document that what we store as metadata is the start metadata plus
    # other stuff
    return {**start_metadata,
            'finish_timestamp': finish_timestamp}


def _tar_iterator(tarball_bytes: Iterator[bytes]) \
        -> Iterator[Tuple[str, Optional[IO]]]:
    # The response is a tarball we need to extract into `output_dir`.
    with tempfile.TemporaryFile() as tarball:
        # `tarfile.open` needs to read from a real file, so we copy to one.
        shutil.copyfileobj(IterIO(tarball_bytes), tarball)
        # And rewind to the start.
        tarball.seek(0)
        tar = tarfile.open(fileobj=tarball)
        for tarinfo in tar.getmembers():
            # Drop the first segment, because it's just the name of the
            # directory that was tarred up, and we don't care.
            path_segments = tarinfo.name.split(os.sep)[1:]
            if path_segments:
                # Unfortunately we can't just pass `*path_segments`
                # because `os.path.join` explicitly expects an argument
                # for the first parameter.
                path = os.path.join(path_segments[0], *path_segments[1:])
                file_bytes = tar.extractfile(tarinfo.name)
                # Not None for files and links
                if file_bytes is not None:
                    yield path, tar.extractfile(tarinfo.name)


def enrich_start_metadata(
        execution_id: str,
        start_metadata: dict, snapshot_id: str, parameters: dict,
        instance_market_spec: dict, execution_spec: dict,
        parallel_indices_range: Optional[Tuple[int, int]],
        index_range_to_run: Optional[Tuple[int, int]],
        indices_per_execution: Optional[int],
        previous_execution_id: Optional[str]) -> dict:
    enriched_start_metadata = deepcopy(start_metadata)
    enriched_start_metadata['execution_id'] = execution_id
    enriched_start_metadata['snapshot_id'] = snapshot_id
    enriched_start_metadata['parameters'] = parameters
    enriched_start_metadata['instance_market_spec'] = instance_market_spec
    enriched_start_metadata['execution_spec'] = {
        k: v for k, v in execution_spec.items()
        if k not in {'user', 'project'}}
    enriched_start_metadata['execution_spec']['index_range_to_run'] = \
        index_range_to_run
    enriched_start_metadata['user'] = execution_spec['user']
    enriched_start_metadata['project'] = execution_spec['project']
    enriched_start_metadata['parallel_indices_range'] = parallel_indices_range
    enriched_start_metadata['indices_per_execution'] = indices_per_execution
    enriched_start_metadata['previous_execution_id'] = previous_execution_id
    return enriched_start_metadata


def is_atomic(start_metadata: dict) -> bool:
    return start_metadata.get('parallel_indices_range', None) is None
