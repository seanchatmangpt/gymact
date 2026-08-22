from dataclasses import dataclass
import json

class MemoryStore:
    def __init__(self): self.rows: list[dict] = []
    def append(self, row: dict) -> None: self.rows.append(dict(row))
    def read(self) -> tuple[dict, ...]: return tuple(dict(r) for r in self.rows)

@dataclass
class JsonlStore:
    path: str
    def append(self, row: dict) -> None:
        with open(self.path, "a", encoding="utf-8") as f: f.write(json.dumps(row, sort_keys=True) + "\n")
    def read(self) -> tuple[dict, ...]:
        with open(self.path, encoding="utf-8") as f: return tuple(json.loads(line) for line in f if line.strip())
