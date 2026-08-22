from __future__ import annotations

from collections.abc import Mapping, Sequence


def differential(left: object, right: object, path: str = "$") -> tuple[str, ...]:
    differences: list[str] = []
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        keys = sorted(set(left) | set(right))
        for key in keys:
            if key not in left or key not in right:
                differences.append(f"{path}.{key}")
            else:
                differences.extend(differential(left[key], right[key], f"{path}.{key}"))
        return tuple(differences)
    if isinstance(left, Sequence) and isinstance(right, Sequence) and not isinstance(left, (str, bytes)):
        if len(left) != len(right):
            differences.append(f"{path}.length")
        for index, (a, b) in enumerate(zip(left, right)):
            differences.extend(differential(a, b, f"{path}[{index}]"))
        return tuple(differences)
    if left != right:
        differences.append(path)
    return tuple(differences)
