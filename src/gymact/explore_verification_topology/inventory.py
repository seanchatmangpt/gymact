from dataclasses import dataclass
from .module_identity import TestModule
from .subject import Refusal

@dataclass(frozen=True)
class ModuleInventory:
    modules: tuple[TestModule, ...]

    @classmethod
    def admit(cls, modules: list[TestModule] | tuple[TestModule, ...]) -> "ModuleInventory":
        ordered = tuple(sorted(modules))
        if len({m.path for m in ordered}) != len(ordered):
            raise Refusal("REFUSED_DUPLICATE_TEST_PATH")
        return cls(ordered)

    def paths(self) -> tuple[str, ...]:
        return tuple(m.path for m in self.modules)
