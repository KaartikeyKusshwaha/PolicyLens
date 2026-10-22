"""Consistent workspace evidence snapshots, printable reports and signed archives."""

import base64
import hashlib
import io
import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from intelligence import SOURCES
from operations import canonical
from store import now
from verify_evidence_pack import verify_pack

MAX_ROWS = 5000
MAX_SNAPSHOT_BYTES = 2_000_000
MAX_REPORT_CHARACTERS = 200_000
RECORD_KINDS = (
    "customer",
    "rule",
    "case",
    "case_note",
    "task",
    "case_evidence",
    "policy_change",
    "policy_impact",
    "traceability_link",
    "backtest",
)
LIMITATIONS = [
    "This workspace snapshot supports human review; it is not compliance certification or legal advice.",
    "Signatures establish integrity relative to an independently trusted key, not truth of supplied records or resistance to host/signing-key compromise.",
    "Source checksums identify the retained feed; raw external feed bytes are not embedded, so this pack cannot independently reconstruct or authenticate that feed.",
    "Agent results remain drafts. Recorded model identifiers do not establish immutable model weights when the provider revision is unreported.",
    "The pack contains private business data. Exported copies require their own access control and retention.",
    "Identity database, membership history, session/key secrets and connector credentials are excluded.",
]


class EvidenceLimit(ValueError):
    pass


def bounded_rows(db, query, parameters=()):
    result = []
    total = 0
    for row in db.execute(query, parameters):
        if len(result) >= MAX_ROWS:
            raise EvidenceLimit(
                "Evidence exceeds the 5,000-row per-section pilot bound."
            )
        value = dict(row)
        total += len(canonical(value).encode())
        if total > MAX_SNAPSHOT_BYTES:
            raise EvidenceLimit("Evidence section exceeds the 2 MB pilot bound.")
        result.append(value)
    return result


def read_snapshot(db, workspace_id, settings):
    """Only called inside the checkpoint's existing SQLite read transaction."""
    records = {}
    for kind in RECORD_KINDS:
        records[kind] = [
            json.loads(r["payload"])
            for r in bounded_rows(
                db, "SELECT payload FROM records WHERE kind=? ORDER BY id", (kind,)
            )
        ]
    policies = bounded_rows(db, "SELECT * FROM policies ORDER BY id")
    versions = bounded_rows(
        db, "SELECT * FROM policy_versions ORDER BY policy_id,created_at,version"
    )
    for row in versions:
        row["payload"] = json.loads(row["payload"])
    sections = {}
    for table in (
        "transactions",
        "alerts",
        "decisions",
        "reviews",
        "jobs",
        "job_steps",
    ):
        sections[table] = bounded_rows(db, f"SELECT * FROM {table} ORDER BY rowid")
        for row in sections[table]:
            row["payload"] = json.loads(row["payload"])
    preferences = db.execute(
        "SELECT payload FROM records WHERE kind='preferences' ORDER BY updated_at DESC LIMIT 1"
    ).fetchone()
    selected = (
        json.loads(preferences[0])["enabled_sources"] if preferences else list(SOURCES)
    )
    metadata = {
        r["id"]: json.loads(r["payload"])
        for r in bounded_rows(
            db,
            "SELECT id,json_remove(payload,'$.entries') AS payload FROM sources ORDER BY id",
        )
    }
    fresh_after = datetime.now(timezone.utc) - timedelta(
        hours=settings.sanctions_max_age_hours
    )
    sources = []
    for source_id, source in SOURCES.items():
        stored = metadata.get(source_id, {})
        fetched = stored.get("fetched_at")
        try:
            stamp = datetime.fromisoformat(fetched) if fetched else None
            fresh = stamp is not None and fresh_after < stamp <= datetime.now(
                timezone.utc
            )
        except (TypeError, ValueError):
            fresh = False
        sources.append(
            {
                "id": source_id,
                "name": source["name"],
                "official_url": source["url"],
                "enabled": source_id in selected,
                "status": "ready" if fresh else "stale" if stored else "not_synced",
                "fetched_at": fetched,
                "published_at": stored.get("published_at"),
                "sha256": stored.get("sha256"),
                "count": stored.get("count", 0),
                "freshness_max_age_hours": settings.sanctions_max_age_hours,
            }
        )
    gaps = []
    if not policies:
        gaps.append("No policies recorded.")
    if not records["rule"]:
        gaps.append("No controls recorded.")
    for source in sources:
        if source["enabled"] and source["status"] != "ready":
            gaps.append(f"Enabled source {source['id']} is {source['status']}.")
    snapshot = {
        "format": "policylens.sponsor-evidence.v1",
        "workspace_id": workspace_id,
        "created_at": now(),
        "scope": "Complete retained workspace business records within explicit pilot export bounds; no date filter or silent sampling.",
        "policies": policies,
        "policy_versions": versions,
        "records": records,
        **sections,
        "source_freshness": sources,
        "coverage_gaps": gaps,
        "limitations": LIMITATIONS,
    }
    if len(canonical(snapshot).encode()) > MAX_SNAPSHOT_BYTES:
        raise EvidenceLimit("Evidence snapshot exceeds the 2 MB pilot bound.")
    return snapshot


def pdf_report(snapshot):
    """Complete snapshot rendered as readable labelled records; JSON preserves Unicode."""
    output = io.BytesIO()
    if len(json.dumps(snapshot, ensure_ascii=True)) > MAX_REPORT_CHARACTERS:
        raise EvidenceLimit(
            "Printable evidence exceeds the 200,000-character pilot bound."
        )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "Record",
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            spaceAfter=4,
            splitLongWords=True,
        )
    )
    styles["Title"].textColor = colors.HexColor("#123248")
    styles["Heading1"].textColor = colors.HexColor("#123248")
    story = [Paragraph("PolicyLens | Sponsor evidence", styles["Title"])]

    def printable(value):
        return escape(str(value).encode("ascii", "backslashreplace").decode())

    def record(value, prefix=""):
        if isinstance(value, dict) and value:
            for key, child in value.items():
                record(
                    child, (prefix + " / " if prefix else "") + key.replace("_", " ")
                )
        elif isinstance(value, list) and value:
            for index, child in enumerate(value, 1):
                record(child, f"{prefix} [{index}]")
        else:
            shown = (
                json.dumps(value, ensure_ascii=True)
                if not isinstance(value, str)
                else value
            )
            story.append(
                Paragraph(
                    ("<b>" + printable(prefix) + ":</b> " if prefix else "")
                    + printable(shown),
                    styles["Record"],
                )
            )

    for text in (
        "Workspace: " + snapshot["workspace_id"],
        "Snapshot created: " + snapshot["created_at"],
        "Audit sequence: " + str(snapshot["audit_snapshot"]["sequence"]),
        "Audit head: " + snapshot["audit_snapshot"]["head_hash"],
        "Human review required. Unicode characters below use JSON escapes for reliable printing; evidence.json retains the original text.",
    ):
        story.append(Paragraph(escape(text), styles["BodyText"]))
        story.append(Spacer(1, 6))
    for title, values in (
        ("Limitations", snapshot["limitations"]),
        ("Coverage gaps", snapshot["coverage_gaps"]),
        ("Source freshness", snapshot["source_freshness"]),
        ("Policies", snapshot["policies"]),
        ("Policy versions", snapshot["policy_versions"]),
        *(
            (kind.replace("_", " ").title(), rows)
            for kind, rows in snapshot["records"].items()
        ),
        *(
            (title.replace("_", " ").title(), snapshot[title])
            for title in (
                "transactions",
                "alerts",
                "decisions",
                "reviews",
                "jobs",
                "job_steps",
            )
        ),
    ):
        story.append(Paragraph(escape(title) + f" ({len(values)})", styles["Heading1"]))
        if not values:
            story.append(
                Paragraph("No records retained in this section.", styles["BodyText"])
            )
        for index, value in enumerate(values, 1):
            if isinstance(value, dict):
                story.append(Paragraph(f"Record {index}", styles["Heading3"]))
            record(value)
            story.append(Spacer(1, 5))
    story.append(Paragraph("Verification", styles["Heading1"]))
    story.append(
        Paragraph(
            "The archive includes a signed file manifest and the full signed audit chain in audit.json. Use a trusted verifier and a separately obtained signing fingerprint. The PDF digest establishes file integrity; it does not independently prove the truth of business records. See README.txt.",
            styles["BodyText"],
        )
    )

    def page(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#d8e1e8"))
        canvas.line(42, 37, document.pagesize[0] - 42, 37)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#526370"))
        canvas.drawString(
            42, 24, "PolicyLens | Private workspace evidence | Human review required"
        )
        canvas.drawRightString(document.pagesize[0] - 42, 24, str(document.page))
        canvas.restoreState()

    SimpleDocTemplate(
        output,
        title="PolicyLens sponsor evidence",
        author="PolicyLens",
        leftMargin=42,
        rightMargin=42,
        topMargin=42,
        bottomMargin=50,
    ).build(story, onFirstPage=page, onLaterPages=page)
    return output.getvalue()


def export_pack(manager, workspace_id):
    audit_bundle, snapshot = manager.capture(
        workspace_id,
        include_events=True,
        snapshot_reader=lambda db: read_snapshot(db, workspace_id, manager.settings),
    )
    anchor = audit_bundle["checkpoint"]["payload"]
    snapshot["audit_snapshot"] = {
        k: anchor[k] for k in ("workspace_id", "sequence", "head_hash")
    }
    readme = (
        "PolicyLens sponsor evidence pack\n\n"
        "Contains private business records for the complete retained workspace.\n"
        "evidence.json is the machine-readable business snapshot; report.pdf prints the same sections.\n"
        "audit.json is the full signed audit bundle from the same SQLite read transaction.\n"
        "manifest.json signs all other file digests with the checkpoint identity.\n\n"
        "Verify with a TRUSTED COPY of backend/verify_evidence_pack.py obtained from the reviewed repository.\n"
        "The included verify.py is provided for convenience, not a trust root. Do not execute scripts from untrusted archives.\n"
        "Install cryptography==50.0.2, then:\n"
        "python verify_evidence_pack.py pack.zip --fingerprint INDEPENDENTLY_TRUSTED_SHA256\n\n"
        + "\n".join(LIMITATIONS)
        + "\n"
    )
    files = {
        "evidence.json": (canonical(snapshot) + "\n").encode(),
        "audit.json": (canonical(audit_bundle) + "\n").encode(),
        "report.pdf": pdf_report(snapshot),
        "verify.py": Path(__file__).with_name("verify_evidence_pack.py").read_bytes(),
        "README.txt": readme.encode(),
    }
    root = manager.root()
    key = manager.signing_key(root)
    public, fingerprint = manager.identity(key)
    payload = {
        "schema": "policylens.evidence-manifest.v1",
        **snapshot["audit_snapshot"],
        "created_at": snapshot["created_at"],
        "files": {
            name: hashlib.sha256(value).hexdigest() for name, value in files.items()
        },
    }
    files["manifest.json"] = canonical(
        {
            "payload": payload,
            "algorithm": "Ed25519",
            "public_key": public,
            "signature": base64.b64encode(
                key.sign(canonical(payload).encode())
            ).decode(),
        }
    ).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    result = output.getvalue()
    verify_pack(result, fingerprint)
    return result
