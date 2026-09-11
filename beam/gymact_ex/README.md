# GymActEx

`GymActEx` is the in-repository BEAM projection of GymAct's bounded execution
profile. GymAct remains semantic authority; this project does not define a
second gym ontology, standing lattice, authority model, receipt model, or
provider SPI.

The projection calls the real GymAct FastAPI surface and exposes the eight
portable runtime operations:

```text
discover
materialize
observe
act
verify
checkpoint
restore
teardown
```

It additionally exposes the production combinatorial DO path
`act_selected/3`, the compatibility BRCE path `act_admitted/3`, and read-only
profile/contract/evidence/capability queries.

## Use

```elixir
client = GymActEx.new(base_url: "http://127.0.0.1:8000")

{:ok, providers} = GymActEx.discover(client)

{:ok, materialized} =
  GymActEx.materialize(client, %{
    provider: "memory",
    config: %{initial: %{healthy: false}, requires_authority: false},
    idempotency_key: "example-materialize"
  })

episode_id = materialized["episode"]["episode_id"]

{:ok, _result} =
  GymActEx.act(client, episode_id, %{
    episode_id: episode_id,
    capability: "urn:gymact:memory:capability:set",
    payload: %{key: "healthy", value: true},
    idempotency_key: "example-act"
  })

{:ok, %{"passed" => true}} = GymActEx.verify(client, episode_id, %{healthy: true})
```

The raw `act/3` operation is the generic GymAct execution-profile operation.
The Python production HTTP surface deprecates that endpoint in favor of the
DCM/cut-bound `act_selected/3` path. Production applications should preserve
that distinction rather than treating a successful HTTP request as authority.

## Chicago court

The Chicago test starts a real Python `GymAct` runtime with the real
`MemoryProvider`, serves it through the real FastAPI/Uvicorn surface, and then
drives it from the real Elixir client. There are no HTTP mocks or fake
providers in the court.

From the repository root:

```bash
bash scripts/chicago_gymact_ex.sh
```

The court proves a cross-runtime sequence:

```text
discover
-> materialize
-> observe
-> act
-> verify
-> checkpoint
-> act
-> restore
-> observe
-> teardown
-> evidence-chain verification
```

A passing court proves the BEAM client exercised those boundaries against a
real local GymAct runtime. It does not claim production DCM authority,
external-provider standing, or equivalence beyond the operations actually
exercised.
