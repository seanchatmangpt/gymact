# protocol-gym-pack

This is the compiled half of the Protocol → Gym compiler. A pack is mounted by a ggen
consumer; it is not itself the executable project.

The checked-in Gall consumer is `rust/protocol_gym/`. Its `pack` symlink mounts this
pack inside the consumer boundary so the ggen gym can dependency-close it when copying
the world. Replay with:

```bash
cd rust/protocol_gym
ggen sync run
cargo test
```

For a real discovered subject, create another dependency-closed consumer `ggen.toml`,
write its admitted `ontology.ttl` from `protocol_gym_spec_to_rdf`, and mount this pack.

The pack owns **11 normal consumer-project outputs**. It never writes a `generated/`
directory and never manufactures Python protocol clients. Discovery evidence begins
`STRUCTURAL`.
