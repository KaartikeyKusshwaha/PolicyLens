import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
  Database,
  FileCheck2,
  ScanLine,
  ShieldCheck,
} from "lucide-react";
import { ErrorNotice, Field, PageHeading, Submit } from "../components";
import { api } from "../services/api";
import { useWorkspace } from "../App";

export default function Evaluate() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { health } = useWorkspace();
  async function submit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const transaction = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const result = await api("/transactions/evaluate", {
        method: "POST",
        body: { transaction },
      });
      navigate(`/decisions/${result.id}`);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="TRANSACTION WORKSPACE"
        title="A closer look. A clearer decision."
      >
        Add the details. We’ll connect the transaction to your policy evidence.
      </PageHeading>
      <div className="form-layout">
        <form className="panel form-panel" onSubmit={submit}>
          <div className="section-heading">
            <span className="section-icon">
              <ScanLine size={20} />
            </span>
            <div>
              <h2>Transaction details</h2>
              <p>All fields are required for a useful assessment.</p>
            </div>
          </div>
          <div className="form-grid">
            <Field label="Transaction ID" wide>
              <input
                name="transaction_id"
                defaultValue={`TXN-${Date.now().toString(36).toUpperCase()}`}
                required
                maxLength={100}
              />
            </Field>
            <Field label="Amount">
              <input
                name="amount"
                type="number"
                min="0.01"
                step="0.01"
                max="9999999999999999.99"
                placeholder="0.00"
                required
              />
            </Field>
            <Field label="Currency">
              <select name="currency" defaultValue="INR">
                {[
                  "INR",
                  "USD",
                  "EUR",
                  "GBP",
                  "AED",
                  "CAD",
                  "AUD",
                  "JPY",
                  "CHF",
                  "SGD",
                ].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </Field>
            <div className="form-divider wide">PARTIES & CORRIDOR</div>
            <Field label="Sender’s full name">
              <input
                name="sender"
                placeholder="Full legal name"
                minLength={3}
                maxLength={200}
                required
              />
            </Field>
            <Field label="Sender’s country">
              <input
                name="sender_country"
                placeholder="e.g. India"
                minLength={2}
                maxLength={100}
                required
              />
            </Field>
            <Field label="Receiver’s full name">
              <input
                name="receiver"
                placeholder="Full legal name"
                minLength={3}
                maxLength={200}
                required
              />
            </Field>
            <Field label="Receiver’s country">
              <input
                name="receiver_country"
                placeholder="e.g. United Kingdom"
                minLength={2}
                maxLength={100}
                required
              />
            </Field>
            <Field
              label="Purpose & context"
              wide
              hint="Include the payment purpose, relationship, and any due diligence already performed."
            >
              <textarea
                name="description"
                rows={4}
                placeholder="Describe what this payment is for…"
                minLength={10}
                maxLength={2000}
                required
              />
            </Field>
          </div>
          <ErrorNotice message={error} />
          <div className="form-actions">
            <Link className="text-link" to="/">
              <ArrowLeft size={15} /> Back to overview
            </Link>
            <Submit busy={busy}>
              <ScanLine size={17} /> Run assessment
            </Submit>
          </div>
          <p className="privacy-note">
            Transaction details and relevant policy excerpts are sent to Groq
            for analysis. Assessments are stored locally.
          </p>
        </form>
        <aside className="form-aside">
          <div className="panel guidance-panel">
            <ShieldCheck size={29} />
            <h2>Evidence before conclusions.</h2>
            <p>
              Each assessment connects your transaction to the information
              behind it.
            </p>
            {[
              {
                icon: BookOpen,
                title: "Your policy library",
                text: "Relevant passages, with verified quotations.",
              },
              {
                icon: Database,
                title: "Official sanctions data",
                text: "Full OFAC SDN names and aliases from your latest sync.",
              },
              {
                icon: FileCheck2,
                title: "A reviewable audit trail",
                text: "Original input, sources, model, and human review.",
              },
            ].map(({ icon: Icon, title, text }) => (
              <div className="guidance-item" key={title}>
                <Icon size={18} />
                <div>
                  <strong>{title}</strong>
                  <p>{text}</p>
                </div>
              </div>
            ))}
          </div>
          {(health.data?.ai.status !== "configured" ||
            health.data?.sanctions.status !== "ready") && (
            <div className="notice warning">
              <div>
                <strong>Finish connecting your workspace</strong>
                <p>
                  Add your Groq key and sync OFAC data before running an
                  evaluation.
                </p>
                <Link className="text-link" to="/sources">
                  Open data sources →
                </Link>
              </div>
            </div>
          )}
          <div className="aside-caption">
            An assessment supports your review. It does not approve or execute a
            payment.
          </div>
        </aside>
      </div>
    </>
  );
}
