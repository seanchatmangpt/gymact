from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gymact.action_contract import (
    ActionDefinition,
    ExecutionGrant,
    ExpectedEffect,
    PreparedAction,
    SubjectRef,
    VerificationKind,
    VerificationStrategy,
    construct_prepared_action,
)
from gymact.crown_runtime import execute_admitted, execute_verified, reconcile_uncertain
from gymact.local_providers import FilesystemProvider, GitProvider, SQLiteProvider
from gymact.models import (
    ActuationIntent,
    ActuationResult,
    Operation,
    Receipt,
    Standing,
    VerificationResult,
)


class MechanicalRuntime:
    """Mechanics-only test double; never used to claim provider integration standing."""

    def __init__(
        self,
        actuation: ActuationResult,
        verification: VerificationResult,
    ) -> None:
        self.actuation = actuation
        self.verification = verification
        self.recorded: list[Receipt] = []
        self.act_calls = 0

    async def act(self, intent: ActuationIntent) -> ActuationResult:
        del intent
        self.act_calls += 1
        return self.actuation

    async def verify(
        self,
        episode_id: str,
        expected: dict[str, object],
    ) -> VerificationResult:
        del episode_id, expected
        return self.verification

    def _record(self, receipt: Receipt) -> Receipt:
        self.recorded.append(receipt)
        return receipt


def actuation(
    *,
    accepted: bool = True,
    standing: Standing = Standing.ALIVE,
    pre: str = "a",
    post: str = "b",
    reason: str | None = None,
) -> ActuationResult:
    return ActuationResult(
        accepted=accepted,
        standing=standing,
        receipt=Receipt(
            episode_id="episode",
            operation=Operation.ACT,
            standing=standing,
            subject_ref="urn:subject:test",
            capability_ref="urn:capability:test",
            pre_state_digest=pre,
            post_state_digest=post,
            reason=reason,
        ),
    )


def verification(*, passed: bool = True, state_digest: str = "b") -> VerificationResult:
    return VerificationResult(
        episode_id="episode",
        passed=passed,
        expected={"ok": True},
        observed={"ok": passed},
        state_digest=state_digest,
    )


INTENT = ActuationIntent(
    episode_id="episode",
    capability="urn:capability:test",
    idempotency_key="intent-1",
)


@pytest.mark.asyncio
async def test_crown_alive_requires_postcondition_verification() -> None:
    runtime = MechanicalRuntime(actuation(), verification(passed=True))
    result = await execute_verified(runtime, INTENT, {"ok": True})
    assert result.standing is Standing.ALIVE
    assert result.verification is not None
    assert result.receipt.operation is Operation.VERIFY
    assert result.receipt.verification_id == result.verification.verification_id


@pytest.mark.asyncio
async def test_failed_postcondition_refuses_crown() -> None:
    runtime = MechanicalRuntime(actuation(), verification(passed=False))
    result = await execute_verified(runtime, INTENT, {"ok": True})
    assert result.standing is Standing.REFUSED
    assert result.receipt.reason == "POSTCONDITION_FAILED"


@pytest.mark.asyncio
async def test_changed_world_after_error_is_uncertain_then_reconciled() -> None:
    runtime = MechanicalRuntime(
        actuation(
            accepted=False,
            standing=Standing.BLOCKED,
            pre="a",
            post="b",
            reason="PROVIDER_ERROR:RuntimeError",
        ),
        verification(passed=True, state_digest="b"),
    )
    result = await execute_verified(runtime, INTENT, {"ok": True})
    assert result.standing is Standing.UNCERTAIN
    reconciled = await reconcile_uncertain(runtime, result, {"ok": True})
    assert reconciled.reconciliation.standing is Standing.ALIVE
    assert reconciled.reconciliation.retry_admitted is False


@pytest.mark.asyncio
async def test_reconcile_no_effect_does_not_admit_retry() -> None:
    runtime = MechanicalRuntime(
        actuation(accepted=False, standing=Standing.BLOCKED, pre="a", post="b"),
        verification(passed=False, state_digest="a"),
    )
    result = await execute_verified(runtime, INTENT, {"ok": True})
    reconciled = await reconcile_uncertain(runtime, result, {"ok": True})
    assert reconciled.reconciliation.standing is Standing.REFUSED
    assert reconciled.reconciliation.retry_admitted is False


def admitted_fixture() -> tuple[ActionDefinition, PreparedAction, ExecutionGrant]:
    effect = ExpectedEffect(predicate="state", parameters={"value": 1})
    action = ActionDefinition(
        semantic_id="urn:action:set",
        provider_ref="urn:provider:test",
        capability_ref="urn:capability:test",
        subject_type="schema:Thing",
        input_schema={"type": "object", "required": ["value"]},
        expected_effects=(effect,),
        verification=VerificationStrategy(
            kind=VerificationKind.EXACT_STATE,
            observer_ref="urn:observer:test",
            expected={"value": 1},
        ),
    )
    subject = SubjectRef(
        semantic_id="urn:subject:1",
        provider_ref="provider-subject",
        revision="rev-1",
    )
    prepared = construct_prepared_action(
        action,
        episode_id="episode",
        subject=subject,
        payload={"value": 1},
        admission_digest="admission",
        idempotency_key="intent-1",
    )
    grant = ExecutionGrant(
        principal="urn:principal:test",
        action_ref=action.semantic_id,
        subject=subject,
        capability_ref=action.capability_ref,
        authority_ref="urn:authority:test",
        policy_revision="policy-1",
        admitted_observation_ref="urn:observation:1",
        intended_effects=action.expected_effects,
        nonce="nonce",
    )
    return action, prepared, grant


@pytest.mark.asyncio
async def test_revision_drift_refuses_before_do() -> None:
    action, prepared, grant = admitted_fixture()
    runtime = MechanicalRuntime(actuation(), verification())
    result = await execute_admitted(
        runtime,
        action,
        prepared,
        grant,
        current_revision="rev-2",
        expected={"value": 1},
    )
    assert result.standing is Standing.REFUSED
    assert result.receipt.reason == "REVISION_MISMATCH_REFUSED"
    assert runtime.act_calls == 0


@pytest.mark.asyncio
async def test_real_filesystem_provider(tmp_path: Path) -> None:
    environment = await FilesystemProvider().materialize(
        scenario=None,
        config={"root": str(tmp_path)},
    )
    write = next(item for item in environment.capabilities() if item.binding == "write_text")
    await environment.actuate(
        write,
        {"path": "nested/proof.txt", "text": "verified consequence"},
    )
    passed, observed = await environment.verify({"files": {"nested/proof.txt": {"size": 20}}})
    assert passed
    assert observed["files"]["nested/proof.txt"]["sha256"]
    with pytest.raises(ValueError, match="AMBIGUOUS_SUBJECT_REFUSED"):
        await environment.actuate(write, {"path": "../escape.txt", "text": "no"})


@pytest.mark.asyncio
async def test_real_filesystem_provider_delete(tmp_path: Path) -> None:
    environment = await FilesystemProvider().materialize(
        scenario=None,
        config={"root": str(tmp_path)},
    )
    write = next(item for item in environment.capabilities() if item.binding == "write_text")
    delete = next(item for item in environment.capabilities() if item.binding == "delete")
    await environment.actuate(
        write,
        {"path": "nested/proof.txt", "text": "verified consequence"},
    )
    assert (tmp_path / "nested" / "proof.txt").is_file()
    result = await environment.actuate(delete, {"path": "nested/proof.txt"})
    assert result == {"path": "nested/proof.txt", "deleted": True}
    assert not (tmp_path / "nested" / "proof.txt").exists()
    passed, observed = await environment.verify({"files": {}})
    assert passed
    assert observed["files"] == {}


@pytest.mark.asyncio
async def test_real_git_provider_revision_bound_branch(tmp_path: Path) -> None:
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=tmp_path,
        check=True,
        stdout=subprocess.PIPE,
    )
    subprocess.run(
        ["git", "config", "user.email", "gymact@example.invalid"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "GymAct Test"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "base"],
        cwd=tmp_path,
        check=True,
        stdout=subprocess.PIPE,
    )
    environment = await GitProvider().materialize(
        scenario=None,
        config={"root": str(tmp_path)},
    )
    before = await environment.observe()
    branch = next(item for item in environment.capabilities() if item.binding == "create_branch")
    await environment.actuate(
        branch,
        {"name": "agent/proof", "expected_revision": before["head"]},
    )
    assert (await environment.observe())["branch"] == "agent/proof"
    with pytest.raises(ValueError, match="REVISION_MISMATCH_REFUSED"):
        await environment.actuate(
            branch,
            {"name": "agent/stale", "expected_revision": "0" * 40},
        )


@pytest.mark.asyncio
async def test_real_git_provider_write_text_and_commit(tmp_path: Path) -> None:
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=tmp_path,
        check=True,
        stdout=subprocess.PIPE,
    )
    subprocess.run(
        ["git", "config", "user.email", "gymact@example.invalid"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "GymAct Test"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "base"],
        cwd=tmp_path,
        check=True,
        stdout=subprocess.PIPE,
    )
    environment = await GitProvider().materialize(
        scenario=None,
        config={"root": str(tmp_path)},
    )
    before = await environment.observe()
    write = next(item for item in environment.capabilities() if item.binding == "write_text")
    commit = next(item for item in environment.capabilities() if item.binding == "commit")
    await environment.actuate(write, {"path": "proof.txt", "text": "committed proof"})
    assert (tmp_path / "proof.txt").read_text(encoding="utf-8") == "committed proof"
    result = await environment.actuate(commit, {"message": "add proof.txt"})
    after = await environment.observe()
    assert result["head"] == after["head"]
    assert after["head"] != before["head"]
    assert after["status"] == ""


@pytest.mark.asyncio
async def test_real_sqlite_provider_checkpoint_restore(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    environment = await SQLiteProvider().materialize(
        scenario=None,
        config={"database": str(database)},
    )
    set_capability = next(item for item in environment.capabilities() if item.binding == "set")
    await environment.actuate(set_capability, {"key": "count", "value": 3})
    passed, observed = await environment.verify({"values": {"count": 3}})
    assert passed and observed["values"] == {"count": 3}
    checkpoint = await environment.checkpoint()
    await environment.actuate(set_capability, {"key": "count", "value": 4})
    await environment.restore(checkpoint)
    assert (await environment.observe())["values"] == {"count": 3}


@pytest.mark.asyncio
async def test_real_sqlite_provider_delete(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    environment = await SQLiteProvider().materialize(
        scenario=None,
        config={"database": str(database)},
    )
    set_capability = next(item for item in environment.capabilities() if item.binding == "set")
    delete_capability = next(
        item for item in environment.capabilities() if item.binding == "delete"
    )
    await environment.actuate(set_capability, {"key": "count", "value": 3})
    passed, observed = await environment.verify({"values": {"count": 3}})
    assert passed and observed["values"] == {"count": 3}
    result = await environment.actuate(delete_capability, {"key": "count"})
    assert result == {"key": "count", "deleted": True}
    observed_after = await environment.observe()
    assert observed_after["values"] == {}
    assert "count" not in observed_after["values"]


@pytest.mark.asyncio
async def test_real_kernel_filesystem_crown_path(tmp_path: Path) -> None:
    """Dependency-closed integration gate; cloud runs it when the full package is present."""
    from gymact.authority import AllowListAuthorityResolver
    from gymact.models import MaterializationIntent
    from gymact.runtime import GymAct

    authority_ref = "urn:test:authority:crown"
    runtime = GymAct(
        validate_profile=False,
        authority_resolver=AllowListAuthorityResolver({authority_ref}),
    )
    runtime.register_provider(FilesystemProvider())
    materialized = await runtime.materialize(
        MaterializationIntent(
            provider="filesystem",
            config={"root": str(tmp_path)},
            idempotency_key="filesystem-materialize",
        )
    )
    assert materialized.episode is not None
    result = await execute_verified(
        runtime,
        ActuationIntent(
            episode_id=materialized.episode.episode_id,
            capability="urn:gymact:filesystem:capability:write-text",
            payload={"path": "proof.txt", "text": "crown"},
            authority_ref=authority_ref,
            idempotency_key="filesystem-write",
        ),
        {"files": {"proof.txt": {"size": 5}}},
    )
    assert result.standing is Standing.ALIVE
    assert result.verification is not None and result.verification.passed
    assert runtime.verify_evidence_chain()
    operations = [
        receipt.operation for receipt in runtime.episode_receipts(materialized.episode.episode_id)
    ]
    # Two real, distinct VERIFY receipts now trail the ACT: GymAct.verify()
    # itself independently records one (gymact.verification.PostconditionVerifier
    # closing the "verify never produced a Receipt" gap), and execute_verified's
    # own richer crown-level verified-transition receipt (_verification_receipt,
    # linking acknowledgement_status/world_changed off the actuation) follows it
    # -- a genuine evidence-trail improvement, not a duplicate.
    assert operations[-3:] == [Operation.ACT, Operation.VERIFY, Operation.VERIFY]
