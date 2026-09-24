# Compromised ggen receipt-signing keys (v26.9.23)

Recorded 2026-09-24 (operator security item, single-repo migration). These private ed25519 seeds were committed to this
PUBLIC repository's default branch, so they are compromised: every receipt signed with them carries NO signing authority
(standing of such signatures: REFUSED, broken_term R_missing_authority). This commit removes them from the tree (history is
not rewritten; no force-push) and ignores `.ggen/keys/signing.key`; the next `ggen` run generates a fresh, untracked
keypair (rotation). ggen is being fixed to write `.ggen/keys/.gitignore` itself so the class cannot recur.

| private key path (removed) | sha256 of the compromised private key file | sha256 of its public verifying.key |
|---|---|---|
| `.ggen/keys/signing.key` | `3d1a84981f86dd4552beb3ef4c901d676c992696ca323372af7a62305a622cfd` | `d6097851f28762c6973136abc0c3924557a83f47697f0ebc64ea713b044ecc20` |
