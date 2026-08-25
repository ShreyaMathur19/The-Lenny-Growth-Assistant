# Sanitized AI-assisted build log

This folder is intentionally committed because the take-home asks for coding-agent transcripts/logs, including decisions and corrections. Secrets and private candidate data are excluded.

## Task

Build a full-stack "Lenny Growth Assistant" with FastAPI, PostgreSQL, Pi Coding Agent SDK, local Ollama, grounded transcript retrieval, Ship30 skill, artifact viewer, deployment/docs/tests.

## Key reasoning / direction

- Started from the evaluator journey rather than a broad feature list: Q&A -> follow-up -> Ship30 -> artifact -> local model visibility.
- Chose explicit retrieval in FastAPI and a narrow Pi generation service. This makes source grounding testable and leaves persistence independent of the SDK's internal session format.
- Chose pgvector in the required PostgreSQL database rather than adding a second vector database.
- Chose restrictive HTML artifacts (no arbitrary JS) to reduce XSS/exfiltration risk.

## Corrected approach

### Initial idea

Call Ollama directly from FastAPI for all generation because it is the simplest implementation.

### Problem found

That would satisfy local-model behavior but would not satisfy the assignment's explicit requirement for an Anthropic Claude Agent SDK or Pi Coding Agent layer.

### Correction

Introduced `agent-service/`, integrated Pi's SDK programmatically, registered Ollama as a Pi custom model, and kept FastAPI as the product API/orchestration layer.

## Validation focus

- model/provider can change by environment configuration
- no Pi filesystem/shell tools granted to generation session
- source metadata persisted with answers
- artifact HTML passes through sanitization + sandbox isolation
- failure paths return stable, explainable codes
