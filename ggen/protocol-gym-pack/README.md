# protocol-gym-pack

This is the compiled half of the Protocol → Gym compiler.

Replace/admit `ontology.ttl` with the public-semantic ABox emitted by
`gymact.protocol_gym_rdf.protocol_gym_spec_to_rdf`, then run:

```bash
ggen sync run
cargo test --manifest-path ../../rust/protocol_gym/Cargo.toml
```

The pack owns **11 normal project outputs**. It never writes a `generated/` directory and
never manufactures Python protocol clients. Discovery evidence begins `STRUCTURAL`.
