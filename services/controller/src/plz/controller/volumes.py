import io
import os.path
import tarfile
import tempfile
from abc import ABC, abstractmethod
from typing import List

import docker
import docker.errors
from docker.models.containers import Container
from docker.models.volumes import Volume
from docker.types import Mount


class VolumeObject(ABC):
    @abstractmethod
    def put_in(self, container: Container, root: str):
        pass


class VolumeFile(VolumeObject):
    def __init__(self, path: str, contents: str):
        self.path = path
        self.contents: bytes = contents.encode('utf-8')

    def put_in(self, container: Container, root: str):
        with tempfile.NamedTemporaryFile() as f:
            with tarfile.open(f.name, mode='w') as tar:
                tarinfo = tarfile.TarInfo(name=self.path)
                tarinfo.size = len(self.contents)
                tar.addfile(tarinfo, fileobj=io.BytesIO(self.contents))
            f.seek(0)
            container.put_archive(root, f)


class VolumeEmptyDirectory(VolumeObject):
    def __init__(self, path: str):
        self.path = path

    def put_in(self, container: Container, root: str):
        with tempfile.NamedTemporaryFile() as f:
            with tarfile.open(f.name, mode='w') as tar:
                tarinfo = tarfile.TarInfo(name=self.path)
                tarinfo.type = tarfile.DIRTYPE
                tar.addfile(tarinfo)
            f.seek(0)
            container.put_archive(root, f)


class VolumeDirectory(VolumeObject):
    def __init__(self, path: str, contents_tarball: io.IOBase):
        self.path = path
        self.contents_tarball = contents_tarball

    def put_in(self, container: Container, root: str):
        full_path = os.path.join(root, self.path)
        exit_code, output = container.exec_run(['mkdir', full_path])
        if exit_code > 0:
            raise VolumeCreationError(output.decode('utf-8'))
        # noinspection PyTypeChecker
        # (the tarball can be an `IOBase` too,
        #  but the docker-py documentation says it must be `bytes`)
        container.put_archive(full_path, self.contents_tarball)


class Volumes:
    VOLUME_MOUNT = '/plz'
    CONFIGURATION_FILE = 'configuration.json'
    CONFIGURATION_FILE_PATH = os.path.join(VOLUME_MOUNT, CONFIGURATION_FILE)
    INPUT_DIRECTORY = 'input'
    INPUT_DIRECTORY_PATH = os.path.join(VOLUME_MOUNT, INPUT_DIRECTORY)
    OUTPUT_DIRECTORY = 'output'
    OUTPUT_DIRECTORY_PATH = os.path.join(VOLUME_MOUNT, OUTPUT_DIRECTORY)
    MEASURES_DIRECTORY = 'measures'
    MEASURES_DIRECTORY_PATH = os.path.join(VOLUME_MOUNT, MEASURES_DIRECTORY)

    @staticmethod
    def for_host(docker_url):
        docker_client = docker.DockerClient(base_url=docker_url)
        return Volumes(docker_client)

    def __init__(self, docker_client: docker.DockerClient):
        self.docker_client = docker_client

    def create(self, name: str, objects: List[VolumeObject]) -> Volume:
        root = '/output'
        volume = self.docker_client.volumes.create(name)
        container = self.docker_client.containers.run(
            image=self._busybox_image(),
            command=['cat'],  # wait forever
            mounts=[Mount(source=volume.name, target=root)],
            stdin_open=True,
            remove=True,
            detach=True)
        try:
            for volume_object in objects:
                volume_object.put_in(container, root)
        finally:
            container.kill()
        return volume

    def remove(self, name: str):
        try:
            volume = self.docker_client.volumes.get(name)
            volume.remove()
        except docker.errors.NotFound:
            pass

    def _busybox_image(self):
        try:
            self.docker_client.images.get('busybox')
        except docker.errors.NotFound:
            self.docker_client.images.pull('busybox', 'latest')
        return 'busybox'


class VolumeCreationError(Exception):
    pass
