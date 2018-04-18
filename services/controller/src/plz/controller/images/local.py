from typing import BinaryIO, Iterator

import docker
import docker.utils
import requests
import requests_unixsocket

from plz.controller.images.images_base import Images


class LocalImages(Images):
    def __init__(self,
                 docker_host: str,
                 docker_api_client: docker.APIClient,
                 repository: str):
        super().__init__(repository)
        if not docker_host:
            self.docker_host = 'http+unix://%2Fvar%2Frun%2Fdocker.sock'
        else:
            self.docker_host = docker.utils.parse_host(docker_host)
        self.docker_api_client = docker_api_client

    def build(self, fileobj: BinaryIO, tag: str) -> Iterator[str]:
        """
        Builds an image from the tarball supplied as ``attr:fileobj``.

        We used to use the Docker client to build the image, but for some
        reason it's much slower, with a minimum of 5 seconds to build anything
        under testing. Going direct seems to be much faster.
        """
        tag = f'{self.repository}:{tag}'
        with requests_unixsocket.monkeypatch():
            return requests.post(
                self.docker_host + '/build',
                params={
                    't': tag,
                },
                headers={
                    'Content-Type': 'application/tar',
                    'Content-Encoding': 'bz2',
                },
                data=fileobj,
            )

    def for_host(self, docker_url: str) -> 'LocalImages':
        new_docker_api_client = docker.APIClient(base_url=docker_url)
        return LocalImages(new_docker_api_client, self.repository)

    def push(self, tag: str):
        pass

    def pull(self, tag: str):
        pass

    def can_pull(self, _) -> bool:
        return True
