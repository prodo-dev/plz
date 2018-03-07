import io
import os.path
import tarfile
import tempfile
from typing import Dict

import docker
import docker.errors
from docker.models.volumes import Volume
from docker.types import Mount


class VolumeFile:
    def __init__(self, contents):
        self.contents: bytes = contents.encode('utf-8')


class Volumes:
    VOLUME_MOUNT = '/batman'
    CONFIGURATION_FILE_PATH = os.path.join(VOLUME_MOUNT, 'configuration.json')

    @staticmethod
    def for_host(docker_url):
        docker_client = docker.DockerClient(base_url=docker_url)
        return Volumes(docker_client)

    def __init__(self, docker_client: docker.DockerClient):
        self.docker_client = docker_client

    def create(self, name: str, files: Dict[str, VolumeFile]) -> Volume:
        with tempfile.NamedTemporaryFile() as f:
            with tarfile.open(f.name, mode='w') as tar:
                for filepath, volume_file in files.items():
                    tarinfo = tarfile.TarInfo(name=filepath)
                    tarinfo.size = len(volume_file.contents)
                    tar.addfile(tarinfo=tarinfo,
                                fileobj=io.BytesIO(volume_file.contents))
            f.seek(0)
            tarball = f.read()

        volume = self.docker_client.volumes.create(name)
        container = self.docker_client.containers.run(
            image='busybox',
            command=f'sleep 600 & PID=$!; trap "kill $PID" TERM',
            mounts=[Mount(source=volume.name, target='/output')],
            detach=True)
        container.put_archive('/output', tarball)
        container.stop()
        container.remove()
        return volume

    def remove(self, name: str):
        try:
            volume = self.docker_client.volumes.get(name + 'x')
            volume.remove()
        except docker.errors.NotFound:
            pass
