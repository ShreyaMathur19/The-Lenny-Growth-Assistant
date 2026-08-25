"""initial schema

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("user_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])
    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(120), nullable=True),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.String(36), sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("artifact_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_artifacts_session_id", "artifacts", ["session_id"])
    op.create_table(
        "transcript_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_repo", sa.String(300), nullable=False),
        sa.Column("source_path", sa.String(500), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("episode_title", sa.String(500), nullable=True),
        sa.Column("guest", sa.String(300), nullable=True),
        sa.Column("publish_date", sa.String(30), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column("extra_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_path", "chunk_index", name="uq_source_chunk"),
    )
    op.create_index("ix_transcript_chunks_source_path", "transcript_chunks", ["source_path"])
    op.execute("CREATE INDEX IF NOT EXISTS ix_transcript_chunks_embedding_hnsw ON transcript_chunks USING hnsw (embedding vector_cosine_ops)")


def downgrade():
    op.drop_table("transcript_chunks")
    op.drop_table("artifacts")
    op.drop_table("messages")
    op.drop_table("chat_sessions")
