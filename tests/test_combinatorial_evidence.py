from __future__ import annotations

from rdflib import RDF, URIRef
from rdflib.namespace import DCTERMS, PROV

from gymact.evidence import MemoryReceiptLedger, evidence_graph
from gymact.models import Operation, Receipt, Standing


def test_public_prov_graph_contains_selection_graph_path_and_morphism_lineage() -> None:
    ledger = MemoryReceiptLedger()
    receipt = Receipt(
        receipt_id="r1",
        episode_id="episode",
        operation=Operation.VERIFY,
        standing=Standing.ALIVE,
        possibility_graph_digest="graph-digest",
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
    assert (selection_ref, RDF.type, PROV.Entity) in graph
    assert (receipt_ref, PROV.wasDerivedFrom, selection_ref) in graph
    assert (selection_ref, DCTERMS.references, graph_ref) in graph
    assert (selection_ref, PROV.wasDerivedFrom, URIRef("urn:evidence:benchmark")) in graph
