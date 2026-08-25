# Artifact Generation Skill

Purpose: generate a complete Markdown or HTML/CSS artifact derived from the current conversation and grounded transcript evidence.

For Markdown:
- Produce a complete readable document with headings, lists/tables when useful, and [S#] citations.

For HTML:
- Produce a complete self-contained HTML fragment or document with inline CSS.
- Prefer semantic HTML and responsive CSS.
- Never include JavaScript, script tags, external iframes, forms, object/embed tags, tracking pixels, remote scripts, or event-handler attributes.
- Do not require external assets to communicate the core information.
- Include source references as visible text when the artifact makes grounded claims.

The frontend will sanitize HTML and render it in a sandboxed iframe; do not attempt to bypass that isolation.
