# protocol-gym-pack

This is the compiled half of the Protocol → Gym compiler. A pack is mounted by a ggen
consumer; it is not itself the executable project.

The checked-in Gall consumer is `rust/protocol_gym/`. Replay directly with:

```bash
cd rust/protocol_gym
ggen sync run
cargo test
```

Its `ggen.toml` names the canonical pack and ontology by relative path. When the same
consumer is materialized through `GgenProvider`, `bundle_root` admits the containing
repository boundary; the provider preflights every declared ontology/template/pack
path, copies those dependencies into an isomorphic private bundle, and runs ggen only
from that copied consumer. A dependency or symlink resolving outside `bundle_root` is
refused before copying.

The pack owns **11 normal consumer-project outputs**. It never writes a `generated/`
directory and never manufactures Python protocol clients. Discovery evidence begins
`STRUCTURAL`.
