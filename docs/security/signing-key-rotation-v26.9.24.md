# Signing-key rotation (v26.9.24)

Recorded 2026-09-24 (fleet key scan after the single-repo migration). Base `f0caffba449b` of `gymact`.
Every private key listed here was committed to this repository and is therefore compromised: every receipt or
attestation signed with it carries no signing authority (standing REFUSED, broken_term R_missing_authority).
The keys leave the tree (history is not rewritten; no force-push), and each key directory's `.gitignore` now
covers both halves. Every checkout keeps its own pair: ggen generates one on first use, and a tracked public
half without its private half would make that first `ggen sync` refuse [FM-KEY-010/011]. The canonical
checkout's new public key is published below for anyone verifying its future receipts.

| key dir | removed private key sha256 | removed public key sha256 | new public key (canonical checkout) |
|---|---|---|---|
| `.ggen/keys` | removed earlier | `d6097851f28762c6973136abc0c3924557a83f47697f0ebc64ea713b044ecc20` | `9edead2f7afcf3a06217ac253f567725eb51dd9bca4e9332dc0ff68001d5a1dd` |

## Keys exposed on non-default branches (revoked 2026-09-24)

The v26.9.24 rotation scanned default branches only. A scan of every `origin/*` branch found the
private keys below committed on non-default branches only. Each is compromised and revoked: any receipt
or attestation signed with it carries no signing authority (standing REFUSED, broken_term
R_missing_authority). A disk scan of the canonical checkouts on 2026-09-24 found three of these keys in
use (ggen/packs, ignored files) and replaced them with fresh pairs. Copies in agent worktrees and tool
caches may still hold them. History is not rewritten, so the branches keep the blobs.

| path | private key sha256 | derived public key | branches (count, first) |
|---|---|---|---|
| `.ggen/keys/signing.key` | `3d1a84981f86dd4552beb3ef4c901d676c992696ca323372af7a62305a622cfd` | `7920f7e0483b86bd2f8e5e6ced4d3295a912eaad03c687941e72152da6ec2b1e` | 5, `adopt/engineering-standards-v26.9.21` |
