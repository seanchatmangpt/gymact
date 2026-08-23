from gymact.explore_ack_storage import StorageKind, candidates, select


def test_storage_alternatives_preserved_before_selection():
    assert [candidate.kind for candidate in candidates()] == [
        StorageKind.MEMORY,
        StorageKind.JSONL,
        StorageKind.SQLITE,
    ]
    assert select(True, True).kind is StorageKind.SQLITE
