import itertools
import json
import os
from typing import BinaryIO

import docker.utils
import glob2

from plz.cli.exceptions import CLIException
from plz.cli.git import get_ignored_git_files, is_git_present
from plz.cli.log import log_error
from plz.controller.api import Controller


def capture_build_context(
        image: str, image_extensions: [str], command: str,
        context_path: [str],
        excluded_paths: [str], included_paths: [str],
        exclude_gitignored_files) -> BinaryIO:
    dockerfile_path = os.path.join(context_path, 'plz.Dockerfile')
    dockerfile_created = False
    try:
        with open(dockerfile_path, mode='x') as dockerfile:
            dockerfile_created = True
            dockerfile.write(f'FROM {image}\n')
            for step in image_extensions:
                dockerfile.write(step)
                dockerfile.write('\n')
            dockerfile.write(
                f'WORKDIR /src\n'
                f'COPY . ./\n'
                f'CMD {command}\n'
            )
        os.chmod(dockerfile_path, 0o644)
        matching_excluded_paths = get_matching_excluded_paths(
            context_path=context_path, excluded_paths=excluded_paths,
            included_paths=included_paths,
            exclude_gitignored_files=exclude_gitignored_files)
        build_context = docker.utils.build.tar(
            path=context_path,
            exclude=matching_excluded_paths,
            gzip=True,
        )
    except FileExistsError as e:
        raise CLIException(
            'The directory cannot have a plz.Dockerfile.') from e
    finally:
        if dockerfile_created:
            os.remove(dockerfile_path)
    return build_context


def get_matching_excluded_paths(
        context_path: [str], excluded_paths: [str], included_paths: [str],
        exclude_gitignored_files: bool) -> [str]:
    def abs_path_glob_including_snapshot(p):
        return os.path.abspath(os.path.join(context_path, p))

    def expand_if_dir(path):
        if os.path.isdir(path):
            # Return the dir as well as the files inside
            return itertools.chain(
                iter([path]),
                glob2.iglob(
                    os.path.join(path, '**'), recursive=True,
                    include_hidden=True))
        else:
            return iter([path])

    included_paths = set(
        ip
        for p in included_paths
        for ip in glob2.iglob(abs_path_glob_including_snapshot(p),
                              recursive=True,
                              include_hidden=True))
    # Get the files inside the directories
    included_paths = set(p for ip in included_paths for p in expand_if_dir(ip))

    all_included_prefixes = set(
        os.sep.join(ip.split(os.sep)[:n+1])
        for ip in included_paths
        for n in range(len(ip.split(os.sep))))

    # Expand the globs
    excluded_paths = [ep for p in excluded_paths
                      for ep in glob2.iglob(
                          abs_path_glob_including_snapshot(p),
                          recursive=True,
                          include_hidden=True)]

    # Add the git ignored files
    git_ignored_files = []
    # A value of None for exclude_gitignored_files means "exclude if git is
    # available"
    use_git = exclude_gitignored_files or (
            exclude_gitignored_files is None and is_git_present(context_path))
    if use_git:
        git_ignored_files = [abs_path_glob_including_snapshot('.git')] + \
                            get_ignored_git_files(context_path)
    excluded_paths += git_ignored_files

    excluded_and_not_included_paths = []
    for ep in excluded_paths:
        if ep in all_included_prefixes:
            excluded_and_not_included_paths += (
                p for p in expand_if_dir(ep) if p not in all_included_prefixes
            )
        else:
            excluded_and_not_included_paths.append(ep)

    return [p[len(os.path.abspath(context_path)) + 1:]
            for p in excluded_and_not_included_paths]


def get_context_files(context_path: str, matching_excluded_paths: [str]):
    # Mimic what docker.utils.build.tar does
    return docker.utils.build.exclude_paths(
        os.path.abspath(context_path),
        matching_excluded_paths)


def submit_context_for_building(
        user: str,
        project: str,
        controller: Controller,
        build_context: BinaryIO,
        quiet_build: bool) -> str:
    metadata = {
        'user': user,
        'project': project,
    }
    status_json_strings = controller.create_snapshot(
        metadata, build_context)
    errors = []
    snapshot_id: str = None
    for json_str in status_json_strings:
        data = json.loads(json_str)
        if 'stream' in data:
            if not quiet_build:
                print(data['stream'], end='', flush=True)
        if 'error' in data:
            errors.append(data['error'].rstrip())
        if 'id' in data:
            snapshot_id = data['id']
    if errors or not snapshot_id:
        log_error('The snapshot was not successfully created.')
        pull_access_denied = False
        for error in errors:
            if error.startswith('pull access denied'):
                pull_access_denied = True
            print(error)
        exc_message = 'We did not receive a snapshot ID.'
        if pull_access_denied:
            raise CLIException(exc_message) \
                from PullAccessDeniedException()
        else:
            raise CLIException(exc_message)
    return snapshot_id


class PullAccessDeniedException(Exception):
    pass
