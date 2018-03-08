import io
import os.path
import tarfile
import tempfile
from abc import ABC, abstractmethod
from typing import Iterator, List

import docker
import docker.errors
from docker.models.volumes import Volume
from docker.types import Mount


class VolumeObject(ABC):
    @abstractmethod
    def add_to(self, tar: tarfile.TarFile):
        pass


class VolumeFile(VolumeObject):
    def __init__(self, path: str, contents: str):
        self.path = path
        self.contents: bytes = contents.encode('utf-8')

    def add_to(self, tar: tarfile.TarFile):
        tarinfo = tarfile.TarInfo(name=self.path)
        tarinfo.size = len(self.contents)
        tar.addfile(tarinfo, fileobj=io.BytesIO(self.contents))


class VolumeDirectory(VolumeObject):
    def __init__(self, path: str):
        self.path = path

    def add_to(self, tar: tarfile.TarFile):
        tarinfo = tarfile.TarInfo(name=self.path)
        tarinfo.type = tarfile.DIRTYPE
        tar.addfile(tarinfo)


class Volumes:
    VOLUME_MOUNT = '/batman'
    CONFIGURATION_FILE = 'configuration.json'
    CONFIGURATION_FILE_PATH = os.path.join(VOLUME_MOUNT, CONFIGURATION_FILE)
    OUTPUT_DIRECTORY = 'output'
    OUTPUT_DIRECTORY_PATH = os.path.join(VOLUME_MOUNT, OUTPUT_DIRECTORY)

    # `cat` will wait around indefinitely until it gets a SIGTERM.
    # That's all we need, because we're only creating containers to get access
    # to the volumes.
    WAIT_COMMAND = ['cat']

    @staticmethod
    def for_host(docker_url):
        docker_client = docker.DockerClient(base_url=docker_url)
        return Volumes(docker_client)

    def __init__(self, docker_client: docker.DockerClient):
        self.docker_client = docker_client

    def create(self, name: str, objects: List[VolumeObject]) -> Volume:
        with tempfile.NamedTemporaryFile() as f:
            with tarfile.open(f.name, mode='w') as tar:
                for volume_object in objects:
                    volume_object.add_to(tar)
            f.seek(0)
            tarball = f.read()

        volume = self.docker_client.volumes.create(name)
        container = self.docker_client.containers.run(
            image='busybox',
            command=self.WAIT_COMMAND,
            mounts=[Mount(source=volume.name, target='/output')],
            detach=True)
        container.put_archive('/output', tarball)
        container.stop()
        container.remove()
        return volume

    def extract(self, volume_name: str, path: str) -> Iterator[bytes]:
        container = self.docker_client.containers.run(
            image='busybox',
            command=self.WAIT_COMMAND,
            mounts=[Mount(source=volume_name, target='/input')],
            detach=True)
        tar, _ = container.get_archive(os.path.join('/input', path))
        yield from tar
        container.stop()
        container.remove()

    def remove(self, name: str):
        try:
            volume = self.docker_client.volumes.get(name)
            volume.remove()
        except docker.errors.NotFound:
            pass