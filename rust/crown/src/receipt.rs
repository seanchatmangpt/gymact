use crate::admission::REQUIRED_EVIDENCE;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CrownReceipt<'a> {
    pub bindings: &'a [(&'a str, &'a str)],
    pub transition_receipt_id: &'a str,
    pub replay_receipt_digest: &'a str,
}

pub fn complete(receipt: &CrownReceipt<'_>) -> bool {
    !receipt.transition_receipt_id.is_empty()
        && !receipt.replay_receipt_digest.is_empty()
        && REQUIRED_EVIDENCE.iter().all(|required| {
            receipt.bindings.iter().any(|(name, value)| name == required && !value.is_empty())
        })
}
