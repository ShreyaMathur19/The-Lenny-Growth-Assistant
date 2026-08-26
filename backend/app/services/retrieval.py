import logging
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TranscriptChunk
from app.services.ollama import embed_texts


logger = logging.getLogger("lenny.retrieval")


# ============================================================
# Retrieval configuration
# ============================================================
#
# Vector databases ALWAYS return the nearest records.
#
# "Nearest" does not necessarily mean "relevant".
#
# For example:
#
#   User question:
#       "How should I design a quantum computer?"
#
# The database may still return product-growth transcripts
# because they are technically the nearest available vectors.
#
# We therefore apply a minimum similarity threshold.
#
# Default:
#     0.60
#
# Can be changed using:
#
#     MIN_RETRIEVAL_SIMILARITY=0.60
#
# without modifying application code.
# ============================================================

MIN_SIMILARITY = float(
    os.getenv(
        "MIN_RETRIEVAL_SIMILARITY",
        "0.60",
    )
)


async def retrieve_chunks(
    db: AsyncSession,
    query: str,
    top_k: int = 6,
) -> list[dict]:
    """
    Retrieve transcript chunks relevant to the user's query.

    Workflow:

        User query
            ↓
        Ollama embedding
            ↓
        pgvector cosine-distance search
            ↓
        Candidate chunks
            ↓
        Convert distance → similarity
            ↓
        Apply MIN_SIMILARITY
            ↓
        Return only relevant transcript chunks

    If no chunk passes the threshold, this function returns [].

    routes.py should then return the deterministic
    "insufficient evidence" response without calling the LLM.
    """

    # ========================================================
    # 1. Validate query
    # ========================================================

    query = query.strip()

    if not query:
        return []

    # ========================================================
    # 2. Generate query embedding
    # ========================================================

    embeddings = await embed_texts(
        [query]
    )

    if not embeddings:
        logger.warning(
            "retrieval_embedding_empty",
            extra={
                "query_preview": query[:100],
            },
        )

        return []

    query_embedding = embeddings[0]

    # ========================================================
    # 3. Build cosine-distance expression
    # ========================================================
    #
    # Cosine distance:
    #
    #     0.0 → extremely similar
    #     1.0 → unrelated
    #
    # We later convert this to:
    #
    #     similarity = 1 - distance
    #
    # Therefore:
    #
    #     1.0 similarity → very similar
    #     0.0 similarity → unrelated
    #
    # ========================================================

    distance = (
        TranscriptChunk.embedding
        .cosine_distance(
            query_embedding
        )
    )

    # ========================================================
    # 4. Retrieve more candidates than we ultimately need
    # ========================================================
    #
    # Example:
    #
    # top_k = 6
    #
    # We fetch ~18 candidates first.
    #
    # Some may be rejected by the relevance threshold.
    #
    # Then we return up to 6 genuinely relevant chunks.
    # ========================================================

    candidate_limit = max(
        top_k * 3,
        12,
    )

    stmt = (
        select(
            TranscriptChunk,
            distance.label(
                "distance"
            ),
        )
        .order_by(
            distance.asc()
        )
        .limit(
            candidate_limit
        )
    )

    result = await db.execute(
        stmt
    )

    rows = result.all()

    if not rows:
        logger.info(
            "retrieval_no_candidates",
            extra={
                "query_preview":
                    query[:100],
            },
        )

        return []

    # ========================================================
    # 5. Apply semantic relevance threshold
    # ========================================================

    retrieved: list[dict] = []

    highest_similarity = None

    for chunk, distance_value in rows:

        if distance_value is None:
            continue

        cosine_distance = float(
            distance_value
        )

        similarity = (
            1.0 - cosine_distance
        )

        if highest_similarity is None:
            highest_similarity = similarity
        else:
            highest_similarity = max(
                highest_similarity,
                similarity,
            )

        # ----------------------------------------------------
        # Temporary but useful logging.
        #
        # This allows us to compare:
        #
        # Adam Fishman question:
        #     similarity ~0.7+
        #
        # Quantum-computer question:
        #     similarity ~0.3-0.5
        #
        # Then MIN_SIMILARITY can be tuned accurately.
        # ----------------------------------------------------

        logger.info(
            "retrieval_candidate",
            extra={
                "query_preview":
                    query[:100],

                "episode":
                    chunk.episode_title,

                "guest":
                    chunk.guest,

                "similarity":
                    round(
                        similarity,
                        4,
                    ),

                "threshold":
                    MIN_SIMILARITY,
            },
        )

        # ----------------------------------------------------
        # Reject semantically weak evidence.
        # ----------------------------------------------------

        if similarity < MIN_SIMILARITY:
            continue

        # ----------------------------------------------------
        # Candidate passed relevance threshold.
        # ----------------------------------------------------

        retrieved.append(
            {
                "id":
                    chunk.id,

                "episode_title":
                    chunk.episode_title,

                "guest":
                    chunk.guest,

                "source_url":
                    chunk.source_url,

                "source_path":
                    chunk.source_path,

                "chunk_index":
                    chunk.chunk_index,

                "content":
                    chunk.content,

                "similarity":
                    similarity,
            }
        )

        # We only need top_k accepted chunks.
        if len(retrieved) >= top_k:
            break

    # ========================================================
    # 6. Log final retrieval decision
    # ========================================================

    logger.info(
        "retrieval_completed",
        extra={
            "query_preview":
                query[:100],

            "candidates_checked":
                len(rows),

            "chunks_accepted":
                len(retrieved),

            "highest_similarity":
                (
                    round(
                        highest_similarity,
                        4,
                    )
                    if highest_similarity
                    is not None
                    else None
                ),

            "minimum_similarity":
                MIN_SIMILARITY,
        },
    )

    # ========================================================
    # 7. Return relevant evidence
    # ========================================================

    return retrieved