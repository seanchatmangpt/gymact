# CareerGym — public-semantic career world

CareerGym models a career process as an executable gym **without inventing a private career ontology**.

The canonical source is `ontology.ttl`. Every `urn:gymact:careergym:*` term is an ABox/profile resource, SKOS concept, plan instance, or action/observation identity. Domain meaning is carried by public vocabularies:

- Schema.org — `Person`, `Organization`, `JobPosting`, `Message`, `CreativeWork`, `SendAction`, locations and addresses.
- PROV-O — observations, activities, derivation, agents, entities, and plans.
- P-PLAN — the opportunity-to-close process and ordered steps.
- ODRL — bounded policy facts around use of the resume artifact.
- SKOS — skill classifications.
- OWL-Time — temporal windows.
- DCTERMS — labels, descriptions, conformance and relations.

## First admitted episode

The initial ABox captures the 2026-08-10 recruiter observation for two 12-month+ auto-manufacturer contract opportunities: AI Engineer and ML/AI Data Science, on-site in Torrance CA or Marysville OH, with Python/AWS/Docker/AI-ML/data requirements and a recruiter request for a resume.

This is an observation, not proof that either job exists beyond the supplied recruiter message. The manufacturer remains unidentified, so the graph preserves that uncertainty instead of fabricating an employer identity.

## Process

`careerPlan` is a P-PLAN graph:

`observe -> normalize -> match -> preserve options -> admit -> tailor resume -> construct response -> authorized send -> verify -> wait -> schedule -> interview -> follow-up -> offer evaluation -> close`

The plan does not imply that each step must execute. DfCM preserves reversible alternatives before admission; consequential actions remain behind GymAct/BRCE authority.

## Gates

- `010_no_custom_tbox.rq`: any CareerGym-owned class/property/predicate is a violation.
- `020_profile_basis.rq`: the profile must contain the plan, resume artifact, at least one job posting, a send intent, and the minimum 15-step process basis.

## Claim ceiling

Current standing is **PARTIAL_ALIVE** after graph publication only. A real CareerGym episode requires a provider that observes the connected career surfaces, executes only admitted/authorized consequences, emits a schema-valid OCEL 2.0 log, and independently verifies the actual consequence.
