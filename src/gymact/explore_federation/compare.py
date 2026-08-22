def compare(left, right, path: str = "$") -> tuple[str, ...]:
    if type(left) is not type(right):
        return (path,)
    if isinstance(left, dict):
        differences = []
        for key in sorted(set(left) | set(right)):
            differences.extend(compare(left.get(key), right.get(key), f"{path}.{key}"))
        return tuple(differences)
    if isinstance(left, (list, tuple)):
        differences = []
        for index in range(max(len(left), len(right))):
            left_value = left[index] if index < len(left) else object()
            right_value = right[index] if index < len(right) else object()
            differences.extend(compare(left_value, right_value, f"{path}[{index}]"))
        return tuple(differences)
    return () if left == right else (path,)
