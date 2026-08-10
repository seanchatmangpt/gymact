from __future__ import annotations

import pytest
from rdflib import RDF, URIRef
from rdflib.namespace import DCTERMS, PROV

from gymact.evidence import MemoryReceiptLedger, digest, evidence_graph
from gymact.models import Operation, Receipt, Standing


def test_public_prov_graph_contains_selection_graph_path_and_morphism_lineage() -> None:
    ledger = MemoryReceiptLedger()
    receipt = Receipt(
        receipt_id="r1",
        episode_id="episode",
        operation=Operation.VERIFY,
        standing=Standing.ALIVE,
        possibility_graph_digest="graph-digest",
        possibility_exploration_digest="exploration-digest",
        possibility_path_id="path-id",
        possibility_morphism_id="do-id",
        selection_digest="selection-digest",
        selection_basis_refs=("urn:evidence:benchmark",),
        verified=True,
    )
    ledger.append(receipt)
    graph = evidence_graph(ledger.records())

    receipt_ref = URIRef("urn:gymact:receipt:r1")
    selection_ref = URIRef("urn:gymact:selection:selection-digest")
    graph_ref = URIRef("urn:gymact:possibility-graph:graph-digest")
    morphism_ref = URIRef(f"urn:gymact:possibility-morphism:{digest('do-id')}")
    assert (selection_ref, RDF.type, PROV.Entity) in graph
    assert (receipt_ref, PROV.wasDerivedFrom, selection_ref) in graph
    assert (selection_ref, DCTERMS.references, graph_ref) in graph
    assert (selection_ref, DCTERMS.references, morphism_ref) in graph
    assert (selection_ref, PROV.wasDerivedFrom, URIRef("urn:evidence:benchmark")) in graph


def test_receipt_refuses_self_referential_parent() -> None:
    with pytest.raises(ValueError, match="PARENT_RECEIPT_SELF_REFERENCE"):
        Receipt(
            receipt_id="r1",
            episode_id="episode",
            operation=Operation.VERIFY,
            standing=Standing.ALIVE,
            parent_receipt_ids=("r1",),
        )


def test_receipt_refuses_duplicate_parent_ids() -> None:
    with pytest.raises(ValueError, match="PARENT_RECEIPT_IDS_DUPLICATE"):
        Receipt(
            receipt_id="r1",
            episode_id="episode",
            operation=Operation.VERIFY,
            standing=Standing.ALIVE,
            parent_receipt_ids=("p1", "p1"),
        )
