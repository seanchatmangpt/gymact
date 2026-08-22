def compare(left: dict[str, str], right: dict[str, str]):
    shared = sorted(set(left) & set(right))
    if not shared:
        return "UNKNOWN"
    if all(left[key] == right[key] for key in shared):
        return "COMPATIBLE"
    return "DIVERGED"
