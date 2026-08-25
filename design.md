# Design — The Lenny Growth Assistant

## Design principles

1. **Trust before novelty.** Sources should be easy to inspect; the product should make its grounding visible.
2. **Chat is primary, artifacts are secondary.** The artifact viewer appears only when needed and never navigates the user away from the conversation.
3. **Model choice is explicit.** Local vs cloud is visible at the top of the product so users know where generation occurs.
4. **Progressive disclosure.** Source cards live under expandable sections to keep answers readable while preserving traceability.
5. **Operational states are product states.** Missing Ollama, cloud keys, or data should produce understandable UI errors rather than generic failures.

## Information architecture

- Left sidebar: New Chat + persisted chat list
- Top bar: product identity, model selector, mode selector
- Main chat: messages, citations/sources, loading/error states
- Composer: prompt, artifact type, quick actions
- Right panel: rendered artifact + security indicator

## Key states

### Empty / first use

A short welcome message explains the three supported jobs: grounded Q&A, Ship30 essay, artifacts. Example actions reduce blank-page friction.

### Retrieval/generation

The UI displays a concise status: "Retrieving transcripts and generating a grounded answer…" It does not pretend retrieval and generation are instantaneous.

### Answer with sources

The answer uses readable Markdown. A collapsed Source section shows episode/guest/excerpt and a link back to the transcript.

### Insufficient evidence

The assistant states that indexed transcripts do not support the answer. It does not fill the response with general model knowledge.

### Failure

Errors appear near the conversation composer and are written as user-actionable descriptions (for example, local model unavailable).

### Artifact open

Desktop: chat and artifact are side-by-side. Mobile/tablet: artifact becomes a full-width overlay under the fixed top region.

## Responsive behavior

- >980 px: two-column chat + artifact when artifact is open.
- 700–980 px: artifact overlays chat to preserve readable width.
- <700 px: sidebar becomes off-canvas, toolbar labels collapse, composer/source cards remain touch friendly.

## Accessibility

- semantic buttons, labels, details/summary source disclosure
- iframe has a descriptive title
- artifact panel has an accessible label
- controls include aria-labels where icon-only
- no reliance on color alone for model/security/error meaning
- reasonable text contrast and scalable system fonts
- keyboard Enter sends, Shift+Enter inserts newline

## Artifact viewer security UX

A small security banner says HTML is sanitized and rendered without script permissions. This makes a technical safety decision visible without overwhelming the main experience.

## Visual choices

The UI intentionally uses neutral backgrounds, restrained borders, and one dark primary action rather than a colorful dashboard. This keeps attention on research/content and resembles a professional internal tool.
