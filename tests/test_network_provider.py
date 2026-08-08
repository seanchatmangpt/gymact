from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from gymact.network_providers import HTTPJSONProvider, HTTP_JSON_CAPABILITIES


class Handler(BaseHTTPRequestHandler):
    state = {"count": 1}

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _send(self, value: dict[str, object], status: int = 200) -> None:
        raw = json.dumps(value, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send({"ok": True})
            return
        if self.path == "/state":
            self._send(dict(type(self).state))
            return
        self._send({"error": "not found"}, 404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/act":
            operation = body["operation"]
            payload = body["payload"]
            if operation == "set":
                type(self).state[str(payload["key"])] = payload.get("value")
            elif operation == "delete":
                type(self).state.pop(str(payload["key"]), None)
            self._send({"accepted": True})
            return
        if self.path == "/restore":
            type(self).state = dict(body["state"])
            self._send({"restored": True})
            return
        self._send({"error": "not found"}, 404)


def test_real_loopback_network_consequence_and_independent_observation() -> None:
    Handler.state = {"count": 1}
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    async def run() -> None:
        provider = HTTPJSONProvider()
        env = await provider.materialize(
            scenario=None,
            config={"base_url": f"http://127.0.0.1:{server.server_port}"},
        )
        before = await env.observe()
        assert before["count"] == 1
        effect = await env.actuate(
            HTTP_JSON_CAPABILITIES[0],
            {"key": "count", "value": 2},
        )
        assert effect["accepted"] is True
        passed, observed = await env.verify({"count": 2})
        assert passed and observed["count"] == 2
        checkpoint = await env.checkpoint()
        await env.actuate(HTTP_JSON_CAPABILITIES[1], {"key": "count"})
        assert "count" not in await env.observe()
        await env.restore(checkpoint)
        assert (await env.observe())["count"] == 2
        await env.teardown()

    try:
        asyncio.run(run())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_provider_rejects_non_network_subject() -> None:
    async def run() -> None:
        try:
            await HTTPJSONProvider().materialize(
                scenario=None,
                config={"base_url": "file:///tmp/x"},
            )
        except ValueError as exc:
            assert str(exc) == "PROVIDER_CONFIGURATION_REQUIRED"
        else:
            raise AssertionError("expected refusal")

    asyncio.run(run())
