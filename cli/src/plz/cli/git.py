import os
import subprocess
from typing import Optional

import glob2

from plz.cli.exceptions import CLIException


def get_head_commit_or_none(context_path: str) -> Optional[str]:
    if is_git_present(context_path):
        return _get_head_commit(context_path)
    else:
        return None


def get_ignored_git_files(context_path: str) -> [str]:
    all_files = os.linesep.join(
        glob2.iglob(
            os.path.join(context_path,
                         '**'),
            recursive=True,
            include_hidden=True))
    # Using --no-index, so that .gitignored but indexed files need to be
    # included explicitly.
    result = subprocess.run(
        ['git',
         '-C',
         context_path,
         'check-ignore',
         '--stdin',
         '--no-index'],
        input=all_files,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8')
    return_code = result.returncode
    # When there are no ignored files it returns with exit code 1
    correct_return_code = return_code == 0 or (
        return_code == 1 and result.stdout == '')
    if not correct_return_code or result.stderr != '':
        raise SystemError(
            'Cannot list files from git.\n'
            f'Return code is: {result.returncode}\n'
            f'Stderr: [{result.stderr}]')
    return [os.path.abspath(p) for p in result.stdout.splitlines()]


def is_git_present(context_path: str) -> bool:
    # noinspection PyBroadException
    try:
        result = subprocess.run(
            ['git',
             '-C',
             context_path,
             'rev-parse',
             '--show-toplevel'],
            input=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8')
        return result.returncode == 0 and result.stderr == '' and \
            len(result.stdout) > 0
    except Exception:
        return False


def _get_head_commit(context_path: str) -> Optional[str]:
    if not _is_there_a_head_commit(context_path):
        return None
    result = subprocess.run(
        ['git',
         '-C',
         context_path,
         'rev-parse',
         'HEAD'],
        input=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8')
    commit = result.stdout.strip()
    if result.returncode != 0 or result.stderr != '' or len(commit) == 0:
        raise CLIException(
            'Couldn\'t get HEAD commit. \n'
            f'Return code: {result.returncode}. \n'
            f'Stdout: {result.stdout}. \n'
            f'Stderr: [{result.stderr}]. \n')
    return commit


def _is_there_a_head_commit(context_path: str) -> bool:
    # We could be doing `git rev-list -n 1 --all`, and check that the output
    # is non-empty, but Ubuntu ships with ridiculous versions of git
    result = subprocess.run(
        ['git',
         '-C',
         context_path,
         'show-ref',
         '--head'],
        input=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8')
    if result.returncode not in {0, 1} or result.stderr != '':
        raise CLIException(
            'Error finding if there are commits. \n'
            f'Return code: {result.returncode}. \n'
            f'Stdout: {result.stdout}. \n'
            f'Stderr: [{result.stderr}]. \n')
    return result.returncode == 0 and ' HEAD\n' in result.stdout
