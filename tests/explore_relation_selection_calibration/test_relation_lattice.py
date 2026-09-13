from gymact.explore_relation_selection_calibration.relation import Relation, discharges, maximal


def test_relation_lattice_noncollapsed() -> None:
    assert discharges(Relation.EXACT, Relation.STUTTER)
    assert discharges(Relation.EXACT, Relation.PARTIAL_ORDER)
    assert discharges(Relation.STUTTER, Relation.ACTIVITY)
    assert discharges(Relation.PARTIAL_ORDER, Relation.ACTIVITY)
    assert not discharges(Relation.STUTTER, Relation.PARTIAL_ORDER)
    assert not discharges(Relation.PARTIAL_ORDER, Relation.STUTTER)
    assert maximal({Relation.STUTTER, Relation.PARTIAL_ORDER, Relation.ACTIVITY}) == {
        Relation.STUTTER,
        Relation.PARTIAL_ORDER,
    }
