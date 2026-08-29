from __future__ import annotations

import httpx

from gymact.gyms.gcp_discovery_live import load_resilient_discovery_census


class _SequenceClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = iter(responses)

    def get(self, _url: str) -> httpx.Response:
        return next(self._responses)


def _response(status: int, url: str, *, json_body=None, body: bytes = b"") -> httpx.Response:
    request = httpx.Request("GET", url)
    if json_body is not None:
        return httpx.Response(status, request=request, json=json_body)
    return httpx.Response(status, request=request, content=body)


def test_exhausted_transient_discovery_document_is_preserved_not_raised() -> None:
    directory_url = "https://discovery.googleapis.com/discovery/v1/apis"
    document_url = "https://example.googleapis.com/$discovery/rest?version=v1"
    directory = {
        "items": [
            {
                "name": "example",
                "version": "v1",
                "title": "Example",
                "preferred": True,
                "discoveryRestUrl": document_url,
            }
        ]
    }
    client = _SequenceClient(
        [
            _response(200, directory_url, json_body=directory),
            _response(502, document_url, body=b"bad gateway"),
            _response(502, document_url, body=b"bad gateway"),
            _response(502, document_url, body=b"bad gateway"),
            _response(502, document_url, body=b"bad gateway"),
        ]
    )

    result = load_resilient_discovery_census(client=client)

    assert result.complete_probe is True
    assert result.census.apis == ()
    assert len(result.unavailable) == 1
    unavailable = result.unavailable[0]
    assert unavailable.identity == "example:v1"
    assert unavailable.status_code == 502
    assert unavailable.reason == "ADVERTISED_DISCOVERY_TRANSIENT_EXHAUSTED"
    assert len(unavailable.response_digest_blake3) == 64
