import { useState } from "react";
import { ArrowUpRight, BookOpen, Send, Sparkles } from "lucide-react";
import { Link } from "../navigation";
import {
  ErrorNotice,
  Evidence,
  Field,
  PageHeading,
  Submit,
} from "../components";
import { api } from "../services/api";

export default function Assistant() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [asked, setAsked] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function ask(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    const form = new FormData(event.currentTarget);
    try {
      const response = await api("/query", {
        method: "POST",
        body: { query: question, topic: form.get("topic") || null },
      });
      setAsked(question);
      setResult(response);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="ASK YOUR KNOWLEDGE"
        title="Complex policies. Plain answers."
      >
        Ask a question, follow the citations, and see exactly where the answer
        comes from.
      </PageHeading>
      <div className="assistant-layout">
        <div>
          <form className="panel assistant-form" onSubmit={ask}>
            <div className="assistant-form-title">
              <span className="sparkle-icon">
                <Sparkles size={24} />
              </span>
              <div>
                <h2>What would you like to understand?</h2>
                <p>Answers are grounded in your uploaded policies.</p>
              </div>
            </div>
            <label className="sr-only" htmlFor="question">
              Your policy question
            </label>
            <textarea
              id="question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              required
              minLength={5}
              maxLength={2000}
              rows={4}
              placeholder="What due diligence does our policy require for a cross-border transfer?"
            />
            <div className="assistant-form-bottom">
              <select
                name="topic"
                aria-label="Limit question to a policy topic"
              >
                <option value="">Search all topics</option>
                {["aml", "kyc", "sanctions", "fraud", "general"].map((t) => (
                  <option key={t} value={t}>
                    {t.toUpperCase()}
                  </option>
                ))}
              </select>
              <Submit busy={busy}>
                Ask assistant <Send size={16} />
              </Submit>
            </div>
            <ErrorNotice message={error} />
          </form>
          {result ? (
            <section className="panel answer-panel" aria-live="polite">
              <div className="eyebrow">YOUR QUESTION</div>
              <h2>{asked}</h2>
              <div className="answer-text">{result.answer}</div>
              {result.limitations.length > 0 && (
                <div className="notice warning">
                  <div>
                    <strong>Limits of this answer</strong>
                    <ul>
                      {result.limitations.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
              <h3>
                Follow the evidence{" "}
                <span className="count-pill">{result.citations.length}</span>
              </h3>
              <Evidence citations={result.citations} />
            </section>
          ) : (
            <div className="question-suggestions">
              <span className="eyebrow">A FEW PLACES TO START</span>
              {[
                "When is enhanced due diligence required?",
                "What sanctions checks are required before a transfer?",
                "Which records must we keep for a KYC review?",
              ].map((text) => (
                <button
                  key={text}
                  onClick={() => {
                    setQuestion(text);
                    document.getElementById("question").focus();
                  }}
                >
                  {text}
                  <ArrowUpRight size={16} />
                </button>
              ))}
            </div>
          )}
        </div>
        <aside className="panel guidance-panel">
          <BookOpen size={28} />
          <h2>
            Your documents.
            <br />
            Your answers.
          </h2>
          <p>
            The assistant searches your policy library, then asks Groq to
            explain the relevant passages.
          </p>
          <div className="aside-rule" />
          <h3>Grounded, by design</h3>
          <p>
            Every accepted answer includes quotations checked against the
            original policy text.
          </p>
          <h3>Make the question specific</h3>
          <p>
            Use the terminology in your documents. If no relevant evidence is
            found, the assistant will ask for more.
          </p>
          <Link className="text-link" to="/policies">
            Browse policy library <ArrowUpRight size={15} />
          </Link>
          <p className="privacy-note">
            Questions and relevant policy excerpts are sent to Groq. Review its
            data terms before using confidential material.
          </p>
        </aside>
      </div>
    </>
  );
}
