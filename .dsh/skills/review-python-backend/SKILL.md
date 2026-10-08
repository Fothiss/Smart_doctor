---
name: review-python-backend
description: Use when reviewing Python backend changes — a diff, a pull request, a new endpoint/service/schema, or a self-check after writing backend code. Produces findings by severity with evidence and a concrete fix, instead of style nitpicks. Not for frontend, infrastructure, or Dockerfile review.
---

# Python Backend Review

## Workflow

1. **Scope the review.** If given a diff, work only from it. If asked to "review a module", first read its callers: router → service → client.
2. **Read project rules if present.** `AGENTS.md`, `CONVENTIONS.md`, `CONTRIBUTING.md` at the repo root. Violating a documented rule is always a `blocker`.
3. **Walk the checklist by group** (below) — only over changed code and its immediate surroundings.
4. **Trust tool output, not your eyes.** Run whatever the project has configured (`ruff`, `mypy`, `pytest`, `pre-commit`). If tests are missing or the linter is weak, that is a finding — not a reason to skip the check.
5. **Emit the report** in the format below. Do not restate the code — go straight to findings.

## Checklist by group

| Group | What to look for |
|---|---|
| Architecture and layers | logic in the router/controller, service aware of transport, circular imports, global config instead of an argument |
| Async and concurrency | blocking I/O inside `async def`, missing `await`, `lru_cache` on async, races under concurrent requests |
| Error handling | bare `except`, swallowed exception, `raise` without `from`, internals leaked into the response, wrong 4xx/5xx codes |
| Types and validation | manual checks instead of a schema, mutable defaults, incomplete serialization, `str` constants instead of `StrEnum` |
| Security | path traversal in filenames, missing size/type limits on uploads, secrets in code, unauthenticated endpoints |
| Data and transactions | partial writes without rollback, missing uniqueness, N+1, missing indexes |
| Resources | loading an entire file into memory, recreating a client/model per request, unbounded `limit` |
| Tests and observability | no test for a new branch, test without assert, logs without identifiers, missing timeouts on external calls |

## Report format

Start with a one-line verdict, then findings in descending severity.
