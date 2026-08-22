from __future__ import annotations
from dataclasses import replace
from .model import Binding, Refusal

def renew(binding: Binding, *, receipt: str, schema: str, binding_id: str) -> Binding:
    if schema != binding.schema:
        raise Refusal("REFUSED_SCHEMA_DRIFT_RENEWAL")
    return replace(binding, receipt=receipt, binding_id=binding_id)
