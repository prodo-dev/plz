from abc import abstractmethod
from typing import Optional

from plz.cli.operation import Operation


class CompositionOperation(Operation):
    def run_maybe_composite(self,
                            execution_id: Optional[str] = None,
                            composition_path: [(str, str)] = None):
        execution_id = self.get_execution_id() \
            if execution_id is None else execution_id
        composition_path = [] if composition_path is None else composition_path
        composition = self.controller.get_execution_composition(execution_id)
        if 'indices_to_compositions' in composition:
            for index, e_id in composition['indices_to_compositions'].items():
                self.run_maybe_composite(
                    execution_id=e_id,
                    composition_path=composition_path + [
                        ('parallel', index)])
        else:
            self.run_atomic(execution_id, composition_path)

    @abstractmethod
    def run_atomic(
            self, atomic_execution_id: str, composition_path: [(str, str)]):
        pass

    def run(self):
        self.run_maybe_composite(self.get_execution_id())


def create_path_string_prefix(composition_path: [(str, str)]):
    path_string_prefix = '-'.join(
        '-'.join(node for node in composition_path))
    if len(path_string_prefix) > 0:
        path_string_prefix += '#'
    return path_string_prefix
