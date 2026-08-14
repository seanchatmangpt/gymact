#!/usr/bin/env bash
set -euo pipefail

PACK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PACK_ROOT/../.." && pwd)"
GGEN_BIN="${GGEN_BIN:-ggen}"
RUSTC_BIN="${RUSTC_BIN:-rustc}"

command -v "$GGEN_BIN" >/dev/null 2>&1 || { echo "sregym-e2e-pack: ggen binary not found: $GGEN_BIN" >&2; exit 2; }
command -v "$RUSTC_BIN" >/dev/null 2>&1 || { echo "sregym-e2e-pack: rustc not found: $RUSTC_BIN" >&2; exit 2; }

SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT
PROJECT="$SCRATCH/consumer"
mkdir -p "$PROJECT/templates"
: > "$PROJECT/ontology.ttl"

cat > "$PROJECT/ggen.toml" <<EOF
[project]
name = "sregym-e2e-pack-check"

[ontology]
source = "ontology.ttl"

[packs]
sregym-e2e-pack = { path = "$PACK_ROOT" }

[templates]
dir = "templates"
EOF

(
    cd "$PROJECT"
    "$GGEN_BIN" sync run
)

GENERATED=(
    "src/sregym_e2e_contract.rs"
    "wit/sregym-e2e.wit"
    "tests/sregym_e2e_contract_proof.rs"
    "src/gymact/generated/sregym_mcp_catalog.py"
)
for path in "${GENERATED[@]}"; do
    test -s "$PROJECT/$path" || {
        echo "sregym-e2e-pack: generated file missing or empty: $path" >&2
        exit 1
    }
done

grep -Fq "ba07faf1a322f9b6d4a279643bb796aa2f36f64b" "$PROJECT/src/sregym_e2e_contract.rs"
grep -Fq "capability_count: 14" "$PROJECT/src/sregym_e2e_contract.rs"
grep -Fq "read_count: 11" "$PROJECT/src/sregym_e2e_contract.rs"
grep -Fq "do_count: 3" "$PROJECT/src/sregym_e2e_contract.rs"
grep -Fq "corpus_count: 21" "$PROJECT/src/sregym_e2e_contract.rs"
grep -Fq "deterministic_program_count: 2" "$PROJECT/src/sregym_e2e_contract.rs"
grep -Fq "STRUCTURAL_ADMISSION_IS_ALIVE: bool = false" "$PROJECT/src/sregym_e2e_contract.rs"
grep -Fq "package gymact:sregym-e2e@0.2.0;" "$PROJECT/wit/sregym-e2e.wit"
grep -Fq "structural-admission-is-alive=false" "$PROJECT/wit/sregym-e2e.wit"
grep -Fq "SREGYM_UPSTREAM_REVISION" "$PROJECT/src/gymact/generated/sregym_mcp_catalog.py"
grep -Fq "wrong_dns_policy_astronomy_shop" "$PROJECT/src/gymact/generated/sregym_mcp_catalog.py"
grep -Fq "internal_traffic_policy_local_astronomy_shop" "$PROJECT/src/gymact/generated/sregym_mcp_catalog.py"

RECEIPT_VERIFY="$SCRATCH/receipt-verify.json"
(
    cd "$PROJECT"
    "$GGEN_BIN" receipt verify > "$RECEIPT_VERIFY"
)
grep -Fq '"valid": true' "$RECEIPT_VERIFY"
grep -Fq '"outputs": 4' "$RECEIPT_VERIFY"
grep -Fq '"signed": true' "$RECEIPT_VERIFY"
grep -Fq '"signature_valid": true' "$RECEIPT_VERIFY"

(
    cd "$PROJECT"
    "$RUSTC_BIN" --edition 2021 --test tests/sregym_e2e_contract_proof.rs -o "$SCRATCH/sregym-e2e-contract-proof"
    "$SCRATCH/sregym-e2e-contract-proof"
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
<urn:gymact:sregym:e2e:contract> dct:hasVersion "not-the-admitted-revision" .
EOF

SABOTAGE_LOG="$SCRATCH/sabotage.log"
if ( cd "$PROJECT" && "$GGEN_BIN" sync run >"$SABOTAGE_LOG" 2>&1 ); then
    echo "sregym-e2e-pack: semantic sabotage unexpectedly generated" >&2
    cat "$SABOTAGE_LOG" >&2
    exit 1
fi
grep -Fq "010_contract" "$SABOTAGE_LOG" || {
    echo "sregym-e2e-pack: sabotage failed, but not through 010_contract" >&2
    cat "$SABOTAGE_LOG" >&2
    exit 1
}

( cd "$PROJECT" && sha256sum "${GENERATED[@]}" > "$AFTER" )
cmp "$BEFORE" "$AFTER"

echo "sregym-e2e-pack: STRUCTURAL_ALIVE — ggen sync, signed receipt chain, Rust/WIT/Python projections, rustc proof, idempotency, and gate refusal passed; runtime SREGym ALIVE is not asserted"
