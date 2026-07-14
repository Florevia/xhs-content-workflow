# Research Before Generate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** API note generation runs Claude web search first, injects a structured `research_brief` into `generate_note`, and persists the brief in package JSON/Markdown so image copy stops being hollow.

**Architecture:** Two-phase: `research_topic()` (web_search → brief JSON) then existing generate path with `{research_brief}` in the prompt. Draft/no-API path keeps optional hand-written briefs and marks「未联网核验」when absent.

**Tech Stack:** Python 3 stdlib + `anthropic` Messages API `web_search_20250305`, `unittest`.

---

## File map

| File | Role |
|------|------|
| `src/xhs_workflow/research.py` | New: prompt build, validate, format, `research_topic` |
| `src/xhs_workflow/claude_client.py` | Add `complete_json_with_web_search` |
| `prompts/research_note.md` | New research template |
| `prompts/generate_note.md` | Inject brief + density rules |
| `src/xhs_workflow/generate.py` | Wire research → generate |
| `src/xhs_workflow/packages.py` | Markdown「联网资料摘要」 |
| `src/xhs_workflow/draft_package.py` | Brief passthrough / 未联网核验 |
| `tests/test_core.py` | ResearchTests + prompt/generate/draft/package cases |
| `.env.example`, `AGENTS.md`, `.cursor/rules/xhs-workflow.mdc` | Config + rule #9 |

- [x] Task 1: Research module (TDD)
- [x] Task 2: Claude web search client method
- [x] Task 3: Prompts (`research_note.md` + `generate_note.md`)
- [x] Task 4: Wire `generate.py` + skip flag
- [x] Task 5: Packages markdown summary
- [x] Task 6: Draft package compliance note
- [x] Task 7: Docs/rules/env sync
- [x] Task 8: Full test suite + py_compile (64 tests OK)

See design: `docs/superpowers/specs/2026-07-14-research-before-generate-design.md`
