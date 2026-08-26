import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.models import Artifact, ChatSession, Message
from app.schemas import (
    ArtifactOut,
    ChatRequest,
    ChatResponse,
    MessageOut,
    ProviderConfig,
    SessionCreate,
    SessionOut,
    SourceOut,
)
from app.services.agent import AgentServiceError, generate_with_agent
from app.services.ollama import OllamaUnavailable, ollama_health
from app.services.retrieval import retrieve_chunks
from app.services.routing import detect_mode


router = APIRouter()
settings = get_settings()
logger = logging.getLogger("lenny.api")


# ============================================================
# Helpers
# ============================================================

def source_models(chunks: list[dict]) -> list[SourceOut]:
    """
    Convert retrieved transcript chunks into API source objects.

    retrieval.py returns semantic relevance in `similarity`.
    The API exposes that value using SourceOut.score.
    """
    return [
        SourceOut(
            id=chunk["id"],
            episode_title=chunk.get("episode_title"),
            guest=chunk.get("guest"),
            source_url=chunk.get("source_url"),
            source_path=chunk["source_path"],
            excerpt=chunk["content"][:280].replace("\n", " "),
            score=chunk.get("similarity"),
        )
        for chunk in chunks
    ]


def message_out(message: Message) -> MessageOut:
    """
    Convert a persisted Message ORM object into an API response.
    """
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        provider=message.provider,
        model=message.model,
        sources=[
            SourceOut(**source)
            for source in (message.source_metadata or [])
        ],
        created_at=message.created_at,
    )


# ============================================================
# Health
# ============================================================

@router.get("/health")
async def health(
    db: AsyncSession = Depends(get_db),
):
    db_ok = True

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    ollama_ok = await ollama_health()

    return {
        "status": (
            "healthy"
            if db_ok and ollama_ok
            else "degraded"
        ),
        "database": (
            "connected"
            if db_ok
            else "unavailable"
        ),
        "ollama": (
            "available"
            if ollama_ok
            else "unavailable"
        ),
    }


# ============================================================
# Provider configuration
# ============================================================

@router.get(
    "/config",
    response_model=ProviderConfig,
)
async def config():
    return ProviderConfig(
        local_provider="ollama",
        local_model=settings.ollama_chat_model,
        cloud_provider="configured-in-agent-service",
        cloud_model="configured-in-agent-service",
        cloud_enabled=True,
    )


# ============================================================
# Sessions
# ============================================================

@router.post(
    "/sessions",
    response_model=SessionOut,
)
async def create_session(
    payload: SessionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    metadata = dict(payload.user_metadata)

    metadata.setdefault(
        "user_agent",
        request.headers.get(
            "user-agent",
            "unknown",
        )[:500],
    )

    session = ChatSession(
        user_id=payload.user_id,
        user_metadata=metadata,
    )

    db.add(session)

    await db.commit()
    await db.refresh(session)

    return session


@router.get(
    "/sessions",
    response_model=list[SessionOut],
)
async def list_sessions(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .order_by(
            ChatSession.updated_at.desc()
        )
        .limit(50)
    )

    return result.scalars().all()


# ============================================================
# Artifacts
# ============================================================

@router.get(
    "/sessions/{session_id}/artifacts",
    response_model=list[ArtifactOut],
)
async def list_artifacts(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Artifact)
        .where(
            Artifact.session_id == session_id
        )
        .order_by(
            Artifact.created_at.desc()
        )
        .limit(20)
    )

    artifacts = result.scalars().all()

    return [
        ArtifactOut(
            id=artifact.id,
            type=artifact.artifact_type,
            title=artifact.title,
            content=artifact.content,
        )
        for artifact in artifacts
    ]


# ============================================================
# Messages
# ============================================================

@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[MessageOut],
)
async def list_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Message)
        .where(
            Message.session_id == session_id
        )
        .order_by(
            Message.created_at
        )
    )

    messages = result.scalars().all()

    return [
        message_out(message)
        for message in messages
    ]


# ============================================================
# Chat
# ============================================================

@router.post(
    "/chat",
    response_model=ChatResponse,
)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    started = time.perf_counter()

    # --------------------------------------------------------
    # 1. Validate session
    # --------------------------------------------------------

    session = await db.get(
        ChatSession,
        payload.session_id,
    )

    if not session:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SESSION_NOT_FOUND",
                "message": (
                    "Chat session does not exist."
                ),
            },
        )

    # --------------------------------------------------------
    # 2. Determine request mode
    # --------------------------------------------------------

    mode = (
        detect_mode(payload.message)
        if payload.mode == "auto"
        else payload.mode
    )

    # --------------------------------------------------------
    # 3. Update session
    # --------------------------------------------------------

    session.updated_at = datetime.now(
        timezone.utc
    )

    # --------------------------------------------------------
    # 4. Save user message
    # --------------------------------------------------------

    user_message = Message(
        session_id=session.id,
        role="user",
        content=payload.message,
    )

    db.add(user_message)

    if session.title == "New chat":
        session.title = (
            payload.message
            .strip()
            .replace("\n", " ")[:80]
        )

    # Get generated user-message ID.
    await db.flush()

    # --------------------------------------------------------
    # 5. Load previous conversation context
    # --------------------------------------------------------

    history_result = await db.execute(
        select(Message)
        .where(
            Message.session_id == session.id,
            Message.id != user_message.id,
        )
        .order_by(
            Message.created_at.desc()
        )
        .limit(
            settings.max_history_messages
        )
    )

    history = list(
        reversed(
            history_result.scalars().all()
        )
    )

    # --------------------------------------------------------
    # Persist the user's turn before slow model work.
    #
    # This means model failure/timeout does not silently
    # remove the user's submitted message.
    # --------------------------------------------------------

    await db.commit()

    # --------------------------------------------------------
    # 6. Retrieve transcript evidence
    # --------------------------------------------------------

    retrieval_started = time.perf_counter()

    try:
        chunks = await retrieve_chunks(
            db,
            payload.message,
            top_k=settings.top_k,
        )

    except OllamaUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "OLLAMA_UNAVAILABLE",
                "message": (
                    "Local embedding model is unavailable. "
                    "Start Ollama and pull the configured "
                    "embedding model."
                ),
            },
        ) from exc

    retrieval_ms = int(
        (
            time.perf_counter()
            - retrieval_started
        )
        * 1000
    )

    # ========================================================
    # 7. HARD GROUNDING GUARD
    # ========================================================
    #
    # retrieval.py applies MIN_SIMILARITY.
    #
    # Therefore, if chunks is empty, no transcript evidence
    # was considered sufficiently relevant.
    #
    # IMPORTANT:
    # Do not send the question to the LLM in that situation.
    #
    # This prevents:
    #
    # quantum computing question
    #       ↓
    # unrelated growth transcript
    #       ↓
    # LLM invents an answer
    #
    # Instead:
    #
    # unrelated question
    #       ↓
    # no relevant chunks
    #       ↓
    # deterministic refusal
    #
    # ========================================================

    if not chunks:
        answer = (
            "I couldn't find sufficient evidence in the indexed "
            "Lenny's Podcast transcripts to answer that question."
        )

        assistant = Message(
            session_id=session.id,
            role="assistant",
            content=answer,
            provider=payload.provider,
            model=None,
            source_metadata=[],
        )

        db.add(assistant)

        await db.commit()
        await db.refresh(assistant)

        total_ms = int(
            (
                time.perf_counter()
                - started
            )
            * 1000
        )

        logger.info(
            "chat_insufficient_evidence",
            extra={
                "session_id": session.id,
                "provider": payload.provider,
                "mode": mode,
                "chunks_found": 0,
                "retrieval_ms": retrieval_ms,
                "total_ms": total_ms,
            },
        )

        return ChatResponse(
            message=message_out(
                assistant
            ),
            mode=mode,
            artifact=None,
        )

    # --------------------------------------------------------
    # 8. Convert chunks into source metadata
    # --------------------------------------------------------

    sources = source_models(
        chunks
    )

    # --------------------------------------------------------
    # 9. Build source-labelled RAG context
    # --------------------------------------------------------

    context_parts = []

    for index, chunk in enumerate(
        chunks,
        start=1,
    ):
        episode = (
            chunk.get("episode_title")
            or "Unknown"
        )

        guest = (
            chunk.get("guest")
            or "Unknown"
        )

        source = (
            chunk.get("source_url")
            or chunk["source_path"]
        )

        context_parts.append(
            f"[S{index}] "
            f"Episode: {episode} | "
            f"Guest: {guest} | "
            f"Source: {source}\n"
            f"{chunk['content']}"
        )

    context = "\n\n".join(
        context_parts
    )

    # --------------------------------------------------------
    # 10. Previous conversation for the agent
    # --------------------------------------------------------

    history_payload = [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in history
    ]

    # --------------------------------------------------------
    # 11. Generate with Pi Agent
    # --------------------------------------------------------

    try:
        agent_result = await generate_with_agent(
            {
                "provider": payload.provider,
                "mode": mode,
                "artifactType": (
                    payload.artifact_type
                ),
                "message": payload.message,
                "history": history_payload,
                "context": context,
            }
        )

    except AgentServiceError as exc:
        code = str(exc)

        status = (
            504
            if code == "MODEL_TIMEOUT"
            else 503
        )

        logger.exception(
            "agent_generation_failed",
            extra={
                "session_id": session.id,
                "provider": payload.provider,
                "mode": mode,
                "error_code": code,
            },
        )

        raise HTTPException(
            status_code=status,
            detail={
                "code": code,
                "message": (
                    "The model service could not "
                    "complete the request."
                ),
            },
        ) from exc

    # --------------------------------------------------------
    # 12. Save assistant response
    # --------------------------------------------------------

    assistant = Message(
        session_id=session.id,
        role="assistant",
        content=agent_result["text"],
        provider=payload.provider,
        model=agent_result.get("model"),
        source_metadata=[
            source.model_dump()
            for source in sources
        ],
    )

    db.add(assistant)

    await db.flush()

    # --------------------------------------------------------
    # 13. Save artifact
    # --------------------------------------------------------

    artifact_out = None

    raw_artifact = agent_result.get(
        "artifact"
    )

    if raw_artifact:
        artifact = Artifact(
            session_id=session.id,
            message_id=assistant.id,
            artifact_type=(
                raw_artifact["type"]
            ),
            title=(
                raw_artifact.get(
                    "title",
                    "Generated artifact",
                )[:200]
            ),
            content=(
                raw_artifact["content"]
            ),
        )

        db.add(artifact)

        await db.flush()

        artifact_out = ArtifactOut(
            id=artifact.id,
            type=artifact.artifact_type,
            title=artifact.title,
            content=artifact.content,
        )

    # --------------------------------------------------------
    # 14. Commit assistant + artifact
    # --------------------------------------------------------

    await db.commit()
    await db.refresh(assistant)

    # --------------------------------------------------------
    # 15. Structured observability
    # --------------------------------------------------------

    total_ms = int(
        (
            time.perf_counter()
            - started
        )
        * 1000
    )

    logger.info(
        "chat_completed",
        extra={
            "session_id": session.id,
            "provider": payload.provider,
            "model": agent_result.get(
                "model"
            ),
            "mode": mode,
            "chunks_found": len(chunks),
            "retrieval_ms": retrieval_ms,
            "total_ms": total_ms,
        },
    )

    # --------------------------------------------------------
    # 16. Response
    # --------------------------------------------------------

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