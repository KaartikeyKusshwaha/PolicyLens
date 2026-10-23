# Oracle-host isolated deletion/recovery checks

Seven existing `backend/tests/test_deletion_execution.py` scenarios ran on the
actual Oracle pilot host using the deployed SQLCipher/runtime dependencies.
The seven relevant deployed source files matched local SHA-256 values before and
after execution. Pytest 9.0.2 was installed only in a separate test venv; the
application environment was not modified. Tests and all writable data were staged
under a fresh, private `/var/lib/policylens-synthetic-deletion-20261024` directory.

A hardened transient systemd unit ran as `policylens`, with private networking,
private temporary storage, protected filesystem/home and a five-minute runtime
limit. Only the synthetic root was writable. Fixtures explicitly create aged
fictional records and use in-process FastAPI TestClient; this is host/platform
acceptance of selected tests, not the deployed HTTPS user workflow.

The initial invocation stopped during collection because the separate venv did
not inherit the application's dependency directory. After that terminal failure,
the explicit Python path was corrected to read deployed packages, and the second
invocation completed: **7 passed, 21 deselected in 39.69 seconds**, exit zero,
about 119.3 MiB peak memory, zero peak swap. No assertions were relaxed.

Covered scenarios prove within these fixtures:

- Exact eligible logical deletion retains governance/audit, restarts and includes
  the receipt in a verified sponsor pack.
- Ten linked operational records are removed in dependency order, with policy
  governance retained.
- An injected audit failure rolls rows back, blocks startup and requires a proved
  abort rather than false commit.
- Guard-flush failure preserves the complete rollback and requires abort.
- Truncated guard publication refuses startup, further execution/export and false
  reconciliation claims.
- Post-commit publication interruption requires matching receipt/absent targets
  for commit reconciliation; reintroduced records refuse runtime verification.
- An old snapshot that would resurrect deleted records is refused before restore
  destination creation; a new snapshot restores the receipt and deleted state.

The JUnit result was fetched through verified SSH and parsed independently; its
digest and exact scenario names are in `summary.json`. Raw JUnit and synthetic
databases remain private. Both live services were active and both HTTPS readiness
checks passed afterward. No live workspace data was deleted or modified.

This does not prove complete copy discovery, audit-PII handling, physical/media
erasure, machine power-loss durability, HTTPS deletion review, off-machine recovery
of an executed-deletion guard, independent security review or real-data readiness.
Source tests cover logic; running them on the target host adds platform evidence
without replacing these remaining requirements. Artifact hashes bind retained
reports, not an independent attestation.

## Actual off-machine executed-history follow-up

The completed `test_executed_deletion_refuses_old_restore` synthetic installation
was selected while stopped. Using its original protected installation key, the
operator exported its complete authenticated deletion history, a fresh current
guard and a two-database SQLCipher snapshot. The history contained one executed
receipt. Source-side digests were retained separately before transfer.

Those bytes crossed verified-host SSH to the Windows receiver. The dedicated
receiver directory was restricted to the current user and SYSTEM before any
recovery key was written. The source installation key and a newly generated,
separate archive-encryption key remain private outside Git. The transport archive
and complete deletion history were encrypted at the receiver; original database
snapshot files remained SQLCipher ciphertext.

The receiver checked the source history digest, authenticated and encrypted the
history, recovered it into a new state root using the separately pinned current
digest, then performed a guarded database restore into a new data root. Runtime
suppression verification matched the recovered external state to the restored
database. The synthetic customer remained absent, one execution receipt survived,
the audit verified and sessions were revoked. `offmachine-recovery.json` records
these observations. No restored HTTP server or new model call was involved.

This follow-up establishes actual off-machine executed-history recovery for this
one isolated synthetic installation. It does not establish complete copy discovery,
physical erasure, live pilot deletion, a scheduled transfer of future execution
receipts, independent custody or owner acceptance. The original test-only snapshots
and private recovery artifacts are deliberately preserved; preservation is not an
erasure claim.
