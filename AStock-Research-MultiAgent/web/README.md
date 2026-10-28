# Web Platform

The Web platform is a local, front-end/back-end separated interface over the existing LangGraph + ReAct + MCP workflow.

## Structure

```text
web/
  backend/
    app/
      main.py            FastAPI routes and SSE endpoint
      database.py        SQLite sessions, messages, tasks and events
      intent_router.py   LLM structured output with deterministic fallback
      task_manager.py    Background research-task lifecycle
      events.py          SSE wake-up broker
    requirements.txt
  frontend/
    src/
      components/        Chat, report, intent and execution panels
      api.ts             REST/SSE client
      App.tsx            Application state and responsive layout
    package.json
```

## Install

From the repository root (`D:\Agent\Finance` in the example):

```powershell
uv pip install --python '.\.venv\Scripts\python.exe' -r '.\AStock-Research-MultiAgent\web\backend\requirements.txt'
uv pip install --python '.\.venv\Scripts\python.exe' -r '.\AStock-Research-MultiAgent\requirements-dev.txt'

Set-Location '.\AStock-Research-MultiAgent\web\frontend'
npm install
```

Copy `AStock-Research-MultiAgent/.env.example` to `.env` and configure the model API. The API key is read only by FastAPI/Python and is never sent to the browser.

## Run locally

Terminal 1, from `AStock-Research-MultiAgent`:

```powershell
& '..\.venv\Scripts\python.exe' -m uvicorn web.backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2, from `AStock-Research-MultiAgent/web/frontend`:

```powershell
npm run dev
```

Open `http://localhost:5173`.

Use one Uvicorn worker in the current version. Research jobs are in-process async tasks; SQLite persists their events. A user-requested cancellation is restored as cancelled after a backend restart, while other interrupted tasks are marked failed.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/chat` | Create a queued research task; supports `Idempotency-Key` |
| `GET` | `/api/chat/{task_id}/events` | Replay and stream real runtime events using SSE |
| `GET` | `/api/tasks/{task_id}` | Read current task status and final report |
| `POST` | `/api/tasks/{task_id}/cancel` | Request cooperative cancellation of a queued or running task |
| `POST` | `/api/intent` | Parse structured intent independently |
| `POST` | `/api/sessions` | Create a conversation |
| `GET` | `/api/sessions` | List conversation history |
| `GET` | `/api/sessions/{id}` | Restore messages and task records |
| `DELETE` | `/api/sessions/{id}` | Delete an idle conversation |
| `GET` | `/api/health` | Check API, SQLite and configuration state |

SSE supports browser reconnection through event IDs and the `Last-Event-ID` header. A refreshed UI may reconnect from event 0 and reconstruct the execution panel from persisted events.

While a task is queued or running, the send arrow becomes a stop-square control. Cancellation transitions through `cancelling` to `cancelled`, emits replayable SSE events, and does not persist a partial assistant report.

## Direct factual queries

Unambiguous, read-only questions can bypass the research and summary agents and invoke exactly one allowlisted MCP tool. Supported v1 facts are stock basic information, industry, recent price/PE/PB/PS data, dividends for an explicit year, and the latest trading date.

The direct route is conservative: a stock code is required for stock facts, dividend queries require a year, and analytical/comparative/calculation/advice questions continue through the existing LangGraph workflow. The LLM cannot provide an arbitrary tool name; a deterministic policy compiles the query into a fixed tool and validated arguments. An unambiguous direct fact also skips the intent LLM; ambiguous requests still use the structured Intent Router before entering LangGraph.

Set `DIRECT_TOOL_ROUTING_ENABLED=0` to disable this route without changing code.

## Test and build

```powershell
# From AStock-Research-MultiAgent
& '..\.venv\Scripts\python.exe' -m pytest

# From web/frontend
npm test
npm run build
```

## Current routing boundary

Allowlisted factual queries use the direct MCP route. All other requests continue through the existing deterministic `plan_query` + LangGraph workflow. A direct-tool failure is surfaced as a task error instead of silently launching agents, so one-tool cost and behavior remain predictable.
