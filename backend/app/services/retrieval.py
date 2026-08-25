from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.models import TranscriptChunk
from app.services.ollama import embed_texts

settings = get_settings()


async def retrieve_chunks(db: AsyncSession, query: str, top_k: int | None = None) -> list[dict]:
    [embedding] = await embed_texts([query])
    distance = TranscriptChunk.embedding.cosine_distance(embedding).label("distance")
    stmt = (
        select(TranscriptChunk, distance)
        .order_by(distance)
        .limit(top_k or settings.top_k)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "id": chunk.id,
            "content": chunk.content,
            "source_path": chunk.source_path,
            "source_url": chunk.source_url,
            "episode_title": chunk.episode_title,
            "guest": chunk.guest,
            "score": max(0.0, 1.0 - float(dist)),
        }
        for chunk, dist in rows
    ]
