import argparse
import asyncio
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.db.session import SessionLocal
from app.models import TranscriptChunk
from app.services.ollama import embed_texts


# ============================================================
# Source configuration
# ============================================================

SOURCE_REPO = "https://github.com/ChatPRD/lennys-podcast-transcripts"

SOURCE_RAW_BASE = (
    "https://github.com/ChatPRD/"
    "lennys-podcast-transcripts/blob/main/episodes"
)


# ============================================================
# Demo-friendly defaults
# ============================================================

DEFAULT_MAX_TRANSCRIPTS = int(
    os.getenv("MAX_TRANSCRIPTS", "30")
)

DEFAULT_CHUNK_SIZE = int(
    os.getenv("CHUNK_SIZE", "1500")
)

DEFAULT_CHUNK_OVERLAP = int(
    os.getenv("CHUNK_OVERLAP", "150")
)

DEFAULT_EMBED_BATCH_SIZE = int(
    os.getenv("EMBED_BATCH_SIZE", "12")
)


# ============================================================
# Metadata helpers
# ============================================================

def make_json_safe(value: Any) -> Any:
    """
    Convert YAML-loaded Python objects into values that can
    safely be stored inside PostgreSQL JSON columns.

    yaml.safe_load() may return:
      - datetime.date
      - datetime.datetime
      - other non-JSON-native values

    json.dumps(default=str) converts unsupported values
    into strings recursively.
    """
    return json.loads(
        json.dumps(
            value,
            default=str,
            ensure_ascii=False,
        )
    )


def safe_string(value: Any) -> str | None:
    """
    Safely convert optional metadata fields to strings.
    """
    if value is None:
        return None

    if isinstance(value, str):
        return value

    return str(value)


# ============================================================
# Transcript parsing
# ============================================================

def parse_transcript(path: Path) -> tuple[dict[str, Any], str]:
    """
    Read a transcript markdown file.

    Supports YAML frontmatter:

    ---
    title: Example Episode
    guest: Example Guest
    publish_date: 2024-01-01
    ---

    Transcript content...
    """

    raw = path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    if raw.startswith("---"):
        parts = raw.split("---", 2)

        if len(parts) == 3:
            try:
                metadata = yaml.safe_load(parts[1]) or {}

                if not isinstance(metadata, dict):
                    metadata = {}

            except yaml.YAMLError:
                metadata = {}

            transcript = parts[2].strip()

            return metadata, transcript

    return {}, raw.strip()


# ============================================================
# Chunking
# ============================================================

def chunk_text(
    text: str,
    words_per_chunk: int,
    overlap: int,
) -> list[str]:
    """
    Split transcript text into overlapping word-based chunks.

    Example:

    chunk_size = 1500
    overlap = 150

    Chunk 1:
      words 0 -> 1499

    Chunk 2:
      words 1350 -> 2849

    The overlap helps preserve context at chunk boundaries.
    """

    if words_per_chunk <= 0:
        raise ValueError(
            "words_per_chunk must be greater than 0"
        )

    if overlap < 0:
        raise ValueError(
            "overlap cannot be negative"
        )

    if overlap >= words_per_chunk:
        raise ValueError(
            "overlap must be smaller than words_per_chunk"
        )

    text = text.strip()

    if not text:
        return []

    words = re.split(r"\s+", text)

    if not words:
        return []

    chunks: list[str] = []

    step = words_per_chunk - overlap

    start = 0

    while start < len(words):
        end = start + words_per_chunk

        chunk_words = words[start:end]

        if not chunk_words:
            break

        # Avoid a useless tiny final chunk.
        if len(chunk_words) < 80 and chunks:
            chunks[-1] += " " + " ".join(chunk_words)
            break

        chunks.append(
            " ".join(chunk_words)
        )

        if end >= len(words):
            break

        start += step

    return chunks


# ============================================================
# Record preparation
# ============================================================

def build_records(
    root: Path,
    max_transcripts: int,
    chunk_size: int,
    overlap: int,
) -> tuple[list[dict[str, Any]], int]:
    """
    Parse transcript files and create database-ready chunk
    records.

    max_transcripts:
        15 -> first 15 usable transcripts
        30 -> first 30 usable transcripts
        0  -> all transcripts
    """

    transcript_paths = sorted(
        root.rglob("*.md")
    )

    print(
        f"Found {len(transcript_paths)} transcript files"
    )

    records: list[dict[str, Any]] = []

    selected_transcripts = 0

    for path in transcript_paths:

        # ----------------------------------------------------
        # Stop when demo limit is reached.
        # ----------------------------------------------------

        if (
            max_transcripts > 0
            and selected_transcripts >= max_transcripts
        ):
            break

        metadata, transcript = parse_transcript(path)

        # Ignore empty/unusable files.
        if len(transcript.strip()) < 200:
            continue

        selected_transcripts += 1

        relative_path = (
            path.relative_to(root)
            .as_posix()
        )

        chunks = chunk_text(
            text=transcript,
            words_per_chunk=chunk_size,
            overlap=overlap,
        )

        episode_title = (
            metadata.get("title")
            or metadata.get("episode")
            or path.parent.name
            .replace("-", " ")
            .replace("_", " ")
            .title()
        )

        guest = safe_string(
            metadata.get("guest")
        )

        publish_date = safe_string(
            metadata.get("publish_date")
            or metadata.get("date")
        )

        # Convert ALL metadata to JSON-safe values.
        safe_metadata = make_json_safe(
            {
                key: value
                for key, value in metadata.items()
                if key != "description"
            }
        )

        for chunk_index, chunk in enumerate(chunks):

            records.append(
                {
                    "id": str(uuid.uuid4()),

                    "source_repo": SOURCE_REPO,

                    "source_path": relative_path,

                    "source_url": (
                        f"{SOURCE_RAW_BASE}/"
                        f"{relative_path}"
                    ),

                    "episode_title": safe_string(
                        episode_title
                    ),

                    "guest": guest,

                    "publish_date": publish_date,

                    "chunk_index": chunk_index,

                    "content": chunk,

                    "extra_metadata": safe_metadata,
                }
            )

    return records, selected_transcripts


# ============================================================
# Database persistence
# ============================================================

async def upsert_batch(
    db,
    batch: list[dict[str, Any]],
) -> None:
    """
    Insert/update one embedding batch.

    Each batch is committed immediately so completed work
    survives if a later batch fails.
    """

    statement = insert(
        TranscriptChunk
    ).values(batch)

    statement = statement.on_conflict_do_update(
        constraint="uq_source_chunk",
        set_={
            "source_url":
                statement.excluded.source_url,

            "episode_title":
                statement.excluded.episode_title,

            "guest":
                statement.excluded.guest,

            "publish_date":
                statement.excluded.publish_date,

            "content":
                statement.excluded.content,

            "embedding":
                statement.excluded.embedding,

            "extra_metadata":
                statement.excluded.extra_metadata,
        },
    )

    await db.execute(statement)

    await db.commit()


# ============================================================
# Main ingestion pipeline
# ============================================================

async def ingest(
    root: Path,
    replace: bool,
    max_transcripts: int,
    chunk_size: int,
    overlap: int,
    embed_batch_size: int,
) -> None:
    """
    Complete RAG ingestion pipeline:

        transcript files
              ↓
        parse metadata
              ↓
        split into chunks
              ↓
        embed batch
              ↓
        store batch
              ↓
        commit
              ↓
        next batch
    """

    if not root.exists():
        raise RuntimeError(
            f"Transcript directory does not exist: {root}. "
            "Run fetch_transcripts.py first."
        )

    records, selected_transcripts = build_records(
        root=root,
        max_transcripts=max_transcripts,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    if not records:
        raise RuntimeError(
            f"No transcript chunks found under {root}"
        )

    total_records = len(records)

    print()
    print("=" * 65)
    print("INGESTION CONFIGURATION")
    print("=" * 65)

    print(
        f"Transcripts selected : {selected_transcripts}"
    )

    print(
        f"Chunks prepared      : {total_records}"
    )

    print(
        f"Chunk size           : {chunk_size} words"
    )

    print(
        f"Chunk overlap        : {overlap} words"
    )

    print(
        f"Embedding batch size : {embed_batch_size}"
    )

    print(
        f"Replace existing     : {replace}"
    )

    print("=" * 65)
    print()

    async with SessionLocal() as db:

        # ----------------------------------------------------
        # Optional clean ingestion
        # ----------------------------------------------------

        if replace:
            print(
                "Clearing existing transcript chunks..."
            )

            await db.execute(
                delete(TranscriptChunk)
            )

            await db.commit()

            print(
                "Existing transcript chunks cleared."
            )

            print()

        # ----------------------------------------------------
        # Embed + persist incrementally
        # ----------------------------------------------------

        for start in range(
            0,
            total_records,
            embed_batch_size,
        ):

            batch = records[
                start:
                start + embed_batch_size
            ]

            texts = [
                record["content"]
                for record in batch
            ]

            batch_number = (
                start // embed_batch_size
            ) + 1

            try:
                embeddings = await embed_texts(
                    texts
                )

            except Exception as exc:
                print()
                print(
                    f"Embedding failed on batch "
                    f"{batch_number}"
                )

                print(
                    f"Chunk range: "
                    f"{start + 1}-"
                    f"{start + len(batch)}"
                )

                raise RuntimeError(
                    "Ollama embedding request failed"
                ) from exc

            if len(embeddings) != len(batch):
                raise RuntimeError(
                    "Embedding count mismatch: "
                    f"expected {len(batch)}, "
                    f"received {len(embeddings)}"
                )

            # Attach embeddings to DB records.
            for record, embedding in zip(
                batch,
                embeddings,
                strict=True,
            ):
                record["embedding"] = embedding

            # Store this batch immediately.
            try:
                await upsert_batch(
                    db,
                    batch,
                )

            except Exception:
                await db.rollback()
                raise

            completed = min(
                start + len(batch),
                total_records,
            )

            percentage = (
                completed
                / total_records
                * 100
            )

            print(
                f"Embedded + stored "
                f"{completed}/{total_records} chunks "
                f"({percentage:.1f}%)"
            )

    print()
    print("=" * 65)

    print(
        f"Ingestion complete: "
        f"{total_records} chunks "
        f"from {selected_transcripts} transcripts."
    )

    print("=" * 65)


# ============================================================
# CLI
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Index Lenny podcast transcripts "
            "into PostgreSQL + pgvector."
        )
    )

    parser.add_argument(
        "--input",
        default="/data/transcripts",
        help=(
            "Directory containing downloaded "
            "transcript markdown files."
        ),
    )

    parser.add_argument(
        "--replace",
        action="store_true",
        help=(
            "Delete existing transcript chunks "
            "before indexing."
        ),
    )

    parser.add_argument(
        "--max-transcripts",
        type=int,
        default=DEFAULT_MAX_TRANSCRIPTS,
        help=(
            "Maximum number of transcripts to index. "
            "Use 0 for the complete corpus."
        ),
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=(
            "Approximate words per transcript chunk."
        ),
    )

    parser.add_argument(
        "--overlap",
        type=int,
        default=DEFAULT_CHUNK_OVERLAP,
        help=(
            "Word overlap between adjacent chunks."
        ),
    )

    parser.add_argument(
        "--embed-batch-size",
        type=int,
        default=DEFAULT_EMBED_BATCH_SIZE,
        help=(
            "Chunks sent to Ollama per embedding request."
        ),
    )

    args = parser.parse_args()

    # ========================================================
    # CLI validation
    # ========================================================

    if args.max_transcripts < 0:
        parser.error(
            "--max-transcripts must be 0 or greater"
        )

    if args.chunk_size <= 0:
        parser.error(
            "--chunk-size must be greater than 0"
        )

    if args.overlap < 0:
        parser.error(
            "--overlap cannot be negative"
        )

    if args.overlap >= args.chunk_size:
        parser.error(
            "--overlap must be smaller than --chunk-size"
        )

    if args.embed_batch_size <= 0:
        parser.error(
            "--embed-batch-size must be greater than 0"
        )

    asyncio.run(
        ingest(
            root=Path(args.input),

            replace=args.replace,

            max_transcripts=args.max_transcripts,

            chunk_size=args.chunk_size,

            overlap=args.overlap,

            embed_batch_size=args.embed_batch_size,
        )
    )


if __name__ == "__main__":
    main()