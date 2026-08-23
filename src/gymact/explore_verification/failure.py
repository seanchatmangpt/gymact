def inject(name: str, fail: set[str]):
    return "FAIL" if name in fail else "PASS"
