# World Cyber Gym Pack

Enterprise-architecture profile for a bounded synthetic cyber-physical dependency world.

`ontology.ttl` is canonical. Python consumes it directly through `DependencyWorldProvider`.
`ggen` independently projects the same admitted graph into a static Rust catalog, WIT ABI,
and compiled semantic reference. Generated projections are ephemeral and carry no external
actuation surface.

The graph uses public vocabularies only: PROF, PROV-O, P-PLAN, SOSA, WoT TD, ODRL,
SHACL/EARL, DQV, SKOS and DCTERMS. Local IRIs are ABox identities, SKOS concepts,
metrics, profile resources and shapes; no local TBox or predicates are defined.

The red/gray surface is intentionally bounded to abstract synthetic state transitions over
assets already declared in the materialized graph. It contains no exploit implementation,
network target, credential, process execution, shell, malware, persistence, or arbitrary URL.
