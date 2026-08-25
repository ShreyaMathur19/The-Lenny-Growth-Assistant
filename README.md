# The Lenny Growth Assistant

A full-stack, AI-powered product and growth assistant grounded in Lenny's Podcast transcripts. It supports source-grounded conversational Q&A, a dedicated Ship 30 for 30 writing skill, local Ollama and optional cloud models through the Pi Coding Agent SDK, and safe in-app Markdown/HTML artifacts.

## What is implemented

- **FastAPI backend** with typed request/response contracts, sessions, structured errors, health endpoint, and PostgreSQL persistence.
- **PostgreSQL + pgvector** transcript store with Ollama embeddings and cosine-similarity retrieval.
- **Pi Coding Agent SDK service** with explicit Q&A, Ship30, and Artifact skills.
- **Local Ollama path** for the submitted demo plus optional Anthropic/OpenAI cloud model configuration.
- **React/Vite frontend** with session history, model/mode selectors, source cards, responsive UI, and an artifact side panel.
- **Safe artifact rendering** using DOMPurify plus a sandboxed iframe without script permissions.
- **Docker Compose**, Alembic migrations, structured logging, automated tests, and transcript ingestion scripts.

## Architecture

```text
Browser (React)
      |
      v
FastAPI :8000 ------------------> PostgreSQL + pgvector
      |                                  ^
      |                                  |
      |                            transcript chunks
      |                                  ^
      |                                  |
      +--> Retrieval --> Ollama /api/embed
      |
      +--> Pi Agent Service :3001 --> Ollama (local demo)
                                 \--> Anthropic/OpenAI (optional)
```

FastAPI owns product state, retrieval, persistence, and API contracts. The Node service is intentionally narrow: it is the required Pi agent layer and owns model selection plus skill execution. This keeps model/provider concerns out of the application API.

## Prerequisites

- Docker Engine + Docker Compose v2
- 8 GB RAM recommended for the default local model; more is helpful while indexing
- Internet access once to pull Docker images, Ollama models, npm/pip packages during builds, and the public transcript archive

## Quick start

### 1. Configure

```bash
cp .env.example .env
```

Cloud keys are optional. Never commit `.env`.

### 2. First-time data/model bootstrap

```bash
./scripts/bootstrap.sh
```

This starts PostgreSQL/Ollama, pulls the configured local chat and embedding models, downloads the public transcript archive, applies migrations, and indexes transcript chunks.

### 3. Start the product

```bash
docker compose up --build
```

Open:

- UI: `http://localhost:5173`
- FastAPI docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/health`

After the first bootstrap, normal startup is one command: `docker compose up --build`.

## Transcript source and ingestion

Default source: `https://github.com/ChatPRD/lennys-podcast-transcripts`.

The downloader extracts the repository's `episodes/**/transcript.md` files to `data/transcripts/`. The ingestion job:

1. Parses YAML frontmatter when present.
2. Preserves guest, title, publish date, path, and source URL.
3. Splits each transcript into ~700-word chunks with ~100-word overlap.
4. Creates embeddings with the configured Ollama embedding model.
5. Upserts the chunks into PostgreSQL/pgvector.
6. Retrieval returns the closest chunks and exposes traceable source metadata to both the model and UI.

Manual refresh:

```bash
docker compose run --rm backend python scripts/fetch_transcripts.py
docker compose run --rm backend python scripts/ingest_transcripts.py --replace
```

The archive is intentionally not committed to this repository so the evaluator gets the public source directly and the code repository stays small.

## LLM configuration

### Local Ollama — required demo path

Defaults:

```env
OLLAMA_CHAT_MODEL=llama3.2:3b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

The Pi service generates a custom `models.json` at runtime and registers Ollama through its OpenAI-compatible `/v1` endpoint.

### Cloud model — optional

```env
CLOUD_PROVIDER=anthropic
CLOUD_MODEL=claude-sonnet-4-5
ANTHROPIC_API_KEY=...
```

Or set `CLOUD_PROVIDER=openai`, choose a model available to the installed Pi catalog, and provide `OPENAI_API_KEY`.

The UI exposes **Ollama · Local** and **Cloud**. Missing cloud keys return a structured service error instead of silently falling back.

## Product modes

### Q&A

Retrieves transcript chunks and asks the Q&A skill to answer only from supplied evidence. Grounded claims use `[S1]`, `[S2]`, etc. Source cards in the UI link back to transcript files.

### Ship 30 for 30

A separate `agent-service/skills/ship30/SKILL.md` encodes the writing behavior rather than relying on a one-off prompt. It targets an approximately 1,250-word essay with a strong opener, clear progression, skimmable subheads/lists, varied rhythm, selective emphasis, and a useful takeaway—all still constrained to transcript evidence.

### Artifact

Produces a structured response containing a short assistant message plus Markdown or HTML artifact content. The artifact is persisted separately from chat messages.

## Artifact security

Generated HTML is treated as untrusted.

Defense in depth:

1. The agent skill forbids JavaScript, forms, iframes, embeds, external scripts, and event handlers.
2. The frontend sanitizes generated HTML with DOMPurify and explicit forbidden tags/attributes.
3. Sanitized HTML renders in an `<iframe sandbox="">` with no `allow-scripts`, no same-origin grant, and `no-referrer`.
4. The main application never inserts raw model HTML directly into its DOM.

This intentionally trades interactive JavaScript artifacts for a much smaller security surface in the take-home.

## API surface

- `GET /api/health`
- `GET /api/config`
- `POST /api/sessions`
- `GET /api/sessions`
- `GET /api/sessions/{session_id}/messages`
- `GET /api/sessions/{session_id}/artifacts`
- `POST /api/chat`

Example chat request:

```json
{
  "session_id": "...",
  "message": "What do Lenny's guests say about improving activation?",
  "provider": "ollama",
  "mode": "auto",
  "artifact_type": "markdown"
}
```

## Failure behavior

The application handles these deliberately:

- Ollama/embedding endpoint unavailable -> `OLLAMA_UNAVAILABLE`
- agent/model timeout -> `MODEL_TIMEOUT`
- agent service unavailable -> `AGENT_UNAVAILABLE`
- cloud key missing -> explicit agent error
- unknown session -> `SESSION_NOT_FOUND`
- no retrieved chunks -> assistant says the indexed material does not support the answer
- database failure -> health becomes degraded; unhandled errors return a generic error without secrets
- malformed artifact model output -> safe Markdown fallback rather than unsafe rendering

Structured logs record session ID, provider/model, route mode, number of chunks, retrieval latency, and total latency.

## Tests

Local backend tests:

```bash
docker compose run --rm backend pytest -q
```

Agent type check:

```bash
cd agent-service
npm install
npm run typecheck
```

Frontend production build:

```bash
cd frontend
npm install
npm run build
```

Critical automated coverage includes routing, transcript chunking, and agent-service contract behavior. A production extension would add containerized PostgreSQL integration tests for persistence/vector retrieval and browser E2E tests.

## Manual UI test plan

1. Create two chats and verify history remains independent.
2. Ask a grounded question and verify source cards + `[S#]` citations are present.
3. Ask a follow-up; verify the previous turn is included while facts remain grounded in newly retrieved context.
4. Select Ship30 and verify long-form, skimmable output with citations.
5. Select Artifact -> Markdown and verify native side-panel rendering.
6. Select Artifact -> HTML and verify it renders beside chat.
7. Ask the model to include `<script>alert(1)</script>` in an HTML artifact; verify no script executes.
8. Stop Ollama and verify a clear availability error.
9. Select Cloud without a key and verify a clear configuration error.
10. Resize below 700 px and verify the chat remains usable and artifact viewer becomes a full-width overlay.

## Troubleshooting

### `OLLAMA_UNAVAILABLE`

```bash
docker compose up -d ollama
docker compose --profile setup run --rm ollama-init
```

### No transcript results

Check chunk count:

```bash
docker compose exec postgres psql -U postgres -d lenny -c "select count(*) from transcript_chunks;"
```

If zero, rerun the ingestion commands in the transcript section.

### Cloud model not found

Pi's model catalog changes over time. Set `CLOUD_MODEL` to an ID present in your installed Pi version/provider catalog. The local Ollama model does not depend on the remote catalog.

### Reset local data

```bash
docker compose down -v
rm -rf data/transcripts/*
```

Then rerun `./scripts/bootstrap.sh`.

## Repository guide

```text
backend/                 FastAPI, DB models, retrieval, migrations, ingestion
agent-service/           Pi SDK model layer and reusable skills
frontend/                React chat + Artifact Viewer
scripts/                 bootstrap/check commands
agent-transcripts/       sanitized AI-assisted development notes
PRD.md                   discovery brief, scope, success, acceptance criteria
architecture.md          detailed technical architecture and trade-offs
design.md                interaction/UX decisions and states
```

## Handoff / extension points

- Add reranking in `backend/app/services/retrieval.py` without changing API contracts.
- Add a new writing capability as a separate skill and explicit route rather than growing the base prompt.
- Add authentication by replacing the demo `user_id` with authenticated identity and applying session ownership checks.
- Replace the local transcript fetcher with an approved internal data pipeline while preserving source metadata.
- Add streaming by exposing SSE/WebSocket from FastAPI while consuming Pi's delta events.

## Important trade-offs

- **Retrieval over full-corpus long context:** lower context cost and better traceability; quality depends on chunking/embeddings.
- **FastAPI + small Node Pi service:** slightly more operational surface, but satisfies the required FastAPI API and Pi agent layer with clear boundaries.
- **No arbitrary JS artifacts:** less interactivity, much stronger default safety.
- **Simple heuristic routing:** deterministic and debuggable for the take-home; a classifier/tool-router can replace it later.
- **No authentication:** intentionally out of scope for this internal-assistant MVP; sessions still persist user metadata and are structured for future ownership controls.
