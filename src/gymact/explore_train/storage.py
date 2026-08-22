import json
from dataclasses import dataclass


class MemoryStore:
    def __init__(self):
        self.rows: list[dict] = []

    def append(self, row: dict) -> None:
        self.rows.append(dict(row))

    def read(self) -> tuple[dict, ...]:
        return tuple(dict(row) for row in self.rows)


@dataclass
class JsonlStore:
    path: str

    def append(self, row: dict) -> None:
        with open(self.path, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")

    def read(self) -> tuple[dict, ...]:
        with open(self.path, encoding="utf-8") as stream:
            return tuple(json.loads(line) for line in stream if line.strip())
