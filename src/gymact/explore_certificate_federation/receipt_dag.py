from dataclasses import dataclass
import hashlib

from .refusal import FederationRefusal


@dataclass(frozen=True)
class ReceiptNode:
    node_id: str
    digest: str
    parents: tuple[str, ...] = ()


def dag_root(nodes: tuple[ReceiptNode, ...]) -> str:
    by_id = {node.node_id: node for node in nodes}
    if len(by_id) != len(nodes) or not nodes:
        raise FederationRefusal("INVALID_RECEIPT_DAG")
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id not in by_id:
            raise FederationRefusal("MISSING_RECEIPT_PARENT")
        if node_id in visiting:
            raise FederationRefusal("CYCLIC_RECEIPT_DAG")
        if node_id in done:
            return
        visiting.add(node_id)
        for parent in by_id[node_id].parents:
            visit(parent)
        visiting.remove(node_id)
        done.add(node_id)

    for node_id in sorted(by_id):
        visit(node_id)
    payload = "|".join(f"{node.node_id}:{node.digest}:{','.join(sorted(node.parents))}" for node in sorted(nodes, key=lambda n: n.node_id))
    return hashlib.sha256(payload.encode()).hexdigest()
