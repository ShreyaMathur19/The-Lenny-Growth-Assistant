# PRD — The Lenny Growth Assistant

## 1. Discovery brief

### Primary user and job

Primary user: a product manager, growth lead, founder, or operator who wants to reuse Lenny's Podcast knowledge while making a product/growth decision or producing internal content.

Job to be done: ask a natural-language question, receive a trustworthy synthesis grounded in relevant transcripts, continue the conversation, and turn that research into reusable written or visual artifacts without learning prompt engineering, model configuration, or retrieval infrastructure.

### Pain removed

Today the user must search many long transcripts, manually compare advice across episodes, keep track of sources, and then reformat the research for a memo/essay/brief. The assistant compresses this workflow while keeping the underlying transcript evidence visible.

### Success metrics

Primary product metric:

- **Grounded answer rate:** at least 90% of supported evaluation questions return an answer with at least one relevant transcript source and inline `[S#]` citation.

Operational metrics:

- 100% of conversations survive app refresh/restart once persisted to PostgreSQL.
- 100% of generated HTML artifacts execute no JavaScript in the application viewer.
- Health endpoint identifies database and Ollama availability without exposing credentials.
- Target median local Q&A latency: <15 seconds on the documented machine after models are warm (hardware-dependent, treated as a target rather than a guarantee).

### Assumptions

1. This is an internal single-tenant evaluation product; authentication and enterprise authorization are not required for the take-home.
2. Public Lenny transcript data is permitted for the evaluation and source links should remain traceable.
3. Local Ollama quality/latency will vary by evaluator hardware.
4. The evaluator values reproducibility and graceful failure more than sophisticated autonomous agent behavior.
5. Markdown and non-scripted HTML cover the artifact requirement sufficiently while keeping rendering safe.

## 2. Scope

### Included

- independent persisted chat sessions
- source-grounded RAG over Lenny transcripts
- follow-up conversation context
- explicit source cards and citations
- local Ollama demo path
- optional cloud-provider path
- dedicated Ship 30 for 30 skill
- Markdown/HTML artifacts rendered beside chat
- artifact sanitization/isolation
- structured logs, health endpoint, and clear errors
- Docker Compose workflow
- automated critical-path tests plus manual UI test plan

### Intentionally excluded

- authentication / SSO / RBAC
- multi-tenant data isolation
- web-wide search
- transcript editing/content CMS
- arbitrary JavaScript artifacts
- Kubernetes/autoscaling
- advanced agent planning/multi-agent orchestration
- analytics/admin dashboard

Reason: these do not improve the core evaluator journey enough to justify their implementation and operational risk in a take-home.

## 3. Core user flows

### Flow A — grounded Q&A

1. User creates a chat.
2. User asks a product/growth question.
3. System embeds the query and retrieves the top transcript chunks.
4. Pi agent receives only the relevant chunks plus recent chat history.
5. Assistant synthesizes the answer and attaches `[S#]` citations.
6. UI exposes readable source cards with transcript links.
7. Conversation is persisted.

### Flow B — follow-up

1. User asks a follow-up in the same session.
2. Recent conversation is provided as conversational context.
3. Retrieval runs again for the current request.
4. Factual claims still require support from current retrieved transcript context.

### Flow C — Ship30

1. User selects Ship30 or requests an essay.
2. Router selects the dedicated Ship30 skill.
3. Retrieval supplies supporting transcript evidence.
4. Skill produces approximately 1,250 words with a strong hook, progression, skimmable formatting, and actionable takeaway.
5. Claims remain source cited.

### Flow D — artifact

1. User requests Markdown or HTML from the current conversation.
2. Artifact skill returns a typed artifact payload.
3. Backend persists the artifact separately from the assistant message.
4. Frontend opens the artifact beside chat.
5. HTML is sanitized then rendered in a sandboxed iframe.

## 4. Acceptance criteria

### Sessions / persistence

- New Chat creates a new server-side session ID.
- Two sessions do not share message history.
- Refreshing and reopening a session loads persisted messages.
- Messages include timestamps and provider/model metadata where applicable.

### Grounding

- Answers identify transcript sources.
- Assistant does not claim unsupported knowledge when retrieval is empty.
- Source metadata is traceable back to transcript path/URL.

### Models

- Ollama is visibly selectable and is the default demo provider.
- Cloud provider can be configured without application-code changes.
- Missing keys or unavailable models produce clear errors.

### Ship30

- implemented as a separate reusable skill file
- target length approximately 1,250 words when evidence supports it
- strong opener and progression
- headings/lists/selective bold emphasis
- specific takeaway
- grounded claims use source citations

### Artifacts

- Markdown renders natively in the side panel.
- HTML renders natively in the side panel.
- model-generated scripts/event handlers do not execute.
- artifact can be closed without destroying chat state.

### Operations

- documented first-time bootstrap path
- normal startup uses `docker compose up --build`
- `.env.example` contains no secrets
- health reports database/Ollama state
- structured logs contain enough fields to diagnose retrieval/model latency

## 5. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Hallucination | User trusts unsupported advice | Retrieval-only grounding contract, citations, explicit insufficient-evidence behavior |
| Weak local model | Poor synthesis/JSON compliance | Small skills, low-complexity output contract, structured fallback, optional cloud provider |
| Retrieval miss | Relevant transcript omitted | overlapping chunks, top-k retrieval, traceability; reranking is future extension |
| Long latency | Poor UX | visible thinking state, structured latency logs, small default model |
| Model/API cost | Cloud usage can grow | local default, provider visibility, no silent cloud fallback |
| Data leakage | Sensitive prompt sent to cloud | local default; provider explicitly chosen by user |
| Unsafe HTML | XSS / exfiltration | skill restrictions + DOMPurify + sandboxed iframe + no scripts/referrer |
| DB failure | sessions lost/unavailable | health degradation, structured errors, durable PostgreSQL volume |
| Pi catalog drift | cloud model ID may change | environment-configured model; local model registered explicitly |

## 6. Implementation plan

1. Establish repository boundaries, Docker services, DB schema and migrations.
2. Build transcript fetch/chunk/embed/upsert pipeline.
3. Build vector retrieval with source metadata.
4. Implement Pi agent service with local Ollama model registration.
5. Add explicit skills and deterministic router.
6. Build FastAPI sessions/chat orchestration and persistence.
7. Build React chat UI and artifact viewer.
8. Add security, errors, logs and health checks.
9. Add tests and clean-clone documentation.
10. Validate local Ollama demo and record 2–3 minute walkthrough.
