# CREST 1.0 Web App

React 19 + TypeScript + Vite single-page application for the CREST 1.0 product
layer. It includes the public product site and the control-plane app. There is
no external UI component library; the design system is defined in
`src/styles.css` with light and dark themes.

## Routes

| Path | Page |
| --- | --- |
| `/` | Product landing page |
| `/docs` | Product documentation |
| `/security` | Security model |
| `/app` | Dashboard |
| `/app/tasks` | Task list |
| `/app/tasks/new` | Create a task |
| `/app/tasks/:taskId` | Task detail: result, plan, executions, evidence, approvals, events |
| `/app/approvals` | Approval queue |
| `/app/autonomy` | Autonomy ceiling and permission matrix |
| `/app/providers` | Provider configuration and connection tests |
| `/app/routing` | Risk-class routing rules |
| `/app/evidence` | Evidence ledger |
| `/app/audit` | Audit log |
| `/app/budgets` | Budget limits and usage |
| `/app/demos` | Offline demo scenarios |
| `/app/settings` | Global settings, token, export, retention |
| `/app/system` | Runtime and database diagnostics |

Unknown routes render a 404 page.

## Development

Start the backend first:

```bash
python -m uvicorn crest.api:app --host 127.0.0.1 --port 8000
```

Then:

```bash
cd web
npm install
npm run dev
```

Vite serves <http://127.0.0.1:5173> and proxies `/api` to
`http://127.0.0.1:8000` (see `vite.config.ts`).

## Build

```bash
npm run build
```

The build runs `tsc -b` and Vite, and writes `dist/`. The FastAPI backend serves
`dist/` when it exists, including an SPA fallback for client-side routes.

Current build output (validated):

- 55 modules
- JS: ~452 kB (~126 kB gzip)
- CSS: ~63 kB (~11.6 kB gzip)

## API access

All requests go through `src/lib/api.ts`. The base URL is empty by default
(same origin). Set `VITE_API_BASE` at build time for a separately hosted
frontend.

If the backend sets `CREST_API_TOKEN`, enter the token in **Settings**. It is
stored in `localStorage` under `crest.token` and sent as a bearer token. The
token is never stored server-side.

## Structure

```text
src/
  App.tsx              router composition
  main.tsx             bootstrap
  styles.css           design tokens, themes, all page styles
  components/
    AppLayout.tsx      app shell, sidebar, topbar, connection status
    PublicLayout.tsx   public header/footer
    TaskForm.tsx       create/edit form and client-side validation
    EvidenceViewer.tsx evidence detail and content viewer
    Modal.tsx          accessible confirmation modal
    ThemeToggle.tsx    light/dark switch
    UI.tsx             cards, badges, notices, loading/empty/error states
    Icons.tsx          inline SVG icon set
  lib/
    api.ts             typed API client
    types.ts           shared types and response helpers
    useApi.ts          loading/error/reload hook
    theme.tsx          theme provider and persistence
    toast.tsx          toast provider
    format.ts          dates, numbers, currency, status labels
  pages/               public and app pages
```

## Behavior notes

- The frontend is not the authority. Autonomy, permissions, budgets,
  approvals, verification, and the gate are enforced by the backend.
- Demo scenarios run the real engine paths with the offline mock provider.
  High-risk mock evidence produces `ABSTAIN` after approval by design.
- Simulated output is labelled as simulated.
- Cost and token usage come from the backend; the UI does not fabricate
  metrics.
- Theme choice persists in `localStorage` under `crest.theme`.

## Validation

- `npm run build` passes.
- Browser E2E was run against a live backend: landing, dashboard, tasks, task
  creation and execution, approvals, autonomy, providers, routing, evidence,
  audit, budgets, demos, settings, system, docs, security, 404, and theme
  switching.
- The verified offline paths include success (`Completed` / `ACCEPT`),
  verification failure (`Failed` / `REJECT`), budget exhaustion, and
  high-risk approval followed by `ABSTAIN`.

See `../docs/PRODUCT_COMPLETION_TRACKER.md` for the full validation record and
known gaps.
