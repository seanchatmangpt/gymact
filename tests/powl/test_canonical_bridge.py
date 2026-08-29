# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Real, identity-based proof that the ``powl`` dependency wiring works.

No mocks: this imports the real ``gymact.powl.canonical_bridge`` module and
the real ``powl.execution`` package (a real editable path dependency of this
project, see ``pyproject.toml``'s ``[tool.uv.sources]``) and asserts that the
symbols re-exported by the bridge module are the *actual same objects* as
the ones in ``powl.execution`` -- an ``is`` identity check, not a structural
comparison, so a re-export that accidentally wrapped/copied/shadowed the
real symbol would fail this test.
"""

from __future__ import annotations

import powl.execution as powl_execution

from gymact.powl import canonical_bridge


def test_bridge_reexports_are_the_real_powl_execution_objects() -> None:
    for name in canonical_bridge.__all__:
        bridged = getattr(canonical_bridge, name)
        real = getattr(powl_execution, name)
        assert bridged is real, f"{name}: bridge re-export is not the real powl.execution object"


def test_bridge_all_matches_powl_execution_all() -> None:
    assert set(canonical_bridge.__all__) == set(powl_execution.__all__)


def test_replay_is_the_real_powl_execution_replay() -> None:
    from powl.execution import replay as powl_replay

    from gymact.powl.canonical_bridge import replay

    assert replay is powl_replay
