"""FastAPI entry point for the stock research Web platform."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env", override=False)

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from src.dialogue.graph import DialogueGraph
from src.dialogue.intent_service import ContextualIntentService
from src.dialogue.security_resolver import MCPSecurityResolver
from src.planning.direct_tool_planner import DirectToolPlanner
from src.services.direct_tool_service import DirectToolService
from src.services.research_service import ResearchService
from web.backend.app.config import settings
from web.backend.app.database import Database
from web.backend.app.events import EventBroker
from web.backend.app.intent_router import IntentRouter
from web.backend.app.models import (
    ChatAccepted,
    ChatRequest,
    CreateSessionRequest,
    HealthResponse,
    IntentAnalysis,
    IntentRequest,
    SessionDetail,
    SessionSummary,
    TaskRecord,
)
from web.backend.app.task_manager import TaskManager, TaskNotCancellableError


database = Database(settings.database_path)
broker = EventBroker()
intent_router = IntentRouter(use_llm=settings.intent_router_use_llm)
contextual_intent_service = ContextualIntentService(
    use_llm=settings.intent_router_use_llm
)
dialogue_graph = DialogueGraph(
    contextual_intent_service,
    security_resolver=MCPSecurityResolver(),
)
research_service = ResearchService(
    log_dir=settings.log_dir,
    timezone_name=settings.timezone_name,
)
direct_tool_planner = (
    DirectToolPlanner(timezone_name=settings.timezone_name)
    if settings.direct_tool_routing_enabled
    else None
)
direct_tool_service = (
    DirectToolService(
        log_dir=settings.log_dir,
        timezone_name=settings.timezone_name,
    )
    if settings.direct_tool_routing_enabled
    else None
)
task_manager = TaskManager(
    database,
    broker,
    intent_router,
    research_service,
    direct_tool_planner,
    direct_tool_service,
    dialogue_graph,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    database.initialize()
    database.recover_incomplete_tasks()
    yield


app = FastAPI(
    title="Stock Research Multi-Agent API",
    version="0.1.0",
    description="REST and SSE facade over the existing LangGraph research workflow.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    database.healthcheck()
    return HealthResponse(
        model_configured=all(
            os.getenv(name)
            for name in (
                "OPENAI_COMPATIBLE_API_KEY",
                "OPENAI_COMPATIBLE_BASE_URL",
                "OPENAI_COMPATIBLE_MODEL",
            )
        ),
        mcp_configured=True,
    )


@app.post("/api/intent", response_model=IntentAnalysis)
async def parse_intent(body: IntentRequest) -> IntentAnalysis:
    return await intent_router.parse(body.query.strip())


@app.post(
    "/api/chat",
    response_model=ChatAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_chat_task(
    body: ChatRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ChatAccepted:
    query = body.query.strip()
    if idempotency_key and len(idempotency_key) > 200:
        raise HTTPException(status_code=400, detail="Idempotency-Key is too long")
    if idempotency_key:
        existing = database.get_task_by_idempotency_key(idempotency_key)
        if existing is not None:
            return ChatAccepted(
                task_id=existing["id"],
                session_id=existing["session_id"],
                status=existing["status"],
                events_url=f"/api/chat/{existing['id']}/events",
                reused=True,
            )
    if body.session_id:
        try:
            database.get_session_row(body.session_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Session not found") from error
        session_id = body.session_id
    else:
        session_id = database.create_session()["id"]

    try:
        task, reused = database.create_task(
            session_id=session_id,
            query=query,
            architecture=body.architecture,
            idempotency_key=idempotency_key,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Session not found") from error
    if not reused:
        task_manager.submit(task["id"])
    return ChatAccepted(
        task_id=task["id"],
        session_id=task["session_id"],
        status=task["status"],
        events_url=f"/api/chat/{task['id']}/events",
        reused=reused,
    )


@app.get("/api/tasks/{task_id}", response_model=TaskRecord)
def get_task(task_id: str) -> TaskRecord:
    try:
        return TaskRecord.model_validate(database.get_task(task_id))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Task not found") from error


@app.post(
    "/api/tasks/{task_id}/cancel",
    response_model=TaskRecord,
    status_code=status.HTTP_202_ACCEPTED,
)
async def cancel_task(task_id: str) -> TaskRecord:
    try:
        return TaskRecord.model_validate(task_manager.cancel(task_id))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Task not found") from error
    except TaskNotCancellableError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/chat/{task_id}/events")
async def stream_events(
    task_id: str,
    request: Request,
    after: int = Query(default=0, ge=0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    try:
        database.get_task(task_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Task not found") from error

    cursor = after
    if last_event_id:
        try:
            cursor = max(cursor, int(last_event_id))
        except ValueError:
            pass

    async def generate() -> AsyncIterator[str]:
        nonlocal cursor
        while True:
            if await request.is_disconnected():
                break
            events = database.list_events(task_id, after_id=cursor)
            for event in events:
                cursor = event["id"]
                body = {
                    "id": event["id"],
                    "type": event["event_type"],
                    "created_at": event["created_at"],
                    "payload": event["payload"],
                }
                yield (
                    f"id: {event['id']}\n"
                    f"event: {event['event_type']}\n"
                    f"data: {json.dumps(body, ensure_ascii=False)}\n\n"
                )

            task = database.get_task(task_id)
            if task["status"] in {"completed", "failed", "cancelled"} and len(events) < 200:
                break
            notified = await broker.wait(task_id, timeout=15.0)
            if not notified:
                yield ": keepalive\n\n"
        broker.discard(task_id)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post(
    "/api/sessions",
    response_model=SessionSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_session(body: CreateSessionRequest) -> SessionSummary:
    return SessionSummary.model_validate(database.create_session(body.title.strip()))


@app.get("/api/sessions", response_model=list[SessionSummary])
def list_sessions() -> list[SessionSummary]:
    return [SessionSummary.model_validate(item) for item in database.list_sessions()]


@app.get("/api/sessions/{session_id}", response_model=SessionDetail)
def get_session(session_id: str) -> SessionDetail:
    try:
        return SessionDetail.model_validate(database.get_session(session_id))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Session not found") from error


@app.get("/api/sessions/{session_id}/state")
def get_session_state(session_id: str) -> dict:
    try:
        database.get_session_row(session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Session not found") from error
    return database.get_dialogue_state(session_id) or {
        "session_id": session_id,
        "task_status": "idle",
        "state_version": 0,
    }


@app.delete("/api/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str) -> Response:
    if database.session_has_active_tasks(session_id):
        raise HTTPException(
            status_code=409,
            detail="A running task must finish before the session can be deleted",
        )
    if not database.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
