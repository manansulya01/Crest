import { Link } from 'react-router-dom';
import { Icon } from '../components/Icons';
import type { IconName } from '../components/Icons';

const principles: Array<{ icon: IconName; title: string; body: string }> = [
  {
    icon: 'lock',
    title: 'Local-first by default',
    body: 'The server binds to 127.0.0.1, the database lives under ~/.crest, and no analytics or telemetry are included. External provider calls are disabled until explicitly enabled.',
  },
  {
    icon: 'shield',
    title: 'Fail closed',
    body: 'Unknown actions, unknown policy keys, exceeded autonomy, missing keys, disabled providers, insufficient budget, expired approvals, and unverifiable outcomes all deny or abstain rather than proceed.',
  },
  {
    icon: 'key',
    title: 'Secrets stay out of state',
    body: 'Provider API keys are read from process environment variables at call time. They are never written to SQLite, returned by the API, included in exports, or printed in audit detail.',
  },
  {
    icon: 'gate',
    title: 'Independence is explicit',
    body: 'Evidence carries an independence flag. A verifier using the same provider and model as the generator is recorded as not independent, and cannot satisfy the high-risk gate.',
  },
  {
    icon: 'evidence',
    title: 'Content-addressed records',
    body: 'Evidence is stored with SHA-256 hashes and provenance so tampering is detectable on inspection. Hashing is integrity, not a signature or an attestation of truth.',
  },
  {
    icon: 'audit',
    title: 'Append-only audit',
    body: 'Task, policy, approval, execution, verification, gate, provider, routing, and settings events are persisted server-side. Redaction runs before persistence.',
  },
];

const enforcement: Array<{ control: string; where: string; failure: string }> = [
  {
    control: 'Global autonomy ceiling',
    where: 'Task creation, task update, every execution step',
    failure: 'AUTONOMY_EXCEEDS_GLOBAL_MAX',
  },
  {
    control: 'Custom policy',
    where: 'Policy module at level 5 only',
    failure: 'Unknown actions and keys rejected',
  },
  {
    control: 'Provider access',
    where: 'Before every provider call',
    failure: 'Disabled, missing key, or external calls off → denied',
  },
  {
    control: 'Cost and token budgets',
    where: 'Pre-flight and after every response',
    failure: 'budget_exhausted terminal state',
  },
  {
    control: 'Approvals',
    where: 'Engine, bound to policy fingerprint',
    failure: 'Expired, consumed, or fingerprint mismatch → denied',
  },
  {
    control: 'Verification',
    where: 'After provider output, before acceptance',
    failure: 'Failed verification is never reported complete',
  },
  {
    control: 'High-Risk Gate',
    where: 'After verification for high-risk acceptance',
    failure: 'ABSTAIN when independent evidence is insufficient',
  },
];

const boundaries: Array<{ title: string; body: string; tone: 'success' | 'warn' | 'danger' }> = [
  {
    title: 'In scope',
    tone: 'success',
    body: 'Single-user local deployment; one trusted operator; provider credentials supplied by that operator; tasks created through the local API.',
  },
  {
    title: 'Partially addressed',
    tone: 'warn',
    body: 'Multi-process access to the SQLite database, local browser threat models, retention of sensitive task content, and optional bearer authentication. Controls exist, but they are not hardened against a hostile local administrator.',
  },
  {
    title: 'Out of scope',
    tone: 'danger',
    body: 'Multi-tenant isolation, remote untrusted users, signed attestations, supply-chain guarantees for model providers, and protection against an attacker who already controls the host or the Python process.',
  },
];

export function SecurityPage() {
  return (
    <div className="security-page">
      <section className="page-hero page-hero-security">
        <div className="container">
          <span className="eyebrow">Security model</span>
          <h1>Authority is explicit, bounded, and auditable.</h1>
          <p>
            CREST is an execution control plane, not a safety guarantee. This page states what the
            system enforces, where it enforces it, and which threats remain outside its scope.
          </p>
          <div className="posture-banner">
            <Icon name="shield" size={18} />
            <div>
              <strong>Security posture: Level 3 — supervised personal use.</strong>
              <span>
                Suitable for a single operator on a local machine. Not production-ready for untrusted
                multi-tenant traffic.
              </span>
            </div>
          </div>
        </div>
      </section>

      <section className="section section-muted">
        <div className="container">
          <div className="section-heading">
            <span className="eyebrow">Principles</span>
            <h2>Six properties the product is built around.</h2>
          </div>
          <div className="security-grid">
            {principles.map((principle) => (
              <article key={principle.title} className="security-card">
                <span className="security-icon">
                  <Icon name={principle.icon} size={20} />
                </span>
                <h3>{principle.title}</h3>
                <p>{principle.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="section-heading">
            <span className="eyebrow">Enforcement</span>
            <h2>The frontend is a client. The engine is the authority.</h2>
            <p>
              Every control below is re-checked server-side. A modified browser, a direct API call, or
              a stale page cannot grant authority the engine does not allow.
            </p>
          </div>
          <div className="docs-table-wrap security-table-wrap">
            <table className="docs-table">
              <thead>
                <tr>
                  <th>Control</th>
                  <th>Enforced at</th>
                  <th>Failure behavior</th>
                </tr>
              </thead>
              <tbody>
                {enforcement.map((row) => (
                  <tr key={row.control}>
                    <td>
                      <strong>{row.control}</strong>
                    </td>
                    <td>{row.where}</td>
                    <td className="muted">{row.failure}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="section section-muted">
        <div className="container">
          <div className="section-heading">
            <span className="eyebrow">Trust boundaries</span>
            <h2>What the model protects — and what it does not.</h2>
          </div>
          <div className="boundary-grid">
            {boundaries.map((boundary) => (
              <article key={boundary.title} className={`boundary-card boundary-${boundary.tone}`}>
                <h3>{boundary.title}</h3>
                <p>{boundary.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="section-heading">
            <span className="eyebrow">Evidence integrity</span>
            <h2>What a hash proves.</h2>
          </div>
          <div className="evidence-properties">
            <div className="evidence-property">
              <Icon name="check" size={18} />
              <div>
                <strong>Integrity</strong>
                <p>
                  A content hash changes if the stored content changes. This makes accidental or
                  in-place modification detectable when evidence is inspected or exported.
                </p>
              </div>
            </div>
            <div className="evidence-property">
              <Icon name="check" size={18} />
              <div>
                <strong>Provenance metadata</strong>
                <p>
                  Each record carries a source type, source id, execution id, independence flag, and
                  timestamps, so a reviewer can trace how it was produced.
                </p>
              </div>
            </div>
            <div className="evidence-property">
              <Icon name="x" size={18} />
              <div>
                <strong>Not a signature</strong>
                <p>
                  CREST does not sign evidence with a key held outside the local process. A hash alone
                  does not prove who produced the content, and does not prove the content is true.
                </p>
              </div>
            </div>
            <div className="evidence-property">
              <Icon name="x" size={18} />
              <div>
                <strong>Not a truth oracle</strong>
                <p>
                  Verification checks acceptance criteria and output format. It does not establish
                  that a model's claims about the world are correct.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section section-dark">
        <div className="container">
          <div className="section-heading section-heading-light">
            <span className="eyebrow">Operational guidance</span>
            <h2>Running it responsibly.</h2>
          </div>
          <div className="guidance-grid">
            <div>
              <span className="guidance-number">01</span>
              <h3>Keep it local</h3>
              <p>
                Bind to 127.0.0.1. Do not expose the API to a network without a reverse proxy,
                authentication, TLS, and a separate security review.
              </p>
            </div>
            <div>
              <span className="guidance-number">02</span>
              <h3>Start offline</h3>
              <p>
                Use the mock provider to validate task design, criteria, budgets, and approval flows
                before enabling any external provider.
              </p>
            </div>
            <div>
              <span className="guidance-number">03</span>
              <h3>Enable spend deliberately</h3>
              <p>
                External calls and spending are off by default. Configure pricing, set tight budgets,
                and keep external approval enabled when you turn them on.
              </p>
            </div>
            <div>
              <span className="guidance-number">04</span>
              <h3>Review abstentions</h3>
              <p>
                An ABSTAIN is a successful refusal, not a bug. Inspect the evidence and gate reason
                before rerunning with stronger independent verification.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="section-heading">
            <span className="eyebrow">Reporting</span>
            <h2>Found a problem?</h2>
            <p>
              Security issues should be reported privately through the repository's security policy
              rather than a public issue. Include reproduction steps, affected version, and expected
              versus actual behavior. Do not include live credentials.
            </p>
          </div>
          <div className="security-cta">
            <a
              className="btn btn-outline"
              href="https://github.com/manansulya01/Crest/security"
              target="_blank"
              rel="noreferrer"
            >
              <Icon name="github" size={16} /> Repository security
            </a>
            <a
              className="btn btn-ghost"
              href="https://github.com/manansulya01/Crest/blob/feat/crest-1.0-product/docs/security-model.md"
              target="_blank"
              rel="noreferrer"
            >
              <Icon name="book" size={16} /> Full security model
            </a>
            <Link to="/docs" className="btn btn-ghost">
              Documentation <Icon name="arrow-right" size={15} />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
