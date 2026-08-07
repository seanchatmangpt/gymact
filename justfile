# justfile — local mirror of .github/workflows/test.yml ("v26.8.7 contract")
#
# Each recipe below corresponds 1:1 to a job in that workflow so CI and local
# runs stay a single source of truth. Update both together.

set shell := ["bash", "-euo", "pipefail", "-c"]

default: all

# Run every job, in the same order CI runs them.
all: lock test package docs

# job: lock — Resolve dependency lock
lock:
    uv lock
    uv lock --check

# job: test — Python <version> (defaults to the interpreter uv picks; pass a
# version explicitly to mirror a specific matrix leg, e.g. `just test 3.11`)
test version="":
    uv sync --all-extras --group dev {{ if version != "" { "--python " + version } else { "" } }}
    uv run coverage run -m pytest
    uv run coverage report
    uv run ruff check src tests
    uv run ruff format --check src tests

# Run the full CI Python matrix locally (requires those interpreters to be
# installable/available to uv).
test-matrix:
    just test 3.11
    just test 3.12
    just test 3.13

# job: package — Build distribution
package:
    rm -rf dist
    uv build
    uvx twine check dist/*
    rm -rf /tmp/gymact-wheel
    python3 -m venv /tmp/gymact-wheel
    /tmp/gymact-wheel/bin/pip install -q dist/*.whl
    /tmp/gymact-wheel/bin/gymact version
    /tmp/gymact-wheel/bin/gymact validate-profile
    /tmp/gymact-wheel/bin/gymact export-profile /tmp/exported-profile
    test -s /tmp/exported-profile/profile.ttl
    test -s /tmp/exported-profile/profile.shacl.ttl

# job: docs — Build documentation
docs:
    uv sync --group dev
    uv run zensical build --clean

# job: container — Build and probe production container
#
# One shebang script for the whole recipe: `just` only honors `#!/...` as the
# recipe's first line — a shebang appearing mid-recipe is treated as a plain
# comment, and every other line then runs as its own separate `bash -c`
# invocation with no shared variables (bit us with `$cid` once already).
container:
    #!/usr/bin/env bash
    set -euo pipefail
    docker build --target production -t gymact:26.8.7 .
    docker run --rm gymact:26.8.7 version
    cid="$(docker run -d -p 127.0.0.1:8000:8000 gymact:26.8.7)"
    trap 'docker rm -f "$cid" >/dev/null 2>&1 || true' EXIT
    for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8000/health | grep -q 'ALIVE'; then
    exit 0
    fi
    sleep 1
    done
    docker logs "$cid"
    exit 1
