# Architecture — The Lenny Growth Assistant

## 1. Component boundaries

### React frontend

Responsibilities:
- session navigation
- model/mode selection
- chat rendering
- source disclosure
- Markdown artifact rendering
- HTML sanitization and iframe isolation

It does not call model providers directly and does not own authoritative session state.

### FastAPI backend

Responsibilities:
- public API contracts and validation
- session/message/artifact persistence
- current-turn retrieval
- orchestration of Pi agent service
- source metadata returned to UI
- structured logging and health

### Pi agent service

Responsibilities:
- satisfy required Pi Coding Agent SDK integration
- register local Ollama as a custom model provider
- load dedicated skills
- choose configured local/cloud model
- run isolated in-memory agent sessions
- enforce system-level grounding/output contracts

The service has no direct database access.

### PostgreSQL + pgvector

Stores:
- chat sessions
- messages
- artifacts
- transcript chunks and vectors

### Ollama

Two responsibilities:
- local generation via Pi's OpenAI-compatible provider integration
- transcript/query embeddings through Ollama's embedding API

## 2. Database schema

### `chat_sessions`

- `id` UUID string PK
- `user_id`
- `title`
- `user_metadata` JSON
- `created_at`, `updated_at`

### `messages`

- `id` PK
- `session_id` FK
- `role`
- `content`
- `provider`, `model`
- `source_metadata` JSON snapshot
- `created_at`

Source metadata is copied into the assistant message so past responses remain explainable even if the transcript index changes later.

### `artifacts`

- `id` PK
- `session_id`, `message_id` FKs
- `artifact_type`
- `title`
- `content`
- `created_at`

### `transcript_chunks`

- source repo/path/URL
- episode title, guest, publish date
- `chunk_index`
- chunk content
- vector embedding
- additional metadata JSON

Unique `(source_path, chunk_index)` makes ingestion idempotent. HNSW cosine index supports vector search.

## 3. Retrieval flow

```text
question
  -> Ollama embedding model
  -> cosine vector search in pgvector
  -> top K chunks
  -> context labels [S1..Sk]
  -> Pi skill + selected generation model
  -> answer
  -> same source metadata returned to UI
```

Chunking default: approximately 700 words with 100-word overlap. This is intentionally understandable and easy to tune. A later version could switch to semantic boundaries/token-aware chunking and add a reranker.

## 4. Session-context strategy

FastAPI stores the full conversation and sends the most recent 12 messages to Pi on each request. Pi uses an in-memory session per request; PostgreSQL is the durable source of truth.

Why: durable state remains provider/SDK-independent, server restarts do not lose context, and Pi's internal session format is not coupled to the product database.

Grounding rule: conversation history helps resolve references ("that framework"), but factual claims must still be supported by transcript chunks retrieved for the current turn.

## 5. Agent routing

Routing is deterministic:

- request mentions HTML/Markdown/artifact/dashboard/render -> Artifact
- request mentions Ship30 / 30 for 30 / essay / long-form -> Ship30
- otherwise -> Q&A

The UI can override Auto with an explicit mode. This avoids spending a model call on classification and makes failure behavior easy to test. A learned router can replace `detect_mode()` later.

## 6. Pi SDK integration

The agent service uses `ModelRuntime` and `createAgentSession()` from `@earendil-works/pi-coding-agent`.

At runtime it writes a minimal Pi custom-model configuration for Ollama:

- provider ID `ollama`
- OpenAI-compatible completions API
- `http://ollama:11434/v1`
- dummy local key because Ollama does not require auth
- configured chat model ID

No tools are enabled for generation because the application performs retrieval explicitly and supplies trusted context. This reduces the agent's authority and prevents accidental filesystem/shell access.

Cloud provider/model IDs are environment-driven and resolved through Pi's model runtime. API keys are passed to Pi as runtime credentials, not written to the repository.

## 7. Artifact security

Generated HTML is untrusted.

### Generation-time restriction

Artifact skill tells the model not to emit JavaScript, forms, iframe/object/embed content, event handlers, or external scripts.

### Sanitization

Frontend passes HTML through DOMPurify with additional forbidden tags/attributes.

### Isolation

Sanitized markup is assigned to `srcDoc` on:

```html
<iframe sandbox="" referrerpolicy="no-referrer">
```

No `allow-scripts` and no `allow-same-origin` are granted. This is intentionally restrictive.

### Trade-off

Interactive JS artifacts are excluded. The security simplification is appropriate for an internal take-home where the requirement is rendered HTML/CSS, not arbitrary application execution.

## 8. API contracts

`POST /api/chat` accepts:

- session ID
- message
- provider (`ollama|cloud`)
- mode (`auto|qa|ship30|artifact`)
- artifact type (`markdown|html`)

It returns:

- persisted assistant message
- resolved mode
- source metadata
- optional persisted artifact

Errors use stable codes inside FastAPI `detail` objects so the UI can evolve without parsing arbitrary exception strings.

## 9. Observability

Backend structured logs include:

- `session_id`
- `provider`
- `model`
- `mode`
- `chunks_found`
- `retrieval_ms`
- `total_ms`

Agent service emits JSON events for service startup and generation failure. Health reports database and Ollama availability.

Production extension: add request IDs/tracing across FastAPI -> Pi service -> Ollama, metrics, and centralized log shipping.

## 10. Resilience / failure modes

- unavailable embedding model: fail fast with setup guidance rather than generating ungrounded content
- empty retrieval: no model call; return explicit unsupported answer
- agent timeout: 504-style model timeout response
- unavailable agent service: 503
- cloud key missing: explicit error, no silent provider switch
- malformed artifact JSON: preserve model result as a Markdown artifact so the viewer stays safe and the request is not lost
- DB outage: degraded health and generic client error without secrets

## 11. Deployment topology

Docker Compose services:

```text
frontend -> backend -> postgres
                 \-> agent -> ollama/cloud
                 \-> ollama embeddings
```

Named volumes preserve Postgres and Ollama model data. Transcript files are host-mounted under `data/` so refresh/re-ingest is visible and controllable.

## 12. Security boundaries beyond artifacts

- `.env` ignored; `.env.example` contains no secrets
- cloud keys only enter the agent container as environment variables
- public API validates request lengths/types
- model receives only retrieved public transcript context + recent conversation
- Pi built-in tools are disabled
- backend generic exception handler prevents raw stack traces from reaching clients
- transcript source URL/path remains visible for auditability

## 13. Known limitations / next steps

1. Add auth/session ownership before multi-user production deployment.
2. Add hybrid keyword+vector retrieval and reranking.
3. Add streaming/SSE for better perceived latency.
4. Add E2E browser tests and containerized pgvector integration tests.
5. Add transcript refresh/version metadata and background ingestion job.
6. Add evaluation set measuring citation precision, answer faithfulness, retrieval recall and local-vs-cloud quality.
