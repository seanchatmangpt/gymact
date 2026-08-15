"""World Cyber Range: enterprise profile over a shared dependency world.

The canonical scenario/capability/actor graph lives in
`ggen/world-cyber-gym-pack/ontology.ttl`. Python executes that admitted graph
natively; multiple actor-scoped episodes may join one explicit ``world_id``;
ggen independently projects the same graph into Rust/WIT/static reference
data.
"""

from __future__ import annotations

from pathlib import Path

from gymact.gyms.shared_dependency_world import SharedDependencyWorldProvider

REPO_ROOT = Path(__file__).resolve().parents[3]
WORLD_CYBER_PACK_DIR = REPO_ROOT / "ggen" / "world-cyber-gym-pack"
LOCAL_PREFIX = "urn:gymact:world-cyber:"


def build_world_cyber_provider() -> SharedDependencyWorldProvider:
    return SharedDependencyWorldProvider(
        name="world-cyber",
        pack_dir=WORLD_CYBER_PACK_DIR,
        local_prefix=LOCAL_PREFIX,
    )


WorldCyberProvider = build_world_cyber_provider
