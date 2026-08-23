import hashlib
import json


def make(subject_sha: str, standing: str, axes: dict[str, str]):
    body = {
        "subject_sha": subject_sha,
        "standing": standing,
        "axes": dict(sorted(axes.items())),
        "actuation_performed": False,
    }
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return {"body": body, "sha256": hashlib.sha256(payload).hexdigest()}


def replay(receipt):
    fresh = make(
        receipt["body"]["subject_sha"],
        receipt["body"]["standing"],
        receipt["body"]["axes"],
    )
    if fresh["sha256"] != receipt["sha256"]:
        raise ValueError("REFUSED_RECEIPT_MISMATCH")
    return True
