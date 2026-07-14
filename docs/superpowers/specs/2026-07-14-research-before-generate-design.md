# Design: Research Before Generate（联网资料 → 再生成图文）

**Date:** 2026-07-14  
**Status:** Approved  
**Goal:** 解决小红书图文「内容空洞」——API 生成路径在写正文 / `image_suggestions` 之前，必须用 Claude web search 拉最新公开资料，并把事实锚点与外部观点注入生成结果。

## Background

当前链路是：选题 → 直接 `generate_note`（仅 brand / pillars / compliance / topic 元数据）→ 配图规划。没有联网检索，图上只能堆框架金句（如「流量≠收入」），缺少日期、事件、官方口径或外部代表性判断。

## Decisions (locked)

| Question | Choice |
|----------|--------|
| Where does research live? | **A** — baked into the code pipeline (`generate_note` path) |
| Which topics? | **A** — all topics run research |
| What must land on content images? | **C** — fact anchors **and** external viewpoints |
| Search backend? | **A** — Claude Messages API `web_search` tool |
| Implementation shape? | **Approach 2** — two-phase: research brief → generate (no hard per-image gate yet) |

## Architecture

```text
topics.csv / Topic
        │
        ▼
┌─────────────────────────┐
│ research_topic()          │  Claude + web_search
│ → research_brief JSON     │  facts / viewpoints / sources
└───────────┬─────────────┘
            │ inject into prompt
            ▼
┌─────────────────────────┐
│ generate (existing)       │  generate_note.md + brief
│ → titles / body /         │
│   image_suggestions       │
│ → finalize image_prompts  │
└───────────┬─────────────┘
            ▼
  publish package JSON (includes research_brief)
```

### Component boundaries

| Component | Responsibility |
|-----------|----------------|
| `src/xhs_workflow/research.py` (new) | Build research prompt, call web-search client, validate/normalize brief, format brief for generation prompt |
| `src/xhs_workflow/claude_client.py` | Add `complete_json_with_web_search`; keep existing `complete_json` unchanged |
| `prompts/research_note.md` (new) | Research-only template: must search public web; no fabrication |
| `prompts/generate_note.md` | Add `{research_brief}` placeholder + density rules for content images |
| `src/xhs_workflow/generate.py` | Per topic: research → generate → write `research_brief` into result |
| `src/xhs_workflow/draft_package.py` | Optional hand-written `research_brief` in drafts; if missing, mark compliance as 未联网核验 |
| `src/xhs_workflow/packages.py` | Brief rides in `raw` / package JSON; when `research_brief` is present, Markdown includes a short「联网资料摘要」section (facts/viewpoints counts + `query_summary`) |
| Publish / image automation | **Unchanged** |

## Data model: `research_brief`

```json
{
  "query_summary": "本次检索意图一句话",
  "as_of": "YYYY-MM-DD",
  "facts": [
    {
      "claim": "可核对的事实锚点（含时间/事件/公开口径）",
      "source_name": "来源名",
      "source_url": "https://...",
      "confidence": "high | medium | low"
    }
  ],
  "viewpoints": [
    {
      "summary": "外部代表性判断（改写，不挂真实账号 ID）",
      "stance": "bullish | bearish | neutral | mixed",
      "source_name": "来源类型，如 财经媒体/分析师观点/社区讨论",
      "source_url": "https://...",
      "confidence": "high | medium | low"
    }
  ],
  "gaps": ["没搜到或不确定、生成时需回避的点"],
  "risk_notes": ["金融/时效相关的合规提醒"]
}
```

**Soft targets:** ≥3 `facts` and ≥2 `viewpoints`. If search cannot fill the quota, record shortfalls in `gaps` — never invent claims.

## Prompt rules (generation)

1. Inject the full `research_brief` into `generate_note.md`.
2. Every **content** slide (not cover/ending) in `image_suggestions` must reference at least **one fact anchor** and **one viewpoint anchor** in its 补充说明 (may be paraphrased; no fake personal experience).
3. Body copy must use concrete material from the brief; framework-only slogans without anchors are not enough.
4. Existing financial compliance red lines stay: no stock picks, no return promises, no leverage parameters; influencer views must be anonymized/rewritten.
5. `compliance_check` should note whether networked sources were used; drafts without a brief mark「未联网核验」.

## Claude web search API

- New client method: `complete_json_with_web_search(prompt, system, max_tokens=..., max_uses=...)`.
- Tool: `web_search_20250305` with `name: "web_search"` and `allowed_callers: ["direct"]` for compatibility with the current default model (`claude-sonnet-4-5`).
- Default `max_uses`: **5** (overridable via `CLAUDE_WEB_SEARCH_MAX_USES`).
- Parse final assistant text with existing `extract_json_object`.
- Research system prompt must **steer Claude to always search** (all topics), not answer from training data alone.

## Error handling

| Failure | Behavior |
|---------|----------|
| Missing API key / anthropic package | `ClaudeConfigError` (existing) |
| Web search unavailable / research call fails | `ResearchError` — **abort that topic**; do not silently generate hollow copy |
| Research response not JSON / missing `facts` or `viewpoints` keys | `ResearchError` |
| Generation failure | Same as today |
| Local debug skip | Only if `XHS_SKIP_RESEARCH=1` (explicit): skip the research API call, omit `research_brief` (or set `null`), and add compliance note「已跳过联网检索(XHS_SKIP_RESEARCH)」. Default path never auto-degrades. |

## Draft / no-API path

- If draft JSON includes `research_brief`, copy into package `raw` unchanged.
- If absent: do not call Claude; add compliance note「未联网核验」.
- No automatic research in `create_package.py` (no API mode by design).

## Testing

All in `tests/test_core.py` with `unittest`; never hit real network or Anthropic.

- **ResearchTests:** prompt assembly, brief formatting, structure validation (pure functions).
- **PromptTests:** checked-in `generate_note.md` includes `{research_brief}` and fact+viewpoint image rules; research template exists with required strings.
- **Generation flow:** mock `research_topic` + `complete_json`; assert call order and that `research_brief` is written into the finalized result.
- **DraftPackageTests:** with / without `research_brief`.

## Out of scope (YAGNI)

- Hard gate rejecting packages when a content slide fails to cite the brief (Approach 3 — later).
- Third-party search APIs (Tavily / SerpAPI) or dedicated Twitter scrapers.
- Changes to ChatGPT image automation or Xiaohongshu publish CLI.
- Auto-research inside no-API draft creation.

## Docs / rules sync

After implementation, update `AGENTS.md` §8 and `.cursor/rules/xhs-workflow.mdc` with one business rule: API note generation must run web research first and persist `research_brief` in the package/archive payload.

## Success criteria

1. `PYTHONPATH=src python3 src/generate_note.py` (when used) produces packages whose JSON contains a populated `research_brief`.
2. Generated `image_suggestions` for content slides carry concrete fact + viewpoint anchors derived from the brief.
3. Unit tests cover research + injection without live API calls.
4. Skipping research requires an explicit env flag; failure does not fall back to hollow generation.
