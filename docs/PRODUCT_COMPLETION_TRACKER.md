# CREST 1.0 — Product Completion Tracker

Status: **product layer complete for the stated scope; validation recorded
below.** This file distinguishes what was executed and observed from what was
implemented but not live-validated.

- Branch: `feat/crest-1.0-product`
- Version: `1.0.0`
- Validation date: 2026-11-13
- Security posture: **Level 3 — supervised personal use**
- Tested execution path: **offline deterministic mock provider**
- Live external provider calls: **none**

---

## 1. Delivered

| Area | Status | Location |
| --- | --- | --- |
| Product engine | Complete | `src/crest/product/engine.py` |
| SQLite persistence | Complete | `src/crest/product/db.py` |
| Settings and validation | Complete | `src/crest/product/settings.py` |
| Autonomy and policy | Complete | `src/crest/product/policy.py` |
| Planner | Complete | `src/crest/product/planner.py` |
| Providers | Complete (mock validated) | `src/crest/product/providers.py` |
| Verification | Complete | `src/crest/product/verification.py` |
| HTTP API | Complete | `src/crest/product/api.py`, `src/crest/api.py` |
| Public site | Complete | `/`, `/docs`, `/security`, 404 |
| Product app | Complete, 14 pages | `web/src/pages/` |
| App shell and themes | Complete | `web/src/components/AppLayout.tsx`, `web/src/styles.css` |
| Typed API client | Complete | `web/src/lib/api.ts` |
| Browser desktop launcher | Complete | `crest_desktop.py` |
| Product tests | 39 passing | `tests/product/` |
| Documentation set | Complete | `docs/PRODUCT_*.md`, this file |
| Native desktop package | **Not attempted** | No Tauri/Electron/pywebview |

---

## 2. Requirement matrix

| Requirement | Status | Evidence |
| --- | --- | --- |
| Preserve research runtime, benchmarks, experiments, history | Satisfied | Product code is additive under `src/crest/product/` and `web/`; full suite includes the existing research tests |
| Work on `feat/crest-1.0-product` without rewriting history | Satisfied | Branch used; no force-push or history rewrite |
| 14 app pages | Satisfied | Dashboard, Tasks, New Task, Task Detail, Approvals, Autonomy, Providers, Routing, Evidence, Audit, Budgets, Demos, Settings, System |
| Product website at `/`, app at `/app` | Satisfied | React Router routes; verified in browser |
| Polished responsive light/dark UI | Satisfied (implemented; breakpoints present) | Custom design system; theme toggle verified; mobile layout not screenshot-audited exhaustively |
| Real backend data, no fake metrics or dead controls | Satisfied | All pages use `web/src/lib/api.ts`; aggregates come from `/api/v1/stats/overview` and `/api/v1/budgets/summary`; demo labels are explicit |
| Real provider adapters | Satisfied (mock validated) | Mock, Gemini, OpenAI-compatible adapters; Gemini/OpenAI not live-tested |
| External calls opt-in, spending off by default | Satisfied | `allow_external_calls=false`; provider status and key checks; tests |
| Server-side autonomy, permissions, budgets, approvals, gate, verification, recovery, audit | Satisfied | `policy.py`, `engine.py`, `verification.py`, `high_risk_gate.py`; 39 product tests + manual API smokes |
| Offline mock end-to-end and failure scenarios | Satisfied | Success, verification failure, recovery, budget exhaustion, observe denial, assisted approval, high-risk abstention, custom-policy denial |
| Browser desktop launcher remains working | Satisfied | `crest_desktop.py` starts the server and opens `/app`; browser-based wording |
| Do not call the launcher native | Satisfied | Documented as browser-based everywhere |
| Full regression | **471 passed** | `pytest -q` on 2026-11-13 |
| Frontend build | Passes | 55 modules; JS ~452 kB / ~126 kB gzip; CSS ~63 kB / ~11.6 kB gzip |
| Fresh-install validation | Passes | Isolated venv + `pip install -e ".[product]"`; health, low-risk success, high-risk approval → abstain, export |
| Browser E2E | Passes | In-app browser navigation sweep + headless Chrome CDP create/failure flows |
| Commit, push, verify remote | Pending at tracker write | See release section below |
| No claim of unrun tests | Satisfied | This tracker separates executed from implemented |

---

## 3. Validation evidence

### 3.1 Product tests

Command:

```powershell
$env:PYTHONPATH="src;."; python -m pytest tests/product -q -p no:cacheprovider
```

Result: **39 passed**.

Coverage includes task creation and validation, autonomy ceiling, custom
policies, observe denial, assisted approval, budget exhaustion, verification
failure, recovery, high-risk gate abstention, evidence, audit, persistence,
auth, export, cancellation, and interruption recovery.

### 3.2 Full regression

Command:

```powershell
$env:PYTHONPATH="src;."; python -m pytest -q -p no:cacheprovider
```

Result: **471 passed in 97.74s**.

This includes the existing research runtime, adapters, security, persistence,
CLI, integration, and the 39 new product tests.

### 3.3 Frontend build

Command:

```powershell
cd web
npm run build
```

Result: **passes**. `tsc -b` and Vite complete with 55 modules.

### 3.4 Fresh-install validation

An isolated virtual environment was created under the temp directory, then:

```powershell
python -m pip install -e ".[product]"
```

Observed versions: CREST `1.0.0`, FastAPI `0.162.6`, Uvicorn `0.54.0`, HTTPX
`0.28.1`.

A fresh data directory was started on port 8011 and exercised over HTTP:

| Check | Result |
| --- | --- |
| `/api/v1/health` | `status=ok`, `version=1.0.0`, `database=ok` |
| Low-risk task, autonomy 3, mock | `completed`, verification `passed`, gate `ACCEPT` |
| High-risk task, autonomy 3, mock | `awaiting_approval` |
| Approve high-risk task | `abstained`, verification `passed`, gate `ABSTAIN` |
| Export | Contains application, settings, providers, routing, tables |

Result: **FRESH INSTALL E2E: PASS**.

### 3.5 Browser E2E

Two browser passes were used:

1. **In-app browser against a live server** (port 8010): landing, dashboard,
   tasks, approvals, autonomy, providers, routing, evidence, audit, budgets,
   demos, settings, system, docs, security, 404. No console errors or error
   states. The success demo reached `Completed` / verification passed /
   `ACCEPT`. The high-risk demo paused for approval, then reached `abstained` /
   `ABSTAIN` with output retained. Theme switching persisted.
2. **Headless Chrome over the DevTools protocol**, after the form and gate
   fixes: real form input, task creation, execution, and failure demos.

Headless run result:

| Check | Result |
| --- | --- |
| Budget input validity before submit | valid (`step` fix) |
| Task creation and navigation | `/app/tasks/<id>` |
| Low-risk execution | `Completed`, verification passed, gate `ACCEPT` |
| Verification-failure demo | `Failed`, verification failed, gate `REJECT` |
| Budget-exhaustion demo | `Budget Exhausted` |
| Theme toggle | dark → light |
| Console errors | none |

Result: **CDP BROWSER E2E: PASS**.

### 3.6 Manual API smokes

Executed during development against the live server: success, high-risk
approval → abstain, verification failure, recovery, budget exhaustion, observe
denial, assisted approval, and custom-policy denial. These are superseded by
the automated product tests where covered.

---

## 4. Defects found and fixed during validation

1. **Task form could not submit with a normal budget.** The budget input used
   `min="0.000001"` with `step="0.01"`, so HTML number validation accepted only
   `0.000001`, `0.010001`, … and rejected `1`. Native validation blocked the
   submit event before React ran. Fixed with `step="any"` in the task form and
   the two settings budget inputs. Verified in headless Chrome.
2. **Failed verification recorded gate `ACCEPT`.** For low/medium risk the gate
   returned its base-admission result even when verification failed, producing
   a misleading `Failed / ACCEPT` display. The engine now records `REJECT` when
   verification fails. The product test was strengthened to assert `REJECT`.
   Verified in headless Chrome.

---

## 5. Not validated / known gaps

| Gap | Status | Notes |
| --- | --- | --- |
| Live Gemini / OpenAI-compatible calls | Not validated | Adapters implemented; no external calls or spend were made. `GEMINI_API_KEY` was not used. |
| Native desktop packaging | Not attempted | No Tauri, Electron, or pywebview installed. `crest_desktop.py` is a browser launcher. |
| Multi-user or remote deployment | Out of scope | Level 3 posture; localhost single-operator design. |
| Signed evidence / attestations | Not implemented | Content hashes prove integrity, not origin or truth. |
| Exhaustive mobile visual audit | Not performed | Responsive breakpoints and layouts exist; only desktop browser flows were exercised. |
| Multi-process SQLite stress | Covered by existing tests | Full suite passes; the design remains local-first. |
| Retention purge in production data | Not exercised destructively | Endpoint and tests exist; no real user data was purged. |

---

## 6. Release checklist

- [x] Product engine, API, web app, launcher implemented
- [x] 39 product tests passing
- [x] Full regression 471 passing
- [x] Frontend production build passing
- [x] Fresh-install E2E passing
- [x] Browser E2E passing
- [x] Documentation set written
- [x] README and web README updated honestly
- [x] Working tree reviewed for artifacts and secrets
- [x] Commit and push `feat/crest-1.0-product`
- [x] Verify remote branch and commit hash

### Release record

Pushed normally to `origin/feat/crest-1.0-product` (no force, no history
rewrite):

| Commit | Description |
| --- | --- |
| `3591937` | `feat(product): add CREST 1.0 engine, API, and browser launcher` |
| `d326ceb` | `feat(web): add CREST 1.0 product site and control-plane app` |
| `0a1ebb0` | `test(product): cover policy, budgets, approvals, gate, and recovery` |
| `60f5100` | `docs: document the CREST 1.0 product, API, and operations` |

Remote verification immediately after the push:

```text
git ls-remote origin refs/heads/feat/crest-1.0-product
60f5100dc1d24d3cfc5276348dc7c9f55b05a81f  refs/heads/feat/crest-1.0-product

git rev-parse HEAD
60f5100dc1d24d3cfc5276348dc7c9f55b05a81f
```

Local and remote hashes matched. This tracker update is a follow-up commit on
the same branch.
