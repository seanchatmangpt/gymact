# Model advice at the DCM boundary

GymAct treats model output as powerless planning advice.

The producer may be a GNN, ONNX model, scikit-learn estimator, Nx/Axon model, LLM, rule engine, planner, or other computation. The producer never defines applicability or authority.

The contract is:

formal candidate set
-> independent GymAct admission/evaluation
-> model ordering advice
-> ranked admitted candidates
-> ordinary DCM selection
-> irreversible cut
-> fresh authority
-> BRCE
-> consequence
-> verification
-> receipt

ModelAdvice is bound to the exact possibility-graph digest, planning subject, formal projection, artifact identity, capability, and input projection.

apply_model_advice() preserves two invariants:

1. a model cannot add a candidate that formal machinery did not supply;
2. a model cannot silently remove an independently admitted candidate.

An advised DO edge still fails admission without an execution grant. Advice itself is always Standing.CANDIDATE and authorizes_actuation=false.

This lets AutoFDE/SA2A use learned search geometry while GymAct remains the consequence-law boundary.
