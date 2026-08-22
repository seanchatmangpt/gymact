from dataclasses import dataclass
from pathlib import PurePosixPath

from .subject import Refusal

@dataclass(frozen=True, order=True)
class TestModule:
    path: str

    def __post_init__(self) -> None:
        p = PurePosixPath(self.path)
        if p.is_absolute() or ".." in p.parts or p.suffix != ".py" or not p.name.startswith("test_"):
            raise Refusal("REFUSED_INVALID_TEST_MODULE")
        object.__setattr__(self, "path", p.as_posix())

    @property
    def basename(self) -> str:
        return PurePosixPath(self.path).name

    @property
    def parent(self) -> str:
        return PurePosixPath(self.path).parent.as_posix()
