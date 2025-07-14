# Celery Post-Implementation De-commission Plan

Once the Celery migration is verified in production (all pipelines complete end-to-end, UI receives real-time updates, and legacy paths are unused) the following legacy artefacts can be safely removed.

## 1. Python Modules / Scripts

| File / Module | Replacement | Action |
|---------------|-------------|--------|
| `background_worker.py` | `knowledge_base_agent/tasks/agent_tasks.py::run_agent_task` | Delete file & references |
| `web_api_only.py`      | REST `/v2/agent/*` & Celery tasks | Delete file, update imports |
| `queue_listener` + `update_queue` usage in `web.py` | Redis pub/sub via `TaskProgressManager` & `RealtimeManager` | Remove code paths and global vars |
| `multiprocessing` helper functions (`run_agent_process`, etc.) in comments | N/A | Delete | 
| Any `test_background_worker*` API routes | New test can hit Celery tasks | Remove decorators |

## 2. Flask Routes (API)

| Route | Status | Removal Step |
|-------|--------|-------------|
| `/api/agent/start`, `/agent/start` (410) | Deprecated | Delete after UI fully on V2 |
| `/api/agent/stop`,  `/agent/stop`  | Deprecated | Delete |
| `/agent/status_legacy`            | Deprecated | Delete |
| `/agent/test-*` endpoints         | Dev utilities | Delete or move to unit tests |

## 3. Front-end JS

• Remove any code that references legacy endpoints (`/agent/start`, `/agent/stop`, etc.).  
• Remove SocketIO paths that emit legacy events if still present (`run_agent`, `stop_agent`).

## 4. Config / ENV

| Variable | Notes |
|----------|-------|
| `USE_CELERY` – once confident, set default **True** and eventually drop flag & branching code.
| Any multiprocessing-specific timeouts / paths – review and delete.

## 5. Logging Helpers

`recent_logs` deque in `web.py` is now redundant because task logs live in Redis + DB.  Plan:
1. Keep for 1 release as fallback.  
2. Switch UI to `/v2/logs/*` exclusively.  
3. Remove deque & helper functions.

## 6. Documentation

• Remove multiprocessing sections from `docs/implementation_plan.md`.  
• Archive the original migration plan under `docs/legacy/`.

## 7. Release Checklist

1. **Flag Flip** – set `USE_CELERY=true` in `.env`, deploy, watch Flower & UI.  
2. **Blue/Green test** – run full pipeline, confirm DB & files update, logs stream.  
3. **Smoke tests** – start/stop agent, run chat endpoint, clear logs.  
4. **Code cleanup PR** – delete files and routes listed above, run linters & unit tests.  
5. **Tag release** – `v2.0.0-celery`.

## 8. Post-cleanup Optimisations

• Consider enabling Celery Beat for scheduled agent runs.  
• Containerise later (Docker/Compose or k8s) – separate document.

---
**Status key**  
☑️ pending removal 🔄 in progress ✅ removed 