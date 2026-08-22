from __future__ import annotations

from collections.abc import Mapping, Sequence


def diff(left: object, right: object, path: str = "$" ) -> tuple[str, ...]:
    if type(left) is not type(right):
        return (f"{path}:type",)
    if isinstance(left, Mapping):
        paths: list[str] = []
        keys = sorted(set(left) | set(right))
        for key in keys:
            if key not in left or key not in right:
                paths.append(f"{path}.{key}:missing")
            else:
                paths.extend(diff(left[key], right[key], f"{path}.{key}"))
        return tuple(paths)
    if isinstance(left, Sequence) and not isinstance(left, (str, bytes, bytearray)):
        if len(left) != len(right):
            return (f"{path}:length",)
        paths: list[str] = []
        for index, (l_value, r_value) in enumerate(zip(left, right, strict=True)):
            paths.extend(diff(l_value, r_value, f"{path}[{index}]"))
        return tuple(paths)
    return () if left == right else (path,)
