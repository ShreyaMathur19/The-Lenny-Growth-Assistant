# Sanitized review / correction log

## Review checklist

- Requirement: FastAPI backend -> implemented.
- Requirement: independent persisted sessions -> PostgreSQL chat sessions/messages.
- Requirement: cloud + local model toggle -> Ollama + environment-selected Pi cloud provider.
- Requirement: local Ollama demo -> default provider/model in UI and Compose.
- Requirement: grounded transcript answers -> vector retrieval + [S#] context labels + source cards.
- Requirement: dedicated Ship30 skill -> separate SKILL.md.
- Requirement: native Markdown/HTML artifacts -> side panel.
- Requirement: untrusted HTML isolation -> model restrictions + DOMPurify + sandbox iframe.
- Requirement: one-command normal startup -> Docker Compose; documented first-time model/data bootstrap.
- Requirement: logs/resilience -> structured logs, health, explicit errors.
- Requirement: handoff docs -> README, PRD, design, architecture.

## Deliberate simplifications

- Authentication omitted for internal evaluation scope.
- Heuristic route selection instead of an LLM classifier.
- No arbitrary JavaScript artifacts.
- No background ingestion worker; ingestion is a reproducible explicit operation.

## Remaining environment-dependent validation

A clean machine must still pull Docker/npm/pip/Ollama assets and the transcript archive. Local model quality/latency is hardware dependent; the cloud provider path also depends on a valid API key/model ID.
