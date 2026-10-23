# Retained synthetic HTTP load reports

These files contain aggregate synthetic observations only. Private run databases,
keys, cookies, server logs and signed business archives are deliberately excluded.
See `docs/PILOT_LOAD.md` and `evaluation/pilot_load.py` for the repeatable protocol.

| Report | Envelope and outcome | Canonical report SHA-256 |
| --- | --- | --- |
| `smoke.json` | Four customers/eight unique transactions, two clients; passed | `4ed1f0113f5e7ba876b7a2730060be06f5dd14221b31a11c955ee6f5e7507b5b` |
| `envelope-before-print-bound-failed.json` | 100 customers/1,000 unique transactions, four clients; failed at signed PDF export | `b0a3f283d18d62a0cc083522e69803d54ccd5aa3f369a57e28766fb5db8b9b0a` |
| `envelope-after-print-bound.json` | Same requested envelope, new isolated run after the print-bound fix; passed | `234e5586258d87d8aa745cdc81f0fae14a97a8f34517576aeb837b5ef5746a18` |

Each report digest hashes sorted compact JSON after removing `report_sha256`.
The failed result retains its failure phase, observed latencies and failed gate.
The successful result is a new run, not substituted outcomes from the earlier one.
`source-sha256.json` hashes the final successful runner and backend Python sources;
it does not describe the earlier smoke/failing implementation's print bound.

This is one local Windows machine, one Uvicorn worker, SQLCipher, no outbound
providers, no agent worker, and a chosen p95 threshold. It is not Oracle capacity
evidence, real partner validation, production or browser acceptance, a security
review, model/sanctions accuracy evidence, or an independently authenticated timing
attestation. The existing failed agent-preparation quality gate is unchanged.
