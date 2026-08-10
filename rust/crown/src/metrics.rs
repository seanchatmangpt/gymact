#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Metric {
    pub id: &'static str,
    pub title: &'static str,
}

pub const METRICS: &[Metric] = &[
    Metric { id: "actuation_efficiency", title: "Actuation efficiency" },
    Metric { id: "cost_efficiency", title: "Cost efficiency" },
    Metric { id: "generalization", title: "Generalization" },
    Metric { id: "latency_efficiency", title: "Latency efficiency" },
    Metric { id: "portability", title: "Portability" },
    Metric { id: "quality", title: "Quality" },
    Metric { id: "recovery", title: "Recovery" },
    Metric { id: "verifiability", title: "Verifiability" },
];
