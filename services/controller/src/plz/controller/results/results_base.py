import io
import os
import shutil
import tarfile
import tempfile
from abc import ABC, abstractmethod
from typing import Iterator


class ResultsStorage(ABC):
    @abstractmethod
    def publish(self,
                execution_id: str,
                exit_status: int,
                logs: Iterator[bytes],
                output_tarball: Iterator[bytes]):
        pass


# This is duplicated in the CLI. We need a place for common code.
def untar(stream: Iterator[bytes], output_dir: str) -> Iterator[str]:
    # The response is a tarball we need to extract into `output_dir`.
    with tempfile.TemporaryFile() as tarball:
        # `tarfile.open` needs to read from a real file, so we copy to one.
        for chunk in stream:
            tarball.write(chunk)
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
                # Just because it's nice, yield the file to be extracted.
                yield path
                source: io.BufferedReader = tar.extractfile(tarinfo.name)
                if source:
                    # Finally, write the file.
                    absolute_path = os.path.join(output_dir, path)
                    os.makedirs(os.path.dirname(absolute_path),
                                exist_ok=True)
                    with open(absolute_path, 'wb') as dest:
                        shutil.copyfileobj(source, dest)
