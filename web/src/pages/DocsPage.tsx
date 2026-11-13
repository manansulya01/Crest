import { Link } from 'react-router-dom';
import { Icon } from '../components/Icons';
import type { IconName } from '../components/Icons';

const quickstart = `# 1. Install the Python package with product extras
pip install -e ".[product]"

# 2. Build the web app (once)
cd web
npm install
npm run build
cd ..

# 3. Start the API (serves the built app too)
python -m uvicorn crest.api:app --host 127.0.0.1 --port 8000

# 4. Or use the desktop launcher
python crest_desktop.py`;

const apiExample = `# Health and diagnostics
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/diagnostics

# Create an offline task
curl -X POST http://127.0.0.1:8000/api/v1/tasks \\
  -H "Content-Type: application/json" \\
  -d '{
    "title": "Summarize the release notes",
    "description": "Return a short summary.",
    "risk_class": "low",
    "autonomy_level": 3,
    "provider": "mock",
    "model": "mock-fast",
    "acceptance_criteria": ["CREST"]
  }'

# Execute and wait for the terminal state
curl -X POST "http://127.0.0.1:8000/api/v1/tasks/<task_id>/execute?wait=true"`;

const levels: Array<{ level: string; name: string; body: string; tone: string }> = [
  {
    level: '1',
    name: 'Observe',
    body: 'Plans and records intent. Provider calls are denied. Useful for dry runs and policy review.',
    tone: 'info',
  },
  {
    level: '2',
    name: 'Assisted',
    body: 'Pauses for a fresh human approval before the provider call. Every approval is bound to a policy fingerprint.',
    tone: 'info',
  },
  {
    level: '3',
    name: 'Bounded',
    body: 'Default posture. Executes within budgets and verification, with recovery limited to a fixed number of attempts.',
    tone: 'success',
  },
  {
    level: '4',
    name: 'Adaptive',
    body: 'Allows bounded adaptation inside the same budgets, verification, and gate. Requires explicit elevation.',
    tone: 'warn',
  },
  {
    level: '5',
    name: 'Custom',
    body: 'Adds an optional per-task policy that can only narrow permissions. Unknown actions and keys fail closed.',
    tone: 'warn',
  },
];

const endpoints: Array<{ method: string; path: string; body: string }> = [
  { method: 'GET', path: '/api/v1/health', body: 'Liveness and version.' },
  { method: 'GET', path: '/api/v1/diagnostics', body: 'Runtime, database integrity, provider and safety state.' },
  { method: 'GET', path: '/api/v1/tasks', body: 'Paginated task list with status, risk, and search filters.' },
  { method: 'POST', path: '/api/v1/tasks', body: 'Create a task; validates autonomy, budgets, routing, and policy.' },
  { method: 'GET', path: '/api/v1/tasks/{id}', body: 'Full task record with plan, executions, evidence, approvals, and events.' },
  { method: 'PATCH', path: '/api/v1/tasks/{id}', body: 'Edit a task; resets pending state and expires outstanding approvals.' },
  { method: 'DELETE', path: '/api/v1/tasks/{id}', body: 'Soft-delete a task; audit events remain.' },
  { method: 'POST', path: '/api/v1/tasks/{id}/plan', body: 'Generate and persist a deterministic plan.' },
  { method: 'POST', path: '/api/v1/tasks/{id}/execute', body: 'Execute under policy; optionally wait for the terminal state.' },
  { method: 'POST', path: '/api/v1/tasks/{id}/approve', body: 'Approve or reject a pending decision.' },
  { method: 'POST', path: '/api/v1/tasks/{id}/cancel', body: 'Request cooperative cancellation.' },
  { method: 'GET', path: '/api/v1/tasks/{id}/report', body: 'Download a JSON task report.' },
  { method: 'GET', path: '/api/v1/evidence', body: 'Paginated evidence ledger with kind, status, task, and search filters.' },
  { method: 'GET', path: '/api/v1/audit', body: 'Paginated audit events with event type, task, and search filters.' },
  { method: 'GET', path: '/api/v1/approvals', body: 'Approval queue filtered by status.' },
  { method: 'GET', path: '/api/v1/providers', body: 'Provider configuration and status; never returns secrets.' },
  { method: 'PUT', path: '/api/v1/providers/{id}', body: 'Update provider routing configuration.' },
  { method: 'POST', path: '/api/v1/providers/{id}/test', body: 'Explicit connection test; requires external calls when applicable.' },
  { method: 'GET', path: '/api/v1/routing', body: 'Routing rules and fallback setting.' },
  { method: 'PUT', path: '/api/v1/routing', body: 'Replace routing rules.' },
  { method: 'GET', path: '/api/v1/settings', body: 'Current global settings and ceilings.' },
  { method: 'PUT', path: '/api/v1/settings', body: 'Update settings with server-side validation.' },
  { method: 'GET', path: '/api/v1/stats/overview', body: 'Dashboard aggregates and recent activity.' },
  { method: 'GET', path: '/api/v1/budgets/summary', body: 'Budget limits and per-task usage.' },
  { method: 'GET', path: '/api/v1/export', body: 'Download a full JSON backup without credentials.' },
];

const links: Array<{ icon: IconName; title: string; body: string; href: string }> = [
  {
    icon: 'book',
    title: 'Research book',
    body: 'The full research record: questions, experiments, benchmarks, negative results, and limits.',
    href: 'https://github.com/manansulya01/Crest/blob/feat/crest-1.0-product/docs/CREST_RESEARCH_BOOK.md',
  },
  {
    icon: 'terminal',
    title: 'Installation guide',
    body: 'Fresh-install steps, platform notes, configuration, and troubleshooting.',
    href: 'https://github.com/manansulya01/Crest/blob/feat/crest-1.0-product/docs/CREST_1_0_INSTALLATION.md',
  },
  {
    icon: 'shield',
    title: 'Security model',
    body: 'Threat model, trust boundaries, enforcement points, and known limitations.',
    href: 'https://github.com/manansulya01/Crest/blob/feat/crest-1.0-product/docs/security-model.md',
  },
  {
    icon: 'layers',
    title: 'Architecture',
    body: 'How the research runtime, product engine, database, API, and web app fit together.',
    href: 'https://github.com/manansulya01/Crest/blob/feat/crest-1.0-product/docs/architecture.md',
  },
];

export function DocsPage() {
  return (
    <div className="docs-page">
      <section className="page-hero">
        <div className="container">
          <span className="eyebrow">Documentation</span>
          <h1>Run CREST locally, end to end.</h1>
          <p>
            CREST 1.0 ships a Python engine, a FastAPI backend, a React web app, and an offline mock
            provider. The quickstart below is the validated path: no external provider keys and no
            network spend are required.
          </p>
          <div className="page-hero-actions">
            <Link to="/app" className="btn btn-primary">
              Open the app <Icon name="arrow-right" size={16} />
            </Link>
            <Link to="/security" className="btn btn-outline">
              Read the security model
            </Link>
          </div>
        </div>
      </section>

      <div className="container docs-layout">
        <aside className="docs-toc" aria-label="On this page">
          <span className="docs-toc-title">On this page</span>
          <a href="#quickstart">Quickstart</a>
          <a href="#concepts">Core concepts</a>
          <a href="#autonomy">Autonomy levels</a>
          <a href="#offline">Offline demos</a>
          <a href="#api">HTTP API</a>
          <a href="#cli">CLI</a>
          <a href="#configuration">Configuration</a>
          <a href="#limits">Known limits</a>
          <a href="#more">Further reading</a>
        </aside>

        <article className="docs-body">
          <section id="quickstart" className="docs-section">
            <h2>Quickstart</h2>
            <p>
              Requirements: Python 3.11+ and Node.js 20+. The product extra adds FastAPI, Uvicorn, and
              HTTPX. The default data directory is <code className="inline-code">~/.crest</code>; set{' '}
              <code className="inline-code">CREST_DATA_DIR</code> to override it.
            </p>
            <pre className="code-panel docs-code">{quickstart}</pre>
            <p className="docs-note">
              <Icon name="info" size={15} /> The API binds to <code className="inline-code">127.0.0.1</code>{' '}
              by default. The built web app is served by the API when{' '}
              <code className="inline-code">web/dist</code> exists. Vite dev mode proxies{' '}
              <code className="inline-code">/api</code> to the backend.
            </p>
          </section>

          <section id="concepts" className="docs-section">
            <h2>Core concepts</h2>
            <div className="docs-card-grid">
              <div className="docs-mini-card">
                <h3>Task</h3>
                <p>
                  A unit of work with a risk class, autonomy level, provider route, cost and token
                  budgets, timeout, output format, acceptance criteria, and optional demo scenario.
                </p>
              </div>
              <div className="docs-mini-card">
                <h3>Plan</h3>
                <p>
                  A deterministic, persisted sequence of steps. Planning is always allowed; execution
                  steps are individually authorized.
                </p>
              </div>
              <div className="docs-mini-card">
                <h3>Execution</h3>
                <p>
                  One attempt with ordered steps, usage accounting, errors, and cancellation state.
                  Interrupted runs are marked interrupted, never complete.
                </p>
              </div>
              <div className="docs-mini-card">
                <h3>Evidence</h3>
                <p>
                  Content-addressed records for provider output, deterministic verification, verifier
                  results, and gate decisions, each with provenance and an independence flag.
                </p>
              </div>
              <div className="docs-mini-card">
                <h3>Approval</h3>
                <p>
                  A human decision bound to the current policy fingerprint. Approvals expire after one
                  hour, and editing a task invalidates them.
                </p>
              </div>
              <div className="docs-mini-card">
                <h3>Gate decision</h3>
                <p>
                  ACCEPT, ABSTAIN, or REJECT. High-risk acceptance requires independent evidence; with
                  mock-only evidence the gate abstains.
                </p>
              </div>
            </div>
          </section>

          <section id="autonomy" className="docs-section">
            <h2>Autonomy levels</h2>
            <p>
              The global ceiling defaults to level 3. Levels 4 and 5 require explicit elevation in
              Settings or the Autonomy page. No level bypasses budgets, verification, or the gate.
            </p>
            <div className="docs-level-list">
              {levels.map((level) => (
                <div key={level.level} className="docs-level">
                  <span className={`docs-level-number tone-bg-${level.tone}`}>{level.level}</span>
                  <div>
                    <h3>{level.name}</h3>
                    <p>{level.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section id="offline" className="docs-section">
            <h2>Offline demos</h2>
            <p>
              The mock provider is deterministic and makes no network calls. Demo scenarios exercise
              the real engine paths: success, verification failure, recovery, budget exhaustion,
              observe-mode denial, assisted approval, high-risk gate abstention, and custom-policy
              denial.
            </p>
            <p>
              Open <Link to="/app/demos">Offline demos</Link> in the app. The high-risk demo pauses for
              approval first; after approval, mock-only evidence is insufficient and the task
              abstains. That is the intended behavior, not a failure.
            </p>
            <p className="docs-note">
              <Icon name="alert" size={15} /> Simulated output is labelled as such throughout the app.
              It is not evidence of live model reliability.
            </p>
          </section>

          <section id="api" className="docs-section">
            <h2>HTTP API</h2>
            <p>
              The interactive OpenAPI docs are served at{' '}
              <a href="/api/docs" target="_blank" rel="noreferrer" className="inline-link">
                /api/docs <Icon name="external" size={12} />
              </a>
              . All product routes are under <code className="inline-code">/api/v1</code>. If{' '}
              <code className="inline-code">CREST_API_TOKEN</code> is set on the server, every route
              except health requires a bearer token.
            </p>
            <pre className="code-panel docs-code">{apiExample}</pre>
            <div className="docs-table-wrap">
              <table className="docs-table">
                <thead>
                  <tr>
                    <th>Method</th>
                    <th>Path</th>
                    <th>Purpose</th>
                  </tr>
                </thead>
                <tbody>
                  {endpoints.map((endpoint) => (
                    <tr key={`${endpoint.method}-${endpoint.path}`}>
                      <td>
                        <span className={`method method-${endpoint.method.toLowerCase()}`}>
                          {endpoint.method}
                        </span>
                      </td>
                      <td>
                        <code className="inline-code">{endpoint.path}</code>
                      </td>
                      <td>{endpoint.body}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section id="cli" className="docs-section">
            <h2>CLI</h2>
            <p>
              The original research runtime CLI remains available and unchanged. The product app does
              not replace it; both operate on the same repository.
            </p>
            <pre className="code-panel docs-code">{`crest init --root .
crest verify --action modify_file --recovery restore_from_snapshot --target README.md --scope '*'
crest exec filesystem modify_file --arg path=README.md --arg content='hello'
crest status
crest audit`}</pre>
            <p>
              See <code className="inline-code">docs/cli.md</code> for the full command reference.
            </p>
          </section>

          <section id="configuration" className="docs-section">
            <h2>Configuration</h2>
            <div className="docs-table-wrap">
              <table className="docs-table">
                <thead>
                  <tr>
                    <th>Variable</th>
                    <th>Default</th>
                    <th>Meaning</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>
                      <code className="inline-code">CREST_DATA_DIR</code>
                    </td>
                    <td>
                      <code className="inline-code">~/.crest</code>
                    </td>
                    <td>SQLite database, WAL files, and local state.</td>
                  </tr>
                  <tr>
                    <td>
                      <code className="inline-code">CREST_API_TOKEN</code>
                    </td>
                    <td>unset</td>
                    <td>When set, requires a bearer token on API routes except health.</td>
                  </tr>
                  <tr>
                    <td>
                      <code className="inline-code">CREST_HOST</code> /{' '}
                      <code className="inline-code">CREST_PORT</code>
                    </td>
                    <td>
                      <code className="inline-code">127.0.0.1:8000</code>
                    </td>
                    <td>Desktop launcher bind address.</td>
                  </tr>
                  <tr>
                    <td>
                      <code className="inline-code">GEMINI_API_KEY</code>
                    </td>
                    <td>unset</td>
                    <td>Read from the environment for the Gemini adapter; never persisted.</td>
                  </tr>
                  <tr>
                    <td>
                      <code className="inline-code">VITE_API_BASE</code>
                    </td>
                    <td>empty (same origin)</td>
                    <td>Build-time API base URL for a separately hosted frontend.</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p>
              Settings, provider configuration, routing rules, and safety switches are managed in the
              app and persisted in SQLite. External calls are disabled by default.
            </p>
          </section>

          <section id="limits" className="docs-section">
            <h2>Known limits</h2>
            <ul className="docs-list">
              <li>
                CREST is Level 3 — supervised personal use. It is not a production-hardened
                multi-tenant service and does not provide an unconditional safety guarantee.
              </li>
              <li>
                Evidence is content-addressed but not signed. Hashes prove integrity, not origin or
                truth.
              </li>
              <li>
                Live external providers were not validated in this release. The tested execution path
                is the offline mock provider.
              </li>
              <li>
                The desktop launcher is browser-based. It starts the local server and opens the app; it
                is not a packaged native binary.
              </li>
              <li>
                Cost accounting depends on per-provider pricing configured by the operator. Unset
                pricing records $0 while token limits remain authoritative.
              </li>
            </ul>
          </section>

          <section id="more" className="docs-section">
            <h2>Further reading</h2>
            <div className="docs-link-grid">
              {links.map((link) => (
                <a
                  key={link.title}
                  className="docs-link-card"
                  href={link.href}
                  target="_blank"
                  rel="noreferrer"
                >
                  <span className="docs-link-icon">
                    <Icon name={link.icon} size={19} />
                  </span>
                  <div>
                    <h3>
                      {link.title} <Icon name="external" size={12} />
                    </h3>
                    <p>{link.body}</p>
                  </div>
                </a>
              ))}
            </div>
          </section>
        </article>
      </div>
    </div>
  );
}
