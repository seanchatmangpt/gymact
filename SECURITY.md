# GymAct security model

GymAct treats benchmark actuation as a consequential world transition, not as a tool-call convenience layer.

## Hard invariants

1. An `authority_ref` is an identifier, never permission. A provider/environment that requires authority is fail-closed unless the configured `AuthorityResolver` returns an explicit positive decision.
2. Authority requirements are monotonic. Scenario/configuration data may raise a requirement; it must not lower a requirement imposed by the provider or environment.
3. MCP, HTTP, CLI, broker, provider and model boundaries do not grant authority. They submit typed intents to the same kernel.
4. Accepted invocation is not verified consequence. GymAct keeps actuation result, subsequent observation, independent verification and benchmark score separate.
5. Idempotency keys are bound to exact intent digests. Reuse with a different intent is refused.
6. External authority/provider/verification/recovery boundaries are bounded by `RuntimeLimits`. Timeout is `BLOCKED`, not success and not an authorization denial.
7. Consequential dispositions produce `Receipt` evidence. The reference ledger chains receipts with BLAKE3-256.
8. Raw provider exception messages are not copied into receipts. Error class and a digest are retained instead.
9. Provider plugins are never loaded during discovery. Plugin code executes only after an explicit named load request.

## Evidence scope

`MemoryReceiptLedger` is tamper-evident, not tamper-proof. Its BLAKE3 chain can detect mutation of a captured ledger, but an actor with complete control over process memory can rewrite an in-memory chain. High-assurance deployments should inject a durable ledger that anchors or signs records outside the GymAct process.

The RDF evidence projection uses public PROV-O and EARL terms. It is an evidence representation, not a digital signature and not a substitute for external audit storage.

## Timeout scope

Cancellation is cooperative at the Python async boundary. A provider that delegates work to an uncancellable external system must implement its own idempotency/reconciliation semantics. When GymAct times out, it reports `BLOCKED`; it does not infer that the external system did nothing.

## Reporting

Do not include credentials, cloud account identifiers, customer data, or active exploit material in public reports. Report security issues privately to the repository owner through GitHub's private vulnerability reporting channel when enabled.
