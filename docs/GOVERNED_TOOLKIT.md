# Governed agent toolkit

Implemented and deployed to Oracle. Actual HTTPS CLI/MCP context, review-task,
denial, audit and revocation checks passed on the isolated synthetic installation.
A separate local MCP subprocess produced and reverified a live four-citation
draft; see `evaluation/results/20261024-live-mcp-recovery/`. Configured Claude/
Cursor host acceptance, deployed live-model drafting and remaining browser
scenarios are still unverified.
The MCP implementation uses the official [Python SDK v2](https://py.sdk.modelcontextprotocol.io/)
and its stdio transport. This is a local stdio bridge to PolicyLens's authenticated
HTTPS API, not an unauthenticated public MCP port or an OAuth service.

The current investigation prompt is `policylens-governance-v2`. Briefs may carry
a nullable, nonbinding `draft_disposition` for [scorecard comparison](AGENT_SCORECARDS.md).
It does not update the human case disposition. Older keys/queued runs pinned to v1
are refused; administrators must reissue keys and submit reviewed new runs.

## Create access

An administrator creates a key in Settings & Agents -> Agent keys. Choose a distinct
agent name, individual tools, expiry (up to 90 days), requests/minute, daily model-run
budget and optional identifier masking. Creation requires password reauthentication
and the current second factor when MFA is enabled. The credential is returned once;
only its SHA-256 hash is stored. Store it in the agent's protected environment or a
private credential file, not source control or chat.

Revocation denies new requests and cancels pending runs. A model request already
sent cannot be recalled. An expired key or a key whose issuing administrator loses
admin membership is invalid. Restoring a database snapshot revokes all agent keys.
Human cookies never override a supplied agent bearer identity. Keys cannot use the
ordinary account, approval, case-action or other application API endpoints.

## Registry and permissions

| Tool | Class | Boundary |
| --- | --- | --- |
| search_policy | read | Bounded lexical policy retrieval with references |
| get_control | read | Control definition and recorded approval history |
| simulate_control | draft | Historical simulation; no activation or live alerts |
| simulate_control_tuning | draft | Compare supplied thresholds against an explicit historical workload target |
| draft_control_tuning | request-approval | Create a pinned tuning draft; a different human from the author/key issuer must approve |
| list_alerts | read | Paginated recorded alerts, optionally filtered by case |
| get_case_context | read | Case/customer evidence and recorded work |
| draft_investigation_brief | draft | Queues the existing investigation runner |
| verify_evidence | read | Quotes checked against a run's collected policy snapshot |
| create_review_task | request-approval | Creates an open human-review task; grants no approval |
| export_case_pack | read | Customer-scoped JSON case pack, registered in copy custody; signed sponsor packs are available through the human evidence API |
| run_playbook | draft | Existing investigation, screening, policy, policy-change and report playbooks |
| get_agent_run | read | Progress, steps, evidence and draft result |
| control_agent_run | draft | Pause/resume/cancel only this key's own run |

No tool approves, activates, closes, executes payments or files. Tool scopes are
checked on every invocation. Tenant selection comes from the key, never arguments.
Argument models reject extra fields; invalid input responses omit raw values.
Authenticated calls, starts/completions, failures and denials are audited under
`agent:<key-id>`. Invalid credential attempts and rate-limit results are recorded
centrally without retaining the credential or submitted evidence.

The per-key daily budget and workspace budget both apply. One model attempt per
run remains the rule; failures consume that attempt. Polling also consumes request
budget. Key revocation cancels queued/running/paused work at the database boundary.

## Model identity and masking

Each key and queued run captures the model ID, configured revision, prompt version
and masking choice. Execution uses that saved configuration even if deployment
settings change afterward. A returned model ID must match the request. If an
explicit `GROQ_MODEL_REVISION` is configured, the provider's `system_fingerprint`
must match; a mismatch fails the run without another model attempt.

The default revision is `provider-unreported`. This is intentionally explicit:
**a provider-managed model ID alone does not pin underlying weights**. The actual
returned model/fingerprint and enforcement status are recorded in a run step.
Do not claim immutable provider versioning when no enforceable revision is known.
An operator must use a revision supported by the provider to satisfy that stronger
deployment gate; arbitrary labels will fail when the provider does not report them.

Optional pseudonymization masks structured names, emails, addresses, external
references, LEIs and account references, and omits private notes. Known names are
also replaced in surrounding text. Aliases use keyed hashes; the original mapping
is not sent to the model. Opaque internal record IDs and citation references remain
usable. Source quote references resolve on the server, and verification can check
the same masked evidence view exposed to the agent.

This is **not complete anonymization**. Unknown personal information in arbitrary
free text may remain; source URLs and policy references are retained. Model hosts
can see returned tool evidence. Choose scopes and source content accordingly.
Production masking requires the separately provisioned installation security key.

## Install the SDK, CLI and MCP bridge

From the repository root, using a private Python 3.11+ environment:

```sh
python -m pip install './toolkit[mcp]'
```

Use the actual environment's Python executable in client configurations. Put the
one-time credential in a file accessible only to the current service/user. Set
`POLICYLENS_URL` to the HTTPS application origin and `POLICYLENS_AGENT_KEY_FILE` to
that file. `POLICYLENS_AGENT_KEY` is also supported, but a private file avoids
embedding credentials in client JSON. Loopback HTTP is permitted only for local
development. TLS certificate verification stays enabled; redirects are refused.

```sh
policylens list-tools
policylens call search_policy --arguments policy-query.json
```

`policy-query.json` contains `{"query":"identity verification"}`. Arguments may
also be supplied as a JSON object on stdin. The CLI has no approval/closure command
and no credential flag. The SDK makes no automatic mutation retries.

```python
from policylens_toolkit import PolicyLens

with PolicyLens.from_environment() as client:
    context = client.call("get_case_context", case_id="YOUR_CASE_ID")
    run = client.call("draft_investigation_brief", case_id=context["id"])
    result = client.wait_for_run(run["id"], timeout=180, interval=5)
    # A timeout preserves the live run ID; poll that same ID later.
    if result["state"] == "completed":
        client.call("create_review_task", case_id=context["id"],
                    instructions="Review the cited draft independently before a disposition.")
```

The agent needs every tool used in its journey, including `get_agent_run` to poll.
An incomplete/failed run must not be treated as a completed investigation.

## Claude Desktop configuration example

The official SDK's [host-configuration guide](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/get-started/real-host.md)
documents stdio `command`, `args` and `env` entries. Host acceptance remains pending.

Merge this entry into the host's existing MCP configuration. These are example
paths; use your installed environment and private credential file. This work does
not modify your desktop client configuration or grant it access automatically.

```json
{
  "mcpServers": {
    "policylens": {
      "command": "C:\\path\\to\\venv\\Scripts\\python.exe",
      "args": ["-m", "policylens_toolkit.mcp_server"],
      "env": {
        "POLICYLENS_URL": "https://YOUR_POLICYLENS_HOST",
        "POLICYLENS_AGENT_KEY_FILE": "C:\\private\\policylens-agent.txt"
      }
    }
  }
}
```

## Cursor configuration example

See [Cursor's MCP configuration documentation](https://prod.cursor.com/docs/mcp).

The same stdio entry can be used in the project or user MCP configuration. Keep
the credential file outside the repository; a project configuration may name its
path, but must not contain the key itself.

```json
{
  "mcpServers": {
    "policylens": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["-m", "policylens_toolkit.mcp_server"],
      "env": {
        "POLICYLENS_URL": "https://YOUR_POLICYLENS_HOST",
        "POLICYLENS_AGENT_KEY_FILE": "/private/policylens-agent.txt"
      }
    }
  }
}
```

Client configuration UI and deployment acceptance remain deferred. Automated tests
exercise SDK requests, the MCP protocol, a real stdio subprocess and loopback HTTP.
The seeded MCP journey collects case context, queues the existing runner, verifies
cited output, requests human review and is refused approval/closure. No browser is
required for these tests, and no real business records are inserted.
