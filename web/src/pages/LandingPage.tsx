import { Link } from 'react-router-dom';
import { Icon } from '../components/Icons';
import type { IconName } from '../components/Icons';

const features: Array<{ icon: IconName; title: string; body: string }> = [
  {
    icon: 'layers',
    title: 'Autonomy that narrows',
    body: 'Five server-enforced levels from Observe to Custom. Higher levels expand what may be attempted; they never remove budgets, verification, approvals, or the gate.',
  },
  {
    icon: 'budget',
    title: 'Budgets that stop',
    body: 'Cost and token limits are checked before every provider call and after every response. Exhaustion is a terminal state, not a silent overspend.',
  },
  {
    icon: 'check',
    title: 'Verification before acceptance',
    body: 'Deterministic checks, JSON validation, failure-phrase detection, and optional independent verifier calls run before any result is called complete.',
  },
  {
    icon: 'gate',
    title: 'High-risk abstention',
    body: 'The Strong High-Risk Gate abstains when independent evidence is insufficient. With mock-only evidence, a high-risk task correctly refuses acceptance.',
  },
  {
    icon: 'evidence',
    title: 'Evidence ledger',
    body: 'Provider output, checks, verifier results, and gate decisions are content-addressed and recorded with provenance. Hashes prove integrity, not truth.',
  },
  {
    icon: 'flask',
    title: 'Offline-first demos',
    body: 'A deterministic mock provider exercises the real engine paths — failures, recovery, approvals, budget stops, and gate abstention — with no network calls.',
  },
];

const pipeline = [
  {
    title: 'Plan',
    detail: 'Interpret the task, risk class, autonomy, criteria, and route.',
    badge: 'Policy checked',
    tone: 'info',
  },
  {
    title: 'Execute',
    detail: 'Call the selected provider inside token, cost, and time limits.',
    badge: 'Budgeted',
    tone: 'info',
  },
  {
    title: 'Verify',
    detail: 'Run deterministic checks and optional independent verification.',
    badge: 'Evidence recorded',
    tone: 'success',
  },
  {
    title: 'Gate',
    detail: 'For high-risk acceptance, require independent evidence or abstain.',
    badge: 'Narrow veto',
    tone: 'warn',
  },
  {
    title: 'Audit',
    detail: 'Persist status, evidence, approvals, and every policy decision.',
    badge: 'Append-only',
    tone: 'neutral',
  },
];

export function LandingPage() {
  return (
    <div className="landing">
      <section className="hero">
        <div className="hero-bg" aria-hidden="true" />
        <div className="container hero-inner">
          <div className="hero-copy">
            <div className="hero-eyebrow">
              <span className="eyebrow-dot" />
              CREST 1.0 · local-first inference control plane
            </div>
            <h1>
              Agents propose.
              <br />
              <span className="accent-text">Evidence decides.</span>
            </h1>
            <p className="hero-lead">
              CREST is an outcome-constrained execution layer for AI agents. It grants autonomous
              capability only when policy, budgets, verification, and independently reviewed
              evidence support the result — and abstains when they do not.
            </p>
            <div className="hero-actions">
              <Link to="/app" className="btn btn-primary btn-lg">
                Open the app <Icon name="arrow-right" size={18} />
              </Link>
              <Link to="/docs" className="btn btn-outline btn-lg">
                Read the docs
              </Link>
            </div>
            <div className="hero-facts">
              <span>
                <Icon name="lock" size={14} /> Local-first
              </span>
              <span>
                <Icon name="layers" size={14} /> 5 autonomy levels
              </span>
              <span>
                <Icon name="flask" size={14} /> Offline mock provider
              </span>
              <span>
                <Icon name="database" size={14} /> SQLite WAL
              </span>
            </div>
          </div>

          <div className="hero-visual" aria-label="Illustrative execution path">
            <div className="hero-panel">
              <div className="hero-panel-head">
                <div>
                  <span className="panel-kicker">Execution path</span>
                  <strong>Outcome-constrained run</strong>
                </div>
                <span className="panel-live">
                  <span className="status-dot status-dot-online" /> Control flow
                </span>
              </div>
              <ol className="pipeline">
                {pipeline.map((step, index) => (
                  <li key={step.title} className="pipeline-step">
                    <span className="pipeline-index">{String(index + 1).padStart(2, '0')}</span>
                    <div className="pipeline-body">
                      <div className="pipeline-title">
                        <strong>{step.title}</strong>
                        <span className={`badge tone-${step.tone}`}>{step.badge}</span>
                      </div>
                      <p>{step.detail}</p>
                    </div>
                  </li>
                ))}
              </ol>
              <div className="hero-panel-foot">
                <Icon name="shield" size={15} />
                <span>Approval, verification, and the gate are enforced server-side.</span>
              </div>
            </div>
            <div className="hero-caveat">
              Illustration of the control flow. Not a claim of live reliability.
            </div>
          </div>
        </div>
      </section>

      <section className="section section-muted">
        <div className="container">
          <div className="section-heading">
            <span className="eyebrow">The problem</span>
            <h2>Agents can act. Proving the outcome is harder.</h2>
            <p>
              A model response is not evidence that a task succeeded. CREST separates learning,
              verification, and admission so that execution authority is a policy decision — not a
              side effect of a fluent answer.
            </p>
          </div>
          <div className="problem-grid">
            <div className="problem-card">
              <Icon name="alert" size={22} />
              <h3>Fluent is not correct</h3>
              <p>
                A convincing answer can still fail acceptance criteria, return malformed JSON, or
                contain a failure phrase. CREST checks before accepting.
              </p>
            </div>
            <div className="problem-card">
              <Icon name="budget" size={22} />
              <h3>Retries can spend silently</h3>
              <p>
                Recovery loops are useful only inside explicit cost, token, and time limits. CREST
                fails closed when a budget cannot support the next call.
              </p>
            </div>
            <div className="problem-card">
              <Icon name="gate" size={22} />
              <h3>High-risk needs independence</h3>
              <p>
                For high-risk acceptance, one model agreeing with itself is not enough. The gate
                abstains when independent evidence is insufficient.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="section-heading">
            <span className="eyebrow">What CREST does</span>
            <h2>One control plane for the whole execution path.</h2>
            <p>
              Every task carries its risk class, autonomy level, provider route, budgets, acceptance
              criteria, and approval state. Every decision is persisted.
            </p>
          </div>
          <div className="feature-grid">
            {features.map((feature) => (
              <article key={feature.title} className="feature-card">
                <span className="feature-icon">
                  <Icon name={feature.icon} size={21} />
                </span>
                <h3>{feature.title}</h3>
                <p>{feature.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section section-dark">
        <div className="container">
          <div className="section-heading section-heading-light">
            <span className="eyebrow">How it works</span>
            <h2>Authority is granted step by step, never assumed.</h2>
          </div>
          <div className="how-grid">
            <div className="how-step">
              <span className="how-number">01</span>
              <h3>Define the task</h3>
              <p>
                Choose a risk class, autonomy level, provider route, budgets, timeout, output format,
                and acceptance criteria. Custom policies at level 5 can only narrow permissions.
              </p>
            </div>
            <div className="how-step">
              <span className="how-number">02</span>
              <h3>Execute under policy</h3>
              <p>
                The engine re-checks autonomy, provider access, and budgets before every call. High-risk
                and external actions pause for a fresh approval bound to the policy fingerprint.
              </p>
            </div>
            <div className="how-step">
              <span className="how-number">03</span>
              <h3>Verify and gate</h3>
              <p>
                Deterministic checks run first. The Strong High-Risk Gate then accepts, abstains, or
                rejects based on evidence sufficiency — never on confidence alone.
              </p>
            </div>
            <div className="how-step">
              <span className="how-number">04</span>
              <h3>Record and review</h3>
              <p>
                Results, evidence hashes, approvals, gate reasons, and audit events are stored locally.
                Export a task report or a full JSON backup at any time.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="section section-muted">
        <div className="container research-grid">
          <div>
            <span className="eyebrow">Research foundation</span>
            <h2>Built on a measured gate, with the caveat attached.</h2>
            <p>
              CREST grew out of a research runtime on capability admission and recovery evidence. The
              Strong High-Risk Gate is a narrow runtime veto: it does not replace verification, and it
              does not create a safety guarantee.
            </p>
            <div className="research-actions">
              <a
                className="btn btn-outline"
                href="https://github.com/manansulya01/Crest/blob/feat/crest-1.0-product/docs/CREST_RESEARCH_BOOK.md"
                target="_blank"
                rel="noreferrer"
              >
                <Icon name="book" size={16} /> Read the research book
              </a>
              <Link to="/security" className="btn btn-ghost">
                Security model <Icon name="arrow-right" size={15} />
              </Link>
            </div>
          </div>
          <blockquote className="research-quote">
            <p>
              “In the Cycle 3 simulation, the Strong High-Risk Gate reduced risk-weighted loss by
              25.9% by abstaining on high-risk tasks with insufficient independent evidence.”
            </p>
            <footer>
              <BadgeLabel />
              Simulation result. It is not a live reliability claim and does not transfer
              automatically to real provider traffic.
            </footer>
          </blockquote>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="section-heading">
            <span className="eyebrow">Scope and honesty</span>
            <h2>What CREST is not</h2>
          </div>
          <div className="not-grid">
            <div>
              <Icon name="x" size={18} />
              <p>Not a guarantee that an agent's output is correct or safe.</p>
            </div>
            <div>
              <Icon name="x" size={18} />
              <p>Not a signed attestation service; evidence hashes prove integrity, not origin.</p>
            </div>
            <div>
              <Icon name="x" size={18} />
              <p>Not a production-hardened multi-tenant platform; the posture is Level 3 supervised use.</p>
            </div>
            <div>
              <Icon name="x" size={18} />
              <p>Not a native desktop package; the desktop launcher starts the local server and opens a browser.</p>
            </div>
            <div>
              <Icon name="x" size={18} />
              <p>Not validated against live external providers in this release; mock paths are the tested path.</p>
            </div>
            <div>
              <Icon name="x" size={18} />
              <p>Not an autonomous money-spender: external calls and spending are opt-in and off by default.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="section cta-section">
        <div className="container cta-card">
          <div>
            <span className="eyebrow">Start locally</span>
            <h2>Run the control plane on your machine.</h2>
            <p>
              Install the product extra, start the API, build the web app, and open the launcher. The
              offline mock provider works without a key.
            </p>
          </div>
          <div className="cta-actions">
            <Link to="/app" className="btn btn-primary btn-lg">
              Open the app <Icon name="arrow-right" size={18} />
            </Link>
            <Link to="/docs" className="btn btn-outline btn-lg">
              Installation guide
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

function BadgeLabel() {
  return <span className="quote-tag">Cycle 3 simulation</span>;
}
