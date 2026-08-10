#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Capability { pub id: &'static str, pub title: &'static str, pub consequence: &'static str }

pub const CAPABILITIES: &[Capability] = &[
    Capability { id: "do", title: "Fixture DO capability", consequence: "urn:gymact:consequence:do" },
    Capability { id: "read", title: "Fixture read capability", consequence: "urn:gymact:consequence:read" },
];
