from typing import BinaryIO, Iterator

import docker

from plz.controller.images.images_base import Images


class LocalImages(Images):
    def __init__(self, docker_api_client: docker.APIClient, repository: str):
        super().__init__(repository)
        self.docker_api_client = docker_api_client

    def build(self, fileobj: BinaryIO, tag: str) -> Iterator[str]:
        """
        Builds an image from the tarball supplied as ``attr:fileobj``.

        We used to use `docker_api_client.build` to build the image, but it's
        much slower, with a minimum of 5 seconds to build anything under
        testing. Turns out that it takes _ages_ to figure out authentication
        for building/pulling, which sucks.

        At some point, let's send them a patch upstream. Until then, sending a
        request directly to Docker over HTTP works.
        """
        tag = f'{self.repository}:{tag}'
        return self.docker_api_client.post(
            self.docker_api_client.base_url + '/build',
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
