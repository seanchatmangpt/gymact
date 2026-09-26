# RFC v26.9.26 — architecture selection/transition experiment seed

## Ownership
GymAct provides worlds and experiments for enterprise architecture selection and transition, not production authority.

## Definition of done
1. Define an enterprise-architecture world with Strategy, OperatingModel, capabilities, ABBs, candidate SBBs and constraints.
2. Add policies/planners that select among qualified SBBs while preserving DfCM frontier evidence.
3. Simulate Baseline -> TransitionArchitecture -> TargetArchitecture.
4. Add nondeterministic failure worlds for supplier outage, cost change, SBB incompatibility, migration rollback and policy drift.
5. Capture OCEL/process evidence and postconditions separately from telemetry.
6. Prove strategy/operating-model changes alter selection pressure without rewriting ABB identity unnecessarily.
7. Add one experiment comparing reuse, compose, extend and manufacture alternatives.
8. Export deterministic experiment receipts for autofde-lab/affidavit.

GymAct results are evidence/candidates, never production DO.
