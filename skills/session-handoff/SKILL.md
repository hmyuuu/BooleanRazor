---
name: session-handoff
description: Use when one session has completed or advanced work and another session needs compact context to continue, including requests like "handoff to session X" or "have a session handoff".
---

# Session Handoff

Use this when work from the current session should continue in another session.

Write a compact handoff message and send it to the next session when a delivery tool is available. If no delivery tool is available, give the user the message and say it was not sent.

If the user passed arguments, treat them as the next session focus. Shape `Focus`, `Next`, and `Suggested Skills` around that focus.

## Template

```markdown
Focus: <what the next session should work on>

State:
- Repo/path: `<path>`
- Branch/commit: `<branch>` / `<sha>`
- PR/issue: <number or link>

Done:
- <completed work from this session>

References:
- <paths or URLs for PRDs, plans, issues, commits, diffs, docs>

Next:
1. <next action>
2. <next action>

Suggested Skills:
- <skill name>: <why the next session should use it>

Do Not Assume:
- <unfinished work, caveat, boundary, or missing proof>

Ask Human If:
- <decision, blocked proof, or policy choice>
```

## Rules

- Keep the message short enough to read in one screen.
- Reference existing artifacts by path or URL. Do not duplicate PRDs, plans, ADRs, issues, commits, or diffs.
- Redact API keys, passwords, tokens, private keys, `.env` values, and personally identifiable information.
- Do not claim completion without proof. Put missing proof, failed proof, caveats, and human decisions in `Ask Human If`.

## Final Pass

Cut filler. Use concrete paths, commits, commands, issue numbers, and skill names. Remove anything the next session can read from a linked artifact.
