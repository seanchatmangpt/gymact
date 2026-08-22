from dataclasses import dataclass


@dataclass(frozen=True)
class Difference:
    path: str
    left: object
    right: object


def compare(left: object, right: object, path: str = "$") -> tuple[Difference, ...]:
    if type(left) is not type(right):
        return (Difference(path, left, right),)
    if isinstance(left, dict):
        diffs = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                diffs.append(Difference(f"{path}.{key}", left.get(key), right.get(key)))
            else:
                diffs.extend(compare(left[key], right[key], f"{path}.{key}"))
        return tuple(diffs)
    if isinstance(left, (list, tuple)):
        if len(left) != len(right):
            return (Difference(path + ".length", len(left), len(right)),)
        diffs = []
        for index, (a, b) in enumerate(zip(left, right, strict=True)):
            diffs.extend(compare(a, b, f"{path}[{index}]"))
        return tuple(diffs)
    return () if left == right else (Difference(path, left, right),)
