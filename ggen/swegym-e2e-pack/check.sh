#!/usr/bin/env bash
set -euo pipefail

PACK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PACK_ROOT/../.." && pwd)"
GGEN_BIN="${GGEN_BIN:-ggen}"
RUSTC_BIN="${RUSTC_BIN:-rustc}"

if ! command -v "$GGEN_BIN" >/dev/null 2>&1; then
    echo "swegym-e2e-pack: ggen binary not found: $GGEN_BIN" >&2
    exit 2
fi
if ! command -v "$RUSTC_BIN" >/dev/null 2>&1; then
    echo "swegym-e2e-pack: rustc not found: $RUSTC_BIN" >&2
    exit 2
fi

SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT
PROJECT="$SCRATCH/consumer"
mkdir -p "$PROJECT/templates" "$PROJECT/shapes"
: > "$PROJECT/ontology.ttl"

cat > "$PROJECT/ggen.toml" <<EOF
[project]
name = "swegym-e2e-pack-check"

[ontology]
source = "ontology.ttl"

[packs]
swegym-e2e-pack = { path = "$PACK_ROOT" }

[templates]
dir = "templates"
EOF

cp "$REPO_ROOT/src/gymact/ontology/profile.shacl.ttl" "$PROJECT/shapes/profile.shacl.ttl"

(
    cd "$PROJECT"
    "$GGEN_BIN" sync run
)

GENERATED=(
    "src/swegym_e2e_contract.rs"
    "wit/swegym-e2e.wit"
    "tests/swegym_e2e_contract_proof.rs"
)
for path in "${GENERATED[@]}"; do
    test -s "$PROJECT/$path" || {
        echo "swegym-e2e-pack: generated file missing or empty: $path" >&2
        exit 1
    }
done

grep -Fq "SWE-Gym/SWE-Gym@main" "$PROJECT/src/swegym_e2e_contract.rs"
grep -Fq "urn:gymact:swegym:capability:evaluate-patch" "$PROJECT/src/swegym_e2e_contract.rs"
grep -Fq '"solved"' "$PROJECT/src/swegym_e2e_contract.rs"
grep -Fq '"materialize"' "$PROJECT/src/swegym_e2e_contract.rs"
grep -Fq '"act"' "$PROJECT/src/swegym_e2e_contract.rs"
grep -Fq '"verify"' "$PROJECT/src/swegym_e2e_contract.rs"
grep -Fq '"teardown"' "$PROJECT/src/swegym_e2e_contract.rs"
grep -Fq "package gymact:swegym-e2e@0.1.0;" "$PROJECT/wit/swegym-e2e.wit"
grep -Fq "interface swegym-e2e-verifier" "$PROJECT/wit/swegym-e2e.wit"

RECEIPT_VERIFY="$SCRATCH/receipt-verify.json"
(
    cd "$PROJECT"
    "$GGEN_BIN" receipt verify > "$RECEIPT_VERIFY"
)
grep -Fq '"valid": true' "$RECEIPT_VERIFY"
grep -Fq '"outputs": 3' "$RECEIPT_VERIFY"
grep -Fq '"signed": true' "$RECEIPT_VERIFY"
grep -Fq '"signature_valid": true' "$RECEIPT_VERIFY"

(
    cd "$PROJECT"
    "$RUSTC_BIN" --edition 2021 --test tests/swegym_e2e_contract_proof.rs \
        -o "$SCRATCH/swegym-e2e-contract-proof"
    "$SCRATCH/swegym-e2e-contract-proof"
)

BEFORE="$SCRATCH/before.sha256"
AFTER="$SCRATCH/after.sha256"
(
    cd "$PROJECT"
    sha256sum "${GENERATED[@]}" > "$BEFORE"
    "$GGEN_BIN" sync run
    sha256sum "${GENERATED[@]}" > "$AFTER"
)
cmp "$BEFORE" "$AFTER"

RECEIPT_HISTORY="$SCRATCH/receipt-history.json"
(
    cd "$PROJECT"
    "$GGEN_BIN" receipt history > "$RECEIPT_HISTORY"
)
grep -Fq '"valid": true' "$RECEIPT_HISTORY"
grep -Fq '"records": 2' "$RECEIPT_HISTORY"

cat > "$PROJECT/ontology.ttl" <<'EOF'
@prefix dct: <http://purl.org/dc/terms/> .
<urn:gymact:swegym:e2e:contract> dct:hasVersion "not-the-admitted-revision" .
EOF

SABOTAGE_LOG="$SCRATCH/sabotage.log"
if (
    cd "$PROJECT"
    "$GGEN_BIN" sync run >"$SABOTAGE_LOG" 2>&1
); then
    echo "swegym-e2e-pack: semantic sabotage unexpectedly generated" >&2
    cat "$SABOTAGE_LOG" >&2
    exit 1
fi
grep -Fq "010_contract" "$SABOTAGE_LOG" || {
    echo "swegym-e2e-pack: sabotage failed, but not through 010_contract" >&2
    cat "$SABOTAGE_LOG" >&2
    exit 1
}

(
    cd "$PROJECT"
    sha256sum "${GENERATED[@]}" > "$AFTER"
)
cmp "$BEFORE" "$AFTER"

echo "swegym-e2e-pack: ALIVE — real ggen sync, signed receipt chain, generated Rust/WIT, rustc proof, idempotency, and gate refusal all passed"
