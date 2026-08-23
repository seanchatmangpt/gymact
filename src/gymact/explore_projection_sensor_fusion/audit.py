import hashlib


def audit_root(digests: tuple[str, ...]) -> str:
    leaves = sorted(bytes.fromhex(digest) for digest in digests)
    if not leaves:
        return hashlib.sha256(b"").hexdigest()
    nodes = [hashlib.sha256(b"leaf:" + leaf).digest() for leaf in leaves]
    while len(nodes) > 1:
        if len(nodes) % 2:
            nodes.append(nodes[-1])
        nodes = [
            hashlib.sha256(b"node:" + nodes[index] + nodes[index + 1]).digest()
            for index in range(0, len(nodes), 2)
        ]
    return nodes[0].hex()
