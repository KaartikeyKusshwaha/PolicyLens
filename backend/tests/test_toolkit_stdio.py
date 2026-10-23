"""Exercise installed CLI and MCP stdio processes through an actual HTTP socket."""

import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time

import uvicorn
from mcp import Client, StdioServerParameters

from test_toolkit import case, key
from test_workflows import prepare


def test_stdio_transport_and_cli_against_real_http_boundary(workspace, tmp_path):
    client, _, _, _ = prepare(workspace)
    _, current = case(client)
    credential = key(client)
    key_file = tmp_path / "agent-credential"
    key_file.write_text(credential["token"], encoding="utf-8")
    key_file.chmod(0o600)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(client.app, lifespan="off", log_level="error")
    )
    thread = threading.Thread(
        target=server.run, kwargs={"sockets": [listener]}, daemon=True
    )
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.started
        environment = {
            **os.environ,
            "POLICYLENS_URL": f"http://127.0.0.1:{port}",
            "POLICYLENS_AGENT_KEY_FILE": str(key_file),
        }
        environment.pop("POLICYLENS_AGENT_KEY", None)
        command = subprocess.run(
            [
                sys.executable,
                "-m",
                "policylens_toolkit.cli",
                "call",
                "get_case_context",
            ],
            input=json.dumps({"case_id": current["id"]}),
            text=True,
            capture_output=True,
            timeout=20,
            env=environment,
        )
        assert command.returncode == 0, command.stderr
        assert json.loads(command.stdout)["id"] == current["id"]
        assert credential["token"] not in command.stdout + command.stderr

        async def journey():
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "policylens_toolkit.mcp_server"],
                env=environment,
            )
            async with Client(params) as agent:
                discovered = await agent.list_tools()
                assert "draft_investigation_brief" in {
                    tool.name for tool in discovered.tools
                }
                response = await agent.call_tool(
                    "get_case_context", {"case_id": current["id"]}
                )
                assert response.structured_content["id"] == current["id"]
                denied = await agent.call_tool("close_case", {})
                assert denied.is_error

        asyncio.run(journey())
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
    assert not thread.is_alive()
