pub const REQUIRED_EVIDENCE: &[&str] = &[
    "admitted_observation_digest",
    "authority_evidence_ref",
    "consequence_digest",
    "experiment_digest",
    "receipt_digest",
    "replay_receipt_digest",
    "subject_digest",
    "verifier_digest",
];

pub fn admit(flags: &[(&str, bool)]) -> Result<(), &'static str> {
    for required in REQUIRED_EVIDENCE {
        if !flags.iter().any(|(name, admitted)| name == required && *admitted) {
            return Err("REFUSED:CROWN:EVIDENCE_INCOMPLETE");
        }
    }
    Ok(())
}
