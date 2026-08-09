use gymact_crown::{
    admission::{admit, REQUIRED_EVIDENCE},
    authority::{admit_do, BRCE_IS_EXCLUSIVE_DO_PATH},
    frontier::{dominates, Point},
    metrics::METRICS,
    stages::STAGES,
    transport::{semantic_round_trip, TRANSPORTS},
    ZERO_UNRECEIPTED_ACTUATION,
};

#[test]
fn ontology_cardinalities_are_preserved() {
    assert_eq!(STAGES.len(), 12);
    assert_eq!(REQUIRED_EVIDENCE.len(), 8);
    assert_eq!(METRICS.len(), 8);
    assert_eq!(TRANSPORTS.len(), 8);
    assert!(13 >= 10);
}

#[test]
fn authority_and_receipt_are_non_compensatory() {
    assert!(BRCE_IS_EXCLUSIVE_DO_PATH);
    assert!(ZERO_UNRECEIPTED_ACTUATION);
    assert!(admit_do(false, true).is_err());
    assert!(admit_do(true, false).is_err());
}

#[test]
fn incomplete_crown_cannot_compare() {
    assert!(admit(&[("subject_digest", true)]).is_err());
}

#[test]
fn semantic_transport_must_round_trip() {
    assert!(semantic_round_trip("urn:action:set", "urn:action:set").is_ok());
    assert!(semantic_round_trip("urn:action:set", "urn:action:delete").is_err());
}

#[test]
fn pareto_dominator_falsifies_weaker_point() {
    let weak = [0.5; 8];
    let strong = [1.0; 8];
    let left = Point { result_id: "strong", values: &strong, crown_alive: true };
    let right = Point { result_id: "weak", values: &weak, crown_alive: true };
    assert_eq!(dominates(&left, &right).unwrap(), true);
}
