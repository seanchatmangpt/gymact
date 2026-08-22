import hashlib
import json


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def make(payload: dict) -> dict:
    body = {
        "schema": "gymact.explore-federation/v1",
        "payload": payload,
        "actuation_performed": False,
    }
    return {"body": body, "sha256": hashlib.sha256(canonical(body)).hexdigest()}
