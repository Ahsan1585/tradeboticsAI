# Model-Efficiency Router Subagent — Design

## Purpose

An advisory-only subagent, invoked by the orchestrator (Claude Code) before delegating work, that classifies task complexity and recommends the cheapest Claude model tier sufficient for that task. It never performs the task itself and never changes its own model — a subagent definition's `model` field is fixed at dispatch time by the orchestrator, so "switching models" happens through the orchestrator acting on this agent's recommendation, not through the subagent reconfiguring itself mid-run.

## Location & Scope

- File: `~/.claude/agents/model-router.md`
- Scope: global (all projects) — model routing is a generic concern, not specific to any one codebase.

## Agent Configuration

- **Model:** `claude-haiku-4-5` — classification is a lightweight judgment call, not deep reasoning, so the cheapest tier is sufficient for the advisor itself.
- **Tools:** `Read`, `Glob`, `Grep` only. No `Bash`, `Write`, `Edit`, or `Agent` — the advisor inspects context if needed but never acts and never self-dispatches.

## Input Contract

The orchestrator calls this agent with:
- A description of the task about to be delegated.
- Optionally, relevant file paths or code snippets if the complexity judgment depends on code the advisor hasn't seen.

## Output Contract

A short structured report:

```
recommended_model: haiku | sonnet | opus | fable
reasoning: one or two sentences
requires_user_confirmation: true|false   # always true when recommended_model is opus or fable
```

## Decision Heuristic (cheapest first)

| Tier | Price ($/MTok in/out) | Use for |
|---|---|---|
| Haiku | $1 / $5 | Classification, extraction, simple lookups, short deterministic transforms, boilerplate generation |
| Sonnet (default when unsure) | $3 / $15 | Most coding/agentic work, multi-file reasoning, typical debugging and feature implementation |
| Opus | $5 / $25 | Complex architecture decisions, security-critical review, long-horizon multi-step reasoning |
| Fable | $10 / $50 | Only the hardest long-horizon/reasoning tasks, or when the user has explicitly asked for maximum capability |

Sonnet is the fallback tier when the advisor is uncertain — it is not reserved only for "obviously medium" tasks.

## Escalation Gate

Any `opus` or `fable` recommendation is advisory only. The orchestrator surfaces it to the user via `AskUserQuestion` before dispatching the real work at that tier. `haiku`/`sonnet` recommendations proceed without asking — these are routine, low-stakes cost decisions.

## Non-Goals

- This agent does not execute the delegated task.
- This agent does not have the ability to change its own model mid-run (not possible in the current subagent architecture — only the orchestrator's `model` param at dispatch time selects a model).
- This agent is not a general-purpose executor; it is purely a classifier/advisor.
