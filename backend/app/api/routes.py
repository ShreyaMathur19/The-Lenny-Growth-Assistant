import logging
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.db.session import get_db
from app.models import Artifact, ChatSession, Message
from app.schemas import ArtifactOut, ChatRequest, ChatResponse, MessageOut, ProviderConfig, SessionCreate, SessionOut, SourceOut
from app.services.agent import AgentServiceError, generate_with_agent
from app.services.ollama import OllamaUnavailable, ollama_health
from app.services.retrieval import retrieve_chunks
from app.services.routing import detect_mode

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("lenny.api")


def source_models(chunks: list[dict]) -> list[SourceOut]:
    return [
        SourceOut(
            id=c["id"],
            episode_title=c.get("episode_title"),
            guest=c.get("guest"),
            source_url=c.get("source_url"),
            source_path=c["source_path"],
            excerpt=c["content"][:280].replace("\n", " "),
            score=c.get("score"),
        )
        for c in chunks
    ]


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    ollama_ok = await ollama_health()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "unavailable",
        "ollama": "available" if ollama_ok else "unavailable",
    }


@router.get("/config", response_model=ProviderConfig)
async def config():
    # Cloud configuration itself lives in the Pi service; this endpoint keeps the UI explicit.
    return ProviderConfig(
        local_provider="ollama",
        local_model=settings.ollama_chat_model,
        cloud_provider="configured-in-agent-service",
        cloud_model="configured-in-agent-service",
        cloud_enabled=True,
    )


@router.post("/sessions", response_model=SessionOut)
async def create_session(payload: SessionCreate, request: Request, db: AsyncSession = Depends(get_db)):
    metadata = dict(payload.user_metadata)
    metadata.setdefault("user_agent", request.headers.get("user-agent", "unknown")[:500])
    session = ChatSession(user_id=payload.user_id, user_metadata=metadata)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ChatSession).order_by(ChatSession.updated_at.desc()).limit(50))
    return result.scalars().all()


@router.get("/sessions/{session_id}/artifacts", response_model=list[ArtifactOut])
async def list_artifacts(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Artifact).where(Artifact.session_id == session_id).order_by(Artifact.created_at.desc()).limit(20))
    return [ArtifactOut(id=a.id, type=a.artifact_type, title=a.title, content=a.content) for a in result.scalars().all()]


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.created_at))
    messages = result.scalars().all()
    return [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            provider=m.provider,
            model=m.model,
            sources=[SourceOut(**s) for s in (m.source_metadata or [])],
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    started = time.perf_counter()
    session = await db.get(ChatSession, payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": "Chat session does not exist."})

    mode = detect_mode(payload.message) if payload.mode == "auto" else payload.mode
    session.updated_at = datetime.now(timezone.utc)
    user_message = Message(session_id=session.id, role="user", content=payload.message)
    db.add(user_message)
    if session.title == "New chat":
        session.title = payload.message.strip().replace("\n", " ")[:80]
    await db.flush()

    history_result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id, Message.id != user_message.id)
        .order_by(Message.created_at.desc())
        .limit(settings.max_history_messages)
    )
    history = list(reversed(history_result.scalars().all()))

    retrieval_started = time.perf_counter()
    try:
        chunks = await retrieve_chunks(db, payload.message)
    except OllamaUnavailable:
        await db.rollback()
        raise HTTPException(
            status_code=503,
            detail={"code": "OLLAMA_UNAVAILABLE", "message": "Local embedding model is unavailable. Start Ollama and pull the configured embedding model."},
        )
    retrieval_ms = int((time.perf_counter() - retrieval_started) * 1000)

    if not chunks:
        answer = "I couldn't find sufficient support for this question in the indexed Lenny transcripts."
        assistant = Message(session_id=session.id, role="assistant", content=answer, provider=payload.provider, source_metadata=[])
        db.add(assistant)
        await db.commit()
        await db.refresh(assistant)
        return ChatResponse(
            message=MessageOut(id=assistant.id, role="assistant", content=answer, provider=payload.provider, model=None, sources=[], created_at=assistant.created_at),
            mode=mode,
        )

    sources = source_models(chunks)
    context = "\n\n".join(
        f"[S{i+1}] Episode: {c.get('episode_title') or 'Unknown'} | Guest: {c.get('guest') or 'Unknown'} | Source: {c.get('source_url') or c['source_path']}\n{c['content']}"
        for i, c in enumerate(chunks)
    )
    history_payload = [{"role": m.role, "content": m.content} for m in history]

    try:
        agent_result = await generate_with_agent(
            {
                "provider": payload.provider,
                "mode": mode,
                "artifactType": payload.artifact_type,
                "message": payload.message,
                "history": history_payload,
                "context": context,
            }
        )
    except AgentServiceError as exc:
        await db.rollback()
        code = str(exc)
        status = 504 if code == "MODEL_TIMEOUT" else 503
        raise HTTPException(status_code=status, detail={"code": code, "message": "The model service could not complete the request."})

    assistant = Message(
        session_id=session.id,
        role="assistant",
        content=agent_result["text"],
        provider=payload.provider,
        model=agent_result.get("model"),
        source_metadata=[s.model_dump() for s in sources],
    )
    db.add(assistant)
    await db.flush()

    artifact_out = None
    if agent_result.get("artifact"):
        raw = agent_result["artifact"]
        artifact = Artifact(
            session_id=session.id,
            message_id=assistant.id,
            artifact_type=raw["type"],
            title=raw.get("title", "Generated artifact")[:200],
            content=raw["content"],
        )
        db.add(artifact)
        await db.flush()
        artifact_out = ArtifactOut(id=artifact.id, type=artifact.artifact_type, title=artifact.title, content=artifact.content)

    await db.commit()
    await db.refresh(assistant)
    total_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "chat_completed",
        extra={
            "session_id": session.id,
            "provider": payload.provider,
            "model": agent_result.get("model"),
            "mode": mode,
            "chunks_found": len(chunks),
            "retrieval_ms": retrieval_ms,
            "total_ms": total_ms,
        },
    )
    return ChatResponse(
        message=MessageOut(
            id=assistant.id,
            role="assistant",
            content=assistant.content,
            provider=assistant.provider,
            model=assistant.model,
            sources=sources,
            created_at=assistant.created_at,
        ),
        mode=mode,
        artifact=artifact_out,
    )
