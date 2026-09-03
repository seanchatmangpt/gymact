# justfile — local mirror of .github/workflows/ci.yml (release verification contract)
#
# Each recipe corresponds to a CI boundary so local and remote admission exercise the
# same commands. The container recipe remains separate because it requires Docker.

set shell := ["bash", "-euo", "pipefail", "-c"]

default: all

all: lock test package docs

lock:
    uv lock
    uv lock --check

test version="":
    #!/usr/bin/env bash
    set -euo pipefail
    requested="{{version}}"
    if [[ -n "$requested" ]]; then
      uv sync --all-extras --group dev --python "$requested"
    else
      uv sync --all-extras --group dev
    fi
    py_minor="$(uv run python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    # uv's [tool.uv] override-dependencies pins playwright>=1.47,<2 (see
    # pyproject.toml), which resolves a prebuilt greenlet wheel on every
    # supported Python (including 3.13) instead of the browsergym-core==0.14.3
    # default pin (playwright==1.44 -> greenlet==3.0.3, no 3.13 wheel). So
    # BrowserGym installs and runs identically across the whole matrix now.
    if [[ -f "${AUTOFDE_LAB:-$HOME/autofde-lab}/vendor/gyms/browsergym/browsergym/core/pyproject.toml" ]]; then
      uv pip install -e "${AUTOFDE_LAB:-$HOME/autofde-lab}/vendor/gyms/browsergym/browsergym/core"
    else
      uv pip install "browsergym-core @ git+https://github.com/ServiceNow/BrowserGym.git@9e779f087de9a65668b6974d11f9ce9816026e96#subdirectory=browsergym/core"
    fi
    uv run playwright install chromium
    uv run gymact validate-profile
    uv run python -c 'from gymact.gyms.browsergym import BROWSERGYM_CAPABILITIES; from gymact.semantic import ProfileAuthority; r = ProfileAuthority().validate_capabilities(BROWSERGYM_CAPABILITIES); print(r.model_dump_json()); assert r.conforms, r.report_text'
    # monkeypatch.setenv/delenv/chdir/syspath_prepend control the real
    # environment (e.g. installing a real fake binary earlier on PATH) --
    # they do not fake a collaborator's interactions, so they are not
    # banned here. monkeypatch.setattr/delattr/setitem/delitem substitute
    # real objects/attributes and ARE the interaction-faking this guard
    # exists to catch. See tests/gyms/test_dev_portfolio_unit.py's module
    # docstring for the real, documented monkeypatch.setenv use this
    # narrower pattern is written to allow.
    if grep -RInE 'unittest\.mock|\bMock\b|\bpatch\b|monkeypatch\.(setattr|delattr|setitem|delitem)' tests; then
      echo 'mock-grep: forbidden test seam found' >&2
      exit 1
    else
      echo 'mock-grep: zero matches'
    fi
    uv run coverage run -m pytest -v
    uv run coverage report
    uv run ruff check src tests
    uv run ruff format --check src tests

test-matrix:
    just test 3.11
    just test 3.12
    just test 3.13

package:
    #!/usr/bin/env bash
    set -euo pipefail
    rm -rf dist /tmp/gymact-wheel /tmp/exported-profile /tmp/manufacturing-bundle
    uv build
    uvx twine check dist/*
    python3 -m venv /tmp/gymact-wheel
    /tmp/gymact-wheel/bin/pip install -q dist/*.whl
    /tmp/gymact-wheel/bin/gymact version
    /tmp/gymact-wheel/bin/gymact validate-profile
    /tmp/gymact-wheel/bin/gymact contract > /tmp/runtime-contract.json
    /tmp/gymact-wheel/bin/gymact export-profile /tmp/exported-profile
    /tmp/gymact-wheel/bin/gymact export-bundle /tmp/manufacturing-bundle
    test -s /tmp/exported-profile/profile.ttl
    test -s /tmp/exported-profile/profile.shacl.ttl
    test -s /tmp/manufacturing-bundle/profile.ttl
    test -s /tmp/manufacturing-bundle/profile.shacl.ttl
    test -s /tmp/manufacturing-bundle/runtime-contract.jcs.json
    /tmp/gymact-wheel/bin/python - <<'PY'
    import json
    from pathlib import Path
    from gymact import build_contract
    from gymact.evidence import canonical_bytes

    observed = json.loads(Path('/tmp/runtime-contract.json').read_text())
    assert observed['contract_digest'] == build_contract().contract_digest
    bundle = Path('/tmp/manufacturing-bundle/runtime-contract.jcs.json').read_bytes()
    assert bundle == canonical_bytes(build_contract().model_dump(mode='json'))
    PY

docs:
    uv sync --group dev
    uv run zensical build --clean

# composition-court — named exact-subject court for merge/composition standing.
# It is also part of the normal pytest suite; this target exists so a local
# merge can cheaply requalify the exact composed subject before inheriting any
# branch-local standing.
composition-court:
    uv run pytest -v tests/test_default_head_composition_court.py

# ggen-bridge-check — NOT a CI job, NOT part of `all`: this repo has no
# Rust toolchain and CI never sets one up (confirmed: none of
# .github/workflows/*.yml touch rust/cargo/ggen). Requires a real `ggen`
# binary on PATH (build one from the sibling `ggen` repo:
# `cargo build --release -p ggen-cli` there, then add its target/release/
# to PATH, or set GGEN_BIN to its exact path). Proves ggen/gymact-bridge-pack
# actually generates from ontology/profile.{ttl,shacl.ttl} (real symlinks
# into src/gymact/ontology/, not a copy) by running a real `ggen sync run`
# against a scratch consumer project, the same way
# ~/ggen/crates/ggen-engine/tests/gymact_bridge_pack_e2e.rs historically did
# from the Rust side.
ggen-bridge-check:
    #!/usr/bin/env bash
    set -euo pipefail
    GGEN_BIN="${GGEN_BIN:-ggen}"
    if ! command -v "$GGEN_BIN" >/dev/null 2>&1; then
        echo "ggen-bridge-check: no '$GGEN_BIN' binary on PATH." >&2
        echo "  Build one from the sibling ggen repo and either add target/release/" >&2
        echo "  to PATH or set GGEN_BIN to its exact path." >&2
        exit 2
    fi
    # Manufacturer identity is standing-bearing, not advisory. The repository
    # and CI capsule now pin ggen 26.8.11; another version is a different
    # subject and must not inherit that qualification.
    PINNED_VERSION="$(tr -d '[:space:]' < "$(pwd)/.ggen-version")"
    INSTALLED_VERSION="$("$GGEN_BIN" --version | head -n1 | awk '{print $2}')"
    if [ "$INSTALLED_VERSION" != "$PINNED_VERSION" ]; then
        echo "REFUSED:GGEN_VERSION_DRIFT:installed=$INSTALLED_VERSION pinned=$PINNED_VERSION" >&2
        exit 3
    fi
    PACK_ROOT="$(pwd)/ggen/gymact-bridge-pack"
    SCRATCH="$(mktemp -d)"
    trap 'rm -rf "$SCRATCH"' EXIT
    mkdir -p "$SCRATCH/consumer/templates" "$SCRATCH/consumer/shapes"
    printf '' > "$SCRATCH/consumer/ontology.ttl"
    cat > "$SCRATCH/consumer/ggen.toml" <<EOF
    [project]
    name = "consumer"

    [ontology]
    source = "ontology.ttl"

    [packs]
    gymact-bridge-pack = { path = "$PACK_ROOT" }

    [templates]
    dir = "templates"
    EOF
    cp "$PACK_ROOT/ontology/profile.shacl.ttl" "$SCRATCH/consumer/shapes/profile.shacl.ttl"
    (cd "$SCRATCH/consumer" && "$GGEN_BIN" sync run)
    for f in src/gymact_operation_catalog.rs src/gymact_mcp_tools.rs docs/gymact-bridge/reference.md tests/gymact_bridge_operation_catalog_proof.rs; do
        test -s "$SCRATCH/consumer/$f" || { echo "ggen-bridge-check: expected generated file missing: $f" >&2; exit 1; }
    done
    echo "ggen-bridge-check: OK — all 4 expected files generated with ggen $PINNED_VERSION"

# ggen-gates-check — NOT part of `all`: runs every ggen/*/gates/*.rq SPARQL
# gate against its own pack's ontology.ttl via rdflib. Unlike
# ggen-bridge-check, this needs no external `ggen` binary — it re-implements
# ggen's own ASK/SELECT-empty-passes gate contract directly (see
# scripts/run_sparql_gates.py's module docstring). Read-only verification,
# closes the gap that every pack's gates/*.rq file was real and checked-in
# but nothing in this repo actually executed any of them.
ggen-gates-check:
    uv run python scripts/run_sparql_gates.py

# ocel-standing — NOT part of `all`: human-facing batch report over
# reports/ocel/, per .claude/rules/ocel-standing.md ("useful as a
# human-facing batch report ... it is not banned, it is just not a
# substitute for a direct-state test assertion"). The real gate is
# tests/test_ocel_standing.py, already exercised by `just test`; this target
# only makes the existing script easier to find and run for a cross-subject
# standing overview.
ocel-standing:
    uv run python scripts/ocel_standing.py reports/ocel

# capability-manifest — NOT part of `all`: a reporting artifact for
# downstream consumers (e.g. autofde-lab's own capability allowlist), not a
# build-blocking check. Closes a real follow-up ~/ggen/packs/
# domain-capability-pack's own pack.toml names as out of scope for that
# pack: a generated, checkable source of truth for gymact's real capability
# surface, so a hand-copied downstream allowlist has something real to
# diff against instead of drifting silently (the exact drift that pack
# found: an allowlist's own comment claiming 5 sregym capabilities exist
# when the real source has grown to 14).
capability-manifest:
    uv run python scripts/capability_manifest.py

# observe-independence-check — raw report remains advisory because fully
# simulated worlds legitimately have no external I/O channel. The exact-head
# composition court hard-fails if any already-proven live external provider
# silently loses its independently detectable I/O read path.
observe-independence-check:
    uv run python scripts/check_observe_independence.py

# job: container — Build and probe production container
#
# One shebang script for the whole recipe: `just` only honors `#!/...` as the
# recipe's first line — a shebang appearing mid-recipe is treated as a plain
# comment, and every other line then runs as its own separate `bash -c`
# invocation with no shared variables (bit us with `$cid` once already).
container:
    #!/usr/bin/env bash
    set -euo pipefail
    docker build --target production -t gymact:ci-local .
    docker run --rm gymact:ci-local version
    docker run --rm gymact:ci-local contract | grep -q 'contract_digest'
    cid="$(docker run -d -p 127.0.0.1:8000:8000 gymact:ci-local)"
    trap 'docker rm -f "$cid" >/dev/null 2>&1 || true' EXIT
    for _ in $(seq 1 30); do
      if curl -fsS http://127.0.0.1:8000/health | grep -q 'ALIVE'; then
        curl -fsS http://127.0.0.1:8000/contract | grep -q 'RFC8785-JCS'
        curl -fsS http://127.0.0.1:8000/evidence | grep -q 'verified'
        exit 0
      fi
      sleep 1
    done
    docker logs "$cid"
    exit 1

# --- act (local GitHub Actions parity) --------------------------------------
# GitHub Actions minutes are finite; these recipes run the real workflows
# locally via `act` instead. Machine-specific flags live here (not in
# .actrc, which has no override/merge mechanism). Defaults match this
# machine (Colima, Apple Silicon); override elsewhere, e.g.
# `ACT_CONTAINER_ARCH=linux/amd64 ACT_DAEMON_SOCKET= just act-list`.
act_arch := env_var_or_default("ACT_CONTAINER_ARCH", "linux/arm64")
# act's OWN connection to the Docker daemon comes from the standard
# DOCKER_HOST env var, which it does NOT infer from the active `docker
# context` (verified: with DOCKER_HOST unset, act defaulted to the stale
# /var/run/docker.sock symlink even though `docker context ls` shows
# `colima` active and that's where images live).
export DOCKER_HOST := env_var_or_default("ACT_DAEMON_SOCKET", "unix://" + env_var_or_default("HOME", "") + "/.colima/default/docker.sock")
# `--container-daemon-socket` is a DIFFERENT thing: the socket bind-mounted
# INTO job containers for docker-in-docker steps (needed by ci.yml's
# `artifact` job, which runs real `docker build`/`docker run`). Bind-mounting
# Colima's real socket path directly fails under this VM backend ("mkdir
# .../docker.sock: operation not supported"); /var/run/docker.sock works
# because that path is native to the VM's own root filesystem (matches the
# working invocation recorded in ggen-ecosystem's docs/DEFINITION-OF-DONE.md).
act_container_socket := env_var_or_default("ACT_CONTAINER_DAEMON_SOCKET", "unix:///var/run/docker.sock")
# Deliberately NOT using --bind here (unlike ggen-ecosystem's act-governance
# recipe, which needs it for one specific docker-outside-of-docker scratch-
# mount pattern). None of gymact's jobs do that pattern: ci.yml's `artifact`
# job's `docker build .` and `docker run -p ...` don't reference any
# bind-mount path created by a live job step — `docker build`'s context is a
# tar stream sent to the daemon, not a path reference, so copy-mode (act's
# default) is correct and sufficient. --bind is NOT a free correctness
# upgrade: `actions/checkout`'s `ref: <sha>` step does a raw SHA checkout
# directly against the real working tree under --bind, which both discards
# uncommitted/untracked changes (git checkout --force + git clean -fdx) and
# detaches HEAD from whatever branch was checked out (this actually happened
# in ggen-ecosystem — see that repo's Justfile for the full incident). Only
# add --bind to a specific recipe here if a real DooD scratch-mount need is
# found, scoped exactly like ggen-ecosystem's act_flags_bind, with the same
# uncommitted-changes guard.
act_flags := "--container-architecture " + act_arch + " --container-daemon-socket " + act_container_socket + " --secret-file .secrets --env-file .env"

act-list:
    act -l {{act_flags}}

act-validate:
    #!/usr/bin/env bash
    set -euo pipefail
    for f in .github/workflows/*.yml; do
      echo "== act -n: $f =="
      act -n -W "$f" {{act_flags}}
    done

# Cheap smoke tier: 3 representative explore-*.yml courts, real execution.
act-explore-smoke:
    #!/usr/bin/env bash
    set -euo pipefail
    for f in explore-federation.yml explore-verification.yml explore-ack-discharge.yml; do
      echo "== $f =="
      act pull_request -W ".github/workflows/$f" {{act_flags}}
    done

# Every explore-*.yml for real (23 workflows) — run once the smoke tier passes.
act-explore-all:
    #!/usr/bin/env bash
    set -euo pipefail
    for f in .github/workflows/explore-*.yml; do
      echo "== $f =="
      act pull_request -W "$f" {{act_flags}}
    done

act-dmedi-train:
    act pull_request -W .github/workflows/dmedi-explore-train.yml {{act_flags}}

act-r54:
    act pull_request -W .github/workflows/r54-epistemic-consumer.yml {{act_flags}}

act-r58:
    act pull_request -W .github/workflows/r58-independent-consumer.yml {{act_flags}}

act-r79:
    act pull_request -W .github/workflows/r79-tcps-ready-set-consumer.yml {{act_flags}}

act-aws-botocore:
    act pull_request -W .github/workflows/aws-botocore-scalar-contract.yml {{act_flags}}

act-gcp-census:
    act pull_request -W .github/workflows/gcp-public-contract-census.yml {{act_flags}}

act-envharness:
    act pull_request -W .github/workflows/envharness.yml {{act_flags}}

act-v2691:
    act pull_request -W .github/workflows/v2691-world-execution.yml {{act_flags}}

act-ddui:
    act pull_request -W .github/workflows/dd-ui-profile.yml {{act_flags}}

act-enterprise-connection:
    act pull_request -W .github/workflows/enterprise-connection-crown.yml {{act_flags}}

# Cross-repo reusable workflow call — resolved against the local checkout of
# seanchatmangpt/chatman-ecosystem on this machine instead of the network.
act-federated:
    act pull_request -W .github/workflows/federated-capability-owner.yml \
      --local-repository seanchatmangpt/chatman-ecosystem@7430dfc9b3ca138e703430d25de7c6f48a8d6ade=/Users/sac/chatman-ecosystem \
      {{act_flags}}

# ci.yml, staged: single Python version first, then the full matrix.
act-core-single:
    act pull_request -W .github/workflows/ci.yml -j core --matrix python:3.12 {{act_flags}}

act-core:
    act pull_request -W .github/workflows/ci.yml -j core {{act_flags}}

act-cloudsim:
    act pull_request -W .github/workflows/ci.yml -j cloudsim {{act_flags}}

# Full ci.yml event so the artifact-server can bridge core/cloudsim -> artifact
# (needs the Tier-B v3 dual-path already applied to ci.yml's upload/download
# sites to actually succeed end to end).
act-ci-full:
    act pull_request -W .github/workflows/ci.yml {{act_flags}}

# NEVER run for real under act: release.yml does real GH Pages deploy
# (environment: github-pages) and real PyPI OIDC trusted publishing
# (id-token: write) — both independently unsupported by act. Dry-run only.
act-release-dryrun:
    act -n -W .github/workflows/release.yml {{act_flags}}

# NEVER run for real: gcp-empirical-campaign.yml can spend real GCP resources
# when allow_do=true. Dry-run only, and no GCP_ACCESS_TOKEN is ever placed in
# .secrets by design.
act-gcp-campaign-dryrun:
    act -n -W .github/workflows/gcp-empirical-campaign.yml {{act_flags}}
