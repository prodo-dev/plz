from abc import abstractmethod
from typing import Any, List, Optional

from plz.cli.operation import Operation


class CompositionOperation(Operation):
    def _run_composition(
            self, composition: dict, composition_path: [(str, Any)]):
        if 'indices_to_compositions' in composition:
            for index, c in composition['indices_to_compositions'].items():
                self._run_composition(
                    composition=c,
                    composition_path=composition_path + [('parallel', index)])
        else:
            self.run_atomic(composition['execution_id'], composition_path)

    @abstractmethod
    def run_atomic(
            self, atomic_execution_id: str, composition_path: [(str, Any)]):
        pass

    def run(self):
        composition = self.controller.get_execution_composition(
            self.get_execution_id())
        self._run_composition(composition, composition_path=[])


def create_path_string_prefix(composition_path: [(str, Any)]):
    path_string_prefix = ':'.join('-'.join(node) for node in composition_path)
    if len(path_string_prefix) > 0:
        path_string_prefix += '#'
    return path_string_prefix


def get_all_atomic(composition: dict,
                   _start: Optional[List[str]] = None) -> {str}:
    if _start is None:
        _start = set()
    if 'indices_to_compositions' in composition:
        for sub_comp in composition['indices_to_compositions'].values():
            get_all_atomic(sub_comp, _start)
    else:
        _start.add(composition['execution_id'])
    return _start
