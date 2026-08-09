use gymact_protocol_gym::{
    authority::{admit_do, ADVERTISED_CAPABILITY_GRANTS_AUTHORITY, BRCE_REQUIRED_FOR_DO},
    capabilities::CAPABILITIES,
    standing::{crown, discovered, Standing},
};

#[test]
fn discovery_stays_structural() {
    assert_eq!(discovered(), Standing::Structural);
    assert!(!ADVERTISED_CAPABILITY_GRANTS_AUTHORITY);
    assert!(BRCE_REQUIRED_FOR_DO);
}

#[test]
fn ontology_cardinality_is_preserved() {
    assert_eq!(CAPABILITIES.len(), 2);
}

#[test]
fn crown_is_non_compensatory() {
    assert!(admit_do(false).is_err());
    assert!(crown(false, true, true).is_err());
    assert!(crown(true, false, true).is_err());
    assert!(crown(true, true, false).is_err());
}
