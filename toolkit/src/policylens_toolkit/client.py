import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx


class PolicyLensError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code = status, code
        super().__init__(message)


class PolicyLens:
    def __init__(self, base_url, api_key, *, client=None):
        url = urlsplit(base_url)
        if (
            url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in ("", "/")
            or not url.hostname
        ):
            raise ValueError(
                "Use a PolicyLens origin without credentials, path, query or fragment."
            )
        if url.scheme != "https" and not (
            url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError(
                "Use HTTPS; plain HTTP is limited to loopback development."
            )
        if not api_key or "\n" in api_key or "\r" in api_key:
            raise ValueError("A scoped agent key is required.")
        self._api_key = api_key
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"), timeout=90, follow_redirects=False
        )

    @classmethod
    def from_environment(cls):
        key_file = os.environ.get("POLICYLENS_AGENT_KEY_FILE")
        key = (
            Path(key_file).read_text(encoding="utf-8").strip()
            if key_file
            else os.environ.get("POLICYLENS_AGENT_KEY", "")
        )
        return cls(os.environ.get("POLICYLENS_URL", "http://127.0.0.1:8000"), key)

    def request(self, method, path, arguments=None):
        if not path.startswith("/api/toolkit/") or "://" in path or ".." in path:
            raise ValueError("The SDK can address only governed toolkit endpoints.")
        try:
            response = self._client.request(
                method,
                path,
                headers={"Authorization": "Bearer " + self._api_key},
                json=arguments,
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            raise PolicyLensError(
                0,
                "transport_failed",
                "PolicyLens could not be reached. No mutation was retried.",
            ) from exc
        if 300 <= response.status_code < 400:
            raise PolicyLensError(
                response.status_code,
                "redirect_refused",
                "Agent credentials are never forwarded through redirects.",
            )
        try:
            body = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise PolicyLensError(
                response.status_code,
                "invalid_response",
                "PolicyLens did not return JSON.",
            ) from exc
        if response.is_error:
            detail = body.get("detail", {})
            raise PolicyLensError(
                response.status_code,
                detail.get("code", "request_failed")
                if isinstance(detail, dict)
                else "request_failed",
                detail.get("message", "The governed request failed.")
                if isinstance(detail, dict)
                else "The governed request failed.",
            )
        return body

    def list_tools(self):
        return self.request("GET", "/api/toolkit/tools")["tools"]

    def call(self, tool, **arguments):
        if not re.fullmatch(r"[a-z][a-z_]{0,79}", tool):
            raise ValueError("Use a tool name from list_tools.")
        return self.request("POST", "/api/toolkit/call/" + tool, arguments)

    def wait_for_run(self, run_id, *, timeout=180, interval=5):
        if timeout <= 0 or interval < 2:
            raise ValueError(
                "Use a positive timeout and a polling interval of at least two seconds."
            )
        end = time.monotonic() + timeout
        while True:
            run = self.call("get_agent_run", run_id=run_id)
            if run["state"] in {
                "completed",
                "failed",
                "cancelled",
                "interrupted",
                "paused",
            }:
                return run
            if time.monotonic() >= end:
                raise TimeoutError("Run is still active; poll the same run ID later.")
            time.sleep(min(interval, max(0, end - time.monotonic())))

    def close(self):
        if self._owns_client:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
