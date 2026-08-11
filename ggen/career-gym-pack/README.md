# CareerGym — Fortune-5 ATS public-semantic profile

CareerGym models the candidate/recruiting state space as a public-semantic ABox. It does **not** define a private CareerGym TBox.

## Public semantic stack

- Schema.org: Person, ProfilePage, JobPosting, ApplyAction, AssessAction, Event, Offer, Message, CreativeWork, Place.
- PROV-O: evidence, provenance, agents, activities, bundles, derivation.
- P-PLAN: ordered recruiting/application lifecycle.
- SKOS: local observed concepts plus mappings to external labor-market taxonomies.
- ESCO: authoritative occupation/skill Linked Data mapping target.
- O*NET: US occupation, skills, abilities, activities and task mapping target.
- W3C Verifiable Credentials: credential envelope for independently verifiable claims.
- ODRL: consent/use/distribution policy.
- OWL-Time: retention, response, interview and offer windows.
- DCTERMS: descriptions, conformance and relations.

## Fortune-5 ATS coverage

The profile carries the interoperable basis needed to project into enterprise ATS families without making any vendor schema canonical:

1. candidate identity and deduplication basis;
2. parser-safe resume artifact separated from source-of-truth evidence;
3. work/skill/credential provenance;
4. requisition and job-posting identity;
5. source/referral provenance;
6. application lifecycle;
7. screening and assessment stages;
8. interview scheduling;
9. offer/compensation/contingency envelope;
10. background/onboarding stage;
11. work-authorization status as UNKNOWN unless observed;
12. optional demographic/compliance category isolated from matching;
13. consent, distribution and retention policy;
14. ESCO/O*NET taxonomy resolution;
15. vendor projections for Workday, SAP SuccessFactors and Oracle Recruiting;
16. consequence verification and terminal standing downstream through GymAct/BRCE.

## Non-negotiable fences

Observed != admitted. Resume parsed != candidate data verified. Application submitted != application received. Interview scheduled != attended. Offer generated != offer accepted.

Unknown contact, work authorization, demographic, employer, compensation, or credential facts are never inferred.

A vendor ATS object is a projection of the canonical public graph. Workday/SAP/Oracle field names never become CareerGym semantic authority.

## Current episode

The first ABox preserves the supplied 2026-08-10 recruiter message for two 12-month+ AI/ML/data roles with an unidentified major auto manufacturer in Torrance CA or Marysville OH. Unknown employer/recruiter details remain unknown.

## Gates

- `010_no_custom_tbox.rq`: rejects CareerGym-owned classes/properties/predicates.
- `020_profile_basis.rq`: requires the core candidate/application process.
- `030_ats_interop_basis.rq`: requires the enterprise ATS projection basis.
- `040_sensitive_unknowns.rq`: fails if sensitive/work-authorization unknowns are silently converted into asserted values.
- `050_consequence_separation.rq`: enforces intent != consequence semantics.

Current standing remains PARTIAL_ALIVE until exact-head execution validates these gates and a real provider produces independently verified OCEL evidence.
