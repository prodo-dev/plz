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

    _DUMMY_IMAGE_NAME = 'busybox'

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
        container = self.docker_client.containers.create(
            image=self._dummy_image(),
            mounts=[Mount(source=volume.name, target='/output')])
        container.put_archive('/output', tarball)
        container.remove()
        return volume

    def get_files(self, volume_name: str, path: str) -> Iterator[bytes]:
        container = self.docker_client.containers.create(
            image=self._dummy_image(),
            mounts=[Mount(source=volume_name, target='/input')])
        tar, _ = container.get_archive(os.path.join('/input', path))
        yield from tar
        container.remove()

    def remove(self, name: str):
        try:
            volume = self.docker_client.volumes.get(name)
            volume.remove()
        except docker.errors.NotFound:
            pass

    def _dummy_image(self):
        try:
            self.docker_client.images.get(self._DUMMY_IMAGE_NAME)
        except docker.errors.NotFound:
            self.docker_client.images.pull(self._DUMMY_IMAGE_NAME, 'latest')
        return self._DUMMY_IMAGE_NAME
