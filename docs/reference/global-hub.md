# Global AI gym hub

GymAct's hub layer is a federation control plane, not a new ambient execution path.

`gymact.ggen_marketplace.review_marketplace()` scans every admitted `packs/*/pack.toml` in a local ggen-marketplace checkout and produces a deterministic relevance ordering. It never executes pack templates, gates, or generated code. The exact marketplace revision and the current architectural selection are pinned in `ggen/global-hub-marketplace.lock.toml`.

The first selected pack set is deliberately conjunctive:

- `autofde-semantic-registry-pack` supplies the federated semantic inventory, standing, provider/source distinctions, SHACL admission, and receipt discipline.
- `automatic-autonomic-operations-pack` supplies independent positive/refusal/receipt-replay proof obligations for unattended operations.
- `ggen-combinatorial-maximalism-pack` supplies bounded reversible construction plus brokered irreversible publication and BLAKE3 replay evidence.

`gymact.hub.FederatedGymRegistry` admits advertisements as structural routing knowledge. A remote `ALIVE` claim remains a remote claim: registration yields only `STRUCTURAL` local standing. Selection matches capability sets deterministically and returns `ROUTE_CANDIDATES_SELECTED_NOT_EXECUTED`; it never contacts the endpoint, materializes a provider, or grants DO authority.

The execution boundary remains unchanged:

```text
marketplace manifests -> review -> selected pack rails
                                  |
remote advertisements -> admit -> select -> candidate route
                                           |
                                           v
                               existing GymAct CONSTRUCT/BRCE path
                                           |
                                           v
                                      receipted DO
```

This separation lets GymAct become a global index/router for heterogeneous gyms without allowing catalog metadata, remote standing claims, ggen output, or transport identity to become execution authority.
