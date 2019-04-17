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

DOCKERFILE_NAME = 'plz.Dockerfile'


def capture_build_context(image: str, image_extensions: [str], command: [str],
                          context_path: [str], excluded_paths: [str],
                          included_paths: [str],
                          exclude_gitignored_files) -> BinaryIO:
    dockerfile_path = os.path.join(context_path, DOCKERFILE_NAME)
    dockerfile_created = False
    try:
        if not os.path.isfile(dockerfile_path):
            with open(dockerfile_path, mode='x') as dockerfile:
                dockerfile_created = True
                dockerfile.write(f'FROM {image}\n')
                for step in image_extensions:
                    dockerfile.write(step)
                    dockerfile.write('\n')
                dockerfile.write(f'WORKDIR /src\n'
                                 f'COPY . ./\n'
                                 f'CMD {json.dumps(command)}\n')
            os.chmod(dockerfile_path, 0o644)
        included_files, _ = get_included_and_excluded_files(
            context_path=context_path,
            excluded_paths=excluded_paths,
            included_paths=included_paths + [DOCKERFILE_NAME],
            exclude_gitignored_files=exclude_gitignored_files)
        build_context = docker.utils.build.create_archive(
            root=os.path.abspath(context_path),
            files=included_files,
            gzip=True)
    finally:
        if dockerfile_created:
            os.remove(dockerfile_path)
    return build_context


def get_included_and_excluded_files(context_path: [str], excluded_paths: [str],
                                    included_paths: [str],
                                    exclude_gitignored_files: bool
                                    ) -> ({str}, {str}):
    def abs_path_glob_including_snapshot(p):
        return glob2.iglob(os.path.abspath(os.path.join(context_path, p)),
                           recursive=True,
                           include_hidden=True)

    included_paths = {
        tuple(ip.split(os.sep))
        for p in included_paths for ip in abs_path_glob_including_snapshot(p)
    }

    excluded_paths = {
        tuple(ip.split(os.sep))
        for p in excluded_paths for ip in abs_path_glob_including_snapshot(p)
    }

    # Add the git ignored files if specified in the config
    # A value of None for exclude_gitignored_files means "exclude if git is
    # available"
    use_git = exclude_gitignored_files or (exclude_gitignored_files is None
                                           and is_git_present(context_path))
    if use_git:
        excluded_paths.update(get_ignored_git_files(context_path))
        excluded_paths.add(abs_path_glob_including_snapshot('.git'))

    def strip_context_path(f):
        return f[len(os.path.abspath(context_path)) + len(os.sep):]

    context_files = abs_path_glob_including_snapshot('**')
    included_files = set()
    excluded_files = set()
    for f in context_files:
        f_split = tuple(f.split(os.sep))
        f_prefixes = {
            f_split[0:i + 1]
            for i in range(0, len(f_split))
        }
        # A file matches a excluded path if one of it prefixes is a excluded
        # path. Same for included
        if len(f_prefixes.intersection(excluded_paths)) and (not len(
                f_prefixes.intersection(included_paths))):
            excluded_files.add(strip_context_path(f))
        else:
            included_files.add(strip_context_path(f))
    return included_files, excluded_files


def submit_context_for_building(user: str, project: str,
                                controller: Controller,
                                build_context: BinaryIO,
                                quiet_build: bool) -> str:
    metadata = {
        'user': user,
        'project': project,
    }
    status_json_strings = controller.create_snapshot(metadata, build_context)
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
