import json


class MemoryStore:
    def __init__(self) -> None:
        self.rows = []

    def append(self, row: dict) -> None:
        self.rows.append(dict(row))

    def replay(self) -> tuple[dict, ...]:
        return tuple(dict(row) for row in self.rows)


def encode_jsonl(rows: list[dict]) -> str:
    return "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows
    )
