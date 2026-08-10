#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Stage {
    pub order: &'static str,
    pub id: &'static str,
    pub title: &'static str,
}

pub const STAGES: &[Stage] = &[
    Stage { order: "010", id: "observe", title: "Observe raw world evidence" },
    Stage { order: "020", id: "admit", title: "Admit bounded observation" },
    Stage { order: "030", id: "select", title: "Select reversible candidate" },
    Stage { order: "040", id: "construct", title: "Construct powerless artifact" },
    Stage { order: "050", id: "authorize", title: "Resolve explicit authority" },
    Stage { order: "060", id: "actuate", title: "Actuate only through BRCE" },
    Stage { order: "070", id: "observe_consequence", title: "Observe external consequence" },
    Stage { order: "080", id: "verify", title: "Verify objective independently" },
    Stage { order: "090", id: "receipt", title: "Bind execution receipt" },
    Stage { order: "100", id: "replay", title: "Replay exact evidence" },
    Stage { order: "110", id: "standing", title: "Admit Crown standing" },
    Stage { order: "120", id: "compare", title: "Compare bounded SOTA frontier" },
];

pub fn stage(id: &str) -> Option<&'static Stage> {
    STAGES.iter().find(|stage| stage.id == id)
}
