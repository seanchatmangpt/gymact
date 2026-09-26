#!/usr/bin/env python3
"""LANE 8 anti-vacuity harness for ~/.zcode/dfcm/validate_receipt.py v2.

For each case: write a fixture receipt, run the real validator, assert the verdict
(ADMITTED/REFUSED) and that refusals carry the expected typed term. A check that
cannot refuse is vacuous; every refusal below is a witnessed firing.

Run: python3 validator_antivacuity.py   (exit 0 iff all witnessed)
"""
import json, subprocess, sys, tempfile
from pathlib import Path

VALIDATOR = Path.home() / ".zcode/dfcm/validate_receipt.py"
REPO = str(Path.home() / "affidavit")
ANCHOR = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"],
                        capture_output=True, text=True).stdout.strip()
assert len(ANCHOR) == 40, f"bad anchor {ANCHOR!r}"


def base_receipt(**over):
    r = {
        "work_order_id": "ALOOP-ZCODE-DOGFOOD-001/lane-8",
        "origin_authority": {"ceiling": "DO", "grant": "operator-dispatch ALOOP-ZCODE-DOGFOOD-001", "actor": "lane-8"},
        "provider": {"name": "zcode", "transport": "local-session", "authority_ceiling": "DO"},
        "provider_execution_id": "lane-8-run-0001",
        "identity": {"subject": "dfcm-receipt-schema-v2", "repo": REPO,
                     "subject_sha": ANCHOR, "base_sha": ANCHOR},
        "authority": {"ceiling": "DO", "grant": "operator-dispatch ALOOP-ZCODE-DOGFOOD-001", "actor": "lane-8"},
        "consequence": {"commits": [], "files_changed": [".zcode/dfcm/receipt.schema.json"],
                        "remote_effects": []},
        "replay": {"commands": [{"cmd": "python3 ~/.zcode/dfcm/validate_receipt.py <fixture>", "exit": 0,
                                 "cwd": str(Path.home() / ".zcode/workspace/default/aloop-dogfood-001/lane-8")}],
                   "durable_location": "~/.zcode/workspace/default/aloop-dogfood-001/lane-8/"},
        "standing": {"value": "PARTIAL_ALIVE", "derived_from": "validator run in this harness"},
    }
    r.update(over)
    return r


def run_validator(receipt, tmp, name):
    p = tmp / f"{name}.json"
    p.write_text(json.dumps(receipt, indent=2))
    proc = subprocess.run([sys.executable, str(VALIDATOR), str(p)], capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def main():
    tmp = Path(tempfile.mkdtemp(prefix="lane8-antivac-"))
    cases = []  # (name, receipt, expect_admit, expect_terms)

    cases.append(("positive_v2_full", base_receipt(), True, []))
    # missing the four new required fields (v1-shaped receipt) -> schema refuses
    v1 = base_receipt()
    for k in ["work_order_id", "origin_authority", "provider", "provider_execution_id"]:
        del v1[k]
    cases.append(("missing_new_required_fields", v1, False, ["required"]))
    # un-namespaced extension key -> validator namespace gate
    cases.append(("extension_without_namespace",
                  base_receipt(notes={"ttl": "smuggled"}), False, ["R_missing_identity"]))
    # namespaced extension admitted
    cases.append(("namespaced_extension",
                  base_receipt(**{"provider_ext.zcode": {"session": "ALOOP-ZCODE-DOGFOOD-001"}}),
                  True, []))
    # extension value not an object
    cases.append(("extension_value_not_object",
                  base_receipt(**{"provider_ext.zcode": "flat"}), False, ["R_missing_identity"]))
    # pre-existing check 1: ALIVE with a non-zero replay exit
    r = base_receipt()
    r["replay"]["commands"][0]["exit"] = 1
    r["standing"]["value"] = "ALIVE"
    r["standing"]["derived_from"] = "claim without green replay"
    cases.append(("alive_nonzero_exit", r, False, ["admission_vacuous"]))
    # pre-existing check 2: subject_sha not a commit (still fires; typed message)
    r = base_receipt()
    r["identity"]["subject_sha"] = "0" * 40
    cases.append(("subject_sha_not_commit", r, False, ["R_missing_identity"]))
    # digest stuffed into subject_sha never silently passes even with subject_digest present
    r = base_receipt()
    r["identity"]["subject_sha"] = "1" * 40
    r["identity"]["subject_digest"] = {"algorithm": "sha256", "value": "a" * 64}
    cases.append(("digest_in_subject_sha", r, False, ["R_missing_identity"]))
    # lawful digest-subject routing: commit anchor resolves + sha256 pack digest rides subject_digest
    import hashlib
    payload = json.dumps(base_receipt(), sort_keys=True).encode()
    r = base_receipt()
    r["identity"]["subject_digest"] = {"algorithm": "sha256", "value": hashlib.sha256(payload).hexdigest()}
    cases.append(("digest_via_subject_digest", r, True, []))
    # fail-closed: repo not locally verifiable -> refusal, never silent pass
    r = base_receipt()
    r["identity"]["repo"] = "github.com/seanchatmangpt/affidavit"
    cases.append(("repo_not_locally_verifiable", r, False, ["R_missing_identity"]))
    # BLOCKED standing without broken_term -> schema refuses (pre-existing)
    r = base_receipt()
    r["standing"] = {"value": "BLOCKED", "derived_from": "no authority"}
    cases.append(("blocked_without_broken_term", r, False, ["broken_term"]))

    witnessed, failed = 0, 0
    for name, receipt, expect_admit, terms in cases:
        code, out = run_validator(receipt, tmp, name)
        admitted = code == 0
        ok = admitted == expect_admit and all(t in out for t in terms)
        witnessed += ok
        failed += not ok
        verdict = "ADMITTED" if admitted else "REFUSED "
        print(f"[{'OK ' if ok else 'FAIL'}] {name}: {verdict} exit={code}")
        for line in out.strip().splitlines()[1:]:
            print("       " + line.strip())
    print(f"\nwitnessed={witnessed}/{len(cases)} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
