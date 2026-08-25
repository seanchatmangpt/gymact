#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

from rdflib import Graph

ROOT = pathlib.Path(__file__).resolve().parent
SUBJECT_PATH = ROOT / "subject.json"
ADAPTER_PATH = ROOT / "adapter.ttl"
QUERY_DIR = ROOT / "queries"
RECEIPT_PATH = ROOT / "last-receipt.json"
EXPECTED_CONSUMER = "b40df62bbb1f6d5661eb1dbeb332476c90faa470"
EXPECTED_PRODUCER = "8bd29043a2818a5fb6a4de65cc403eff8e495b58"


def refuse(reason: str, details: list[str]) -> int:
    receipt = {"schema": "gymact.r58-consumer-receipt/1", "standing": "REFUSED", "reason": reason, "details": details, "consequential_do": False}
    RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(f"REFUSED[{reason}]=" + ",".join(details))
    return 1


def main() -> int:
    subject = json.loads(SUBJECT_PATH.read_text())
    checks = {
        "schema": subject.get("schema") == "ggen.epistemic-consumer-subject/2",
        "consumer_repo": subject.get("consumer_repo") == "seanchatmangpt/gymact",
        "consumer_base": subject.get("consumer_base") == EXPECTED_CONSUMER,
        "producer_base": subject.get("producer_base") == EXPECTED_PRODUCER,
        "target": subject.get("producer_target_token") == "esf:gymactTarget",
        "no_do": subject.get("consequential_do") is False,
        "sha_shape": all(re.fullmatch(r"[0-9a-f]{40}", subject.get(k, "")) for k in ("consumer_base", "producer_base")),
    }
    failures = [name for name, ok in checks.items() if not ok]
    for name, ok in checks.items():
        print(f"SUBJECT_{name.upper()}={'PASS' if ok else 'FAIL'}")
    if failures:
        return refuse("R58_SUBJECT_CONTRACT", failures)

    graph = Graph().parse(ADAPTER_PATH, format="turtle")
    queries = sorted(QUERY_DIR.glob("*.rq"))
    if len(queries) != 20:
        return refuse("R58_QUERY_CENSUS", [f"expected=20", f"observed={len(queries)}"])
    for query_path in queries:
        passed = bool(getattr(graph.query(query_path.read_text()), "askAnswer", False))
        print(f"COURT_{query_path.stem}={'PASS' if passed else 'FAIL'}")
        if not passed:
            failures.append(query_path.name)
    if failures:
        return refuse("R58_CONSUMER_COURT", failures)

    digest = hashlib.sha256(SUBJECT_PATH.read_bytes() + b"\n" + ADAPTER_PATH.read_bytes()).hexdigest()
    receipt = {
        "schema": "gymact.r58-consumer-receipt/1",
        "standing": "ALIVE",
        "consumer_repo": "seanchatmangpt/gymact",
        "consumer_base": EXPECTED_CONSUMER,
        "producer_repo": "seanchatmangpt/ggen-marketplace",
        "producer_base": EXPECTED_PRODUCER,
        "producer_target_token": "esf:gymactTarget",
        "courts_executed": 20,
        "subject_adapter_digest_sha256": digest,
        "consequential_do": False,
        "authority": ["OBSERVE", "VERIFY", "CONSTRUCT"],
    }
    RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print("R58_CONSUMER_COURT=ALIVE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
