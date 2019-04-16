from typing import BinaryIO, Callable, Iterator

import docker

from plz.controller.images.images_base import Images


class LocalImages(Images):
    def __init__(self,
                 docker_api_client_creator: Callable[[], docker.APIClient],
                 repository: str):
        super().__init__(docker_api_client_creator, repository)

    def build(self, fileobj: BinaryIO, tag: str) -> Iterator[bytes]:
        return self._build(fileobj, tag)

    def for_host(self, docker_url: str) -> 'LocalImages':
        def new_docker_api_client_creator():
            return docker.APIClient(base_url=docker_url)

        return LocalImages(new_docker_api_client_creator, self.repository)

    def push(self, tag: str):
        pass

    def pull(self, tag: str):
        pass

    def can_pull(self, _) -> bool:
        return True
