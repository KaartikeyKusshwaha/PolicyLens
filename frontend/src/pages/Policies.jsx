import { useState } from "react";
import { useParams } from "react-router-dom";
import { Link, useNavigate } from "../navigation";
import {
  ArrowLeft,
  ArrowUpRight,
  BookOpen,
  FileText,
  Plus,
  Upload,
} from "lucide-react";
import {
  Empty,
  ErrorNotice,
  Field,
  formatDate,
  Loading,
  PageHeading,
  SearchBox,
  Submit,
  useResource,
} from "../components";
import { api } from "../services/api";

export function Policies() {
  const { data, error, loading, reload } = useResource("/policies");
  const [search, setSearch] = useState("");
  const [topic, setTopic] = useState("all");
  const filtered = data?.filter(
    (p) =>
      `${p.title} ${p.topic} ${p.version}`
        .toLowerCase()
        .includes(search.toLowerCase()) &&
      (topic === "all" || p.topic === topic),
  );
  return (
    <>
      <PageHeading
        eyebrow="YOUR SOURCE OF TRUTH"
        title="A library built on your policies."
        action={
          <Link className="button primary" to="/policies/new">
            <Plus size={17} /> Add policy
          </Link>
        }
      >
        Keep the documents that guide every assessment in one searchable place.
      </PageHeading>
      <p><Link className="button secondary" to="/policies/traceability">Open policy-to-control traceability</Link></p>
      <ErrorNotice message={error} retry={reload} />
      <section className="panel">
        <div className="library-toolbar">
          <SearchBox
            value={search}
            onChange={setSearch}
            placeholder="Search policy titles or topics…"
          />
          <select
            aria-label="Filter policies by topic"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          >
            <option value="all">All topics</option>
            {["aml", "kyc", "sanctions", "fraud", "general"].map((t) => (
              <option key={t} value={t}>
                {t.toUpperCase()}
              </option>
            ))}
          </select>
          <span className="muted">{data?.length || 0} documents</span>
        </div>
        {loading ? (
          <Loading />
        ) : filtered?.length ? (
          <div className="policy-grid">
            {filtered.map((p) => (
              <article className="policy-card" key={p.id}>
                <div className="policy-card-top">
                  <span className="document-icon">
                    <FileText size={24} />
                  </span>
                  <span className="topic-pill">{p.topic.toUpperCase()}</span>
                </div>
                <h2>{p.title}</h2>
                <p>Version {p.version}</p>
                <div className="policy-card-bottom">
                  <small>
                    Updated {new Date(p.updated_at).toLocaleDateString()}
                  </small>
                  <Link
                    className="icon-button"
                    aria-label={`View or edit ${p.title}`}
                    to={`/policies/${p.id}/edit`}
                  >
                    <ArrowUpRight size={18} />
                  </Link>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <Empty
            icon={BookOpen}
            title={
              data?.length
                ? "No matching policies"
                : "Make your knowledge the foundation."
            }
            action={
              <Link className="button secondary" to="/policies/new">
                <Upload size={16} /> Add your first policy
              </Link>
            }
          >
            {data?.length
              ? "Try another title or topic."
              : "Upload a PDF, DOCX, or text document—or paste the policy text. Your library starts empty."}
          </Empty>
        )}
      </section>
      <div className="subtle-note">
        <BookOpen size={16} />
        <p>
          Only documents in this library are used as policy authority. Public
          sanctions data adds screening evidence; it does not create policy
          rules.
        </p>
      </div>
    </>
  );
}

export function PolicyEditor() {
  const { id } = useParams();
  const resource = useResource(id ? `/policies/${id}` : "/policies");
  const [mode, setMode] = useState("text");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      if (mode === "file" && !id) {
        await api("/policies/file", { method: "POST", body: form });
      } else {
        await api(id ? `/policies/${id}` : "/policies", {
          method: id ? "PUT" : "POST",
          body: Object.fromEntries(form),
        });
      }
      navigate("/policies");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (id && resource.loading) return <Loading />;
  if (id && resource.error)
    return <ErrorNotice message={resource.error} retry={resource.reload} />;
  const policy = id ? resource.data : null;
  return (
    <>
      <PageHeading
        eyebrow="POLICY LIBRARY"
        title={
          id ? "Keep your policies current." : "Add knowledge. Build clarity."
        }
      >
        {id
          ? "Use a new version number. Existing assessments retain their original evidence."
          : "Your next assessment is only as useful as the policies behind it."}
      </PageHeading>
      <form className="panel form-panel editor-panel" onSubmit={submit}>
        {!id && (
          <div
            className="segmented"
            role="group"
            aria-label="Policy input type"
          >
            <button
              type="button"
              className={mode === "text" ? "selected" : ""}
              onClick={() => setMode("text")}
            >
              <FileText size={16} /> Paste text
            </button>
            <button
              type="button"
              className={mode === "file" ? "selected" : ""}
              onClick={() => setMode("file")}
            >
              <Upload size={16} /> Upload document
            </button>
          </div>
        )}
        <div className="form-grid">
          <Field label="Policy title" wide>
            <input
              name="title"
              required
              minLength={3}
              maxLength={180}
              defaultValue={policy?.title}
              placeholder="e.g. Customer due diligence policy"
            />
          </Field>
          <Field label="Topic">
            <select name="topic" defaultValue={policy?.topic || "general"}>
              {["general", "aml", "kyc", "sanctions", "fraud"].map((t) => (
                <option key={t} value={t}>
                  {t.toUpperCase()}
                </option>
              ))}
            </select>
          </Field>
          <Field
            label="Version"
            hint={
              id
                ? `Current version: ${policy.version}. Enter a different version.`
                : "Keep a clear record of which policy was used."
            }
          >
            <input
              name="version"
              required
              maxLength={30}
              defaultValue={policy?.version || "1.0"}
            />
          </Field>
          <Field label="Original source link (optional)" wide>
            <input
              name="source_url"
              type="url"
              defaultValue={policy?.source_url}
              maxLength={1000}
              placeholder="https://…"
            />
          </Field>
          {mode === "file" && !id ? (
            <Field
              label="Document"
              wide
              hint="PDF, DOCX, or UTF-8 TXT · up to 5 MB · PDFs must contain selectable text."
            >
              <div className="file-upload">
                <Upload size={26} />
                <strong>Choose a policy document</strong>
                <input
                  type="file"
                  name="file"
                  accept=".pdf,.docx,.txt"
                  required
                />
              </div>
            </Field>
          ) : (
            <Field
              label="Policy content"
              wide
              hint="50–300,000 characters. Include the complete rules and any exceptions."
            >
              <textarea
                name="content"
                rows={15}
                minLength={50}
                maxLength={300000}
                defaultValue={policy?.content}
                required
                placeholder="Paste the policy you want your assessments to follow…"
              />
            </Field>
          )}
        </div>
        {id && (
          <p className="muted">Last updated {formatDate(policy.updated_at)}</p>
        )}
        <ErrorNotice message={error} />
        <div className="form-actions">
          <Link to="/policies" className="text-link">
            <ArrowLeft size={15} /> Policy library
          </Link>
          <Submit busy={busy}>
            {id ? "Save new version" : "Add to library"}
          </Submit>
        </div>
      </form>
    </>
  );
}
